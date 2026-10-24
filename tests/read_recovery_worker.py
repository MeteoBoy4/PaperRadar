"""只从恢复库/响应及固定常量回放 Read;不恢复正文上下文。"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from paper_radar.backup import restore_backup, verify_contents
from tests.backup_support import tree
from tests.read_recovery_support import assert_restored_policy_rejections, recovery_view


def guard(blocked: list[Path], reads: set[Path]) -> None:
    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event in {"subprocess.Popen", "os.system", "socket.connect"}:
            raise RuntimeError("external_execution_forbidden")
        if event not in {"open", "sqlite3.connect", "os.listdir", "os.scandir"}:
            return
        if not args or not isinstance(args[0], str | bytes):
            return
        raw = args[0].decode() if isinstance(args[0], bytes) else args[0]
        parsed = unquote(urlsplit(raw).path) if raw.startswith("file:") else raw
        path = Path(parsed).resolve()
        if any(path == base or base in path.parents for base in blocked):
            raise RuntimeError("original_directory_forbidden")
        if event in {"open", "sqlite3.connect"}:
            reads.add(path)

    sys.addaudithook(audit)
    assert_blocked(blocked)


def assert_blocked(blocked: list[Path]) -> None:
    for base in blocked:
        try:
            sqlite3.connect(f"{(base / 'probe').as_uri()}?mode=ro", uri=True)
        except RuntimeError as error:
            assert str(error) == "original_directory_forbidden"
        else:
            raise AssertionError("original_path_not_blocked")


def run() -> None:
    batch, target, moved, expected_path = map(Path, sys.argv[1:5])
    expected = json.loads(expected_path.read_text())
    blocked = [Path(value).resolve() for value in sys.argv[5:]]
    reads: set[Path] = set()
    guard(blocked, reads)
    restored = restore_backup(batch, target)
    assert restored.target_dir == target.resolve()
    before = tree(target)
    assert (
        recovery_view(target / "database.sqlite3", target, expected["artifacts"])
        == expected["view"]
    )
    assert tree(target) == before
    target.rename(moved)
    blocked.extend([batch.resolve(), target.resolve()])
    assert_blocked(blocked)
    reads.clear()
    database = moved / "database.sqlite3"
    assert database.resolve().is_relative_to(moved.resolve())
    assert recovery_view(database, moved, expected["artifacts"]) == expected["view"]
    assert_restored_policy_rejections(database, moved, expected["artifacts"])
    verify_contents(moved, restored.manifest)
    assert tree(moved) == before
    assert database.read_bytes()[18:20] == b"\x01\x01"
    assert database.resolve() in reads
    blob_reads = [path for path in reads if "blobs" in path.parts]
    assert blob_reads and all(
        path.is_relative_to(moved.resolve()) for path in blob_reads
    )
    assert not any(
        name.startswith(("paper_radar.llm", "docling")) for name in sys.modules
    )
    print(
        json.dumps(
            {
                "cases": 4,
                "snapshots": 2,
                "original_paths_blocked": True,
                "read_only": True,
                "relocated": True,
                "no_business_facts": True,
                "restored_policy_rejections": True,
            }
        )
    )


if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("read_recovery_failed")
        raise SystemExit(1) from None
