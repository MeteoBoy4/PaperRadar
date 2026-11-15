"""D1:Read 失败只读查询跨根用途,保留旧 CLI 列表与执行守卫。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.body import BodyService
from paper_radar.cli import app
from paper_radar.eligibility import RootPurpose
from tests.a7_registration_support import archive


@pytest.mark.parametrize("purpose", tuple(RootPurpose))
@pytest.mark.parametrize("legacy", (False, True))
def test_read_failure_query_is_read_only_and_root_neutral(
    tmp_path: Path, purpose: RootPurpose, legacy: bool
) -> None:
    data = archive(tmp_path)
    if purpose is not RootPurpose.UNKNOWN:
        BodyService(data.database, data.data_root).register_root(purpose)
    database = (
        data.database.rename(tmp_path / "paper-radar.sqlite3")
        if legacy
        else data.database
    )
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))
    }
    arguments = (
        ["--root", str(tmp_path)]
        if legacy
        else ["--database", str(database), "--data-root", str(data.data_root)]
    )
    result = CliRunner().invoke(
        app, ["reading", "failures", *arguments, "--snapshot", data.snapshot_id]
    )
    assert result.exit_code == 0, result.output
    if legacy:
        assert json.loads(result.stdout) == []
        assert f"根用途：{purpose.value}" in result.stderr
    else:
        assert json.loads(result.stdout) == {
            "root_purpose": purpose.value,
            "snapshot_id": data.snapshot_id,
            "failures": [],
        }
    after = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))
    }
    assert after == before
    assert not (tmp_path / "logs").exists()


def test_read_failure_query_missing_database_creates_nothing(tmp_path: Path) -> None:
    missing = tmp_path / "absent" / "database.sqlite3"
    result = CliRunner().invoke(
        app,
        [
            "reading",
            "failures",
            "--database",
            str(missing),
            "--data-root",
            str(tmp_path / "missing-data"),
            "--snapshot",
            "a" * 64,
        ],
    )
    assert result.exit_code == 2
    assert "database_missing" in result.output
    assert list(tmp_path.iterdir()) == []
