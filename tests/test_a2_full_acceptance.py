"""#25 完整 A2 结论绑定本次运行。保留 A2-01 历史范围。"""

from __future__ import annotations

import importlib.metadata
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from scripts.a1_acceptance import capture_identity
from scripts.a2_full_acceptance import write_full_a2_conclusion
from scripts.offline_evidence import default_checks, file_sha256
from tests.a2_full_support import init_fixture_repository, passed_receipt

ROOT = Path(__file__).resolve().parents[1]


def same_run(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    identity = capture_identity(ROOT)
    run_id = "synthetic-full-a2"
    evidence = {
        "format_version": 1,
        "run_id": run_id,
        "scope": {
            "issue": 12,
            "claim": "implemented_offline_checks_only",
            "full_a1_verified": False,
            "stage_a_verified": False,
        },
        "completed": True,
        "overall": "passed",
        "code": identity.code,
        "lockfile_sha256": identity.lockfile_sha256,
        "checks": [
            {"id": check.id, "status": "passed", "reason": "none", "exit_code": 0}
            for check in default_checks()
        ],
    }
    evidence_path = tmp_path / f"{run_id}.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    a1: dict[str, Any] = {
        "format_version": 1,
        "scope": "a1_screening_authoritative_contracts",
        "run_id": run_id,
        "status": "passed",
        "a1_verified": True,
        "evidence_sha256": file_sha256(evidence_path),
        "code": identity.code,
        "worktree_sha256": identity.worktree_sha256,
        "lockfile_sha256": identity.lockfile_sha256,
    }
    a1_path = tmp_path / f"{run_id}.a1.json"
    a1_path.write_text(json.dumps(a1), encoding="utf-8")
    evidence_path.with_suffix(".pytest.json").write_text(
        json.dumps(passed_receipt(run_id)),
        encoding="utf-8",
    )
    return evidence_path, a1_path, a1


def test_full_a2_records_independent_scope_formats_fixtures_and_actual_migration(
    tmp_path: Path,
) -> None:
    evidence, a1_path, a1 = same_run(tmp_path)
    path, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert result["status"] == "passed", result["reasons"]
    assert path.name == "synthetic-full-a2.a2-full.json"
    assert json.loads(path.read_bytes()) == result
    assert result["scope"] == "a2_versioned_config_snapshots"
    assert result["issue"] == 25
    assert result["format_version"] == 2
    assert result["a2_verified"] is True
    assert result["stage_a_verified"] is result["live_verified"] is False
    assert result["migration_revision"] == "a601_paper_facts"
    assert result["format_versions"] == {
        "snapshot": 1,
        "stage_projections": {
            "boundary": 1,
            "value": 1,
            "reuse": 1,
            "extraction": 1,
            "read": 1,
            "suggestion": 1,
        },
        "calibration_baseline": 1,
        "adapter_semantics": 1,
    }
    assert set(result["environment"]["dependencies"]) == {
        "alembic",
        "SQLAlchemy",
        "PyYAML",
    }
    assert all(result["environment"]["dependencies"].values())
    assert result["evidence_sha256"] == file_sha256(evidence)
    assert result["a1_conclusion_sha256"] == file_sha256(a1_path)
    assert result["pytest_receipt_sha256"] == file_sha256(
        evidence.with_suffix(".pytest.json")
    )
    assert all(record["result"] == "passed" for record in result["test_execution"])
    assert result["fixture_files"]
    assert all(item["result"] == "passed" for item in result["fixture_files"])
    assert {
        "stage_input_fingerprints",
        "business_facts",
        "doctor",
        "tasks_and_shared_interfaces",
        "backup_and_recovery",
        "live_source_audit",
        "stage_b",
    } <= set(result["not_assessed"])


