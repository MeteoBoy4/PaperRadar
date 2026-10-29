"""A5 是同次必需结论,不从前置或退出零继承能力。"""

import json
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.offline_evidence import file_sha256
from tests.a5_acceptance_support import conclude, same_a5_run


def test_a5_is_required_and_declares_all_same_run_predecessors() -> None:
    group = next(group for group in acceptance_groups() if group.name == "A5")
    assert group.required is True
    assert group.dependencies == ("A1", "完整 A2", "A3")
    assert group.suffix == ".a5.json"


def test_a5_records_complete_independent_capabilities_and_live_boundaries(
    tmp_path: Path,
) -> None:
    _, result = conclude(tmp_path, same_a5_run(tmp_path))
    assert result["status"] == "passed", result["reasons"]
    assert result["a5_verified"] is True
    assert result["rpc_verified"] is False
    assert result["capabilities"] == dict.fromkeys(
        (
            "boundary",
            "value",
            "reuse",
            "extraction",
            "payload_replay",
            "comparison",
            "isolated_restore_replay",
        ),
        "passed",
    )

    assert result["migration_revision"] == "feed06_language_provenance"
    assert result["scope"] == "a5_stage_input_fingerprints"
    assert (result["format_version"], result["parent_issue"], result["issue"]) == (
        1,
        47,
        47,
    )
    assert result["stage_a_verified"] is result["live_verified"] is False
    assert {
        "rpc_compatibility",
        "stage_a",
        "read_fingerprints",
        "suggestion_fingerprints",
        "report_fingerprints",
        "paper_fact_mapping",
        "task_budget",
        "live",
        "live_source_audit",
        "nas_restore",
        "automatic_fulltext_reading",
    } <= set(result["not_assessed"])
    assert result["format_versions"] == {
        "stage_inputs": {"boundary": 1, "value": 1, "reuse": 1, "extraction": 1},
        "stage_projections": {"boundary": 1, "value": 1, "reuse": 1, "extraction": 1},
    }
    assert result["environment"]["dependencies"]["pydantic"]
    assert all(row["result"] == "passed" for row in result["test_execution"])


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
    inputs = same_a5_run(tmp_path)
    evidence, a1_path, a1, full_path, full, _, _, _ = inputs
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
    assert result["a5_verified"] is False
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
def test_a5_requires_real_complete_integer_execution_counts(
    tmp_path: Path, case: str
) -> None:
    inputs = same_a5_run(tmp_path)
    evidence, _, _, full_path, full, a3_path, a3, _ = inputs
    receipt = evidence.with_suffix(".pytest.json")
    raw = json.loads(receipt.read_bytes())
    module = raw["modules"]["tests/test_stage_inputs.py"]
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
        raw["modules"].pop("tests/test_stage_inputs.py")
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
    a3["pytest_receipt_sha256"] = file_sha256(receipt)
    a3["a2_full_conclusion_sha256"] = file_sha256(full_path)
    a3_path.write_text(json.dumps(a3), encoding="utf-8")
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == ("incomplete" if case == "incomplete" else "failed")
    assert result["a5_verified"] is False
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
    inputs = same_a5_run(material, root=root)
    if case == "source":
        selected = root / "src/paper_radar/stage_inputs/service.py"
        selected.write_bytes(selected.read_bytes() + b"\n# changed\n")
    elif case == "helper":
        (root / "scripts/verification_checks.py").unlink()
    elif case == "fixture":
        (root / "tests/fixtures/stage_inputs/boundary-v1.json").unlink()
    else:
        inputs = (
            inputs[0],
            inputs[1],
            inputs[2],
            inputs[3],
            inputs[4],
            inputs[5],
            inputs[6],
            replace(inputs[7], lockfile_sha256="0" * 64),
        )
    _, result = conclude(material, inputs, root=root)
    assert result["status"] == "failed"
    assert "identity_changed" in {reason["code"] for reason in result["reasons"]}
    if case != "baseline":
        assert "scope_drift" in {reason["code"] for reason in result["reasons"]}


def test_a5_records_missing_dependencies_and_captured_interrupt_without_raw_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    inputs = same_a5_run(tmp_path)
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

    inputs = same_a5_run(tmp_path)
    migrations = tmp_path / "migrations"
    shutil.copytree(Path(database.__file__).parent / "migrations", migrations)
    (migrations / "versions/unregistered.py").write_text(
        "revision='unregistered'\ndown_revision='feed06_language_provenance'\n"
        "def upgrade():pass\ndef downgrade():pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(database, "_MIGRATIONS", migrations)
    _, result = conclude(tmp_path, inputs)
    assert result["migration_revision"] == "unregistered"
    assert result["status"] == "failed"
    assert "migration_unavailable" in {reason["code"] for reason in result["reasons"]}


def test_a5_captured_interrupt_is_incomplete_and_existing_conclusion_is_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    inputs = same_a5_run(tmp_path)

    def interrupt(name: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(importlib.metadata, "version", interrupt)
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == "incomplete"
    assert result["a5_verified"] is False
    old = path.read_bytes()
    with pytest.raises(FileExistsError):
        conclude(tmp_path, inputs)
    assert path.read_bytes() == old


@pytest.mark.parametrize("predecessor", ["a1", "full", "a3"])
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "returned",
        "run",
        "file",
        "scope",
        "issue",
        "bool_format",
        "status",
        "verified",
        "hash",
        "identity",
    ],
)
def test_every_predecessor_must_independently_bind_and_pass(
    tmp_path: Path,
    predecessor: str,
    fault: str,
) -> None:
    inputs = same_a5_run(tmp_path)
    offset = {"a1": 1, "full": 3, "a3": 5}[predecessor]
    path, value = inputs[offset], inputs[offset + 1]
    assert isinstance(path, Path) and isinstance(value, dict)
    if fault == "missing":
        path.unlink()
    else:
        key, replacement = {
            "returned": ("private_returned_mismatch", True),
            "run": ("run_id", "historical"),
            "file": ("evidence_file", "historical.json"),
            "scope": ("scope", "historical"),
            "issue": ("issue", 0),
            "bool_format": ("format_version", True),
            "status": ("status", "failed"),
            "verified": (
                {"a1": "a1_verified", "full": "a2_verified", "a3": "a3_verified"}[
                    predecessor
                ],
                1,
            ),
            "hash": ("evidence_sha256", "0" * 64),
            "identity": ("worktree_sha256", "0" * 64),
        }[fault]
        value[key] = replacement
        if fault != "returned":
            path.write_text(json.dumps(value))
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert result["a5_verified"] is False


