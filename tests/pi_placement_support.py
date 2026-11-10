"""仅替换 Linux manager/cgroup I/O;真实 socket、ptrace、隔离与 exec。"""

import hashlib
import os
from pathlib import Path

import pytest

from paper_radar.pi_execution import placement


class LocalPlacementPlatform(placement.LinuxPlacementPlatform):
    refuse = False

    def manager_environment(self) -> dict[str, str]:
        return {}

    def spawn(self, argv: tuple[str, ...], env: dict[str, str]):
        return super().spawn(argv[8:], env)

    def scope_identity(
        self, target: placement.PlacementTarget, unit: str
    ) -> tuple[int, int]:
        return 1, 2

    def verify(
        self, target: placement.PlacementTarget, pid: int, start: int, unit: str
    ) -> None:
        if self.refuse:
            raise placement.ExecutionError("placement_mismatch")
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
