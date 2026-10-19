"""#53 调用方的明确合成事实与公共阶段输入组合。不保存生产事实。"""

import hashlib
from typing import Any

from paper_radar.config import RuntimeConfigSnapshot, StageName
from paper_radar.stage_inputs import (
    ExtractionFacts,
    ExtractionRef,
    ReuseFacts,
    ScreeningFacts,
    SelectedExcerpt,
    SourceSnapshotRef,
    StageInput,
    build_stage_input,
)


def synthetic_submission() -> dict[str, Any]:
    return {
        "screening": {
            "title": "Synthetic title",
            "abstract": "Synthetic abstract\n",
            "abstract_truncated": False,
        },
        "excerpts": [
            {
                "excerpt_id": "availability-1",
                "kind": "availability",
                "text": "Synthetic availability text",
                "locator": ["section", "block-1"],
            },
            {
                "excerpt_id": "methods-1",
                "kind": "methods",
                "text": "Synthetic methods text",
                "locator": ["section", "block-2"],
            },
        ],
    }


def synthetic_members() -> dict[str, dict[str, str]]:
    # 仅纯契约 fixture 使用合成原字节的独立 SHA-256。恢复路径从真实成员取哈希。
    return {
        case: {role: hashlib.sha256(raw).hexdigest() for role, raw in content.items()}
        for case, content in {
            "pdf": {"payload": b"Synthetic PDF bytes"},
            "structured": {"payload": b"Synthetic source snapshot"},
            "body": {
                "reading": b"Synthetic reading text",
                "evidence_map": b'{"blocks":["block-1","block-2"]}',
            },
        }.items()
    }


def rebuild_inputs(
    snapshot: RuntimeConfigSnapshot,
    members: dict[str, dict[str, str]],
    submission: dict[str, Any],
    *,
    reverse: bool = False,
) -> dict[str, StageInput]:
    """哈希只来自调用方刚从指定制品 get_artifact 得到的成员。"""

    def ordered(fields: dict[str, Any]) -> dict[str, Any]:
        keys = reversed(fields) if reverse else iter(fields)
        return {key: fields[key] for key in keys}

    screening = ScreeningFacts(**ordered(submission["screening"]))
    extraction = build_stage_input(
        snapshot,
        StageName.EXTRACTION,
        ExtractionFacts(pdf_sha256=members["pdf"]["payload"]),
    )
    result = {"extraction": extraction}
    stages = (
        (StageName.VALUE, StageName.BOUNDARY)
        if reverse
        else (
            StageName.BOUNDARY,
            StageName.VALUE,
        )
    )
    for stage in stages:
        result[stage.value] = build_stage_input(snapshot, stage, screening)
    for case in ("structured", "body"):
        excerpts = []
        for item in submission["excerpts"]:
            source: SourceSnapshotRef | ExtractionRef
            if case == "structured":
                source = SourceSnapshotRef(
                    **ordered(
                        {
                            "content_sha256": members["structured"]["payload"],
                            "locator": item["locator"],
                        }
                    )
                )
            else:
                source = ExtractionRef(
                    **ordered(
                        {
                            "extraction_input": extraction,
                            "reading_sha256": members["body"]["reading"],
                            "evidence_map_sha256": members["body"]["evidence_map"],
                            "locator": item["locator"],
                        }
                    )
                )
            excerpts.append(
                SelectedExcerpt(
                    **ordered(
                        {
                            "excerpt_id": item["excerpt_id"],
                            "kind": item["kind"],
                            "text": item["text"],
                            "source": source,
                        }
                    )
                )
            )
        result[case] = build_stage_input(
            snapshot, StageName.REUSE, ReuseFacts(excerpts=excerpts)
        )
    return result
