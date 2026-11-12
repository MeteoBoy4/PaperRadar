"""#177 所有者豁免的公开边界;不绑定历史验收分母。"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from paper_radar.config import upgrade_database


def command(database: Path, *options: str) -> Result:
    return CliRunner().invoke(
        app, ["live-evidence", "owner-waiver", "--database", str(database), *options]
    )


def test_owner_action_is_explicit_persistent_and_versioned(tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    initial = command(database)
    assert initial.exit_code == 0, initial.output
    assert "enabled=false version=0" in initial.output
    missing_reason = command(database, "--enable")
    assert missing_reason.exit_code == 2
    assert "owner_waiver_action_invalid" in missing_reason.output
    enabled = command(database, "--enable", "--reason", "所有者接受残余风险")
    assert enabled.exit_code == 0, enabled.output
    assert "enabled=true version=1" in enabled.output
    assert "owner_evidence_prerequisite_waived" in enabled.output
    assert "证据前提已由所有者豁免（ADR-0068）" in enabled.output
    assert "enabled=true version=1" in command(database).output
    disabled = command(database, "--disable", "--reason", "恢复严格路径")
    assert disabled.exit_code == 0, disabled.output
    assert "enabled=false version=2" in disabled.output
    assert "strict_since=" in disabled.output
    assert "enabled=false version=2" in command(database).output


def test_waiver_allows_screening_without_evidence_or_protected_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.screening_tasks import SuccessReceipt
    from tests.pi_execution_service_support import service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )
    enabled = command(service.database, "--enable", "--reason", "所有者明确豁免")
    assert enabled.exit_code == 0, enabled.output
    result = service.run_attempt(receipt.receipt_id)
    assert isinstance(result, SuccessReceipt)
    assert result.executor_kind == "pi_rpc"
    assert service.tasks.status(receipt.receipt_id).used_attempts == 1
    assert (credentials / "auth-observed.json").exists()
    assert "enabled=true version=1" in command(service.database).output


def test_disabling_waiver_rejects_preexisting_verified_and_activated_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import timedelta

    import pytest

    from paper_radar.config.owner_waiver import record_owner_waiver
    from paper_radar.pi_execution import ExecutionError
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    ledger, _, _ = protected_admission(tmp_path / "evidence", monkeypatch)
    service, receipt, credentials = product_inputs(tmp_path / "product", monkeypatch)
    record_owner_waiver(
        service.database, enabled=True, reason="显式豁免", actor="owner", now=NOW
    )
    record_owner_waiver(
        service.database, enabled=False, reason="重新采集", actor="owner", now=NOW
    )
    service._now = lambda: NOW + timedelta(seconds=1)
    before = ledger.audit()
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(receipt.receipt_id)
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()
    assert ledger.audit() == before


def test_doctor_discloses_waiver_without_fabricating_verified_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config.owner_waiver import record_owner_waiver
    from tests.live_evidence_ledger_support import NOW
    from tests.test_doctor_live_admission import diagnose, selected_site
    from tests.test_doctor_process import logical

    database, snapshot, credentials, ledger, _ = selected_site(
        tmp_path, monkeypatch, capabilities=("file_isolation",), activate=False
    )
    record_owner_waiver(
        database, enabled=True, reason="豁免证据前提", actor="owner", now=NOW
    )
    before = logical(database)
    evidence_before = ledger.audit()
    result = diagnose(database, snapshot, credentials)
    assert result.exit_code == 0, result.output
    assert "证据前提已由所有者豁免（ADR-0068）" in result.output
    assert "reason=owner_evidence_prerequisite_waived" in result.output
    assert "check=admission_evidence result=not_assessed" in result.output
    assert "evidence=verified" not in result.output
    assert logical(database) == before
    assert ledger.audit() == evidence_before


def test_waiver_allows_read_without_evidence_and_keeps_pi_rpc_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.read_tasks import ReadAnalysis
    from tests.read_execution_support import setup

    service, task, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )
    enabled = command(service.database, "--enable", "--reason", "所有者接受风险")
    assert enabled.exit_code == 0, enabled.output
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis)
    assert result.executor_kind == "pi_rpc"
    assert service.tasks.task(task.task_id).remaining_attempts == 1


def test_waiver_keeps_test_analysis_ineligible_for_ordinary_consumers(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.read_tasks import ReadAnalysis, ReadTaskError, ReadTasks
    from tests.read_tasks_support import ready, valid_candidate

    data, _, extraction = ready(tmp_path)
    assert command(data.database, "--enable", "--reason", "所有者豁免").exit_code == 0
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="test-source",
    )
    analysis = tasks.run_once(task.task_id, lambda _: valid_candidate())
    assert isinstance(analysis, ReadAnalysis) and analysis.executor_kind == "test"
    with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
        tasks.analysis(analysis.analysis_id, ordinary=True)


def test_owner_policy_change_during_preparation_refuses_before_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    import pytest

    from paper_radar.pi_execution import ExecutionError
    from paper_radar.pi_execution import service as execution
    from tests.pi_execution_service_support import service_inputs

    service, receipt, _ = service_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )
    assert command(service.database, "--enable", "--reason", "显式开启").exit_code == 0
    from paper_radar.pi_execution.launcher import PreparedLaunch, prepare_launch

    original = prepare_launch

    @contextmanager
    def changed(*args: Any, **kwargs: Any) -> Iterator[PreparedLaunch]:
        with original(*args, **kwargs) as prepared:
            assert (
                command(service.database, "--disable", "--reason", "撤回豁免").exit_code
                == 0
            )
            yield prepared

    monkeypatch.setattr(execution, "prepare_launch", changed)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(receipt.receipt_id)
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert "enabled=false version=2" in command(service.database).output


@pytest.mark.parametrize(
    "corruption",
    [
        "true_format",
        "float_format",
        "missing_format",
        "unknown_field",
        "kind",
        "name",
        "hash",
        "version",
    ],
)
def test_invalid_owner_history_fails_closed(tmp_path: Path, corruption: str) -> None:
    import hashlib
    import json
    import sqlite3
    from contextlib import closing

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    assert command(database, "--enable", "--reason", "显式动作").exit_code == 0
    with closing(sqlite3.connect(database)) as connection:
        raw = connection.execute("SELECT raw_content FROM config_versions").fetchone()[
            0
        ]
        payload = json.loads(raw)
        if corruption == "true_format":
            payload["format_version"] = True
        elif corruption == "float_format":
            payload["format_version"] = 1.0
        elif corruption == "missing_format":
            del payload["format_version"]
        elif corruption == "unknown_field":
            payload["automatic_enable"] = True
        raw = json.dumps(payload).encode()
        connection.execute(
            "UPDATE config_versions SET raw_content=?,raw_sha256=?",
            (
                raw,
                "f" * 64 if corruption == "hash" else hashlib.sha256(raw).hexdigest(),
            ),
        )
        if corruption == "kind":
            connection.execute("UPDATE config_versions SET kind='owner_waiver_v999'")
        elif corruption == "name":
            connection.execute("UPDATE config_versions SET name='unknown'")
        elif corruption == "version":
            connection.execute("UPDATE config_versions SET declared_version='999'")
        connection.commit()
    result = command(database)
    assert result.exit_code == 2, result.output
    assert "owner_waiver_history_invalid" in result.output


def test_backup_restore_retains_owner_versions_and_revalidation_barrier(
    tmp_path: Path,
) -> None:
    from datetime import timedelta

    from paper_radar.backup import create_backup, restore_backup, verify_backup
    from paper_radar.config import load_config_snapshot
    from paper_radar.config.owner_waiver import owner_waiver, record_owner_waiver
    from tests.backup_support import populated
    from tests.live_evidence_ledger_support import NOW

    database, data_root, snapshot_id = populated(tmp_path / "source")
    before = load_config_snapshot(database, snapshot_id)
    record_owner_waiver(
        database, enabled=True, reason="明确豁免", actor="owner", now=NOW
    )
    record_owner_waiver(
        database,
        enabled=False,
        reason="恢复严格",
        actor="owner",
        now=NOW + timedelta(seconds=1),
    )
    expected = owner_waiver(database)
    batch = create_backup(database, data_root, tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    restored_database = restored.target_dir / "database.sqlite3"
    actual = owner_waiver(restored_database)
    assert actual == expected
    assert actual.version == 2 and not actual.enabled
    assert actual.strict_since == NOW + timedelta(seconds=1)
    assert (
        load_config_snapshot(restored_database, snapshot_id).snapshot_id
        == before.snapshot_id
    )


@pytest.mark.parametrize("activate", [False, True])
def test_strict_path_requires_new_collection_claims_receipt_and_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, activate: bool
) -> None:
    from datetime import timedelta

    from paper_radar.config.owner_waiver import record_owner_waiver
    from paper_radar.pi_execution import ExecutionError
    from paper_radar.screening_tasks import SuccessReceipt
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    cutoff = NOW - timedelta(seconds=1)
    protected_admission(tmp_path / "evidence", monkeypatch, activate=activate)
    service, receipt, _ = product_inputs(tmp_path / "product", monkeypatch)
    record_owner_waiver(
        service.database, enabled=True, reason="先豁免", actor="owner", now=cutoff
    )
    record_owner_waiver(
        service.database, enabled=False, reason="恢复严格", actor="owner", now=cutoff
    )
    service._now = lambda: NOW
    if not activate:
        with pytest.raises(ExecutionError, match="evidence_missing"):
            service.run_attempt(receipt.receipt_id)
        assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    else:
        assert isinstance(service.run_attempt(receipt.receipt_id), SuccessReceipt)


@pytest.mark.parametrize("consumer", ["screening", "read"])
def test_corrupt_waiver_refuses_without_protected_writes_or_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    import sqlite3
    from contextlib import closing

    from paper_radar.live_evidence import service as evidence_service
    from paper_radar.pi_execution import ExecutionError
    from tests.pi_execution_service_support import service_inputs
    from tests.read_execution_support import setup

    calls: list[object] = []
    if consumer == "screening":
        screening, receipt, credentials = service_inputs(tmp_path, monkeypatch)
        database, task_id = screening.database, receipt.receipt_id
        run: Callable[[str], object] = screening.run_attempt
    else:
        reading, task, credentials = setup(tmp_path, monkeypatch)
        database, task_id = reading.database, task.task_id
        run = reading.run_attempt
    assert command(database, "--enable", "--reason", "所有者动作").exit_code == 0
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE config_versions SET raw_sha256='invalid' WHERE kind='owner_waiver'"
        )
        connection.commit()

    def helper(arguments: tuple[str, ...]) -> bool:
        calls.append(arguments)
        return False

    monkeypatch.setattr(evidence_service, "_run_helper", helper)
    monkeypatch.setattr(
        evidence_service, "_append_pending", lambda record: calls.append(record)
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        run(task_id)
    assert not calls
    assert not (credentials / "auth-observed.json").exists()
    if consumer == "screening":
        assert screening.tasks.status(task_id).used_attempts == 0
    else:
        assert reading.tasks.task(task_id).remaining_attempts == 2


@pytest.mark.parametrize("consumer", ["screening", "read"])
def test_pipeline_cannot_enable_waiver_without_owner_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    from paper_radar.pi_execution import ExecutionError
    from tests.pi_execution_service_support import service_inputs
    from tests.read_execution_support import setup

    if consumer == "screening":
        screening, receipt, _ = service_inputs(tmp_path, monkeypatch)
        database, task_id = screening.database, receipt.receipt_id
        run: Callable[[str], object] = screening.run_attempt
    else:
        reading, task, _ = setup(tmp_path, monkeypatch)
        database, task_id = reading.database, task.task_id
        run = reading.run_attempt
    with pytest.raises(ExecutionError, match="evidence_missing"):
        run(task_id)
    assert "enabled=false version=0" in command(database).output
