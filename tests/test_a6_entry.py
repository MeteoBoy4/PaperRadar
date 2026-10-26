"""真实完整入口在 A6 最终发布和前置漂移时不能继承历史成功。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import run_full_verification
from tests.a2_full_support import fake_checks, repository_copy
from tests.a8_acceptance_support import passed_receipt


def test_a6_only_failure_blocks_real_entry_even_when_full_a2_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository_copy(tmp_path / "repo")
    vector = root / "tests/fixtures/a6_capabilities.json"
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
    for suffix in ("a1", "a2-full", "a3", "a4", "a5"):
        assert (
            json.loads(next(output.glob(f"*.{suffix}.json")).read_bytes())["status"]
            == "passed"
        )
    a6 = json.loads(next(output.glob("*.a6.json")).read_bytes())
    assert a6["status"] == "failed" and not a6["a6_verified"]
    assert {reason["code"] for reason in a6["reasons"]} == {"scope_drift"}
    assert all(value == "failed" for value in a6["capabilities"].values())
    assert len(tuple(output.glob("*.json"))) == 14


@pytest.mark.parametrize("failure", ["interrupt", "io"])
def test_real_entry_final_a6_publication_failure_preserves_all_previous_conclusions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = root / "verification-runs"
    output.mkdir()
    historical = output / "historical.a6.json"
    historical.write_bytes(b'{"status":"passed","a6_verified":true}')
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
    if str(target).endswith('.a6.json'):
        assert len(published)==6
        assert all(path.read_bytes()==raw for path,raw in published.items())
        raise {"KeyboardInterrupt" if failure == "interrupt" else "OSError"}()
    original(source,target)
    published[Path(target)]=Path(target).read_bytes()
os.link=fail
try:
    code=main()
except (KeyboardInterrupt,OSError):
    assert len(published)==6
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
    assert historical.read_bytes() == b'{"status":"passed","a6_verified":true}'
    assert list(output.glob("*.a6.json")) == [historical]
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
        )
        for path in output.glob(pattern)
    )


@pytest.mark.parametrize("replaced", ["receipt", "predecessor"])
def test_a6_rechecks_bound_bytes_before_final_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replaced: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = tmp_path / "runs"
    original = Path.read_bytes
    observed = 0
    suffix = ".pytest.json" if replaced == "receipt" else ".a5.json"

    def replace_after_read(path: Path) -> bytes:
        nonlocal observed
        raw = original(path)
        if path.parent == output and path.name.endswith(suffix):
            observed += 1
            # A6 capture+parse已读完后替换;前三组分别读取回执三次。
            trigger = 14 if replaced == "receipt" else 2
            if observed == trigger:
                path.write_bytes(b'{"PRIVATE_REPLACEMENT":true}')
        return raw

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    run_full_verification(root, output)
    path = next(output.glob("*.a6.json"))
    result = json.loads(path.read_bytes())
    assert result["status"] == "failed"
    assert not result["a6_verified"]
    assert "binding_mismatch" in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE_REPLACEMENT" not in path.read_text()


@pytest.mark.parametrize("failed_group", ["a4", "a5"])
def test_a4_only_failure_preserves_a6_but_a5_failure_blocks_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_group: str
) -> None:
    from scripts.a2_full_acceptance import acceptance_groups
    from scripts.verification_run import run_verification

    root = repository_copy(tmp_path / "repo")
    path = root / (
        "tests/fixtures/pi_supply/manifest-vector.json"
        if failed_group == "a4"
        else "tests/fixtures/stage_inputs/boundary-v1.json"
    )
    path.write_bytes(path.read_bytes() + b"\n")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    run = run_verification(root, tmp_path / "runs", acceptance_groups())
    assert run.passed is False
    a6 = run.conclusions["A6"][1]
    assert a6["status"] == ("passed" if failed_group == "a4" else "failed")
    assert a6["a6_verified"] is (failed_group == "a4")
    if failed_group == "a5":
        assert "prerequisite_not_passed" in {reason["code"] for reason in a6["reasons"]}
    terminal = json.loads((run.output_dir / f"{run.run_id}.terminal.json").read_bytes())
    assert terminal["exit_code"] == 1


@pytest.mark.parametrize("existing", [False, True])
def test_a6_nested_entry_preserves_outer_test_receipt(
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
            "tests/test_a6_entry.py::"
            "test_real_entry_final_a6_publication_failure_preserves_all_previous_conclusions[io]",
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
