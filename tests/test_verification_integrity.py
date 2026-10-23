"""完整公开入口继续拒绝实际执行不足与发布前回执替换。"""

from __future__ import annotations

import json
import os
import select
import shlex
import signal
import socket
import subprocess
import sys
import uuid
from contextlib import suppress
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import run_full_verification
from scripts.offline_evidence import default_checks, run_offline_verification
from tests.a2_full_support import fake_checks, repository_copy
from tests.a7_acceptance_support import passed_receipt


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "node",
    [
        "tests/test_verification_integrity.py::"
        "test_receipt_replacement_before_final_publication_cannot_pass",
        "tests/test_a2_full_entry.py::"
        "test_one_plan_produces_seven_bound_files_and_never_inherits_previous_success[failed]",
        "tests/test_a3_entry.py::"
        "test_real_entry_final_a3_publication_failure_preserves_all_previous_conclusions[io]",
        "tests/test_a4_entry.py::"
        "test_real_entry_final_a4_publication_failure_preserves_all_previous_conclusions[io]",
        "tests/test_a5_entry.py::"
        "test_real_entry_final_a5_publication_failure_preserves_all_previous_conclusions[io]",
    ],
)
def test_nested_entry_tests_preserve_outer_receipt(
    tmp_path: Path, node: str, existing: bool
) -> None:
    sentinel = tmp_path / "outer.pytest.json"
    original = b"outer receipt must remain unchanged\n" if existing else None
    if original is not None:
        sentinel.write_bytes(original)
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment.update(
        PAPER_RADAR_TEST_RECEIPT=str(sentinel),
        PAPER_RADAR_TEST_RUN_ID="outer-sentinel-run",
    )
    result = subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:scripts.a2_test_receipt",
            node,
        ),
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert (sentinel.read_bytes() if sentinel.exists() else None) == original
    assert result.returncode == 0, result.stdout + result.stderr


def test_only_tests_check_receives_its_own_receipt_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").touch()
    (root / "uv.lock").touch()
    binary = tmp_path / "bin"
    binary.mkdir()
    log = tmp_path / "environment.jsonl"
    uv = binary / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"with open({str(log)!r}, 'a') as stream:\n"
        "    stream.write(json.dumps([sys.argv[1:], "
        "os.environ.get('PAPER_RADAR_TEST_RECEIPT'), "
        "os.environ.get('PAPER_RADAR_TEST_RUN_ID')]) + '\\n')\n"
        "print(json.dumps({'python': '3.14.0', 'dependencies': {}}))\n"
    )
    uv.chmod(0o755)
    sentinel = tmp_path / "outer.pytest.json"
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("PAPER_RADAR_TEST_RECEIPT", str(sentinel))
    monkeypatch.setenv("PAPER_RADAR_TEST_RUN_ID", "outer-run")

    path, evidence = run_offline_verification(root, default_checks(), tmp_path / "runs")

    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert evidence["overall"] == "passed"
    assert len(records) == 7  # 一次环境探测, 加六项固定检查。
    assert [record[1:] for record in records] == [
        [None, None],
        [None, None],
        [None, None],
        [None, None],
        [None, None],
        [str(path.with_suffix(".pytest.json").resolve()), evidence["run_id"]],
        [None, None],
    ]
    assert os.environ["PAPER_RADAR_TEST_RECEIPT"] == str(sentinel)
    assert os.environ["PAPER_RADAR_TEST_RUN_ID"] == "outer-run"


