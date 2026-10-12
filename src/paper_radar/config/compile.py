"""只依赖已验证配置值的确定性快照编译和就绪判断。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from paper_radar.config.adapters import AdapterSemantics
from paper_radar.config.escalation import Escalation, EscalationSemantics
from paper_radar.config.extraction import Extraction, ExtractionSemantics
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.read import ReadConfig, ReadSemantics
from paper_radar.config.schema import (
    MODEL_SLOTS,
    PROFILE_FIELDS,
    Models,
    Profile,
    PromptName,
    Settings,
    SlotStatus,
    model_slot_status,
    profile_field_status,
    text_is_placeholder,
)
from paper_radar.config.topics import EnabledTopic, Topics, TopicsStatus
from paper_radar.contracts.schema import ContractName

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
    VALUE_PROMPT_PLACEHOLDER = "value_prompt_placeholder"
    VALUE_CONTRACT = "value_contract"
    TOPICS = "topics"
    REUSE_MODEL = "reuse_model"
    REUSE_MODEL_PLACEHOLDER = "reuse_model_placeholder"
    REUSE_PROMPT = "reuse_prompt"
    REUSE_PROMPT_PLACEHOLDER = "reuse_prompt_placeholder"
    REUSE_CONTRACT = "reuse_contract"
    EXCERPT_SELECTOR = "excerpt_selector"
    EXTRACTION_CONFIG = "extraction_config"
    READ_MODEL = "read_model"
    READ_MODEL_PLACEHOLDER = "read_model_placeholder"
    READ_PROMPT = "read_prompt"
    READ_PROMPT_PLACEHOLDER = "read_prompt_placeholder"
    READ_CONTRACT = "read_contract"
    CHUNKING_VERSION = "chunking_version"
    SUGGESTION_RULE = "suggestion_rule"
    ESCALATION_PARAMETERS = "escalation_parameters"
    DECISION_REASONS_CONTRACT = "decision_reasons_contract"
    SCREENING_ADAPTER_PROMPT_PLACEHOLDER = "screening_adapter_prompt_placeholder"
    REUSE_ADAPTER_PROMPT_PLACEHOLDER = "reuse_adapter_prompt_placeholder"
    READ_ADAPTER_PROMPT_PLACEHOLDER = "read_adapter_prompt_placeholder"


class MaterialKind(StrEnum):
    PROFILE = "profile"
    TOPICS = "topics"
    MODELS = "models"
    ESCALATION = "escalation"
    EXTRACTION = "extraction"
    READ = "read"
    ADAPTER = "adapter"
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
class SelectedMaterials:
    """活跃选择或历史回放得到的已验证材料。"""

    settings: Settings
    profile: Profile | None
    profile_material: Material | None
    models: Models | None
    topics: Topics | None
    additional: tuple[CompiledMaterial, ...]
    escalation: Escalation | None = None
    extraction: Extraction | None = None
    adapters: tuple[tuple[str, AdapterSemantics], ...] = ()
    read: ReadConfig | None = None


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
    topics_status: TopicsStatus
    enabled_topics: tuple[EnabledTopic, ...]
    escalation: EscalationSemantics | None
    extraction: ExtractionSemantics | None
    adapters: Mapping[str, AdapterSemantics | None]
    read: ReadSemantics | None

    @property
    def adapter_slots(self) -> Mapping[str, SlotStatus]:
        return MappingProxyType(
            {
                slot: (
                    SlotStatus.UNCONFIGURED
                    if semantics is None
                    else SlotStatus.PLACEHOLDER
                    if text_is_placeholder(semantics.system_prompt_text)
                    else SlotStatus.CONFIGURED
                )
                for slot, semantics in self.adapters.items()
            }
        )

    @property
    def adapter_dependencies(self) -> Mapping[str, tuple[StageName, ...]]:
        return MappingProxyType(
            {
                "screening": (StageName.BOUNDARY, StageName.VALUE),
                "reuse_assessment": (StageName.REUSE,),
                "reading": (StageName.READ,),
            }
        )

    @property
    def calibration_adapter_slots(self) -> tuple[str, ...]:
        return ("screening", "reuse_assessment")


def compile_snapshot(materials: SelectedMaterials) -> RuntimeConfigSnapshot:
    """新增材料种类沿用包络格式。条目按 kind/name/version 排序。"""
    settings = materials.settings
    profile = materials.profile
    material = materials.profile_material
    models = materials.models
    topics = materials.topics
    escalation = materials.escalation
    extraction = materials.extraction
    additional = materials.additional
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
    if settings.topics is not None:
        selectors["topics"] = settings.topics
    if settings.escalation is not None:
        selectors["escalation"] = settings.escalation
    if settings.extraction is not None:
        selectors["extraction"] = settings.extraction
    if settings.read is not None:
        selectors["read"] = settings.read
    for group in ("prompts", "contracts"):
        chosen = {
            name: version
            for name, version in getattr(settings, group).model_dump().items()
            if version is not None
        }
        if chosen:
            selectors[group] = chosen
    chosen_adapters = {
        name: version
        for name, version in settings.adapters.model_dump().items()
        if version is not None
    }
    if chosen_adapters:
        selectors["adapters"] = chosen_adapters
    payload = {
        "format_version": FORMAT_VERSION,
        "selectors": selectors,
        "materials": entries,
    }
    missing_profile = (
        () if profile_status is SlotStatus.CONFIGURED else (MissingReason.PROFILE,)
    )
    adapters = dict(materials.adapters)

    def adapter_reason(
        slot: str, placeholder: MissingReason
    ) -> tuple[MissingReason, ...]:
        selected = adapters.get(slot)
        if selected is not None and text_is_placeholder(selected.system_prompt_text):
            return (placeholder,)
        return ()

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

    screening_model_missing = model_reason(
        "screening",
        MissingReason.SCREENING_MODEL,
        MissingReason.SCREENING_MODEL_PLACEHOLDER,
    )

    def prompt_reason(
        name: PromptName, missing: MissingReason, placeholder: MissingReason
    ) -> tuple[MissingReason, ...]:
        prompt = next(
            (
                item.material
                for item in additional
                if item.material.kind is MaterialKind.PROMPT
                and item.material.name == name
            ),
            None,
        )
        if prompt is None:
            return (missing,)
        if text_is_placeholder(prompt.raw.decode("utf-8")):
            return (placeholder,)
        return ()

    def contract_reason(
        name: ContractName, missing: MissingReason
    ) -> tuple[MissingReason, ...]:
        present = any(
            item.material.kind is MaterialKind.CONTRACT_SCHEMA
            and item.material.name == name
            for item in additional
        )
        return () if present else (missing,)

    boundary_missing = (
        *missing_profile,
        *screening_model_missing,
        *adapter_reason(
            "screening", MissingReason.SCREENING_ADAPTER_PROMPT_PLACEHOLDER
        ),
        *prompt_reason(
            PromptName.BOUNDARY,
            MissingReason.BOUNDARY_PROMPT,
            MissingReason.BOUNDARY_PROMPT_PLACEHOLDER,
        ),
        *contract_reason(ContractName.BOUNDARY, MissingReason.BOUNDARY_CONTRACT),
    )
    value_missing = (
        *missing_profile,
        *screening_model_missing,
        *adapter_reason(
            "screening", MissingReason.SCREENING_ADAPTER_PROMPT_PLACEHOLDER
        ),
        *prompt_reason(
            PromptName.VALUE,
            MissingReason.VALUE_PROMPT,
            MissingReason.VALUE_PROMPT_PLACEHOLDER,
        ),
        *contract_reason(ContractName.VALUE_PREDICTION, MissingReason.VALUE_CONTRACT),
        *((MissingReason.TOPICS,) if topics is None else ()),
    )
    reuse_missing = (
        *missing_profile,
        *adapter_reason(
            "reuse_assessment", MissingReason.REUSE_ADAPTER_PROMPT_PLACEHOLDER
        ),
        *model_reason(
            "reuse_assessment",
            MissingReason.REUSE_MODEL,
            MissingReason.REUSE_MODEL_PLACEHOLDER,
        ),
        *prompt_reason(
            PromptName.REUSE,
            MissingReason.REUSE_PROMPT,
            MissingReason.REUSE_PROMPT_PLACEHOLDER,
        ),
        *contract_reason(ContractName.REUSE_ASSESSMENT, MissingReason.REUSE_CONTRACT),
        *((MissingReason.EXCERPT_SELECTOR,) if escalation is None else ()),
    )
    suggestion_missing = (
        *(
            (MissingReason.SUGGESTION_RULE, MissingReason.ESCALATION_PARAMETERS)
            if escalation is None
            else ()
        ),
        *contract_reason(
            ContractName.DECISION_REASONS, MissingReason.DECISION_REASONS_CONTRACT
        ),
    )
    stages = {
        StageName.BOUNDARY: StageReadiness(
            StageStatus.READY if not boundary_missing else StageStatus.NOT_READY,
            boundary_missing,
        ),
        StageName.VALUE: StageReadiness(
            StageStatus.READY if not value_missing else StageStatus.NOT_READY,
            value_missing,
        ),
        StageName.REUSE: StageReadiness(
            StageStatus.READY if not reuse_missing else StageStatus.NOT_READY,
            reuse_missing,
        ),
        StageName.EXTRACTION: StageReadiness(
            StageStatus.READY if extraction is not None else StageStatus.NOT_READY,
            () if extraction is not None else (MissingReason.EXTRACTION_CONFIG,),
        ),
        StageName.READ: StageReadiness(
            StageStatus.NOT_READY,
            (
                *missing_profile,
                *adapter_reason(
                    "reading", MissingReason.READ_ADAPTER_PROMPT_PLACEHOLDER
                ),
                *model_reason(
                    "reading",
                    MissingReason.READ_MODEL,
                    MissingReason.READ_MODEL_PLACEHOLDER,
                ),
                *prompt_reason(
                    PromptName.READING,
                    MissingReason.READ_PROMPT,
                    MissingReason.READ_PROMPT_PLACEHOLDER,
                ),
                MissingReason.READ_CONTRACT,
                *((MissingReason.CHUNKING_VERSION,) if materials.read is None else ()),
            ),
        ),
        StageName.SUGGESTION: StageReadiness(
            StageStatus.READY if not suggestion_missing else StageStatus.NOT_READY,
            suggestion_missing,
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
        topics_status=(
            TopicsStatus.CONFIGURED if topics is not None else TopicsStatus.UNCONFIGURED
        ),
        enabled_topics=topics.enabled_topics if topics is not None else (),
        escalation=escalation.semantics if escalation is not None else None,
        extraction=extraction.semantics if extraction is not None else None,
        adapters=MappingProxyType({name: adapters.get(name) for name in MODEL_SLOTS}),
        read=materials.read.semantics if materials.read is not None else None,
    )
