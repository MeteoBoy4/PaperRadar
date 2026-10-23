"""新进程只消费档案库身份与请求;只输出安全回执或受控原因。"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from paper_radar.papers import PaperError
from paper_radar.screening_tasks import ScreeningTasks, TaskError
from paper_radar.storage.errors import StorageError


def main() -> None:
    tasks = ScreeningTasks(Path(sys.argv[1]))
    request = json.loads(sys.argv[2])
    try:
        receipt = tasks.register(request)
    except (TaskError, PaperError, StorageError) as error:
        print(json.dumps({"reason": error.reason}))
    else:
        print(json.dumps(asdict(receipt)))


if __name__ == "__main__":
    main()
