"""独立进程执行受控操作;能力仅经权限受限的测试文件交换。"""

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from paper_radar.papers import PaperError
from paper_radar.screening_tasks import ScreeningTasks, TaskError
from paper_radar.screening_tasks.attempt_models import Claim
from paper_radar.stage_inputs import StageInput
from paper_radar.storage.errors import StorageError
from tests.a3_process_support import checkpoint


def load_claim(path: Path) -> Claim:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Claim(
        **{
            **raw,
            "claimed_at": datetime.fromisoformat(raw["claimed_at"]),
            "expires_at": datetime.fromisoformat(raw["expires_at"]),
        }
    )


def save_claim(path: Path, claim: Claim) -> None:
    raw = asdict(claim)
    raw["claimed_at"] = claim.claimed_at.isoformat()
    raw["expires_at"] = claim.expires_at.isoformat()
    path.touch(mode=0o600)
    path.write_text(json.dumps(raw), encoding="utf-8")


def main() -> None:
    database, receipt_id, operation, instant, capability = sys.argv[1:]
    now = datetime.fromisoformat(instant)
    tasks = ScreeningTasks(Path(database), clock=lambda: now)
    try:
        result: dict[str, object]
        if operation == "claim":
            claim = tasks.claim(receipt_id)
            save_claim(Path(capability), claim)
            result = {"task_id": claim.task_id, "attempt_no": claim.attempt_no}
        elif operation == "renew":
            claim = load_claim(Path(capability))
            result = {"expires_at": tasks.renew(claim.renewal_handle).isoformat()}
        elif operation == "reclaim":
            result = asdict(tasks.reclaim(receipt_id))
        elif operation == "fail":
            from paper_radar.screening_tasks.attempt_models import (
                FailureKind,
                FailureReport,
            )

            claim = load_claim(Path(capability))
            failure = tasks.fail(claim, FailureReport(FailureKind.TIMEOUT))
            result = {"task_id": failure.task_id, "attempt_no": failure.attempt_no}
        elif operation == "run_once":
            from paper_radar.screening_tasks.attempt_models import (
                FailureKind,
                FailureReport,
            )

            def executor(
                stage_input: StageInput, correction: str | None, handle: str
            ) -> FailureReport:
                with Path(capability).open("a", encoding="utf-8") as marker:
                    marker.write("called\n")
                checkpoint()
                return FailureReport(FailureKind.TIMEOUT)

            failure = tasks.run_once(receipt_id, executor)
            result = {"task_id": failure.task_id, "attempt_no": failure.attempt_no}
        else:
            raise ValueError("unsupported test operation")
    except (TaskError, PaperError, StorageError) as error:
        result = {"reason": error.reason}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
