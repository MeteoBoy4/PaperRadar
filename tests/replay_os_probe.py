"""仅 /tmp 自建对照用;直接 syscall 与真实已打开本地 socket,不用于产品传 fd。"""

import ctypes
import errno
import json
import os
import socket
import sys
from pathlib import Path


def main() -> None:
    root, source, fd = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    result: dict[str, object] = {}
    for label, path in (
        ("restored", root / "contents/database.sqlite3"),
        ("original", source),
        ("escape", root / "views/escape"),
    ):
        try:
            with path.open("rb") as stream:
                stream.read(1)
            result[label] = "allowed"
        except OSError as error:
            result[label] = error.errno
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            with socket.socket(family, socket.SOCK_STREAM):
                pass
            result[str(family)] = "allowed"
        except OSError as error:
            result[str(family)] = error.errno
    libc = ctypes.CDLL(None, use_errno=True)

    class Address(ctypes.Structure):
        _fields_ = [("family", ctypes.c_ushort), ("path", ctypes.c_char * 108)]

    address = Address(socket.AF_UNIX, os.fsencode(sys.argv[4]))
    value = libc.connect(fd, ctypes.byref(address), 2 + len(address.path) + 1)
    result["connect"] = "allowed" if value == 0 else ctypes.get_errno()
    os.close(fd)
    result["no_new_privs"] = libc.prctl(39, 0, 0, 0, 0)
    result["seccomp"] = libc.prctl(21, 0, 0, 0, 0)
    print(json.dumps(result, sort_keys=True))
    assert errno.EPERM == 1


if __name__ == "__main__":
    main()
