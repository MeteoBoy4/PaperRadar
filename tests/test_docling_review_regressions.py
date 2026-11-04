"""D1: 外部审阅后的公共 smoke/probe/CLI 与冷进程哨兵回归。"""

import json
import os
import sqlite3
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.config import compile_config
from paper_radar.docling_runtime import probe_docling_runtime
from scripts.check_docling_imports import main
from tests.config_extraction_support import extraction_inputs
from tests.docling_runtime_support import environment
from tests.test_docling_import_smoke import installed as installed


@pytest.mark.parametrize(
    ("minor", "abi_flag", "abiflags", "reason"),
    [
        (14, 0, "t", "platform_unsupported"),
        (14, 1, "", "platform_unsupported"),
        (13, None, "", "platform_unknown"),
        (14, None, "", "platform_unknown"),
    ],
)
def test_smoke_and_probe_reject_unsupported_or_unknown_build_abi(
    installed: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    minor: int,
    abi_flag: int | None,
    abiflags: str,
    reason: str,
) -> None:
    environment(monkeypatch)
    monkeypatch.setattr(sys, "version_info", (3, minor, 0))
    monkeypatch.setattr(sys, "abiflags", abiflags)
    monkeypatch.setattr(sysconfig, "get_config_var", lambda _name: abi_flag)
    probe = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert probe.reason == reason
    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"[{reason}]" in captured.err
    assert "平台" in captured.err and "下一步" in captured.err


@pytest.mark.parametrize(("minor", "abi_flag"), [(12, None), (13, 0), (14, 0)])
def test_smoke_and_probe_accept_supported_gil_builds(
    installed: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    minor: int,
    abi_flag: int | None,
) -> None:
    monkeypatch.setattr(sys, "version_info", (3, minor, 0))
    monkeypatch.setattr(sys, "abiflags", "")
    monkeypatch.setattr(sysconfig, "get_config_var", lambda _name: abi_flag)
    probe = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert probe.reason == "dependencies_discoverable"
    assert main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["gil_enabled"] is True
    assert result["model_loading"] == result["pdf_parsing"] == "not_assessed"


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_cold_guard_rejects_unrelated_sqlite_sidecar_write(
    tmp_path: Path, suffix: str
) -> None:
    unrelated = tmp_path / f"unrelated.sqlite{suffix}"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; open(sys.argv[1], 'w').write('bad')",
            str(unrelated),
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "docling_runtime_guard"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DOCLING_READONLY_DATABASE": str(tmp_path / "selected.sqlite"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 97, result.stdout + result.stderr
    assert not unrelated.exists()


def test_cold_guard_keeps_selected_database_sidecar_exception(
    tmp_path: Path,
) -> None:
    database = tmp_path / "selected.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE observation(value INTEGER)")
        connection.execute("INSERT INTO observation VALUES (7)")
        connection.commit()
        # 保持 WAL/SHM 存在;冷进程只读查询并显式以可写模式打开内部 WAL,
        # 不改字节,验证哨兵确实保留本次数据库例外,而非拒绝全部写打开。
        wal = Path(str(database) + "-wal")
        before_wal, before_db = wal.read_bytes(), database.read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sqlite3, sys; "
                "db = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True); "
                "print(db.execute('SELECT value FROM observation').fetchone()[0]); "
                "open(sys.argv[1] + '-wal', 'ab').close()",
                str(database),
            ],
            cwd=tmp_path,
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": str(Path(__file__).parent / "docling_runtime_guard"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "DOCLING_READONLY_DATABASE": str(database),
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == "7\n"
        assert wal.read_bytes() == before_wal
        assert database.read_bytes() == before_db


@pytest.mark.parametrize(
    "observation",
    [
        "importlib.metadata.version('paper-radar')",
        "importlib.util.find_spec('docling')",
    ],
)
def test_help_guard_detects_inventory_and_top_level_discovery(
    tmp_path: Path, observation: str
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib.metadata, importlib.util; {observation}",
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "docling_runtime_guard"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DOCLING_HELP_ONLY": "1",
            "DOCLING_FORBID_PROBE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 97, result.stdout + result.stderr


@pytest.mark.parametrize("selection", ["settings", "snapshot"])
def test_runtime_scope_only_displays_its_required_and_unassessed_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: str
) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace("cpu-v1", "cpu-v2"))
    saved = compile_config(settings, database)
    chosen = str(settings) if selection == "settings" else saved.snapshot_id[:12]
    environment(monkeypatch)
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "docling-runtime",
            "--database",
            str(database),
            f"--{selection}",
            chosen,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "scope=docling-runtime result=passed" in result.output
    assert "check=selection result=passed" in result.output
    assert "check=docling_fixture.platform result=passed" in result.output
    assert (
        "check=docling_fixture.dependency.docling-core result=passed" in result.output
    )
    assert (
        "category=docling_fixture Docling 样本门禁 result=not_assessed" in result.output
    )
    assert "check=docling_fixture.native_abi result=not_assessed" in result.output
    for unrelated in (
        "stage=",
        "Profile",
        "外发",
        "业务配置缺项",
        "category=feed",
        "category=pi_adapter",
    ):
        assert unrelated not in result.output
    assert "0 不代表任何阶段可运行。" in result.output
