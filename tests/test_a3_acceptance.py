"""A3 公共结论必须绑定本次所有前置和实际执行。"""

import json
from pathlib import Path

import pytest

from scripts.a3_acceptance import write_a3_conclusion
from scripts.offline_evidence import file_sha256
from tests.a3_acceptance_support import ROOT, conclude, same_a3_run


def test_a3_records_its_independent_scope_actual_revision_and_all_bound_inputs(
    tmp_path: Path,
) -> None:
    evidence, a1_path, a1, full_path, full, baseline = same_a3_run(tmp_path)
    path, result = write_a3_conclusion(
        ROOT,
        evidence,
        a1_path,
        a1,
        full_path,
        full,
        tmp_path,
        baseline,
        expected_run_id=a1["run_id"],
    )
    assert path.name == "synthetic-full-a2.a3.json"
    assert json.loads(path.read_bytes()) == result
    assert result["status"] == "passed", result["reasons"]
    assert result["scope"] == "a3_artifact_backup_restore"
    assert (result["parent_issue"], result["issue"], result["format_version"]) == (
        29,
        35,
        1,
    )
    assert result["a3_verified"] is True
    assert result["stage_a_verified"] is result["live_verified"] is False
    assert result["migration_revision"] == "a601_paper_facts"
    assert result["environment"]["sqlite"]
    assert result["format_versions"] == {
        "artifact": 1,
        "blob_layout": 1,
        "backup": 1,
        "backup_database_revision": "a601_paper_facts",
    }
    for key, source in (
        ("evidence", evidence),
        ("a1_conclusion", a1_path),
        ("a2_full_conclusion", full_path),
        ("pytest_receipt", evidence.with_suffix(".pytest.json")),
    ):
        assert result[key + "_file"] == source.name
        assert result[key + "_sha256"] == file_sha256(source)
    assert all(row["result"] == "passed" for row in result["test_execution"])
    assert {
        "paper_business_facts",
        "stage_input_fingerprints",
        "attempts_and_leases",
        "report_rebuild",
        "pi_execution",
        "docling_execution",
        "live_source_audit",
        "nas_restore",
    } <= set(result["not_assessed"])


@pytest.mark.parametrize(
    "case",
    [
        "missing_a1",
        "missing_full",
        "missing_evidence",
        "returned_value",
        "a1_failed",
        "full_failed",
        "verified_not_bool",
        "a1_old_format",
        "full_old_format",
        "evidence_old_format",
        "old_run",
        "wrong_file",
        "wrong_scope",
        "wrong_evidence_hash",
        "wrong_a1_hash",
        "bool_check_exit",
        "skipped_check",
        "missing_check",
        "incomplete",
    ],
)
def test_same_run_and_predecessor_success_are_independent_requirements(
    tmp_path: Path, case: str
) -> None:
    inputs = same_a3_run(tmp_path)
    evidence, a1_path, a1, full_path, full, _ = inputs
    raw = json.loads(evidence.read_bytes())
    expected = "binding_mismatch"
    if case == "missing_a1":
        a1_path.unlink()
    elif case == "missing_full":
        full_path.unlink()
    elif case == "missing_evidence":
        evidence.unlink()
        expected = "evidence_unavailable"
    elif case == "returned_value":
        a1["a1_verified"] = False
    elif case == "a1_failed":
        a1.update(status="failed", a1_verified=False)
        expected = "prerequisite_not_passed"
    elif case == "full_failed":
        full.update(status="failed", a2_verified=False)
        expected = "prerequisite_not_passed"
    elif case == "verified_not_bool":
        full["a2_verified"] = 1
        expected = "prerequisite_not_passed"
    elif case.endswith("old_format"):
        selected = (
            a1
            if case == "a1_old_format"
            else full
            if case == "full_old_format"
            else raw
        )
        selected["format_version"] = 0
        expected = "format_mismatch"
    elif case == "old_run":
        full["run_id"] = "old-run"
    elif case == "wrong_file":
        full["evidence_file"] = "old-run.json"
    elif case == "wrong_scope":
        full["scope"] = "a2_01_profile_runtime_config_snapshots"
    elif case == "wrong_evidence_hash":
        full["evidence_sha256"] = "0" * 64
    elif case == "wrong_a1_hash":
        full["a1_conclusion_sha256"] = "0" * 64
    elif case in {"bool_check_exit", "skipped_check", "missing_check"}:
        expected = "check_not_passed"
        if case == "bool_check_exit":
            raw["checks"][0]["exit_code"] = False
        elif case == "skipped_check":
            raw["checks"][0].update(status="not_run", reason="skipped", exit_code=None)
        else:
            raw["checks"].pop()
    elif case == "incomplete":
        full["status"] = "incomplete"
        expected = "run_incomplete"
    if evidence.exists():
        evidence.write_text(json.dumps(raw), encoding="utf-8")
    if case not in {"missing_a1", "returned_value"}:
        a1_path.write_text(json.dumps(a1), encoding="utf-8")
    if case != "missing_full":
        full_path.write_text(json.dumps(full), encoding="utf-8")
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == ("incomplete" if case == "incomplete" else "failed")
    assert result["a3_verified"] is False
    assert expected in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "old_run",
        "old_format",
        "bool_format",
        "bool_exit",
        "float_exit",
        "incomplete",
        "missing_module",
        "bool_count",
        "negative_count",
        "text_count",
        "float_count",
        "missing_count",
        "skip",
        "deselect",
        "collect_only",
        "modules_not_object",
    ],
)
def test_a3_requires_real_complete_integer_execution_counts(
    tmp_path: Path, case: str
) -> None:
    inputs = same_a3_run(tmp_path)
    evidence, _, _, full_path, full, _ = inputs
    receipt = evidence.with_suffix(".pytest.json")
    raw = json.loads(receipt.read_bytes())
    module = raw["modules"]["tests/test_artifact_contract.py"]
    if case == "old_run":
        raw["run_id"] = "old-run"
    elif case == "old_format":
        raw["format_version"] = 0
    elif case == "bool_format":
        raw["format_version"] = True
    elif case in {"bool_exit", "float_exit"}:
        raw["exit_code"] = False if case == "bool_exit" else 0.0
    elif case == "incomplete":
        raw["completed"] = False
    elif case == "missing_module":
        raw["modules"].pop("tests/test_artifact_contract.py")
    elif case == "bool_count":
        module["failed"] = False
    elif case == "negative_count":
        module["failed"] = -1
    elif case == "text_count":
        module["failed"] = "0"
    elif case == "float_count":
        module["failed"] = 0.0
    elif case == "missing_count":
        module.pop("failed")
    elif case == "skip":
        module.update(passed=14, skipped=1)
    elif case == "deselect":
        module.update(collected=14, passed=14, deselected=1)
    elif case == "collect_only":
        module["passed"] = 0
    elif case == "modules_not_object":
        raw["modules"] = []
    receipt.write_text(json.dumps(raw), encoding="utf-8")
    if case == "missing":
        receipt.unlink()
    # 前置可在自己的固定范围通过;A3必须另外核对这部分计数。
    full["pytest_receipt_sha256"] = file_sha256(receipt)
    full_path.write_text(json.dumps(full), encoding="utf-8")
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == ("incomplete" if case == "incomplete" else "failed")
    assert result["a3_verified"] is False
    expected = (
        "format_mismatch" if case == "bool_format" else "test_execution_not_passed"
    )
    assert expected in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize("case", ["source", "helper", "fixture", "baseline"])