@pytest.mark.parametrize("domain", ["stage_inputs", "stage_projections"])
@pytest.mark.parametrize("stage", ["boundary", "value", "reuse", "extraction"])
@pytest.mark.parametrize("version", [2, True])
def test_actual_production_formats_are_verified_independently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    domain: str,
    stage: str,
    version: object,
) -> None:
    from paper_radar.config import StageName, projections
    from paper_radar.stage_inputs import service

    inputs = same_a5_run(tmp_path)
    module = service if domain == "stage_inputs" else projections
    attribute = (
        "STAGE_INPUT_FORMAT_VERSIONS"
        if domain == "stage_inputs"
        else "PROJECTION_FORMAT_VERSIONS"
    )
    versions = dict(getattr(module, attribute))
    versions[StageName(stage)] = version
    monkeypatch.setattr(module, attribute, versions)
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert "stage_input_format_drift" in {
        reason["code"] for reason in result["reasons"]
    }


def test_stage_input_format_versions_are_public_and_read_only() -> None:
    from paper_radar.config import StageName
    from paper_radar.stage_inputs import STAGE_INPUT_FORMAT_VERSIONS

    assert dict(STAGE_INPUT_FORMAT_VERSIONS) == {
        StageName.BOUNDARY: 1,
        StageName.VALUE: 1,
        StageName.REUSE: 1,
        StageName.EXTRACTION: 1,
    }
    with pytest.raises(TypeError):
        STAGE_INPUT_FORMAT_VERSIONS[StageName.BOUNDARY] = 2  # type: ignore[index]


@pytest.mark.parametrize(
    "damage", ["empty_tests", "empty_sources", "empty_fixtures", "count_keys"]
)
def test_scope_cannot_hide_missing_modules_or_empty_material_sets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from scripts import a5_acceptance

    inputs = same_a5_run(tmp_path)
    attribute = {
        "empty_tests": "REQUIRED_TEST_MODULES",
        "empty_sources": "REQUIRED_SOURCE_MODULES",
        "empty_fixtures": "REQUIRED_FIXTURE_FILES",
        "count_keys": "REQUIRED_TEST_CASE_COUNTS",
    }[damage]
    monkeypatch.setattr(a5_acceptance, attribute, {} if damage == "count_keys" else ())
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert "scope_drift" in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize(
    "damage", ["scope_a1", "scope_stage", "evidence", "a1", "full", "a3", "baseline"]
)
def test_rebound_identity_chain_rejects_integer_boolean_impostors(
    tmp_path: Path, damage: str
) -> None:
    from dataclasses import replace

    inputs = same_a5_run(tmp_path)
    evidence, a1_path, a1, full_path, full, a3_path, a3, baseline = inputs
    raw = json.loads(evidence.read_bytes())
    if damage.startswith("scope_"):
        key = "full_a1_verified" if damage == "scope_a1" else "stage_a_verified"
        raw["scope"][key] = 0
    elif damage == "baseline":
        code = baseline.code.copy()
        code["dirty"] = int(bool(code["dirty"]))  # type: ignore[typeddict-item]
        inputs = (
            evidence,
            a1_path,
            a1,
            full_path,
            full,
            a3_path,
            a3,
            replace(baseline, code=code),
        )
    else:
        value = {"evidence": raw, "a1": a1, "full": full, "a3": a3}[damage]
        value["code"]["dirty"] = int(value["code"]["dirty"])
    # 全部重绑;拒绝确因新组格式核对,不依赖旧字节链接不一致。
    evidence.write_text(json.dumps(raw))
    a1["evidence_sha256"] = file_sha256(evidence)
    a1_path.write_text(json.dumps(a1))
    full.update(
        evidence_sha256=file_sha256(evidence), a1_conclusion_sha256=file_sha256(a1_path)
    )
    full_path.write_text(json.dumps(full))
    a3.update(
        evidence_sha256=file_sha256(evidence),
        a1_conclusion_sha256=file_sha256(a1_path),
        a2_full_conclusion_sha256=file_sha256(full_path),
    )
    a3_path.write_text(json.dumps(a3))
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert not result["a5_verified"]
    expected = "binding_mismatch" if damage.startswith("scope_") else "identity_changed"
    assert expected in {reason["code"] for reason in result["reasons"]}
