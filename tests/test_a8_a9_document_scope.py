"""活文档与冻结证明通过仓库副本中的现有 writer 分别核验。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.scope_document_support import prepared_repository, writer_conclusion


def test_a8_a9_migration_records_every_inventory_removal() -> None:
    from scripts.verification_scope_audit import audit_scopes
    from scripts.verification_scope_registry import load_scopes
    from tests.a9_acceptance_support import ROOT

    directory = ROOT / "docs/verification"
    inventory = json.loads((directory / "scope-material-inventory.json").read_bytes())
    migration = json.loads((directory / "a8-a9-document-migration.json").read_bytes())
    removed = [
        row
        for row in inventory["bindings"]
        if row["group"] in {"A8", "A9"}
        and row["disposition"] == "remove_after_migration"
    ]
    assert len(removed) == 13
    assert migration["removed_bindings"] == removed
    assert len(migration["frozen_test_changes"]) == 2
    fixed = {
        (row["group"], row["kind"], row["path"])
        for row in audit_scopes(ROOT, load_scopes(ROOT))["files"]
        if row["group"] in {"A8", "A9"}
    }
    expected = {
        (row["group"], row["kind"], row["path"])
        for row in inventory["bindings"]
        if row["group"] in {"A8", "A9"} and row not in removed
    }
    # 第二步新增的审计闭包独立维护,不追溯改写第一步inventory。
    additions = {
        ("A8", "source", "scripts/verification_scope_baseline.py"),
        ("A9", "source", "scripts/verification_scope_baseline.py"),
        ("A9", "source", "scripts/verification_scope_collection.py"),
    }
    # 第二步将这14条精确scope材料边迁成显式证明引用,不改变其他材料。
    references = {
        (group, "source", f"scripts/{name}_scope.py")
        for group, names in (
            ("A8", ("a1", "a2_full", "a3", "a5", "a6", "a7")),
            ("A9", ("a1", "a2_full", "a3", "a4", "a5", "a6", "a7", "a8")),
        )
        for name in names
    }
    preparation = json.loads(
        (directory / "scope-extensible-groups-delivery.json").read_bytes()
    )
    additions.update(
        (row["group"], row["kind"], row["path"])
        for row in preparation["added_bindings"]
        if row["group"] in {"A8", "A9"}
    )
    assert fixed == (expected | additions) - references
    scopes = {scope.group: scope for scope in load_scopes(ROOT)}
    actual_references: set[tuple[str, str, str]] = set()
    for group in ("A8", "A9"):
        paths = scopes[group].references
        assert isinstance(paths, tuple)
        actual_references.update((group, "source", path) for path in paths)
    assert actual_references == references
    for row in removed:
        for material in row["replacement"]["materials"]:
            assert any(
                group == row["group"] and path == material for group, _, path in fixed
            )


# 本模块独立审阅的范围;不从另一个测试模块继承白名单或权威预期。
REVIEWED = frozenset(
    {
        "scripts/a9_acceptance.py",
        "scripts/verification_scope_audit.py",
        "tests/fixtures/a9_coverage.json",
        "tests/test_a9_scope.py",
        "tests/test_a9_integrity.py",
        "docs/contracts/verification-status.md",
    }
)


def _prepared_repository(target: Path) -> Path:
    return prepared_repository(
        target, reviewed=REVIEWED, verified_groups=frozenset({"A8", "A9"})
    )


def test_a9_story_coverage_does_not_depend_on_live_read_contract(
    tmp_path: Path,
) -> None:
    root = _prepared_repository(tmp_path / "repo")
    contract = root / "docs/contracts/read-validation.md"
    contract.write_bytes(contract.read_bytes() + b"\n")
    result = writer_conclusion(root, tmp_path / "run", 9)
    assert result["story_coverage"]["document"] == (
        "docs/verification/contracts-read-validation-history.md"
    )
    assert result["story_coverage"]["count"] == 42


def test_a9_provenance_replay_points_to_frozen_rules(tmp_path: Path) -> None:
    root = _prepared_repository(tmp_path / "repo")
    result = writer_conclusion(root, tmp_path / "run", 9)
    assert result["status"] == "passed", result["reasons"]
    assert result["capability_evidence"]["provenance_replay"] == {
        "cases": ["tests/test_read_context.py"],
        "materials": [
            "src/paper_radar/reading/context.py",
            "docs/verification/contracts-read-validation-history.md",
        ],
    }


@pytest.mark.parametrize(
    "document",
    ["README.md", "docs/contracts/pi-rpc.md", "docs/contracts/verification-status.md"],
)
def test_a8_live_document_changes_keep_writer_passed(
    tmp_path: Path, document: str
) -> None:
    root = _prepared_repository(tmp_path / "repo")
    target = root / document
    target.write_bytes(target.read_bytes() + b"\n")
    result = writer_conclusion(root, tmp_path / "run", 8)
    assert result["status"] == "passed", result["reasons"]
    assert result["a8_verified"] is True


@pytest.mark.parametrize(
    "document",
    [
        "README.md",
        "GLOSSARY.md",
        "intent/draft.md",
        "docs/contracts/read-validation.md",
        "docs/contracts/frozen-contracts.md",
        "docs/contracts/runtime-config.md",
        "docs/contracts/config-projections.md",
        "docs/contracts/config-snapshots.md",
        "docs/contracts/verification-status.md",
        "docs/contracts/backup-restore.md",
    ],
)
def test_a9_live_document_changes_keep_writer_passed(
    tmp_path: Path, document: str
) -> None:
    root = _prepared_repository(tmp_path / "repo")
    target = root / document
    target.write_bytes(target.read_bytes() + b"\n")
    result = writer_conclusion(root, tmp_path / "run", 9)
    assert result["status"] == "passed", result["reasons"]
    assert result["a9_verified"] is True


@pytest.mark.parametrize(
    ("group", "material"),
    [
        ("8", "docs/verification/contracts-pi-rpc-history.md"),
        ("8", "docs/verification/a8-requirements.md"),
        ("8", "tests/fixtures/a8_capabilities.json"),
        ("9", "docs/verification/contracts-read-validation-history.md"),
        ("9", "tests/fixtures/a9_coverage.json"),
        ("9", "docs/verification/a9-scope-review.md"),
    ],
)
def test_frozen_proof_damage_still_rejects_writer(
    tmp_path: Path, group: str, material: str
) -> None:
    root = _prepared_repository(tmp_path / "repo")
    target = root / material
    target.write_bytes(target.read_bytes() + b"\n")
    result = writer_conclusion(root, tmp_path / "run", int(group))
    assert result["status"] == "failed"
    assert result[f"a{group}_verified"] is False
    assert {reason["code"] for reason in result["reasons"]} == {"scope_drift"}


def test_rebound_history_still_requires_original_story_ids(tmp_path: Path) -> None:
    root = _prepared_repository(tmp_path / "repo")
    relative = "docs/verification/contracts-read-validation-history.md"
    history = root / relative
    text = history.read_text()
    assert "| US01：" in text
    history.write_text(text.replace("| US01：", "| US00："))
    program = f"""
import hashlib
import re
from pathlib import Path
root = Path.cwd()
digest = hashlib.sha256((root / {relative!r}).read_bytes()).hexdigest()
scope = root / 'scripts/a9_scope.py'
pattern = (
    r'("docs/verification/contracts-read-validation-history.md",\\s*")'
    r'[0-9a-f]{{64}}'
)
text, count = re.subn(pattern, lambda match: match[1] + digest, scope.read_text())
assert count == 1
scope.write_text(text)
"""
    subprocess.run((sys.executable, "-B", "-c", program), cwd=root, check=True)
    result = writer_conclusion(root, tmp_path / "run", 9)
    assert result["status"] == "failed"
    assert {reason["code"] for reason in result["reasons"]} == {"scope_drift"}
    assert any(reason.get("item") == "coverage" for reason in result["reasons"])
    assert all(row["result"] == "passed" for row in result["fixture_files"])
