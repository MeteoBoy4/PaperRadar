"""有界 LF 解帧,只校验外层 JSON,不认识业务字段。"""

import json
import math
from typing import Any

from paper_radar.llm.rpc_types import MAX_FRAME_BYTES, RpcProblem, RpcReason


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RpcProblem(RpcReason.DUPLICATE_KEY)
        result[key] = value
    return result


def _nonfinite(_value: str) -> None:
    raise RpcProblem(RpcReason.NON_FINITE)


def _float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise RpcProblem(RpcReason.NON_FINITE)
    return parsed


class FrameDecoder:
    def __init__(self) -> None:
        self._tail = bytearray()

    @property
    def has_tail(self) -> bool:
        return bool(self._tail)

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        records = []
        for index, piece in enumerate(chunk.split(b"\n")):
            if index:
                records.append(self._record())
            self._tail.extend(piece)
            if len(self._tail) > MAX_FRAME_BYTES:
                raise RpcProblem(RpcReason.FRAME_LIMIT)
        return records

    def _record(self) -> dict[str, Any]:
        raw = bytes(self._tail)
        self._tail.clear()
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise RpcProblem(RpcReason.INVALID_UTF8) from None
        try:
            value = json.loads(
                text,
                object_pairs_hook=_pairs,
                parse_constant=_nonfinite,
                parse_float=_float,
            )
        except (ValueError, RecursionError):
            raise RpcProblem(RpcReason.INVALID_JSON) from None
        if type(value) is not dict:
            raise RpcProblem(RpcReason.NON_OBJECT)
        return value

    def finish(self) -> None:
        if self._tail:
            raise RpcProblem(RpcReason.PARTIAL_FRAME)


def command_frame(command_id: str, name: str, **fields: object) -> bytes:
    try:
        return (
            json.dumps(
                {"id": command_id, "type": name, **fields},
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (UnicodeError, ValueError, TypeError):
        raise RpcProblem(RpcReason.INVALID_DESCRIPTION) from None
