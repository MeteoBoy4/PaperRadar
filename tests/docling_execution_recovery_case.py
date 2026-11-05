"""D1显式双环境工程回归:合成外部worker生产,基础环境异地恢复。"""

import importlib.abc
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any


def produce(root: Path) -> None:
    from paper_radar.backup import create_backup
    from tests.docling_executor_support import prepared_docling

    root.mkdir()
    expected = []
    for label, failure in [("success", None), ("failure", "executor_error")]:
        source = root / label
        saved, service, parser = prepared_docling(source, failure=failure)
        result = service.extract(
            saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
        )
        assert result.attempts[0].executor_audit
        batch = create_backup(
            saved.database, saved.data_root, root / (label + "-batches")
        )
        expected.append(
            {
                "label": label,
                "batch": str(batch.batch_dir),
                "fingerprint": result.fingerprint,
                "paper": saved.paper_id,
                "failure": failure,
                "audit": result.attempts[0].executor_audit.model_dump(mode="json"),
            }
        )
        source.rename(root / (label + "-unavailable"))
    (root / "expected.json").write_text(json.dumps(expected))
    print("synthetic worker backups prepared")


class DenySDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname.split(".")[0] in {
            "docling",
            "docling_core",
            "torch",
            "torchvision",
            "transformers",
            "docling_parse",
            "pypdfium2",
            "huggingface_hub",
        }:
            raise RuntimeError("SDK import forbidden")
        return None


def verify(root: Path) -> None:
    for distribution in ("docling-slim", "docling-core", "torch"):
        try:
            importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            raise AssertionError("必须使用真实无extra环境")
    sys.meta_path.insert(0, DenySDK())
    blocked = {
        root / "success",
        root / "failure",
        root / "success-unavailable",
        root / "failure-unavailable",
    }

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn")):
            raise RuntimeError("external execution forbidden")
        if (
            event in {"open", "os.listdir", "os.scandir", "sqlite3.connect"}
            and args
            and isinstance(args[0], str)
        ):
            path = Path(args[0].removeprefix("file:").split("?", 1)[0]).resolve()
            if any(path == p or p in path.parents for p in blocked):
                raise RuntimeError("original source forbidden")

    sys.addaudithook(guard)
    from paper_radar.backup import create_backup, restore_backup, verify_backup
    from paper_radar.body import BodyService
    from paper_radar.fulltext.artifacts import FulltextArtifacts

    for expected in json.loads((root / "expected.json").read_text()):
        verify_backup(Path(expected["batch"]))
        target = root / (expected["label"] + "-restored")
        restore_backup(Path(expected["batch"]), target)
        service = BodyService(target / "database.sqlite3", target)
        service.validate_all()
        result = service.extraction(expected["fingerprint"])
        assert result and result.remaining_attempts == 1 and len(result.attempts) == 1
        assert result.attempts[0].failure == expected["failure"]
        audit = result.attempts[0].executor_audit
        assert audit and audit.model_dump(mode="json") == expected["audit"]
        if expected["failure"] is None:
            assert result.artifact_id and result.identity
            loaded = FulltextArtifacts(service.store).load(
                result.artifact_id, expected_identity=result.identity
            )
            assert loaded.context.replay()[1].text == "Exact source α = 2."
        # 无extra可再次验证/备份;不回收失联、不解析、不重置预算。
        rebackup = create_backup(
            target / "database.sqlite3",
            target,
            root / (expected["label"] + "-rebackup"),
        )
        verify_backup(rebackup.batch_dir)
        assert service.extraction(expected["fingerprint"]) == result
    print("audited extraction recovered without extra, SDK or original roots")


if __name__ == "__main__":
    {"produce": produce, "verify": verify}[sys.argv[1]](Path(sys.argv[2]).resolve())
