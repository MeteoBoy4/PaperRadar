"""仅合成 HTTP/Pi、parser 与 cgroup 资源源。"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import Result

from paper_radar.config import compile_config
from paper_radar.docling_execution.models import WorkerRequest, WorkerResponse
from paper_radar.experiment.root import ExperimentRoot
from tests.config_extraction_support import EXTRACTION_YAML
from tests.experiment_screen_support import ScreenFixture, screen_fixture
from tests.test_experiment_accept_cli import accept
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_pdf_cli import attach
from tests.test_fulltext_artifacts import document


@dataclass
class ExtractFixture:
    prepared: ScreenFixture
    models: Path
    proc: Path
    group: Path
    meminfo: Path
    snapshot: str

    @property
    def root(self) -> ExperimentRoot:
        return ExperimentRoot(self.prepared.root)

    def extract(self) -> Result:
        return invoke(
            "extract",
            self.prepared.paper_id,
            "--root",
            str(self.prepared.root),
            "--snapshot",
            self.snapshot,
            "--model-root",
            str(self.models),
            "--timeout-seconds",
            "300",
            "--threads",
            "4",
        )


def extract_fixture(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ExtractFixture:
    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    assert attach(prepared, tmp_path).exit_code == 0
    config = prepared.root / "config"
    (config / "extraction").mkdir()
    extraction = yaml.safe_load(EXTRACTION_YAML)
    models = tmp_path / "models"
    models.mkdir()
    repos = {
        "layout": "docling-project/docling-layout-egret-medium",
        "table": "docling-project/docling-models",
        "formula": "docling-project/CodeFormulaV2",
    }
    deployment = []
    for stage, model in extraction["models"].items():
        for member in model["files"]:
            raw = f"synthetic {stage} {member['path']}".encode()
            member["sha256"] = hashlib.sha256(raw).hexdigest()
            path = models / repos[stage].replace("/", "--") / member["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        deployment.append(dict(repo_id=repos[stage], **model))
    (models / "deployment.json").write_text(json.dumps(dict(models=deployment)))
    (config / "extraction/extraction-v1.yaml").write_text(yaml.safe_dump(extraction))
    settings = config / "settings.yaml"
    settings.write_text(settings.read_text() + "\nextraction: extraction-v1\n")
    snapshot = compile_config(
        settings, prepared.root / "paper-radar.sqlite3"
    ).snapshot_id
    proc = tmp_path / "self-cgroup"
    proc.write_text("0::/user/synthetic\n")
    mount = tmp_path / "cgroup"
    group = mount / "user/synthetic"
    group.mkdir(parents=True)
    (mount / "cgroup.controllers").write_text("memory\n")
    for name, value in {
        "memory.max": "8589934592",
        "memory.swap.max": "0",
        "memory.peak": "123456789",
    }.items():
        (group / name).write_text(value)
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable: 1 kB\n")
    from paper_radar.experiment import extraction as execution

    monkeypatch.setattr(
        execution, "RESOURCE_PATHS", execution.ResourcePaths(proc, mount, meminfo, None)
    )
    import os

    monkeypatch.setattr(
        os,
        "statvfs",
        lambda _: SimpleNamespace(f_bavail=100000, f_frsize=4096),
    )
    return ExtractFixture(prepared, models, proc, group, meminfo, snapshot)


def executor(
    monkeypatch: pytest.MonkeyPatch,
    response: WorkerResponse | None = None,
    *,
    on_probe: Callable[[], None] | None = None,
) -> list[WorkerRequest]:
    from paper_radar import docling_executor

    requests: list[WorkerRequest] = []

    class Executor:
        def execute(self, request: WorkerRequest) -> WorkerResponse:
            requests.append(request)
            return response or WorkerResponse(
                document=document(),
                document_json='{"synthetic":true}',
                peak_memory_bytes=4096,
            )

    def probe(*args: object, **kwargs: object) -> SimpleNamespace:
        if on_probe:
            on_probe()
        return SimpleNamespace(passed=True)

    monkeypatch.setattr(docling_executor, "DoclingProcess", Executor)
    monkeypatch.setattr(docling_executor, "probe_docling_runtime", probe)
    return requests
