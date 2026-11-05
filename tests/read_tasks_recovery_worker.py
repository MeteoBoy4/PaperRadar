"""Read异地基础环境恢复:禁止原根、模型及网络,核验完整历史只读。"""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from paper_radar.backup.manifest import BackupManifest


def run() -> None:
    batch, target, moved, expected_path = map(Path, sys.argv[1:5])
    expected = json.loads(expected_path.read_text())
    blocked = [Path(p).resolve() for p in sys.argv[5:]]

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event in {"socket.connect", "subprocess.Popen", "os.system"}:
            raise RuntimeError("external_execution_forbidden")
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
            raise RuntimeError("original_path_forbidden")

    sys.addaudithook(guard)
    for root in blocked:
        try:
            (root / "probe").read_bytes()
        except RuntimeError as error:
            assert str(error) == "original_path_forbidden"
        else:
            raise AssertionError("guard_missing")
    for name in ("docling", "docling-core", "torch"):
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            raise AssertionError("requires_no_extra")
    from paper_radar.backup import restore_backup, verify_contents
    from paper_radar.read_tasks import ReadTaskError, ReadTasks

    restore_backup(batch, target)
    target.rename(moved)
    blocked.extend([target.resolve(), batch.resolve()])
    before = {
        str(p.relative_to(moved)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in moved.rglob("*")
        if p.is_file()
    }
    service = ReadTasks(moved / "database.sqlite3", moved)
    service.validate_all()
    history = service.history(expected["paper"])
    assert [
        [t.generation, t.remaining_attempts, t.status] for t in history
    ] == expected["history"]
    analysis = service.analysis(expected["analysis"])
    assert analysis.raw_candidate.hex() == expected["candidate"]
    assert analysis.discards == tuple(expected["discards"])
    assert analysis.executor_kind == "test" and analysis.root_purpose == "experiment"
    assert (
        service.evidence(analysis.analysis_id, "e000002")[0].text
        == "Exact source α = 2."
    )
    try:
        service.analysis(analysis.analysis_id, ordinary=True)
    except ReadTaskError as error:
        assert error.reason == "ordinary_consumption_denied"
    else:
        raise AssertionError("ordinary_experiment")
    verify_contents(moved, restore_manifest(moved))
    after = {
        str(p.relative_to(moved)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in moved.rglob("*")
        if p.is_file()
    }
    assert before == after
    print("read recovered without extra, model, original roots or state changes")


def restore_manifest(root: Path) -> BackupManifest:
    from paper_radar.backup.manifest import parse_manifest

    return parse_manifest((root / "manifest.json").read_bytes())


if __name__ == "__main__":
    run()
