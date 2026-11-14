"""B 显式 Read 组合;不拥有第二套质量、预算或接收规则。"""

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import Connection, select

from paper_radar.body import BodyService
from paper_radar.body.models import BodyError
from paper_radar.config import (
    ConfigError,
    load_config_snapshot,
    resolve_config_snapshot_reference,
)
from paper_radar.eligibility import QualityBasis
from paper_radar.experiment.egress import (
    EgressError,
    Grant,
    require_egress_authorization,
    selected_grants,
)
from paper_radar.experiment.layout import LayoutError, LayoutReviews, load_body
from paper_radar.experiment.pdf import FrozenSample, PdfError, PdfSamples
from paper_radar.experiment.root import ExperimentError, ExperimentRoot
from paper_radar.feed_metadata.repository import transaction
from paper_radar.fulltext.models import FulltextError
from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadTask, ReadTaskError, ReadTasks
from paper_radar.read_tasks import tables as t
from paper_radar.read_tasks.preconditions import require_facts
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.runtime_logging import Sink
from paper_radar.runtime_logging.events import Clock
from paper_radar.storage.artifact_contract import ArtifactError
from paper_radar.storage.schema import body_layout_reviews, experiment_layout_recordings


class ReadingError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{reason}：Read 已停止;核对当前选样、PDF、唯一正文、所有者六项核查、"
            "egress-status 与 doctor;running 须等待或显式 reclaim，耗尽须显式 retry;"
            "登记重放不执行，请用 --task-id 继续。"
        )


READING_ERRORS = (
    ReadingError,
    ReadTaskError,
    BodyError,
    ConfigError,
    EgressError,
    LayoutError,
    PdfError,
    ExperimentError,
    ArtifactError,
    FulltextError,
)


def task_payload(task: ReadTask) -> dict[str, object]:
    return dict(
        task_id=task.task_id,
        paper_id=task.paper_id,
        fingerprint=task.fingerprint,
        generation=task.generation,
        parent_task_id=task.parent_task_id,
        snapshot_id=task.snapshot_id,
        identity=asdict(task.identity),
        output_language=task.output_language,
        state=task.status,
        remaining_attempts=task.remaining_attempts,
        analysis_id=task.analysis_id,
        attempts=[
            dict(
                attempt_id=a.attempt_id,
                ordinal=a.ordinal,
                lease_until=a.lease_until.isoformat(),
                settled_at=a.settled_at.isoformat() if a.settled_at else None,
                failure=a.failure.value if a.failure else None,
            )
            for a in task.attempts
        ],
    )


