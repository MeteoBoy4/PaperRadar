"""持久 pi_rpc 来源的恢复闭包与损坏拒绝。"""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import BackupError, create_backup, verify_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from tests.a7_value_support import value_payload
from tests.a8_call_support import request_for
from tests.pi_rpc_source_support import NOW, RAW, candidate, source_archive
from tests.test_a7_attempt_backup import rehash_database


def test_mixed_sources_restore_without_original_root_or_install_access(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    data, supplied = source_archive(root)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    boundary = tasks.register(request_for(data))
    value = tasks.register(request_for(data, stage="value", original_title_is_zh=False))
    boundary_success = tasks.run_once(
        boundary.receipt_id, lambda *_: candidate(data, supplied)
    )
    value_success = tasks.run_once(
        value.receipt_id,
        lambda *_: candidate(
            data, supplied, value_payload(display_title_zh="大气过程")
        ),
    )
    assert isinstance(boundary_success, SuccessReceipt)
    assert isinstance(value_success, SuccessReceipt)
    from paper_radar.papers import PaperFacts
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/legacy-test", fields=screening_fields())
    )
    legacy = tasks.register(request_for(data, paper_id=other.paper_id))
    legacy_success = tasks.run_once(legacy.receipt_id, lambda *_: SuccessCandidate(RAW))
    assert isinstance(legacy_success, SuccessReceipt)
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    code = r"""
import json, sys
from pathlib import Path
from paper_radar.screening_tasks import ScreeningTasks
blocked = [Path(value).resolve() for value in sys.argv[5:]]
def audit(event, args):
    if event in {"open", "sqlite3.connect"} and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if any(path == item or item in path.parents for item in blocked):
            raise RuntimeError("original_root_forbidden")
sys.addaudithook(audit)
root = Path(sys.argv[1])
tasks = ScreeningTasks(root / "database.sqlite3", root)
tasks.validate_all()
contents = [tasks.load_success(value) for value in sys.argv[2:5]]
assert [content.receipt.executor_kind for content in contents] == [
    "pi_rpc", "pi_rpc", "test"]
assert contents[0].audit["provider_request_id"] is None
assert contents[1].output.research_value == 4
assert contents[2].audit == {"executor_kind":"test", "reported_provider":None,
    "reported_model":None, "provider_request_id":None,
    "input_tokens":None, "output_tokens":None}
print(json.dumps({"restored": True}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(restored.target_dir),
            boundary_success.success_id,
            value_success.success_id,
            legacy_success.success_id,
            str(root),
            str(tmp_path / "unavailable"),
            str(batch.batch_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
        },
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"restored": True}


@pytest.mark.parametrize(
    "field,value",
    [
        ("supply_id", "0" * 64),
        ("install_id", "0" * 32),
        ("pi_version", "1.3.0"),
        ("node_version", "22.20.0"),
        ("adapter_version", "transport-v2"),
        ("format_version", 3),
        ("format_version", 2.0),
        ("proxy_used", 1),
        ("proxy_port", 8080),
        ("credential_source", "personal_home"),
        ("auth_mode", "api_key"),
        ("credential_provider", "other"),
        ("protocol", "json_schema"),
        ("protocol_profile", "unknown"),
        ("reported_model", None),
        ("input_tokens", True),
        ("provider_request_id", "rpc-id"),
        ("unexpected", "PRIVATE_AUDIT_SENTINEL"),
        ("input_tokens", "missing"),
        ("launch_policy_version", "/home/PRIVATE_AUDIT_SENTINEL"),
    ],
)
def test_persisted_audit_corruption_rejected_by_load_validate_and_backup(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    success = tasks.run_once(receipt.receipt_id, lambda *_: candidate(data, supplied))
    assert isinstance(success, SuccessReceipt)
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    for database in (data.database, batch.batch_dir / "database.sqlite3"):
        with closing(sqlite3.connect(database)) as connection:
            audit = json.loads(
                connection.execute(
                    "SELECT audit_json FROM screening_successes"
                ).fetchone()[0]
            )
            if value == "missing":
                del audit[field]
            else:
                audit[field] = value
            connection.execute(
                "UPDATE screening_successes SET audit_json=?",
                (
                    json.dumps(
                        audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ),
                ),
            )
            connection.commit()
    restarted = ScreeningTasks(data.database, data.data_root)
    for operation in (
        lambda: restarted.load_success(success.success_id),
        restarted.validate_all,
    ):
        with pytest.raises(TaskError) as error:
            operation()
        assert error.value.reason == TaskReason.CORRUPT_REFERENCE
        assert "PRIVATE_AUDIT_SENTINEL" not in str(error.value)
    rehash_database(batch.batch_dir)
    with pytest.raises(BackupError) as rejected:
        verify_backup(batch.batch_dir)
    assert rejected.value.reason == "registration_invalid"
    assert "PRIVATE_AUDIT_SENTINEL" not in str(rejected.value)
