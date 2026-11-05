"""Body 仅凭恢复后的业务库和持久成员回放;不接收内存上下文。"""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


def view(database: Path, root: Path, paper_id: str, fingerprint: str) -> dict[str, Any]:
    from paper_radar.body import BodyService
    from paper_radar.fulltext.artifacts import FulltextArtifacts

    service = BodyService(database, root)
    service.validate_all()
    extracted = service.extraction(fingerprint)
    assert extracted and extracted.artifact_id and extracted.identity
    loaded = FulltextArtifacts(service.store).load(
        extracted.artifact_id, expected_identity=extracted.identity
    )
    facts = service.facts(paper_id, identity=extracted.identity)
    return {
        "root": [facts.root.root_id, facts.root.purpose],
        "pdfs": [p.attachment_id for p in service.pdfs(paper_id)],
        "decisions": [d.fact.reference for d in service.decisions(paper_id)],
        "samples": [s.sample_id for s in service.samples(paper_id)],
        "attempts": [[a.ordinal, a.failure, a.artifact_id] for a in extracted.attempts],
        "quality": [extracted.quality.basis, extracted.quality.failure],
        "reasons": list(facts.reasons),
        "ordinary_reasons": list(
            service.facts(paper_id, identity=extracted.identity, ordinary=True).reasons
        ),
        "evidence": [p.text for p in loaded.context.replay()],
    }


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
            raise AssertionError("unguarded original")
    # 这是真实基础环境,不用已安装 SDK 的禁导入替代无 extra 证明。
    for name in ("docling", "docling-core", "torch"):
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
        else:
            raise AssertionError("requires actual no-extra environment")
    from paper_radar.backup import restore_backup, verify_contents

    restored = restore_backup(batch, target)
    assert (
        view(
            target / "database.sqlite3",
            target,
            expected["paper"],
            expected["fingerprint"],
        )
        == expected["view"]
    )
    target.rename(moved)
    blocked.extend([target.resolve(), batch.resolve()])
    before = {
        str(p.relative_to(moved)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in moved.rglob("*")
        if p.is_file()
    }
    assert (
        view(
            moved / "database.sqlite3",
            moved,
            expected["paper"],
            expected["fingerprint"],
        )
        == expected["view"]
    )
    verify_contents(moved, restored.manifest)
    after = {
        str(p.relative_to(moved)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in moved.rglob("*")
        if p.is_file()
    }
    assert before == after
    assert not (moved / ".body-docling.lock").exists()
    assert not any(
        n.split(".")[0] in {"docling", "docling_core", "torch", "transformers"}
        for n in sys.modules
    )
    print("body recovered without SDK or original roots")


if __name__ == "__main__":
    run()
