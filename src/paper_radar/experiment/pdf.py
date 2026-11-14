"""所有者 PDF 确认先持久化;附加、冻结及关联在同一事务完成。"""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field
from sqlalchemy import Connection, insert, select

from paper_radar.body import BodyService
from paper_radar.body.pdf import valid_pdf_bytes
from paper_radar.body.queries import current_pdf, root_fact
from paper_radar.calibration import visibility
from paper_radar.experiment.acceptance import Acceptances, DelegatedAcceptance
from paper_radar.experiment.candidates import SnapshotModel
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.experiment.selections import SelectionRecord, Selections
from paper_radar.feed_metadata.repository import canonical, sha, transaction
from paper_radar.papers.queries import load_trace, resolve_revision
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.history import (
    HistoryBoundary,
    HistoryKeys,
    HistoryPage,
    history_boundaries,
    history_page,
)
from paper_radar.storage.schema import (
    body_pdfs,
    body_samples,
    experiment_frozen_samples,
    experiment_pdf_confirmations,
    experiment_selections,
)


class PdfError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{reason}：PDF 确认或冻结未完成；请核对所有者归属与合法性确认、"
            "有效 selection/accepted、冻结版本和文件 SHA-256；"
            "中断可用同 request 续办，内容冲突须用新 request。"
        )


class PdfRequest(SnapshotModel):
    paper_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    selection_id: str = Field(min_length=1)
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str = Field(min_length=1, max_length=128)
    owner: Literal["owner"] = "owner"
    actor: Literal["owner", "agent"]
    ownership_confirmed: Literal[True] = True
    lawful_copy_confirmed: Literal[True] = True


class PdfConfirmation(SnapshotModel):
    confirmation_id: str
    root_id: str
    request: PdfRequest
    revision_no: int
    acceptance_id: str
    confirmed_at: str


class FrozenSample(SnapshotModel):
    confirmation_id: str
    attachment_id: str
    sample_id: str
    selection_id: str
    acceptance_id: str
    paper_id: str
    version_id: str
    revision_no: int
    pdf_sha256: str
    feed_id: str
    discovery_id: str
    source_check_id: str
    reason_selection_id: str
    frozen_at: str


def _visibility() -> None:
    if (
        visibility.evaluate_visibility(frozenset()).permission(
            visibility.VisibilityCapability.SET_DECISION
        )
        is not visibility.VisibilityPermission.ALLOWED
    ):
        raise PdfError("visibility_denied")


def _body_request(confirmation_id: str) -> str:
    return f"b-pdf-{confirmation_id}"


