"""B-E14 独立 D1:事务、文件系统、并发及损坏拒绝的故障接缝。"""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.experiment.reports import Reports
from paper_radar.experiment.root import ExperimentRoot
from tests.artifact_support import fail_sql
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report


@pytest.mark.parametrize("stop", ["INSERT INTO report_runs", "UPDATE report_runs"])
def test_database_boundary_failure_reuses_frozen_run_and_never_leaks(
    tmp_path: Path, stop: str
) -> None:
    root = ExperimentRoot(tmp_path / "experiment")
    root.initialize()
    service = Reports(root.database, root.data_root, root.views)
    with fail_sql(stop):
        result = report(
            root.root, "render", "--date", "2026-11-14", "--timezone", "UTC"
        )
    assert result.exit_code == 2 and "execution_failed" in result.output
    repeated = report(root.root, "render", "--date", "2026-11-14", "--timezone", "UTC")
    assert repeated.exit_code == 0, repeated.output
    receipt = json.loads(repeated.stdout)
    assert service.verify(receipt["report_id"]) == receipt
    assert len(list(root.views.glob("*/*.md"))) == 1
    assert list(root.views.glob("*/.report-*")) == []


def test_concurrent_same_day_returns_one_frozen_run(tmp_path: Path) -> None:
    root = ExperimentRoot(tmp_path / "experiment")
    root.initialize()

    def render() -> dict[str, object]:
        return Reports(root.database, root.data_root, root.views).render(
            day="2026-11-14", timezone="UTC"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: render(), range(2)))
    assert receipts[0] == receipts[1]
    assert len(list(root.views.glob("*/*.md"))) == 1


def test_corrupt_bytes_missing_member_and_unsafe_paths_are_rejected(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    read = fixture.read()
    assert read.exit_code == 0, read.output
    root = fixture.layout.extraction.root
    rendered = report(
        root.root,
        "render",
        "--date",
        "2026-11-14",
        "--timezone",
        "UTC",
        "--snapshot",
        fixture.snapshot,
    )
    assert rendered.exit_code == 0, rendered.output
    receipt = json.loads(rendered.stdout)
    report_id = receipt["report_id"]
    path = root.views / receipt["relative_path"]
    original = path.read_bytes()
    path.write_bytes(original + b"PRIVATE_TAMPERED")
    corrupt = report(root.root, "verify", report_id)
    assert corrupt.exit_code == 2 and "content_corrupt" in corrupt.output
    assert "PRIVATE_TAMPERED" not in corrupt.output
    assert report(root.root, "rebuild", report_id).exit_code == 0
    assert path.read_bytes() == original
    path.unlink()
    missing = report(root.root, "verify", report_id)
    assert missing.exit_code == 2 and "file_missing" in missing.output
    outside = tmp_path / "outside.md"
    outside.write_bytes(b"private outside")
    path.symlink_to(outside)
    unsafe = report(root.root, "rebuild", report_id)
    assert unsafe.exit_code == 2 and "unsafe_path" in unsafe.output
    assert outside.read_bytes() == b"private outside"
    path.unlink()
    assert report(root.root, "rebuild", report_id).exit_code == 0
    stable_database = root.database.read_bytes()
    with sqlite3.connect(root.database) as connection:
        connection.execute("DROP TRIGGER report_entries_no_delete")
        connection.execute("DELETE FROM report_entries")
    incomplete = report(root.root, "verify", report_id)
    assert incomplete.exit_code == 2 and "registration_invalid" in incomplete.output
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 2 and "registration_invalid" in backup.output
    root.database.write_bytes(stable_database)
    with sqlite3.connect(root.database) as connection:
        connection.execute("DROP TRIGGER report_runs_publish_only")
        connection.execute("UPDATE report_runs SET relative_path='../PRIVATE_PATH'")
    unsafe_record = report(root.root, "verify", report_id)
    assert (
        unsafe_record.exit_code == 2 and "registration_invalid" in unsafe_record.output
    )
    assert "PRIVATE_PATH" not in unsafe_record.output
