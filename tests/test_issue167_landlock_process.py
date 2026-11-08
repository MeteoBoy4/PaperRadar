"""独立D1:仅自建无秘密进程的process_vm_readv域关系正负对照。"""

import ctypes
import json
import os
import selectors
import shutil
import subprocess
import sys
from pathlib import Path

from paper_radar.pi_execution.isolation import IsolationBoundary, disable_core_dumps

TARGET = """
import ctypes, json, os, resource, sys
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(0x59616d61, ctypes.c_ulong(-1), 0, 0, 0) != 0:
    print(json.dumps({'ready': False}), flush=True)
    raise SystemExit(1)
sentinel = b'synthetic-memory-sentinel'
buffer = ctypes.create_string_buffer(sentinel)
print(json.dumps({'ready': True, 'pid': os.getpid(),
                  'address': ctypes.addressof(buffer),
                  'length': len(sentinel)}), flush=True)
sys.stdin.buffer.read(1)
"""

PEER = """
import ctypes, errno, sys
class IOVec(ctypes.Structure):
    _fields_ = [('base', ctypes.c_void_p), ('length', ctypes.c_size_t)]
libc = ctypes.CDLL(None, use_errno=True)
call = libc.process_vm_readv
call.argtypes = [ctypes.c_int, ctypes.POINTER(IOVec), ctypes.c_ulong,
                ctypes.POINTER(IOVec), ctypes.c_ulong, ctypes.c_ulong]
call.restype = ctypes.c_ssize_t
pid, address, length = map(int, sys.argv[1:])
sentinel = b'synthetic-memory-sentinel'
if length != len(sentinel):
    print('unknown'); raise SystemExit(1)
local = ctypes.create_string_buffer(length)
local_vec = IOVec(ctypes.addressof(local), length)
remote_vec = IOVec(address, length)
result = call(pid, ctypes.byref(local_vec), 1, ctypes.byref(remote_vec), 1, 0)
if result == length and local.raw == sentinel:
    print('allowed')
elif result == -1 and ctypes.get_errno() == errno.EPERM:
    print('denied')
else:
    print('unknown')
"""


def _control_preexec() -> None:
    disable_core_dumps()
    # 正对照也设置no_new_privs,避免把不同的prctl状态错归于Landlock。
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        raise ValueError("synthetic_no_new_privs_unavailable")


def test_process_vm_readv_allows_control_but_denies_added_landlock_domain(
    tmp_path: Path,
) -> None:
    install = tmp_path / "install"
    cwd = tmp_path / "cwd"
    attempt = tmp_path / "attempt"
    for directory in (install, cwd, attempt):
        directory.mkdir()
    executable = install / "synthetic-python"
    shutil.copyfile(Path(sys.executable).resolve(), executable)
    executable.chmod(0o700)
    boundary = IsolationBoundary(install, cwd, attempt, None)
    # 仅合成Python对端的测试私有stdlib读取,不改产品白名单或策略身份。
    boundary._runtime = (*boundary._runtime, Path(sys.base_prefix) / "lib")
    target = subprocess.Popen(
        [sys.executable, "-I", "-S", "-B", "-c", TARGET],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={},
        preexec_fn=_control_preexec,
    )
    try:
        assert target.stdout is not None
        with selectors.DefaultSelector() as ready:
            ready.register(target.stdout, selectors.EVENT_READ)
            assert ready.select(5), "synthetic_target_ready_timeout"
            metadata = json.loads(os.read(target.stdout.fileno(), 512))
        assert metadata.get("ready") is True, "synthetic_target_ptracer_unavailable"
        assert metadata["pid"] == target.pid, "synthetic_target_pid_mismatch"
        argv = [
            str(executable),
            "-I",
            "-S",
            "-B",
            "-c",
            PEER,
            str(target.pid),
            str(metadata["address"]),
            str(metadata["length"]),
        ]
        control = subprocess.run(
            argv,
            cwd=cwd,
            env={},
            capture_output=True,
            timeout=5,
            preexec_fn=_control_preexec,
            check=False,
        )
        assert control.returncode == 0 and control.stdout == b"allowed\n", (
            "positive_control_unknown"
        )
        denied = subprocess.run(
            argv,
            cwd=cwd,
            env={},
            capture_output=True,
            timeout=5,
            preexec_fn=boundary,
            check=False,
        )
        assert denied.returncode == 0 and denied.stdout == b"denied\n", (
            "landlock_process_vm_readv_not_denied"
        )
    finally:
        if target.stdin is not None:
            target.stdin.close()
        try:
            target.wait(timeout=5)
        except subprocess.TimeoutExpired:
            target.kill()
            target.wait(timeout=5)
        if target.stdout is not None:
            target.stdout.close()
