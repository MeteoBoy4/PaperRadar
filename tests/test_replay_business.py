"""B-E16 独立 D1:完整合成 CLI→备份→恢复→实际 OS 冷回放,非现场证明。"""

import json
import sqlite3
from pathlib import Path

import pytest

from tests.experiment_read_support import read_fixture
from tests.exposure_support import backup, payload
from tests.replay_support import cli, replay_args
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report


def test_full_business_replay_keeps_evidence_report_members_exposure_and_every_table(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="degrade")
    read = fixture.read()
    assert read.exit_code == 0, read.output
    analysis = json.loads(read.stdout)["task"]["analysis_id"]
    root = fixture.layout.extraction.root
    receipts = []
    for options in ((), ("--analysis-id", analysis)):
        result = report(
            root.root,
            "render",
            "--date",
            "2026-11-14",
            "--timezone",
            "Asia/Shanghai",
            "--snapshot",
            fixture.snapshot,
            *options,
        )
        assert result.exit_code == 0, result.output
        receipts.append(json.loads(result.stdout))
    exposure_receipt, _, exposure_bytes = payload(root)
    original_reports = {
        r["relative_path"]: (root.views / r["relative_path"]).read_bytes()
        for r in receipts
    }
    assert all(b"PRIVATE_READ_CONCLUSION" in raw for raw in original_reports.values())
    original_log = (root.root / "logs/runtime.jsonl").read_bytes()
    assert backup(root, tmp_path / "backups").exit_code == 0
    (batch,) = (tmp_path / "backups").iterdir()
    (root.root / "restore").mkdir()
    restored = root.root / "restore/session"
    restored_result = cli(
        "restore", "verify", str(batch), "--target", str(restored), "--replay-container"
    )
    assert restored_result.returncode == 0, (
        restored_result.stdout + restored_result.stderr
    )
    database = restored / "contents/database.sqlite3"
    before = database.read_bytes()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        tables_before = tuple(connection.iterdump())
    prepared = fixture.layout.extraction.prepared
    prepared.materials.mkdir(parents=True, exist_ok=True)
    (prepared.materials / "synthetic.txt").write_text("PRIVATE_MATERIAL")
    originals = (
        root.database,
        root.data_root,
        root.config,
        prepared.materials,
        prepared.install,
        fixture.layout.extraction.models,
    )
    first = cli(*replay_args(restored, originals))
    assert first.returncode == 0, first.stdout + first.stderr
    summary = json.loads(first.stdout)
    assert (
        summary["reports"] == 2
        and summary["analyses"] == 1
        and summary["exposures"] == 1
    )
    assert summary["evidence_slices"] >= 1
    assert summary["originals_denied"] == 6 and summary["descendant"] == "verified"
    for receipt in receipts:
        assert (
            restored / "views" / receipt["relative_path"]
        ).read_bytes() == original_reports[receipt["relative_path"]]
    assert (
        restored / "views" / exposure_receipt["relative_path"]
    ).read_bytes() == exposure_bytes
    # 原配置与所有模型/安装材料消失后仍只用持久成员,不补原件。
    for path in (
        root.config,
        prepared.materials,
        prepared.install,
        fixture.layout.extraction.models,
    ):
        path.rename(path.with_name(path.name + "-unavailable"))
    # 删除源 blob,恢复仍不得回读或补原件。
    next(path for path in root.data_root.rglob("*") if path.is_file()).unlink()
    moved = restored.with_name("moved-session")
    restored.rename(moved)
    second = cli(*replay_args(moved, originals))
    assert second.returncode == 0, second.stdout + second.stderr
    assert json.loads(second.stdout)["missing_originals"] == 4
    assert (moved / "contents/database.sqlite3").read_bytes() == before
    with sqlite3.connect(
        f"file:{moved / 'contents/database.sqlite3'}?mode=ro", uri=True
    ) as connection:
        assert tuple(connection.iterdump()) == tables_before
    assert (root.root / "logs/runtime.jsonl").read_bytes() == original_log
    assert not list(moved.rglob("*wal")) and not list(moved.rglob("*shm"))
    assert not (moved / "logs").exists() and not (moved / "views/logs").exists()
    from paper_radar.storage.artifacts import ArtifactStore

    store = ArtifactStore(moved / "contents/database.sqlite3", moved / "contents")
    extraction = next(
        record for record in store.list_artifacts() if record.kind == "extraction"
    )
    members = store.read_artifact(extraction.artifact_id)
    from hashlib import sha256

    digest = sha256(members["evidence_map"]).hexdigest()
    member = moved / "contents/blobs/sha256" / digest[:2] / digest
    member.chmod(0o600)
    member.write_bytes(members["evidence_map"] + b"PRIVATE_TAMPERED_EVIDENCE")
    member.chmod(0o400)
    tampered = cli(*replay_args(moved, originals))
    assert tampered.returncode == 2 and "file_corrupt" in tampered.stderr
    member.unlink()
    missing = cli(*replay_args(moved, originals))
    assert missing.returncode == 2 and "file_missing" in missing.stderr
    assert "PRIVATE_TAMPERED_EVIDENCE" not in tampered.stdout + tampered.stderr
    for private in (
        "PRIVATE_READ_CONCLUSION",
        "PRIVATE_READ_PROMPT",
        "PRIVATE_DISCARDED",
        str(root.root),
    ):
        assert (
            private not in first.stdout + first.stderr + second.stdout + second.stderr
        )
