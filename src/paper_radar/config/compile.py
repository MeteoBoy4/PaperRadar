"""只依赖已验证配置值的确定性快照编译和就绪判断。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.schema import (
    MODEL_SLOTS,
    PROFILE_FIELDS,
    Models,
    Profile,
    Settings,
    SlotStatus,
    model_slot_status,
    profile_field_status,
)

FORMAT_VERSION = 1


class StageName(StrEnum):
    BOUNDARY = "boundary"
    VALUE = "value"
    REUSE = "reuse"
    EXTRACTION = "extraction"
    READ = "read"
    SUGGESTION = "suggestion"


class StageStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"


class MissingReason(StrEnum):
    PROFILE = "profile"
    SCREENING_MODEL = "screening_model"
    SCREENING_MODEL_PLACEHOLDER = "screening_model_placeholder"
    BOUNDARY_PROMPT = "boundary_prompt"
    BOUNDARY_PROMPT_PLACEHOLDER = "boundary_prompt_placeholder"
    BOUNDARY_CONTRACT = "boundary_contract"
    VALUE_PROMPT = "value_prompt"
    VALUE_CONTRACT = "value_contract"
    REUSE_MODEL = "reuse_model"
    REUSE_MODEL_PLACEHOLDER = "reuse_model_placeholder"
    REUSE_PROMPT = "reuse_prompt"
    REUSE_CONTRACT = "reuse_contract"
    EXTRACTION_CONFIG = "extraction_config"
    READ_MODEL = "read_model"
    READ_MODEL_PLACEHOLDER = "read_model_placeholder"
    READ_PROMPT = "read_prompt"
    READ_CONTRACT = "read_contract"
    SUGGESTION_RULE = "suggestion_rule"


class MaterialKind(StrEnum):
    PROFILE = "profile"
    MODELS = "models"
    PROMPT = "prompt"
    CONTRACT_SCHEMA = "contract_schema"
    CONTRACT_MANIFEST = "contract_manifest"


@dataclass(frozen=True, slots=True)
class Material:
    kind: MaterialKind
    name: str
    version: str
    raw: bytes

    @property
    def raw_sha256(self) -> str:
        return sha256(self.raw)


@dataclass(frozen=True, slots=True)
class CompiledMaterial:
    material: Material
    config: Any


@dataclass(frozen=True, slots=True)
class StageReadiness:
    status: StageStatus
    missing: tuple[MissingReason, ...]


@dataclass(frozen=True, slots=True)
class RuntimeConfigSnapshot:
    snapshot_id: str
    profile_status: SlotStatus
    profile_fields: Mapping[str, SlotStatus]
    model_slots: Mapping[str, SlotStatus]
    stages: Mapping[StageName, StageReadiness]
    payload_json: str


def compile_snapshot(
    settings: Settings,
    profile: Profile | None,
    material: Material | None,
    models: Models | None = None,
    additional: tuple[CompiledMaterial, ...] = (),
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
    entries.extend(
        {
            "kind": item.material.kind,
            "name": item.material.name,
            "version": item.material.version,
            "raw_sha256": item.material.raw_sha256,
            "config": item.config,
        }
        for item in additional
    )
    entries.sort(key=lambda entry: (entry["kind"], entry["name"], entry["version"]))
    selectors: dict[str, Any] = {"profile": settings.profile}
    if settings.models is not None:
        selectors["models"] = settings.models
    if settings.prompts.boundary is not None:
        selectors["prompts"] = {"boundary": settings.prompts.boundary}
    if settings.contracts.boundary is not None:
        selectors["contracts"] = {"boundary": settings.contracts.boundary}
    payload = {
        "format_version": FORMAT_VERSION,
        "selectors": selectors,
        "materials": entries,
    }
    missing_profile = (
        () if profile_status is SlotStatus.CONFIGURED else (MissingReason.PROFILE,)
    )
    model_slots = {
        name: model_slot_status(getattr(models, name) if models else None)
        for name in MODEL_SLOTS
    }

    def model_reason(
        name: str, missing: MissingReason, placeholder: MissingReason
    ) -> tuple[MissingReason, ...]:
        status = model_slots[name]
        if status is SlotStatus.CONFIGURED:
            return ()
        return (placeholder if status is SlotStatus.PLACEHOLDER else missing,)

    prompt = next(
        (
            item.material
            for item in additional
            if item.material.kind is MaterialKind.PROMPT
            and item.material.name == "boundary"
        ),
        None,
    )
    prompt_missing: tuple[MissingReason, ...]
    if prompt is None:
        prompt_missing = (MissingReason.BOUNDARY_PROMPT,)
    elif prompt.raw.decode("utf-8").strip() in ("", "..."):
        prompt_missing = (MissingReason.BOUNDARY_PROMPT_PLACEHOLDER,)
    else:
        prompt_missing = ()
    contract_present = any(
        item.material.kind is MaterialKind.CONTRACT_SCHEMA
        and item.material.name == "boundary"
        for item in additional
    )
    boundary_missing = (
        *missing_profile,
        *model_reason(
            "screening",
            MissingReason.SCREENING_MODEL,
            MissingReason.SCREENING_MODEL_PLACEHOLDER,
        ),
        *prompt_missing,
        *((MissingReason.BOUNDARY_CONTRACT,) if not contract_present else ()),
    )
    stages = {
        StageName.BOUNDARY: StageReadiness(
            StageStatus.READY if not boundary_missing else StageStatus.NOT_READY,
            boundary_missing,
        ),
        StageName.VALUE: StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                *model_reason(
                    "screening",
                    MissingReason.SCREENING_MODEL,
                    MissingReason.SCREENING_MODEL_PLACEHOLDER,
                ),
                MissingReason.VALUE_PROMPT,
                MissingReason.VALUE_CONTRACT,
            ),
        ),
        StageName.REUSE: StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                *model_reason(
                    "reuse_assessment",
                    MissingReason.REUSE_MODEL,
                    MissingReason.REUSE_MODEL_PLACEHOLDER,
                ),
                MissingReason.REUSE_PROMPT,
                MissingReason.REUSE_CONTRACT,
            ),
        ),
        StageName.EXTRACTION: StageReadiness(
            StageStatus.NOT_READY, (MissingReason.EXTRACTION_CONFIG,)
        ),
        StageName.READ: StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                *model_reason(
                    "reading",
                    MissingReason.READ_MODEL,
                    MissingReason.READ_MODEL_PLACEHOLDER,
                ),
                MissingReason.READ_PROMPT,
                MissingReason.READ_CONTRACT,
            ),
        ),
        StageName.SUGGESTION: StageReadiness(
            StageStatus.NOT_READY, (MissingReason.SUGGESTION_RULE,)
        ),
    }
    canonical = canonical_json(payload)
    return RuntimeConfigSnapshot(
        snapshot_id=sha256(canonical),
        profile_status=profile_status,
        profile_fields=MappingProxyType(fields),
        model_slots=MappingProxyType(model_slots),
        stages=MappingProxyType(stages),
        payload_json=canonical.decode("utf-8"),
    )
