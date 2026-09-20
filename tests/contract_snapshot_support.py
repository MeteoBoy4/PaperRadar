"""冻结契约测试数据的独立规范 JSON 编码与只读断言。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_json_bytes(value: object) -> bytes:
    """按已发布文件契约编码测试数据。此函数不调用生产序列化实现。"""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def install_self_consistent_schema(snapshot_dir: Path, payload: bytes) -> None:
    """写入 schema 并让清单哈希与其自洽。使判定只由契约规则决定。"""
    (snapshot_dir / "schema.json").write_bytes(payload)
    manifest = json.loads((snapshot_dir / "manifest.json").read_bytes())
    manifest["schema_sha256"] = hashlib.sha256(payload).hexdigest()
    (snapshot_dir / "manifest.json").write_bytes(canonical_json_bytes(manifest))


def self_consistent_huge_integer_schema() -> bytes:
    """含 5000 位整数且自带权威身份的规范 schema。"""
    return (
        b'{\n  "x": ' + b"1" * 5000 + b",\n"
        b'  "x-paper-radar-contract": {\n'
        b'    "name": "boundary",\n'
        b'    "version": "v1"\n'
        b"  }\n"
        b"}\n"
    )


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
