"""通过控制方及只读命令核对同次终态, 不把 pytest 回执当成入口结果。"""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.offline_evidence import file_sha256
from scripts.verification_identity import capture_identity
from scripts.verification_run import AcceptanceGroup, VerificationRun, run_verification
from tests.a2_full_support import ROOT, fake_checks, repository_copy
from tests.a5_acceptance_support import passed_receipt


def test_controller_publishes_bound_terminal_after_all_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    run = run_verification(root, tmp_path / "runs", acceptance_groups())
    terminal = json.loads((run.output_dir / f"{run.run_id}.terminal.json").read_bytes())
    assert terminal["exit_code"] == 0
    assert [group["suffix"] for group in terminal["groups"]] == [
        ".a1.json",
        ".a2.json",
        ".a2-full.json",
        ".a3.json",
        ".a4.json",
        ".a5.json",
    ]
    before = {path: path.read_bytes() for path in run.output_dir.iterdir()}
    result = subprocess.run(
        (
            str(ROOT / "scripts/verification-status"),
            run.run_id,
            "--runs-dir",
            str(run.output_dir),
            "--json",
        ),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    assert report["tests"]["failed"] == 0
    assert report["tests"]["passed"] > 0
    assert report["applicability"] == "different"
    assert before == {path: path.read_bytes() for path in run.output_dir.iterdir()}


@pytest.fixture
def completed_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VerificationRun:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    return run_verification(root, tmp_path / "runs", acceptance_groups())


def query(
    run: VerificationRun, *, as_json: bool = True
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        (
            str(run.root / "scripts/verification-status"),
            run.run_id,
            "--runs-dir",
            str(run.output_dir),
            *(("--json",) if as_json else ()),
        ),
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(ROOT / ".venv")},
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("case", "status", "reason"),
    [
        ("terminal_missing", "unconfirmed", "terminal_missing"),
        ("missing_group", "unavailable", "material_unavailable"),
        ("bad_json", "failed", "invalid_document"),
        ("deep_json", "failed", "invalid_document"),
        ("unknown_format", "failed", "unsupported_format"),
        ("wrong_run", "failed", "run_id_mismatch"),
        ("nonzero", "failed", "exit_nonzero"),
        ("interrupted", "incomplete", "interrupted"),
        ("changed_group", "failed", "binding_mismatch"),
        ("changed_evidence", "failed", "binding_mismatch"),
        ("changed_receipt", "failed", "binding_mismatch"),
        ("false_consistency", "failed", "binding_mismatch"),
        ("duplicate_group", "failed", "invalid_document"),
        ("bool_exit", "failed", "invalid_document"),
        ("unsafe_suffix", "failed", "invalid_document"),
    ],
)
def test_query_rejects_unproven_or_changed_materials_without_writing(
    completed_run: VerificationRun, case: str, status: str, reason: str
) -> None:
    run = completed_run
    path = run.output_dir / f"{run.run_id}.terminal.json"
    terminal = json.loads(path.read_bytes())
    if case == "terminal_missing":
        path.unlink()
    elif case == "missing_group":
        (run.output_dir / f"{run.run_id}.a5.json").unlink()
    elif case == "bad_json":
        path.write_text("{SECRET unexpected failure")
    elif case == "deep_json":
        path.write_text("[" * 2000 + "0" + "]" * 2000)
    elif case == "changed_group":
        (run.output_dir / f"{run.run_id}.a5.json").write_text("{}")
    elif case in ("changed_evidence", "changed_receipt"):
        suffix = ".json" if case == "changed_evidence" else ".pytest.json"
        target = run.output_dir / f"{run.run_id}{suffix}"
        target.write_bytes(target.read_bytes() + b"\n")
    else:
        if case == "unknown_format":
            terminal["format_version"] = 99
        elif case == "wrong_run":
            terminal["run_id"] = "0" * 32
        elif case == "nonzero":
            terminal["exit_code"] = 1
        elif case == "interrupted":
            terminal["interrupted"] = True
        elif case == "false_consistency":
            terminal["materials_consistent"] = False
        elif case == "duplicate_group":
            terminal["groups"].append(terminal["groups"][0])
        elif case == "bool_exit":
            terminal["exit_code"] = False
        elif case == "unsafe_suffix":
            terminal["groups"][0]["suffix"] = "/../../SECRET.json"
        path.write_text(json.dumps(terminal))
    before = {p: p.read_bytes() for p in run.output_dir.iterdir()}
    result = query(run)
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert (report["status"], report["reason"]) == (status, reason)
    text = query(run, as_json=False)
    assert status.encode() in text.stdout and reason.encode() in text.stdout
    assert b"SECRET" not in result.stdout + result.stderr + text.stdout + text.stderr
    assert before == {p: p.read_bytes() for p in run.output_dir.iterdir()}


