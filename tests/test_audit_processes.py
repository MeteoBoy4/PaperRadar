"""两类真实进程验收：同计划互斥，以及 started 后 kill 再继续。"""

import json
from pathlib import Path

import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.fixture_audit import FixtureAudit, FixtureError
from tests.audit_matrix_support import MatrixSources
from tests.audit_process_support import finish, handshake, spawn
from tests.audit_sampling_support import CODE, sampling_service


def test_real_process_flock_excludes_second_writer_but_allows_show_and_replay(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    service = sampling_service(source, MatrixSources())
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert service.data_root
    process = spawn(
        tmp_path / "child.py",
        "lock",
        service.database,
        service.data_root,
        original.plan.plan_id,
    )
    try:
        assert handshake(process) == "locked"
        with pytest.raises(FixtureError) as busy:
            service.resume_audit(
                original.plan.plan_id,
                contact_email="second@example.org",
                code_identity=CODE,
            )
        assert busy.value.reason == "execution_busy"
        assert service.show_audit(original.plan.plan_id) == original
        assert service.replay_audit(original.plan.plan_id).view == original
        lock_files = list(tmp_path.rglob("*.lock"))
        assert len(lock_files) == 1
        identity = lock_files[0].stat().st_ino
        assert process.stdin
        process.stdin.write("release\n")
        process.stdin.flush()
        assert process.wait(timeout=10) == 0
        assert lock_files[0].stat().st_ino == identity
        assert (
            service.resume_audit(
                original.plan.plan_id,
                contact_email="third@example.org",
                code_identity=CODE,
            )
            == original
        )
    finally:
        finish(process)


def test_real_process_killed_after_started_resumes_then_replays_in_isolated_process(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    service = sampling_service(source, MatrixSources())
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    selected = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert service.data_root
    process = spawn(
        tmp_path / "child.py",
        "resume",
        service.database,
        service.data_root,
        plan.plan_id,
    )
    try:
        assert handshake(process) == "http-started"
        during = service.show_audit(plan.plan_id)
        started = next(value for value in during.executions if value.settlement is None)
        assert started.request.journal == "jgr" and started.physical_requests is None
        assert service.replay_audit(plan.plan_id).view == during
        process.kill()
        assert process.wait(timeout=10) != 0
    finally:
        finish(process)
    resumed = service.resume_audit(
        plan.plan_id, contact_email="resumed@example.org", code_identity=CODE
    )
    assert resumed.status == "complete"
    assert [value.members for value in resumed.sampling] == [
        value.members for value in selected.sampling
    ]
    old = next(
        value
        for value in resumed.executions
        if value.execution_id == started.execution_id
    )
    assert old.reason == "outcome_unknown" and old.physical_requests is None
    assert any(
        value.previous_execution_id == old.execution_id and value.reason == "acquired"
        for value in resumed.executions
    )
    expected = service.replay_audit(plan.plan_id)
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    source.rename(tmp_path / "original-unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.replay_audit(plan.plan_id) == expected
    replay = spawn(
        tmp_path / "child.py",
        "replay",
        recovered.database,
        restored.target_dir,
        plan.plan_id,
    )
    try:
        result = json.loads(handshake(replay))
        assert result == {
            "status": "verified",
            "semantic_sha256": expected.semantic_sha256,
        }
        assert replay.wait(timeout=10) == 0
    finally:
        finish(replay)
