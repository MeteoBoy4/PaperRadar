"""D1:封印放置的公开闭合协议;不取得真实 OS 资格。"""

from pathlib import Path

import pytest

from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement_protocol import PlacementProgram


def test_wire_rejects_old_arbitrary_execution_language() -> None:
    from paper_radar.pi_execution.placement_protocol import decode_operation

    with pytest.raises(ExecutionError, match="placement_handshake_invalid"):
        decode_operation(b'{"argv":["/usr/bin/python3","-c","pass"]}')


@pytest.mark.parametrize(
    "raw",
    [
        b'{"operation":"negative","operation":"auth"}',
        b'{"operation":"negative","argv":[]}',
        b'{"operation":"negative","env":{}}',
        b'{"operation":"negative","cwd":"/tmp"}',
        b'{"operation":"negative","runtime_paths":[]}',
        b'{"operation":"negative","resolver_view":"/etc/resolv.conf"}',
        b'{"operation":"negative","fd_index":0}',
        b'{"operation":"negative\\u0000"}',
        b'{"operation":"preflight"}',
        b'{"operation":false}',
        b"[]",
        b'{"operation":"model","resource":"/tmp/x","token":"x","prompt":"x","extra":0}',
    ],
)
def test_wire_refuses_ambiguous_or_expanded_operations(raw: bytes) -> None:
    from paper_radar.pi_execution.placement_protocol import decode_operation

    with pytest.raises(ExecutionError, match="placement_handshake_invalid"):
        decode_operation(raw)


def test_negative_operation_has_no_caller_controlled_execution_fields() -> None:
    from paper_radar.pi_execution.placement_protocol import decode_operation

    assert decode_operation(b'{"operation":"negative"}') == {"operation": "negative"}


def test_wire_is_bounded_before_json_parsing() -> None:
    from paper_radar.pi_execution.placement_protocol import decode_operation

    with pytest.raises(ExecutionError, match="placement_handshake_invalid"):
        decode_operation(b" " * (256 * 1024 + 1))


