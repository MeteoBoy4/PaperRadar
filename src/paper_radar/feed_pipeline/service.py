"""显式Feed组合:保留服务权威;登记前置原子复核。"""

from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select

from paper_radar.feed_ingestion import JGRFeed
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.feed_pipeline.models import (
    CandidateReference,
    PipelineTrace,
    Preparation,
    PreparedItem,
    ValueRegistration,
)
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.papers import PaperFacts
from paper_radar.screening.schema import BoundaryOutput
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.screening_tasks.feed_gate import (
    FeedGate,
    find,
    proofs,
    request_key,
    sha,
)
from paper_radar.screening_tasks.repository import task_database, task_transaction

PipelineReason = Literal[
    "invalid_request",
    "metadata_incomplete",
    "metadata_stale",
    "boundary_missing",
    "out_of_scope",
    "test_source",
    "corrupt_reference",
]


class PipelineError(Exception):
    def __init__(self, reason: PipelineReason) -> None:
        self.reason = reason
        guidance = {
            "invalid_request": "请提供合法value请求及前置依据。",
            "metadata_incomplete": "元数据缺项或适用路线未完成。",
            "metadata_stale": "元数据依据已落后于当前版本或修订，请显式重新准备。",
            "boundary_missing": "请提供当前输入的boundary成功依据。",
            "out_of_scope": "boundary判定out_of_scope，不能登记value。",
            "test_source": "生产入口拒绝test来源，真实生产RPC仍由B承接。",
            "corrupt_reference": "组合依据损坏，请停止使用并核对备份。",
        }
        super().__init__(reason + "：" + guidance.get(reason, "请核对组合前置。"))


