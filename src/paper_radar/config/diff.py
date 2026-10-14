"""两个已验证快照的纯语义比较。不加载快照。不写事实或判定校准等级。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from paper_radar.config.adapters import ADAPTER_NAME, SYSTEM_PROMPT_NAME
from paper_radar.config.compile import MaterialKind, RuntimeConfigSnapshot, StageName
from paper_radar.config.projections import (
    CalibrationBaseline,
    StageConfigProjection,
    project_config,
)


class ConfigCategory(StrEnum):
    """差异的封闭配置类别。adapter 类别按实际选择槽区分。"""

    PROFILE = "profile.profile"
    TOPICS = "topics.topics"
    JOURNALS = "journals.journals"
    MODELS = "models.models"
    ESCALATION = "escalation.escalation"
    EXTRACTION = "extraction.extraction"
    READ = "read.read"
    PROMPT_BOUNDARY = "prompt.boundary"
    PROMPT_VALUE = "prompt.value"
    PROMPT_REUSE = "prompt.reuse"
    PROMPT_READING = "prompt.reading"
    CONTRACT_SCHEMA_BOUNDARY = "contract_schema.boundary"
    CONTRACT_SCHEMA_VALUE_PREDICTION = "contract_schema.value-prediction"
    CONTRACT_SCHEMA_REUSE_ASSESSMENT = "contract_schema.reuse-assessment"
    CONTRACT_SCHEMA_DECISION_REASONS = "contract_schema.decision-reasons"
    CONTRACT_MANIFEST_BOUNDARY = "contract_manifest.boundary"
    CONTRACT_MANIFEST_VALUE_PREDICTION = "contract_manifest.value-prediction"
    CONTRACT_MANIFEST_REUSE_ASSESSMENT = "contract_manifest.reuse-assessment"
    CONTRACT_MANIFEST_DECISION_REASONS = "contract_manifest.decision-reasons"
    ADAPTER_SCREENING = "adapters.screening"
    ADAPTER_REUSE_ASSESSMENT = "adapters.reuse_assessment"
    ADAPTER_READING = "adapters.reading"


@dataclass(frozen=True, slots=True)
class ConfigIdentity:
    kind: MaterialKind
    name: str
    version: str
    raw_sha256: str


@dataclass(frozen=True, slots=True)
class ConfigIdentityChange:
    category: ConfigCategory
    before: tuple[ConfigIdentity, ...]
    after: tuple[ConfigIdentity, ...]


@dataclass(frozen=True, slots=True)
class ComponentChange:
    name: str
    before_configured: bool
    after_configured: bool


@dataclass(frozen=True, slots=True)
class StageProjectionChange:
    stage: StageName
    before: StageConfigProjection
    after: StageConfigProjection
    components: tuple[ComponentChange, ...]


@dataclass(frozen=True, slots=True)
class ConfigSnapshotDiff:
    before_snapshot_id: str
    after_snapshot_id: str
    identity_changes: tuple[ConfigIdentityChange, ...]
    projection_changes: tuple[StageProjectionChange, ...]
    before_baseline: CalibrationBaseline
    after_baseline: CalibrationBaseline

    @property
    def snapshot_changed(self) -> bool:
        return self.before_snapshot_id != self.after_snapshot_id

    @property
    def calibration_changed(self) -> bool:
        return self.before_baseline.baseline_id != self.after_baseline.baseline_id


def _identities(
    snapshot: RuntimeConfigSnapshot,
) -> dict[ConfigCategory, tuple[ConfigIdentity, ...]]:
    by_key = snapshot.materials

    def identity(key: tuple[MaterialKind, str, str]) -> ConfigIdentity:
        entry = by_key[key]
        return ConfigIdentity(
            entry.kind,
            entry.name,
            entry.version,
            entry.raw_sha256,
        )

    result: dict[ConfigCategory, tuple[ConfigIdentity, ...]] = {
        ConfigCategory(f"{kind}.{name}"): (identity((kind, name, version)),)
        for kind, name, version in by_key
        if kind != MaterialKind.ADAPTER and name != SYSTEM_PROMPT_NAME
    }
    for slot, version in snapshot.adapter_selections.items():
        key = (MaterialKind.ADAPTER, ADAPTER_NAME, version)
        resource = json.loads(by_key[key].config_json)["resources"][0]
        result[ConfigCategory(f"adapters.{slot}")] = (
            identity(key),
            identity((MaterialKind.PROMPT, SYSTEM_PROMPT_NAME, resource["version"])),
        )
    return result


def compare_config_snapshots(
    before: RuntimeConfigSnapshot, after: RuntimeConfigSnapshot
) -> ConfigSnapshotDiff:
    """分别重建单快照语义。再比较登记身份、投影与基线。"""
    before_semantics = project_config(before)
    after_semantics = project_config(after)
    before_ids, after_ids = _identities(before), _identities(after)
    identities = tuple(
        ConfigIdentityChange(
            category, before_ids.get(category, ()), after_ids.get(category, ())
        )
        for category in sorted(before_ids.keys() | after_ids.keys())
        if before_ids.get(category) != after_ids.get(category)
    )
    changes: list[StageProjectionChange] = []
    for stage in StageName:
        previous = before_semantics.projections[stage]
        current = after_semantics.projections[stage]
        if previous.projection_id == current.projection_id:
            continue
        previous_components = json.loads(previous.payload_json)["components"]
        current_components = json.loads(current.payload_json)["components"]
        changes.append(
            StageProjectionChange(
                stage,
                previous,
                current,
                tuple(
                    ComponentChange(
                        name,
                        previous_components[name] is not None,
                        current_components[name] is not None,
                    )
                    for name in sorted(
                        previous_components.keys() | current_components.keys()
                    )
                    if previous_components.get(name) != current_components.get(name)
                ),
            )
        )
    return ConfigSnapshotDiff(
        before.snapshot_id,
        after.snapshot_id,
        identities,
        tuple(changes),
        before_semantics.baseline,
        after_semantics.baseline,
    )
