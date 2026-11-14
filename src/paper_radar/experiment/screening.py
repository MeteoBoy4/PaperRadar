"""B 显式 Screening 编排;复用 A7 的事实、预算与权威接收。"""

from dataclasses import asdict
from pathlib import Path

from sqlalchemy import Connection

from paper_radar.config import load_config_snapshot, resolve_config_snapshot_reference
from paper_radar.experiment.egress import (
    EgressError,
    Grant,
    require_egress_authorization,
    selected_grants,
)
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.experiment.selections import (
    SelectionError,
    SelectionRecord,
    Selections,
)
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.feed_metadata.repository import transaction
from paper_radar.feed_pipeline import FeedPipeline
from paper_radar.papers import resolve_revision
from paper_radar.pi_execution import ExecutionRoots
from paper_radar.pi_execution.service import PiExecution
from paper_radar.runtime_logging import Sink
from paper_radar.screening.schema import BoundaryOutput
from paper_radar.screening_tasks import ClaimDenied, RequestReceipt, ScreeningTasks


class ScreenError(ClaimDenied):
    """正常业务拒绝可穿过 A7 事务,不被 ValueError 损坏映射吞掉。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{reason}：Screening 未获继续执行资格；请回查 selection、元数据、"
            "egress-status 与 doctor；需要时由所有者换样或显式 retry。"
        )


def selected_record(root: ExperimentRoot, selection_id: str) -> SelectionRecord:
    root.require()
    records = Selections(root.database, root.data_root).history()
    # 历史 selection 只用于确定性 request 回放,不是继续执行许可。
    record = next((r for r in records if r.selection_id == selection_id), None)
    if record is None:
        raise ScreenError("selection_changed")
    return record


class Screening:
    def __init__(
        self,
        root: ExperimentRoot,
        *,
        snapshot: str,
        credentials_dir: Path,
        material_root: Path,
        install_root: Path,
        sink: Sink | None = None,
    ) -> None:
        self.root = root
        self.snapshot_reference = snapshot
        self.credentials_dir = credentials_dir
        self.material_root, self.install_root = material_root, install_root
        self.sink = sink

    def _check(
        self, connection: Connection, record: SelectionRecord, grants: tuple[Grant, ...]
    ) -> None:
        try:
            Selections(
                self.root.database, self.root.data_root
            ).require_current_in_connection(connection, record)
            revision = resolve_revision(connection, paper_id=record.paper_id)
            if (revision.version_id, revision.revision_no) != (
                record.version_id,
                record.revision_no,
            ):
                raise ScreenError("frozen_version_changed")
            metadata = JGRMetadata(
                self.root.database, self.root.data_root
            ).result_in_connection(connection, record.paper_id)
            if not (
                metadata is not None
                and metadata.minimum_complete
                and metadata.nontruncated_complete
                and metadata.current_version
                and metadata.routes_settled
                and not metadata.missing
            ):
                raise ScreenError("metadata_not_ready")
            for grant in grants:
                require_egress_authorization(
                    self.root,
                    stage=grant.stage,
                    provider=grant.provider,
                    model=grant.model,
                    categories=grant.categories,
                    connection=connection,
                )
        except (EgressError, SelectionError) as error:
            raise ScreenError(error.reason) from None

    def _before(self, record: SelectionRecord, grants: tuple[Grant, ...]) -> None:
        self.root.require()
        with transaction(self.root.database) as connection:
            self._check(connection, record, grants)

    def _stage(
        self,
        execution: PiExecution,
        receipt: RequestReceipt,
        record: SelectionRecord,
        grants: tuple[Grant, ...],
    ) -> dict[str, object]:
        tasks = execution.tasks

        def claim_guard(connection: Connection) -> None:
            self._check(connection, record, grants)
            tasks.require_current_generation(connection, receipt)

        while True:
            status = tasks.status(receipt.receipt_id)
            if status.state in {"succeeded", "failed"}:
                break
            if status.state == "running":
                raise ScreenError("task_running")
            if status.remaining_attempts == 0:
                raise ScreenError("lease_unsettled")
            # 每次只驱动当前代际的剩余尝试;run_attempt 在短事务内最后复核。
            execution.run_attempt(
                receipt.receipt_id,
                before_prepare=lambda: self._before(record, grants),
                claim_guard=claim_guard,
            )
        success = next(
            (
                view.receipt.success_id
                for view in tasks.query_successes(
                    paper_id=receipt.paper_id,
                    stage=receipt.stage,
                    snapshot_id=receipt.snapshot_id,
                )
                if view.receipt.task_id == receipt.task_id
            ),
            None,
        )
        return dict(
            receipt=asdict(receipt),
            state=status.state,
            attempts=status.used_attempts,
            success_id=success,
        )

    def run(
        self, selection_id: str, *, receipt_id: str | None = None
    ) -> dict[str, object]:
        record = selected_record(self.root, selection_id)
        snapshot_id = resolve_config_snapshot_reference(
            self.root.database, self.snapshot_reference
        )
        snapshot = load_config_snapshot(self.root.database, snapshot_id)
        grants = selected_grants(snapshot, ["boundary", "value"])
        execution = PiExecution(
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
        )
        tasks: ScreeningTasks = execution.tasks
        if receipt_id is not None:
            receipt = tasks.get_receipt(receipt_id)
            self._before(record, grants)
            if (
                receipt.paper_id != record.paper_id
                or receipt.version_id != record.version_id
                or receipt.revision_no != record.revision_no
                or receipt.snapshot_id != snapshot_id
            ):
                raise ScreenError("receipt_scope_mismatch")
            with transaction(self.root.database) as connection:
                tasks.require_current_generation(connection, receipt)
            status = tasks.status(receipt_id)
            if status.state == "succeeded":
                raise ScreenError("already_succeeded")
            if status.state == "failed":
                raise ScreenError("budget_exhausted")
            if receipt.stage == "value":
                basis = FeedPipeline(
                    self.root.database, self.root.data_root, sink=self.sink
                ).production_value_basis(receipt_id)
                if basis.metadata_request_key != record.metadata_request_key:
                    raise ScreenError("receipt_scope_mismatch")
            stage = self._stage(
                execution,
                receipt,
                record,
                (grants[0] if receipt.stage == "boundary" else grants[1],),
            )
            state = "succeeded" if stage["state"] == "succeeded" else "budget_exhausted"
            if receipt.stage == "boundary" and state == "succeeded":
                identifier = stage["success_id"]
                assert isinstance(identifier, str)
                content = tasks.load_success(identifier)
                if (
                    isinstance(content.output, BoundaryOutput)
                    and content.output.boundary == "out_of_scope"
                ):
                    state = "out_of_scope"
            return dict(
                selection_id=selection_id,
                state=state,
                boundary=stage if receipt.stage == "boundary" else None,
                value=stage if receipt.stage == "value" else None,
            )

        def request(stage: str) -> dict[str, object]:
            # snapshot 固定请求审计;预算仍由 A7 的 paper/stage/fingerprint 拥有。
            from hashlib import sha256

            identifier = sha256(
                f"{selection_id}:{snapshot_id}:{stage}".encode()
            ).hexdigest()
            return dict(
                paper_id=record.paper_id,
                snapshot_id=snapshot_id,
                stage=stage,
                source="manual",
                request_id=f"b-screen-{identifier}",
                reason="B 所有者选样后的显式 Screening",
                actor="agent",
            )

        boundary_receipt, replayed = tasks.register_with_status(
            request("boundary"),
            registration_guard=lambda connection: self._check(
                connection, record, grants
            ),
        )
        result: dict[str, object] = dict(
            selection_id=selection_id, state="replayed", boundary=None, value=None
        )
        if replayed:
            # 原回执是登记快照;不补后来成功,不认证、不领取、不继续 value。
            result["boundary"] = dict(receipt=asdict(boundary_receipt))
            return result
        boundary = self._stage(execution, boundary_receipt, record, (grants[0],))
        result["boundary"] = boundary
        if boundary["state"] == "failed":
            result["state"] = "budget_exhausted"
            return result
        success_id = boundary["success_id"]
        assert isinstance(success_id, str)
        content = tasks.load_success(success_id)
        if not isinstance(content.output, BoundaryOutput):
            raise ScreenError("boundary_missing")
        if content.receipt.executor_kind != "pi_rpc":
            raise ScreenError("test_source")
        if content.output.boundary == "out_of_scope":
            result["state"] = "out_of_scope"
            return result
        # 两阶段之间短事务重新读取全部有效事实;boundary 成功不授予 value 权限。
        self._before(record, grants)
        value_receipt = (
            FeedPipeline(self.root.database, self.root.data_root, sink=self.sink)
            .register_value(
                request("value"),
                metadata_request_key=record.metadata_request_key,
                boundary_success_id=success_id,
            )
            .receipt
        )
        value = self._stage(execution, value_receipt, record, (grants[1],))
        result["value"] = value
        result["state"] = (
            "succeeded" if value["state"] == "succeeded" else "budget_exhausted"
        )
        return result
