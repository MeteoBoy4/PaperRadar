"""封印采集库存;固定六格、四对照,不接受运行时路径/命令。"""

from datetime import datetime
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, model_validator

from paper_radar.live_evidence.receipt import Digest, Identifier, UseId, WireModel
from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution.admission import EvidenceBinding

USES: tuple[UseId, ...] = (
    "boundary-low",
    "boundary-high",
    "value-low",
    "value-high",
    "read-low",
    "read-high",
)
NEGATIVES = ("outside-tcp443", "nonrouter-udp53", "nonrouter-tcp53", "udp443")


STATIC_COMPONENTS = frozenset(
    {
        B.MODEL_TUPLE,
        B.SUPPLY,
        B.INSTANCE,
        B.SUPPLY_TREE,
        B.INSTANCE_TREE,
        B.PI_VERSION,
        B.NODE_PLATFORM,
        B.LAUNCH_POLICY,
        B.ISOLATION_POLICY,
    }
)
RULE_COMMENTS = tuple("paperradar-negative-" + case for case in NEGATIVES)


class ModelCell(WireModel):
    use_id: UseId
    plan: ApprovedPlanV2
    binding: dict[B, Digest] = Field(default_factory=dict)
    model: EvidenceBinding
    material_sha256: Digest
    snapshot_id: Digest
    request_sha256: Digest

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            not (set(self.binding) == set(B) or set(self.binding) <= STATIC_COMPONENTS)
            or self.plan.kind != "model_six_cell"
            or self.plan.cases != ("model-" + self.use_id,)
            or self.model.thinking_level != self.use_id.rsplit("-", 1)[1]
            or not self.plan.max_auth_calls
            or not self.plan.max_model_calls
            or self.plan.max_network_requests
        ):
            raise ValueError("collector_cell_invalid")
        return self


class NetworkConfiguration(WireModel):
    pool: str
    router: IPv4Address
    outside: IPv4Address
    nonrouter: IPv4Address
    udp443: IPv4Address
    rule_comments: tuple[str, ...] = RULE_COMMENTS
    # 所有者确认原文为封印包单独非秘密成员;本模型不代替owner确认。
    owner_confirmation_sha256: Digest
    plan_ids: tuple[Identifier, ...]
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid(self) -> Self:
        pool = IPv4Network(self.pool, strict=True)
        if (
            self.outside in pool
            or self.nonrouter == self.router
            or self.nonrouter.is_multicast
            or self.outside.is_multicast
            or self.udp443.is_multicast
            or self.outside.is_loopback
            or self.nonrouter.is_loopback
            or self.udp443.is_loopback
            or self.rule_comments != RULE_COMMENTS
            or self.starts_at.tzinfo is None
            or self.ends_at.tzinfo is None
            or self.starts_at >= self.ends_at
        ):
            raise ValueError("collector_network_invalid")
        return self


class ModelManifest(WireModel):
    format_version: Literal[1]
    collector_sha256: Digest
    site_plan_id: Identifier
    site_plan_sha256: Digest
    actual_snapshot_id: Digest
    cells: tuple[ModelCell, ...] = Field(min_length=6, max_length=6)
    negative_plan: ApprovedPlanV2
    network: NetworkConfiguration
    members: dict[str, Digest]

    @model_validator(mode="after")
    def valid(self) -> Self:
        plans = (*tuple(cell.plan for cell in self.cells), self.negative_plan)
        if (
            tuple(cell.use_id for cell in self.cells) != USES
            or len({plan.plan_id for plan in plans}) != 7
            or any(plan.collector_sha256 != self.collector_sha256 for plan in plans)
            or self.negative_plan.kind != "site_beta"
            or self.negative_plan.cases != NEGATIVES
            or self.negative_plan.max_network_requests < 4
            or set(self.network.plan_ids) != {plan.plan_id for plan in plans}
        ):
            raise ValueError("collector_manifest_invalid")
        if any(
            not self.network.starts_at
            <= plan.starts_at
            < plan.ends_at
            <= self.network.ends_at
            for plan in plans
        ):
            raise ValueError("collector_window_invalid")
        if not self.members or any(
            PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or not name.startswith("materials/")
            for name in self.members
        ):
            raise ValueError("collector_members_invalid")
        if any(not set(cell.binding) <= STATIC_COMPONENTS for cell in self.cells):
            raise ValueError("collector_runtime_components_forbidden")
        return self


def material_root(root: Path, use_id: UseId) -> Path:
    return root / "materials" / use_id


class ModelManifestV2(ModelManifest):
    # A new sealed envelope; existing v1 readers and v2 plan/receipt bytes stay frozen.
    format_version: Literal[2]  # type: ignore[assignment]
    normal_refresh_batches: tuple[tuple[UseId, ...], ...] = (
        ("boundary-low",),
        ("boundary-high",),
        ("value-low", "value-high", "read-low", "read-high"),
    )
    normal_refresh_policy: Literal["normal-auth-refresh-v1"] = "normal-auth-refresh-v1"
    completion_target_hours: Literal[72] = 72

    @model_validator(mode="after")
    def batches_valid(self) -> Self:
        if self.normal_refresh_batches != (
            ("boundary-low",),
            ("boundary-high",),
            ("value-low", "value-high", "read-low", "read-high"),
        ):
            raise ValueError("collector_batch_invalid")
        return self


def parse_manifest(raw: bytes) -> ModelManifest:
    import json

    kind = json.loads(raw).get("format_version")
    return (ModelManifestV2 if kind == 2 else ModelManifest).model_validate_json(raw)
