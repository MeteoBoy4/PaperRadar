"""Independent D1: synthetic Python peers, never Pi, credentials, or network.

The explicit 300-second control is invoked separately; default pytest uses a
short real deadline. Neither control proves a live provider/lease outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
from time import monotonic
from typing import Any

import pytest

from paper_radar.llm.models import CallDescription
from paper_radar.llm.rpc import run_call
from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.llm.rpc_types import (
    DEFAULT_LIMITS,
    RpcFailure,
    RpcLimits,
    RpcReason,
    SessionEvent,
)
from tests.a8_pipe_support import fixture_factory

ROOT = Path(__file__).parents[1]
FAST = RpcLimits(initialization=1, total=3, close=1, terminate=2, poll=0.01)


def description() -> CallDescription:
    """Only public synthetic values; do not prepare an installation or DB."""
    return CallDescription(
        stage="boundary",
        fingerprint="synthetic-fingerprint",
        projection_id="synthetic-projection",
        semantic_snapshot_id="synthetic-semantic",
        audit_snapshot_id="synthetic-audit",
        pi_version="1.4.0",
        adapter_version="synthetic-engineering-control",
        protocol_profile="pi-rpc-1.4.0-v1",
        provider="provider-a",
        model="real-model",
        protocol="prompt_only",
        thinking_level="low",
        temperature=None,
        top_p=None,
        policy_json="{}",
        system_prompt=b"Public synthetic system instruction.",
        stage_input_payload=b"{}",
        user_payload_json="{}",
        sampling="provider_default",
    )


@pytest.mark.parametrize("phase", ["after_prompt", "cleanup_group_kill"])
def test_keyboard_interrupt_propagates_after_real_pipe_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    interruption = KeyboardInterrupt("synthetic-control")
    injected = False
    returned: list[object] = []
    scenario = "grandchild_holds" if phase == "after_prompt" else "grandchild_closed"
    with fixture_factory(tmp_path, scenario) as factory:
        original_killpg = os.killpg

        def interrupted_killpg(pid: int, number: int) -> None:
            nonlocal injected
            assert factory.child is not None and pid == factory.child.pid
            if phase == "cleanup_group_kill" and not injected:
                injected = True
                raise interruption
            original_killpg(pid, number)

        def create(call: CallDescription) -> PipeSession:
            session = factory(call)
            original_pump = session.pump

            def interrupted_pump(pending: bytes, timeout: float) -> SessionEvent:
                nonlocal injected
                event = original_pump(pending, timeout)
                factory.collect()
                if phase == "after_prompt" and "Cprompt" in factory.notices:
                    assert not injected
                    injected = True
                    raise interruption
                return event

            monkeypatch.setattr(session, "pump", interrupted_pump)
            return session

        with monkeypatch.context() as patch:
            patch.setattr(os, "killpg", interrupted_killpg)
            with pytest.raises(KeyboardInterrupt) as caught:
                returned.append(
                    run_call(description(), b"synthetic request", create, limits=FAST)
                )
            assert caught.value is interruption
            assert injected and not returned
            # These assertions precede fixture fallback; run_call/PipeSession,
            # rather than the harness, must reclaim leader and grandchild.
            factory.assert_reclaimed()
            assert "Cprompt" in factory.notices


def _notice(descriptor: int, value: dict[str, object]) -> None:
    raw = json.dumps(value, sort_keys=True).encode() + b"\n"
    assert len(raw) < 1024
    while raw:
        raw = raw[os.write(descriptor, raw) :]


def _controller() -> None:
    """Child entry used only by this module's explicit synthetic controller."""
    mode, directory_text, descriptor_text, total_text = sys.argv[1:]
    directory = Path(directory_text)
    descriptor = int(descriptor_text)
    total = float(total_text)
    assert mode in {"external_sigint", "wallclock"}
    prompt_observed = False
    returned: list[object] = []
    interrupted = False
    factory_count = 0
    if mode == "external_sigint":
        limits = RpcLimits(initialization=3, total=10, close=1, terminate=2, poll=0.01)
    elif total == 300:
        limits = DEFAULT_LIMITS
    else:
        assert 0.5 <= total <= 2
        limits = RpcLimits(
            initialization=total / 2,
            total=total,
            close=min(1, total),
            terminate=2,
            poll=0.01,
        )
    try:
        with fixture_factory(directory, "grandchild_holds") as factory:

            def create(call: CallDescription) -> PipeSession:
                nonlocal factory_count
                factory_count += 1
                assert factory_count == 1
                session = factory(call)
                assert factory.child is not None
                descendants = [int(n[1:]) for n in factory.notices if n.startswith("G")]
                assert len(descendants) == 1
                _notice(
                    descriptor,
                    {"phase": "created", "pids": [factory.child.pid, *descendants]},
                )
                original_pump = session.pump

                def observed_pump(pending: bytes, timeout: float) -> SessionEvent:
                    nonlocal prompt_observed
                    event = original_pump(pending, timeout)
                    factory.collect()
                    if not prompt_observed and "Cprompt" in factory.notices:
                        prompt_observed = True
                        _notice(descriptor, {"phase": "prompt"})
                    return event

                session.pump = observed_pump  # type: ignore[method-assign]
                return session

            started = monotonic()
            try:
                returned.append(
                    run_call(description(), b"synthetic request", create, limits=limits)
                )
            except KeyboardInterrupt:
                interrupted = True
            elapsed = monotonic() - started
            factory.assert_reclaimed()
            assert factory_count == 1 and prompt_observed
            if mode == "external_sigint":
                assert interrupted and not returned
                reason = "keyboard_interrupt"
            else:
                assert not interrupted and returned == [RpcFailure(RpcReason.TIMEOUT)]
                assert elapsed >= total
                reason = "timeout"
            output = {
                "category": "synthetic_rpc_fault_engineering",
                "case": mode,
                "result": "observed_expected",
                "reason": reason,
                "elapsed_seconds": elapsed,
                "real_monotonic": True,
                "prompt_observed": prompt_observed,
                "factory_count": factory_count,
                "peer_group_reclaimed_before_fixture_fallback": True,
                "partial_candidate_returned": False,
                "actual_pi": False,
                "network_operations": 0,
            }
        print(json.dumps(output, sort_keys=True), flush=True)
    finally:
        os.close(descriptor)