class PdfSamples:
    """database/data_root 显式,只读历史不要求原路径或当前授权。"""

    def exposure_scope_in_connection(
        self, connection: Connection
    ) -> dict[str, HistoryBoundary]:
        """短写事务使用的只读事件范围元数据;不加载历史或文件。"""
        return history_boundaries(connection, (experiment_pdf_confirmations,))

    def exposure_history_in_connection(
        self, connection: Connection, through: dict[str, HistoryKeys] | None = None
    ) -> tuple[HistoryPage, ...]:
        """持久历史安全投影;保留全部事件,与当前执行资格无关。"""
        return (
            history_page(
                connection,
                experiment_pdf_confirmations,
                ("confirmation_id", "paper_id", "version_id", "record_json"),
                through=through,
                hashed=("record_json",),
            ),
        )

    def __init__(
        self,
        database: Path,
        data_root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database, self.data_root = database, data_root
        self.clock = clock or (lambda: datetime.now(UTC))

    def _records(self, connection: Connection) -> tuple[PdfConfirmation, ...]:
        records = []
        try:
            for row in connection.execute(
                select(experiment_pdf_confirmations).order_by(
                    experiment_pdf_confirmations.c.confirmation_id
                )
            ).mappings():
                record = PdfConfirmation.model_validate_json(row["record_json"])
                if (
                    record.confirmation_id
                    != sha(
                        canonical(
                            record.model_dump(mode="json", exclude={"confirmation_id"})
                        )
                    )
                    or row["record_json"] != canonical(record.model_dump(mode="json"))
                    or any(
                        row[key] != value
                        for key, value in dict(
                            confirmation_id=record.confirmation_id,
                            request_id=record.request.request_id,
                            selection_id=record.request.selection_id,
                            acceptance_id=record.acceptance_id,
                            paper_id=record.request.paper_id,
                            version_id=record.request.version_id,
                        ).items()
                    )
                    or datetime.fromisoformat(record.confirmed_at).utcoffset()
                    != UTC.utcoffset(None)
                ):
                    raise ValueError
                records.append(record)
        except (ValueError, TypeError, KeyError):
            raise PdfError("registration_invalid") from None
        return tuple(records)

    def history(self) -> tuple[PdfConfirmation, ...]:
        """完整核验确认历史,允许仅确认的可续办状态。"""
        return self._validated_history()[0]

    def samples(self) -> tuple[FrozenSample, ...]:
        """确认、关联及安全投影在同一只读快照核验,允许并发滞后。"""
        return self._validated_history()[1]

    def _validated_history(
        self,
    ) -> tuple[tuple[PdfConfirmation, ...], tuple[FrozenSample, ...]]:
        store = ArtifactStore(self.database, self.data_root)
        with transaction(self.database) as connection:
            records = self._records(connection)
            samples: list[tuple[int, FrozenSample]] = []
            selections = Selections(
                self.database, self.data_root
            ).history_in_connection(connection)
            acceptances = Acceptances(self.database, self.data_root).history()
            linked = {
                r["confirmation_id"]: r
                for r in connection.execute(
                    select(experiment_frozen_samples)
                ).mappings()
            }
            marked = (
                connection.execute(
                    select(body_pdfs).where(body_pdfs.c.confirmation_id.is_not(None))
                )
                .mappings()
                .all()
            )
            try:
                if {r["attachment_id"] for r in marked} != {
                    r["attachment_id"] for r in linked.values()
                }:
                    raise ValueError
                if not set(linked) <= {r.confirmation_id for r in records}:
                    raise ValueError
                root = root_fact(connection)
                for record in records:
                    selected = next(
                        s
                        for s in selections
                        if s.selection_id == record.request.selection_id
                    )
                    acceptance = next(
                        a
                        for a in acceptances
                        if a.acceptance_id == record.acceptance_id
                    )
                    if (
                        (
                            record.root_id,
                            record.request.paper_id,
                            record.request.version_id,
                            record.revision_no,
                        )
                        != (
                            root.root_id,
                            selected.paper_id,
                            selected.version_id,
                            selected.revision_no,
                        )
                        or acceptance.request.selection_id != selected.selection_id
                        or datetime.fromisoformat(record.confirmed_at)
                        < datetime.fromisoformat(acceptance.accepted_at)
                    ):
                        raise ValueError
                    if record.confirmation_id not in linked:
                        continue
                    relation = linked[record.confirmation_id]
                    pdf = next(
                        p
                        for p in marked
                        if p["attachment_id"] == relation["attachment_id"]
                    )
                    sample = (
                        connection.execute(
                            select(body_samples).where(
                                body_samples.c.sample_id == relation["sample_id"]
                            )
                        )
                        .mappings()
                        .one()
                    )
                    discovery = next(
                        d
                        for d in load_trace(connection, selected.paper_id).discoveries
                        if d.discovery_id == selected.discovery_id
                    )
                    expected = (
                        selected.paper_id,
                        selected.version_id,
                        record.request.pdf_sha256,
                    )
                    if (
                        (pdf["paper_id"], pdf["version_id"], pdf["pdf_sha256"])
                        != expected
                        or pdf["confirmation_id"] != record.confirmation_id
                        or pdf["requested_version_id"] != selected.version_id
                        or pdf["request_id"] != _body_request(record.confirmation_id)
                        or (
                            sample["paper_id"],
                            sample["version_id"],
                            sample["pdf_sha256"],
                        )
                        != expected
                        or sample["feed_id"] != discovery.feed_id
                        or sample["reason"] != selected.request.reason
                        or sample["request_id"] != _body_request(record.confirmation_id)
                        or datetime.fromisoformat(pdf["attached_at"])
                        < datetime.fromisoformat(record.confirmed_at)
                        or datetime.fromisoformat(sample["frozen_at"])
                        < datetime.fromisoformat(pdf["attached_at"])
                        or not valid_pdf_bytes(
                            store.read_artifact_in_connection(
                                connection, pdf["artifact_id"]
                            )["payload"],
                            record.request.pdf_sha256,
                        )
                    ):
                        raise ValueError
                    samples.append(
                        (
                            sample["sequence"],
                            FrozenSample(
                                confirmation_id=record.confirmation_id,
                                attachment_id=relation["attachment_id"],
                                sample_id=sample["sample_id"],
                                selection_id=selected.selection_id,
                                acceptance_id=record.acceptance_id,
                                paper_id=selected.paper_id,
                                version_id=selected.version_id,
                                revision_no=selected.revision_no,
                                pdf_sha256=record.request.pdf_sha256,
                                feed_id=sample["feed_id"],
                                discovery_id=selected.discovery_id,
                                source_check_id=selected.source_check_id,
                                reason_selection_id=selected.selection_id,
                                frozen_at=sample["frozen_at"],
                            ),
                        )
                    )
                return records, tuple(
                    item[1]
                    for item in sorted(
                        samples, key=lambda item: (item[1].paper_id, item[0])
                    )
                )
            except (ValueError, StopIteration, TypeError, KeyError):
                raise PdfError("registration_invalid") from None

    def _require_confirmation_current(
        self, connection: Connection, record: PdfConfirmation, selected: SelectionRecord
    ) -> None:
        """附加事务内重核确认归属;PDF/样本尚未追加。"""
        _visibility()
        Selections(self.database, self.data_root).require_current_in_connection(
            connection, selected
        )
        revision = resolve_revision(connection, paper_id=selected.paper_id)
        if (revision.version_id, revision.revision_no) != (
            selected.version_id,
            selected.revision_no,
        ):
            raise PdfError("frozen_version_changed")
        if (
            record.request.paper_id,
            record.request.version_id,
            record.request.selection_id,
        ) != (selected.paper_id, selected.version_id, selected.selection_id):
            raise PdfError("confirmation_mismatch")

    def require_current_sample(self, paper_id: str) -> FrozenSample:
        """正文产品入口的前置核验;样本只能匹配当前选样/版本/最新 PDF。"""
        samples = self.samples()
        selections = Selections(self.database, self.data_root).history()
        if not selections or selections[-1].paper_id != paper_id:
            raise PdfError("selection_changed")
        candidates = [s for s in samples if s.paper_id == paper_id]
        if not candidates:
            raise PdfError("sample_missing")
        sample = candidates[-1]
        with transaction(self.database) as connection:
            self.require_current_sample_in_connection(connection, sample)
        return sample

    def require_current_sample_in_connection(
        self, connection: Connection, validated: FrozenSample
    ) -> None:
        """重读事务外完整核验的样本,供正文领取前复查,不作文件 I/O。"""
        selected = (
            connection.execute(
                select(experiment_selections)
                .order_by(experiment_selections.c.sequence.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if selected is None or selected["selection_id"] != validated.selection_id:
            raise PdfError("selection_changed")
        revision = resolve_revision(connection, paper_id=validated.paper_id)
        if (revision.version_id, revision.revision_no) != (
            validated.version_id,
            validated.revision_no,
        ):
            raise PdfError("frozen_version_changed")
        pdf = current_pdf(connection, validated.paper_id, validated.version_id)
        latest = connection.execute(
            select(body_samples.c.sample_id)
            .where(body_samples.c.paper_id == validated.paper_id)
            .order_by(body_samples.c.sequence.desc())
        ).scalar()
        relation = (
            connection.execute(
                select(experiment_frozen_samples).where(
                    experiment_frozen_samples.c.confirmation_id
                    == validated.confirmation_id
                )
            )
            .mappings()
            .first()
        )
        if (
            pdf is None
            or relation is None
            or (pdf.attachment_id, pdf.pdf_sha256, latest)
            != (validated.attachment_id, validated.pdf_sha256, validated.sample_id)
            or (relation["attachment_id"], relation["sample_id"])
            != (validated.attachment_id, validated.sample_id)
        ):
            raise PdfError("sample_mismatch")

    def attach(
        self,
        root: ExperimentRoot,
        *,
        paper_id: str,
        version_id: str,
        selection_id: str,
        pdf: bytes,
        pdf_sha256: str,
        request_id: str,
        owner_confirmed: bool,
        actor: str,
    ) -> tuple[PdfConfirmation, FrozenSample, bool]:
        root.require()
        _visibility()
        if owner_confirmed is not True:
            raise PdfError("owner_confirmation_required")
        if actor not in {"owner", "agent"}:
            raise PdfError("invalid_request")
        try:
            request = PdfRequest.model_validate(
                dict(
                    paper_id=paper_id,
                    version_id=version_id,
                    selection_id=selection_id,
                    pdf_sha256=pdf_sha256,
                    request_id=request_id,
                    actor=actor,
                )
            )
            if any(
                not v.strip() for v in (paper_id, version_id, selection_id, request_id)
            ):
                raise ValueError
        except ValueError:
            raise PdfError("invalid_request") from None
        records = self.history()
        previous = next(
            (r for r in records if r.request.request_id == request_id), None
        )
        if previous is not None and previous.request != request:
            raise PdfError("request_conflict")
        if type(pdf) is not bytes or not valid_pdf_bytes(pdf, pdf_sha256):
            raise PdfError("invalid_pdf")
        selections = Selections(self.database, self.data_root).history()
        if not selections or selections[-1].selection_id != selection_id:
            raise PdfError("selection_changed")
        selected = selections[-1]
        if (paper_id, version_id) != (selected.paper_id, selected.version_id):
            raise PdfError("confirmation_mismatch")
        acceptance = next(
            (
                a
                for a in Acceptances(self.database, self.data_root).history()
                if a.request.selection_id == selection_id
            ),
            None,
        )
        if acceptance is None:
            raise PdfError("acceptance_missing")
        with transaction(self.database, write=True) as connection:
            _visibility()
            Selections(self.database, self.data_root).require_current_in_connection(
                connection, selected
            )
            revision = resolve_revision(connection, paper_id=paper_id)
            if (revision.version_id, revision.revision_no) != (
                version_id,
                selected.revision_no,
            ):
                raise PdfError("frozen_version_changed")
            previous = next(
                (
                    r
                    for r in self._records(connection)
                    if r.request.request_id == request_id
                ),
                None,
            )
            if previous is not None:
                if previous.request != request:
                    raise PdfError("request_conflict")
                record = previous
            else:
                record = self._confirm(connection, request, selected, acceptance)
        # PDF 发布在短事务外;发布失败仍保留所有者确认,无附加事实。
        artifact = ArtifactStore(self.database, self.data_root).publish_single(
            "original_pdf", [pdf], expected_sha256=pdf_sha256
        )
        body = BodyService(self.database, self.data_root)
        with transaction(self.database, write=True) as connection:
            self._require_confirmation_current(connection, record, selected)
            old = (
                connection.execute(
                    select(experiment_frozen_samples).where(
                        experiment_frozen_samples.c.confirmation_id
                        == record.confirmation_id
                    )
                )
                .mappings()
                .first()
            )
            if old is None:
                attachment = body.attach_pdf_in_connection(
                    connection,
                    paper_id,
                    pdf_sha256=pdf_sha256,
                    artifact_id=artifact.artifact_id,
                    request_id=_body_request(record.confirmation_id),
                    version_id=version_id,
                    selected_version_id=version_id,
                    confirmation_id=record.confirmation_id,
                )
                discovery = next(
                    d
                    for d in load_trace(connection, paper_id).discoveries
                    if d.discovery_id == selected.discovery_id
                )
                sample = body.freeze_sample_in_connection(
                    connection,
                    paper_id,
                    feed_id=discovery.feed_id,
                    pdf_sha256=pdf_sha256,
                    reason=selected.request.reason,
                    request_id=_body_request(record.confirmation_id),
                )
                connection.execute(
                    insert(experiment_frozen_samples).values(
                        confirmation_id=record.confirmation_id,
                        attachment_id=attachment.attachment_id,
                        sample_id=sample.sample_id,
                    )
                )
            else:
                latest_pdf = current_pdf(connection, paper_id, version_id)
                latest_sample = (
                    connection.execute(
                        select(body_samples)
                        .where(body_samples.c.paper_id == paper_id)
                        .order_by(body_samples.c.sequence.desc())
                    )
                    .mappings()
                    .first()
                )
                if (
                    latest_pdf is None
                    or latest_pdf.attachment_id != old["attachment_id"]
                    or latest_sample is None
                    or latest_sample["sample_id"] != old["sample_id"]
                ):
                    raise PdfError("sample_mismatch")
        sample_view = next(
            s for s in self.samples() if s.confirmation_id == record.confirmation_id
        )
        return record, sample_view, old is not None

    def _confirm(
        self,
        connection: Connection,
        request: PdfRequest,
        selected: SelectionRecord,
        acceptance: DelegatedAcceptance,
    ) -> PdfConfirmation:
        now = self.clock()
        if now.utcoffset() is None or now < datetime.fromisoformat(
            acceptance.accepted_at
        ):
            raise PdfError("invalid_clock")
        payload = dict(
            root_id=selected.root_id,
            request=request.model_dump(mode="json"),
            revision_no=selected.revision_no,
            acceptance_id=acceptance.acceptance_id,
            confirmed_at=now.astimezone(UTC).isoformat(),
        )
        record = PdfConfirmation.model_validate(
            dict(confirmation_id=sha(canonical(payload)), **payload)
        )
        connection.execute(
            insert(experiment_pdf_confirmations).values(
                confirmation_id=record.confirmation_id,
                request_id=request.request_id,
                selection_id=selected.selection_id,
                acceptance_id=record.acceptance_id,
                paper_id=selected.paper_id,
                version_id=selected.version_id,
                record_json=canonical(record.model_dump(mode="json")),
            )
        )
        return record

    def validate_all(self) -> None:
        self.history()


def receipt(
    record: PdfConfirmation,
    sample: FrozenSample | None = None,
    *,
    replayed: bool = False,
) -> dict[str, object]:
    return dict(
        confirmation_id=record.confirmation_id,
        **record.request.model_dump(mode="json"),
        root_id=record.root_id,
        revision_no=record.revision_no,
        acceptance_id=record.acceptance_id,
        confirmed_at=record.confirmed_at,
        **(
            sample.model_dump(
                mode="json",
                exclude={
                    "confirmation_id",
                    "acceptance_id",
                    "selection_id",
                    "paper_id",
                    "version_id",
                    "pdf_sha256",
                    "revision_no",
                },
            )
            if sample
            else {}
        ),
        replayed=replayed,
    )