def test_history_is_separate_from_current_worktree(
    completed_run: VerificationRun,
) -> None:
    assert json.loads(query(completed_run).stdout)["applicability"] == "same"
    (completed_run.root / "README.md").write_text("changed after verification")
    report = json.loads(query(completed_run).stdout)
    assert report["status"] == "passed"
    assert report["applicability"] == "different"
    (completed_run.root / "scripts/a2_full_acceptance.py").write_text(
        "SECRET invalid registry"
    )
    assert json.loads(query(completed_run).stdout)["status"] == "passed"


def test_historical_checks_do_not_follow_current_execution_plan(
    completed_run: VerificationRun,
) -> None:
    run = completed_run
    source = run.root / "scripts/offline_evidence.py"
    original = source.read_text()
    updated = original.replace('"lockfile",', '"future-lockfile",', 1)
    assert updated != original
    source.write_text(updated)
    before = {path: path.read_bytes() for path in run.output_dir.iterdir()}
    result = query(run)
    report = json.loads(result.stdout)
    assert (report["status"], report["reason"]) == ("passed", "verified")
    assert report["checks_passed"] == report["checks_total"] == 6
    assert report["applicability"] == "different"
    assert before == {path: path.read_bytes() for path in run.output_dir.iterdir()}


@pytest.mark.parametrize("change", ["missing", "reordered", "unknown"])
def test_format_one_rejects_checks_outside_its_historical_plan(
    completed_run: VerificationRun, change: str
) -> None:
    run = completed_run
    evidence = json.loads(run.evidence_path.read_bytes())
    if change == "missing":
        evidence["checks"].pop()
    elif change == "reordered":
        evidence["checks"].reverse()
    else:
        evidence["checks"].append(
            {"id": "future-check", "status": "passed", "reason": "none", "exit_code": 0}
        )
    run.evidence_path.write_text(json.dumps(evidence))
    result = query(run)
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert (report["status"], report["reason"]) == ("failed", "invalid_document")


def test_linked_receipt_must_have_well_formed_counters(
    completed_run: VerificationRun,
) -> None:
    run = completed_run
    receipt_path = run.output_dir / f"{run.run_id}.pytest.json"
    receipt = json.loads(receipt_path.read_bytes())
    receipt["modules"][next(iter(receipt["modules"]))]["passed"] = True
    receipt_path.write_text(json.dumps(receipt))
    terminal_path = run.output_dir / f"{run.run_id}.terminal.json"
    terminal = json.loads(terminal_path.read_bytes())
    terminal["pytest_receipt_sha256"] = file_sha256(receipt_path)
    # 保持前置字节链接有效, 单独验证回执内容而非哈希失配。
    for group in terminal["groups"]:
        path = run.output_dir / f"{run.run_id}{group['suffix']}"
        value = json.loads(path.read_bytes())
        for key, name in list(value.items()):
            if key.endswith("_file"):
                value[key.removesuffix("_file") + "_sha256"] = file_sha256(
                    run.output_dir / name
                )
        path.write_text(json.dumps(value))
        group["sha256"] = file_sha256(path)
    terminal_path.write_text(json.dumps(terminal))
    report = json.loads(query(run).stdout)
    assert (report["status"], report["reason"]) == ("failed", "receipt_not_passed")


