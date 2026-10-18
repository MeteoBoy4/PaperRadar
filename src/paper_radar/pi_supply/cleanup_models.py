"""安装清理计划的严格规范字节;与供给和业务制品清理身份分开。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from paper_radar.config.identity import canonical_json, sha256
from paper_radar.pi_supply.errors import SupplyReason
from paper_radar.pi_supply.models import Frozen, Hash

LocalId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
Nonnegative = Annotated[int, Field(ge=0)]
ProtectionReason = Literal[
    "current",
    "recent_activation",
    "latest_install_check",
    "latest_rpc_compatibility",
    "in_flight",
    "protection_unknown",
]


class CleanupItem(Frozen):
    supply_id: Hash
    install_id: LocalId
    root_id: LocalId
    root_path: str
    relative_path: str
    state: Literal["installed", "retired_pending"]
    disposition: Literal["candidate", "protected", "unverifiable", "absent"]
    protection: tuple[ProtectionReason, ...]
    ever_activated: bool
    observation: Literal["idle", "in_flight", "unknown"]
    reason: SupplyReason | Literal["passed"]
    expected_tree_hash: Hash
    present: bool | None
    actual_tree_hash: Hash | None
    allocated_bytes: Nonnegative | None
    logical_bytes: Nonnegative | None

    @field_validator("protection", mode="before")
    @classmethod
    def sequence(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value


class ManualCleanup(Frozen):
    root_id: LocalId
    relative_path: str
    reason: Literal[
        "unknown_entry", "unknown_staging", "unknown_trash", "root_unverifiable"
    ]

    allocated_bytes: Nonnegative | None = None
    logical_bytes: Nonnegative | None = None
    occupancy_reason: SupplyReason | Literal["passed"] = "tree_invalid"

    @model_validator(mode="after")
    def occupancy_shape(self) -> ManualCleanup:
        if (self.allocated_bytes is None) != (self.logical_bytes is None):
            raise ValueError("partial occupancy")
        if (self.occupancy_reason == "passed") != (self.allocated_bytes is not None):
            raise ValueError("occupancy reason")
        return self


class CleanupPlan(Frozen):
    format_version: Literal[1] = 1
    retention_rule: Literal["library-install-window-v1"] = "library-install-window-v1"
    tree_rule: Literal["tree-v1"] = "tree-v1"
    occupancy_rule: Literal["allocated-inode-v1"] = "allocated-inode-v1"
    created_at: str
    database_id: LocalId
    data_root: str
    config_root: str
    material_root: str
    facts_version: Hash
    facts: dict[str, JsonValue]
    items: tuple[CleanupItem, ...]
    manual: tuple[ManualCleanup, ...]
    present_count: Nonnegative
    over_limit: bool
    allocated_bytes: Nonnegative
    reclaimable_bytes: Nonnegative
    occupancy_unknown: bool

    @field_validator("items", "manual", mode="before")
    @classmethod
    def sequence(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def facts_identity(self) -> CleanupPlan:
        if sha256(canonical_json(self.facts)) != self.facts_version:
            raise ValueError("facts identity")
        if len({item.install_id for item in self.items}) != len(self.items):
            raise ValueError("duplicate installation")
        if self.present_count != sum(item.present is True for item in self.items):
            raise ValueError("present count")
        if self.reclaimable_bytes > self.allocated_bytes:
            raise ValueError("reclaim estimate")
        if self.over_limit != (self.present_count > 4):
            raise ValueError("retention count")
        return self

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json(self.model_dump(mode="json"))

    @property
    def plan_id(self) -> str:
        return sha256(self.canonical_bytes)

    @property
    def candidates(self) -> tuple[CleanupItem, ...]:
        return tuple(item for item in self.items if item.disposition == "candidate")

    @property
    def retired_pending(self) -> tuple[CleanupItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.state == "retired_pending" and item.disposition != "absent"
        )


CleanupPhase = Literal["not_run", "retired", "moved", "completed", "failed"]
PREFLIGHT_REASONS: frozenset[SupplyReason] = frozenset(
    {
        "cleanup_facts_changed",
        "database_unavailable",
        "operation_interrupted",
        "cleanup_failed",
    }
)


class CleanupProgress(Frozen):
    event_id: Annotated[int, Field(ge=1)]
    install_id: LocalId
    phase: CleanupPhase
    reason: SupplyReason | Literal["passed", "not_run"]
    created_at: str


class CleanupExecution(Frozen):
    run_id: LocalId
    plan_id: Hash
    created_at: str
    events: tuple[CleanupProgress, ...]

    @property
    def items(self) -> tuple[CleanupProgress, ...]:
        latest = {event.install_id: event for event in self.events}
        return tuple(latest.values())

    @property
    def passed(self) -> bool:
        return all(item.phase == "completed" for item in self.items)
