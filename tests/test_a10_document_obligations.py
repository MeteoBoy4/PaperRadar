"""冻结文档义务须有独立交付内容, 不能由需求原文或完成回帖替代。"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXCERPTS = "docs/verification/a10-documentation-excerpts.json"


@pytest.mark.parametrize(
    ("requirement_id", "required_text"),
    [
        (
            "A10-106-C6411119180-CLAUSE-001",
            "| 操作 | 输入与副作用 | 证明范围 |",
        ),
        (
            "A10-106-C6411119180-CLAUSE-005",
            "commit + dirty=true 不能区分同一提交后不同工作树内容",
        ),
        ("A10-100-DECISION-017", "旧 a704 批次仍须匹配程序 verify/restore"),
        ("A10-100-C6395756759-CLAUSE-038", "是路由，不是元数据提供方"),
        ("A10-100-C6395756759-CLAUSE-071", "格式为 `format_version=1`"),
        ("A10-100-C6395756759-CLAUSE-115", "审计补充：not_applicable_no_doi"),
        ("A10-100-C6395889326-CLAUSE-061", "是路由，不是元数据提供方"),
        ("A10-100-C6395889326-CLAUSE-083", "Fixture 回放的证明边界"),
        ("A10-100-C6405695568-CLAUSE-045", "只读预检观测，非对应票实测"),
        ("A10-100-C6405695568-CLAUSE-049", "仓库声明来源目录为 `fixtures/a10/`"),
        ("A10-105-AC-010", "不实现 B 就绪判定"),
        ("A10-105-AC-013", "帮助为中文并说明副作用、配额及示例"),
        ("A10-105-C6411118599-CLAUSE-004", "`observed_at=原取得 settled_at`"),
        ("A10-106-AC-010", "| 操作 | 输入与副作用 | 证明范围 |"),
        ("A10-108-AC-004", "共十四份 JSON（十二份主要文件）"),
    ],
)
def test_document_obligation_retains_delivered_baseline_content(
    requirement_id: str, required_text: str
) -> None:
    coverage = json.loads((ROOT / "tests/fixtures/a10_coverage.json").read_bytes())
    requirement = next(
        row
        for row in coverage["requirements"]
        if row["requirement_id"] == requirement_id
    )
    excerpts = json.loads((ROOT / EXCERPTS).read_bytes())
    delivered = [
        row for row in excerpts["excerpts"] if requirement_id in row["requirement_ids"]
    ]
    pointer = (
        "docs/verification/contracts-backup-restore-history.md"
        if requirement_id == "A10-100-DECISION-017"
        else EXCERPTS
    )
    delivered_text = (
        (ROOT / pointer).read_text()
        if pointer != EXCERPTS
        else "\n".join(row["original_text"] for row in delivered)
    )
    assert required_text in delivered_text, requirement_id
    assert pointer in requirement["public_behavior_pointers"]
    assert "documented_decisions" in requirement["mapped_behavior_ids"]
    migration = json.loads(
        (ROOT / "docs/verification/a10-scope-document-migration.json").read_bytes()
    )
    mappings = [
        row
        for row in migration["pointer_migrations"]
        if row["section"] == "requirements" and row["owner_id"] == requirement_id
    ]
    assert mappings
    assert all(row["action"] == "replace_frozen_evidence" for row in mappings)
    assert all(pointer in row["new_pointers"] for row in mappings)


def test_missing_spec_vocabulary_is_disclosed_instead_of_counted_as_covered() -> None:
    coverage = json.loads((ROOT / "tests/fixtures/a10_coverage.json").read_bytes())
    requirement = next(
        row
        for row in coverage["requirements"]
        if row["requirement_id"] == "A10-100-C6405695568-CLAUSE-037"
    )
    assert requirement["status"] == "not_assessed"
    assert requirement["not_assessed_refs"] == ["a10_spec_reason_vocabulary"]
    assert "§8.4" in requirement["not_assessed_responsibility"]["reason"]
    assert EXCERPTS in requirement["public_behavior_pointers"]


def test_review_accounts_for_every_previous_context_and_operation_owner() -> None:
    path = "docs/verification/a10-scope-document-migration.json"
    previous = json.loads(
        subprocess.run(
            ["git", "show", f"7e4b732e89400fb78139c8b1f9a049bb390d2ab9:{path}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
    )
    expected = {
        (row["section"], row["owner_id"])
        for row in previous["pointer_migrations"]
        if row["action"] in {"historical_operation", "remove_context"}
    }
    review = json.loads((ROOT / path).read_bytes())["semantic_review"]
    assert len(expected) == 302
    assert review["reviewed_occurrences"] == 635
    rows = review["owners"]
    assert len(rows) == 302
    assert {(row["section"], row["owner_id"]) for row in rows} == expected
    assert sum(row["reviewed_occurrences"] for row in rows) == 635
    assert all(row["reason"] and row["evidence_pointers"] for row in rows)
    assert (
        sum(row["classification"] == "documentation_obligation" for row in rows) == 16
    )
