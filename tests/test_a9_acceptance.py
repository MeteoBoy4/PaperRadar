"""独立 A9 只证明给定上下文的 Read 离线能力。"""

import hashlib
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import acceptance_groups


def test_a9_is_required_and_only_declares_its_direct_predecessors() -> None:
    group = next(group for group in acceptance_groups() if group.name == "A9")
    assert group.required is True
    assert group.dependencies == ("A1", "完整 A2", "A3")
    assert group.suffix == ".a9.json"
    assert all(
        group.required for group in acceptance_groups() if group.name in {"A4", "A8"}
    )


def test_a9_explicitly_checks_read_contract_without_expanding_a1(
    tmp_path: Path,
) -> None:
    from tests.a2_full_support import repository_copy
    from tests.a9_acceptance_support import conclude, same_a9_run

    root = repository_copy(tmp_path / "repo")
    target = root / "contracts/read/read/v1/schema.json"
    target.unlink()
    _, result = conclude(tmp_path, same_a9_run(tmp_path, root=root), root=root)
    assert result["status"] == "failed"
    assert "read_contract_invalid" in {reason["code"] for reason in result["reasons"]}
    assert result["contracts"][0]["name"] == "read"
    assert result["contracts"][0]["result"] == "failed"
    from scripts.offline_evidence import CONTRACT_NAMES

    assert CONTRACT_NAMES == (
        "boundary",
        "value-prediction",
        "reuse-assessment",
        "decision-reasons",
    )


def test_a9_records_read_rules_contract_same_run_execution_and_coverage(
    tmp_path: Path,
) -> None:
    from tests.a9_acceptance_support import conclude, same_a9_run

    path, result = conclude(tmp_path, same_a9_run(tmp_path))
    assert result["status"] == "passed", result["reasons"]
    assert result["a9_verified"] is True
    assert (result["format_version"], result["issue"], result["parent_issue"]) == (
        1,
        92,
        92,
    )
    assert path.name == "synthetic-a9.a9.json"
    assert (
        result["stage_a_verified"]
        is result["live_verified"]
        is result["rpc_verified"]
        is False
    )
    assert result["migration_revision"] == "feed06_language_provenance"
    assert result["format_versions"] == {
        "read_contract": "v1",
        "evidence_rules": "read-evidence-v1",
        "numeric_rules": "read-numeric-v1",
        "snapshot": 1,
        "backup": 1,
    }
    assert result["contracts"] == [
        {
            "name": "read",
            "version": "v1",
            "schema_sha256": (
                "1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111"
            ),
            "result": "passed",
            "error_category": None,
        }
    ]
    assert result["direct_dependencies"] == ["A1", "完整 A2", "A3"]
    assert result["story_coverage"]["document"] == (
        "docs/verification/contracts-read-validation-history.md"
    )
    assert result["story_coverage"]["count"] == 42
    assert [story["number"] for story in result["story_coverage"]["stories"]] == list(
        range(1, 43)
    )
    assert len(result["coverage_review"]["implementation_decisions"]) == 21
    assert len(result["coverage_review"]["testing_decisions"]) == 20
    assert len(result["coverage_review"]["comments"]) == 4
    assert all(row["result"] == "passed" for row in result["test_execution"])
    assert all(value == "passed" for value in result["capabilities"].values())
    assert {
        "orig_hash_coverage",
        "real_pdf_provenance",
        "map_source_chain",
        "production_pi_model",
        "read_tasks_budgets",
        "stage_a",
        "live",
    } <= set(result["not_assessed"])


@pytest.mark.parametrize("prefix", ["US", "ID", "TD"])
def test_a9_coverage_reads_history_and_rejects_missing_ids_after_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    from scripts import a9_acceptance
    from scripts.a9_scope import REQUIRED_FIXTURE_FILES
    from tests.a9_acceptance_support import ROOT

    paths = (
        "tests/fixtures/a9_coverage.json",
        "docs/contracts/read-validation.md",
        "docs/verification/contracts-read-validation-history.md",
    )
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())

    def bind_documents() -> None:
        registered = dict(REQUIRED_FIXTURE_FILES)
        registered.update(
            (relative, hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest())
            for relative in paths
        )
        monkeypatch.setattr(
            a9_acceptance, "REQUIRED_FIXTURE_FILES", tuple(registered.items())
        )

    bind_documents()
    assert a9_acceptance._coverage(tmp_path) is not None
    history = tmp_path / paths[-1]
    text = history.read_text(encoding="utf-8")
    assert f"| {prefix}01：" in text
    history.write_text(
        text.replace(f"| {prefix}01：", f"| {prefix}00："), encoding="utf-8"
    )
    bind_documents()
    assert a9_acceptance._coverage(tmp_path) is None


def test_failed_read_check_still_records_actual_schema_digest(tmp_path: Path) -> None:
    from scripts.offline_evidence import file_sha256
    from tests.a2_full_support import repository_copy
    from tests.a9_acceptance_support import conclude, same_a9_run

    root = repository_copy(tmp_path / "repo")
    target = root / "contracts/read/read/v1/schema.json"
    target.write_bytes(target.read_bytes() + b"\n")
    _, result = conclude(tmp_path, same_a9_run(tmp_path, root=root), root=root)
    assert result["status"] == "failed"
    assert result["contracts"][0]["schema_sha256"] == file_sha256(target)
    assert result["contracts"][0]["result"] == "failed"
    assert "read_contract_invalid" in {reason["code"] for reason in result["reasons"]}