@pytest.mark.parametrize(
    "case",
    [
        "missing_check",
        "skipped",
        "failed",
        "bool_exit",
        "old_evidence",
        "old_a1",
        "wrong_scope",
        "changed_hash",
        "failed_a1",
        "incomplete",
        "wrong_run",
        "missing_evidence",
        "invalid_evidence",
        "nonobject_evidence",
    ],
)
def test_full_a2_never_reuses_success_for_invalid_or_incomplete_run(
    tmp_path: Path,
    case: str,
) -> None:
    evidence_path, a1_path, a1 = same_run(tmp_path)
    evidence = json.loads(evidence_path.read_bytes())
    if case == "missing_check":
        evidence["checks"].pop()
    elif case == "skipped":
        evidence["checks"][4].update(status="not_run", reason="skipped", exit_code=None)
    elif case == "failed":
        evidence["checks"][4].update(
            status="failed", reason="exit_nonzero", exit_code=1
        )
    elif case == "bool_exit":
        evidence["checks"][4]["exit_code"] = False
    elif case == "old_evidence":
        evidence["format_version"] = 0
    elif case == "old_a1":
        a1["format_version"] = 0
    elif case == "wrong_scope":
        evidence["scope"]["issue"] = 25
    elif case == "failed_a1":
        a1.update(status="failed", a1_verified=False)
    elif case == "incomplete":
        evidence.update(completed=False, overall="incomplete")
    elif case == "wrong_run":
        evidence["run_id"] = "historical-run"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    a1["evidence_sha256"] = file_sha256(evidence_path)
    if case == "changed_hash":
        a1["evidence_sha256"] = "0" * 64
    a1_path.write_text(json.dumps(a1), encoding="utf-8")
    if case == "missing_evidence":
        evidence_path.unlink()
    elif case == "invalid_evidence":
        evidence_path.write_text("{", encoding="utf-8")
    elif case == "nonobject_evidence":
        evidence_path.write_text("[]", encoding="utf-8")

    _, result = write_full_a2_conclusion(ROOT, evidence_path, a1_path, a1, tmp_path)
    assert result["status"] == ("incomplete" if case == "incomplete" else "failed")
    assert result["a2_verified"] is False
    assert result["reasons"]


@pytest.mark.parametrize(
    "component", ["snapshot", "boundary", "read", "baseline", "adapter"]
)
def test_each_format_identity_is_independently_gated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    component: str,
) -> None:
    from paper_radar.config import StageName, adapters, compile, projections

    evidence, a1_path, a1 = same_run(tmp_path)
    if component == "snapshot":
        monkeypatch.setattr(compile, "FORMAT_VERSION", 2)
    elif component == "baseline":
        monkeypatch.setattr(projections, "BASELINE_FORMAT_VERSION", 2)
    elif component == "adapter":
        monkeypatch.setattr(adapters, "ADAPTER_SEMANTICS_FORMAT_VERSION", 2)
    else:
        versions = dict(projections.PROJECTION_FORMAT_VERSIONS)
        versions[StageName(component)] = 2
        monkeypatch.setattr(projections, "PROJECTION_FORMAT_VERSIONS", versions)
    _, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert result["status"] == "failed"
    assert "config_format_drift" in {r["code"] for r in result["reasons"]}