def test_reconstruction_accepts_only_exact_frozen_negative_template(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_execution.placement_protocol import (
        PlacementProgram,
        encode_execution,
        reconstruct_execution,
    )

    program = PlacementProgram(
        1234,
        2345,
        tmp_path / "install",
        tmp_path / "credentials",
        tmp_path / "lock",
        None,
    )
    execution = reconstruct_execution(program, {"operation": "negative"}, ())
    assert execution.argv == (
        "/usr/libexec/paperradar/live-evidence-runtime/python/bin/python3",
        "-I",
        "/usr/libexec/paperradar/live-evidence-runtime/site-packages/paper_radar/live_evidence/network_probe.py",
    )
    assert execution.env == {}
    assert str(execution.cwd) == "/srv/pi-cwd"
    assert (
        encode_execution(
            program,
            execution.argv,
            env={},
            cwd=execution.cwd,
            install=program.install,
            attempt=None,
            proxy_port=None,
            pass_fds=(),
        )
        == b'{"operation":"negative"}'
    )


@pytest.mark.parametrize(
    "change",
    ["node_e", "python_c", "script", "extra_env", "cwd", "install", "attempt", "fds"],
)
def test_execution_rejects_any_expansion_of_frozen_negative_template(
    tmp_path: Path, change: str
) -> None:
    import os

    from paper_radar.pi_execution.placement_protocol import (
        PlacementProgram,
        encode_execution,
    )

    program = PlacementProgram(
        os.getuid(),
        os.getgid(),
        tmp_path / "install",
        tmp_path / "credentials",
        tmp_path / "lock",
        None,
    )
    argv = (str(program.python), "-I", str(program.probe))
    env: dict[str, str] = {}
    descriptors: tuple[int, ...] = ()
    cwd, install, attempt = program.cwd, program.install, None
    if change == "node_e":
        argv = (str(program.node), "-e", "process.exit()")
    elif change == "python_c":
        argv = (str(program.python), "-c", "pass")
    elif change == "script":
        argv = (str(program.python), "-I", "/tmp/script.py")
    elif change == "extra_env":
        env = {"LD_PRELOAD": "/tmp/marker.so"}
    elif change == "cwd":
        cwd = tmp_path
    elif change == "install":
        install = tmp_path
    elif change == "attempt":
        attempt = tmp_path
    else:
        descriptors = (99,)
    with pytest.raises(ExecutionError, match="placement_handshake_invalid"):
        encode_execution(
            program,
            argv,
            env=env,
            cwd=cwd,
            install=install,
            attempt=attempt,
            proxy_port=None,
            pass_fds=descriptors,
        )


def _program_with_resources(
    tmp_path: Path, kind: str
) -> tuple[PlacementProgram, Path, int]:
    import os
    import tempfile

    from paper_radar.pi_execution.placement_protocol import PlacementProgram
    from paper_radar.pi_execution.resources import SETTINGS_JSON

    lock = tmp_path / "install.lock"
    lock.write_bytes(b"")
    lock.chmod(0o600)
    program = PlacementProgram(
        os.getuid(),
        os.getgid(),
        tmp_path / "install",
        tmp_path / "credentials",
        lock,
        None,
    )
    root = Path(
        tempfile.mkdtemp(
            prefix="paper-radar-auth-" if kind == "auth" else "paper-radar-pi-",
            dir="/tmp",
        )
    )
    for name in ("home", "tmp", *(("agent",) if kind == "model" else ())):
        (root / name).mkdir(mode=0o700)
    if kind == "model":
        (root / "agent/settings.json").write_bytes(SETTINGS_JSON)
    return program, root, os.open(lock, os.O_RDONLY | os.O_CLOEXEC)


def test_model_rebuilds_fixed_argv_env_and_transfers_only_install_lock(
    tmp_path: Path,
) -> None:
    import os
    import shutil

    from paper_radar.pi_execution.placement_protocol import (
        MODEL_OPTIONS,
        PlacementProgram,
        encode_execution,
        reconstruct_execution,
    )

    program, root, lock = _program_with_resources(tmp_path, "model")
    assert isinstance(program, PlacementProgram)
    try:
        operation = {
            "operation": "model",
            "resource": str(root),
            "token": "synthetic-oauth-token",
            "prompt": "固定系统指令\n",
        }
        execution = reconstruct_execution(program, operation, (lock,))
        assert execution.argv == (
            str(program.node),
            str(program.pi),
            *MODEL_OPTIONS,
            "固定系统指令\n",
        )
        assert execution.env == {
            "PI_CODING_AGENT_DIR": str(root / "agent"),
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "PI_OFFLINE": "1",
            "HOME": str(root / "home"),
            "TMPDIR": str(root / "tmp"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": str(program.node.parent),
            "OPENAI_API_KEY": "synthetic-oauth-token",
        }
        assert execution.metadata_fd is None and execution.attempt == root
        assert b'"argv"' not in encode_execution(
            program,
            execution.argv,
            env=execution.env,
            cwd=program.cwd,
            install=program.install,
            attempt=root,
            proxy_port=None,
            pass_fds=(lock,),
        )
    finally:
        os.close(lock)
        shutil.rmtree(root)


def test_auth_rebuilds_fixed_helper_and_metadata_write_pipe(tmp_path: Path) -> None:
    import os
    import shutil

    from paper_radar.pi_execution.placement_protocol import (
        PlacementProgram,
        reconstruct_execution,
    )

    program, root, lock = _program_with_resources(tmp_path, "auth")
    assert isinstance(program, PlacementProgram)
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        execution = reconstruct_execution(
            program,
            {"operation": "auth", "resource": str(root), "attempt_timeout": "300"},
            (lock, write_fd),
        )
        assert execution.argv == (str(program.node), str(program.auth_helper))
        assert execution.cwd == program.credentials
        assert execution.env["PAPERRADAR_AUTH_METADATA_FD"] == str(write_fd)
        assert execution.env["PI_CODING_AGENT_DIR"] == str(program.credentials)
        assert "NODE_OPTIONS" not in execution.env
        assert "OPENAI_API_KEY" not in execution.env
        assert execution.attempt is None
    finally:
        for fd in (lock, read_fd, write_fd):
            os.close(fd)
        shutil.rmtree(root)


@pytest.mark.parametrize(
    "damage",
    [
        "extra",
        "directory",
        "socket",
        "writable_lock",
        "wrong_lock",
        "metadata_read",
        "metadata_regular",
        "metadata_fifo",
        "resource_symlink",
        "settings_symlink",
        "extra_resource",
    ],
)
def test_operation_rejects_untrusted_descriptors_and_resource_shapes(
    tmp_path: Path, damage: str
) -> None:
    import os
    import shutil
    import socket

    from paper_radar.pi_execution.placement_protocol import (
        PlacementProgram,
        reconstruct_execution,
    )

    kind = "auth" if damage.startswith("metadata") else "model"
    program, root, lock = _program_with_resources(tmp_path, kind)
    assert isinstance(program, PlacementProgram)
    descriptors: tuple[int, ...] = (lock,)
    operation = {"operation": kind, "resource": str(root)}
    if kind == "model":
        operation.update({"token": "synthetic-token", "prompt": "fixed prompt"})
    else:
        operation["attempt_timeout"] = "300"
    opened: list[int] = []
    with socket.socket() as connection:
        try:
            if damage == "extra":
                descriptors = (lock, lock)
            elif damage == "directory":
                opened.append(os.open(tmp_path, os.O_RDONLY))
                descriptors = tuple(opened)
            elif damage == "socket":
                descriptors = (connection.fileno(),)
            elif damage == "writable_lock":
                opened.append(os.open(program.lock, os.O_RDWR))
                descriptors = tuple(opened)
            elif damage == "wrong_lock":
                wrong = tmp_path / "wrong.lock"
                wrong.write_bytes(b"")
                opened.append(os.open(wrong, os.O_RDONLY))
                descriptors = tuple(opened)
            elif damage == "metadata_read":
                opened.extend(os.pipe2(os.O_NONBLOCK))
                descriptors = (lock, opened[0])
            elif damage == "metadata_fifo":
                fifo = tmp_path / "named-fifo"
                os.mkfifo(fifo)
                opened.append(os.open(fifo, os.O_RDONLY | os.O_NONBLOCK))
                opened.append(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
                descriptors = (lock, opened[-1])
            elif damage == "metadata_regular":
                descriptors = (lock, lock)
            elif damage == "resource_symlink":
                (root / "home").rmdir()
                (root / "home").symlink_to(tmp_path, target_is_directory=True)
            elif damage == "settings_symlink":
                (root / "agent/settings.json").unlink()
                (root / "agent/settings.json").symlink_to(program.lock)
            else:
                (root / "unexpected").write_bytes(b"")
            with pytest.raises(ExecutionError, match="placement_handshake_invalid"):
                reconstruct_execution(program, operation, descriptors)
        finally:
            for fd in (lock, *opened):
                os.close(fd)
            shutil.rmtree(root)


def test_operation_cannot_select_a_business_root_as_temporary_resource(
    tmp_path: Path,
) -> None:
    import os
    import shutil
    from dataclasses import replace

    from paper_radar.pi_execution.placement_protocol import reconstruct_execution

    program, root, lock = _program_with_resources(tmp_path, "model")
    program = replace(program, protected_roots=(root,))
    try:
        with pytest.raises(ExecutionError, match="placement_handshake_invalid"):
            reconstruct_execution(
                program,
                {
                    "operation": "model",
                    "resource": str(root),
                    "token": "synthetic-token",
                    "prompt": "fixed prompt",
                },
                (lock,),
            )
    finally:
        os.close(lock)
        shutil.rmtree(root)
