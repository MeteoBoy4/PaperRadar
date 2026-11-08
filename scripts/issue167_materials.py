"""#167 六格离线合成输入;不启动 Pi、不读认证、不授予现场许可。"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from paper_radar.config import StageName, compile_config, upgrade_database
from paper_radar.contracts import export_frozen_contract
from paper_radar.fulltext.canonical import (
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalProvenance,
)
from paper_radar.fulltext.normalization import (
    canonical_json,
    normalize_document,
    render_reading,
)
from paper_radar.fulltext.quality import reconstruct_context
from paper_radar.llm import build_call, render_request
from paper_radar.llm.rpc import validate_request
from paper_radar.read_inputs.budget import read_input_budget
from paper_radar.reading.acceptance_v2 import validate_read_output_v2
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.screening.context import ValuePredictionContext
from paper_radar.screening.validation import validate_output
from paper_radar.stage_inputs import (
    ExtractionFacts,
    ReadFacts,
    ScreeningFacts,
    build_stage_input,
)

PROJECT = Path(__file__).resolve().parents[1]
TEXTS = (
    "This is a fictional comparison of toy estimators A and B on a synthetic sequence.",
    (
        "No real dataset or code is provided. "
        "These fictional results have no scientific claim."
    ),
)
SYSTEM = "只依据显式输入执行合成协议任务，输出契约要求的纯 JSON，不调用工具。\n"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def expected_output(stage: StageName) -> dict[str, object]:
    if stage is StageName.BOUNDARY:
        return {"boundary": "in_scope", "reason_zh": "合成估计量比较符合虚构研究范围。"}
    if stage is StageName.VALUE:
        return {
            "research_value": 2,
            "reuse_feasibility": 2,
            "research_value_reason_zh": "只有合成示例，科研价值有限。",
            "reuse_feasibility_reason_zh": "摘要未说明真实数据或代码。",
            "reuse_feasibility_inferable": False,
            "value_types": [],
            "topic_ids": ["toy"],
            "abstract_brief_zh": "比较虚构估计量，不含真实数据。",
            "why_it_may_matter_zh": "可用作协议测试的简单背景。",
            "display_title_zh": "合成估计量示例",
        }
    return {
        "output_language": "zh",
        "one_sentence_conclusion": "本例仅比较虚构估计量。",
        "research_question": "如何比较合成序列上的玩具估计量？",
        "methods_summary": "比较玩具估计量。",
        "data_summary": "仅使用虚构合成序列。",
        "main_findings": [],
        "research_value": 2,
        "research_value_reason": {
            "statement": "比较只涉及虚构估计量。",
            "evidence": [{"evidence_id": "e000001"}],
        },
        "reuse_feasibility": 2,
        "reuse_feasibility_reason": {
            "statement": "没有真实数据或代码。",
            "evidence": [{"evidence_id": "e000002"}],
        },
        "required_adaptations": [],
        "reusable_points": [],
        "key_limitations": [],
        "open_questions": [],
        "value_types": [],
        "why_it_matters": "提供合成协议测试背景。",
        "next_action": "审阅合成输入。",
        "degraded_content_warnings": [],
    }


def pdf_bytes() -> bytes:
    """固定一页 PDF;与手制 canonical 对照,不冒称 SDK 提取。"""
    stream = (
        "BT /F1 10 Tf 40 740 Td (" + TEXTS[0] + ") Tj 0 -30 Td (" + TEXTS[1] + ") Tj ET"
    ).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n"
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return (
        result
        + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )


def write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")


def generate(root: Path) -> dict[str, Any]:
    """只创建新根;旧封印不可覆写。所有配置/数据库属于本次合成目录。"""
    root.mkdir(parents=True, exist_ok=False)
    database = root / "synthetic.sqlite3"
    upgrade_database(database)
    config = root / "config"
    profile = {
        key: "完全虚构：比较玩具估计量A和B，仅有合成序列，不提供真实数据或工具。"
        for key in (
            "background",
            "core_questions",
            "transferable_methods",
            "available_data_and_tools",
            "theory_and_cognitive_interests",
            "constraints_and_exclusions",
        )
    }
    write_yaml(
        config / "profiles/issue167-profile-v1.yaml",
        {"version": "issue167-profile-v1", **profile},
    )
    slot = {
        "provider": "openai",
        "model": "gpt-6.1-sol",
        "protocol": "prompt_only",
        "sampling": "provider_default",
    }
    write_yaml(
        config / "models/issue167-models-v1.yaml",
        {
            "format_version": 2,
            "version": "issue167-models-v1",
            "screening": dict(slot),
            "reading": dict(slot),
            "reuse_assessment": None,
        },
    )
    write_yaml(
        config / "topics/issue167-topics-v1.yaml",
        {
            "version": "issue167-topics-v1",
            "topics": [
                {
                    "id": "toy",
                    "name": "合成估计量",
                    "description": "只比较虚构估计量",
                    "enabled": True,
                }
            ],
        },
    )
    write_yaml(
        config / "read/issue167-read-v1.yaml",
        {"version": "issue167-read-v1", "chunking_version": "v1"},
    )
    recipe = PROJECT / "intent/review/issue-167/synthetic-extraction.yaml"
    write_yaml(
        config / "extraction/issue167-synthetic-extraction-v1.yaml",
        yaml.safe_load(recipe.read_text()),
    )
    (config / "prompts").mkdir()
    (config / "prompts/pi-system-issue167-v1.md").write_text(SYSTEM)
    for level in ("low", "high"):
        write_yaml(
            config / f"adapters/issue167-{level}-v1.yaml",
            {
                "version": f"issue167-{level}-v1",
                "backend": "pi-rpc",
                "pi_version": "1.4.0",
                "adapter_version": "issue167-synthetic-v1",
                "thinking_level": level,
                "policy": {"version": "bounded-rpc-v1"},
                "resources": [
                    {
                        "kind": "system_prompt",
                        "name": "pi-system",
                        "version": "issue167-v1",
                        "sha256": digest(SYSTEM.encode()),
                    }
                ],
            },
        )
    for name, prompt_folder in (
        ("boundary", "screening"),
        ("value", "screening"),
        ("reading", "reading"),
    ):
        path = (
            root
            / "prompts"
            / prompt_folder
            / ("issue167-v1.md" if name == "reading" else f"{name}-issue167-v1.md")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "本例完全虚构，仅作协议探测。只依据显式输入输出 contract 的纯 JSON，"
            "使用有意义中文。不得调用工具或增加回合。若摘要不足判断复用，说明‘摘要未说明’；"
            "Read 两个评分理由分别引用相关 evidence_id，不能虚构数值。\n"
        )
    for name in ("boundary", "value-prediction", "read"):
        export_frozen_contract(name, "v1", root / "contracts")
    pdf = pdf_bytes()
    document = CanonicalDocument(
        pages=(CanonicalPage(page_no=1, width=600.0, height=800.0),),
        blocks=tuple(
            CanonicalBlock(
                ref=f"s{i}",
                order=(i,),
                label="text",
                orig=text,
                text=text,
                provenance=(
                    CanonicalProvenance(
                        page_no=1,
                        bbox=(40.0, float(20 + i * 30), 580.0, float(40 + i * 30)),
                        charspan=(0, len(text)),
                    ),
                ),
            )
            for i, text in enumerate(TEXTS, 1)
        ),
    )
    evidence_map = normalize_document(document)
    reading = render_reading(evidence_map)
    map_bytes = canonical_json(evidence_map.model_dump(mode="json"))
    common = root / "source"
    common.mkdir()
    for name, raw in {
        "synthetic.pdf": pdf,
        "canonical.json": canonical_json(document.model_dump(mode="json")),
        "reading.md": reading,
        "evidence-map.json": map_bytes,
    }.items():
        (common / name).write_bytes(raw)
    cases = []
    for level in ("low", "high"):
        settings = config / f"settings-{level}.yaml"
        write_yaml(
            settings,
            {
                "profile": "issue167-profile-v1",
                "models": "issue167-models-v1",
                "topics": "issue167-topics-v1",
                "read": "issue167-read-v1",
                "extraction": "issue167-synthetic-extraction-v1",
                "adapters": {
                    "screening": f"issue167-{level}-v1",
                    "reading": f"issue167-{level}-v1",
                },
                "prompts": {
                    "boundary": "issue167-v1",
                    "value": "issue167-v1",
                    "reading": "issue167-v1",
                },
                "contracts": {"boundary": "v1", "value_prediction": "v1", "read": "v1"},
            },
        )
        snapshot = compile_config(settings, database)
        extraction = build_stage_input(
            snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256=digest(pdf))
        )
        identity = ExtractionIdentity(
            extraction.fingerprint, digest(reading), digest(map_bytes)
        )
        context = reconstruct_context(evidence_map, identity, expected_language="zh")
        for stage in (StageName.BOUNDARY, StageName.VALUE, StageName.READ):
            facts = (
                ReadFacts(
                    extraction_input=extraction,
                    reading_sha256=identity.reading_sha256,
                    evidence_map_sha256=identity.evidence_map_sha256,
                    output_language="zh",
                )
                if stage is StageName.READ
                else ScreeningFacts(
                    title="Synthetic estimator example",
                    abstract=(
                        "This fictional study compares toy estimators A and B on a "
                        "synthetic sequence. No real dataset or code is supplied."
                    ),
                    abstract_truncated=False,
                )
            )
            stage_input = build_stage_input(snapshot, stage, facts)
            description = build_call(
                stage_input,
                snapshot,
                snapshot,
                read_context=context if stage is StageName.READ else None,
                reading=reading if stage is StageName.READ else None,
            )
            request = render_request(description)
            if validate_request(request) is not None:
                raise ValueError("synthetic_request_invalid")
            if stage is StageName.READ and not read_input_budget(description).accepted:
                raise ValueError("synthetic_read_budget_exceeded")
            folder = root / f"{stage.value}-{level}"
            folder.mkdir()
            candidate = canonical_json(expected_output(stage))
            if stage is StageName.READ:
                validate_read_output_v2(candidate, context, attempt_ordinal=1)
            elif stage is StageName.VALUE:
                validate_output(
                    "value_prediction",
                    candidate,
                    ValuePredictionContext(
                        enabled_topic_ids=frozenset({"toy"}), original_title_is_zh=False
                    ),
                )
            else:
                validate_output("boundary", candidate)
            descriptor = {
                key: value.decode("utf-8") if isinstance(value, bytes) else value
                for key, value in asdict(description).items()
            }
            files = {
                "stage-input.json": stage_input.payload_bytes,
                "system.txt": description.system_prompt,
                "user.txt": request,
                "description.json": canonical_json(descriptor),
                "extraction-input.json": extraction.payload_bytes,
                "context.json": canonical_json(asdict(context)),
                "expected-valid-output.json": candidate,
            }
            for name, raw in files.items():
                (folder / name).write_bytes(raw)
            cases.append(
                {
                    "case": folder.name,
                    "consumer": stage.value,
                    "thinking": level,
                    "snapshot_id": snapshot.snapshot_id,
                    "fingerprint": stage_input.fingerprint,
                    "sha256": {name: digest(raw) for name, raw in files.items()},
                }
            )
    manifest = {
        "format_version": 1,
        "plan": "issue-167-A6-v1",
        "authorization": "not_granted",
        "source_kind": "synthetic_canonical_not_docling_observation",
        "model": slot,
        "cases": cases,
        "source_sha256": {
            p.name: digest(p.read_bytes()) for p in sorted(common.iterdir())
        },
        "configuration_sha256": {
            str(p.relative_to(root)): digest(p.read_bytes())
            for base in (config, root / "prompts", root / "contracts")
            for p in sorted(base.rglob("*"))
            if p.is_file()
        },
    }
    (root / "manifest.json").write_bytes(canonical_json(manifest) + b"\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="生成 #167 新合成输入，不执行模型或认证"
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("--public-manifest", type=Path)
    args = parser.parse_args()
    result = generate(args.root)
    if args.public_manifest:
        args.public_manifest.write_bytes(canonical_json(result) + b"\n")
    print(json.dumps({"cases": len(result["cases"]), "authorization": "not_granted"}))
