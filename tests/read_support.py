"""Read 公共边界的独立合成材料;不代表生产正文。"""

import json
from typing import Any


def candidate(**changes: Any) -> bytes:
    reason = {
        "statement": "该方法提供了新的比较方式。",
        "evidence": [{"evidence_id": "e1"}],
    }
    value: dict[str, Any] = {
        "output_language": "zh",
        "one_sentence_conclusion": "该研究比较了降水预测方法。",
        "research_question": "如何提高预测质量？",
        "methods_summary": "比较独立预测。",
        "data_summary": "使用公开观测数据。",
        "main_findings": [],
        "research_value": 3,
        "research_value_reason": reason,
        "reuse_feasibility": 3,
        "reuse_feasibility_reason": reason,
        "required_adaptations": [],
        "reusable_points": [],
        "key_limitations": [],
        "open_questions": [],
        "value_types": ["method"],
        "why_it_matters": "有助于比较预测方法。",
        "next_action": "检查研究假设。",
        "degraded_content_warnings": [],
    }
    value.update(changes)
    return json.dumps(value, ensure_ascii=False).encode()


def context_for(source: str = "可靠的正文说明。", **changes: Any) -> Any:
    from paper_radar.reading import (
        Evidence,
        ExtractionIdentity,
        PageFact,
        Provenance,
        ReadContext,
        SourceBlock,
    )

    identity = ExtractionIdentity("extraction-1", "reading-1", "map-1")
    values: dict[str, Any] = {
        "identity": identity,
        "expected_language": "zh",
        "pages": [PageFact(identity, 3, 600, 800, "top_left")],
        "source_blocks": [SourceBlock(identity, "s1", source)],
        "evidence": [
            Evidence(
                identity, "e1", [Provenance("s1", 3, (0, 0, 600, 800), 0, len(source))]
            )
        ],
    }
    values.update(changes)
    return ReadContext(**values)