@pytest.mark.parametrize("missing_version", ["absent", "empty"])
def test_dependency_missing_and_interruption_are_redacted_and_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_version: str,
) -> None:
    evidence, a1_path, a1 = same_run(tmp_path)
    original = importlib.metadata.version

    def missing(name: str) -> str:
        if name == "PyYAML":
            if missing_version == "empty":
                return ""
            raise importlib.metadata.PackageNotFoundError("PRIVATE_SECRET_MARKER")
        return original(name)

    with monkeypatch.context() as scoped:
        scoped.setattr(importlib.metadata, "version", missing)
        path, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert result["status"] == "failed"
    assert result["environment"]["dependencies"]["PyYAML"] is None
    assert "dependency_unavailable" in {r["code"] for r in result["reasons"]}
    assert "PRIVATE_SECRET_MARKER" not in path.read_text(encoding="utf-8")

    def interrupt(_name: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(importlib.metadata, "version", interrupt)
    _, result = write_full_a2_conclusion(
        ROOT, evidence, a1_path, a1, tmp_path / "interrupted"
    )
    assert result["status"] == "incomplete"
    assert not result["a2_verified"]


def test_migration_revision_comes_from_a_real_temporary_database_and_new_head_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.storage import database

    migrations = tmp_path / "migrations"
    shutil.copytree(ROOT / "src/paper_radar/storage/migrations", migrations)
    (migrations / "versions/new_head.py").write_text(
        'revision = "unregistered_head"\n'
        'down_revision = "a601_paper_facts"\n'
        "def upgrade():\n    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(database, "_MIGRATIONS", migrations)
    evidence, a1_path, a1 = same_run(tmp_path)
    _, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert result["migration_revision"] == "unregistered_head"
    assert result["status"] == "failed"
    assert "migration_unavailable" in {r["code"] for r in result["reasons"]}
    assert not list(tmp_path.glob("*.sqlite3"))


def test_failed_migration_does_not_reveal_original_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import Engine, event

    def fail_migration(*_args: Any) -> None:
        raise RuntimeError("PRIVATE_PROFILE_PROMPT_SECRET_MARKER")

    evidence, a1_path, a1 = same_run(tmp_path)
    event.listen(Engine, "before_cursor_execute", fail_migration)
    try:
        path, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    finally:
        event.remove(Engine, "before_cursor_execute", fail_migration)
    assert result["status"] == "failed"
    assert result["migration_revision"] is None
    assert "PRIVATE_PROFILE_PROMPT_SECRET_MARKER" not in path.read_text(
        encoding="utf-8"
    )


def test_fixed_files_cannot_disappear_or_drift_and_worktree_change_cannot_pass(
    tmp_path: Path,
) -> None:
    from scripts.a2_full_scope import (
        REQUIRED_FIXTURE_FILES,
        REQUIRED_SOURCE_MODULES,
        REQUIRED_TEST_MODULES,
    )

    root = tmp_path / "repo"
    root.mkdir()
    for relative in {
        p
        for p, _ in (
            *REQUIRED_TEST_MODULES,
            *REQUIRED_SOURCE_MODULES,
            *REQUIRED_FIXTURE_FILES,
        )
    } | {"uv.lock"}:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    init_fixture_repository(root)
    evidence, a1_path, a1 = same_run(tmp_path)
    identity = capture_identity(root)
    payload = json.loads(evidence.read_bytes())
    payload.update(code=identity.code, lockfile_sha256=identity.lockfile_sha256)
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    a1.update(
        code=identity.code,
        worktree_sha256=identity.worktree_sha256,
        lockfile_sha256=identity.lockfile_sha256,
        evidence_sha256=file_sha256(evidence),
    )
    a1_path.write_text(json.dumps(a1), encoding="utf-8")
    for index, relative in enumerate(
        (
            "tests/test_config_transactions.py",
            "src/paper_radar/config/projections.py",
            "examples/config/settings-pi.yaml",
            "uv.lock",
        )
    ):
        target = root / relative
        original = target.read_bytes()
        target.unlink()
        _, missing = write_full_a2_conclusion(
            root, evidence, a1_path, a1, tmp_path / f"missing-{index}"
        )
        assert missing["status"] == "failed"
        assert "identity_changed" in {r["code"] for r in missing["reasons"]}
        if relative != "uv.lock":
            assert any(r.get("item") == relative for r in missing["reasons"])
        target.write_bytes(original + b"\n")
        _, drifted = write_full_a2_conclusion(
            root, evidence, a1_path, a1, tmp_path / f"drift-{index}"
        )
        assert drifted["status"] == "failed"
        target.write_bytes(original)


def test_conclusion_does_not_overwrite_or_upgrade_existing_legacy_conclusion(
    tmp_path: Path,
) -> None:
    evidence, a1_path, a1 = same_run(tmp_path)
    legacy = tmp_path / "synthetic-full-a2.a2.json"
    legacy.write_bytes(b'{"status":"failed","a2_01_verified":false}\n')
    original = legacy.read_bytes()
    path, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert result["status"] == "passed", result["reasons"]
    assert legacy.read_bytes() == original
    with pytest.raises(FileExistsError):
        write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert json.loads(path.read_bytes()) == result


def test_evidence_replacement_during_validation_cannot_bind_an_unchecked_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence, a1_path, a1 = same_run(tmp_path)
    original_read = Path.read_bytes
    reads = 0

    def replace_after_read(path: Path) -> bytes:
        nonlocal reads
        raw = original_read(path)
        if path == evidence:
            reads += 1
            if reads == 2:
                replacement = json.loads(raw)
                replacement["checks"][4]["status"] = "failed"
                path.write_text(json.dumps(replacement), encoding="utf-8")
        return raw

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    _, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert result["status"] == "failed"
    assert "binding_mismatch" in {r["code"] for r in result["reasons"]}


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "skipped",
        "deselected",
        "partial",
        "old_format",
        "wrong_run",
        "incomplete",
    ],
)
def test_fixed_tests_must_have_same_run_execution_not_only_a_successful_exit(
    tmp_path: Path,
    case: str,
) -> None:
    evidence, a1_path, a1 = same_run(tmp_path)
    receipt_path = evidence.with_suffix(".pytest.json")
    receipt = json.loads(receipt_path.read_bytes())
    if case == "missing":
        receipt_path.unlink()
    else:
        record = receipt["modules"]["tests/test_config_service.py"]
        if case == "skipped":
            record.update(skipped=record["collected"], passed=0)
        elif case == "deselected":
            record.update(deselected=record["collected"], collected=0, passed=0)
        elif case == "partial":
            record["collected"] -= 1
            record["passed"] -= 1
        elif case == "old_format":
            receipt["format_version"] = 0
        elif case == "wrong_run":
            receipt["run_id"] = "historical-run"
        elif case == "incomplete":
            receipt["completed"] = False
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    _, result = write_full_a2_conclusion(ROOT, evidence, a1_path, a1, tmp_path)
    assert result["status"] == ("incomplete" if case == "incomplete" else "failed")
    assert not result["a2_verified"]
    assert "test_execution_not_passed" in {
        reason["code"] for reason in result["reasons"]
    }