@pytest.mark.parametrize("suffix", [".json", ".a5.json", ".pytest.json"])
def test_unreadable_material_is_unavailable(
    completed_run: VerificationRun, suffix: str
) -> None:
    path = completed_run.output_dir / f"{completed_run.run_id}{suffix}"
    path.chmod(0)
    try:
        report = json.loads(query(completed_run).stdout)
        assert (report["status"], report["reason"]) == (
            "unavailable",
            "material_unavailable",
        )
    finally:
        path.chmod(0o600)


def test_unknown_group_format_is_rejected_even_with_valid_byte_links(
    completed_run: VerificationRun,
) -> None:
    run = completed_run
    terminal_path = run.output_dir / f"{run.run_id}.terminal.json"
    terminal = json.loads(terminal_path.read_bytes())
    group = terminal["groups"][-1]
    path = run.output_dir / f"{run.run_id}{group['suffix']}"
    value = json.loads(path.read_bytes())
    value["format_version"] = 999
    path.write_text(json.dumps(value))
    group.update(format_version=999, sha256=file_sha256(path))
    terminal_path.write_text(json.dumps(terminal))
    report = json.loads(query(run).stdout)
    assert (report["status"], report["reason"]) == ("failed", "unsupported_format")


@pytest.mark.parametrize("required", [False, True])
def test_future_group_is_never_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required: bool
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))

    def extra(run: VerificationRun, interrupted: bool) -> tuple[Path, dict[str, Any]]:
        from scripts.verification_publication import publish_conclusion

        value = {"format_version": 1, "run_id": run.run_id, "status": "failed"}
        return publish_conclusion(
            run.output_dir, run.run_id, ".future.json", value
        ), value

    run = run_verification(
        root,
        tmp_path / "runs",
        (
            *acceptance_groups(),
            AcceptanceGroup("未来组", ".future.json", extra, required),
        ),
    )
    report = json.loads(query(run).stdout)
    assert (report["status"], report["reason"]) == ("failed", "unsupported_format")
    terminal = json.loads((run.output_dir / f"{run.run_id}.terminal.json").read_bytes())
    assert terminal["exit_code"] == (1 if required else 0)
    # 查询不从当前生产 registry 推导历史清单; 已登记未来组的缺失始终可见。
    (run.output_dir / f"{run.run_id}.future.json").unlink()
    assert json.loads(query(run).stdout)["reason"] == "material_unavailable"


