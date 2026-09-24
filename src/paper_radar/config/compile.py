"""只依赖已验证配置值的确定性快照编译和就绪判断。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.schema import (
    PROFILE_FIELDS,
    Profile,
    Settings,
    SlotStatus,
    profile_field_status,
)

FORMAT_VERSION = 1


class StageStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"


class MissingReason(StrEnum):
    PROFILE = "profile"
    SCREENING_MODEL = "screening_model"
    BOUNDARY_PROMPT = "boundary_prompt"
    BOUNDARY_CONTRACT = "boundary_contract"
    VALUE_PROMPT = "value_prompt"
    VALUE_CONTRACT = "value_contract"
    REUSE_MODEL = "reuse_model"
    REUSE_PROMPT = "reuse_prompt"
    REUSE_CONTRACT = "reuse_contract"
    EXTRACTION_CONFIG = "extraction_config"
    READ_MODEL = "read_model"
    READ_PROMPT = "read_prompt"
    READ_CONTRACT = "read_contract"
    SUGGESTION_RULE = "suggestion_rule"


@dataclass(frozen=True, slots=True)
class Material:
    kind: str
    name: str
    version: str
    raw: bytes

    @property
    def raw_sha256(self) -> str:
        return sha256(self.raw)


@dataclass(frozen=True, slots=True)
class StageReadiness:
    status: StageStatus
    missing: tuple[MissingReason, ...]


@dataclass(frozen=True, slots=True)
class RuntimeConfigSnapshot:
    snapshot_id: str
    profile_status: SlotStatus
    profile_fields: Mapping[str, SlotStatus]
    stages: Mapping[str, StageReadiness]
    payload_json: str


def compile_snapshot(
    settings: Settings, profile: Profile | None, material: Material | None
) -> RuntimeConfigSnapshot:
    """新增材料种类沿用包络格式。条目按 kind/name/version 排序。"""
    fields = {
        field: profile_field_status(getattr(profile, field) if profile else None)
        for field in PROFILE_FIELDS
    }
    if profile is None:
        profile_status = SlotStatus.UNCONFIGURED
    elif all(status is SlotStatus.CONFIGURED for status in fields.values()):
        profile_status = SlotStatus.CONFIGURED
    elif any(status is SlotStatus.PLACEHOLDER for status in fields.values()):
        profile_status = SlotStatus.PLACEHOLDER
    else:
        profile_status = SlotStatus.UNCONFIGURED

    entries: list[dict[str, Any]] = []
    if material is not None and profile is not None:
        entries.append(
            {
                "kind": material.kind,
                "name": material.name,
                "version": material.version,
                "raw_sha256": material.raw_sha256,
                "config": profile.model_dump(),
            }
        )
    payload = {
        "format_version": FORMAT_VERSION,
        "selectors": {"profile": settings.profile},
        "materials": entries,
    }
    missing_profile = (
        () if profile_status is SlotStatus.CONFIGURED else (MissingReason.PROFILE,)
    )
    stages = {
        "boundary": StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                MissingReason.SCREENING_MODEL,
                MissingReason.BOUNDARY_PROMPT,
                MissingReason.BOUNDARY_CONTRACT,
            ),
        ),
        "value": StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                MissingReason.SCREENING_MODEL,
                MissingReason.VALUE_PROMPT,
                MissingReason.VALUE_CONTRACT,
            ),
        ),
        "reuse": StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                MissingReason.REUSE_MODEL,
                MissingReason.REUSE_PROMPT,
                MissingReason.REUSE_CONTRACT,
            ),
        ),
        "extraction": StageReadiness(
            StageStatus.NOT_READY, (MissingReason.EXTRACTION_CONFIG,)
        ),
        "read": StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                MissingReason.READ_MODEL,
                MissingReason.READ_PROMPT,
                MissingReason.READ_CONTRACT,
            ),
        ),
        "suggestion": StageReadiness(
            StageStatus.NOT_READY, (MissingReason.SUGGESTION_RULE,)
        ),
    }
    canonical = canonical_json(payload)
    return RuntimeConfigSnapshot(
        snapshot_id=sha256(canonical),
        profile_status=profile_status,
        profile_fields=MappingProxyType(fields),
        stages=MappingProxyType(stages),
        payload_json=canonical.decode("utf-8"),
    )