class FeedPipeline:
    def __init__(
        self, database: Path, data_root: Path, *, http: SourceHTTPExecutor | None = None
    ) -> None:
        self.database, self.data_root = database, data_root
        executor = http or SourceHTTPExecutor()
        self.feed = JGRFeed(database, data_root, http=executor)
        self.metadata = JGRMetadata(database, data_root, http=executor)
        self.papers = PaperFacts(database, data_root)
        self.tasks = ScreeningTasks(database, data_root)

    def prepare(
        self, feed_id: str, *, request_id: str, contact_email: str
    ) -> Preparation:
        check = self.feed.check(
            feed_id, request_id=request_id, contact_email=contact_email
        )
        output = []
        for item in check.items:
            result = item.result
            if result is None or result.paper_id is None:
                output.append(
                    PreparedItem(
                        item.position,
                        None,
                        conflict_id=result.conflict_id if result else None,
                        reason=item.reason,
                    )
                )
                continue
            metadata = self.metadata.enrich(
                result.paper_id,
                request_id=sha(check.check_id + result.paper_id),
                contact_email=contact_email,
            )
            output.append(
                PreparedItem(
                    item.position,
                    result.paper_id,
                    metadata.request_key,
                    metadata.model_copy(update={"title": None}),
                    reason=None if metadata.minimum_complete else "metadata_incomplete",
                )
            )
        return Preparation(check.check_id, tuple(output))

    def trace(self, paper_id: str) -> PipelineTrace:
        trace = self.papers.trace(paper_id)
        current = trace.current
        return PipelineTrace(
            paper_id,
            current.version_id,
            current.revision_no,
            tuple(
                value.model_copy(update={"title": None})
                for value in self.metadata.requests(paper_id)
            ),
            self.papers.conflicts(paper_id=paper_id),
            dict(observations=self.tasks.language_observations(paper_id)),
            self.tasks.receipts(paper_id),
            fields={
                name: CandidateReference.from_fact(current.version_id, name, fact)
                for name, fact in current.fields.items()
            },
            selection=current.selection,
            candidates=tuple(
                CandidateReference.from_fact(observation.version_id, name, fact)
                for observation in trace.observations
                for name, fact in observation.fields.items()
            ),
            decisions=trace.decisions,
            discoveries=trace.discoveries,
            acquisitions=trace.acquisitions,
        )

    def register_value(
        self,
        raw_request: object,
        *,
        metadata_request_key: str,
        boundary_success_id: str,
    ) -> ValueRegistration:
        return self._register(
            raw_request, metadata_request_key, boundary_success_id, "production"
        )

    def register_test_value(
        self,
        raw_request: object,
        *,
        metadata_request_key: str,
        boundary_success_id: str,
    ) -> ValueRegistration:
        """显式test用途;保留metadata/current/boundary/语言所有检查。"""
        return self._register(
            raw_request, metadata_request_key, boundary_success_id, "test"
        )

    def _result(self, basis: dict[str, Any]) -> ValueRegistration:
        receipt = self.tasks.get_receipt(basis["receipt_id"])
        return ValueRegistration(
            basis["purpose"],
            receipt,
            basis["metadata_request_key"],
            basis["boundary_success_id"],
            self.tasks.language_basis(receipt.receipt_id),
        )

    def _register(
        self,
        raw: object,
        metadata_key: str,
        boundary_id: str,
        purpose: Literal["production", "test"],
    ) -> ValueRegistration:
        if (
            type(raw) is not dict
            or raw.get("stage") != "value"
            or type(raw.get("snapshot_id")) is not str
            or "original_title_is_zh" in raw
        ):
            raise PipelineError("invalid_request")
        key = request_key(raw, metadata_key, boundary_id, purpose)
        with (
            task_database(self.database, write=False) as engine,
            task_transaction(engine, write=False) as connection,
        ):
            old = find(connection, key)
        if old is not None:
            return self._verify_basis(old)
        metadata = self.metadata.replay(metadata_key)
        if metadata.paper_id != raw.get("paper_id") or not metadata.minimum_complete:
            raise PipelineError("metadata_incomplete")
        current = self.papers.show(metadata.paper_id)
        if (current.version_id, current.revision_no) != (
            metadata.version_id,
            metadata.revision_no,
        ):
            raise PipelineError("metadata_stale")
        successes = self.tasks.query_successes(
            paper_id=metadata.paper_id,
            stage="boundary",
            snapshot_id=raw["snapshot_id"],
        )
        boundary = next(
            (
                item
                for item in successes
                if item.receipt.success_id == boundary_id
                and item.applicability == "current"
            ),
            None,
        )
        if boundary is None:
            raise PipelineError("boundary_missing")
        content = self.tasks.load_success(boundary_id)
        if not isinstance(content.output, BoundaryOutput):
            raise PipelineError("boundary_missing")
        if content.output.boundary == "out_of_scope":
            raise PipelineError("out_of_scope")
        if purpose == "production" and content.receipt.executor_kind == "test":
            raise PipelineError("test_source")
        gate = FeedGate(
            key,
            metadata_key,
            boundary_id,
            purpose,
            current.version_id,
            current.revision_no,
            boundary.receipt.fingerprint,
        )
        receipt = self.tasks.register_feed_value(raw, feed_gate=gate)
        return self._result(
            dict(
                receipt_id=receipt.receipt_id,
                purpose=purpose,
                metadata_request_key=metadata_key,
                boundary_success_id=boundary_id,
            )
        )

    def _verify_basis(self, row: dict[str, Any]) -> ValueRegistration:
        result = self._result(row)
        metadata = self.metadata.replay(result.metadata_request_key)
        content = self.tasks.load_success(result.boundary_success_id)
        frozen = self.tasks.load_input(result.receipt.receipt_id)
        successes = self.tasks.query_successes(
            paper_id=result.receipt.paper_id,
            stage="boundary",
            snapshot_id=result.receipt.snapshot_id,
        )
        if (
            metadata.paper_id != result.receipt.paper_id
            or metadata.version_id != row["version_id"]
            or metadata.revision_no != row["revision_no"]
            or bool(set(metadata.missing) - {"current_version_changed"})
            or not any(
                value.receipt.success_id == result.boundary_success_id
                for value in successes
            )
            or content.receipt.fingerprint != row["boundary_fingerprint"]
            or not isinstance(content.output, BoundaryOutput)
            or content.output.boundary == "out_of_scope"
            or (
                result.purpose == "production"
                and content.receipt.executor_kind == "test"
            )
            or frozen.original_title_is_zh
            != result.language_basis["original_title_is_zh"]
        ):
            raise PipelineError("corrupt_reference")
        return result

    def validate_all(self) -> None:
        self.papers.validate_all()
        self.tasks.validate_all()
        self.feed.validate_all()
        self.metadata.validate_all()
        with (
            task_database(self.database, write=False) as engine,
            task_transaction(engine, write=False) as connection,
        ):
            rows = [
                find(connection, key)
                for key in connection.execute(select(proofs.c.request_key)).scalars()
            ]
        for row in rows:
            if row is None:
                raise PipelineError("corrupt_reference")
            self._verify_basis(row)