def test_optional_group_failure_does_not_override_required_groups(
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
    result = subprocess.run(
        (sys.executable, "-B", "-m", "scripts.a1_acceptance"),
        cwd=root,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    output = root / "verification-runs"
    a2_path = next(output.glob("*.a2.json"))
    a2 = json.loads(a2_path.read_bytes())
    assert a2["status"] == "failed"
    run = VerificationRun(
        root,
        output,
        capture_identity(root),
        output / f"{a2['run_id']}.json",
        a2["run_id"],
        (),
    )
    report = json.loads(query(run).stdout)
    assert (report["status"], report["reason"]) == ("passed", "verified")


@pytest.mark.parametrize("suffix", [".a4.json", ".terminal.json"])
def test_publication_failure_leaves_terminal_unconfirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = tmp_path / "runs"
    original = os.link

    def fail(source: Path, target: Path) -> None:
        if target.name.endswith(suffix):
            raise OSError("SECRET publication failure")
        original(source, target)

    monkeypatch.setattr(os, "link", fail)
    with pytest.raises(OSError, match="publication failure"):
        run_verification(root, output, acceptance_groups())
    evidence_path = next(
        path for path in output.glob("*.json") if path.name.count(".") == 1
    )
    probe = VerificationRun(
        root, output, capture_identity(root), evidence_path, evidence_path.stem, ()
    )
    report = json.loads(query(probe).stdout)
    assert (report["status"], report["reason"]) == ("unconfirmed", "terminal_missing")
    assert not list(output.glob("*.terminal.json"))
    assert not list(output.glob("*.tmp"))


@pytest.mark.parametrize("stop", ["failed", "interrupted"])
def test_actual_execution_failure_is_preserved_in_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    monkeypatch.setenv("A2_TEST_STOP", stop)
    run = run_verification(root, tmp_path / "runs", acceptance_groups())
    report = json.loads(query(run).stdout)
    assert (report["status"], report["reason"]) == (
        ("failed", "exit_nonzero")
        if stop == "failed"
        else ("incomplete", "interrupted")
    )


def test_help_missing_materials_and_invalid_arguments_are_local_and_redacted(
    tmp_path: Path,
) -> None:
    entry = ROOT / "scripts/verification-status"
    before = set(tmp_path.iterdir())
    help_result = subprocess.run(
        (str(entry), "--help"), cwd=tmp_path, capture_output=True
    )
    assert help_result.returncode == 0 and "只读查询" in help_result.stdout.decode()
    invalid = subprocess.run(
        (str(entry), "--SECRET"), cwd=tmp_path, capture_output=True
    )
    assert invalid.returncode == 2 and b"SECRET" not in invalid.stderr
    missing = subprocess.run(
        (str(entry), "0" * 32, "--runs-dir", str(tmp_path), "--json"),
        cwd=tmp_path,
        capture_output=True,
    )
    report = json.loads(missing.stdout)
    assert (report["status"], report["reason"]) == (
        "unavailable",
        "material_unavailable",
    )
    assert set(tmp_path.iterdir()) == before


def test_receipt_completion_and_partial_publication_are_not_overall_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    ready, release = tmp_path / "ready", tmp_path / "release"
    os.mkfifo(ready)
    os.mkfifo(release)
    barrier = (
        f"with open({str(ready)!r}, 'wb', buffering=0) as stream: stream.write(b'x')\n"
        f"with open({str(release)!r}, 'rb', buffering=0) as stream: stream.read(1)\n"
    )
    writer = tmp_path / "write_receipt.py"
    writer.write_text(writer.read_text() + barrier)
    output = tmp_path / "runs"
    command = f"""
import os
from pathlib import Path
from scripts.a2_full_acceptance import acceptance_groups
from scripts.verification_run import run_verification
original = os.link
def gate(source, target):
    if str(target).endswith('.a4.json'):
{"".join("        " + line + chr(10) for line in barrier.splitlines())}
    original(source, target)
os.link = gate
run = run_verification(Path({str(root)!r}), Path({str(output)!r}), acceptance_groups())
raise SystemExit(0 if run.passed else 1)
"""
    ready_fd = os.open(ready, os.O_RDWR | os.O_NONBLOCK)
    release_fd = os.open(release, os.O_RDWR | os.O_NONBLOCK)
    process = subprocess.Popen(
        (sys.executable, "-B", "-c", command),
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for phase, check in [("checking", "tests"), ("publishing", None)]:
            assert select.select([ready_fd], [], [], 20)[0], "未到达进程屏障"
            assert os.read(ready_fd, 1) == b"x"
            receipt_path = next(output.glob("*.pytest.json"))
            receipt = json.loads(receipt_path.read_bytes())
            assert receipt["completed"] is True and receipt["exit_code"] == 0
            probe = VerificationRun(
                root,
                output,
                capture_identity(root),
                output / f"{receipt['run_id']}.json",
                receipt["run_id"],
                (),
            )
            report = json.loads(query(probe).stdout)
            assert report["status"] == "unconfirmed"
            assert report["phase"] == phase and report["current_check"] == check
            assert process.poll() is None
            assert not list(output.glob("*.terminal.json"))
            os.write(release_fd, b"x")
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, (stdout, stderr)
        assert json.loads(query(probe).stdout)["status"] == "passed"
    finally:
        if process.poll() is None:
            os.write(release_fd, b"xx")
            process.send_signal(signal.SIGINT)
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        os.close(ready_fd)
        os.close(release_fd)
