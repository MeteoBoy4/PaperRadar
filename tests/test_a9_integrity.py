"""同次文件、固定执行与实际规则不能被历史成功或伪类型替代。"""

import errno
import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.a9_acceptance_support import Inputs, conclude, rebind, same_a9_run


@pytest.fixture
def a9_inputs(tmp_path: Path) -> Inputs:
    return same_a9_run(tmp_path)


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
def test_every_direct_predecessor_requires_real_same_run_bindings(
    tmp_path: Path, a9_inputs: Inputs, predecessor: str, fault: str
) -> None:
    inputs = a9_inputs
    offset = {"a1": 1, "full": 3, "a3": 5}[predecessor]
    path, value = inputs[offset], inputs[offset + 1]
    assert isinstance(path, Path) and isinstance(value, dict)
    expected = "binding_mismatch"
    if fault == "missing":
        path.unlink()
    else:
        key, replacement = {
            "returned": ("PRIVATE_RETURNED_MISMATCH", True),
            "run": ("run_id", "historical"),
            "file": ("evidence_file", "historical.json"),
            "scope": ("scope", "historical"),
            "issue": ("issue", True),
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
        if fault == "bool_format":
            expected = "format_mismatch"
        elif fault in {"status", "verified"}:
            expected = "prerequisite_not_passed"
        elif fault == "identity":
            expected = "identity_changed"
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert result["a9_verified"] is False
    assert expected in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE_RETURNED_MISMATCH" not in path.read_text()


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "old_run",
        "bool_format",
        "bool_exit",
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
        "short_execution",
    ],
)
def test_execution_receipt_requires_every_fixed_real_test(
    tmp_path: Path, a9_inputs: Inputs, fault: str
) -> None:
    path = a9_inputs[0].with_suffix(".pytest.json")
    receipt = json.loads(path.read_bytes())
    module = receipt["modules"]["tests/test_read_recovery.py"]
    if fault == "old_run":
        receipt["run_id"] = "historical"
    elif fault == "bool_format":
        receipt["format_version"] = True
    elif fault == "bool_exit":
        receipt["exit_code"] = False
    elif fault == "incomplete":
        receipt["completed"] = False
    elif fault == "missing_module":
        receipt["modules"].pop("tests/test_read_recovery.py")
    elif fault in {"bool_count", "negative_count", "text_count", "float_count"}:
        module["failed"] = {
            "bool_count": False,
            "negative_count": -1,
            "text_count": "0",
            "float_count": 0.0,
        }[fault]
    elif fault == "missing_count":
        module.pop("failed")
    elif fault == "skip":
        module.update(passed=10, skipped=1)
    elif fault == "deselect":
        module.update(collected=10, passed=10, deselected=1)
    elif fault == "collect_only":
        module["passed"] = 0
    elif fault == "modules_not_object":
        receipt["modules"] = []
    elif fault == "short_execution":
        module.update(collected=10, passed=10)
    path.write_text(json.dumps(receipt))
    if fault == "missing":
        path.unlink()
    rebind(a9_inputs)
    _, result = conclude(tmp_path, a9_inputs)
    assert result["status"] == ("incomplete" if fault == "incomplete" else "failed")
    assert (
        "format_mismatch" if fault == "bool_format" else "test_execution_not_passed"
    ) in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "reordered",
        "skip",
        "failed",
        "bool_exit",
        "float_exit",
        "nonobject",
        "incomplete",
    ],
)
def test_six_actual_checks_cannot_be_omitted_reordered_or_reused(
    tmp_path: Path, a9_inputs: Inputs, fault: str
) -> None:
    path = a9_inputs[0]
    evidence = json.loads(path.read_bytes())
    if fault == "missing":
        evidence["checks"].pop()
    elif fault == "reordered":
        evidence["checks"].reverse()
    elif fault == "nonobject":
        evidence["checks"][0] = None
    elif fault == "incomplete":
        evidence.update(completed=False, overall="incomplete")
    else:
        evidence["checks"][0].update(
            {
                "skip": dict(status="not_run", reason="skipped", exit_code=None),
                "failed": dict(status="failed", reason="exit_nonzero", exit_code=1),
                "bool_exit": dict(exit_code=False),
                "float_exit": dict(exit_code=0.0),
            }[fault]
        )
    path.write_text(json.dumps(evidence))
    rebind(a9_inputs)
    _, result = conclude(tmp_path, a9_inputs)
    assert result["status"] == ("incomplete" if fault == "incomplete" else "failed")
    assert "check_not_passed" in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize(
    "material",
    [
        "src/paper_radar/reading/numbers.py",
        "src/paper_radar/reading/validation.py",
        "src/paper_radar/reading/result.py",
        "tests/read_recovery_worker.py",
        "tests/test_screening_architecture.py",
        "tests/fixtures/a9_coverage.json",
        "docs/contracts/read-validation.md",
        "scripts/a9_acceptance.py",
    ],
)
def test_actual_rule_support_and_coverage_bytes_are_fixed(
    tmp_path: Path, material: str
) -> None:
    from tests.a2_full_support import repository_copy

    root = repository_copy(tmp_path / "repo")
    inputs = same_a9_run(tmp_path, root=root)
    target = root / material
    target.write_bytes(target.read_bytes() + b"\n")
    path, result = conclude(tmp_path, inputs, root=root)
    assert result["status"] == "failed"
    assert {"scope_drift", "identity_changed"} <= {
        reason["code"] for reason in result["reasons"]
    }
    assert "PRIVATE" not in path.read_text()


