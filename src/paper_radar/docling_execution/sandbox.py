"""Linux x86_64 worker 隔离;过滤器继承到全部后代。"""

import ctypes
import errno
import resource


class _Filter(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("jt", ctypes.c_ubyte),
        ("jf", ctypes.c_ubyte),
        ("k", ctypes.c_uint),
    ]


class _Program(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ushort), ("filter", ctypes.POINTER(_Filter))]


def restrict_worker(memory_limit_bytes: int) -> None:
    # 地址空间而非物理 RSS/整组 MemoryMax;不宣称通用适用阈值。
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # seccomp_data.arch/nr/args[0]。未知架构与 x32 ABI 均终止。
    instructions = [
        _Filter(0x20, 0, 0, 4),
        _Filter(0x15, 1, 0, 0xC000003E),
        _Filter(0x06, 0, 0, 0x80000000),
        _Filter(0x20, 0, 0, 0),
        _Filter(0x35, 0, 1, 0x40000000),
        _Filter(0x06, 0, 0, 0x80000000),
    ]
    # 禁网络与进程组/namespace 逃逸。clone3 返回 ENOSYS 以保留 pthread clone 回退。
    for number in (
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
        51,
        52,
        53,
        54,
        55,
        109,
        112,
        272,
        308,
        425,
        426,
        427,
        101,
        311,
    ):
        instructions.extend(
            [_Filter(0x15, 0, 1, number), _Filter(0x06, 0, 0, 0x00050000 | errno.EPERM)]
        )
    instructions.extend(
        [_Filter(0x15, 0, 1, 435), _Filter(0x06, 0, 0, 0x00050000 | errno.ENOSYS)]
    )
    # clone 可创建普通线程/同组后代,禁止任何 CLONE_NEW* namespace。
    instructions.extend(
        [
            _Filter(0x15, 0, 4, 56),
            _Filter(0x20, 0, 0, 16),
            _Filter(0x45, 0, 1, 0x7E020000),
            _Filter(0x06, 0, 0, 0x00050000 | errno.EPERM),
            _Filter(0x06, 0, 0, 0x7FFF0000),
            _Filter(0x06, 0, 0, 0x7FFF0000),
        ]
    )
    array = (_Filter * len(instructions))(*instructions)
    program = _Program(len(instructions), array)
    libc = ctypes.CDLL(None, use_errno=True)
    if (
        libc.prctl(38, 1, 0, 0, 0) != 0
        or libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0
    ):
        raise OSError("无法建立 worker 隔离")
