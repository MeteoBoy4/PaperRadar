"""D1: 冷进程帮助/历史回放/运行诊断的禁 SDK 与只读证据。"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from tests.config_extraction_support import extraction_inputs
from tests.docling_runtime_support import MODULES, V2_VERSIONS
from tests.test_doctor_process import inventory, logical


def invoke(
    root: Path,
    *args: str,
    facts: dict[str, object] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / "docling_runtime_guard"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "DOCLING_HELP_ONLY": "1" if "--help" in args else "0",
    }
    if facts is not None:
        env["DOCLING_FACTS"] = json.dumps(facts)
    return subprocess.run(
        [str(Path(sys.executable).with_name("paper-radar")), *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


@pytest.mark.parametrize(
    "args", [(), ("doctor",), ("config", "check"), ("config", "snapshots", "list")]
)
def test_help_cannot_probe_or_load_sdk(tmp_path: Path, args: tuple[str, ...]) -> None:
    result = invoke(tmp_path, *args, "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    assert inventory(tmp_path) == ()


@pytest.mark.parametrize("selection", ["settings", "snapshot"])
@pytest.mark.parametrize(
    ("case", "reason", "status"),
    [
        ("complete", "dependencies_discoverable", 0),
        ("missing", "dependency_missing", 2),
        ("cv2", "dependency_missing", 2),
        ("mismatch", "dependency_version_mismatch", 2),
        ("inconsistent", "dependency_inconsistent", 2),
        ("unsupported", "platform_unsupported", 2),
        ("unknown", "platform_unknown", 2),
    ],
)
def test_cold_runtime_matrix_never_loads_sdk_or_writes_business_state(
    tmp_path: Path,
    selection: str,
    case: str,
    reason: str,
    status: int,
) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace("cpu-v1", "cpu-v2"))
    saved = compile_config(settings, database)
    chosen = str(settings) if selection == "settings" else saved.snapshot_id[:12]
    if selection == "snapshot":
        shutil.rmtree(settings.parent)
    versions, modules = dict(V2_VERSIONS), set(MODULES)
    if case == "missing":
        versions, modules = {}, set()
    elif case == "cv2":
        del versions["opencv-python-headless"]
        modules.remove("cv2")
    elif case == "mismatch":
        versions["docling-core"] = "2.101.1"
    elif case == "inconsistent":
        modules.remove("docling_core")
    facts: dict[str, object] = {
        "system": "Darwin" if case == "unsupported" else "Linux",
        "libc": None if case == "unknown" else "glibc 2.28",
        "versions": versions,
        "modules": sorted(modules),
    }
    before_tree, before_db = inventory(tmp_path), logical(database)
    result = invoke(
        tmp_path,
        "doctor",
        "--scope",
        "docling-runtime",
        "--database",
        str(database),
        f"--{selection}",
        chosen,
        facts=facts,
    )
    assert result.returncode == status, result.stdout + result.stderr
    assert f"reason={reason}" in result.stdout
    assert "check=docling_fixture.native_abi result=not_assessed" in result.stdout
    assert inventory(tmp_path) == before_tree
    assert logical(database) == before_db


def test_real_base_environment_missing_extra_is_actionable_and_readonly(
    tmp_path: Path,
) -> None:
    # 本冷进程直接观察真实环境;装好 extra 的最终门禁也可运行,不假设缺包。
    settings, _, database = extraction_inputs(tmp_path)
    before_tree, before_db = inventory(tmp_path), logical(database)
    result = invoke(
        tmp_path,
        "doctor",
        "--scope",
        "docling-runtime",
        "--database",
        str(database),
        "--settings",
        str(settings),
    )
    assert result.returncode in {0, 2}, result.stdout + result.stderr
    assert "scope=docling-runtime result=" in result.stdout
    if "result=missing reason=dependency_missing" in result.stdout:
        assert "uv sync --locked --extra docling" in result.stdout
    assert "Docling 样本门禁 result=not_assessed" in result.stdout
    assert inventory(tmp_path) == before_tree
    assert logical(database) == before_db


def test_probe_module_import_has_no_inventory_or_platform_observation(
    tmp_path: Path,
) -> None:
    script = """
import importlib.metadata, importlib.util, os, platform, sysconfig

def forbidden(*args, **kwargs):
    os._exit(97)

importlib.metadata.version = forbidden
importlib.util.find_spec = forbidden
platform.system = forbidden
platform.machine = forbidden
os.confstr = forbidden
sysconfig.get_config_var = forbidden
import paper_radar.docling_runtime
print('import_without_probe')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "import_without_probe\n"
    assert inventory(tmp_path) == ()


@pytest.mark.parametrize("scope", ["basic", "config", "load"])
def test_nonruntime_config_and_historical_load_never_probe_inventory(
    tmp_path: Path,
    scope: str,
) -> None:
    settings, _, database = extraction_inputs(tmp_path)
    saved = compile_config(settings, database)
    if scope == "load":
        shutil.rmtree(settings.parent)
        args = ["config", "diff", saved.snapshot_id, saved.snapshot_id]
    else:
        args = ["doctor", "--scope", scope]
        if scope == "config":
            args.extend(["--settings", str(settings)])
    before_tree, before_db = inventory(tmp_path), logical(database)
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            *args,
            "--database",
            str(database),
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "docling_runtime_guard"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DOCLING_FORBID_PROBE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert inventory(tmp_path) == before_tree
    assert logical(database) == before_db


@pytest.mark.parametrize(
    "selection",
    [
        [],
        ["--settings", "SECRET", "--snapshot", "SECRET"],
        ["--snapshot", "SECRET", "--credentials-dir", "SECRET"],
    ],
)
def test_runtime_usage_errors_cannot_access_database_or_echo_secrets(
    tmp_path: Path,
    selection: list[str],
) -> None:
    result = invoke(
        tmp_path,
        "doctor",
        "--scope",
        "docling-runtime",
        "--database",
        "SECRET",
        *selection,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "SECRET" not in result.stdout + result.stderr
    assert "配置选择无效" in result.stdout + result.stderr
    assert inventory(tmp_path) == ()
