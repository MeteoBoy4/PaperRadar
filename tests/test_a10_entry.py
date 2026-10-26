"""真实完整入口在 A10 最终发布和前置漂移时不能继承历史成功。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.a2_full_support import fake_checks, repository_copy
from tests.a10_acceptance_support import passed_receipt


def test_a10_only_failure_blocks_real_entry_even_when_full_a2_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository_copy(tmp_path / "repo")
    vector = root / "tests/fixtures/a10_coverage.json"
    vector.write_bytes(vector.read_bytes() + b"\n")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    executed = subprocess.run(
        (sys.executable, "-m", "scripts.a1_acceptance"),
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert executed.returncode == 1
    output = root / "verification-runs"
    for suffix in ("a1", "a2-full", "a3", "a4", "a5", "a6", "a7", "a8", "a9"):
        assert (
            json.loads(next(output.glob(f"*.{suffix}.json")).read_bytes())["status"]
            == "passed"
        )
    a10 = json.loads(next(output.glob("*.a10.json")).read_bytes())
    assert a10["status"] == "failed" and not a10["a10_verified"]
    assert {reason["code"] for reason in a10["reasons"]} == {"scope_drift"}
    assert all(value == "failed" for value in a10["capabilities"].values())
    assert len(tuple(output.glob("*.json"))) == 14


@pytest.mark.parametrize("failure", ["interrupt", "io"])
def test_real_entry_final_a10_publication_failure_preserves_all_previous_conclusions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = root / "verification-runs"
    output.mkdir()
    historical = output / "historical.a10.json"
    historical.write_bytes(b'{"status":"passed","a10_verified":true}')
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os,sys
from pathlib import Path
from scripts.a2_full_acceptance import main
original=os.link
published={{}}
def fail(source,target):
    if str(target).endswith('.a10.json'):
        assert len(published)==10
        assert all(path.read_bytes()==raw for path,raw in published.items())
        raise {"KeyboardInterrupt" if failure == "interrupt" else "OSError"}()
    original(source,target)
    published[Path(target)]=Path(target).read_bytes()
os.link=fail
try:
    code=main()
except (KeyboardInterrupt,OSError):
    assert len(published)==10
    assert all(path.read_bytes()==raw for path,raw in published.items())
    sys.exit(3)
sys.exit(code)
""",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert historical.read_bytes() == b'{"status":"passed","a10_verified":true}'
    assert list(output.glob("*.a10.json")) == [historical]
    assert not list(output.glob("*.tmp"))
    assert all(
        json.loads(path.read_bytes())["status"] == "passed"
        for pattern in (
            "*.a1.json",
            "*.a2.json",
            "*.a2-full.json",
            "*.a3.json",
            "*.a4.json",
            "*.a5.json",
            "*.a6.json",
            "*.a7.json",
            "*.a8.json",
            "*.a9.json",
        )
        for path in output.glob(pattern)
    )


@pytest.mark.parametrize("failed_group", ["a4", "a7", "a8", "a9"])
def test_unrelated_required_group_failure_preserves_direct_a10_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_group: str
) -> None:
    from scripts.a2_full_acceptance import acceptance_groups
    from scripts.verification_run import run_verification

    root = repository_copy(tmp_path / "repo")
    path = root / (
        "tests/fixtures/pi_supply/manifest-vector.json"
        if failed_group == "a4"
        else (
            "tests/fixtures/a9_coverage.json"
            if failed_group == "a9"
            else f"tests/fixtures/{failed_group}_capabilities.json"
        )
    )
    path.write_bytes(path.read_bytes() + b"\n")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    run = run_verification(root, tmp_path / "runs", acceptance_groups())
    assert run.passed is False
    a10 = run.conclusions["A10"][1]
    assert a10["status"] == "passed", a10["reasons"]
    assert a10["a10_verified"] is True
    terminal = json.loads((run.output_dir / f"{run.run_id}.terminal.json").read_bytes())
    assert terminal["exit_code"] == 1


@pytest.mark.parametrize("existing", [False, True])
def test_a10_nested_entry_preserves_outer_test_receipt(
    tmp_path: Path, existing: bool
) -> None:
    sentinel = tmp_path / "outer.pytest.json"
    original = b"outer unchanged\n" if existing else None
    if original:
        sentinel.write_bytes(original)
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment.update(
        PAPER_RADAR_TEST_RECEIPT=str(sentinel), PAPER_RADAR_TEST_RUN_ID="outer"
    )
    result = subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:scripts.a2_test_receipt",
            "tests/test_a10_entry.py::"
            "test_real_entry_final_a10_publication_failure_preserves_all_previous_conclusions[io]",
        ),
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (sentinel.read_bytes() if sentinel.exists() else None) == original


def test_optional_a2_01_failure_remains_independent_of_required_a10(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository_copy(tmp_path / "repo")
    scope = root / "scripts/a2_scope.py"
    scope.write_text(
        scope.read_text().replace(
            "SNAPSHOT_FORMAT_VERSION = 1", "SNAPSHOT_FORMAT_VERSION = 0"
        )
    )
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    executed = subprocess.run(
        (sys.executable, "-B", "-m", "scripts.a1_acceptance"),
        cwd=root,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert executed.returncode == 0
    output = root / "verification-runs"
    optional = json.loads(next(output.glob("*.a2.json")).read_bytes())
    a10 = json.loads(next(output.glob("*.a10.json")).read_bytes())
    terminal = json.loads(next(output.glob("*.terminal.json")).read_bytes())
    assert optional["status"] == "failed" and not optional["a2_01_verified"]
    assert a10["status"] == "passed" and a10["a10_verified"] is True
    assert terminal["exit_code"] == 0 and terminal["materials_consistent"] is True
    assert len(tuple(output.glob("*.json"))) == 14
