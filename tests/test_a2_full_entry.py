"""完整离线入口只跑一次计划。结论共享身份。"""

from __future__ import annotations

import importlib.metadata
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import run_full_verification
from scripts.offline_evidence import file_sha256
from tests.a2_full_support import ROOT, fake_checks, repository_copy
from tests.a5_acceptance_support import passed_receipt


@pytest.mark.parametrize("stop", ["passed", "failed", "interrupted", "legacy_mismatch"])
def test_one_plan_produces_seven_bound_files_and_never_inherits_previous_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stop: str,
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    monkeypatch.setenv("A2_TEST_STOP", stop)
    passed = stop in {"passed", "legacy_mismatch"}
    expected_status = (
        "passed" if passed else "incomplete" if stop == "interrupted" else "failed"
    )
    if stop == "legacy_mismatch":
        # 模拟旧切片自己的格式门槛失败。完整入口须由 A1 + 完整 A2 判定。
        legacy_scope = root / "scripts/a2_scope.py"
        legacy_scope.write_text(
            legacy_scope.read_text(encoding="utf-8").replace(
                "SNAPSHOT_FORMAT_VERSION = 1",
                "SNAPSHOT_FORMAT_VERSION = 0",
            ),
            encoding="utf-8",
        )
    output = root / "verification-runs"
    output.mkdir()
    (output / "historical.a2-full.json").write_text(
        '{"status":"passed","a2_verified":true}',
        encoding="utf-8",
    )
    executed = subprocess.run(
        (sys.executable, "-m", "scripts.a1_acceptance"),
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert executed.returncode == (0 if passed else 1), executed.stdout
    paths = [
        p for p in output.glob("*.a2-full.json") if p.name != "historical.a2-full.json"
    ]
    assert len(paths) == 1
    path = paths[0]
    full = json.loads(path.read_bytes())
    assert full["status"] == expected_status
    assert full["a2_verified"] is passed
    run_id = full["run_id"]
    files = [
        output / f"{run_id}{suffix}.json"
        for suffix in ("", ".a1", ".a2", ".a2-full", ".a3", ".a4", ".a5")
    ]
    assert all(p.is_file() for p in files)
    assert path == files[3]
    payloads = [json.loads(p.read_bytes()) for p in files]
    assert all(p["run_id"] == run_id for p in payloads)
    assert all(p["evidence_sha256"] == file_sha256(files[0]) for p in payloads[1:])
    assert full["a1_conclusion_sha256"] == file_sha256(files[1])
    a3 = payloads[4]
    assert a3["status"] == expected_status
    assert a3["a3_verified"] is passed
    assert a3["scope"] == "a3_artifact_backup_restore"
    assert (a3["parent_issue"], a3["issue"]) == (29, 35)
    assert a3["a1_conclusion_sha256"] == file_sha256(files[1])
    assert a3["a2_full_conclusion_sha256"] == file_sha256(files[3])
    if passed:
        assert a3["pytest_receipt_sha256"] == file_sha256(
            output / a3["pytest_receipt_file"]
        )
    a4 = payloads[5]
    assert a4["status"] == expected_status
    assert a4["a4_verified"] is passed
    assert a4["a3_conclusion_sha256"] == file_sha256(files[4])
    assert a4["a1_conclusion_sha256"] == file_sha256(files[1])
    assert a4["a2_full_conclusion_sha256"] == file_sha256(files[3])
    if passed:
        assert a4["pytest_receipt_sha256"] == file_sha256(
            output / a4["pytest_receipt_file"]
        )
    a5 = payloads[6]
    assert a5["status"] == expected_status
    assert a5["a5_verified"] is passed
    assert a5["a1_conclusion_sha256"] == file_sha256(files[1])
    assert a5["a2_full_conclusion_sha256"] == file_sha256(files[3])
    assert a5["a3_conclusion_sha256"] == file_sha256(files[4])
    if passed:
        assert a5["pytest_receipt_sha256"] == file_sha256(
            output / a5["pytest_receipt_file"]
        )
    assert payloads[2]["scope"] == "a2_01_profile_runtime_config_snapshots"
    assert payloads[2]["a2_01_verified"] is (stop == "passed")
    commands = log.read_text(encoding="utf-8").splitlines()
    assert len(commands) == (6 if passed else 5)
    assert sum(" pytest" in command for command in commands) == 1
    assert (output / "historical.a2-full.json").read_text(encoding="utf-8") == (
        '{"status":"passed","a2_verified":true}'
    )


def test_full_entry_help_is_local_and_does_not_create_evidence_or_databases(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    wrapper = scripts / "check-offline"
    wrapper.write_bytes((ROOT / "scripts/check-offline").read_bytes())
    wrapper.chmod(0o755)
    result = subprocess.run(
        (str(wrapper), "--help"),
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(ROOT / "tests/deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "临时数据库" in result.stdout
    assert "不操作用户数据库" in result.stdout
    assert "A2-01" in result.stdout and "完整 A2" in result.stdout
    assert all(group in result.stdout for group in ("A3", "A4", "A5"))
    assert "七份主要文件" in result.stdout
    assert "[离线检查]" not in result.stdout
    assert set(tmp_path.iterdir()) == {scripts}
    assert set(scripts.iterdir()) == {wrapper}


def test_interruption_while_generating_legacy_conclusion_keeps_seven_files_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    original_version = importlib.metadata.version
    interrupted = False

    def interrupt_once(name: str) -> str:
        nonlocal interrupted
        if name == "alembic" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        return original_version(name)

    monkeypatch.setattr(importlib.metadata, "version", interrupt_once)
    output = tmp_path / "runs"
    _, full = run_full_verification(root, output)
    assert full["status"] == "incomplete"
    assert not full["a2_verified"]
    assert len(list(output.glob("*.json"))) == 9
    assert (
        json.loads(next(output.glob("*.a3.json")).read_bytes())["status"]
        == "incomplete"
    )
    assert len(log.read_text(encoding="utf-8").splitlines()) == 6


def test_real_skipped_suite_cannot_pass_complete_entry_even_when_pytest_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = repository_copy(tmp_path / "repo")
    (root / "conftest.py").write_text(
        "import pytest\ndef pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.skip(reason='PRIVATE_SKIP_REASON'))\n",
        encoding="utf-8",
    )
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    uv = binary / "uv"
    invocation = (
        f"{shlex.quote(sys.executable)} "
        f"{shlex.quote(str(tmp_path / 'write_receipt.py'))}"
    )
    uv.write_text(
        uv.read_text(encoding="utf-8").replace(
            invocation,
            f"{shlex.quote(sys.executable)} -m pytest -q -p scripts.a2_test_receipt",
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = tmp_path / "runs"
    _, full = run_full_verification(root, output)
    evidence = json.loads((output / full["evidence_file"]).read_bytes())
    assert evidence["overall"] == "passed"
    assert full["status"] == "failed"
    assert not full["a2_verified"]
    assert "test_execution_not_passed" in {reason["code"] for reason in full["reasons"]}
    assert all(
        record["passed"] == 0 and record["skipped"] > 0
        for record in full["test_execution"]
    )
    assert "PRIVATE_SKIP_REASON" not in json.dumps(full)
