"""独立进程显式 retry/回收;安全回执不包含自由审计文本。"""

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from paper_radar.papers import PaperError
from paper_radar.screening_tasks import ScreeningTasks, TaskError
from paper_radar.storage.errors import StorageError


def main() -> None:
    database, data_root, receipt_id, operation, instant, request_path = sys.argv[1:]
    now = datetime.fromisoformat(instant)
    service = ScreeningTasks(Path(database), Path(data_root), clock=lambda: now)
    try:
        if operation == "retry":
            result = asdict(service.retry(json.loads(Path(request_path).read_text())))
        elif operation == "reclaim":
            result = asdict(service.reclaim(receipt_id))
        else:
            raise ValueError("unsupported test operation")
    except (TaskError, PaperError, StorageError) as error:
        result = {"reason": error.reason}
        if isinstance(error, TaskError) and error.successor_task_id:
            result["successor_task_id"] = error.successor_task_id
    print(json.dumps(result))


if __name__ == "__main__":
    main()