def _pin_owned_peer(pid: object, expected_parent: int, expected_group: int) -> int:
    """Pin only the synthetic controller's announced peer or direct descendant."""
    assert type(pid) is int and pid > 1
    descriptor = os.pidfd_open(pid)
    try:
        assert not select.select([descriptor], [], [], 0)[0]
        # Only /proc stat metadata of the just-created synthetic pair is read.
        # No cmdline, environment, memory, logs, or unrelated process is read.
        fields = Path(f"/proc/{pid}/stat").read_bytes().rsplit(b") ", 1)[1].split()
        assert int(fields[1]) == expected_parent
        assert int(fields[2]) == expected_group
        assert not select.select([descriptor], [], [], 0)[0]
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def run_control(directory: Path, *, mode: str, total: float = 0.75) -> dict[str, Any]:
    """One synthetic controller; a real SIGINT is sent exactly once if requested."""
    assert mode in {"external_sigint", "wallclock"}
    directory.mkdir(mode=0o700)
    peer_directory = directory / "peer"
    peer_directory.mkdir(mode=0o700)
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-s",
            "-c",
            "from tests.test_issue167_live_fault_engineering import _controller; "
            "_controller()",
            mode,
            str(peer_directory),
            str(write_fd),
            str(total),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=directory,
        start_new_session=True,
        bufsize=0,
        pass_fds=(write_fd,),
        env={
            "PYTHONPATH": os.pathsep.join(
                [str(ROOT / "tests/deny_external_io"), str(ROOT / "src"), str(ROOT)]
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    os.close(write_fd)
    controller_fd = os.pidfd_open(process.pid)
    peers: list[int] = []
    tail = b""
    signal_count = 0
    phases: list[str] = []
    deadline = monotonic() + (340 if total == 300 else 20)
    try:
        while process.poll() is None:
            assert monotonic() < deadline, "synthetic_controller_deadline"
            if not select.select([read_fd], [], [], 0.05)[0]:
                continue
            data = os.read(read_fd, 1024)
            if not data:
                continue
            tail += data
            assert len(tail) < 2048
            while b"\n" in tail:
                raw, tail = tail.split(b"\n", 1)
                notice = json.loads(raw)
                if notice.get("phase") == "created":
                    assert not phases and not peers
                    assert set(notice) == {"phase", "pids"}
                    pids = notice["pids"]
                    assert type(pids) is list and len(pids) == 2
                    peer_pid = pids[0]
                    assert type(peer_pid) is int
                    peers.append(_pin_owned_peer(peer_pid, process.pid, peer_pid))
                    peers.append(_pin_owned_peer(pids[1], peer_pid, peer_pid))
                    phases.append("created")
                else:
                    assert notice == {"phase": "prompt"} and phases == ["created"]
                    phases.append("prompt")
                    if mode == "external_sigint":
                        assert signal_count == 0
                        assert not select.select([controller_fd], [], [], 0)[0]
                        signal.pidfd_send_signal(controller_fd, signal.SIGINT)
                        signal_count += 1
        assert process.returncode == 0, "synthetic_controller_unknown"
        assert phases == ["created", "prompt"] and not tail and len(peers) == 2
        assert all(select.select([fd], [], [], 1)[0] for fd in peers)
        assert process.stdout is not None
        raw_output = process.stdout.read(4097)
        assert len(raw_output) <= 4096
        output: dict[str, Any] = json.loads(raw_output)
        assert output["category"] == "synthetic_rpc_fault_engineering"
        assert output["result"] == "observed_expected" and output["case"] == mode
        assert output["peer_group_reclaimed_before_fixture_fallback"] is True
        assert output["partial_candidate_returned"] is False
        assert output["actual_pi"] is False and output["network_operations"] == 0
        assert signal_count == (1 if mode == "external_sigint" else 0)
        output["external_sigint_count"] = signal_count
        output["peer_exit_independently_observed"] = True
        output["parent_absolute_limit_seconds"] = 340 if total == 300 else 20
        return output
    finally:
        if process.poll() is None:
            signal.pidfd_send_signal(controller_fd, signal.SIGKILL)
            process.wait(timeout=2)
        # Only failure fallback. Successful evidence above precedes these calls.
        for descriptor in peers:
            if not select.select([descriptor], [], [], 0)[0]:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            os.close(descriptor)
        os.close(controller_fd)
        os.close(read_fd)
        if process.stdout is not None:
            process.stdout.close()


def source_bindings() -> dict[str, str]:
    names = (
        "src/paper_radar/llm/rpc.py",
        "src/paper_radar/llm/rpc_pipes.py",
        "src/paper_radar/llm/rpc_types.py",
        "tests/a8_pipe_support.py",
        "tests/a8_pipe_worker.py",
        "tests/test_issue167_live_fault_engineering.py",
    )
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names
    }


def test_external_pidfd_sigint_preserves_interruption_and_reclaims_group(
    tmp_path: Path,
) -> None:
    output = run_control(tmp_path / "sigint", mode="external_sigint")
    assert output["reason"] == "keyboard_interrupt"
    assert output["external_sigint_count"] == 1
    assert output["peer_exit_independently_observed"] is True
    assert output["factory_count"] == 1


def test_short_real_wallclock_uses_public_timeout_and_reclaims_group(
    tmp_path: Path,
) -> None:
    output = run_control(tmp_path / "wallclock", mode="wallclock", total=0.75)
    assert output["reason"] == "timeout"
    assert 0.75 <= output["elapsed_seconds"] < 5
    assert output["external_sigint_count"] == 0
    assert output["peer_exit_independently_observed"] is True