def registration_receipt(tasks: ReadTasks, request_id: str) -> dict[str, object] | None:
    """原登记回执只含不可变身份;不把后来尝试/成功混入重放。"""
    with transaction(tasks.database) as connection:
        row = (
            connection.execute(
                select(t.registrations).where(
                    t.registrations.c.request_id == request_id
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        task = tasks.task(row["task_id"])
        return dict(
            request_id=request_id,
            task_id=task.task_id,
            paper_id=task.paper_id,
            fingerprint=task.fingerprint,
            generation=task.generation,
            snapshot_id=row["snapshot_id"],
            label=row["label"],
            registered_at=row["registered_at"],
        )


class Reading:
    def __init__(
        self,
        root: ExperimentRoot,
        *,
        snapshot: str,
        credentials_dir: Path,
        material_root: Path,
        install_root: Path,
        sink: Sink | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.root, self.snapshot = root, snapshot
        self.credentials_dir, self.material_root = credentials_dir, material_root
        self.install_root, self.sink = install_root, sink
        self.clock = clock

    def _guard(
        self,
        sample: FrozenSample,
        identity: ExtractionIdentity,
        review_id: str,
        grant: Grant,
    ) -> Callable[[Connection], None]:
        def check(connection: Connection) -> None:
            PdfSamples(
                self.root.database, self.root.data_root
            ).require_current_sample_in_connection(connection, sample)
            body = BodyService(self.root.database, self.root.data_root)
            if (
                body.current_body_in_connection(connection, sample.paper_id).identity
                != identity
            ):
                raise ReadingError("body_identity_mismatch")
            require_facts(body, connection, sample.paper_id, identity)
            # 标记与关联都必须存在;actor/request 文本不授予所有者来源。
            if (
                connection.execute(
                    select(experiment_layout_recordings.c.review_id)
                    .join(
                        body_layout_reviews,
                        experiment_layout_recordings.c.review_id
                        == body_layout_reviews.c.review_id,
                    )
                    .where(
                        experiment_layout_recordings.c.review_id == review_id,
                        experiment_layout_recordings.c.sample_id == sample.sample_id,
                        body_layout_reviews.c.recording_kind == "stage_b_owner_review",
                        body_layout_reviews.c.passed == 1,
                    )
                ).first()
                is None
            ):
                raise ReadingError("owner_review_required")
            require_egress_authorization(
                self.root,
                stage=grant.stage,
                provider=grant.provider,
                model=grant.model,
                categories=grant.categories,
                connection=connection,
            )

        return check

    def run(
        self,
        paper: str,
        *,
        identity: ExtractionIdentity,
        request_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, object]:
        from paper_radar.pi_execution import ExecutionRoots
        from paper_radar.read_execution import ReadExecution

        self.root.require()
        if (request_id is None) == (task_id is None):
            raise ReadingError("invalid_execution_mode")
        snapshot = resolve_config_snapshot_reference(self.root.database, self.snapshot)
        tasks = ReadTasks(
            self.root.database, self.root.data_root, sink=self.sink, clock=self.clock
        )
        if request_id is not None:
            old = registration_receipt(tasks, request_id)
            if old is not None:
                # register 独立核对请求摘要;重放不重验当前资格、不认证、不继续。
                tasks.register(
                    paper,
                    snapshot_id=snapshot,
                    extraction_fingerprint=identity.extraction_fingerprint,
                    request_id=request_id,
                )
                old_task = tasks.task(str(old["task_id"]))
                if old_task.identity != identity:
                    raise ReadingError("request_conflict")
                return dict(state="replayed", receipt=old)
        validated = load_body(self.root.database, self.root.data_root, paper, identity)
        if validated.view.quality.basis is not QualityBasis.EXPERIMENT_DOCUMENT_GATE:
            raise ReadingError("document_gate_required")
        reviews = LayoutReviews(self.root.database, self.root.data_root).history(paper)
        owner = next(
            (
                r
                for r in reviews
                if r["sample_id"] == validated.sample.sample_id
                and r["fingerprint"] == identity.extraction_fingerprint
                and r["reading_sha256"] == identity.reading_sha256
                and r["evidence_map_sha256"] == identity.evidence_map_sha256
                and r["passed"] is True
            ),
            None,
        )
        if owner is None:
            raise ReadingError("owner_review_required")
        grant = selected_grants(
            load_config_snapshot(self.root.database, snapshot), ["read"]
        )[0]
        check = self._guard(validated.sample, identity, str(owner["review_id"]), grant)

        registered_task = task_id

        def task_check(connection: Connection) -> None:
            check(connection)
            if registered_task is not None:
                tasks.require_latest_in_connection(connection, registered_task)

        def before() -> None:
            # 文件、完整上游闭包和正文回放在短事务外重新验证。
            current = load_body(
                self.root.database, self.root.data_root, paper, identity
            )
            if current.sample != validated.sample:
                raise ReadingError("sample_changed")
            LayoutReviews(self.root.database, self.root.data_root).history(paper)
            with transaction(self.root.database) as connection:
                task_check(connection)

        before()
        if task_id is None:
            assert request_id is not None
            task, replayed = tasks.register_with_status(
                paper,
                snapshot_id=snapshot,
                extraction_fingerprint=identity.extraction_fingerprint,
                request_id=request_id,
                registration_guard=check,
            )
            receipt = registration_receipt(tasks, request_id)
            if replayed:
                return dict(state="replayed", receipt=receipt)
        else:
            task = tasks.task(task_id)
            if (task.paper_id, task.identity, task.output_language) != (
                paper,
                identity,
                "zh",
            ):
                raise ReadingError("task_scope_mismatch")
            tasks.prepare_execution(task_id, audit_snapshot_id=snapshot)
            receipt = dict(task_id=task_id)
        registered_task = task.task_id
        if task_id is not None and task.status == "succeeded":
            raise ReadTaskError("already_succeeded")
        execution = ReadExecution(
            self.root.database,
            self.root.data_root,
            roots=ExecutionRoots(
                self.root.data_root,
                self.root.config,
                self.material_root,
                self.install_root,
            ),
            credentials_dir=self.credentials_dir,
            auth_mode="chatgpt_subscription",
            sink=self.sink,
            clock=self.clock,
        )
        for _ in range(task.remaining_attempts):
            task = tasks.task(task.task_id)
            if task.status == "running":
                raise ReadingError("task_running")
            if task.status in {"failed", "succeeded"}:
                break
            execution.run_attempt(
                task.task_id,
                audit_snapshot_id=snapshot,
                before_prepare=before,
                claim_guard=task_check,
            )
        task = tasks.task(task.task_id)
        if task.status == "running":
            raise ReadingError("task_running")
        return dict(state=task.status, receipt=receipt, task=task_payload(task))


def analysis_payload(
    database: Path, data_root: Path, analysis_id: str, *, snapshot_id: str | None = None
) -> dict[str, object]:
    """获准私有视图;安全诊断不得调用这个内容投影。"""
    queries = ReadQueries(database, data_root)
    view = queries.analysis(analysis_id, snapshot_id=snapshot_id)
    tasks = ReadTasks(database, data_root)
    accepted = tasks.analysis(analysis_id)
    task = tasks.task(accepted.task_id)
    basis = task.attempts[accepted.attempt_ordinal - 1].basis
    pdf = next(
        (
            p
            for p in tasks.body.pdfs(accepted.paper_id)
            if p.attachment_id == basis.get("pdf_id")
        ),
        None,
    )
    if pdf is None:
        raise ReadTaskError("corrupt_reference")
    output = view.output.model_dump(mode="json")
    evidence_ids: set[str] = set()

    def collect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "evidence_id" and isinstance(child, str):
                    evidence_ids.add(child)
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(output)
    return dict(
        analysis_id=analysis_id,
        task_id=accepted.task_id,
        fingerprint=accepted.fingerprint,
        snapshot_id=task.snapshot_id,
        pdf_sha256=pdf.pdf_sha256,
        sample_id=basis.get("sample_id"),
        paper_id=view.paper_id,
        warning="实验分析：受限内容未核对;表格精确值、公式及不可靠字符须回查 PDF。",
        body_status=view.body_status,
        config_status=view.config_status,
        identity=asdict(view.identity),
        root_purpose=view.root_purpose,
        executor_kind=view.executor_kind,
        quality_basis=view.quality_basis,
        has_discards=view.has_discards,
        discard_counts=[asdict(c) for c in view.discard_counts],
        discards=list(accepted.discards),
        restricted_content_warning=True,
        rule_versions=dict(
            evidence=accepted.evidence_rule_version,
            numeric=accepted.numeric_rule_version,
            limitation=accepted.limitation_rule_version,
        ),
        output=output,
        evidence={
            key: [asdict(s) for s in queries.evidence(analysis_id, key)]
            for key in sorted(evidence_ids)
        },
    )


def validate_read_links(database: Path, data_root: Path) -> None:
    """B 样本的 Read 领取必须引用同样本的结构化所有者核查;旧库事实不补标。"""
    samples = {s.sample_id: s for s in PdfSamples(database, data_root).samples()}
    reviews = {
        str(r["review_id"]): r for r in LayoutReviews(database, data_root).history()
    }
    tasks = ReadTasks(database, data_root)
    for paper in tasks.papers():
        for task in tasks.history(paper):
            for attempt in task.attempts:
                sample_id = attempt.basis.get("sample_id")
                if sample_id not in samples:
                    continue
                review_id = attempt.basis.get("review_id")
                review = reviews.get(review_id) if review_id else None
                if not (
                    review is not None
                    and review["sample_id"] == sample_id
                    and review["paper_id"] == paper
                    and review["passed"] is True
                    and review["fingerprint"] == task.identity.extraction_fingerprint
                    and review["reading_sha256"] == task.identity.reading_sha256
                    and review["evidence_map_sha256"]
                    == task.identity.evidence_map_sha256
                    and attempt.basis.get("quality_basis") == "experiment_document_gate"
                    and attempt.basis.get("purpose") == "experiment"
                ):
                    raise ReadingError("registration_invalid")
