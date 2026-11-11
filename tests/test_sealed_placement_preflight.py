"""D1: fixed harmless traced probe, with real ptrace and a local OS adapter."""

import os
import subprocess
from pathlib import Path
from typing import Protocol

import pytest

from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement import PlacementTarget


class ProbeRecord(Protocol):
    events: list[str]
    spawned: subprocess.Popen[bytes] | None


def test_traced_probe_refuses_root_or_other_product_identity() -> None:
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.pi_execution.placement_preflight import run_traced_preflight
    from tests.pi_placement_support import local_placement

    patch = pytest.MonkeyPatch()
    try:
        local_placement(patch)
        from paper_radar.pi_execution.placement import load_placement_target

        with pytest.raises(ExecutionError, match="placement_unavailable"):
            run_traced_preflight(
                load_placement_target(), product_uid=0, product_gid=os.getgid()
            )
    finally:
        patch.undo()


@pytest.fixture(scope="module")
def native_peer(tmp_path_factory: pytest.TempPathFactory) -> Path:
    import subprocess

    from paper_radar.live_evidence.placement_build import freeze_placement
    from tests.site_collector_support import site_configuration

    root = tmp_path_factory.mktemp("traced-preflight-native")
    staged = root / "staged"
    (staged / "resources").mkdir(parents=True)
    (staged / "resources/resolv.conf").write_bytes(b"nameserver 192.0.2.1\n")
    freeze_placement(staged, site_configuration(root), Path.cwd())
    adapter = root / "adapter.c"
    adapter.write_text(r"""
#define _GNU_SOURCE
#include <unistd.h>
#include <sys/syscall.h>
#include <string.h>
static int wrong_exec;
static int adapter_execve(const char *path, char *const argv[], char *const env[]) {
    if (wrong_exec && !strcmp(path, "/usr/bin/true")) {
        char *wrong[] = {"/usr/bin/sleep", "30", NULL};
        return syscall(SYS_execve, wrong[0], wrong, env);
    }
    return syscall(SYS_execve, path, argv, env);
}
#define execve adapter_execve
#define main native_main
#include "placement_native.c"
#undef main
#undef execve
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    core_zero();
    close_unknown_fds(3);
    if (!strcmp(argv[2], "exit")) return 125;
    if (!strcmp(argv[2], "stall")) { for (;;) pause(); }
    if (!strcmp(argv[2], "bad-ready")) {
        write(1, "X\n", 2); for (;;) pause();
    }
    if (strcmp(argv[2], "no-nnp")) install_namespace_filter();
    wrong_exec = !strcmp(argv[2], "wrong-exec");
    need(prctl(PR_SET_DUMPABLE, 1, 0, 0, 0) == 0);
    traced_preflight(argv[1]);
    return 3;
}
""")
    binary = root / "peer"
    result = subprocess.run(
        (
            "/usr/bin/cc",
            "-static",
            "-O2",
            "-I",
            str(staged / "placement"),
            str(adapter),
            "-o",
            str(binary),
        ),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    return binary


def _platform(
    monkeypatch: pytest.MonkeyPatch,
    native_peer: Path,
    *,
    mode: str = "normal",
) -> tuple[ProbeRecord, PlacementTarget]:
    import subprocess
    from dataclasses import replace

    from paper_radar.pi_execution import placement
    from paper_radar.pi_execution import placement_preflight as probe
    from tests.pi_placement_support import local_placement

    local = local_placement(monkeypatch)

    class LocalProbe(probe.LinuxPreflightPlatform):
        events: list[str]
        spawned: subprocess.Popen[bytes] | None = None

        def __init__(self) -> None:
            self.events = []

        def manager_environment(self) -> dict[str, str]:
            return {}

        def spawn(
            self, argv: tuple[str, ...], env: dict[str, str]
        ) -> subprocess.Popen[bytes]:
            assert argv[:6] == (
                "/usr/bin/systemd-run",
                "--user",
                "--scope",
                "--quiet",
                "--collect",
                "--expand-environment=no",
            )
            assert argv[-3:] == (
                "/usr/libexec/paperradar/live-evidence-runtime/placement-pre",
                "--preflight-traced",
                str(os.getpid()),
            )
            self.events.append("spawn-fixed-scope")
            self.spawned = super().spawn(
                (str(native_peer), str(os.getpid()), mode), env
            )
            return self.spawned

        def expected_executable(self, *, final: bool) -> Path:
            return super().expected_executable(final=True) if final else native_peer

        def scope_identity(self, target: object, unit: str) -> tuple[int, int]:
            return 1, 2

        def verify(self, target: object, pid: int, start: int, unit: str) -> None:
            if unit == "paperradar-anchor.service":
                self.events.append("anchor")
                return
            assert local.process_identity(pid)[0] == start
            final = os.path.samefile(f"/proc/{pid}/exe", "/usr/bin/true")
            self.events.append("verify-true" if final else "verify-post")
            if mode == "placement-drift" and final:
                raise ExecutionError("placement_mismatch")

        def inspect(self, pid: int) -> probe.PreflightProcessState:
            state = super().inspect(pid)
            final = not os.path.samefile(f"/proc/{pid}/exe", native_peer)
            assert state.tracer == (os.getpid() if final else 0)
            self.events.append(
                "inspect-true-traced" if final else "inspect-post-untraced"
            )
            # Only LSM/capability removal and actual namespace creation are OS
            # fixtures. The executable, PID, core/NNP/filter/FDs and ptrace are real.
            state = replace(
                state,
                capabilities=(0,) * 5,
                namespaces=((9, 10), (9, 11)),
                profile="paperradar-placement-post-v1 (enforce)",
            )
            if mode == "caps":
                state = replace(state, capabilities=(0, 0, 1, 0, 0))
            if mode == "profile":
                state = replace(state, profile="unconfined")
            if mode == "namespace":
                actual = Path("/proc/self/ns/user").stat()
                state = replace(
                    state, namespaces=((actual.st_dev, actual.st_ino), (9, 11))
                )
            return state

    platform = LocalProbe()
    monkeypatch.setattr(probe, "PREFLIGHT_PLATFORM", platform)
    return platform, placement.load_placement_target()


def test_real_ptrace_true_exec_stop_then_detach_and_no_process_remains(
    monkeypatch: pytest.MonkeyPatch,
    native_peer: Path,
) -> None:
    from paper_radar.pi_execution.placement_preflight import run_traced_preflight

    platform, target = _platform(monkeypatch, native_peer)
    run_traced_preflight(target, product_uid=os.getuid(), product_gid=os.getgid())
    assert platform.events == [
        "anchor",
        "spawn-fixed-scope",
        "verify-post",
        "inspect-post-untraced",
        "verify-true",
        "inspect-true-traced",
    ]
    assert platform.spawned is not None
    assert platform.spawned.returncode == 0
    assert not Path(f"/proc/{platform.spawned.pid}").exists()


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("exit", "placement_peer_exited"),
        ("stall", "placement_handshake_timeout"),
        ("bad-ready", "placement_handshake_invalid"),
        ("wrong-exec", "placement_exec_failed"),
        ("no-nnp", "placement_exec_failed"),
        ("caps", "placement_exec_failed"),
        ("profile", "placement_exec_failed"),
        ("namespace", "placement_exec_failed"),
        ("placement-drift", "placement_mismatch"),
    ],
)
def test_traced_probe_failure_is_controlled_and_reaps_waiting_or_traced_target(
    monkeypatch: pytest.MonkeyPatch,
    native_peer: Path,
    mode: str,
    reason: str,
) -> None:
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.pi_execution.placement_preflight import run_traced_preflight

    platform, target = _platform(monkeypatch, native_peer, mode=mode)
    with pytest.raises(ExecutionError, match=reason):
        run_traced_preflight(
            target, product_uid=os.getuid(), product_gid=os.getgid(), timeout=0.5
        )
    assert platform.spawned is not None
    assert platform.spawned.poll() is not None
    assert not Path(f"/proc/{platform.spawned.pid}").exists()


@pytest.mark.parametrize("release", [b"", b"X", b"GG"])
def test_native_traced_mode_refuses_eof_wrong_or_extra_release_byte(
    native_peer: Path,
    release: bytes,
) -> None:
    import subprocess

    child = subprocess.Popen(
        (str(native_peer), str(os.getpid()), "normal"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert child.stdout is not None
    assert child.stdout.readline() == f"R {child.pid}\n".encode()
    stdout, stderr = child.communicate(release, timeout=2)
    assert child.returncode == 125
    assert stdout == stderr == b""
