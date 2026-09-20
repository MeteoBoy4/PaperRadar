"""冻结契约测试数据的独立规范 JSON 编码与只读断言。"""

from __future__ import annotations

import json
from pathlib import Path


def canonical_json_bytes(value: object) -> bytes:
    """按已发布文件契约编码测试数据。此函数不调用生产序列化实现。"""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def filesystem_fingerprint(root: Path) -> dict[str, tuple[int, int, bytes | None]]:
    """记录目录树中每个条目的 mtime、权限与内容。用于证明检查只读。

    目标不存在时返回空映射。因此也能证明失败路径没有创建目录。无法读取的
    文件只记录内容为 `None`。便于对比权限失败前后的状态。
    """
    fingerprint: dict[str, tuple[int, int, bytes | None]] = {}
    if not root.exists():
        return fingerprint
    for path in sorted(root.rglob("*")):
        stat = path.stat()
        content: bytes | None = None
        if path.is_file():
            try:
                content = path.read_bytes()
            except OSError:
                content = None
        fingerprint[str(path.relative_to(root))] = (
            stat.st_mtime_ns,
            stat.st_mode,
            content,
        )
    return fingerprint
