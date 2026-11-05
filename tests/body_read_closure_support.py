"""公共消费者组装;复用外部Pi进程/准入工程替身,不提供生产准入。"""

from pathlib import Path
from typing import Any

import pytest

from paper_radar.body import BodyService
from paper_radar.read_execution import ReadExecution
from paper_radar.read_tasks import ReadTask
from tests.read_execution_support import allow_engineering_path, setup


def closure(
    root: Path, monkeypatch: pytest.MonkeyPatch, *, mode: str = "normal"
) -> tuple[ReadExecution, ReadTask, BodyService]:
    service, task, _ = setup(root, monkeypatch, mode=mode)
    allow_engineering_path(monkeypatch)
    return service, task, BodyService(service.database, service.data_root)


def projection(database: Path, root: Path, paper: str, snapshot: str) -> dict[str, Any]:
    """只用公开历史读取口保存业务与字节,不复制接收/资格算法。"""
    import json
    from dataclasses import asdict

    from paper_radar.config import list_config_snapshots, load_config_snapshot
    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.pi_supply import activation_history
    from paper_radar.read_queries import ReadQueries
    from paper_radar.read_tasks import ReadTaskError, ReadTasks
    from paper_radar.storage.artifacts import ArtifactStore
    from tests.read_queries_support import query_projection

    body = BodyService(database, root)
    tasks = ReadTasks(database, root)
    store = ArtifactStore(database, root)
    query = ReadQueries(database, root)
    analyses = tasks.analyses(paper)
    assert analyses
    artifacts = {
        record.artifact_id: {
            "kind": record.kind,
            "members": {
                role: raw.hex()
                for role, raw in store.read_artifact(record.artifact_id).items()
            },
        }
        for record in store.list_artifacts()
    }
    for analysis in analyses:
        assert (
            query.evidence(analysis.analysis_id, "e000002")[0].text
            == "Exact source α = 2."
        )
        with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
            query.analysis(analysis.analysis_id, ordinary=True)
    configs = list_config_snapshots(database)
    extractions = []
    for a in analyses:
        extracted = body.extraction(a.identity.extraction_fingerprint)
        assert extracted is not None
        extractions.append(asdict(extracted))
    result = {
        "root": asdict(body.root()),
        "pdfs": [asdict(p) for p in body.pdfs(paper)],
        "samples": [asdict(s) for s in body.samples(paper)],
        "decisions": [asdict(d) for d in body.decisions(paper)],
        "extractions": extractions,
        "analyses": [asdict(a) for a in analyses],
        "tasks": [asdict(t) for t in tasks.history(paper)],
        "budgets": [
            [t.task_id, t.status, t.remaining_attempts] for t in tasks.history(paper)
        ],
        "metadata": [
            m.model_dump(mode="json")
            for m in JGRMetadata(database, root).requests(paper)
        ],
        "config_ids": [c.snapshot_id for c in configs],
        "config_payloads": [
            [c.snapshot_id, load_config_snapshot(database, c.snapshot_id).payload_json]
            for c in configs
        ],
        "activations": [asdict(a) for a in activation_history(database)],
        "artifacts": artifacts,
        "queries": query_projection(query, paper, snapshot),
    }
    # JSON是树外进程传输格式,不成为产品Schema或测试预期算法。
    projected: dict[str, Any] = json.loads(
        json.dumps(
            result, default=lambda x: x.hex() if isinstance(x, bytes) else str(x)
        )
    )
    return projected
