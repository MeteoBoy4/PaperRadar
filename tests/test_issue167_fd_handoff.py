"""Unbound #167 real synthetic flock/OFD and anonymous IPC tests."""

import fcntl
import os
import socket
import time
from pathlib import Path

import pytest

from scripts.issue167_fd_handoff import (
    HandoffRejected,
    Mode,
    SyntheticHandoff,
    receive_lock,
)


def exclusively_available(lock: Path) -> bool:
    descriptor = os.open(lock, os.O_RDONLY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True
    finally:
        os.close(descriptor)


def test_original_ofd_survives_parent_close_in_descendant(tmp_path: Path) -> None:
    lock = tmp_path / "synthetic.lock"
    lock.write_bytes(b"not-secret")
    with SyntheticHandoff(lock) as transfer:
        assert os.lseek(transfer.descriptor, 0, os.SEEK_CUR) == 7
        reopened = os.open(lock, os.O_RDONLY)
        try:
            # Same inode does not imply the same open file description.
            assert os.fstat(reopened).st_ino == os.fstat(transfer.descriptor).st_ino
            assert os.lseek(reopened, 0, os.SEEK_CUR) == 0
            assert os.lseek(transfer.descriptor, 0, os.SEEK_CUR) == 7
        finally:
            os.close(reopened)
        transfer.close_parent_descriptor()
        assert not exclusively_available(lock)
        assert transfer.child is not None and transfer.child.poll() is None
    assert exclusively_available(lock)
    assert transfer.child is not None and transfer.child.returncode == 0


@pytest.mark.parametrize(
    "mode,reason",
    [("missing_ack", "handoff_ack_missing"), ("failed_ack", "handoff_ack_failed")],
)
def test_missing_or_failed_ack_reclaims_lock_bounded(
    tmp_path: Path, mode: Mode, reason: str
) -> None:
    lock = tmp_path / "synthetic.lock"
    lock.touch()
    started = time.monotonic()
    with pytest.raises(HandoffRejected, match=rf"^{reason}$"):
        SyntheticHandoff(lock, timeout=0.3, mode=mode)
    assert time.monotonic() - started < 2
    assert exclusively_available(lock)


def test_frame_without_descriptor_cannot_claim_transfer() -> None:
    sender, receiver = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    with sender, receiver:
        sender.sendmsg([b"synthetic-lock-v1"])
        with pytest.raises(HandoffRejected, match=r"^handoff_frame_invalid$"):
            receive_lock(receiver)


def test_invalid_timeout_refuses_before_open(tmp_path: Path) -> None:
    for timeout in (0, 6, float("nan"), True):
        with pytest.raises(HandoffRejected, match=r"^handoff_timeout_invalid$"):
            SyntheticHandoff(tmp_path / "missing", timeout=timeout)
