"""备份前捕获公共工作流投影;不删除旧 trace 字段或读取恢复后输出。"""

from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from paper_radar.paper_trace import query_paper_trace


def workflow_snapshot(database: Path, data_root: Path, paper_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = TypeAdapter(dict[str, Any]).dump_python(
        query_paper_trace(database, data_root, paper_id).safe_payload(), mode="json"
    )
    return payload
