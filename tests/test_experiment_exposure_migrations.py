"""B-E15 独立 D1: 非空报告库升级、事务故障与标准恢复。"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.experiment.reports import Reports
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION
from tests.test_experiment_exposure_cli import export
from tests.test_experiment_reports_cli import report
from tests.test_stage_b_report_renderer_migrations import legacy_root


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "CREATE TABLE exposure_exports",
        "CREATE TRIGGER exposure_exports_no_update",
        "UPDATE alembic_version",
    ],
)
def test_nonempty_reports_revision_upgrade_failure_retry_and_restore(
    tmp_path: Path, stop: str | None
) -> None:
    # 冻结的合成 b008/v1 非空根:不让当前 renderer2 产物冒充 b006 历史。
    root = ExperimentRoot(legacy_root(tmp_path))
    with sqlite3.connect(root.database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("b008_body_selection",)
        assert connection.execute(
            "SELECT renderer_version,state FROM report_runs"
        ).fetchall() == [(1, "published")]
    original = root.initialize()
    with sqlite3.connect(root.database) as connection:
        (historical_id,) = connection.execute(
            "SELECT report_id FROM report_runs "
            "WHERE renderer_version=1 AND state='published'"
        ).fetchone()
    rendered = report(root.root, "verify", historical_id)
    assert rendered.exit_code == 0, rendered.output
    report_id = json.loads(rendered.stdout)["report_id"]
    original_receipt = json.loads(rendered.stdout)
    report_path = root.views / original_receipt["relative_path"]
    original_report = report_path.read_bytes()
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(root.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b006_reports")
            connection.commit()
    finally:
        engine.dispose()
    with sqlite3.connect(root.database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("b006_reports",)
        assert connection.execute(
            "SELECT renderer_version,state FROM report_runs"
        ).fetchall() == [(1, "published")]
    if stop:
        with fail_sql(stop), pytest.raises(StorageError) as error:
            upgrade_database(root.database)
        assert error.value.reason == "upgrade_failed"
        with sqlite3.connect(root.database) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("b006_reports",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name='exposure_exports'"
                ).fetchall()
                == []
            )
    assert upgrade_database(root.database) == EXPECTED_MIGRATION_REVISION
    assert root.require() == original
    assert (
        Reports(root.database, root.data_root, root.views).receipt(report_id)["state"]
        == "published"
    )
    assert (
        Reports(root.database, root.data_root, root.views).receipt(report_id)
        == original_receipt
    )
    assert report_path.read_bytes() == original_report
    receipt = export(root.root)
    for operation in (
        "UPDATE exposure_exports SET format_version=1",
        "DELETE FROM exposure_exports",
    ):
        with (
            sqlite3.connect(root.database) as connection,
            pytest.raises(sqlite3.IntegrityError, match="append_only"),
        ):
            connection.execute(operation)
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
    assert backup.exit_code == 0, backup.output
    (batch,) = (tmp_path / "backups").iterdir()
    target = tmp_path / "restored"
    restored = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restored.returncode == 0, restored.stdout + restored.stderr
    from paper_radar.experiment.exposure import Exposures

    recovered = Exposures(target / "database.sqlite3", target)
    assert recovered.receipt(receipt["export_id"]) == receipt
    restored_reports = Reports(target / "database.sqlite3", target, target / "views")
    assert restored_reports.receipt(report_id) == original_receipt
    restored_reports.replay()
    assert (target / "views" / original_receipt["relative_path"]).read_bytes() == (
        original_report
    )
