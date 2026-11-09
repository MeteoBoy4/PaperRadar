"""Pi 实际本机合成启动的历史恢复、当前准入和供给引用组合。"""

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from paper_radar.backup import BackupError, create_backup, verify_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.pi_execution import ExecutionError
from paper_radar.pi_execution.admission import AdmissionEvidence
from paper_radar.pi_execution.service import PiExecution
from paper_radar.screening_tasks import SuccessReceipt, TaskError
from tests.pi_execution_service_support import allow_synthetic, service_inputs
from tests.test_a7_attempt_backup import rehash_database


def test_restored_real_peer_history_survives_missing_install_but_new_attempt_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tmp_path / "original"
    original.mkdir()
    service, receipt, credentials = service_inputs(original, monkeypatch)
    allow_synthetic(monkeypatch)
    success = service.run_attempt(receipt.receipt_id)
    assert isinstance(success, SuccessReceipt)
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    original.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    cwd = tmp_path / "new-cwd"
    cwd.mkdir()
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", cwd)
    credentials = tmp_path / "new-credentials"
    credentials.mkdir(mode=0o700)
    (credentials / "auth.json").write_text("not parsed")
    resumed = PiExecution(
        restored.target_dir / "database.sqlite3",
        restored.target_dir,
        roots=service.roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    )
    assert resumed.tasks.load_success(success.success_id).receipt == success
    resumed.tasks.validate_all()
    from paper_radar.papers import PaperFacts
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    paper = PaperFacts(resumed.database, restored.target_dir).submit(
        observation(doi="10.1234/restored-new-attempt", fields=screening_fields())
    )
    pending = resumed.tasks.register(
        dict(
            paper_id=paper.paper_id,
            snapshot_id=receipt.snapshot_id,
            stage="boundary",
            source="scheduled",
            scheduled_day="2026-01-02",
        )
    )
    with pytest.raises(ExecutionError, match="install_unavailable"):
        resumed.run_attempt(pending.receipt_id)
    assert resumed.tasks.status(pending.receipt_id).used_attempts == 0
    assert tuple(
        view.receipt
        for view in resumed.tasks.query_successes(
            paper_id=receipt.paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
        )
    ) == (success,)
    allow_synthetic(
        monkeypatch,
        lambda binding: AdmissionEvidence(
            replace(binding, isolation_policy_version="obsolete-policy"),
            True,
            True,
            True,
        ),
    )
    with pytest.raises(ExecutionError, match="evidence_mismatch"):
        resumed.run_attempt(pending.receipt_id)
    assert resumed.tasks.status(pending.receipt_id).used_attempts == 0
    assert resumed.tasks.status(pending.receipt_id).last_failure is None


@pytest.mark.parametrize(
    "field,value", [("install_id", "0" * 32), ("pi_version", "1.3.0")]
)
def test_real_peer_audit_corruption_is_rejected_by_query_and_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    service, receipt, _ = service_inputs(tmp_path, monkeypatch)
    allow_synthetic(monkeypatch)
    success = service.run_attempt(receipt.receipt_id)
    assert isinstance(success, SuccessReceipt)
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    for database in (service.database, batch.batch_dir / "database.sqlite3"):
        with sqlite3.connect(database) as connection:
            audit = json.loads(
                connection.execute(
                    "SELECT audit_json FROM screening_successes"
                ).fetchone()[0]
            )
            audit[field] = value
            connection.execute(
                "UPDATE screening_successes SET audit_json=?",
                (json.dumps(audit, sort_keys=True, separators=(",", ":")),),
            )
    with pytest.raises(TaskError, match="corrupt_reference"):
        service.tasks.load_success(success.success_id)
    with pytest.raises(TaskError, match="corrupt_reference"):
        service.tasks.validate_all()
    rehash_database(batch.batch_dir)
    with pytest.raises(BackupError) as error:
        verify_backup(batch.batch_dir)
    assert error.value.reason == "registration_invalid"
