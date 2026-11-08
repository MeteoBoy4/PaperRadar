"""#167 A4:无秘密、无崩溃的 Linux exec/dumpable 合成探针。"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Literal

# 仅操作新建合成进程自身。普通 exec 后再读取属性,不会读取 core 或进程内容。
_CHILD = r'''
import ctypes
import json
import os
import resource
import sys
libc = ctypes.CDLL(None, use_errno=True)
def prctl(option, value=0):
    result = libc.prctl(option, value, 0, 0, 0)
    if result < 0:
        raise SystemExit(3)
    return result
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
if sys.argv[1] == "1":
    prctl(38, 1)
prctl(4, 0)
before = prctl(3)
post = r"""
import ctypes
import json
import sys
libc = ctypes.CDLL(None, use_errno=True)
after = libc.prctl(3, 0, 0, 0, 0)
nnp = libc.prctl(39, 0, 0, 0, 0)
result = libc.prctl(4, 0, 0, 0, 0)
reapplied = libc.prctl(3, 0, 0, 0, 0)
if after < 0 or nnp < 0 or result < 0 or reapplied < 0:
    raise SystemExit(3)
print(json.dumps({"before_exec": int(sys.argv[1]), "after_exec": after,
                  "after_reapply": reapplied, "no_new_privs": nnp}))
"""
os.execve(sys.executable,
          [sys.executable, "-I", "-S", "-B", "-c", post, str(before)],
          {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
'''


@dataclass(frozen=True)
class DumpableReceipt:
    before_exec: int
    after_exec: int
    after_reapply: int
    no_new_privs: int
    conclusion: Literal["pre_exec_protection_lost", "not_established"]


def decode(raw: bytes) -> DumpableReceipt:
    """仅接受合成子进程固定形状,不把未知结果解释为保护生效。"""
    if len(raw) > 1024:
        raise ValueError("probe_output_invalid")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("probe_output_invalid") from None
    keys = {"before_exec", "after_exec", "after_reapply", "no_new_privs"}
    if type(data) is not dict or set(data) != keys:
        raise ValueError("probe_output_invalid")
    if any(type(value) is not int or value not in {0, 1, 2} for value in data.values()):
        raise ValueError("probe_output_invalid")
    if data["no_new_privs"] not in {0, 1}:
        raise ValueError("probe_output_invalid")
    lost = data["before_exec"] == 0 and data["after_exec"] != 0
    return DumpableReceipt(
        **data,
        conclusion="pre_exec_protection_lost" if lost else "not_established",
    )


def probe(*, no_new_privs: bool) -> DumpableReceipt:
    """只 exec 固定 Python 小程序;无信号、认证、Node、网络或宿主改动。

    不以 crash/core 检验属性。固定小程序无等待和外部输入;父进程不发送回收信号。
    """
    if platform.system() != "Linux":
        raise ValueError("probe_linux_required")
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", _CHILD, str(int(no_new_privs))],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("probe_child_failed")
    receipt = decode(result.stdout)
    if no_new_privs and receipt.no_new_privs != 1:
        raise ValueError("probe_nnp_not_set")
    return receipt


if __name__ == "__main__":
    print(json.dumps([asdict(probe(no_new_privs=mode)) for mode in (False, True)]))
