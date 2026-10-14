"""已验证单快照的六阶段语义与校准基线。纯计算。不访问外部材料。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from paper_radar.config.compile import MaterialKind, RuntimeConfigSnapshot, StageName
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.schema import PROFILE_FIELDS
from paper_radar.config.topics import TopicsStatus

PROJECTION_FORMAT_VERSIONS: Mapping[StageName, int] = MappingProxyType(
    {stage: 1 for stage in StageName}
)
BASELINE_FORMAT_VERSION = 1
CALIBRATION_STAGES = (
    StageName.BOUNDARY,
    StageName.VALUE,
    StageName.REUSE,
    StageName.EXTRACTION,
    StageName.SUGGESTION,
)


@dataclass(frozen=True, slots=True)
class StageConfigProjection:
    stage: StageName
    format_version: int
    payload_json: str = field(repr=False)

    @property
    def projection_id(self) -> str:
        return sha256(self.payload_json.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class CalibrationBaseline:
    format_version: int
    payload_json: str = field(repr=False)

    @property
    def baseline_id(self) -> str:
        return sha256(self.payload_json.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class ConfigSemantics:
    projections: Mapping[StageName, StageConfigProjection]
    baseline: CalibrationBaseline


def project_config(snapshot: RuntimeConfigSnapshot) -> ConfigSemantics:
    """输入必须已由 check/compile/load 验证。不改变快照或配置就绪判断。"""
    materials = {
        (material.kind, material.name): json.loads(material.config_json)
        for material in snapshot.materials.values()
    }
    profile = materials.get((MaterialKind.PROFILE, "profile"))
    profile_semantics = (
        {name: profile[name] for name in PROFILE_FIELDS}
        if profile is not None
        else None
    )
    models = materials.get((MaterialKind.MODELS, "models"))

    def contract_components(name: str) -> dict[str, Any] | None:
        schema = materials.get((MaterialKind.CONTRACT_SCHEMA, name))
        if schema is None:
            return None
        return {
            "schema": schema,
            "manifest": materials.get((MaterialKind.CONTRACT_MANIFEST, name)),
        }

    def model_components(
        slot: str, prompt_name: str, contract_name: str
    ) -> dict[str, Any]:
        prompt = materials.get((MaterialKind.PROMPT, prompt_name))
        adapter = snapshot.adapters[slot]
        return {
            "profile": profile_semantics,
            "model": models[slot] if models is not None else None,
            "prompt": prompt["text"] if prompt is not None else None,
            "contract": contract_components(contract_name),
            "adapter": adapter.semantics_id if adapter is not None else None,
        }

    boundary = model_components("screening", "boundary", "boundary")
    value = model_components("screening", "value", "value-prediction")
    value["topics"] = (
        [
            {"id": topic.id, "name": topic.name, "description": topic.description}
            for topic in sorted(snapshot.enabled_topics, key=lambda topic: topic.id)
        ]
        if snapshot.topics_status is TopicsStatus.CONFIGURED
        else None
    )
    escalation = snapshot.escalation
    reuse = model_components("reuse_assessment", "reuse", "reuse-assessment")
    reuse.update(
        excerpt_selector_version=(
            escalation.excerpt_selector_version if escalation is not None else None
        ),
        excerpt_priority=(
            list(escalation.excerpt_priority) if escalation is not None else None
        ),
    )
    reading = model_components("reading", "reading", "read")
    reading["chunking_version"] = (
        snapshot.read.chunking_version if snapshot.read is not None else None
    )
    suggestion = {
        "suggestion_rule_version": (
            escalation.suggestion_rule_version if escalation is not None else None
        ),
        "reuse_escalation_research_values": (
            sorted(set(escalation.reuse_escalation_research_values))
            if escalation is not None
            else None
        ),
        "contract": contract_components("decision-reasons"),
    }
    extraction = snapshot.extraction
    extraction_components = {
        "extraction": (
            {
                "backend": {
                    "backend_id": extraction.backend.backend_id,
                    "backend_version": extraction.backend.backend_version,
                    "component_versions": dict(extraction.backend.component_versions),
                },
                "model_artifacts": [
                    {
                        "stage": model.stage,
                        "model_id": model.model_id,
                        "repo_id": model.repo_id,
                        "commit_sha": model.commit_sha,
                        "files": [
                            file.model_dump()
                            for file in sorted(model.files, key=lambda file: file.path)
                        ],
                    }
                    for model in sorted(
                        extraction.model_artifacts, key=lambda model: model.stage.value
                    )
                ],
                "backend_config": json.loads(extraction.backend_config_json),
                "normalization_version": extraction.normalization_version,
            }
            if extraction is not None
            else None
        )
    }
    components = {
        StageName.BOUNDARY: boundary,
        StageName.VALUE: value,
        StageName.REUSE: reuse,
        StageName.EXTRACTION: extraction_components,
        StageName.READ: reading,
        StageName.SUGGESTION: suggestion,
    }
    projections = {
        stage: StageConfigProjection(
            stage,
            PROJECTION_FORMAT_VERSIONS[stage],
            canonical_json(
                {
                    "kind": "stage_config_projection",
                    "stage": stage,
                    "format_version": PROJECTION_FORMAT_VERSIONS[stage],
                    "components": components[stage],
                }
            ).decode("utf-8"),
        )
        for stage in StageName
    }
    baseline = CalibrationBaseline(
        BASELINE_FORMAT_VERSION,
        canonical_json(
            {
                "kind": "calibration_baseline",
                "format_version": BASELINE_FORMAT_VERSION,
                "projections": {
                    stage: projections[stage].projection_id
                    for stage in CALIBRATION_STAGES
                },
            }
        ).decode("utf-8"),
    )
    return ConfigSemantics(MappingProxyType(projections), baseline)
