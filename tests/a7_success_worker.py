"""独立进程提交原始成功候选;领取能力仅由私有文件读取。"""

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from paper_radar.papers import PaperError
from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate, TaskError
from paper_radar.storage.errors import StorageError
from tests.a7_attempts_worker import load_claim

RAW_ONE = (
    b'{"boundary":"in_scope","reason_zh":"Atmospheric prediction is directly studied."}'
)
RAW_TWO = (
    b'{"boundary":"out_of_scope",'
    b'"reason_zh":"The work concerns unrelated crystal synthesis."}'
)


def main() -> None:
    database, data_root, receipt_id, operation, instant, capability, variant = sys.argv[
        1:
    ]
    now = datetime.fromisoformat(instant)
    tasks = ScreeningTasks(Path(database), Path(data_root), clock=lambda: now)
    try:
        if operation == "submit":
            raw = RAW_ONE if variant == "one" else RAW_TWO
            receipt = tasks.submit(load_claim(Path(capability)), SuccessCandidate(raw))
            result = asdict(receipt)
            result["settled_at"] = receipt.settled_at.isoformat()
        elif operation == "reclaim":
            result = asdict(tasks.reclaim(receipt_id))
        else:
            raise ValueError("unsupported test operation")
    except (TaskError, PaperError, StorageError) as error:
        result = {"reason": error.reason}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
