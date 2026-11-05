"""真实无SDK新进程恢复并仅查询;原根、网络和模型执行禁用。"""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


def run() -> None:
    batch, target, moved, expected_file = map(Path, sys.argv[1:5])
    expected = json.loads(expected_file.read_text())
    blocked = [Path(p).resolve() for p in sys.argv[5:]]

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == "import" and args[0].split(".")[0] in {
            "docling",
            "docling_core",
            "torch",
            "openai",
            "anthropic",
        }:
            raise AssertionError("sdk_model_import_forbidden")
        if event in {"socket.connect", "subprocess.Popen", "os.system"}:
            raise AssertionError("external_execution_forbidden")
        if (
            event not in {"open", "sqlite3.connect", "os.listdir", "os.scandir"}
            or not args
            or not isinstance(args[0], str | bytes)
        ):
            return
        value = args[0].decode() if isinstance(args[0], bytes) else args[0]
        path = Path(
            unquote(urlsplit(value).path) if value.startswith("file:") else value
        ).resolve()
        if any(path == root or root in path.parents for root in blocked):
            raise AssertionError("original_path_forbidden")
        if event == "sqlite3.connect" and expected.get("queries_started"):
            assert "mode=ro" in value

    sys.addaudithook(guard)
    for name in ("docling", "docling-core", "torch"):
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            raise AssertionError("requires_actual_no_extra")
    from paper_radar.backup import restore_backup
    from paper_radar.read_queries import ReadQueries
    from paper_radar.read_tasks import ReadTaskError, ReadTasks
    from tests.read_queries_support import query_projection

    restore_backup(batch, target)
    target.rename(moved)
    blocked.extend((target.resolve(), batch.resolve()))
    expected["queries_started"] = True

    def hashes() -> dict[str, str]:
        return {
            str(p.relative_to(moved)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in moved.rglob("*")
            if p.is_file()
        }

    before = hashes()
    query = ReadQueries(moved / "database.sqlite3", moved)
    actual = query_projection(query, expected["paper"], expected["snapshot"])
    assert actual == expected["projection"]
    view = query.analysis(expected["analysis"], snapshot_id=expected["snapshot"])
    assert (
        view.has_discards
        and view.config_status == "old"
        and view.body_status == "current"
    )
    assert not hasattr(view, "raw_candidate")
    assert query.evidence(view.analysis_id, "e000002")[0].text == "Exact source α = 2."
    try:
        query.analysis(view.analysis_id, ordinary=True)
    except ReadTaskError as error:
        assert error.reason == "ordinary_consumption_denied"
    else:
        raise AssertionError("ordinary_experiment")
    tasks = ReadTasks(moved / "database.sqlite3", moved)
    assert [
        [t.task_id, t.remaining_attempts, t.status]
        for t in tasks.history(expected["paper"])
    ] == expected["tasks"]
    assert hashes() == before
    print("read query recovered without SDK, models, writes or lease recovery")


if __name__ == "__main__":
    run()
