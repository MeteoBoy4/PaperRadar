"""D1:v1/v2 共同行为、明确差异及无 extra 冷进程重算。"""

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from paper_radar.reading import ReadOutputError, SourceBlock, validate_read_output
from paper_radar.reading.acceptance_v2 import ReadV2OutputError, validate_read_output_v2
from tests.read_support import candidate, context_for


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"research_value": 2, "value_types": []},
        {
            "main_findings": [
                {"statement": "提高了 12 km。", "evidence": [{"evidence_id": "e1"}]}
            ]
        },
        {
            "main_findings": [
                {"statement": "提高了 99 km。", "evidence": [{"evidence_id": "e1"}]}
            ]
        },
        {"degraded_content_warnings": ["请人工核对。", "请人工核对。"]},
    ],
)
def test_shared_valid_behaviors_match_v1(changes: dict[str, Any]) -> None:
    raw = candidate(**changes)
    context = context_for("提高了 12 km。")
    old = validate_read_output(raw, context)
    new = validate_read_output_v2(raw, context, attempt_ordinal=1)
    # 程序警告模板已改为安全文本;模型字段、诊断和来源切片保持。
    old_analysis = old.analysis.model_dump(exclude={"degraded_content_warnings"})
    new_analysis = new.analysis.model_dump(exclude={"degraded_content_warnings"})
    assert new_analysis == old_analysis
    assert new.model_warnings == old.model_warnings
    assert [(d.location, d.reason.value, d.ordinal) for d in new.diagnostics] == [
        (d.location, d.reason.value, d.ordinal) for d in old.diagnostics
    ]
    assert (new.identity, new.mode, new.support) == (
        old.identity,
        old.mode,
        old.support,
    )


@pytest.mark.parametrize(
    ("raw", "category"),
    [
        (b'{"a": 1, "a": 2}', "invalid_json"),
        (b"{} trailing", "invalid_json"),
        (b"\xef\xbb\xbf{}", "invalid_json"),
        (b'{"x": NaN}', "invalid_json"),
        (b'{"x": "\\ud800"}', "invalid_json"),
        (candidate(output_language="en"), "language_mismatch"),
        (candidate(one_sentence_conclusion="..."), "invalid_text"),
        (candidate(research_value=0), "invalid_score"),
        (candidate(reuse_feasibility="3"), "invalid_type"),
        (candidate(value_types=[]), "value_types_required"),
        (candidate(value_types=["method", "method"]), "duplicate_value_type"),
        (candidate(value_types=["other"]), "invalid_enum"),
        (candidate(extra_secret="secret"), "extra_field"),
        (
            candidate(research_value_reason={"statement": "依据。", "evidence": []}),
            "evidence_required",
        ),
        (
            candidate(
                reuse_feasibility_reason={
                    "statement": "依据。",
                    "evidence": [{"evidence_id": ""}],
                }
            ),
            "invalid_evidence_id",
        ),
        (
            candidate(
                research_value_reason={
                    "statement": "依据。",
                    "evidence": [{"evidence_id": "bad"}],
                }
            ),
            "unknown_evidence",
        ),
    ],
)
def test_shared_rejections_match_v1_at_both_attempts(raw: bytes, category: str) -> None:
    context = context_for()
    with pytest.raises(ReadOutputError) as old:
        validate_read_output(raw, context)
    assert category in {i.category.value for i in old.value.issues}
    for ordinal in (1, 2):
        with pytest.raises(ReadV2OutputError) as new:
            validate_read_output_v2(raw, context, attempt_ordinal=ordinal)
        assert [(i.location, i.category.value) for i in new.value.issues] == [
            (i.location, i.category.value) for i in old.value.issues
        ]
        assert new.value.__cause__ is new.value.__context__ is None


