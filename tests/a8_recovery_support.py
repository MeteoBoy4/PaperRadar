"""RPC 恢复组合的外部会话故障与显式请求;不另建预算规则。"""

from typing import Any

from paper_radar.config import compile_config
from paper_radar.screening_tasks import RequestReceipt
from tests.a8_call_support import Archive
from tests.a8_rpc_support import FakeFactory


def fault_factory(kind: str) -> FakeFactory:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "new_session" and kind == "transport":
            raise BrokenPipeError("TRANSPORT_ERROR_SECRET")
        if name == "new_session" and kind == "environment":
            records[-1]["data"]["cancelled"] = True
        if name == "prompt":
            if kind == "interrupt":
                raise KeyboardInterrupt
            if kind == "timeout":
                return records[:1]
            if kind == "protocol":
                return [records[0], {"type": "queue_update"}]
        return records

    return FakeFactory(
        raw='{"boundary":"in_scope","reason_zh":"完整失败原文_SECRET","extra":true}',
        mutate=mutate,
    )


def retry_request(
    data: Archive, parent: RequestReceipt, **changes: object
) -> dict[str, object]:
    return {
        "paper_id": parent.paper_id,
        "stage": parent.stage,
        "snapshot_id": data.snapshot_id,
        "parent_task_id": parent.task_id,
        "request_id": "rpc-explicit-retry",
        "actor": "测试研究者",
        "reason": "显式重试 RPC 历史任务",
        **changes,
    }


def audit_upgrade(data: Archive, *, pi_version: str = "1.4.0") -> str:
    original = data.settings.parent / "adapters/pi-v1.yaml"
    newer = data.settings.parent / "adapters/pi-v2.yaml"
    text = original.read_text()
    old_pi = next(line for line in text.splitlines() if line.startswith("pi_version:"))
    newer.write_text(
        text.replace("version: pi-v1", "version: pi-v2")
        .replace(old_pi, f"pi_version: {pi_version}")
        .replace("transport-v1", "transport-v2")
    )
    data.settings.write_text(
        data.settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
    )
    return compile_config(data.settings, data.database).snapshot_id
