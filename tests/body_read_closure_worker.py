"""两个真实base冷进程的verify/restore及搬迁只读回查。"""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


def run() -> None:
    phase = sys.argv[1]
    batch, target, moved, expected_path = map(Path, sys.argv[2:6])
    expected = json.loads(expected_path.read_text())
    blocked = [Path(p).resolve() for p in sys.argv[6:]]
    if phase == "query":
        blocked += [batch.resolve(), target.resolve()]
    readonly = False
    probes: list[str] = []

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == "import" and args[0].split(".")[0] in {
            "docling",
            "docling_core",
            "torch",
            "transformers",
            "openai",
            "anthropic",
        }:
            raise AssertionError("sdk_model_import_forbidden")
        if event in {"socket.connect", "socket.bind", "subprocess.Popen", "os.system"}:
            raise AssertionError("network_model_execution_forbidden")
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
        if readonly and event == "sqlite3.connect":
            assert "mode=ro" in value
        if readonly and event == "open" and len(args) > 1 and isinstance(args[1], str):
            assert not any(c in args[1] for c in "wax+")

    sys.addaudithook(guard)
    for root in blocked:
        try:
            (root / "probe").read_bytes()
        except AssertionError as error:
            assert str(error) == "original_path_forbidden"
            probes.append(str(root))
        else:
            raise AssertionError("original_guard_not_active")
    for name in ("docling-slim", "docling-core", "torch", "transformers"):
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            raise AssertionError("requires_actual_no_extra")
    from paper_radar.backup import restore_backup, verify_backup, verify_contents
    from tests.body_read_closure_support import projection

    if phase == "restore":
        verified = verify_backup(batch)
        restored = restore_backup(batch, target)
        assert restored.manifest == verified.manifest
        verify_contents(target, restored.manifest)
        target.rename(moved)
        assert not (moved / ".body-docling.lock").exists()
        assert not (moved / ".body-read.lock").exists()
    else:
        readonly = True

        def hashes() -> dict[str, str]:
            return {
                str(p.relative_to(moved)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in moved.rglob("*")
                if p.is_file()
            }

        before = hashes()
        actual = projection(
            moved / "database.sqlite3", moved, expected["paper"], expected["snapshot"]
        )
        assert actual == expected["projection"]
        assert hashes() == before
        assert not any(
            name.split(".")[0] in {"docling", "docling_core", "torch", "transformers"}
            for name in sys.modules
        )
    print(
        json.dumps(
            {
                "phase": phase,
                "guard_probes": len(probes),
                "sdk_imported": False,
                "passed": True,
            }
        )
    )


if __name__ == "__main__":
    run()
