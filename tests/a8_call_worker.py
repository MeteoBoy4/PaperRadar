"""跨进程请求身份核对。只输出固定摘要。"""

import hashlib
import sys
from pathlib import Path

from paper_radar.llm import render_request
from paper_radar.screening_tasks import ScreeningTasks
from tests.a8_call_support import prepare_call

if __name__ == "__main__":
    description = prepare_call(ScreeningTasks(Path(sys.argv[1])), sys.argv[2])
    print(hashlib.sha256(render_request(description)).hexdigest())
