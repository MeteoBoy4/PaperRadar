"""实验报告的固定输入、原子发布与只读恢复;SQLite 是唯一事实源。"""

import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Connection, func, insert, select, update

from paper_radar.body import BodyService
from paper_radar.body.models import BodyError, DecisionMetadata
from paper_radar.calibration import visibility
from paper_radar.doctor.admission import report_admission_fragment
from paper_radar.eligibility import RootPurpose
from paper_radar.experiment.acceptance import Acceptances, DelegatedAcceptance
from paper_radar.experiment.reading import analysis_payload
from paper_radar.experiment.report_rendering import ReportEntry, ReportInput, render
from paper_radar.experiment.selections import SelectionRecord, Selections
from paper_radar.feed_ingestion import JGRFeed
from paper_radar.feed_ingestion import tables as feed_tables
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.feed_metadata import tables as metadata_tables
from paper_radar.feed_metadata.repository import canonical, sha, transaction
from paper_radar.papers import PaperFacts
from paper_radar.read_tasks import ReadTasks
from paper_radar.runtime_logging import RuntimeLog, Sink
from paper_radar.runtime_logging.events import Clock
from paper_radar.screening.reasons import ScreeningResult
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.screening_tasks import tables as screening_tables
from paper_radar.storage.filesystem import (
    UnsafePathError,
    controlled_path,
    sync_directory,
)
from paper_radar.storage.history import (
    HistoryBoundary,
    HistoryKeys,
    HistoryPage,
    history_boundaries,
    history_page,
)
from paper_radar.storage.schema import report_entries, report_runs


class ReportError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{reason}：报告操作停止；请核对报告身份、固定成员、制品闭包与受控路径；"
            "篡改先 verify，缺失投影可 rebuild；不重新执行模型。"
        )


def _visible() -> None:
    if (
        visibility.evaluate_visibility(frozenset()).permission(
            visibility.VisibilityCapability.AGENT_CONTENT
        )
        is not visibility.VisibilityPermission.ALLOWED
    ):
        raise ReportError("visibility_denied")


def _day(day: str, timezone: str) -> None:
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
        ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise ReportError("invalid_date_timezone") from None


