"""合成 Pi RPC、HTTP、parser;授权与六项核查走真实 CLI。"""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from paper_radar.config import compile_config
from paper_radar.contracts import export_frozen_contract
from tests.experiment_layout_support import LayoutFixture, layout_fixture
from tests.pi_execution_support import PeerRun
from tests.test_experiment_candidates_cli import FeedFixture, invoke


@dataclass
class ReadFixture:
    layout: LayoutFixture
    snapshot: str

    def read(
        self, *, request: str | None = "read-1", task: str | None = None
    ) -> Result:
        fixture = self.layout.extraction.prepared
        return invoke(
            *self.layout.args("read"),
            "--snapshot",
            self.snapshot,
            "--credentials-dir",
            str(fixture.credentials),
            "--material-root",
            str(fixture.materials),
            "--install-root",
            str(fixture.install),
            *(["--request-id", request] if request is not None else []),
            *(["--task-id", task] if task is not None else []),
        )

    def query(self, command: str, *args: str) -> Result:
        return CliRunner().invoke(
            app,
            [
                "reading",
                command,
                *args,
                "--root",
                str(self.layout.extraction.root.root),
            ],
        )


def read_fixture(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "normal",
    reviewed: bool = True,
) -> ReadFixture:
    original = PeerRun.__init__
    # 改写外部合成对端的发布字节;安装/保护/认证/准入及 ReadExecution 均真实。
    output = {
        "output_language": "zh",
        "one_sentence_conclusion": "PRIVATE_READ_CONCLUSION",
        "research_question": "如何比较预测？",
        "methods_summary": "独立比较。",
        "data_summary": "公开数据。",
        "main_findings": [],
        "research_value": 3,
        "research_value_reason": {
            "statement": "有比较价值。",
            "evidence": [{"evidence_id": "e000002"}],
        },
        "reuse_feasibility": 3,
        "reuse_feasibility_reason": {
            "statement": "可以比较。",
            "evidence": [{"evidence_id": "e000002"}],
        },
        "required_adaptations": [],
        "reusable_points": [],
        "key_limitations": [],
        "open_questions": [],
        "value_types": ["method"],
        "why_it_matters": "支持比较。",
        "next_action": "核查 PDF。",
        "degraded_content_warnings": [],
    }
    if mode == "degrade":
        output["main_findings"] = [
            {
                "statement": "PRIVATE_DISCARDED",
                "evidence": [{"evidence_id": "PRIVATE_BAD_ID"}],
            },
            {"statement": "有效结果。", "evidence": [{"evidence_id": "e000002"}]},
        ]
    raw = "{}" if mode == "invalid" else json.dumps(output, ensure_ascii=False)

    def initialize(self: PeerRun, peer: str) -> None:
        before = '    cwd = "<cwd>\\n"'
        replacement = f"""    if '\\"stage\\":\\"read\\"' in command["message"]:
        raw = {raw!r}
"""
        assert before in peer
        original(self, peer.replace(before, replacement + before))

    monkeypatch.setattr(PeerRun, "__init__", initialize)
    layout = layout_fixture(feed, tmp_path, monkeypatch)
    if reviewed:
        layout.review()
    root = layout.extraction.root
    config = root.config
    (config / "read").mkdir()
    (config / "read/read-v1.yaml").write_text(
        "version: read-v1\nchunking_version: v1\n"
    )
    prompt = root.root / "prompts/reading"
    prompt.mkdir()
    (prompt / "v1.md").write_text("PRIVATE_READ_PROMPT\n")
    export_frozen_contract("read", "v1", root.root / "contracts")
    settings = config / "settings.yaml"
    values = yaml.safe_load(settings.read_text())
    values["read"] = "read-v1"
    values["prompts"]["reading"] = "v1"
    values["contracts"]["read"] = "v1"
    models_path = config / "models/models-v1.yaml"
    models = yaml.safe_load(models_path.read_text())
    models["version"] = "models-read-v1"
    models["reading"] = dict(models["screening"])
    (models_path.parent / "models-read-v1.yaml").write_text(yaml.safe_dump(models))
    values["models"] = "models-read-v1"
    settings.write_text(yaml.safe_dump(values))
    snapshot = compile_config(settings, root.database).snapshot_id
    result = invoke(
        "egress-authorize",
        "--root",
        str(root.root),
        "--snapshot",
        snapshot,
        "--stage",
        "boundary",
        "--stage",
        "value",
        "--stage",
        "read",
        "--reason",
        "PRIVATE_READ_EGRESS_REASON",
    )
    assert result.exit_code == 0, result.output
    return ReadFixture(layout, snapshot)
