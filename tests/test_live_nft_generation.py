"""D1: 固定只读 GETGEN 的独立 UAPI 包络,不建立真实 Netlink socket。"""

import os
import socket
import struct
from typing import Any, Self

import pytest

GOOD = bytes.fromhex(
    "300000000f0a000001000000d2040000"
    "0000002a"
    "080001000000002a"
    "08000200000004d2"
    "0c000300707974686f6e3300"
)


class ReplySocket:
    def __init__(
        self, reply: bytes = GOOD, *, sender: tuple[int, int] = (0, 0), flags: int = 0
    ) -> None:
        self.reply, self.sender, self.flags = reply, sender, flags
        self.sent = b""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def settimeout(self, value: float) -> None:
        assert value == 2

    def bind(self, address: tuple[int, int]) -> None:
        assert address == (0, 0)

    def getsockname(self) -> tuple[int, int]:
        return 1234, 0

    def sendto(self, raw: bytes, address: tuple[int, int]) -> int:
        assert address == (0, 0)
        self.sent = raw
        return len(raw)

    def recvmsg(self, size: int) -> tuple[bytes, list[Any], int, tuple[int, int]]:
        assert size == 4096
        return self.reply, [], self.flags, self.sender


def generation(monkeypatch: pytest.MonkeyPatch, reply: ReplySocket) -> int:
    from paper_radar.live_evidence.nft_generation import nft_generation

    monkeypatch.setattr(os, "urandom", lambda count: b"\x01\x00\x00\x00")

    def connect(family: int, kind: int, protocol: int) -> ReplySocket:
        assert (family, kind, protocol) == (socket.AF_NETLINK, socket.SOCK_RAW, 12)
        return reply

    monkeypatch.setattr(socket, "socket", connect)
    return nft_generation()


def test_fixed_getgen_reads_u32_generation_and_exact_kernel_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = ReplySocket()
    assert generation(monkeypatch, reply) == 42
    assert reply.sent == bytes.fromhex("14000000100a010001000000d204000000000000")


@pytest.mark.parametrize(
    "change",
    [
        "short",
        "length",
        "type",
        "multi",
        "sequence",
        "port",
        "family",
        "version",
        "resource",
        "duplicate",
        "unknown",
        "flagged",
        "short_attr",
        "missing_attr",
        "zero_gen",
        "name_nul",
        "trailing",
        "truncated",
        "source",
        "groups",
        "timeout",
    ],
)
def test_malformed_or_unavailable_generation_never_becomes_a_snapshot(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    raw = bytearray(GOOD)

    def word(offset: int, value: int, format: str) -> None:
        struct.pack_into(format, raw, offset, value)

    if change == "short":
        raw = raw[:19]
    elif change in {"length", "type", "multi", "sequence", "port", "resource"}:
        offset, value, format = {
            "length": (0, 44, "=I"),
            "type": (4, 2, "=H"),
            "multi": (6, 2, "=H"),
            "sequence": (8, 2, "=I"),
            "port": (12, 0, "=I"),
            "resource": (18, 41, "!H"),
        }[change]
        word(offset, value, format)
    elif change in {"family", "version"}:
        raw[16 if change == "family" else 17] = 1
    elif change == "duplicate":
        raw.extend(raw[20:28])
        word(0, len(raw), "=I")
    elif change in {"unknown", "flagged", "short_attr"}:
        word(
            22 if change != "short_attr" else 20,
            {"unknown": 4, "flagged": 0x4001, "short_attr": 3}[change],
            "=H",
        )
    elif change == "missing_attr":
        del raw[28:36]
        word(0, len(raw), "=I")
    elif change == "zero_gen":
        word(24, 0, "!I")
        word(18, 0, "!H")
    elif change == "name_nul":
        raw[41] = 0
    elif change == "trailing":
        raw.extend(b"\0" * 4)
        word(0, len(raw), "=I")
    reply = ReplySocket(
        bytes(raw),
        sender=(1, 0) if change == "source" else (0, 0),
        flags=socket.MSG_TRUNC if change == "truncated" else 0,
    )
    if change == "groups":
        monkeypatch.setattr(reply, "getsockname", lambda: (1234, 1))
    if change == "timeout":

        def timeout(size: int) -> tuple[bytes, list[Any], int, tuple[int, int]]:
            raise TimeoutError

        monkeypatch.setattr(reply, "recvmsg", timeout)
    with pytest.raises(ValueError, match=r"^nft_generation_unavailable$"):
        generation(monkeypatch, reply)


def test_real_uid1000_eperm_packet_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from paper_radar.live_evidence.nft_generation import nft_generation

    # Exact read-only probe bytes from 2026-11-11; process exit 0 was only capture.
    reply = ReplySocket(
        bytes.fromhex(
            "2800000002000000015071174e040900ffffffff"
            "14000000100a0100015071174e04090000000000"
        )
    )
    monkeypatch.setattr(reply, "getsockname", lambda: (590926, 0))
    monkeypatch.setattr(os, "urandom", lambda count: bytes.fromhex("01507117"))
    monkeypatch.setattr(socket, "socket", lambda *args: reply)
    with pytest.raises(ValueError, match=r"^nft_generation_unavailable$"):
        nft_generation()


@pytest.mark.parametrize("value", [65536, 0xFFFFFFFF])
def test_complete_u32_generation_is_not_the_u16_resource_only(
    monkeypatch: pytest.MonkeyPatch, value: int
) -> None:
    raw = bytearray(GOOD)
    struct.pack_into("!I", raw, 24, value)
    struct.pack_into("!H", raw, 18, value & 0xFFFF)
    assert generation(monkeypatch, ReplySocket(bytes(raw))) == value


@pytest.mark.parametrize("name", [b"\0", b"a" * 15 + b"\0", b"\xff\0"])
def test_kernel_process_name_is_opaque_bounded_bytes(
    monkeypatch: pytest.MonkeyPatch, name: bytes
) -> None:
    raw = bytearray(GOOD[:36])
    raw.extend(struct.pack("=HH", 4 + len(name), 3) + name)
    raw.extend(b"\0" * (-len(raw) % 4))
    struct.pack_into("=I", raw, 0, len(raw))
    assert generation(monkeypatch, ReplySocket(bytes(raw))) == 42