@pytest.mark.parametrize(
    ("kind", "unreliable", "text", "old_category", "new_reason"),
    [
        (
            "formula",
            False,
            "公式给出结论。",
            "restricted_source_reference",
            "restricted_source_reference",
        ),
        (
            "text",
            True,
            "该方法可复用。",
            "restricted_source_reference",
            "restricted_source_reference",
        ),
        (
            "table",
            False,
            "提高了 12 km。",
            "restricted_numeric_support",
            "restricted_numeric_support",
        ),
    ],
)
def test_v1_retains_historical_hard_failure_while_v2_warns(
    kind: Any,
    unreliable: bool,
    text: str,
    old_category: str,
    new_reason: str,
) -> None:
    base = context_for("提高了 12 km。")
    context = context_for(
        "提高了 12 km。",
        source_blocks=[
            SourceBlock(base.identity, "s1", "提高了 12 km。", kind, unreliable),
        ],
    )
    raw = candidate(
        main_findings=[{"statement": text, "evidence": [{"evidence_id": "e1"}]}]
    )
    with pytest.raises(ReadOutputError) as old:
        validate_read_output(raw, context)
    assert old.value.issues[0].category.value == old_category
    new = validate_read_output_v2(raw, context, attempt_ordinal=1)
    assert new_reason in {d.reason.value for d in new.diagnostics}
    assert len(new.analysis.main_findings) == 1


# 独立的持久清单样例,不能由本次实现输出生成预期。
_EXPECTED_DISCARDS = [
    {
        "location": "$.key_limitations[0]",
        "item_category": "key_limitations",
        "ordinal": 1,
        "reason": "unknown_evidence",
        "positions": [],
    }
]


def test_deterministic_recomputation_matches_saved_discard_fields() -> None:
    raw = candidate(
        key_limitations=[
            {"statement": "局限。", "evidence": [{"evidence_id": "bad-secret"}]}
        ]
    )
    first = validate_read_output_v2(raw, context_for(), attempt_ordinal=2)
    second = validate_read_output_v2(
        bytes(raw), context_for(), degrade_policy="final_attempt", attempt_ordinal=2
    )
    assert second == first
    assert (
        json.loads(json.dumps([asdict(d) for d in second.discards]))
        == _EXPECTED_DISCARDS
    )


def test_cold_process_accepts_and_recomputes_without_extra_or_external_io(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "candidate.json"
    raw_path.write_bytes(
        candidate(
            key_limitations=[
                {
                    "statement": "局限。",
                    "evidence": [{"evidence_id": "bad-secret"}],
                }
            ]
        )
    )
    historical_path = tmp_path / "v1-candidate.json"
    historical_path.write_bytes(candidate())
    script = r"""
import importlib.abc
import json
import sys
from dataclasses import asdict
from pathlib import Path

class DenyExtra(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = {'docling', 'docling_core', 'torch', 'transformers'}
        if fullname.split('.')[0] in forbidden:
            raise AssertionError('extra import forbidden')
sys.meta_path.insert(0, DenyExtra())
from paper_radar.reading import (
    Evidence, ExtractionIdentity, PageFact, Provenance, ReadContext, SourceBlock,
    validate_read_output,
)
from paper_radar.reading.acceptance_v2 import validate_read_output_v2
identity = ExtractionIdentity('extraction-1', 'reading-1', 'map-1')
context = ReadContext(identity, [PageFact(identity, 3, 600, 800, 'top_left')],
    [SourceBlock(identity, 's1', '可靠的正文说明。')],
    [Evidence(identity, 'e1', [Provenance('s1', 3, (0, 0, 600, 800), 0, 8)])], 'zh')
result = validate_read_output_v2(Path(sys.argv[1]).read_bytes(), context,
    degrade_policy='final_attempt', attempt_ordinal=2)
old = validate_read_output(Path(sys.argv[2]).read_bytes(), context)
print(json.dumps({'v1_versions': [old.evidence_rule_version, old.numeric_rule_version],
    'discards': [asdict(d) for d in result.discards],
    'versions': [result.evidence_rule_version, result.numeric_rule_version,
                 result.content_limitation_rule_version],
    'policy': result.degrade_policy, 'ordinal': result.attempt_ordinal}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(raw_path), str(historical_path)],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "v1_versions": ["read-evidence-v1", "read-numeric-v1"],
        "discards": _EXPECTED_DISCARDS,
        "versions": [
            "read-evidence-v2",
            "read-numeric-v2",
            "read-content-limitation-v1",
        ],
        "policy": "final_attempt",
        "ordinal": 2,
    }
