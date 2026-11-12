"""D1: finite native markers through public traced preflight, with no live scope."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

import pytest

from paper_radar.pi_execution import placement_preflight as probe
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement import PlacementTarget
from paper_radar.pi_execution.placement_protocol import NATIVE_PREFLIGHT_CHECKPOINTS

TARGET = PlacementTarget.model_construct(
    slice="paperradar.slice", anchor_pid=42, anchor_start=1
)


class DiagnosticPlatform(probe.LinuxPreflightPlatform):
    def __init__(self, stderr: bytes, stdout: bytes = b"", code: int = 125) -> None:
        self.stderr, self.stdout, self.code = stderr, stdout, code

    def manager_environment(self) -> dict[str, str]:
        return {}

    def verify(self, *args: Any) -> None:
        pass

    def spawn(
        self, argv: tuple[str, ...], env: dict[str, str]
    ) -> subprocess.Popen[bytes]:
        # The test process writes only supplied finite bytes; no namespace/scope IO.
        return subprocess.Popen(
            (
                sys.executable,
                "-I",
                "-S",
                "-c",
                "import os,sys;os.write(2,bytes.fromhex(sys.argv[1]));"
                "os.write(1,bytes.fromhex(sys.argv[2]));sys.exit(int(sys.argv[3]))",
                self.stderr.hex(),
                self.stdout.hex(),
                str(self.code),
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )


def run(platform: DiagnosticPlatform, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe, "PREFLIGHT_PLATFORM", platform)
    probe.run_traced_preflight(
        TARGET, product_uid=os.getuid(), product_gid=os.getgid(), timeout=2
    )


@pytest.mark.parametrize("checkpoint", NATIVE_PREFLIGHT_CHECKPOINTS)
def test_known_native_checkpoint_survives_public_traced_refusal(
    monkeypatch: pytest.MonkeyPatch, checkpoint: str
) -> None:
    platform = DiagnosticPlatform(("placement_native_v1:" + checkpoint + "\n").encode())
    with pytest.raises(ExecutionError, match=r"^placement_exec_failed$") as caught:
        run(platform, monkeypatch)
    assert isinstance(caught.value, probe.NativePreflightError)
    assert caught.value.checkpoint == checkpoint


@pytest.mark.parametrize(
    ("stderr", "stdout", "code"),
    [
        (b"SECRET /private/auth/cache", b"", 125),
        (b"placement_native_v1:unknown\n", b"", 125),
        (b"placement_native_v1:pre_post\nSECRET\n", b"", 125),
        (b"placement_native_v1:pre_post\n" * 2, b"", 125),
        (b"placement_native_v1:pre_post", b"", 125),
        (b"placement_native_v1:pre_post\n", b"R 123\n", 125),
        (b"placement_native_v1:pre_post\n", b"", 0),
        (b"x" * 1024, b"", 125),
    ],
)
def test_nonexact_native_diagnostics_never_get_checkpoint_or_echo_bytes(
    monkeypatch: pytest.MonkeyPatch, stderr: bytes, stdout: bytes, code: int
) -> None:
    with pytest.raises(ExecutionError) as caught:
        run(DiagnosticPlatform(stderr, stdout, code), monkeypatch)
    assert caught.value.reason in {
        "placement_peer_exited",
        "placement_handshake_invalid",
    }
    assert not hasattr(caught.value, "checkpoint")
    assert "SECRET" not in str(caught.value)


class LateDiagnosticPlatform(DiagnosticPlatform):
    def expected_executable(self, *, final: bool) -> Any:
        from pathlib import Path

        return Path(sys.executable)

    def scope_identity(self, *args: Any) -> tuple[int, int]:
        return 1, 2

    def inspect(self, pid: int) -> probe.PreflightProcessState:
        from dataclasses import replace

        state = super().inspect(pid)
        # Model only kernel isolation properties; real pid/session/fds and ptrace.
        return replace(
            state,
            capabilities=(0,) * 5,
            no_new_privs=1,
            seccomp=2,
            core=("0", "0"),
            namespaces=((9, 10), (9, 11)),
            profile="paperradar-placement-post-v1 (enforce)",
        )

    def spawn(
        self, argv: tuple[str, ...], env: dict[str, str]
    ) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            (
                sys.executable,
                "-I",
                "-S",
                "-c",
                "import os,sys;os.write(1,('R '+str(os.getpid())+'\\n').encode());"
                "sys.stdin.buffer.read(1);os.write(2,bytes.fromhex(sys.argv[1]));"
                "os._exit(125)",
                self.stderr.hex(),
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )


@pytest.mark.parametrize("checkpoint", ["post_release", "post_exec_true"])
def test_checkpoint_after_ready_survives_actual_ptrace_peer_exit(
    monkeypatch: pytest.MonkeyPatch, checkpoint: str
) -> None:
    with pytest.raises(ExecutionError, match=r"^placement_exec_failed$") as caught:
        run(
            LateDiagnosticPlatform(
                ("placement_native_v1:" + checkpoint + "\n").encode()
            ),
            monkeypatch,
        )
    assert isinstance(caught.value, probe.NativePreflightError)
    assert caught.value.checkpoint == checkpoint


@pytest.mark.parametrize(
    ("stderr", "code", "checkpoint"),
    [
        (b"", 0, None),
        (b"placement_native_v1:pre_post\n", 125, "pre_post"),
        (b"placement_native_v1:post_exec_true\n", 125, "post_exec_true"),
    ],
)
def test_cold_preflight_keeps_finite_diagnostics(
    monkeypatch: pytest.MonkeyPatch, stderr: bytes, code: int, checkpoint: str | None
) -> None:
    monkeypatch.setattr(
        probe, "PREFLIGHT_PLATFORM", DiagnosticPlatform(stderr, code=code)
    )
    if checkpoint is None:
        probe.run_cold_preflight(product_uid=os.getuid(), product_gid=os.getgid())
    else:
        with pytest.raises(ExecutionError, match=r"^placement_exec_failed$") as caught:
            probe.run_cold_preflight(product_uid=os.getuid(), product_gid=os.getgid())
        assert isinstance(caught.value, probe.NativePreflightError)
        assert caught.value.checkpoint == checkpoint


@pytest.mark.parametrize(
    ("stderr", "stdout", "code"),
    [
        (b"SECRET", b"", 125),
        (b"placement_native_v1:pre_post\n", b"", 0),
        (b"placement_native_v1:pre_post\n", b"unexpected", 125),
        (b"placement_native_v1:pre_post\nextra", b"", 125),
    ],
)
def test_cold_preflight_refuses_nonexact_marker(
    monkeypatch: pytest.MonkeyPatch, stderr: bytes, stdout: bytes, code: int
) -> None:
    monkeypatch.setattr(
        probe, "PREFLIGHT_PLATFORM", DiagnosticPlatform(stderr, stdout, code)
    )
    with pytest.raises(ExecutionError, match=r"^placement_exec_failed$") as caught:
        probe.run_cold_preflight(product_uid=os.getuid(), product_gid=os.getgid())
    assert not hasattr(caught.value, "checkpoint")