@pytest.mark.parametrize(
    "target",
    [
        "evidence",
        "a1",
        "full",
        "a3",
        "baseline",
        "scope_a1",
        "scope_stage",
        "a3_parent",
    ],
)
def test_boolean_impostors_are_rejected_even_after_rebinding(
    tmp_path: Path, a9_inputs: Inputs, target: str
) -> None:
    inputs = a9_inputs
    if target == "baseline":
        code = inputs[-1].code.copy()
        code["dirty"] = int(bool(code["dirty"]))  # type: ignore[typeddict-item]
        inputs = (*inputs[:-1], replace(inputs[-1], code=code))
    elif target in {"evidence", "scope_a1", "scope_stage"}:
        raw = json.loads(inputs[0].read_bytes())
        if target == "evidence":
            raw["code"]["dirty"] = int(raw["code"]["dirty"])
        else:
            raw["scope"][
                "full_a1_verified" if target == "scope_a1" else "stage_a_verified"
            ] = 0
        inputs[0].write_text(json.dumps(raw))
    else:
        value = inputs[{"a1": 2, "full": 4, "a3": 6, "a3_parent": 6}[target]]
        assert isinstance(value, dict)
        if target == "a3_parent":
            value["parent_issue"] = True
        else:
            value["code"]["dirty"] = int(value["code"]["dirty"])
    rebind(inputs)
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert (
        "binding_mismatch"
        if target.startswith("scope_") or target == "a3_parent"
        else "identity_changed"
    ) in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize(
    "domain", ["evidence_rules", "numeric_rules", "snapshot", "backup"]
)
@pytest.mark.parametrize("version", [True, 2, 1.0])
def test_real_production_rule_versions_cannot_drift_or_disguise_types(
    tmp_path: Path,
    a9_inputs: Inputs,
    monkeypatch: pytest.MonkeyPatch,
    domain: str,
    version: object,
) -> None:
    from paper_radar import reading
    from paper_radar.backup import manifest
    from paper_radar.config import compile as compiling

    module, attribute = {
        "evidence_rules": (reading, "EVIDENCE_RULE_VERSION"),
        "numeric_rules": (reading, "NUMERIC_RULE_VERSION"),
        "snapshot": (compiling, "FORMAT_VERSION"),
        "backup": (manifest, "BACKUP_FORMAT_VERSION"),
    }[domain]
    monkeypatch.setattr(module, attribute, version)
    _, result = conclude(tmp_path, a9_inputs)
    assert result["status"] == "failed"
    assert "read_format_drift" in {reason["code"] for reason in result["reasons"]}


def test_interruption_is_incomplete_and_publication_never_overwrites(
    tmp_path: Path, a9_inputs: Inputs
) -> None:
    path, result = conclude(tmp_path, a9_inputs, interrupted=True)
    assert result["status"] == "incomplete"
    assert result["a9_verified"] is False
    assert "run_incomplete" in {reason["code"] for reason in result["reasons"]}
    old = path.read_bytes()
    with pytest.raises(FileExistsError) as conflict:
        conclude(tmp_path, a9_inputs)
    assert conflict.value.errno == errno.EEXIST
    assert Path(conflict.value.filename2) == path
    assert path.read_bytes() == old


@pytest.mark.parametrize("target", ["receipt", "predecessor"])
def test_bound_files_are_rechecked_before_publication(
    tmp_path: Path, a9_inputs: Inputs, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    selected = (
        a9_inputs[0].with_suffix(".pytest.json")
        if target == "receipt"
        else a9_inputs[5]
    )
    original = Path.read_bytes
    reads = 0

    def replace_after_read(path: Path) -> bytes:
        nonlocal reads
        raw = original(path)
        if path == selected:
            reads += 1
            if reads == 2:
                path.write_bytes(b'{"PRIVATE_REPLACEMENT":true}')
        return raw

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    path, result = conclude(tmp_path, a9_inputs)
    assert result["status"] == "failed"
    assert "binding_mismatch" in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE_REPLACEMENT" not in path.read_text()


def test_unregistered_real_migration_is_rejected(
    tmp_path: Path, a9_inputs: Inputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from paper_radar.storage import database

    migrations = tmp_path / "migrations"
    shutil.copytree(Path(database.__file__).parent / "migrations", migrations)
    (migrations / "versions/unregistered.py").write_text(
        "revision='unregistered'\ndown_revision='feed06_language_provenance'\n"
        "def upgrade():pass\ndef downgrade():pass\n"
    )
    monkeypatch.setattr(database, "_MIGRATIONS", migrations)
    _, result = conclude(tmp_path, a9_inputs)
    assert result["migration_revision"] == "unregistered"
    assert result["status"] == "failed"
    assert "migration_unavailable" in {reason["code"] for reason in result["reasons"]}


def test_missing_actual_dependency_is_not_configuration_success(
    tmp_path: Path, a9_inputs: Inputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    original = importlib.metadata.version

    def missing(name: str) -> str:
        if name == "pydantic":
            raise importlib.metadata.PackageNotFoundError
        return original(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    _, result = conclude(tmp_path, a9_inputs)
    assert result["status"] == "failed"
    assert "dependency_unavailable" in {reason["code"] for reason in result["reasons"]}


def test_caught_interrupt_is_published_as_incomplete(
    tmp_path: Path, a9_inputs: Inputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    def interrupt(name: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(importlib.metadata, "version", interrupt)
    _, result = conclude(tmp_path, a9_inputs)
    assert result["status"] == "incomplete"
    assert result["a9_verified"] is False
    assert "run_incomplete" in {reason["code"] for reason in result["reasons"]}
