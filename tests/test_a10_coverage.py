"""通过结论边界拒绝虽已重绑字节但未完成或失真的需求台账。"""

import hashlib
import json
from pathlib import Path

import pytest

from tests.a2_full_support import repository_copy
from tests.a10_acceptance_support import conclude, same_a10_run


@pytest.mark.parametrize(
    "fault",
    [
        "draft",
        "open_item",
        "owner_conflict",
        "boolean_format",
        "missing_requirement",
        "duplicate_requirement",
        "source_digest",
        "source_link",
        "source_excerpt",
        "unknown_status",
        "status_object",
        "source_id_object",
        "not_assessed_refs_object",
        "unresolved",
        "no_test",
        "unknown_test_symbol",
        "existing_non_test_symbol",
        "unfixed_material",
        "missing_responsibility",
        "missing_supersession",
        "missing_capability",
    ],
)
def test_rebound_requirement_ledger_must_be_complete_and_point_to_real_fixed_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from scripts import a10_acceptance
    from scripts.a10_scope import REQUIRED_FIXTURE_FILES

    root = repository_copy(tmp_path / "repo")
    path = root / "tests/fixtures/a10_coverage.json"
    ledger = json.loads(path.read_bytes())
    covered = next(row for row in ledger["requirements"] if row["status"] == "covered")
    if fault == "draft":
        ledger["review_state"] = "draft"
    elif fault == "open_item":
        ledger["open_items"] = [{"item_id": "pending_product_assertion"}]
    elif fault == "owner_conflict":
        ledger["owner_conflicts"] = [{"item_id": "unresolved"}]
    elif fault == "boolean_format":
        ledger["format_version"] = True
    elif fault == "missing_requirement":
        ledger["requirements"].pop()
    elif fault == "duplicate_requirement":
        ledger["requirements"][-1] = ledger["requirements"][0]
    elif fault == "source_digest":
        ledger["source_documents"][0]["sha256"] = "0" * 64
    elif fault == "source_link":
        covered["source_url"] = "https://example.invalid/unreviewed"
    elif fault == "source_excerpt":
        covered["original_text"] = "invented requirement outside the retained source"
    elif fault == "unknown_status":
        covered["status"] = "implemented_unscoped"
    elif fault == "status_object":
        covered["status"] = {"unrecognized": True}
    elif fault == "source_id_object":
        covered["source_id"] = []
    elif fault == "not_assessed_refs_object":
        next(row for row in ledger["requirements"] if row["status"] == "not_assessed")[
            "not_assessed_refs"
        ] = [{}]
    elif fault == "unresolved":
        covered["coverage_state"] = "unresolved"
    elif fault == "no_test":
        covered["specific_test_pointers"] = []
    elif fault == "unknown_test_symbol":
        covered["specific_test_pointers"] = [
            "tests/test_a10_acceptance.py::test_nonexistent_assertion"
        ]
    elif fault == "existing_non_test_symbol":
        covered["specific_test_pointers"] = ["tests/test_a10_integrity.py::a10_inputs"]
    elif fault == "unfixed_material":
        covered["scope_materials"] = ["tests/unfixed_requirement.py"]
    elif fault == "missing_responsibility":
        next(row for row in ledger["requirements"] if row["status"] == "not_assessed")[
            "not_assessed_responsibility"
        ] = None
    elif fault == "missing_supersession":
        next(row for row in ledger["requirements"] if row["status"] == "superseded")[
            "supersession"
        ] = []
    elif fault == "missing_capability":
        ledger["capabilities"].pop("registration")
    path.write_text(json.dumps(ledger, ensure_ascii=False))
    monkeypatch.setattr(
        a10_acceptance,
        "REQUIRED_FIXTURE_FILES",
        (
            *(
                (relative, digest)
                for relative, digest in REQUIRED_FIXTURE_FILES
                if relative != "tests/fixtures/a10_coverage.json"
            ),
            (
                "tests/fixtures/a10_coverage.json",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ),
        ),
    )
    inputs = same_a10_run(tmp_path, root=root)
    _, result = conclude(tmp_path, inputs, root=root)
    assert result["status"] == "failed"
    assert any(
        reason["code"] == "scope_drift" and reason.get("item") == "coverage"
        for reason in result["reasons"]
    )
