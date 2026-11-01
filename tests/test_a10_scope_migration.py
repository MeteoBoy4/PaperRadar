"""A10 活文档解绑的逐项迁移及 writer 公共边界。"""

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "78413e6524e0900cb7051a70adcf590fa2e01799"
HEAD_EXPECTATION_CENTRALIZATION = "69aaa69c76f821df1610a5bcc41bbc9fe88e3686"
LEDGER = "tests/fixtures/a10_coverage.json"
MIGRATION = "docs/verification/a10-scope-document-migration.json"
LIVE = {
    "README.md",
    "GLOSSARY.md",
    "intent/draft.md",
    "docs/contracts/backup-restore.md",
    "docs/contracts/fixture-audit.md",
    "docs/contracts/verification-status.md",
}


def baseline_json(relative: str) -> dict[str, Any]:
    value = json.loads(
        subprocess.run(
            ["git", "show", f"{BASELINE}:{relative}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
    )
    assert isinstance(value, dict)
    return value


def test_migration_preserves_sources_and_accounts_for_every_disposition() -> None:
    old = baseline_json(LEDGER)
    current = json.loads((ROOT / LEDGER).read_bytes())
    assert current["ledger_revision"] == 2
    assert current["methodology"]["scope"] != old["methodology"]["scope"]
    assert current["original_inventory_ids"] == old["original_inventory_ids"]
    assert current["source_documents"] == old["source_documents"]
    assert len(current["requirements"]) == 693
    identity_fields = (
        "requirement_id",
        "issue",
        "source_id",
        "source_url",
        "source_kind",
        "category",
        "section",
        "list_context",
        "source_line_start",
        "source_line_end",
        "original_text",
        "spec_status",
        "semantic_role",
        "supersession",
        "refinement",
        "duplicate_of",
    )
    assert [
        {key: row[key] for key in identity_fields} for row in current["requirements"]
    ] == [{key: row[key] for key in identity_fields} for row in old["requirements"]]
    assert len(current["source_documents"]) == 37
    for source in current["source_documents"]:
        assert (
            hashlib.sha256(source["original_text"].encode()).hexdigest()
            == source["sha256"]
        )
    migration = json.loads((ROOT / MIGRATION).read_bytes())
    before = {row["requirement_id"]: row["status"] for row in old["requirements"]}
    changes = [
        {
            "requirement_id": row["requirement_id"],
            "before": before[row["requirement_id"]],
            "after": row["status"],
        }
        for row in current["requirements"]
        if before[row["requirement_id"]] != row["status"]
    ]
    assert changes == migration["requirement_disposition_changes"]
    assert {row["requirement_id"] for row in changes} == {
        "A10-104-BODY-001",
        "A10-105-BODY-001",
        "A10-106-BODY-001",
        "A10-100-C6405695568-CLAUSE-037",
    }
    assert Counter(row["status"] for row in current["requirements"]) == {
        "covered": 546,
        "operational": 111,
        "not_assessed": 29,
        "superseded": 7,
    }


def pointer_occurrences(
    value: dict[str, Any],
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    occurrences = {}
    for section in ("requirements", "behavior_catalog", "extra_safety_assertions"):
        for row in value[section]:
            identity = row.get(
                "requirement_id", row.get("behavior_id", row.get("assertion_id"))
            )
            for field in (
                "public_behavior_pointers",
                "documentation_pointers",
                "scope_materials",
            ):
                for pointer in row.get(field, []):
                    if pointer in LIVE:
                        occurrences[(section, identity, field, pointer)] = row
    for identity, row in value["capabilities"].items():
        for pointer in row["materials"]:
            if pointer in LIVE:
                occurrences[("capabilities", identity, "materials", pointer)] = row
    return occurrences


def test_every_old_document_pointer_has_a_reviewable_semantic_destination() -> None:
    old = baseline_json(LEDGER)
    current = json.loads((ROOT / LEDGER).read_bytes())
    migration = json.loads((ROOT / MIGRATION).read_bytes())
    assert pointer_occurrences(current) == {}
    inventory = json.loads(
        (ROOT / "docs/verification/scope-material-inventory.json").read_bytes()
    )
    assert migration["removed_bindings"] == [
        entry
        for entry in inventory["bindings"]
        if entry["group"] == "A10" and entry["disposition"] == "remove_after_migration"
    ]
    assert {entry["path"] for entry in migration["removed_bindings"]} == LIVE
    expected = pointer_occurrences(old)
    actual = {
        (
            entry["section"],
            entry["owner_id"],
            entry["field"],
            entry["old_pointer"],
        ): entry
        for entry in migration["pointer_migrations"]
    }
    assert actual.keys() == expected.keys()
    assert len(actual) == len(migration["pointer_migrations"])
    for key, row in expected.items():
        entry = actual[key]
        assert entry["reason"]
        assert entry["behavior_ids"] == row.get(
            "mapped_behavior_ids",
            [row.get("behavior_id")] if "behavior_id" in row else [],
        )
        assert entry["action"] in {
            "remove_context",
            "replace_frozen_evidence",
            "historical_operation",
        }
        assert entry["action"] != "remove_context" or key[2] in {
            "scope_materials",
            "documentation_pointers",
            "materials",
        }
        assert entry["new_pointers"] or entry["action"] == "remove_context"
        for destination in entry["destinations"]:
            rows = current[destination["section"]]
            selected = (
                rows[destination["owner_id"]]
                if isinstance(rows, dict)
                else next(
                    item
                    for item in rows
                    if item.get(
                        "requirement_id",
                        item.get("behavior_id", item.get("assertion_id")),
                    )
                    == destination["owner_id"]
                )
            )
            assert set(destination["pointers"]) <= set(selected[destination["field"]])
    behaviors = {row["behavior_id"]: row for row in current["behavior_catalog"]}
    assert behaviors["documented_decisions"]["status"] == "covered"
    for identity in ("sampling_operational_docs", "documents_and_operational_boundary"):
        assert behaviors[identity]["status"] == "operational"
        assert (
            behaviors[identity]["evidence_kind"]
            == "frozen_historical_operation_and_documentation"
        )
    excerpts = json.loads(
        (ROOT / "docs/verification/a10-documentation-excerpts.json").read_bytes()
    )
    for excerpt in excerpts["excerpts"]:
        original = subprocess.run(
            ["git", "show", f"{BASELINE}:{excerpt['path']}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        assert hashlib.sha256(original).hexdigest() == excerpt["source_sha256"]
        retained = b"".join(
            original.splitlines(keepends=True)[
                excerpt["line_start"] - 1 : excerpt["line_end"]
            ]
        )
        assert retained.decode() == excerpt["original_text"]
        assert hashlib.sha256(retained).hexdigest() == excerpt["sha256"]
        assert excerpt["requirement_ids"]


def candidate_writer(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """仅合成副本确认本轮已审阅候选字节,不写生产登记或正式回执。"""
    from scripts import a10_acceptance

    for name in (
        "REQUIRED_SOURCE_MODULES",
        "REQUIRED_TEST_MODULES",
        "REQUIRED_FIXTURE_FILES",
    ):
        monkeypatch.setattr(
            a10_acceptance,
            name,
            tuple(
                (relative, hashlib.sha256((root / relative).read_bytes()).hexdigest())
                for relative, _ in getattr(a10_acceptance, name)
            ),
        )


def test_writer_accepts_changes_to_all_six_unbound_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.a2_full_support import repository_copy
    from tests.a10_acceptance_support import conclude, same_a10_run

    root = repository_copy(tmp_path / "repo")
    candidate_writer(root, monkeypatch)
    for relative in LIVE:
        path = root / relative
        path.write_bytes(path.read_bytes() + b"\nCurrent documentation may evolve.\n")
    inputs = same_a10_run(tmp_path, root=root)
    _, result = conclude(tmp_path, inputs, root=root)
    assert result["status"] == "passed", result["reasons"]
    assert result["requirements_coverage"]["dispositions"] == {
        "covered": 546,
        "superseded": 7,
        "not_assessed": 29,
        "operational": 111,
    }


@pytest.mark.parametrize(
    "fault",
    [
        "old_revision",
        "old_methodology",
        "source_sha",
        "requirement_id",
        "unfixed_requirement",
        "unfixed_behavior",
        "unfixed_documentation",
        "unfixed_capability",
        "unmapped_covered",
        "operation_as_covered",
        "operation_from_product_spec",
    ],
)
def test_writer_rejects_semantically_damaged_rebound_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from tests.a2_full_support import repository_copy
    from tests.a10_acceptance_support import conclude, same_a10_run

    root = repository_copy(tmp_path / "repo")
    path = root / LEDGER
    value = json.loads(path.read_bytes())
    covered = next(row for row in value["requirements"] if row["status"] == "covered")
    behavior = value["behavior_catalog"][0]
    if fault == "old_revision":
        value["ledger_revision"] = 1
    elif fault == "old_methodology":
        value["methodology"]["scope"] = baseline_json(LEDGER)["methodology"]["scope"]
    elif fault == "source_sha":
        value["source_documents"][0]["sha256"] = "0" * 64
    elif fault == "requirement_id":
        covered["requirement_id"] = "invented-unreviewed-id"
    elif fault == "unfixed_requirement":
        covered["public_behavior_pointers"] = ["intent/draft.md"]
    elif fault == "unfixed_behavior":
        behavior["public_behavior_pointers"] = ["intent/draft.md"]
    elif fault == "unfixed_documentation":
        behavior["documentation_pointers"] = ["intent/draft.md"]
    elif fault == "unfixed_capability":
        value["capabilities"]["registration"]["materials"] = ["intent/draft.md"]
    elif fault == "unmapped_covered":
        covered["mapped_behavior_ids"] = ["sampling_operational_docs"]
    elif fault == "operation_as_covered":
        next(
            row
            for row in value["behavior_catalog"]
            if row["behavior_id"] == "sampling_operational_docs"
        )["status"] = "covered"
    elif fault == "operation_from_product_spec":
        next(
            row
            for row in value["behavior_catalog"]
            if row["behavior_id"] == "sampling_operational_docs"
        )["operational_source_ids"] = ["issue-104-body"]
    path.write_text(json.dumps(value, ensure_ascii=False))
    candidate_writer(root, monkeypatch)
    inputs = same_a10_run(tmp_path, root=root)
    _, result = conclude(tmp_path, inputs, root=root)
    assert result["status"] == "failed"
    assert any(
        reason["code"] == "scope_drift" and reason.get("item") == "coverage"
        for reason in result["reasons"]
    )


def test_frozen_negative_case_is_replaced_without_reducing_the_denominator() -> None:
    migration = json.loads((ROOT / MIGRATION).read_bytes())
    change = migration["frozen_test_changes"]
    assert change == [
        {
            "path": "tests/test_a10_integrity.py",
            "test": "test_actual_rule_support_and_coverage_bytes_are_fixed",
            "before": "docs/contracts/fixture-audit.md",
            "after": (
                "docs/adr/0032-relax-paper-acquisition-without-evading-access-controls.md"
            ),
            "before_count": 10,
            "after_count": 10,
            "reason": (
                "S1(b)：现状Contract解绑；以本组仍冻结、原参数表尚未列入的"
                "ADR0032等量替换，保留其余9项及全部拒绝断言。"
            ),
        }
    ]
    old = subprocess.run(
        ["git", "show", f"{BASELINE}:tests/test_a10_integrity.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    # 文档迁移仍按#139之前的不可变字节核验,不把后续合法变化写回旧证明。
    before_centralization = subprocess.run(
        [
            "git",
            "show",
            f"{HEAD_EXPECTATION_CENTRALIZATION}^:tests/test_a10_integrity.py",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    assert hashlib.sha256(before_centralization).hexdigest() == (
        "87060a1084532011f78230314d278030f53dff38245d58ecb64aa13780b3a239"
    )
    assert before_centralization.decode() == old.replace(
        '"docs/contracts/fixture-audit.md"',
        '"docs/adr/0032-relax-paper-acquisition-without-evading-access-controls.md"',
        1,
    )
    # #139仅集中人工head预期;独立绑定其交付checkpoint和台账SHA,拒绝其他改动。
    after_centralization = subprocess.run(
        [
            "git",
            "show",
            f"{HEAD_EXPECTATION_CENTRALIZATION}:tests/test_a10_integrity.py",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    assert hashlib.sha256(after_centralization).hexdigest() == (
        "49e43ecaec3bedb6c3af819cb599f8d8a7ed8a49aa28745500843ebfa07fb97e"
    )
    assert (ROOT / "tests/test_a10_integrity.py").read_bytes() == after_centralization


@pytest.mark.parametrize(
    "relative",
    [
        LEDGER,
        "docs/verification/a10-documentation-excerpts.json",
        "docs/adr/0032-relax-paper-acquisition-without-evading-access-controls.md",
    ],
)
def test_writer_still_rejects_changed_frozen_material_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    from tests.a2_full_support import repository_copy
    from tests.a10_acceptance_support import conclude, same_a10_run

    root = repository_copy(tmp_path / "repo")
    candidate_writer(root, monkeypatch)
    target = root / relative
    target.write_bytes(target.read_bytes() + b"\n")
    inputs = same_a10_run(tmp_path, root=root)
    _, result = conclude(tmp_path, inputs, root=root)
    assert result["status"] == "failed"
    assert "scope_drift" in {reason["code"] for reason in result["reasons"]}
