"""持久正文→Read 纯输入、历史调用描述及领取前预算;不判断用途或领取任务。"""

from dataclasses import dataclass, field
from typing import Literal

from paper_radar.config import RuntimeConfigSnapshot, StageName
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.models import FulltextError
from paper_radar.llm import CallDescription, build_call
from paper_radar.read_inputs.budget import ReadInputBudget, read_input_budget
from paper_radar.read_inputs.corrections import build_read_correction
from paper_radar.reading.acceptance_v2 import validate_read_context_v2
from paper_radar.reading.context import ExtractionIdentity, ReadContext
from paper_radar.stage_inputs import (
    ReadFacts,
    StageInput,
    build_stage_input,
    replay_stage_input,
)


@dataclass(frozen=True, slots=True)
class PreparedReadInput:
    stage_input: StageInput
    context: ReadContext = field(repr=False)
    description: CallDescription
    budget: ReadInputBudget


def prepare_read_input(
    artifacts: FulltextArtifacts,
    artifact_id: str,
    extraction_input: StageInput,
    semantic_snapshot: RuntimeConfigSnapshot,
    audit_snapshot: RuntimeConfigSnapshot,
    *,
    expected_identity: ExtractionIdentity,
    output_language: Literal["zh", "en"] = "zh",
) -> PreparedReadInput:
    """配置与正文均由明确历史引用恢复;返回超额结果不产生持久事实。"""
    if type(extraction_input) is not StageInput:
        raise FulltextError("identity_mismatch")
    # extraction 配方可以来自另一份已登记历史快照;不借 Read 配置改写正文。
    replayed = replay_stage_input(
        extraction_input.payload_bytes, extraction_input.fingerprint
    )
    if (
        replayed != extraction_input
        or extraction_input.stage is not StageName.EXTRACTION
        or type(expected_identity) is not ExtractionIdentity
        or expected_identity.extraction_fingerprint != extraction_input.fingerprint
    ):
        raise FulltextError("identity_mismatch")
    identity = expected_identity
    loaded = artifacts.load(
        artifact_id, expected_identity=identity, expected_language=output_language
    )
    context = validate_read_context_v2(loaded.context)
    facts = ReadFacts(
        extraction_input=extraction_input,
        reading_sha256=identity.reading_sha256,
        evidence_map_sha256=identity.evidence_map_sha256,
        output_language=output_language,
    )
    stage_input = build_stage_input(semantic_snapshot, StageName.READ, facts)
    description = build_call(
        stage_input,
        semantic_snapshot,
        audit_snapshot,
        read_context=context,
        reading=loaded.reading,
    )
    return PreparedReadInput(
        stage_input, context, description, read_input_budget(description)
    )


__all__ = [
    "PreparedReadInput",
    "ReadInputBudget",
    "build_read_correction",
    "prepare_read_input",
    "read_input_budget",
]