@pytest.mark.parametrize("interrupt", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("ignore_term", [False, True])
def test_interrupted_check_stops_entire_process_group_before_publication(
    tmp_path: Path, interrupt: signal.Signals, ignore_term: bool
) -> None:
    address = "\0paperradar-61-" + uuid.uuid4().hex
    marker = tmp_path / "grandchild-wrote"
    member = tmp_path / "grandchild-pid"
    published_with_live_member = tmp_path / "published-with-live-member"
    later = tmp_path / "later-ran"
    output = tmp_path / "runs"
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import os, signal, socket, subprocess, sys\n"
        "from pathlib import Path\n"
        "if len(sys.argv) == 1:\n"
        "    child = subprocess.Popen([sys.executable, __file__, 'grandchild'])\n"
        "    child.wait()\n"
        "else:\n"
        f"    if {ignore_term!r}: signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"    Path({str(member)!r}).write_text(str(os.getpid()))\n"
        "    connection = socket.socket(socket.AF_UNIX)\n"
        f"    connection.connect({address!r})\n"
        "    connection.sendall(f'{os.getpid()} {os.getppid()} {os.getpgrp()} "
        "{os.getsid(0)}\\n'.encode())\n"
        "    if connection.recv(32) == b'release':\n"
        f"        Path({str(marker)!r}).touch()\n"
        "        connection.sendall(b'wrote')\n"
    )
    later_code = f"from pathlib import Path; Path({str(later)!r}).touch()"
    controller = f"""
import os, select, signal, sys
from pathlib import Path
from scripts.offline_evidence import Check, run_offline_verification
# 同一 CPU 使 SIGKILL 返回后不能借另一 CPU 的调度掩盖退出等待缺失。
os.sched_setaffinity(0, {{min(os.sched_getaffinity(0))}})
def observe_publication(event, args):
    if (event == 'open' and isinstance(args[0], str)
        and args[0].startswith({str(output) + "/."!r})
        and args[0].endswith('.tmp') and Path({str(member)!r}).exists()):
        try:
            death = os.pidfd_open(int(Path({str(member)!r}).read_text()))
        except ProcessLookupError:
            return
        try:
            if not select.select([death], [], [], 0)[0]:
                Path({str(published_with_live_member)!r}).touch()
        finally:
            os.close(death)
sys.addaudithook(observe_publication)
def interrupt(signum, frame):
    raise KeyboardInterrupt
signal.signal(signal.SIGTERM, interrupt)
_, evidence = run_offline_verification(
    Path.cwd(),
    (Check('tests', ('uv', 'run', '--offline', '--locked', 'python', {str(worker)!r})),
     Check('later', ({sys.executable!r}, '-c', {later_code!r}))),
    Path({str(output)!r}),
)
raise SystemExit(0 if evidence['overall'] == 'passed' else 1)
"""
    deaths: list[int] = []
    group: int | None = None
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(address)
        listener.listen(1)
        listener.settimeout(15)
        process = subprocess.Popen(
            (sys.executable, "-c", controller),
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(15)
                with connection.makefile("rb") as stream:
                    identifiers = stream.readline().split()
                child, parent, group, session = map(int, identifiers)
                deaths = [os.pidfd_open(pid) for pid in {child, parent, group}]
                process.send_signal(interrupt)
                assert process.wait(timeout=15) == 1
                dead, _, _ = select.select(deaths, [], [], 0)
                if len(dead) != len(deaths):
                    # 屏障由测试控制; 旧实现仍存活的后代必须完成写入后才断言。
                    connection.sendall(b"release")
                    assert connection.recv(32) == b"wrote"
                assert len(dead) == len(deaths)
                assert group == session and group != process.pid
                assert not marker.exists()
                assert not published_with_live_member.exists()
            evidence = json.loads(next(output.glob("*.json")).read_bytes())
            assert evidence["format_version"] == 1
            assert evidence["overall"] == "incomplete"
            assert evidence["completed"] is False
            outcomes = [(item["status"], item["reason"]) for item in evidence["checks"]]
            assert outcomes == [
                ("failed", "interrupted"),
                ("not_run", "interrupted"),
            ]
            assert not later.exists()
        finally:
            for pid in (process.pid, group):
                if pid is None:
                    continue
                with suppress(ProcessLookupError):
                    os.killpg(pid, signal.SIGKILL)
            process.wait(timeout=15)
            for fd in deaths:
                os.close(fd)


@pytest.mark.parametrize("mode", ["collect_only", "deselected"])
def test_zero_pytest_exit_cannot_replace_actual_fixed_test_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    uv = binary / "uv"
    invocation = (
        f"{shlex.quote(sys.executable)} "
        f"{shlex.quote(str(tmp_path / 'write_receipt.py'))}"
    )
    options = (
        "--collect-only"
        if mode == "collect_only"
        else "-k test_unselected_profile_is_savable_but_not_ready"
    )
    uv.write_text(
        uv.read_text(encoding="utf-8").replace(
            invocation,
            f"{shlex.quote(sys.executable)} -m pytest -q "
            f"-p scripts.a2_test_receipt {options}",
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
    assert "test_execution_not_passed" in {r["code"] for r in full["reasons"]}
    a4 = json.loads(next(output.glob("*.a4.json")).read_bytes())
    assert a4["status"] == "failed" and not a4["a4_verified"]
    assert "test_execution_not_passed" in {reason["code"] for reason in a4["reasons"]}
    a5 = json.loads(next(output.glob("*.a5.json")).read_bytes())
    assert a5["status"] == "failed" and not a5["a5_verified"]
    assert "test_execution_not_passed" in {reason["code"] for reason in a5["reasons"]}
    assert len(log.read_text(encoding="utf-8").splitlines()) == 6


def test_receipt_replacement_before_final_publication_cannot_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = tmp_path / "runs"
    original = Path.read_bytes
    reads = 0

    def replace_after_read(path: Path) -> bytes:
        nonlocal reads
        raw = original(path)
        if path.parent == output and path.name.endswith(".pytest.json"):
            reads += 1
            if reads == 2:
                path.write_bytes(b'{"secret":"PRIVATE_RECEIPT_MARKER"}')
        return raw

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    path, full = run_full_verification(root, output)
    assert full["status"] == "failed"
    assert not full["a2_verified"]
    assert "binding_mismatch" in {r["code"] for r in full["reasons"]}
    assert "PRIVATE_RECEIPT_MARKER" not in path.read_text(encoding="utf-8")
