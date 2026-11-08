"""#167 synthetic OFD transfer; no systemd, credentials, or product integration."""

from __future__ import annotations

import array
import fcntl
import math
import os
import selectors
import signal
import socket
import stat
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Mode = Literal["ack", "missing_ack", "failed_ack"]
_FRAME = b"synthetic-lock-v1"
_DESCENDANT = """
import os, sys
fd = int(sys.argv[1])
os.lseek(fd, 7, os.SEEK_SET)
sys.stdout.buffer.write(b'READY\\n'); sys.stdout.buffer.flush()
sys.stdin.buffer.read(1)
os.close(fd)
"""


class HandoffRejected(ValueError):
    """Controlled reason only."""


def send_lock(channel: socket.socket, descriptor: int) -> None:
    rights = array.array("i", [descriptor])
    if channel.sendmsg(
        [_FRAME], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, rights)]
    ) != len(_FRAME):
        raise HandoffRejected("handoff_send_incomplete")


def receive_lock(channel: socket.socket) -> int:
    rights = array.array("i")
    payload, ancillary, flags, _ = channel.recvmsg(
        64, socket.CMSG_SPACE(rights.itemsize * 4), socket.MSG_CMSG_CLOEXEC
    )
    for level, kind, raw in ancillary:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            rights.frombytes(raw[: len(raw) - len(raw) % rights.itemsize])
    if (
        payload != _FRAME
        or len(rights) != 1
        or flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC)
    ):
        for descriptor in rights:
            os.close(descriptor)
        raise HandoffRejected("handoff_frame_invalid")
    return rights[0]


def _read_ready(child: subprocess.Popen[bytes], timeout: float) -> None:
    assert child.stdout is not None
    with selectors.DefaultSelector() as ready:
        ready.register(child.stdout, selectors.EVENT_READ)
        if (
            not ready.select(timeout)
            or os.read(child.stdout.fileno(), 64) != b"READY\n"
        ):
            raise HandoffRejected("descendant_not_ready")


def _peer(channel: socket.socket, mode: str) -> int:
    # This peer is a deliberately fixed synthetic executable, not a broker.
    with channel:
        channel.settimeout(2)
        descriptor = receive_lock(channel)
        descendant: subprocess.Popen[bytes] | None = None
        try:
            if mode == "failed_ack":
                channel.sendmsg([b"FAILED"])
                return 1
            descendant = subprocess.Popen(
                [sys.executable, "-I", "-B", "-c", _DESCENDANT, str(descriptor)],
                pass_fds=(descriptor,),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={"LANG": "C"},
            )
            _read_ready(descendant, 1)
            os.close(descriptor)
            descriptor = -1
            # Only the grandchild and driver now hold the original OFD.
            if mode == "missing_ack":
                channel.recvmsg(64)[0]  # Driver aborts after a bounded ACK wait.
                return 1
            channel.sendmsg([b"ACK:7"])
            if channel.recvmsg(64)[0] != b"RELEASE":
                return 1
            assert descendant.stdin is not None
            descendant.stdin.write(b"x")
            descendant.stdin.close()
            descendant.wait(timeout=1)
            channel.sendmsg([b"CLOSED"])
            return 0
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if descendant is not None:
                if descendant.poll() is None:
                    descendant.kill()
                descendant.wait(timeout=1)
                for stream in (descendant.stdin, descendant.stdout):
                    if stream is not None:
                        stream.close()


@dataclass
class PeerProcess:
    pid: int
    returncode: int | None = None

    def poll(self) -> int | None:
        if self.returncode is None:
            waited, status = os.waitpid(self.pid, os.WNOHANG)
            if waited:
                self.returncode = os.waitstatus_to_exitcode(status)
        return self.returncode

    def wait(self, timeout: float) -> int:
        if self.poll() is None:
            descriptor = os.pidfd_open(self.pid)
            try:
                with selectors.DefaultSelector() as exited:
                    exited.register(descriptor, selectors.EVENT_READ)
                    if not exited.select(timeout):
                        raise subprocess.TimeoutExpired("synthetic-peer", timeout)
                _, status = os.waitpid(self.pid, 0)
                self.returncode = os.waitstatus_to_exitcode(status)
            finally:
                os.close(descriptor)
        assert self.returncode is not None
        return self.returncode


class SyntheticHandoff:
    """Caller supplies an existing synthetic lock; never reads its contents.

    A private socketpair and a fixed peer validate transfer semantics. This does
    not authenticate a separately launched service, or prove cgroup reaping.
    """

    def __init__(self, lock: Path, *, timeout: float = 1, mode: Mode = "ack") -> None:
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 5
        ):
            raise HandoffRejected("handoff_timeout_invalid")
        self.timeout = timeout
        self.descriptor = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.child: PeerProcess | None = None
        self.channel: socket.socket | None = None
        try:
            if not stat.S_ISREG(os.fstat(self.descriptor).st_mode):
                raise HandoffRejected("handoff_lock_not_regular")
            fcntl.flock(self.descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
            self.channel, peer = socket.socketpair(
                socket.AF_UNIX, socket.SOCK_SEQPACKET
            )
            self.channel.settimeout(timeout)
            try:
                peer_pid = os.fork()
                if peer_pid == 0:
                    self.channel.close()
                    os.close(self.descriptor)
                    os.setsid()
                    try:
                        code = _peer(peer, mode)
                    except BaseException:
                        code = 2
                    os._exit(code)
                self.child = PeerProcess(peer_pid)
            finally:
                peer.close()
            send_lock(self.channel, self.descriptor)
            try:
                ack = self.channel.recvmsg(64)[0]
            except TimeoutError:
                raise HandoffRejected("handoff_ack_missing") from None
            except OSError:
                raise HandoffRejected("handoff_ack_failed") from None
            if ack != b"ACK:7":
                raise HandoffRejected("handoff_ack_failed")
            if os.lseek(self.descriptor, 0, os.SEEK_CUR) != 7:
                raise HandoffRejected("handoff_ofd_not_shared")
        except BaseException:
            self.close()
            raise

    def close_parent_descriptor(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)  # Never LOCK_UN on a shared OFD.
            self.descriptor = -1

    def close(self) -> None:
        try:
            if self.channel is not None:
                try:
                    self.channel.sendmsg([b"RELEASE"])
                    self.channel.recvmsg(64)[0]
                except OSError:
                    pass
                self.channel.close()
                self.channel = None
            if self.child is not None:
                try:
                    self.child.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    with suppress(ProcessLookupError):
                        os.killpg(self.child.pid, signal.SIGKILL)
                    self.child.wait(timeout=1)
        finally:
            self.close_parent_descriptor()

    def __enter__(self) -> SyntheticHandoff:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
