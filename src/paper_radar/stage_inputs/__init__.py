"""不可变阶段输入、严格回放与只读比较的公共边界。"""

from paper_radar.stage_inputs.service import (
    BuildReason,
    ChangeComponent,
    ComparisonReason,
    ComparisonStatus,
    ExtractionFacts,
    InputField,
    ReplayReason,
    ScreeningFacts,
    StageInput,
    StageInputComparison,
    StageInputError,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)

__all__ = [
    "BuildReason",
    "ChangeComponent",
    "ComparisonReason",
    "ComparisonStatus",
    "ExtractionFacts",
    "InputField",
    "ReplayReason",
    "ScreeningFacts",
    "StageInput",
    "StageInputComparison",
    "StageInputError",
    "build_stage_input",
    "compare_stage_inputs",
    "replay_stage_input",
]
