"""恢复消费者:请求只含受控引用与摘要哈希,不从测试工厂取得论文文本。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from typer.testing import CliRunner

from paper_radar.backup.restore import restore_backup
from paper_radar.cli import app
from paper_radar.papers import AbstractValue, PaperFacts, ScreeningMappingResult


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def mapping_summary(result: ScreeningMappingResult) -> dict[str, object]:
    stages: dict[str, object] = {}
    for name, stage in (("boundary", result.boundary), ("value", result.value)):
        stages[name] = (
            {
                "fingerprint": stage.value.fingerprint,
                "payload_sha256": hashlib.sha256(stage.value.payload_bytes).hexdigest(),
                "size": len(stage.value.payload_bytes),
            }
            if stage.value
            else {"reason": stage.reason}
        )
    return {
        "stages": stages,
        "evidence": digest(result.evidence.model_dump(mode="json", exclude={"doi"}))
        if result.evidence
        else None,
    }


def guard(roots: list[str]) -> dict[str, int]:
    forbidden = tuple(Path(root).resolve() for root in roots)
    counts: dict[str, int] = {}

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event not in {"open", "sqlite3.connect", "os.listdir", "os.scandir"}:
            return
        if not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        counts[event] = counts.get(event, 0) + 1
        raw = os.fsdecode(args[0])
        if raw.startswith("file:"):
            raw = unquote(urlsplit(raw).path)
        candidate = Path(os.path.abspath(raw))
        # Do not resolve here: resolving a denied path itself must not inspect it.
        if any(
            candidate == root or candidate.is_relative_to(root) for root in forbidden
        ):
            raise PermissionError("recovery source access denied")

    sys.addaudithook(audit)
    # Exercise all guards before the recovery operation, including SQLite URI/bytes.
    import sqlite3

    for root in forbidden:
        for kind in ("open", "listdir", "scandir", "sqlite"):
            try:
                if kind == "open":
                    with (root / "probe").open("rb"):
                        pass
                elif kind == "listdir":
                    os.listdir(os.fsencode(root))
                elif kind == "scandir":
                    with os.scandir(root):
                        pass
                else:
                    with sqlite3.connect(f"file:{root}/probe?mode=ro", uri=True):
                        pass
            except PermissionError:
                pass
            else:
                raise AssertionError("source guard was not active")
    counts.clear()
    return counts


def read(request: dict[str, Any]) -> dict[str, object]:
    root = Path(request["root"])
    service = PaperFacts(root / "database.sqlite3", root)
    traces = {}
    runner = CliRunner()
    for paper_id, expected in request["papers"].items():
        trace = service.trace(paper_id)
        assert digest(trace.model_dump(mode="json")) == expected["trace"]
        assert (
            digest(service.show(paper_id).model_dump(mode="json")) == expected["show"]
        )
        for command, model in (("show", trace.current), ("trace", trace)):
            query = runner.invoke(
                app,
                [
                    "paper",
                    command,
                    paper_id,
                    "--database",
                    str(service.database),
                    "--data-root",
                    str(root),
                    "--json",
                    "--show-abstract",
                ],
            )
            assert query.exit_code == 0, "restored CLI query failed"
            assert json.loads(query.stdout) == model.model_dump(mode="json")
            default = runner.invoke(
                app,
                ["paper", command, paper_id, "--database", str(service.database)],
            )
            assert default.exit_code == 0, "default restored CLI failed"
            for source in trace.observations:
                abstract = source.fields.get("abstract")
                if abstract and isinstance(abstract.value, AbstractValue):
                    assert abstract.value.text not in default.stdout
        traces[paper_id] = digest(trace.model_dump(mode="json"))
    for query in request["mappings"]:
        mapped = service.map_screening_inputs(**query["selector"])
        assert mapping_summary(mapped) == query["expected"], (
            "history reconstruction differs"
        )
    return {"traces": traces, "mappings": len(request["mappings"])}


def main() -> None:
    request = json.loads(sys.stdin.read())
    counts = guard(request["forbidden"])
    if request["mode"] == "restore":
        restored = restore_backup(Path(request["batch"]), Path(request["target"]))
        print(json.dumps({"manifest": restored.manifest_sha256, "io": counts}))
    else:
        result = read(request)
        result["io"] = counts
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
