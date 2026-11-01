"""真实标准库子进程观察 Landlock 拒绝;能力不足不得 skip。"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.pi_execution.isolation import IsolationBoundary, isolation_capability


def test_kernel_supports_required_landlock_and_observable_file_denials(
    tmp_path: Path,
) -> None:
    assert isolation_capability() >= 4
    install = tmp_path / "install"
    install.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    executable = install / "node"
    shutil.copyfile(Path(sys.executable).resolve(), executable)
    executable.chmod(0o755)
    allowed = install / "runtime"
    allowed.write_text("readable")
    private = tmp_path / "business.sqlite"
    private.write_text("private sentinel")
    script = """
import json, os, sys
result = {}
for label, path, mode in json.loads(sys.argv[1]):
    try:
        with open(path, mode) as stream:
            stream.read() if mode == 'r' else stream.write('written')
        result[label] = 'allowed'
    except PermissionError:
        result[label] = 'denied'
print(json.dumps(result, sort_keys=True))
"""
    boundary = IsolationBoundary(install, cwd, attempt, None)
    # 对端是标准库 Python;这一个额外运行时读取授权仅为测试私有注入。
    boundary._runtime = (*boundary._runtime, Path(sys.base_prefix) / "lib")
    observed = subprocess.run(
        [
            str(executable),
            "-I",
            "-S",
            "-c",
            script,
            json.dumps(
                [
                    ["runtime", str(allowed), "r"],
                    ["database", str(private), "r"],
                    ["install_write", str(allowed), "w"],
                    ["cwd_write", str(cwd / "AGENTS.md"), "w"],
                    ["attempt_write", str(attempt / "own"), "w"],
                ]
            ),
        ],
        preexec_fn=boundary,
        capture_output=True,
        timeout=10,
        check=True,
    )
    assert json.loads(observed.stdout) == {
        "runtime": "allowed",
        "database": "denied",
        "install_write": "denied",
        "cwd_write": "denied",
        "attempt_write": "allowed",
    }


def test_tcp_ports_are_observably_limited_to_443_and_explicit_proxy(
    tmp_path: Path,
) -> None:
    import socket

    install = tmp_path / "install"
    install.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    executable = install / "node"
    shutil.copyfile(Path(sys.executable).resolve(), executable)
    executable.chmod(0o755)
    with socket.socket() as proxy, socket.socket() as private:
        proxy.bind(("127.0.0.1", 0))
        proxy.listen()
        private.bind(("127.0.0.1", 0))
        private.listen()
        allowed_port = proxy.getsockname()[1]
        denied_port = private.getsockname()[1]
        boundary = IsolationBoundary(install, cwd, attempt, allowed_port)
        boundary._runtime = (*boundary._runtime, Path(sys.base_prefix) / "lib")
        script = """
import json, socket, sys
result = {}
for label, port in [('proxy', int(sys.argv[1])), ('private', int(sys.argv[2]))]:
    with socket.socket() as connection:
        connection.settimeout(1)
        try:
            connection.connect(('127.0.0.1', port))
            result[label] = 'allowed'
        except PermissionError:
            result[label] = 'denied'
with socket.socket() as server:
    try:
        server.bind(('127.0.0.1', 0))
        result['bind'] = 'allowed'
    except PermissionError:
        result['bind'] = 'denied'
print(json.dumps(result))
"""
        result = subprocess.run(
            [
                str(executable),
                "-I",
                "-S",
                "-c",
                script,
                str(allowed_port),
                str(denied_port),
            ],
            preexec_fn=boundary,
            capture_output=True,
            check=True,
            timeout=10,
        )
    assert json.loads(result.stdout) == {
        "proxy": "allowed",
        "private": "denied",
        "bind": "denied",
    }


def test_unavailable_kernel_capability_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    import pytest

    from paper_radar.pi_execution import ExecutionError, isolation

    monkeypatch.setattr(isolation._LIBC, "syscall", lambda *args: 3)
    with pytest.raises(ExecutionError, match="isolation_unavailable"):
        isolation_capability()
