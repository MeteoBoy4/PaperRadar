"""paper retry 规范请求的冷恢复,只查询不执行。"""

import hashlib
import importlib.abc
import json
import sys
from pathlib import Path


class NoRuntime(importlib.abc.MetaPathFinder):
    def find_spec(
        self, fullname: str, path: object = None, target: object = None
    ) -> None:
        if fullname.startswith(
            ("paper_radar.read_execution", "paper_radar.pi_execution", "docling")
        ):
            raise AssertionError("execution runtime forbidden")


def main() -> None:
    root = Path(sys.argv[1])
    sys.meta_path.insert(0, NoRuntime())

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event.startswith(("socket.", "subprocess.")):
            raise AssertionError("external IO forbidden")

    sys.addaudithook(audit)
    from paper_radar.experiment.reading import registration_receipt, task_payload
    from paper_radar.experiment.validation import validate_all
    from paper_radar.read_tasks import ReadTasks

    def hashes() -> dict[str, str]:
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }

    before = hashes()
    tasks = ReadTasks(root / "database.sqlite3", root)
    tasks.validate_all()
    validate_all(root / "database.sqlite3", root)
    replayed = tasks.replay_retry_paper(
        sys.argv[2],
        snapshot_id=sys.argv[3],
        request_id="cold-paper-retry",
        reason="owner retries",
        actor="owner",
    )
    assert (
        replayed is not None and replayed.status == "ready" and replayed.attempts == ()
    )
    result = dict(
        receipt=registration_receipt(tasks, "cold-paper-retry"),
        tasks=[task_payload(t) for t in tasks.history(sys.argv[2])],
    )
    assert hashes() == before
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
