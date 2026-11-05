"""单次受限 worker 监管;不管理业务预算、根锁或总耗时。"""

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

from pydantic import ValidationError

from paper_radar.docling_execution.models import WorkerRequest, WorkerResponse

OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "CUDA_VISIBLE_DEVICES": "",
}
MAX_RESPONSE_BYTES = 128 * 1024 * 1024


class DoclingProcess:
    def __init__(self, *, command: tuple[str, ...] | None = None) -> None:
        # 可替换 seam 是整个外部进程,不替换内部 SDK 对象。
        self.command = command or (
            sys.executable,
            "-m",
            "paper_radar.docling_execution.worker",
        )

    def execute(self, request: WorkerRequest) -> WorkerResponse:
        response_path = Path(request.response_path)
        request_path = response_path.with_name("request.json")
        request_path.write_text(request.model_dump_json(), encoding="utf-8")
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "PYTHONPATH", "LANG", "LC_ALL", "LD_LIBRARY_PATH"}
        }
        environment.update(OFFLINE_ENV)
        environment.update(
            {
                "HOME": str(response_path.parent),
                "HF_HOME": str(response_path.parent / "hf"),
                "TMPDIR": str(response_path.parent),
                "OMP_NUM_THREADS": str(request.threads),
                "MKL_NUM_THREADS": str(request.threads),
                "OPENBLAS_NUM_THREADS": str(request.threads),
                "NUMEXPR_NUM_THREADS": str(request.threads),
                "OMP_THREAD_LIMIT": str(request.threads),
                "TOKENIZERS_PARALLELISM": "false",
            }
        )
        try:
            process = subprocess.Popen(
                [*self.command, str(request_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
                start_new_session=True,
            )
        except OSError:
            return WorkerResponse(failure="executor_error")
        peak = 0
        deadline = time.monotonic() + request.timeout_seconds
        response = WorkerResponse(failure="executor_error")
        try:
            while True:
                pid, status, usage = os.wait4(process.pid, os.WNOHANG)
                if pid:
                    process.returncode = os.waitstatus_to_exitcode(status)
                    peak = int(usage.ru_maxrss) * 1024
                    break
                if time.monotonic() >= deadline:
                    response = WorkerResponse(failure="timeout")
                    break
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
            if process.returncode == 0:
                if (
                    response_path.is_file()
                    and response_path.stat().st_size <= MAX_RESPONSE_BYTES
                ):
                    response = WorkerResponse.model_validate_json(
                        response_path.read_bytes()
                    )
            elif process.returncode == -signal.SIGXCPU:
                response = WorkerResponse(failure="resource_exhausted")
            # 单个 SIGKILL 无法证明 OOM,保持 executor_error。
        except (OSError, ValueError, ValidationError):
            response = WorkerResponse(failure="executor_error")
        finally:
            # 即使直接 worker 已退出,也回收仍在组内的后代。
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            if process.returncode is None:
                _, status, usage = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(status)
                peak = int(usage.ru_maxrss) * 1024
        return response.model_copy(update={"peak_memory_bytes": peak})
