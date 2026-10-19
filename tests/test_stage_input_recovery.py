"""从真实非空备份的历史配置与恢复成员重建阶段输入。"""

import json
import os
import subprocess
import sys
from pathlib import Path

from paper_radar.backup import create_backup, restore_backup
from paper_radar.config import compile_config
from paper_radar.storage.artifacts import ArtifactStore
from tests.backup_support import tree
from tests.config_projection_support import full_inputs, new_yaml_version
from tests.stage_input_recovery_support import synthetic_submission


def test_isolated_restore_rebuilds_all_stage_inputs_from_restored_members(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    settings, database = full_inputs(source)
    topics = settings.parent / "topics/topics-v1.yaml"
    topics.write_text(topics.read_text().replace("enabled: false", "enabled: true"))
    historical = compile_config(settings, database)
    new_yaml_version(settings, "profile", lambda c: c.update(background="Changed"))
    new_yaml_version(
        settings, "extraction", lambda c: c.update(pdf_backend="threaded_docling_parse")
    )
    newer = compile_config(settings, database)
    data_root = source / "data"
    store = ArtifactStore(database, data_root)
    artifact_ids = {
        "pdf": store.publish_single(
            "original_pdf", [b"Synthetic PDF bytes"]
        ).artifact_id,
        "structured": store.publish_single(
            "source_snapshot", [b"Synthetic source snapshot"]
        ).artifact_id,
        "body": store.publish_artifact(
            "extraction",
            {
                "reading": [b"Synthetic reading text"],
                "evidence_map": [b'{"blocks":["block-1","block-2"]}'],
                "document": [b'{"backend":"synthetic"}'],
                "manifest": [b'{"started_at":"historical"}'],
            },
        ).artifact_id,
    }
    batch = create_backup(database, data_root, tmp_path / "backups")
    assert len(batch.manifest.artifacts) == 3 and batch.manifest.blobs
    unavailable = source.rename(tmp_path / "original-unavailable")
    assert not settings.exists() and not database.exists() and not data_root.exists()
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    relocated = restored.target_dir.rename(tmp_path / "relocated")
    before = tree(relocated)
    request = tmp_path / "request.json"
    # 只传显式历史引用、合成事实与固定期望位置。原成员哈希与旧输入对象不跨进程。
    request.write_text(
        json.dumps(
            {
                "root": str(relocated),
                "snapshot_id": historical.snapshot_id,
                "other_snapshot_id": newer.snapshot_id,
                "artifact_ids": artifact_ids,
                "denied_roots": [str(source), str(unavailable)],
                **synthetic_submission(),
            }
        )
    )
    repo = Path(__file__).resolve().parents[1]
    reports = []
    for seed, reverse in (("17", False), ("89", True)):
        submission = json.loads(request.read_bytes())
        submission["reverse"] = reverse
        request.write_text(json.dumps(submission))
        cwd = tmp_path / f"process-{seed}"
        cwd.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.stage_input_process",
                str(request),
                str(repo / "tests/fixtures/stage_inputs/recovery-v1.json"),
            ],
            cwd=cwd,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    (str(repo), str(repo / "tests/deny_network"))
                ),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": seed,
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        report = json.loads(result.stdout)
        assert report["status"] == "passed"
        reports.append(report)
    assert reports[0]["topic_order"] != reports[1]["topic_order"]
    assert reports[0]["construction_order"] != reports[1]["construction_order"]
    assert tree(relocated) == before
    assert (relocated / "database.sqlite3").read_bytes()[18:20] == b"\x01\x01"
