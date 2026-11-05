"""Body D1:业务闭包备份、异地冷进程恢复、篡改和提交故障。"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.body import BodyError
from paper_radar.body.extraction import LOCK_FILENAME
from tests.artifact_support import fail_sql
from tests.body_recovery_worker import view
from tests.body_support import CHECKS, accepted, add_feed, prepared


def test_business_closure_restores_in_moved_cold_no_extra_process(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    saved, service, parser = prepared(source)
    feed = add_feed(saved)
    pdf = service.current_pdf(saved.paper_id)
    assert pdf
    service.freeze_sample(
        saved.paper_id,
        feed_id=feed,
        pdf_sha256=pdf.pdf_sha256,
        reason="selected",
        request_id="sample",
    )
    accepted(saved, service)
    extracted = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert extracted.identity
    service.review_layout(
        extracted.identity,
        passed=True,
        checks=CHECKS,
        note="checked",
        actor="human",
        request_id="review",
    )
    expected = {
        "paper": saved.paper_id,
        "fingerprint": extracted.fingerprint,
        "view": view(
            saved.database, saved.data_root, saved.paper_id, extracted.fingerprint
        ),
    }
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps(expected, ensure_ascii=False))
    backup = create_backup(saved.database, saved.data_root, tmp_path / "batches")
    assert not (backup.batch_dir / LOCK_FILENAME).exists()
    unavailable = tmp_path / "source-unavailable"
    source.rename(unavailable)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.body_recovery_worker",
            str(backup.batch_dir),
            str(tmp_path / "restored"),
            str(tmp_path / "moved"),
            str(expected_path),
            str(source),
            str(unavailable),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).parents[1])
            + os.pathsep
            + str(Path(__file__).parents[1] / "src"),
        },
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "body recovered without SDK or original roots"


def test_lock_in_backup_is_unexpected_entry(tmp_path: Path) -> None:
    saved, service, parser = prepared(tmp_path / "source")
    service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    backup = create_backup(saved.database, saved.data_root, tmp_path / "batches")
    backup.batch_dir.chmod(0o700)
    (backup.batch_dir / LOCK_FILENAME).write_bytes(b"")
    with pytest.raises(BackupError) as error:
        verify_backup(backup.batch_dir)
    assert error.value.reason == "unexpected_entry"


@pytest.mark.parametrize("damage", ["input", "pdf", "review"])
def test_backup_refuses_tampered_business_reference(
    tmp_path: Path, damage: str
) -> None:
    saved, service, parser = prepared(tmp_path / "source")
    extracted = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert extracted.identity
    service.review_layout(
        extracted.identity,
        passed=True,
        checks=CHECKS,
        note="checked",
        actor="human",
        request_id="review",
    )
    statements = {
        "input": "UPDATE body_extraction_inputs SET pdf_sha256='" + "f" * 64 + "'",
        "pdf": "UPDATE body_pdfs SET pdf_sha256='" + "f" * 64 + "'",
        "review": "UPDATE body_layout_reviews SET checks_json='{}'",
    }
    with sqlite3.connect(saved.database) as connection:
        connection.execute(statements[damage])
    with pytest.raises(BackupError) as error:
        create_backup(saved.database, saved.data_root, tmp_path / "batches")
    assert error.value.reason == "registration_invalid"


def test_failed_success_transaction_leaves_no_half_success_and_spends_budget(
    tmp_path: Path,
) -> None:
    saved, service, parser = prepared(tmp_path)
    with (
        fail_sql("INSERT INTO body_extraction_successes"),
        pytest.raises(BodyError) as error,
    ):
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert error.value.reason == "database_failed"
    recovered = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert recovered.artifact_id
    assert [a.failure for a in recovered.attempts] == ["outcome_unknown", None]
    assert recovered.remaining_attempts == 0
    assert parser.calls == 2
    service.validate_all()


@pytest.mark.parametrize("table", ["body_pdfs", "body_samples"])
def test_backup_refuses_gaps_in_append_only_selection_history(
    tmp_path: Path, table: str
) -> None:
    saved, service, _ = prepared(tmp_path / "source")
    pdf = service.current_pdf(saved.paper_id)
    assert pdf
    service.freeze_sample(
        saved.paper_id,
        feed_id=add_feed(saved),
        pdf_sha256=pdf.pdf_sha256,
        reason="selected",
        request_id="sample",
    )
    with sqlite3.connect(saved.database) as connection:
        connection.execute(f"UPDATE {table} SET sequence=2")
    with pytest.raises(BackupError) as error:
        create_backup(saved.database, saved.data_root, tmp_path / "batches")
    assert error.value.reason == "registration_invalid"
