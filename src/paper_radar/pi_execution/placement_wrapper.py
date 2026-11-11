"""固定 post-native 入口;只接闭合操作,不再创建 user/mount namespace。"""

import array
import ctypes
import os
import socket
import struct
import sys
from pathlib import Path

# Native post uses -I -S -B; only the root-protected frozen package tree is added.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from paper_radar.pi_execution.isolation import IsolationBoundary, disable_core_dumps
from paper_radar.pi_execution.placement import verify_inherited_placement
from paper_radar.pi_execution.placement_protocol import (
    MAX_OPERATION_BYTES,
    decode_operation,
    load_inherited_program,
    reconstruct_execution,
)
from paper_radar.pi_execution.resources import proxy_port


def main() -> None:
    if len(sys.argv) != 3:
        raise RuntimeError("placement_handshake_invalid")
    program = load_inherited_program()
    libc = ctypes.CDLL(None, use_errno=True)
    disable_core_dumps()
    if libc.prctl(39, 0, 0, 0, 0) != 1:  # NNP must precede Python.
        raise RuntimeError("placement_exec_failed")
    parent = int(sys.argv[2])
    if parent <= 1 or libc.prctl(0x59616D61, parent, 0, 0, 0) != 0:
        raise RuntimeError("placement_exec_failed")
    target = verify_inherited_placement()
    if (target.resolver_view, target.resolver_digest) != (
        str(program.resolver_view),
        program.resolver_digest,
    ):
        raise RuntimeError("placement_mismatch")
    with socket.socket(socket.AF_UNIX) as channel:
        channel.settimeout(10)
        channel.connect(sys.argv[1])
        pid, uid, gid = struct.unpack(
            "3i", channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        )
        if (pid, uid, gid) != (parent, program.product_uid, program.product_gid):
            raise RuntimeError("placement_handshake_invalid")
        channel.sendall(b"R")
        header, ancillary, flags, _address = channel.recvmsg(
            4,
            socket.CMSG_SPACE(3 * array.array("i").itemsize),
            socket.MSG_CMSG_CLOEXEC,
        )
        descriptors = array.array("i")
        try:
            if len(header) != 4 or flags & ~socket.MSG_CMSG_CLOEXEC:
                raise RuntimeError("placement_handshake_invalid")
            for level, kind, data in ancillary:
                if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                    raise RuntimeError("placement_handshake_invalid")
                descriptors.frombytes(data)
            size = struct.unpack("!I", header)[0]
            if not 0 < size <= MAX_OPERATION_BYTES:
                raise RuntimeError("placement_handshake_invalid")
            payload = bytearray()
            while len(payload) < size:
                data = channel.recv(min(65536, size - len(payload)))
                if not data:
                    raise RuntimeError("placement_peer_exited")
                payload.extend(data)
            operation = decode_operation(bytes(payload))
            payload.clear()
            execution = reconstruct_execution(program, operation, tuple(descriptors))
            if verify_inherited_placement(close=True) != target:
                raise RuntimeError("placement_mismatch")
            os.chdir(execution.cwd)
            os.umask(0o077)
            disable_core_dumps()
            if execution.attempt is not None:
                IsolationBoundary(
                    program.install,
                    execution.cwd,
                    execution.attempt,
                    proxy_port(program.proxy),
                )()
            # Only validated install-lock and metadata-pipe descriptors survive.
            for descriptor in descriptors:
                os.set_inheritable(descriptor, True)
            os.execve(execution.argv[0], execution.argv, execution.env)
        finally:
            for descriptor in descriptors:
                os.close(descriptor)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        os._exit(125)
