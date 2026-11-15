"""B 显式代执行接受:完整预验在事务外,决定和授权关联原子追加。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field
from sqlalchemy import Connection, insert, select

from paper_radar.body import BodyService
from paper_radar.body.queries import decision_events
from paper_radar.calibration import visibility
from paper_radar.config import resolve_config_snapshot_reference
from paper_radar.experiment.candidates import SnapshotModel
from paper_radar.experiment.reasons import AcceptanceReason
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.experiment.selections import SelectionRecord, Selections
from paper_radar.feed_metadata.repository import canonical, sha, transaction
from paper_radar.papers import PaperFacts, resolve_revision
from paper_radar.screening.reasons import ScreeningReasonInput
from paper_radar.screening.schema import BoundaryOutput, ValuePredictionOutput
from paper_radar.screening_tasks import ScreeningTasks, TaskError
from paper_radar.screening_tasks.success_models import SuccessContent
from paper_radar.storage.schema import body_decisions, experiment_acceptances


class AcceptanceError(ValueError):
    def __init__(self, reason: AcceptanceReason | str) -> None:
        self.reason = reason = AcceptanceReason(reason)
        super().__init__(
            f"{reason}：代执行接受未完成；请回查有效 selection、冻结版本及所选快照的"
            "两阶段成功；授权变化须由所有者重新选样，请求冲突请使用新 request。"
        )


class AcceptanceRequest(SnapshotModel):
    paper_id: str = Field(min_length=1)
    selection_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1, max_length=128)


class DelegatedAcceptance(SnapshotModel):
    acceptance_id: str
    request: AcceptanceRequest
    root_id: str
    version_id: str
    revision_no: int
    decision_id: str
    boundary_success_id: str
    value_success_id: str
    authorizer: Literal["owner"] = "owner"
    actor: Literal["agent"] = "agent"
    explanation: Literal["依预先选样授权代执行"] = "依预先选样授权代执行"
    accepted_at: str


def _reason() -> ScreeningReasonInput:
    return ScreeningReasonInput.model_validate(
        dict(result="accepted", source="direct_manual_decision", reason="user_judgment")
    )


def _body_request(request_id: str) -> str:
    return f"b-accept-{sha(request_id)}"


def _visibility() -> None:
    if (
        visibility.evaluate_visibility(frozenset()).permission(
            visibility.VisibilityCapability.SET_DECISION
        )
        is not visibility.VisibilityPermission.ALLOWED
    ):
        raise AcceptanceError("visibility_denied")


def _outputs(boundary: SuccessContent, value: SuccessContent) -> None:
    if (
        boundary.receipt.executor_kind != "pi_rpc"
        or value.receipt.executor_kind != "pi_rpc"
    ):
        raise AcceptanceError("test_source")
    if not isinstance(boundary.output, BoundaryOutput) or not isinstance(
        value.output, ValuePredictionOutput
    ):
        raise AcceptanceError("success_mismatch")
    if boundary.output.boundary == "out_of_scope":
        raise AcceptanceError("out_of_scope")


class Acceptances:
    """查询接受 database/data_root,因此备份恢复无需原根路径。"""

    def __init__(self, database: Path, data_root: Path) -> None:
        self.database, self.data_root = database, data_root

    def _records(self, connection: Connection) -> tuple[DelegatedAcceptance, ...]:
        result = []
        try:
            for row in connection.execute(
                select(experiment_acceptances).order_by(
                    experiment_acceptances.c.acceptance_id
                )
            ).mappings():
                record = DelegatedAcceptance.model_validate_json(row["record_json"])
                if (
                    record.acceptance_id
                    != sha(
                        canonical(
                            record.model_dump(mode="json", exclude={"acceptance_id"})
                        )
                    )
                    or row["record_json"] != canonical(record.model_dump(mode="json"))
                    or any(
                        row[key] != value
                        for key, value in dict(
                            acceptance_id=record.acceptance_id,
                            request_id=record.request.request_id,
                            selection_id=record.request.selection_id,
                            decision_id=record.decision_id,
                            boundary_success_id=record.boundary_success_id,
                            value_success_id=record.value_success_id,
                        ).items()
                    )
                    or datetime.fromisoformat(record.accepted_at).utcoffset()
                    != UTC.utcoffset(None)
                ):
                    raise ValueError
                result.append(record)
        except (ValueError, TypeError, KeyError):
            raise AcceptanceError("registration_invalid") from None
        return tuple(result)

    def history(self) -> tuple[DelegatedAcceptance, ...]:
        tasks = ScreeningTasks(
            self.database, self.data_root, clock=lambda: datetime.now(UTC)
        )
        with transaction(self.database) as connection:
            # 授权、关联和标记使用同一只读快照,并发追加不能被误报为损坏。
            selections = Selections(
                self.database, self.data_root
            ).history_in_connection(connection)
            records = self._records(connection)
            delegated_decisions = set(
                connection.execute(
                    select(body_decisions.c.decision_id).where(
                        body_decisions.c.delegation_kind == "stage_b_preselection"
                    )
                ).scalars()
            )
        try:
            if delegated_decisions != {r.decision_id for r in records}:
                raise ValueError
            for record in records:
                selected = next(
                    s
                    for s in selections
                    if s.selection_id == record.request.selection_id
                )
                if (
                    record.root_id,
                    record.request.paper_id,
                    record.version_id,
                    record.revision_no,
                ) != (
                    selected.root_id,
                    selected.paper_id,
                    selected.version_id,
                    selected.revision_no,
                ):
                    raise ValueError
                boundary = tasks.load_success(record.boundary_success_id)
                value = tasks.load_success(record.value_success_id)
                _outputs(boundary, value)
                mapping = PaperFacts(self.database).map_screening_inputs(
                    version_id=record.version_id,
                    revision_no=record.revision_no,
                    snapshot_id=record.request.snapshot_id,
                )
                with transaction(self.database) as connection:
                    for content in (boundary, value):
                        tasks.require_success_reference_in_connection(
                            connection,
                            content,
                            paper_id=selected.paper_id,
                            mapping=mapping,
                        )
                    event = next(
                        e
                        for e in decision_events(connection, selected.paper_id)
                        if e.fact.reference == record.decision_id
                    )
                    body_row = (
                        connection.execute(
                            select(body_decisions).where(
                                body_decisions.c.decision_id == record.decision_id
                            )
                        )
                        .mappings()
                        .one()
                    )
                    if (
                        event.fact.record != _reason()
                        or event.actor != "agent"
                        or event.version_id != record.version_id
                        or event.revision_no != record.revision_no
                        or event.screening_references
                        != tuple(
                            sorted(
                                (record.boundary_success_id, record.value_success_id)
                            )
                        )
                        or body_row["request_id"]
                        != _body_request(record.request.request_id)
                        or body_row["delegation_kind"] != "stage_b_preselection"
                        or event.decided_at != record.accepted_at
                    ):
                        raise ValueError
            return records
        except (ValueError, StopIteration, TaskError):
            raise AcceptanceError("registration_invalid") from None

    def accept(
        self,
        root: ExperimentRoot,
        *,
        paper_id: str,
        selection_id: str,
        snapshot: str,
        request_id: str,
    ) -> tuple[DelegatedAcceptance, bool]:
        root.require()
        _visibility()
        if not all(
            type(v) is str and v.strip()
            for v in (paper_id, selection_id, snapshot, request_id)
        ):
            raise AcceptanceError("invalid_request")
        snapshot_id = resolve_config_snapshot_reference(self.database, snapshot)
        try:
            request = AcceptanceRequest(
                paper_id=paper_id,
                selection_id=selection_id,
                snapshot_id=snapshot_id,
                request_id=request_id,
            )
        except ValueError:
            raise AcceptanceError("invalid_request") from None
        for old in self.history():
            if old.request.request_id == request_id:
                if old.request != request:
                    raise AcceptanceError("request_conflict")
                return old, True
        selections = Selections(self.database, self.data_root)
        history = selections.history()
        if not history or history[-1].selection_id != selection_id:
            raise AcceptanceError("selection_changed")
        selected: SelectionRecord = history[-1]
        if selected.paper_id != paper_id:
            raise AcceptanceError("selection_mismatch")
        with transaction(self.database) as connection:
            revision = resolve_revision(connection, paper_id=paper_id)
            if (revision.version_id, revision.revision_no) != (
                selected.version_id,
                selected.revision_no,
            ):
                raise AcceptanceError("frozen_version_changed")
        tasks = ScreeningTasks(
            self.database, self.data_root, clock=lambda: datetime.now(UTC)
        )
        contents = []
        for stage in ("boundary", "value"):
            current = next(
                (
                    s
                    for s in tasks.query_successes(
                        paper_id=paper_id, stage=stage, snapshot_id=snapshot_id
                    )
                    if s.applicability == "current"
                ),
                None,
            )
            if current is None:
                raise AcceptanceError(f"{stage}_missing")
            content = tasks.load_success(current.receipt.success_id)
            if content.receipt.executor_kind != "pi_rpc":
                raise AcceptanceError("test_source")
            if (
                isinstance(content.output, BoundaryOutput)
                and content.output.boundary == "out_of_scope"
            ):
                raise AcceptanceError("out_of_scope")
            contents.append(content)
        boundary, value = contents
        _outputs(boundary, value)
        mapping = PaperFacts(self.database).map_screening_inputs(
            paper_id=paper_id, snapshot_id=snapshot_id
        )
        with transaction(self.database, write=True) as connection:
            _visibility()
            for old in self._records(connection):
                if old.request.request_id == request_id:
                    if old.request != request:
                        raise AcceptanceError("request_conflict")
                    return old, True
                if old.request.selection_id == selection_id:
                    raise AcceptanceError("already_accepted")
            selections.require_current_in_connection(connection, selected)
            revision = resolve_revision(connection, paper_id=paper_id)
            if (revision.version_id, revision.revision_no) != (
                selected.version_id,
                selected.revision_no,
            ):
                raise AcceptanceError("frozen_version_changed")
            for content in contents:
                tasks.require_current_success_in_connection(
                    connection, content, paper_id=paper_id, mapping=mapping
                )
            event = BodyService(self.database, self.data_root).decide_in_connection(
                connection,
                paper_id,
                _reason(),
                request_id=_body_request(request_id),
                actor="agent",
                screening_references=(
                    boundary.receipt.success_id,
                    value.receipt.success_id,
                ),
                delegation_kind="stage_b_preselection",
            )
            payload = dict(
                request=request.model_dump(mode="json"),
                root_id=selected.root_id,
                version_id=selected.version_id,
                revision_no=selected.revision_no,
                decision_id=event.fact.reference,
                boundary_success_id=boundary.receipt.success_id,
                value_success_id=value.receipt.success_id,
                authorizer="owner",
                actor="agent",
                explanation="依预先选样授权代执行",
                accepted_at=event.decided_at,
            )
            record = DelegatedAcceptance.model_validate(
                dict(acceptance_id=sha(canonical(payload)), **payload)
            )
            connection.execute(
                insert(experiment_acceptances).values(
                    acceptance_id=record.acceptance_id,
                    request_id=request_id,
                    selection_id=selection_id,
                    decision_id=record.decision_id,
                    boundary_success_id=record.boundary_success_id,
                    value_success_id=record.value_success_id,
                    record_json=canonical(record.model_dump(mode="json")),
                )
            )
            return record, False

    def validate_all(self) -> None:
        self.history()


def receipt(
    record: DelegatedAcceptance, *, replayed: bool = False
) -> dict[str, object]:
    return dict(
        acceptance_id=record.acceptance_id,
        decision_id=record.decision_id,
        paper_id=record.request.paper_id,
        selection_id=record.request.selection_id,
        version_id=record.version_id,
        revision_no=record.revision_no,
        boundary_success_id=record.boundary_success_id,
        value_success_id=record.value_success_id,
        authorizer=record.authorizer,
        actor=record.actor,
        explanation=record.explanation,
        accepted_at=record.accepted_at,
        replayed=replayed,
    )
