"""公共 API 建立失败终态及显式 retry 请求。"""

from paper_radar.screening_tasks import (
    FailureKind,
    FailureReport,
    RequestReceipt,
    ScreeningTasks,
)
from tests.a7_registration_support import Archive


def exhaust(service: ScreeningTasks, receipt: RequestReceipt) -> None:
    for _ in range(2):
        service.fail(
            service.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT)
        )


def retry_for(
    data: Archive, parent: RequestReceipt, **changes: object
) -> dict[str, object]:
    return {
        "paper_id": data.paper_id,
        "stage": parent.stage,
        "snapshot_id": data.snapshot_id,
        "parent_task_id": parent.task_id,
        "request_id": "retry-1",
        "reason": "显式重新处理",
        "actor": "测试研究者",
        **changes,
    }
