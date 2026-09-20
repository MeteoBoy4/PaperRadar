"""冻结契约测试数据的独立规范 JSON 编码。"""

from __future__ import annotations

import json


def canonical_json_bytes(value: object) -> bytes:
    """按已发布文件契约编码测试数据。此函数不调用生产序列化实现。"""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
