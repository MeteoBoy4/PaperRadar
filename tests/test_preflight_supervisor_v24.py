"""D1: v24 reports the exact existing supervisor step without extra probes."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from paper_radar.pi_execution import placement_preflight as probe
from paper_radar.pi_execution.errors import ExecutionError
from tests.test_native_preflight_diagnostics_v24 import TARGET, DiagnosticPlatform
from tests.test_sealed_placement_preflight import _platform
from tests.test_sealed_placement_preflight import native_peer as native_peer


def test_v24_scope_spawn_failure_retains_step_and_original_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Platform(DiagnosticPlatform):
        def manager_preflight_environment(self) -> dict[str, str]:
            return {}

        def spawn(self, *args: Any) -> Any:
            raise ExecutionError("placement_unavailable")

    monkeypatch.setattr(probe, "PREFLIGHT_PLATFORM", Platform(b""))
    with pytest.raises(ExecutionError, match=r"^placement_unavailable$") as caught:
        probe.run_traced_preflight(
            TARGET,
            product_uid=os.getuid(),
            product_gid=os.getgid(),
            aggregate_manager=True,
        )
    assert caught.value.supervisor_checkpoint == "spawn"


@pytest.mark.parametrize("phase", ["post_state", "final_state"])
@pytest.mark.parametrize(
    "field",
    ["exe", "tracer", "ids", "caps", "nnp", "seccomp", "core", "ns", "profile", "fds"],
)
def test_v24_state_refusal_names_only_the_failed_field(
    monkeypatch: pytest.MonkeyPatch, native_peer: Path, phase: str, field: str
) -> None:
    platform, target = _platform(monkeypatch, native_peer)
    monkeypatch.setattr(platform, "manager_preflight_environment", lambda: {})
    original = platform.inspect

    def inspect(pid: int) -> probe.PreflightProcessState:
        state = original(pid)
        final = os.path.samefile(f"/proc/{pid}/exe", "/usr/bin/true")
        if final != (phase == "final_state"):
            return state
        namespace = Path("/proc/self/ns/user").stat()
        changes = {
            "exe": {"executable": (0, 0)},
            "tracer": {"tracer": state.tracer + 1},
            "ids": {"uid": (0, 0, 0, 0)},
            "caps": {"capabilities": (0, 0, 1, 0, 0)},
            "nnp": {"no_new_privs": 0},
            "seccomp": {"seccomp": 0},
            "core": {"core": ("1", "1")},
            "ns": {"namespaces": ((namespace.st_dev, namespace.st_ino), (9, 11))},
            "profile": {"profile": "SECRET unknown profile"},
            "fds": {"descriptors": frozenset({0, 1, 2, 99})},
        }
        return replace(state, **changes[field])

    monkeypatch.setattr(platform, "inspect", inspect)
    with pytest.raises(ExecutionError, match=r"^placement_exec_failed$") as caught:
        probe.run_traced_preflight(
            target,
            product_uid=os.getuid(),
            product_gid=os.getgid(),
            aggregate_manager=True,
        )
    assert caught.value.supervisor_checkpoint == phase + "_" + field
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "step",
    ["anchor", "group_process_scope", "seize", "release", "detach", "final_exit"],
)
def test_v24_existing_step_fault_is_localized(
    monkeypatch: pytest.MonkeyPatch, native_peer: Path, step: str
) -> None:
    platform, target = _platform(monkeypatch, native_peer)
    monkeypatch.setattr(platform, "manager_preflight_environment", lambda: {})
    if step == "anchor":

        def verify(*args: Any) -> None:
            raise ExecutionError("placement_anchor_invalid")

        monkeypatch.setattr(platform, "verify", verify)
    elif step == "group_process_scope":

        def process_identity(pid: int) -> Any:
            raise ExecutionError("placement_anchor_invalid")

        monkeypatch.setattr(platform, "process_identity", process_identity)
    elif step in {"seize", "detach"}:
        original = probe._ptrace

        def ptrace(request: int, pid: int, data: int = 0) -> None:
            if request == (0x4206 if step == "seize" else 17):
                raise ExecutionError("placement_exec_failed")
            original(request, pid, data)

        monkeypatch.setattr(probe, "_ptrace", ptrace)
    else:
        original_spawn = platform.spawn

        def spawn(*args: Any) -> Any:
            child = original_spawn(*args)
            if step == "release":
                original_input = child.stdin

                class BrokenInput:
                    def write(self, data: bytes) -> None:
                        raise OSError("SECRET failed pipe")

                    def close(self) -> None:
                        original_input.close()

                child.stdin = BrokenInput()
            else:
                original_wait = child.wait

                def wait(*args: Any, **kwargs: Any) -> int:
                    result = original_wait(*args, **kwargs)
                    if result == 0:
                        child.returncode = 1
                        return 1
                    return result

                child.wait = wait
            return child

        monkeypatch.setattr(platform, "spawn", spawn)
    with pytest.raises(ExecutionError) as caught:
        probe.run_traced_preflight(
            target,
            product_uid=os.getuid(),
            product_gid=os.getgid(),
            aggregate_manager=True,
        )
    assert caught.value.supervisor_checkpoint == step
    assert caught.value.reason in {"placement_anchor_invalid", "placement_exec_failed"}
    assert "SECRET" not in str(caught.value)


def test_v24_ready_and_exec_stop_refusals_are_localized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_native_preflight_diagnostics_v24 import LateDiagnosticPlatform

    for step, base in (
        ("ready", DiagnosticPlatform),
        ("exec_stop", LateDiagnosticPlatform),
    ):

        class Platform(base):
            def manager_preflight_environment(self) -> dict[str, str]:
                return {}

        monkeypatch.setattr(probe, "PREFLIGHT_PLATFORM", Platform(b"SECRET"))
        with pytest.raises(ExecutionError) as caught:
            probe.run_traced_preflight(
                TARGET,
                product_uid=os.getuid(),
                product_gid=os.getgid(),
                aggregate_manager=True,
            )
        assert caught.value.supervisor_checkpoint == step
        assert caught.value.reason in {"placement_peer_exited", "placement_exec_failed"}
