"""仅替换 Linux manager/cgroup I/O;真实 socket、ptrace、隔离与 exec。"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.pi_execution import placement
from paper_radar.pi_execution.errors import ExecutionError


class LocalPlacementPlatform(placement.LinuxPlacementPlatform):
    refuse = False

    def manager_environment(self) -> dict[str, str]:
        return {}

    def wrapper_command(self, handshake: str, parent: int) -> tuple[str, ...]:
        # OS adapter owns the old arbitrary-target test language. The production
        # native/Python chain contains no switch selecting this fixture.
        return (
            sys.executable,
            "-I",
            str(Path(__file__).parent / "fixtures/pi_placement_os_adapter.py"),
            handshake,
            str(parent),
        )

    def execution_payload(
        self,
        argv: tuple[str, ...],
        *,
        env: dict[str, str],
        cwd: Path,
        install: Path,
        attempt: Path | None,
        proxy_port: int | None,
        pass_fds: tuple[int, ...],
        target: placement.PlacementTarget,
    ) -> bytes:
        from paper_radar.pi_execution import isolation

        return json.dumps(
            {
                "argv": argv,
                "env": env,
                "cwd": str(cwd),
                "install": str(install),
                "attempt": str(attempt) if attempt else None,
                "proxy_port": proxy_port,
                "auth_metadata_fd_index": (
                    pass_fds.index(int(env["PAPERRADAR_AUTH_METADATA_FD"]))
                    if "PAPERRADAR_AUTH_METADATA_FD" in env
                    else None
                ),
                "resolver_view": target.resolver_view,
                "resolver_digest": target.resolver_digest,
                "runtime_paths": [str(path) for path in isolation._RUNTIME_PATHS],
            }
        ).encode()

    def spawn(
        self, argv: tuple[str, ...], env: dict[str, str]
    ) -> subprocess.Popen[bytes]:
        return super().spawn(argv[8:], env)

    def scope_identity(
        self, target: placement.PlacementTarget, unit: str
    ) -> tuple[int, int]:
        return 1, 2

    def verify(
        self, target: placement.PlacementTarget, pid: int, start: int, unit: str
    ) -> None:
        if self.refuse:
            raise ExecutionError("placement_mismatch")
        if self.process_identity(pid)[0] != start:
            raise AssertionError("peer identity changed")


def local_placement(monkeypatch: pytest.MonkeyPatch) -> LocalPlacementPlatform:
    platform = LocalPlacementPlatform()
    target = placement.PlacementTarget.model_construct(
        format_version=1,
        slice="paperradar.slice",
        ancestors=(),
        anchor_pid=os.getpid(),
        anchor_start=platform.process_identity(os.getpid())[0],
        anchor_cgroup="/synthetic",
        egress_digest="1" * 64,
        resolver_view="/etc/resolv.conf",
        resolver_digest=hashlib.sha256(
            Path("/etc/resolv.conf").read_bytes()
        ).hexdigest(),
    )
    monkeypatch.setattr(placement, "PLACEMENT_PLATFORM", platform)
    monkeypatch.setattr(placement, "load_placement_target", lambda **_kwargs: target)
    return platform


def instrument_wrapper(monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    """在独立封装解释器注入 OS 故障;保留真实握手、隔离、ptrace 和 exec。"""
    platform = placement.PLACEMENT_PLATFORM
    spawn = platform.spawn
    bootstrap = (
        "import os, runpy, sys\n"
        "sys.argv = sys.argv[1:]\n"
        + code
        + "\nrunpy.run_path(sys.argv[0], run_name='__main__')\n"
    )

    def instrumented(
        argv: tuple[str, ...], env: dict[str, str]
    ) -> subprocess.Popen[bytes]:
        return spawn((*argv[:10], "-c", bootstrap, *argv[10:]), env)

    monkeypatch.setattr(platform, "spawn", instrumented)
