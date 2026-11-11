"""受保护正常刷新闭环;只消费原七计划完成源,从不派发/等待/重跑。"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from paper_radar.live_evidence.collection import ProtectedCollection
from paper_radar.live_evidence.epoch_lineage import EpochUpgrade
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.model_manifest import ModelManifest, ModelManifestV2
from paper_radar.live_evidence.receipt import (
    Digest,
    Identifier,
    WireModel,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution.auth_metadata import AuthRefreshMetadata


class AuthOperationRecord(WireModel):
    format_version: Literal[1] = 1
    plan_id: Identifier
    case_id: Identifier
    operation_id: Identifier
    receipt_sha256: Digest
    start: int = Field(gt=0, strict=True)
    unit: str = Field(pattern=r"^paperradar-[a-f0-9]{32}\.scope$")
    metadata: AuthRefreshMetadata


class NormalAuthEpoch(WireModel):
    format_version: Literal[1] = 1
    collector_sha256: Digest
    plan_ids: tuple[Identifier, ...]
    deployed_at: datetime


class InheritedAuthEpoch(NormalAuthEpoch):
    format_version: Literal[2] = 2  # type: ignore[assignment]
    inherited_from: EpochUpgrade


def parse_epoch(raw: bytes) -> NormalAuthEpoch:
    import json

    version = json.loads(raw).get("format_version")
    if version == 2:
        return InheritedAuthEpoch.model_validate_json(raw)
    return NormalAuthEpoch.model_validate_json(raw)


def _plan_ids(manifest: ModelManifest) -> tuple[str, ...]:
    return (
        *tuple(cell.plan.plan_id for cell in manifest.cells),
        manifest.negative_plan.plan_id,
    )


def epoch_path(ledger: EvidenceLedger, manifest: ModelManifest) -> Path:
    return (
        ledger.root
        / "inbox"
        / ("normal-auth-epoch-v1-" + content_sha256(manifest.cells[0].plan) + ".json")
    )


def _verify_epoch_chain(
    ledger: EvidenceLedger, manifest: ModelManifest, epoch: NormalAuthEpoch
) -> None:
    import hashlib

    if (
        epoch.collector_sha256 != manifest.collector_sha256
        or epoch.plan_ids != _plan_ids(manifest)
        or epoch.deployed_at.utcoffset() != timedelta(0)
        or not manifest.network.starts_at
        <= epoch.deployed_at
        <= manifest.network.ends_at
    ):
        raise LedgerError("source_untrusted")
    current = epoch
    seen = {epoch_path(ledger, manifest)}
    for _depth in range(16):
        if not isinstance(current, InheritedAuthEpoch):
            return
        source = current.inherited_from
        path = (
            ledger.root
            / "inbox"
            / ("normal-auth-epoch-v1-" + source.first_plan_sha256 + ".json")
        )
        if path in seen:
            raise LedgerError("source_untrusted")
        seen.add(path)
        raw = ledger._read_source(path)
        ancestor = parse_epoch(raw)
        if (
            hashlib.sha256(raw).hexdigest() != source.epoch_sha256
            or ancestor.collector_sha256 != source.collector_sha256
            or ancestor.plan_ids != source.plan_ids
            or ancestor.deployed_at != source.deployed_at
            or current.deployed_at != source.deployed_at
            or source.starts_at != manifest.network.starts_at
            or source.ends_at != manifest.network.ends_at
        ):
            raise LedgerError("source_untrusted")
        current = ancestor
    raise LedgerError("source_untrusted")


def read_epoch(ledger: EvidenceLedger, manifest: ModelManifest) -> NormalAuthEpoch:
    epoch = parse_epoch(ledger._read_source(epoch_path(ledger, manifest)))
    _verify_epoch_chain(ledger, manifest, epoch)
    return epoch


def validate_epoch_inheritance(
    ledger: EvidenceLedger, manifest: ModelManifest, source: EpochUpgrade
) -> NormalAuthEpoch:
    """只读预验;与最终发布共享规则,不因推进安装阶段而放过冲突或缺史。"""
    import hashlib

    existing_path = epoch_path(ledger, manifest)
    source_path = (
        ledger.root
        / "inbox"
        / ("normal-auth-epoch-v1-" + source.first_plan_sha256 + ".json")
    )
    if source_path == existing_path:
        raw = ledger._read_source(existing_path)
        existing = read_epoch(ledger, manifest)
        if (
            hashlib.sha256(raw).hexdigest() != source.epoch_sha256
            or existing.deployed_at != source.deployed_at
            or existing.collector_sha256 != source.collector_sha256
            or existing.plan_ids != source.plan_ids
        ):
            raise LedgerError("source_untrusted")
        return existing
    expected = InheritedAuthEpoch(
        collector_sha256=manifest.collector_sha256,
        plan_ids=_plan_ids(manifest),
        deployed_at=source.deployed_at,
        inherited_from=source,
    )
    _verify_epoch_chain(ledger, manifest, expected)
    if existing_path.exists():
        if ledger._read_source(existing_path) != canonical_bytes(expected):
            raise LedgerError("source_untrusted")
        read_epoch(ledger, manifest)
    elif ProtectedCollection(ledger).has_plan_history(frozenset(_plan_ids(manifest))):
        raise LedgerError("source_untrusted")
    return expected


def initialize_epoch(
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    *,
    now: datetime,
    inherited_from: EpochUpgrade | None = None,
) -> None:
    from paper_radar.live_evidence.sealed_runtime import _publish

    if not isinstance(manifest, ModelManifestV2):
        return
    if inherited_from is not None:
        epoch = validate_epoch_inheritance(ledger, manifest, inherited_from)
        if not epoch_path(ledger, manifest).exists():
            _publish(epoch_path(ledger, manifest), canonical_bytes(epoch))
        return
    if epoch_path(ledger, manifest).exists():
        read_epoch(ledger, manifest)
        return
    plans = frozenset(_plan_ids(manifest))
    if ProtectedCollection(ledger).has_plan_history(plans):
        raise LedgerError("source_untrusted")
    epoch = NormalAuthEpoch(
        collector_sha256=manifest.collector_sha256,
        plan_ids=_plan_ids(manifest),
        deployed_at=now,
    )
    _verify_epoch_chain(ledger, manifest, epoch)
    _publish(epoch_path(ledger, manifest), canonical_bytes(epoch))


class NormalRefreshReview(WireModel):
    format_version: Literal[1] = 1
    manifest_sha256: Digest
    status: Literal["not_assessed", "unknown", "passed"]
    stopped: bool = Field(strict=True)
    next_batch: Literal["A", "B", "C", "none"]
    sources: tuple[Digest, ...] = ()
    provider_real_expiry: Literal["unknown"] = "unknown"
    deployed_at: datetime | None = None
    target_at: datetime | None = None
    target_elapsed: bool = Field(default=False, strict=True)
    six_cells_target: Literal["not_assessed", "pending", "met", "missed"] = (
        "not_assessed"
    )
    reason: Literal[
        "not_observed",
        "external_batch_required",
        "refresh_not_proven",
        "sequence_invalid",
        "target_elapsed",
        "normal_refresh_verified",
    ]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.status == "passed" and (
            self.stopped
            or self.next_batch != "none"
            or len(self.sources) != 3
            or self.reason != "normal_refresh_verified"
        ):
            raise ValueError("normal_refresh_invalid")
        if self.stopped and self.next_batch != "none":
            raise ValueError("normal_refresh_invalid")
        return self


def normal_review_path(ledger: EvidenceLedger, manifest: ModelManifest) -> Path:
    return (
        ledger.root
        / "inbox"
        / ("normal-auth-refresh-v1-" + content_sha256(manifest.cells[0].plan) + ".json")
    )


def operation_path(ledger: EvidenceLedger, receipt_sha: str) -> Path:
    return ledger.root / "inbox" / f"auth-operation-v1-{receipt_sha}.json"


def record_auth_operation(
    collection: ProtectedCollection,
    receipt_sha: str,
    metadata: AuthRefreshMetadata,
    *,
    plan_id: str,
    case_id: str,
    operation_id: str,
    target: tuple[int, int, str],
    started_at: datetime,
    completed_at: datetime,
) -> None:
    from paper_radar.live_evidence.sealed_runtime import _publish

    pid, start, unit = target
    if metadata.pid != pid or not (
        started_at <= metadata.started_at <= metadata.completed_at <= completed_at
    ):
        raise LedgerError("source_untrusted")
    record = AuthOperationRecord(
        plan_id=plan_id,
        case_id=case_id,
        operation_id=operation_id,
        receipt_sha256=receipt_sha,
        start=start,
        unit=unit,
        metadata=metadata,
    )
    _publish(operation_path(collection.ledger, receipt_sha), canonical_bytes(record))


def review_normal_refresh(
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    *,
    now: datetime | None = None,
) -> NormalRefreshReview:
    """受保护来源重放;缺事件不补造,停止是不可逆本包事实。"""
    digest = content_sha256(manifest)
    report_path = normal_review_path(ledger, manifest)
    previous = None
    if report_path.exists():
        previous = NormalRefreshReview.model_validate_json(
            ledger._read_source(report_path)
        )
        if previous.manifest_sha256 != digest:
            raise LedgerError("source_untrusted")
        if previous.stopped:
            read_epoch(ledger, manifest)
            return previous
    if not isinstance(manifest, ModelManifestV2):
        return NormalRefreshReview(
            manifest_sha256=digest,
            status="not_assessed",
            stopped=False,
            next_batch="none",
            reason="not_observed",
        )
    epoch = read_epoch(ledger, manifest)
    target_at = epoch.deployed_at + timedelta(hours=72)
    collection = ProtectedCollection(ledger)
    # Different model tuples are independent evidence. Only the same site/auth
    # channel binding may link the three authentication operations.
    site_binding = {
        k: v for k, v in manifest.cells[0].binding.items() if k != B.MODEL_TUPLE
    }
    if any(
        {k: v for k, v in cell.binding.items() if k != B.MODEL_TUPLE} != site_binding
        for cell in manifest.cells
    ):
        raise LedgerError("source_untrusted")
    receipts = [
        collection.completed_case(cell.plan.cases[0], binding=cell.binding)
        for cell in manifest.cells[:3]
    ]
    if any(
        receipt is not None and receipt.plan_id != manifest.cells[index].plan.plan_id
        for index, receipt in enumerate(receipts)
    ):
        raise LedgerError("source_untrusted")
    sources = tuple(
        content_sha256(receipt) for receipt in receipts if receipt is not None
    )
    all_receipts = [
        collection.completed_case(cell.plan.cases[0], binding=cell.binding)
        for cell in manifest.cells
    ]
    all_done = all(receipt is not None for receipt in all_receipts)
    target_missed = (now is not None and now > target_at and not all_done) or any(
        receipt is not None and receipt.completed_at > target_at
        for receipt in all_receipts
    )

    def result(
        status: Literal["not_assessed", "unknown", "passed"],
        batch: Literal["A", "B", "C", "none"],
        reason: Literal[
            "not_observed",
            "external_batch_required",
            "refresh_not_proven",
            "sequence_invalid",
            "target_elapsed",
            "normal_refresh_verified",
        ],
        stopped: bool = False,
    ) -> NormalRefreshReview:
        return NormalRefreshReview(
            manifest_sha256=digest,
            sources=sources,
            deployed_at=epoch.deployed_at,
            target_at=target_at,
            target_elapsed=now is not None and now > target_at,
            six_cells_target="missed"
            if target_missed
            else "met"
            if all_done
            else "pending",
            status=status,
            stopped=stopped,
            next_batch=batch,
            reason=reason,
        )

    a, b, c = receipts
    if a is None:
        if b is not None or c is not None:
            return result("unknown", "none", "sequence_invalid", True)
        return result("not_assessed", "A", "not_observed")
    if b is None:
        return result("unknown", "B", "external_batch_required")
    events = []
    for index, receipt in enumerate((b, c), 1):
        if receipt is None:
            return result("unknown", "C", "external_batch_required")
        if receipt.started_at < receipts[index - 1].completed_at:  # type: ignore[union-attr]
            return result("unknown", "none", "sequence_invalid", True)
        path = operation_path(ledger, content_sha256(receipt))
        if not path.exists():
            return result("unknown", "none", "refresh_not_proven", True)
        record = AuthOperationRecord.model_validate_json(ledger._read_source(path))
        cell = manifest.cells[index]
        if (
            record.plan_id != cell.plan.plan_id
            or record.case_id != cell.plan.cases[0]
            or record.receipt_sha256 != content_sha256(receipt)
            or record.operation_id not in receipt.reservation_ids
            or not receipt.started_at
            <= record.metadata.started_at
            <= record.metadata.completed_at
            <= receipt.completed_at
            or any(
                value is not True
                for value in (
                    record.metadata.need_refresh,
                    record.metadata.refresh_called,
                    record.metadata.refresh_succeeded,
                    record.metadata.store_committed,
                )
            )
        ):
            return result("unknown", "none", "refresh_not_proven", True)
        events.append(record.metadata)
    if (
        events[0].refresh_at is None
        or events[1].refresh_at is None
        or events[1].refresh_at <= events[0].refresh_at
    ):
        return result("unknown", "none", "sequence_invalid", True)
    return result("passed", "none", "normal_refresh_verified")


def publish_normal_review(
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    *,
    now: datetime,
) -> NormalRefreshReview:
    from paper_radar.live_evidence.sealed_runtime import _publish

    result = review_normal_refresh(ledger, manifest, now=now)
    _publish(
        normal_review_path(ledger, manifest),
        canonical_bytes(result),
        replace=True,
    )
    return result
