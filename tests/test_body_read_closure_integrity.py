"""D1 跨实际消费者的损坏闭包与历史策略拒绝/保留。"""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from paper_radar.backup import (
    BackupError,
    RestoreError,
    create_backup,
    restore_backup,
    verify_backup,
)
from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadAnalysis
from tests.body_read_closure_support import closure


def rewrite_database(batch: Path, sql: str) -> None:
    """损坏注入后重算容器摘要,使验证必须到达业务语义层。"""
    database = batch / "database.sqlite3"
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.execute(sql)
    raw = database.read_bytes()
    database.chmod(0o400)
    manifest = batch / "manifest.json"
    record = json.loads(manifest.read_bytes())
    record["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest.chmod(0o600)
    manifest.write_bytes(
        json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        + b"\n"
    )
    manifest.chmod(0o400)


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("policy", "registration_invalid"),
        ("ordinal", "registration_invalid"),
        ("discards", "registration_invalid"),
        ("cross_body", "registration_invalid"),
        ("decision", "registration_invalid"),
        ("metadata", "registration_invalid"),
        ("rule", "unsupported_rule_version"),
        ("missing_member", "file_missing"),
        ("tampered_member", "file_corrupt"),
    ],
)
def test_complete_pi_backup_refuses_specific_integrity_damage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str, reason: str
) -> None:
    service, task, _ = closure(tmp_path / "source", monkeypatch, mode="degrade")
    service.run_attempt(task.task_id)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis) and result.discards
    other_artifact = ""
    if damage == "cross_body":
        from paper_radar.fulltext.artifacts import FulltextArtifacts
        from tests.test_fulltext_artifacts import document

        doc = document()
        source = doc.blocks[1].model_copy(
            update={"orig": "Other source α = 2.", "text": "Other source α = 2."}
        )
        other = FulltextArtifacts(service.tasks.artifacts.store).publish(
            doc.model_copy(update={"blocks": (doc.blocks[0], source)}),
            extraction_fingerprint=task.identity.extraction_fingerprint,
            backend_config_hash="b" * 64,
            model_artifacts_hash="c" * 64,
            elapsed_seconds=1.0,
            peak_memory_bytes=4096,
        )
        assert other.identity != task.identity
        other_artifact = other.artifact_id
    backup = create_backup(service.database, service.data_root, tmp_path / "backups")
    if damage in {"missing_member", "tampered_member"}:
        artifact = next(a for a in backup.manifest.artifacts if a.kind == "extraction")
        member = next(m for m in artifact.members if m.role == "evidence_map")
        blob = next(b for b in backup.manifest.blobs if b.sha256 == member.sha256)
        path = backup.batch_dir / blob.path
        if damage == "missing_member":
            path.unlink()
        else:
            path.chmod(0o600)
            path.write_bytes(
                path.read_bytes().replace(b"Exact source", b"Wrong source")
            )
            path.chmod(0o400)
    else:
        sql = {
            "policy": "UPDATE read_analyses SET degrade_policy='none'",
            "ordinal": "UPDATE read_analyses SET attempt_ordinal=1",
            "discards": "UPDATE read_analyses SET discards_json='[]'",
            "cross_body": f"UPDATE read_evidence SET artifact_id='{other_artifact}'",
            "decision": "DELETE FROM body_decision_screenings",
            "metadata": "DELETE FROM feed_metadata_routes",
            "rule": "UPDATE read_analyses SET evidence_rule_version='future-evidence'",
        }[damage]
        rewrite_database(backup.batch_dir, sql)
    with pytest.raises(BackupError) as verify:
        verify_backup(backup.batch_dir)
    assert verify.value.reason == reason
    target = tmp_path / "restore"
    with pytest.raises(RestoreError) as restore:
        restore_backup(backup.batch_dir, target)
    assert restore.value.reason == reason
    assert not target.exists()


@pytest.mark.parametrize("policy", ["numeric_rule_version", "limitation_rule_version"])
def test_unknown_warning_policy_restores_saved_analysis_without_rule_equivalence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy: str
) -> None:
    service, task, _ = closure(tmp_path / "source", monkeypatch, mode="degrade")
    service.run_attempt(task.task_id)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis) and result.warnings and result.discards
    backup = create_backup(service.database, service.data_root, tmp_path / "backups")
    rewrite_database(
        backup.batch_dir, f"UPDATE read_analyses SET {policy}='historical-unsupported'"
    )
    restored = restore_backup(backup.batch_dir, tmp_path / "restore")
    from paper_radar.read_tasks import ReadTasks

    saved = ReadTasks(
        restored.target_dir / "database.sqlite3", restored.target_dir
    ).analysis(result.analysis_id)
    assert saved.warnings == result.warnings and saved.discards == result.discards
    assert getattr(saved, policy) == "historical-unsupported"
    assert (
        ReadQueries(restored.target_dir / "database.sqlite3", restored.target_dir)
        .analysis(saved.analysis_id)
        .has_discards
    )


def test_synthetic_v1_analysis_remains_v1_after_complete_pi_backup_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.read_tasks import ReadTasks
    from paper_radar.read_tasks.repository import records
    from paper_radar.reading import validate_read_output

    service, task, _ = closure(tmp_path / "source", monkeypatch)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis)
    v1 = validate_read_output(
        result.raw_candidate, service.tasks.prepare(task.task_id).context
    )
    # 只构造历史fixture,没有产品导入API或v1接收开关。
    with sqlite3.connect(service.database) as connection:
        connection.execute(
            "UPDATE read_analyses SET evidence_rule_version='read-evidence-v1',"
            "numeric_rule_version='read-numeric-v1',limitation_rule_version='none',"
            "degrade_policy='none',output_json=?,diagnostics_json=?,warnings_json=?",
            (
                v1.analysis.model_dump_json(),
                records(v1.diagnostics),
                records(v1.warnings),
            ),
        )
    backup = create_backup(service.database, service.data_root, tmp_path / "backups")
    restored = restore_backup(backup.batch_dir, tmp_path / "restore")
    saved = ReadTasks(
        restored.target_dir / "database.sqlite3", restored.target_dir
    ).analysis(result.analysis_id)
    assert saved.evidence_rule_version == "read-evidence-v1"
    assert saved.numeric_rule_version == "read-numeric-v1"
    assert saved.raw_candidate == result.raw_candidate
