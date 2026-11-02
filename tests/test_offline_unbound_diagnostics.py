"""真实隔离 pytest 失败经公开离线入口输出安全模块定位。"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.offline_evidence import Check, run_offline_verification

ROOT = Path(__file__).resolve().parents[1]
SECRET = "PRIVATE_PROFILE_PROMPT_CREDENTIAL_PARAMETER_SENTINEL"
MODULE = "tests/test_unbound_probe.py"


def probe(root: Path, phase: str) -> None:
    (root / "tests").mkdir()
    (root / "pytest.ini").write_text("[pytest]\n")
    (root / MODULE).write_text(
        "import pytest\n"
        f"SECRET = {SECRET!r}\n"
        + ("raise RuntimeError(SECRET)\n" if phase == "collection" else "")
        + "@pytest.fixture\ndef state():\n"
        + ("    raise RuntimeError(SECRET)\n" if phase == "setup" else "")
        + "    yield\n"
        + ("    raise RuntimeError(SECRET)\n" if phase == "teardown" else "")
        + "@pytest.mark.parametrize('value', [SECRET], ids=[SECRET])\n"
        + "def test_private(state, value):\n"
        + ("    assert False, value\n" if phase == "call" else "    pass\n")
    )


def run_probe(
    root: Path, monkeypatch: pytest.MonkeyPatch, *, mutation: str = ""
) -> tuple[Path, dict[str, Any]]:
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    # 公开入口必须隔离继承的外层pytest身份;没有独立诊断环境变量遗留。
    outer = root / "outer.pytest.json"
    outer.write_text("outer receipt must remain exact")
    monkeypatch.setenv("PAPER_RADAR_TEST_RECEIPT", str(outer))
    monkeypatch.setenv("PAPER_RADAR_TEST_RUN_ID", "outer-run")
    command = (
        sys.executable,
        "-c",
        "import pytest, os, json\nfrom pathlib import Path\n"
        "code = pytest.main(['-p', 'scripts.a2_test_receipt', '-q'])\n"
        + mutation
        + "\nraise SystemExit(code)\n",
    )
    result = run_offline_verification(root, (Check("tests", command),), root / "runs")
    assert outer.read_text() == "outer receipt must remain exact"
    assert not outer.with_suffix(".failures.json").exists()
    return result


@pytest.mark.parametrize("phase", ["setup", "call", "teardown", "collection"])
def test_unbound_real_pytest_failure_has_safe_module_phase_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    phase: str,
) -> None:
    probe(tmp_path, phase)
    path, evidence = run_probe(tmp_path, monkeypatch)
    output = capsys.readouterr().out
    assert f"未绑定失败：{MODULE} ({phase})" in output
    assert SECRET not in output and "test_private" not in output
    assert evidence["overall"] == "failed"
    assert evidence["checks"][0]["exit_code"] in (1, 2)
    receipt = json.loads(path.with_suffix(".pytest.json").read_bytes())
    assert receipt["format_version"] == 1
    assert MODULE not in receipt["modules"]
    sidecar = path.with_suffix(".pytest.failures.json")
    diagnostic = json.loads(sidecar.read_bytes())
    assert diagnostic["run_id"] == evidence["run_id"]
    assert diagnostic["failures"] == [{"module": MODULE, "phase": phase}]
    assert (
        SECRET not in sidecar.read_text() and "test_private" not in sidecar.read_text()
    )
    assert len(list((tmp_path / "runs").glob("*.json"))) == 3


@pytest.mark.parametrize(
    "damage", ["missing", "malformed", "run", "hash", "path", "phase"]
)
def test_missing_or_malformed_auxiliary_diagnostics_cannot_hide_actual_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    damage: str,
) -> None:
    probe(tmp_path, "call")
    mutation = (
        "p = Path(os.environ['PAPER_RADAR_TEST_RECEIPT'])"
        ".with_suffix('.failures.json')\n"
    )
    if damage == "missing":
        mutation += "p.unlink(missing_ok=True)\n"
    elif damage == "malformed":
        mutation += f"p.write_text({SECRET!r})\n"
    else:
        mutation += "d = json.loads(p.read_bytes())\n"
        mutation += {
            "run": "d['run_id'] = 'wrong-run'\n",
            "hash": "d['receipt_sha256'] = '0' * 64\n",
            "path": f"d['failures'][0]['module'] = '/private/{SECRET}/test.py'\n",
            "phase": f"d['failures'][0]['phase'] = {SECRET!r}\n",
        }[damage]
        mutation += "p.write_text(json.dumps(d))\n"
    _, evidence = run_probe(tmp_path, monkeypatch, mutation=mutation)
    output = capsys.readouterr().out
    assert "未绑定失败：" not in output
    assert SECRET not in output
    assert evidence["overall"] == "failed"
    assert evidence["checks"][0]["status"] == "failed"
    assert evidence["checks"][0]["exit_code"] == 1


@pytest.mark.parametrize("failed", [False, True])
def test_fixed_module_and_normal_execution_keep_original_receipt_and_no_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failed: bool,
) -> None:
    probe(tmp_path, "call" if failed else "passed")
    (tmp_path / MODULE).rename(tmp_path / "tests/test_config_service.py")
    path, evidence = run_probe(tmp_path, monkeypatch)
    assert evidence["overall"] == ("failed" if failed else "passed")
    assert evidence["checks"][0]["exit_code"] == int(failed)
    assert "未绑定失败：" not in capsys.readouterr().out
    assert not path.with_suffix(".pytest.failures.json").exists()
    assert len(list((tmp_path / "runs").glob("*.json"))) == 2
    receipt = json.loads(path.with_suffix(".pytest.json").read_bytes())
    assert set(receipt) == {
        "format_version",
        "run_id",
        "completed",
        "exit_code",
        "modules",
    }
    assert receipt["modules"]["tests/test_config_service.py"] == {
        "collected": 1,
        "passed": int(not failed),
        "failed": int(failed),
        "skipped": 0,
        "deselected": 0,
        "incomplete": 0,
    }


def test_non_regular_auxiliary_file_cannot_block_public_offline_failure(
    tmp_path: Path,
) -> None:
    import os
    import subprocess

    probe(tmp_path, "call")
    child = (
        "import pytest,os\nfrom pathlib import Path\n"
        "code=pytest.main(['-p','scripts.a2_test_receipt','-q'])\n"
        "p=Path(os.environ['PAPER_RADAR_TEST_RECEIPT'])"
        ".with_suffix('.failures.json')\n"
        "p.unlink()\nos.mkfifo(p)\nraise SystemExit(code)\n"
    )
    driver = (
        "from pathlib import Path\n"
        "from scripts.offline_evidence import Check,run_offline_verification\n"
        f"root=Path({str(tmp_path)!r})\n"
        f"_,e=run_offline_verification(root,(Check('tests',"
        f"({sys.executable!r},'-c',{child!r})),),root/'runs')\n"
        "assert e['overall']=='failed' and e['checks'][0]['exit_code']==1\n"
    )
    try:
        result = subprocess.run(
            (sys.executable, "-c", driver),
            cwd=tmp_path,
            env={
                **os.environ,
                "PYTHONPATH": str(ROOT),
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            },
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("non-regular auxiliary file blocked public offline entry")
    assert result.returncode == 0, result.stderr
    assert "未绑定失败：" not in result.stdout
    assert SECRET not in result.stdout + result.stderr