def test_fixed_bytes_and_running_identity_cannot_drift(
    tmp_path: Path, case: str
) -> None:
    from dataclasses import replace

    from tests.a2_full_support import repository_copy

    root = repository_copy(tmp_path / "repo")
    material = tmp_path / "material"
    material.mkdir()
    inputs = same_a3_run(material, root=root)
    if case == "source":
        selected = root / "src/paper_radar/backup/service.py"
        selected.write_bytes(selected.read_bytes() + b"\n# changed\n")
    elif case == "helper":
        (root / "scripts/verification_checks.py").unlink()
    elif case == "fixture":
        (root / "tests/fixtures/a3_storage_recovery.json").unlink()
    else:
        inputs = (
            inputs[0],
            inputs[1],
            inputs[2],
            inputs[3],
            inputs[4],
            replace(inputs[5], lockfile_sha256="0" * 64),
        )
    _, result = conclude(material, inputs, root=root)
    assert result["status"] == "failed"
    assert "identity_changed" in {reason["code"] for reason in result["reasons"]}
    if case != "baseline":
        assert "scope_drift" in {reason["code"] for reason in result["reasons"]}


def test_a3_records_missing_dependencies_and_captured_interrupt_without_raw_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    inputs = same_a3_run(tmp_path)
    original = importlib.metadata.version

    def unavailable(name: str) -> str:
        if name == "alembic":
            raise importlib.metadata.PackageNotFoundError("PRIVATE_METADATA")
        return original(name)

    monkeypatch.setattr(importlib.metadata, "version", unavailable)
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert "dependency_unavailable" in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE" not in path.read_text()


def test_actual_new_migration_head_is_rejected_until_explicitly_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from paper_radar.storage import database

    inputs = same_a3_run(tmp_path)
    migrations = tmp_path / "migrations"
    shutil.copytree(Path(database.__file__).parent / "migrations", migrations)
    (migrations / "versions/unregistered.py").write_text(
        "revision='unregistered'\ndown_revision='a601_paper_facts'\n"
        "def upgrade():pass\ndef downgrade():pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(database, "_MIGRATIONS", migrations)
    _, result = conclude(tmp_path, inputs)
    assert result["migration_revision"] == "unregistered"
    assert result["status"] == "failed"
    assert "migration_unavailable" in {reason["code"] for reason in result["reasons"]}


def test_a3_captured_interrupt_is_incomplete_and_existing_conclusion_is_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    inputs = same_a3_run(tmp_path)

    def interrupt(name: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(importlib.metadata, "version", interrupt)
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == "incomplete"
    assert result["a3_verified"] is False
    old = path.read_bytes()
    with pytest.raises(FileExistsError):
        conclude(tmp_path, inputs)
    assert path.read_bytes() == old


@pytest.mark.parametrize("case", ["migration_failure", "storage_format"])
def test_migration_and_format_failures_are_controlled_and_never_inherited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from paper_radar.storage import artifact_contract, database

    inputs = same_a3_run(tmp_path)
    if case == "migration_failure":

        def fail(path: Path) -> str:
            raise RuntimeError("PRIVATE_MIGRATION_FAILURE")

        monkeypatch.setattr(database, "upgrade_database", fail)
    else:
        monkeypatch.setattr(artifact_contract, "ARTIFACT_FORMAT_VERSION", 2)
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    expected = (
        "migration_unavailable"
        if case == "migration_failure"
        else "storage_format_drift"
    )
    assert expected in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE" not in path.read_text()
