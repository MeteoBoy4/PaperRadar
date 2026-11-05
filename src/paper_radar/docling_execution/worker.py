"""先建立 OS 隔离,再延迟加载 SDK;原始异常/日志不回传。"""

import errno
import logging
import resource
import sys
from pathlib import Path

from paper_radar.body.models import ParserFailure
from paper_radar.docling_execution.models import WorkerRequest, WorkerResponse
from paper_radar.docling_execution.sandbox import restrict_worker


def main() -> None:
    request = WorkerRequest.model_validate_json(Path(sys.argv[1]).read_bytes())
    reserve = bytearray(1024 * 1024)
    logging.disable(logging.CRITICAL)
    try:
        restrict_worker(request.memory_limit_bytes)
        from paper_radar.docling_execution.sdk import convert_document

        response = convert_document(request)
    except MemoryError:
        del reserve
        response = WorkerResponse(failure="resource_exhausted")
    except ParserFailure as error:
        response = WorkerResponse(failure=error.failure.value)  # type: ignore[arg-type]
    except OSError as error:
        response = WorkerResponse(
            failure="resource_exhausted"
            if error.errno == errno.ENOMEM
            else "executor_error"
        )
    except Exception:
        # import/native ABI/network/model/未知异常均为 executor_error,不泄露原错误。
        response = WorkerResponse(failure="executor_error")
    response = response.model_copy(
        update={
            "peak_memory_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            * 1024
        }
    )
    Path(request.response_path).write_text(response.model_dump_json(), encoding="utf-8")


if __name__ == "__main__":
    main()
