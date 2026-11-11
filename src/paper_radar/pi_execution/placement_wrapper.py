"""固定封装入口;scope 中先阻塞,再施加隔离并 exec;不输出秘密。"""

import array
import ctypes
import json
import os
import socket
import struct
import sys
from pathlib import Path

# -I forbids cwd/PYTHONPATH discovery; only the frozen package tree is added.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from paper_radar.pi_execution.isolation import (
    IsolationBoundary,
    disable_core_dumps,
)
from paper_radar.pi_execution.resolver import apply_resolver_view


def main() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    disable_core_dumps()
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError("placement_exec_failed")
    if libc.prctl(0x59616D61, int(sys.argv[2]), 0, 0, 0) != 0:  # PR_SET_PTRACER
        raise RuntimeError("placement_exec_failed")
    with socket.socket(socket.AF_UNIX) as channel:
        channel.settimeout(10)
        channel.connect(sys.argv[1])
        channel.sendall(b"R")
        header, ancillary, flags, _address = channel.recvmsg(4, socket.CMSG_SPACE(1024))
        if len(header) != 4 or flags:
            raise RuntimeError("placement_handshake_invalid")
        size = struct.unpack("!I", header)[0]
        if not 0 < size <= 512 * 1024:
            raise RuntimeError("placement_handshake_invalid")
        descriptors = array.array("i")
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                descriptors.frombytes(data)
        for descriptor in descriptors:
            os.set_inheritable(descriptor, True)
        payload = bytearray()
        while len(payload) < size:
            data = channel.recv(min(65536, size - len(payload)))
            if not data:
                raise RuntimeError("placement_peer_exited")
            payload.extend(data)
        spec = json.loads(payload)
        payload.clear()
        metadata_index = spec.get("auth_metadata_fd_index")
        if metadata_index is not None:
            if spec["attempt"] is not None or type(metadata_index) is not int:
                raise RuntimeError("placement_handshake_invalid")
            spec["env"]["PAPERRADAR_AUTH_METADATA_FD"] = str(
                descriptors[metadata_index]
            )
        apply_resolver_view(Path(spec["resolver_view"]), spec["resolver_digest"])
        os.chdir(spec["cwd"])
        os.umask(0o077)
        disable_core_dumps()
        if spec["attempt"] is not None:
            boundary = IsolationBoundary(
                Path(spec["install"]),
                Path(spec["cwd"]),
                Path(spec["attempt"]),
                spec["proxy_port"],
            )
            boundary._runtime = tuple(Path(path) for path in spec["runtime_paths"])
            boundary()
        elif libc.prctl(38, 1, 0, 0, 0) != 0:
            raise RuntimeError("placement_exec_failed")
        os.execve(spec["argv"][0], spec["argv"], spec["env"])


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        os._exit(125)