class Reports:
    """显式 database/data_root/output_dir;恢复无需执行根布局,重建从不写库。"""

    def exposure_scope_in_connection(
        self, connection: Connection
    ) -> dict[str, HistoryBoundary]:
        """短写事务使用的只读事件范围元数据;不加载历史或文件。"""
        return history_boundaries(connection, (report_entries,))

    def exposure_history_in_connection(
        self, connection: Connection, through: dict[str, HistoryKeys] | None = None
    ) -> tuple[HistoryPage, ...]:
        """持久历史安全投影;保留全部事件,与当前执行资格无关。"""
        return (
            history_page(
                connection,
                report_entries,
                (
                    "report_id",
                    "position",
                    "paper_id",
                    "version_id",
                    "revision_no",
                    "primary_kind",
                    "primary_ref",
                    "projection_json",
                ),
                through=through,
                hashed=("projection_json",),
            ),
        )

    def __init__(
        self,
        database: Path,
        data_root: Path,
        output_dir: Path,
        *,
        clock: Clock | None = None,
        sink: Sink | None = None,
    ) -> None:
        self.database, self.data_root, self.output_dir = database, data_root, output_dir
        self.clock = clock or (lambda: datetime.now(UTC))
        self.log = RuntimeLog(sink, clock=clock)

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReportError("invalid_clock")
        return value.astimezone(UTC)

    def _root(self) -> str:
        fact = BodyService(self.database, self.data_root).root()
        if fact.purpose is not RootPurpose.EXPERIMENT or fact.root_id is None:
            raise ReportError("ordinary_consumption_denied")
        return fact.root_id

    def _find(self, key: str) -> str | None:
        with transaction(self.database) as connection:
            return connection.execute(
                select(report_runs.c.report_id).where(report_runs.c.run_key == key)
            ).scalar_one_or_none()

    def _load(self, report_id: str) -> tuple[ReportInput, dict[str, Any]]:
        try:
            with transaction(self.database) as connection:
                row = (
                    connection.execute(
                        select(report_runs).where(report_runs.c.report_id == report_id)
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    raise ReportError("report_not_found")
                inputs = ReportInput.model_validate_json(row["projection_json"])
                entries = tuple(
                    ReportEntry.model_validate_json(r["projection_json"])
                    for r in connection.execute(
                        select(report_entries)
                        .where(report_entries.c.report_id == report_id)
                        .order_by(report_entries.c.position)
                    ).mappings()
                )
                # 每个规范列都和冻结输入相符,不能只验证 JSON 的自洽哈希。
                stored = (
                    connection.execute(
                        select(report_entries)
                        .where(report_entries.c.report_id == report_id)
                        .order_by(report_entries.c.position)
                    )
                    .mappings()
                    .all()
                )
                for entry, record in zip(entries, stored, strict=True):
                    fields = entry.model_dump(
                        exclude={"available_at", "title", "basis"}
                    )
                    if any(record[k] != v for k, v in fields.items()):
                        raise ValueError
                    expected = (
                        entry.first_publication_key if inputs.kind == "daily" else None
                    )
                    if record["daily_first_key"] != expected:
                        raise ValueError
                payload = canonical(inputs.model_dump(mode="json"))
                expected_key = canonical(
                    [inputs.root_id, inputs.kind, inputs.entries[0].analysis_id]
                    if inputs.kind == "paper"
                    else [inputs.root_id, inputs.kind, inputs.report_date]
                )
                if (
                    inputs.report_id != report_id
                    or entries != inputs.entries
                    or payload != row["projection_json"]
                    or sha(payload) != row["input_fingerprint"]
                    or row["run_key"] != expected_key
                    or row["relative_path"] != inputs.relative_path
                    or any(
                        row[k] != getattr(inputs, k)
                        for k in (
                            "kind",
                            "scope",
                            "report_date",
                            "timezone",
                            "renderer_version",
                        )
                    )
                    or sha(render(inputs)) != row["content_sha256"]
                    or (row["state"] == "published")
                    != (row["published_at"] is not None)
                    or inputs.root_id != self._root()
                ):
                    raise ValueError
                return inputs, dict(row)
        except ReportError:
            raise
        except (ValueError, KeyError, TypeError, IndexError):
            raise ReportError("registration_invalid") from None

    def _source_records(
        self,
    ) -> tuple[tuple[DelegatedAcceptance, ...], tuple[SelectionRecord, ...]]:
        return (
            Acceptances(self.database, self.data_root).history(),
            Selections(self.database, self.data_root).history(),
        )

    def _analysis_entry(
        self,
        analysis_id: str,
        snapshot_id: str | None,
        records: tuple[tuple[DelegatedAcceptance, ...], tuple[SelectionRecord, ...]],
    ) -> ReportEntry:
        tasks = ReadTasks(self.database, self.data_root)
        analysis = tasks.analysis(analysis_id)
        if analysis.root_purpose != "experiment" or analysis.executor_kind != "pi_rpc":
            raise ReportError("analysis_scope_invalid")
        task = tasks.task(analysis.task_id)
        attempt = task.attempts[analysis.attempt_ordinal - 1]
        acceptance = next(
            (
                a
                for a in records[0]
                if a.decision_id == attempt.basis.get("decision_id")
            ),
            None,
        )
        if acceptance is None or attempt.settled_at is None:
            raise ReportError("registration_invalid")
        selection = next(
            (
                s
                for s in records[1]
                if s.selection_id == acceptance.request.selection_id
            ),
            None,
        )
        if selection is None:
            raise ReportError("registration_invalid")
        revision = PaperFacts(self.database, self.data_root).revision(
            acceptance.version_id, acceptance.revision_no
        )
        title = revision.fields["title"].value
        if not isinstance(title, str):
            raise ReportError("registration_invalid")
        screening = ScreeningTasks(self.database, self.data_root, clock=self._now)
        outputs = {}
        for stage, success_id in (
            ("boundary", acceptance.boundary_success_id),
            ("value", acceptance.value_success_id),
        ):
            success = screening.load_success(success_id)
            outputs[stage] = dict(
                success_id=success_id,
                artifact_id=success.receipt.artifact_id,
                output=success.output.model_dump(mode="json"),
            )
        payload = analysis_payload(
            self.database, self.data_root, analysis_id, snapshot_id=snapshot_id
        )
        return ReportEntry(
            position=1,
            display_number="N1",
            paper_id=analysis.paper_id,
            version_id=acceptance.version_id,
            revision_no=acceptance.revision_no,
            primary_kind="analysis",
            primary_ref=analysis_id,
            analysis_id=analysis_id,
            supporting_success_id=acceptance.value_success_id,
            section="transferable"
            if set(analysis.output.value_types) & {"method", "data", "code_tool"}
            else "cognitive",
            first_publication_key=f"analysis:{analysis_id}",
            available_at=attempt.settled_at.isoformat(),
            title=title,
            basis=dict(
                analysis=payload,
                screening=outputs,
                acceptance=acceptance.model_dump(mode="json"),
                authorization=selection.model_dump(mode="json"),
            ),
        )

    def _candidates(self, snapshot_id: str | None) -> tuple[ReportEntry, ...]:
        tasks = ReadTasks(self.database, self.data_root)
        records = self._source_records()
        result = [
            self._analysis_entry(key, snapshot_id, records)
            for paper in tasks.papers()
            for key in tasks.analysis_ids(paper)
        ]
        analyses = sorted(
            result, key=lambda e: (e.available_at, e.paper_id, e.primary_ref)
        )
        others = self._nonanalysis_candidates(records)
        return tuple(
            [
                *analyses,
                *sorted(
                    others, key=lambda e: (e.available_at, e.paper_id, e.primary_ref)
                ),
            ]
        )

    def _nonanalysis_entry(
        self,
        selection: SelectionRecord,
        success_id: str,
        *,
        kind: Literal["pending", "blocked"],
        reference: str,
        available_at: str,
        fact: dict[str, Any],
        acceptance: dict[str, Any] | None,
        decision_scope: dict[str, Any],
    ) -> ReportEntry:
        revision = PaperFacts(self.database, self.data_root).revision(
            selection.version_id, selection.revision_no
        )
        title = revision.fields["title"].value
        if not isinstance(title, str):
            raise ReportError("registration_invalid")
        success = ScreeningTasks(self.database, self.data_root).load_success(success_id)
        if (
            success.receipt.executor_kind != "pi_rpc"
            or success.receipt.stage != "value"
        ):
            raise ReportError("registration_invalid")
        return ReportEntry(
            position=1,
            display_number="N1",
            paper_id=selection.paper_id,
            version_id=selection.version_id,
            revision_no=selection.revision_no,
            primary_kind=kind,
            primary_ref=reference,
            supporting_success_id=success_id,
            section=kind,
            first_publication_key=f"{kind}:{reference}",
            available_at=available_at,
            title=title,
            basis=dict(
                screening=dict(
                    value=dict(
                        success_id=success_id,
                        artifact_id=success.receipt.artifact_id,
                        output=success.output.model_dump(mode="json"),
                    )
                ),
                acceptance=acceptance,
                authorization=selection.model_dump(mode="json"),
                fact=fact,
                decision_scope=decision_scope,
            ),
        )

    def _nonanalysis_candidates(
        self,
        records: tuple[tuple[DelegatedAcceptance, ...], tuple[SelectionRecord, ...]],
    ) -> list[ReportEntry]:
        acceptances, selections = records
        accepted = {a.value_success_id: a for a in acceptances}
        tasks = ScreeningTasks(self.database, self.data_root)
        body = BodyService(self.database, self.data_root)
        result = []
        for selection in selections:
            current = PaperFacts(self.database, self.data_root).show(selection.paper_id)
            if (current.version_id, current.revision_no) != (
                selection.version_id,
                selection.revision_no,
            ):
                continue
            with transaction(self.database) as connection:
                metadata = self._decision_metadata(connection, selection.paper_id)
                scope = self._decision_scope(metadata)
                accepted_ids = {a.decision_id for a in acceptances}
                if any(
                    d.result is ScreeningResult.ACCEPTED
                    and d.decision_id not in accepted_ids
                    for d in metadata
                ):
                    raise ReportError("facts_changed")
                ids = tuple(
                    connection.execute(
                        select(screening_tables.successes.c.success_id)
                        .join(
                            screening_tables.budgets,
                            screening_tables.successes.c.budget_id
                            == screening_tables.budgets.c.budget_id,
                        )
                        .where(
                            screening_tables.budgets.c.paper_id == selection.paper_id,
                            screening_tables.budgets.c.stage == "value",
                            screening_tables.budgets.c.version_id
                            == selection.version_id,
                            screening_tables.budgets.c.revision_no
                            == selection.revision_no,
                        )
                    ).scalars()
                )
            for success_id in ids:
                success = tasks.load_success(success_id)
                if success.receipt.executor_kind != "pi_rpc":
                    continue
                acceptance = accepted.get(success_id)
                if acceptance is None:
                    result.append(
                        self._nonanalysis_entry(
                            selection,
                            success_id,
                            kind="pending",
                            reference=success_id,
                            available_at=success.receipt.settled_at.isoformat(),
                            fact=dict(
                                kind="pending",
                                next_action="实验建议无决定权；由所有者显式代执行接受或换样。",
                            ),
                            acceptance=None,
                            decision_scope=scope,
                        )
                    )
                    continue
                if body.current_pdf(selection.paper_id) is None:
                    result.append(
                        self._nonanalysis_entry(
                            selection,
                            success_id,
                            kind="blocked",
                            reference=f"needs-pdf:{acceptance.decision_id}",
                            available_at=acceptance.accepted_at,
                            fact=dict(
                                kind="needs_pdf",
                                decision_id=acceptance.decision_id,
                                next_action="所有者确认合法 PDF 后显式 attach-pdf。",
                            ),
                            acceptance=acceptance.model_dump(mode="json"),
                            decision_scope=scope,
                        )
                    )
                else:
                    for extraction in body.extractions(selection.paper_id):
                        if extraction.artifact_id or not extraction.attempts:
                            continue
                        last = extraction.attempts[-1]
                        if (
                            last.failure is None
                            or last.settled_at is None
                            or (
                                not extraction.permanent_failure
                                and extraction.remaining_attempts
                            )
                        ):
                            continue
                        result.append(
                            self._nonanalysis_entry(
                                selection,
                                success_id,
                                kind="blocked",
                                reference=f"extraction:{last.attempt_id}",
                                available_at=last.settled_at,
                                fact=dict(
                                    kind=last.failure.value,
                                    attempt_id=last.attempt_id,
                                    fingerprint=extraction.fingerprint,
                                    next_action="检查解析失败和版式；保留质量失败，由所有者决定下一步，不自动重试。",
                                ),
                                acceptance=acceptance.model_dump(mode="json"),
                                decision_scope=scope,
                            )
                        )
        # 同一冻结版本可被多次选回;相同制品只生成一个发布键。
        return list({e.first_publication_key: e for e in reversed(result)}.values())

    def _decision_metadata(
        self, connection: Connection, paper_id: str
    ) -> tuple[DecisionMetadata, ...]:
        try:
            return BodyService(
                self.database, self.data_root
            ).decision_metadata_in_connection(connection, paper_id)
        except BodyError:
            raise ReportError("registration_invalid") from None

    @staticmethod
    def _decision_scope(metadata: tuple[DecisionMetadata, ...]) -> dict[str, Any]:
        return dict(
            through_sequence=metadata[-1].sequence if metadata else 0,
            boundary_decision_id=metadata[-1].decision_id if metadata else None,
            decisions_sha256=sha(
                canonical(
                    [[d.decision_id, d.sequence, d.result.value] for d in metadata]
                )
            ),
        )

    def _summary(
        self, candidates: tuple[ReportEntry, ...]
    ) -> tuple[dict[str, int], tuple[str, ...]]:
        warnings: list[str] = []
        with transaction(self.database) as connection:
            checks = connection.execute(
                select(
                    feed_tables.checks.c.check_id, feed_tables.checks.c.feed_id
                ).order_by(feed_tables.checks.c.event_no)
            ).all()
            metadata = tuple(
                connection.execute(select(metadata_tables.runs.c.request_key)).scalars()
            )
            screenings = connection.execute(
                select(func.count()).select_from(screening_tables.successes)
            ).scalar_one()
            published = set(
                connection.execute(
                    select(report_entries.c.daily_first_key).where(
                        report_entries.c.daily_first_key.is_not(None)
                    )
                ).scalars()
            )
            budgets = connection.execute(
                select(
                    screening_tables.budgets.c.paper_id,
                    screening_tables.budgets.c.snapshot_id,
                )
            ).all()
        # 仅当前最新来源检查决定来源健康;历史失败仍由各组件回查。
        latest = {feed_id: check for check, feed_id in checks}
        for check in latest.values():
            view = JGRFeed(self.database, self.data_root).replay(check)
            if not view.complete or any(i.reason is not None for i in view.items):
                warnings.append(
                    f"Feed 异常：check={check} reason={view.reason}；"
                    "下一步：回查原 Feed 检查与条目。"
                )
        metadata_service = JGRMetadata(self.database, self.data_root)
        latest_metadata = {}
        for key in metadata:
            view_metadata = metadata_service.replay(key)
            latest_metadata[view_metadata.paper_id] = view_metadata
        for view_metadata in latest_metadata.values():
            if not view_metadata.nontruncated_complete:
                warnings.append(
                    f"元数据不可得：paper={view_metadata.paper_id} "
                    f"reason={','.join(view_metadata.missing)}；"
                    "下一步：回查元数据路线，不解释为无新论文。"
                )
        screening = ScreeningTasks(self.database, self.data_root, clock=self._now)
        failed_screening: set[tuple[str, str]] = set()
        for snapshot in {snapshot for _paper, snapshot in budgets}:
            for failure in screening.failures(snapshot_id=snapshot):
                failed_screening.add((failure.task.task_id, failure.stage))
        for task_id, stage in sorted(failed_screening):
            warnings.append(
                f"模型失败：task={task_id} stage={stage}；"
                "下一步：screening failures/retry，由所有者显式恢复。"
            )
        reads = ReadTasks(self.database, self.data_root)
        analysis_count = 0
        for paper in reads.papers():
            analysis_count += len(reads.analysis_ids(paper))
            latest_tasks = {task.fingerprint: task for task in reads.history(paper)}
            for task in latest_tasks.values():
                if task.status == "failed":
                    warnings.append(
                        f"Read 模型失败：paper={paper} task={task.task_id}；"
                        f"下一步：reading retry {paper} --snapshot {task.snapshot_id} "
                        "--request-id REQUEST --reason REASON --actor owner。"
                    )
        for entry in candidates:
            if entry.primary_kind == "blocked":
                warnings.append(
                    f"PDF/解析受阻：paper={entry.paper_id} "
                    f"reason={entry.basis['fact']['kind']}；"
                    "下一步：核对合法 PDF 或原解析失败。"
                )
        return {
            "抓取": len(checks),
            "筛选": screenings,
            "精读": analysis_count,
            "积压": sum(e.first_publication_key not in published for e in candidates),
        }, tuple(dict.fromkeys(warnings))

    def render(
        self,
        *,
        day: str,
        timezone: str,
        analysis_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        """显式发布:首次冻结,随后只复用;daily 与 paper 修订身份分开。"""
        _visible()
        _day(day, timezone)
        root_id = self._root()
        kind: Literal["daily", "paper"] = "paper" if analysis_id else "daily"
        key = canonical(
            [root_id, kind, analysis_id] if analysis_id else [root_id, kind, day]
        )
        with self.log.execution("experiment", controlled=(ReportError,)):
            old = self._find(key)
            if old is None:
                now = self._now()
                candidates = self._candidates(snapshot_id)
                if analysis_id:
                    candidates = tuple(
                        e for e in candidates if e.analysis_id == analysis_id
                    )
                    if len(candidates) != 1:
                        raise ReportError("analysis_not_found")
                summary, warnings = self._summary(candidates)
                admission = report_admission_fragment(
                    self.database, snapshot_id=snapshot_id, now=now
                )
                with transaction(self.database, write=True) as connection:
                    old = connection.execute(
                        select(report_runs.c.report_id).where(
                            report_runs.c.run_key == key
                        )
                    ).scalar_one_or_none()
                    if old is None:
                        used = set(
                            connection.execute(
                                select(report_entries.c.daily_first_key).where(
                                    report_entries.c.daily_first_key.is_not(None)
                                )
                            ).scalars()
                        )
                        chosen: list[ReportEntry] = []
                        for entry in candidates:
                            if kind == "daily" and entry.first_publication_key in used:
                                continue
                            if len(chosen) == 5 or (
                                entry.primary_kind == "analysis"
                                and sum(e.primary_kind == "analysis" for e in chosen)
                                == 3
                            ):
                                continue
                            position = len(chosen) + 1
                            if entry.primary_kind != "analysis" and (
                                self._decision_scope(
                                    self._decision_metadata(connection, entry.paper_id)
                                )
                                != entry.basis["decision_scope"]
                            ):
                                raise ReportError("facts_changed")
                            chosen.append(
                                entry.model_copy(
                                    update={
                                        "position": position,
                                        "display_number": f"N{position}",
                                    }
                                )
                            )
                        inputs = ReportInput(
                            report_id=str(uuid4()),
                            kind=kind,
                            root_id=root_id,
                            report_date=day,
                            timezone=timezone,
                            snapshot_id=snapshot_id,
                            frozen_at=now.isoformat(),
                            admission_fragment=admission,
                            summary=summary,
                            warnings=warnings,
                            entries=tuple(chosen),
                        )
                        payload = canonical(inputs.model_dump(mode="json"))
                        connection.execute(
                            insert(report_runs).values(
                                report_id=inputs.report_id,
                                run_key=key,
                                kind=kind,
                                scope="experiment",
                                report_date=day,
                                timezone=timezone,
                                input_fingerprint=sha(payload),
                                projection_json=payload,
                                renderer_version=1,
                                relative_path=inputs.relative_path,
                                content_sha256=sha(render(inputs)),
                                state="prepared",
                            )
                        )
                        for entry in chosen:
                            connection.execute(
                                insert(report_entries).values(
                                    report_id=inputs.report_id,
                                    **entry.model_dump(
                                        exclude={"available_at", "title", "basis"}
                                    ),
                                    daily_first_key=entry.first_publication_key
                                    if kind == "daily"
                                    else None,
                                    projection_json=canonical(
                                        entry.model_dump(mode="json")
                                    ),
                                )
                            )
                        old = inputs.report_id
            self.rebuild(old)
            with transaction(self.database, write=True) as connection:
                connection.execute(
                    update(report_runs)
                    .where(
                        report_runs.c.report_id == old,
                        report_runs.c.state == "prepared",
                    )
                    .values(state="published", published_at=self._now().isoformat())
                )
            return self.receipt(old)

    def _path(self, relative: str, *, create: bool) -> Path:
        try:
            # 输出根自身及全部现有祖先拒绝软链;不能将任意路径解析成获准目录。
            for parent in (self.output_dir, *self.output_dir.parents):
                if parent.is_symlink():
                    raise UnsafePathError
            return controlled_path(
                self.output_dir,
                relative,
                create_directory=(
                    lambda p: p.mkdir(parents=True, exist_ok=True, mode=0o700)
                )
                if create
                else None,
            )
        except (UnsafePathError, OSError):
            raise ReportError("unsafe_path") from None

    def _validate_sources(self, inputs: ReportInput) -> None:
        records = self._source_records() if inputs.entries else ((), ())
        for entry in inputs.entries:
            if entry.primary_kind != "analysis":
                self._validate_nonanalysis(entry, records)
                continue
            current = self._analysis_entry(
                entry.primary_ref, inputs.snapshot_id, records
            )
            frozen_basis = dict(entry.basis)
            current_basis = dict(current.basis)
            for basis in (frozen_basis, current_basis):
                basis["analysis"] = {
                    k: v
                    for k, v in basis["analysis"].items()
                    if k not in {"body_status", "config_status"}
                }
            if (
                canonical(frozen_basis) != canonical(current_basis)
                or entry.title != current.title
                or entry.paper_id != current.paper_id
                or entry.version_id != current.version_id
                or entry.revision_no != current.revision_no
                or entry.supporting_success_id != current.supporting_success_id
                or entry.section != current.section
                or entry.available_at != current.available_at
            ):
                raise ReportError("registration_invalid")

    def _validate_nonanalysis(
        self,
        entry: ReportEntry,
        records: tuple[tuple[DelegatedAcceptance, ...], tuple[SelectionRecord, ...]],
    ) -> None:
        try:
            if entry.primary_kind == "analysis":
                raise ValueError
            selection = SelectionRecord.model_validate_json(
                canonical(entry.basis["authorization"])
            )
            if selection not in records[1]:
                raise ValueError
            success_id = entry.supporting_success_id
            if success_id is None:
                raise ValueError
            acceptance = entry.basis["acceptance"]
            fact = entry.basis["fact"]
            scope = entry.basis["decision_scope"]
            if (
                type(scope) is not dict
                or set(scope)
                != {"through_sequence", "boundary_decision_id", "decisions_sha256"}
                or type(scope["through_sequence"]) is not int
                or scope["through_sequence"] < 0
            ):
                raise ValueError
            with transaction(self.database) as connection:
                metadata = self._decision_metadata(connection, entry.paper_id)
            bounded = tuple(
                d for d in metadata if d.sequence <= scope["through_sequence"]
            )
            if self._decision_scope(bounded) != scope:
                raise ValueError
            accepted_ids = {
                d.decision_id for d in bounded if d.result is ScreeningResult.ACCEPTED
            }
            if not accepted_ids <= {a.decision_id for a in records[0]}:
                raise ValueError
            if entry.primary_kind == "pending":
                success = ScreeningTasks(self.database, self.data_root).load_success(
                    success_id
                )
                if (
                    entry.primary_ref != success_id
                    or entry.available_at != success.receipt.settled_at.isoformat()
                    or acceptance is not None
                ):
                    raise ValueError
                if any(
                    a.value_success_id == success_id and a.decision_id in accepted_ids
                    for a in records[0]
                ):
                    raise ValueError
            else:
                record = next(
                    (a for a in records[0] if a.model_dump(mode="json") == acceptance),
                    None,
                )
                if (
                    record is None
                    or record.value_success_id != success_id
                    or record.decision_id not in accepted_ids
                ):
                    raise ValueError
                if fact["kind"] == "needs_pdf":
                    if (
                        entry.primary_ref != f"needs-pdf:{record.decision_id}"
                        or entry.available_at != record.accepted_at
                        or fact["decision_id"] != record.decision_id
                    ):
                        raise ValueError
                else:
                    attempts = [
                        a
                        for x in BodyService(self.database, self.data_root).extractions(
                            entry.paper_id
                        )
                        if x.fingerprint == fact["fingerprint"]
                        for a in x.attempts
                    ]
                    attempt = next(
                        (a for a in attempts if a.attempt_id == fact["attempt_id"]),
                        None,
                    )
                    if (
                        attempt is None
                        or attempt.failure is None
                        or fact["kind"] != attempt.failure.value
                        or entry.primary_ref != f"extraction:{attempt.attempt_id}"
                        or entry.available_at != attempt.settled_at
                    ):
                        raise ValueError
            expected = self._nonanalysis_entry(
                selection,
                success_id,
                kind=entry.primary_kind,
                reference=entry.primary_ref,
                available_at=entry.available_at,
                fact=fact,
                acceptance=acceptance,
                decision_scope=scope,
            )
            if (
                entry.paper_id,
                entry.version_id,
                entry.revision_no,
                entry.title,
                entry.section,
                canonical(entry.basis),
            ) != (
                expected.paper_id,
                expected.version_id,
                expected.revision_no,
                expected.title,
                expected.section,
                canonical(expected.basis),
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError, StopIteration):
            raise ReportError("registration_invalid") from None

    def rebuild(self, report_id: str) -> dict[str, object]:
        """仅恢复投影文件;可接受 prepared run,不更新发布状态、库或任务。"""
        _visible()
        inputs, row = self._load(report_id)
        self._validate_sources(inputs)
        content = render(inputs)
        path = self._path(inputs.relative_path, create=True)
        if path.exists() and not path.is_file():
            raise ReportError("unsafe_path")
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=".report-", delete=False
            ) as stream:
                temporary = stream.name
                stream.write(content)
                stream.flush()
                if sha(Path(temporary).read_bytes()) != row["content_sha256"]:
                    raise ReportError("content_corrupt")
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
            sync_directory(path.parent)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        return self.receipt(report_id)

    def verify(self, report_id: str) -> dict[str, object]:
        _visible()
        inputs, row = self._load(report_id)
        self._validate_sources(inputs)
        path = self._path(inputs.relative_path, create=False)
        if not path.is_file():
            raise ReportError("file_missing")
        if sha(path.read_bytes()) != row["content_sha256"]:
            raise ReportError("content_corrupt")
        return self.receipt(report_id)

    def receipt(self, report_id: str) -> dict[str, object]:
        inputs, row = self._load(report_id)
        return dict(
            report_id=report_id,
            kind=inputs.kind,
            scope=inputs.scope,
            report_date=inputs.report_date,
            timezone=inputs.timezone,
            state=row["state"],
            relative_path=inputs.relative_path,
            input_fingerprint=row["input_fingerprint"],
            content_sha256=row["content_sha256"],
            members=[
                dict(
                    paper_id=e.paper_id,
                    primary_kind=e.primary_kind,
                    primary_ref=e.primary_ref,
                    display_number=e.display_number,
                    section=e.section,
                    first_publication_key=e.first_publication_key,
                )
                for e in inputs.entries
            ],
        )

    def validate_all(self) -> None:
        with transaction(self.database) as connection:
            ids = tuple(connection.execute(select(report_runs.c.report_id)).scalars())
            dangling = connection.execute(
                select(report_entries.c.report_id)
                .outerjoin(
                    report_runs, report_entries.c.report_id == report_runs.c.report_id
                )
                .where(report_runs.c.report_id.is_(None))
            ).first()
        if dangling:
            raise ReportError("registration_invalid")
        for report_id in ids:
            inputs, _row = self._load(report_id)
            self._validate_sources(inputs)

    def history(self) -> tuple[ReportInput, ...]:
        """获准私有历史;保留原primary/supporting与paper/version,不猜当前性。"""
        _visible()
        with transaction(self.database) as connection:
            ids = tuple(
                connection.execute(
                    select(report_runs.c.report_id).order_by(
                        report_runs.c.report_date, report_runs.c.report_id
                    )
                ).scalars()
            )
        result = []
        for report_id in ids:
            inputs, _row = self._load(report_id)
            self._validate_sources(inputs)
            result.append(inputs)
        return tuple(result)
