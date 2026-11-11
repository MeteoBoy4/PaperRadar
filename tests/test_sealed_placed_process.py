"""D1 public PlacedProcess seam, native OS stage replaced only in the test adapter."""

import hashlib
import os
import sys
import sysconfig
from pathlib import Path

import pytest

from paper_radar.pi_execution import placement, placement_protocol
from paper_radar.pi_execution.errors import ExecutionError
from tests.pi_placement_support import local_placement


def _closed_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[placement.PlacedProcess, placement_protocol.PlacementProgram, Path]:
    platform = local_placement(monkeypatch)
    runtime = tmp_path / "runtime"
    (runtime / "python/bin").mkdir(parents=True)
    (runtime / "python/bin/python3").symlink_to(Path(sys.executable).resolve())
    probe = runtime / "site-packages/paper_radar/live_evidence/network_probe.py"
    probe.parent.mkdir(parents=True)
    marker = tmp_path / "target-started"
    probe.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
    )
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    program = placement_protocol.PlacementProgram(
        os.getuid(),
        os.getgid(),
        tmp_path / "install",
        tmp_path / "credentials",
        tmp_path / "lock",
        None,
        runtime,
        cwd,
        Path("/etc/resolv.conf"),
        hashlib.sha256(Path("/etc/resolv.conf").read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(placement_protocol, "load_program", lambda: program)
    wrapper = Path(placement.__file__).with_name("placement_wrapper.py")
    bootstrap = tmp_path / "bootstrap.py"
    bootstrap.write_text(
        "import ctypes,sys,runpy\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(wrapper.parents[2])!r})\n"
        f"sys.path.append({sysconfig.get_path('purelib')!r})\n"
        "from paper_radar.pi_execution import placement_protocol as p\n"
        f"program=p.PlacementProgram({program.product_uid}, {program.product_gid}, "
        f"Path({str(program.install)!r}), Path({str(program.credentials)!r}), "
        f"Path({str(program.lock)!r}), None, Path({str(runtime)!r}), "
        f"Path({str(cwd)!r}))\n"
        "p.load_inherited_program=lambda: program\n"
        "from types import SimpleNamespace\n"
        "from paper_radar.pi_execution import placement\n"
        "target=SimpleNamespace(resolver_view=str(program.resolver_view),resolver_digest=program.resolver_digest)\n"
        "placement.verify_inherited_placement=lambda **kwargs: target\n"
        "assert ctypes.CDLL(None).prctl(38,1,0,0,0)==0\n"
        "sys.argv=sys.argv[1:]\nrunpy.run_path(sys.argv[0],run_name='__main__')\n"
    )
    monkeypatch.setattr(
        platform,
        "wrapper_command",
        lambda handshake, parent: (
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(bootstrap),
            str(wrapper),
            handshake,
            str(parent),
        ),
    )
    # This adapter uses the real production encoder. Only native/systemd/cgroup
    # are replaced, so socket JSON and the new wrapper remain under test.
    monkeypatch.setattr(
        platform,
        "execution_payload",
        lambda *args, **kwargs: placement.LinuxPlacementPlatform.execution_payload(
            platform, *args, **kwargs
        ),
    )
    return placement.PlacedProcess(), program, marker


def test_closed_process_keeps_target_blocked_until_same_pid_final_exec_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process, program, marker = _closed_process(tmp_path, monkeypatch)
    checks: list[bool] = []
    try:
        child = process.execute(
            (str(program.python), "-I", str(program.probe)),
            env={},
            cwd=program.cwd,
            install=program.install,
            attempt=None,
            proxy_port=None,
            pass_fds=(),
            before_release=lambda: checks.append(not marker.exists()),
        )
        assert checks == [True]
        assert child.wait(timeout=3) == 0
        assert marker.read_text() == "executed"
    finally:
        process.close()


@pytest.mark.parametrize(
    "payload",
    [
        b'{"argv":["/usr/bin/touch","UNUSED"],"env":{}}',
        b'{"operation":"negative","operation":"negative"}',
        b'{"operation":"negative","runtime_paths":["/"]}',
        b'{"operation":"negative","auth_metadata_fd_index":0}',
    ],
)
def test_wrapper_independently_refuses_uncanonical_private_socket_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    process, program, marker = _closed_process(tmp_path, monkeypatch)
    monkeypatch.setattr(
        placement.PLACEMENT_PLATFORM,
        "execution_payload",
        lambda *args, **kwargs: payload,
    )
    try:
        with pytest.raises(ExecutionError, match="placement_exec_failed"):
            process.execute(
                (str(program.python), "-I", str(program.probe)),
                env={},
                cwd=program.cwd,
                install=program.install,
                attempt=None,
                proxy_port=None,
                pass_fds=(),
            )
        assert not marker.exists()
    finally:
        process.close()
