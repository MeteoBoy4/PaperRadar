"""最终验收结论的不可覆盖原子发布; 运行中证据更新不使用此入口。"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any


def publish_conclusion(
    output_dir: Path, run_id: str, suffix: str, conclusion: dict[str, Any]
) -> Path:
    """按历史 JSON 字节规则写出新结论; 目标存在或写入失败时不覆盖。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}{suffix}"
    temporary = output_dir / f".{run_id}.{uuid.uuid4().hex}.tmp"
    payload = (
        json.dumps(conclusion, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
