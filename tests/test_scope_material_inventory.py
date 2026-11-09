"""#126 分类清单以冻结基线回放核验, 不随后续解绑改写历史。"""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "78413e6524e0900cb7051a70adcf590fa2e01799"
INVENTORY = ROOT / "docs/verification/scope-material-inventory.json"


@pytest.fixture(scope="module")
def baseline_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("scope-inventory-baseline")
    archive = subprocess.run(
        ("git", "archive", BASELINE), cwd=ROOT, capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(root, filter="data")
    return root


def test_inventory_preserves_every_baseline_group_kind_path(
    baseline_repository: Path,
) -> None:
    # 子进程执行基线自己的 CLI, 不依赖未来中央登记解释器的实现。
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        (sys.executable, "-B", "-m", "scripts.audit_verification_scope", "--json"),
        cwd=baseline_repository,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    inventory: dict[str, Any] = json.loads(INVENTORY.read_text())
    assert inventory["baseline_commit"] == BASELINE
    canonical = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert inventory["source"]["audit_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert report["issues"] == []
    assert report["affected_groups"] == []
    rows = inventory["bindings"]
    expected = {
        (row["group"], row["kind"], row["path"]): row["expected_sha256"]
        for row in report["files"]
    }
    actual = {
        (row["group"], row["kind"], row["path"]): row["old_sha256"] for row in rows
    }
    assert len(rows) == len(actual) == len(expected) == 1229
    assert len({row["group"] for row in rows}) == 11
    assert len({row["path"] for row in rows}) == 710
    assert actual == expected


def test_classification_distinguishes_authority_from_replacement(
    baseline_repository: Path,
) -> None:
    inventory = json.loads(INVENTORY.read_text())
    rules = inventory["classification_rules"]
    live = set(rules["live_documents"]["exact_paths"])
    expected_live = {
        "README.md",
        "GLOSSARY.md",
        "intent/draft.md",
        *(
            path.relative_to(baseline_repository).as_posix()
            for path in (baseline_repository / "docs/contracts").glob("*.md")
        ),
    }
    # 后续明确授权的精确活路径;冻结基线集合保持,不扫描当前目录放行未知文档。
    authorized_additions = {
        "docs/contracts/pi-execution.md",
        "docs/contracts/offline-pytest-diagnostics.md",
        "docs/contracts/live-evidence.md",
        "docs/contracts/read-execution.md",
        "docs/roadmap.md",
    }
    assert live == expected_live | authorized_additions
    assert all((ROOT / path).is_file() for path in authorized_additions)
    assert "path_prefixes" not in rules["live_documents"]
    rows = inventory["bindings"]
    kept = {
        (row["group"], row["path"]) for row in rows if row["disposition"] == "retain"
    }
    removed = []
    for row in rows:
        category = rules["categories"][row["category"]]
        assert row["purpose"]
        assert category["classification_authority"]
        assert row["classification_authority"] == row["category"]
        if row["path"] in live:
            removed.append(row)
            assert row["category"] == "live_document"
            assert row["disposition"] == "remove_after_migration"
            replacement = row["replacement"]
            assert replacement["reason"]
            if replacement["type"] == "frozen_materials":
                assert replacement["materials"]
                for path in replacement["materials"]:
                    assert (row["group"], path) in kept
            else:
                assert replacement["type"] == "non_evidence_context"
        else:
            assert row["disposition"] == "retain"
            assert row["replacement"] == {"type": "original_binding"}
    # A8 3 条、A9 10 条、A10 6 条, 同一路径跨组分别计数。
    assert len(removed) == 19
    assert {row["group"] for row in removed} == {"A8", "A9", "A10"}
    # 这些 Markdown 与 JSON 仍是冻结依据, 不能被扩展名白名单吞掉。
    for path in (
        "docs/verification/offline-evidence.md",
        "docs/verification/a10-requirements.md",
        "docs/verification/contracts-read-validation-history.md",
        "tests/fixtures/a10_coverage.json",
        "docs/adr/0033-classify-journal-articles-from-explicit-source-types.md",
    ):
        assert path not in live
        assert all(
            row["disposition"] == "retain" for row in rows if row["path"] == path
        )


def test_migration_plan_replays_couplings_and_unbound_disclosure(
    baseline_repository: Path,
) -> None:
    inventory = json.loads(INVENTORY.read_text())
    rows = inventory["bindings"]
    bound = {row["path"] for row in rows}
    disclosed = inventory["unbound_materials"]
    expected_unbound = {
        path.relative_to(baseline_repository).as_posix()
        for directory in ("docs/contracts", "docs/verification")
        for path in (baseline_repository / directory).iterdir()
        if path.is_file()
        and path.relative_to(baseline_repository).as_posix() not in bound
    }
    assert {row["path"] for row in disclosed} == expected_unbound
    assert len(disclosed) == len(expected_unbound)
    assert all(row["disposition"] == "disclose_without_binding" for row in disclosed)
    for coupling in inventory["hidden_couplings"]:
        for pointer in coupling["locations"]:
            path, text = pointer["path"], pointer["baseline_text"]
            assert text in (baseline_repository / path).read_text(), coupling["id"]
        assert coupling["migration_action"]
    a10 = json.loads(
        (baseline_repository / "tests/fixtures/a10_coverage.json").read_text()
    )
    for coupling in inventory["hidden_couplings"]:
        if coupling["id"] != "a10_coverage_pointers":
            continue
        for entry in coupling["references"]:
            path = entry["path"]
            for field in ("scope_materials", "public_behavior_pointers"):
                expected_ids = sorted(
                    row["requirement_id"]
                    for row in a10["requirements"]
                    if path in row.get(field, [])
                )
                assert entry[field]["requirement_ids"] == expected_ids
                assert entry[field]["count"] == len(expected_ids)


def test_excerpt_review_uses_existing_requirement_carriers(
    baseline_repository: Path,
) -> None:
    inventory = json.loads(INVENTORY.read_text())
    review = inventory["excerpt_review"]
    a10 = json.loads(
        (baseline_repository / "tests/fixtures/a10_coverage.json").read_text()
    )
    assert len(a10["requirements"]) == 693
    assert len(a10["source_documents"]) == 37
    for source in a10["source_documents"]:
        assert (
            hashlib.sha256(source["original_text"].encode()).hexdigest()
            == source["sha256"]
        )
    by_behavior = {row["behavior_id"]: row for row in a10["behavior_catalog"]}
    fixed = {
        (row["group"], row["path"])
        for row in inventory["bindings"]
        if row["disposition"] == "retain"
    }
    for assessment in review["assessments"]:
        assert assessment["reason"]
        assert assessment["decision"] == "existing_frozen_carrier"
        for path in assessment["carriers"]:
            assert (assessment["group"], path) in fixed
        if "behavior_id" in assessment:
            behavior = assessment["behavior_id"]
            assert assessment["baseline_behavior"] == by_behavior[behavior]
            ids = sorted(
                row["requirement_id"]
                for row in a10["requirements"]
                if behavior in row.get("mapped_behavior_ids", [])
            )
            assert assessment["requirement_ids"] == ids
    assert {
        row["behavior_id"] for row in review["assessments"] if "behavior_id" in row
    } == {
        "documented_decisions",
        "sampling_operational_docs",
        "documents_and_operational_boundary",
    }
    # 摘录仅在没有既有承载者时添加, 若后续审阅确需摘录, 原文必须可回放。
    for excerpt in review["frozen_excerpts"]:
        assert excerpt["baseline_commit"] == BASELINE
        source = (baseline_repository / excerpt["path"]).read_text()
        assert excerpt["section"] in source
        assert excerpt["original_text"] in source
        assert (
            hashlib.sha256(excerpt["original_text"].encode()).hexdigest()
            == excerpt["sha256"]
        )
