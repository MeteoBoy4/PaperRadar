"""固定只读 nft GETGEN;完整 generation 包络未知即拒绝。

Linux UAPI nf_tables.h/nfnetlink.h; nf_tables_api.c nf_tables_fill_gen_info。
只请求 GETGEN,不订阅、不修改规则,不提供通用 Netlink 接口。
"""

import os
import socket
import struct


def nft_generation() -> int:
    """返回内核完整 u32 genid;错误、截断、未知字段及非内核来源均拒绝。"""
    try:
        with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 12) as channel:
            channel.settimeout(2)
            channel.bind((0, 0))
            port, groups = channel.getsockname()
            if type(port) is not int or port <= 0 or groups != 0:
                raise ValueError("nft_generation_unavailable")
            sequence = struct.unpack("=I", os.urandom(4))[0] or 1
            # NFTABLES subsystem 10, GETGEN 16, REQUEST; nfgen family/version/res=0.
            request = struct.pack("=IHHII", 20, 0x0A10, 1, sequence, port) + b"\0" * 4
            if channel.sendto(request, (0, 0)) != len(request):
                raise ValueError("nft_generation_unavailable")
            raw, ancillary, flags, sender = channel.recvmsg(4096)
        if ancillary or flags != 0 or sender != (0, 0) or len(raw) < 20:
            raise ValueError("nft_generation_unavailable")
        length, kind, flags, actual_sequence, actual_port = struct.unpack_from(
            "=IHHII", raw
        )
        # Kernel unicast hdr pid is our socket port; recvmsg sender must be kernel 0.
        if (length, kind, flags, actual_sequence, actual_port) != (
            len(raw),
            0x0A0F,
            0,
            sequence,
            port,
        ):
            raise ValueError("nft_generation_unavailable")
        family, version, resource = struct.unpack_from("!BBH", raw, 16)
        if family != 0 or version != 0:
            raise ValueError("nft_generation_unavailable")
        attributes: dict[int, bytes] = {}
        offset = 20
        while offset < len(raw):
            if offset + 4 > len(raw):
                raise ValueError("nft_generation_unavailable")
            size, key = struct.unpack_from("=HH", raw, offset)
            aligned = (size + 3) & ~3
            if (
                size < 4
                or offset + aligned > len(raw)
                or key not in {1, 2, 3}
                or key in attributes
                or any(raw[offset + size : offset + aligned])
            ):
                raise ValueError("nft_generation_unavailable")
            attributes[key] = raw[offset + 4 : offset + size]
            offset += aligned
        if (
            set(attributes) != {1, 2, 3}
            or len(attributes[1]) != 4
            or len(attributes[2]) != 4
            or not 1 <= len(attributes[3]) <= 16
            or not attributes[3].endswith(b"\0")
            or b"\0" in attributes[3][:-1]
        ):
            raise ValueError("nft_generation_unavailable")
        generation: int = struct.unpack("!I", attributes[1])[0]
        process = struct.unpack("!I", attributes[2])[0]
        if generation == 0 or process == 0 or resource != generation & 0xFFFF:
            raise ValueError("nft_generation_unavailable")
        return generation
    except (OSError, ValueError, struct.error):
        raise ValueError("nft_generation_unavailable") from None
