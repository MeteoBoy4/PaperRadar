"""B 收口修复的独立 D1:论文默认事实与显式工作流分别可用。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from tests.feed_support import facts, item


@pytest.mark.parametrize("command", ("show", "trace"))
def test_default_facts_and_explicit_workflow_remain_separate(
    tmp_path: Path, command: str
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/offline-compatibility")
    result = service.submit(item(feed.feed_id, payload=b"PRIVATE_RAW_FEED"))
    assert result.paper_id and service.data_root
    expected = (
        service.trace(result.paper_id)
        if command == "trace"
        else service.show(result.paper_id)
    ).model_dump(mode="json")
    arguments = [
        "paper",
        command,
        result.paper_id,
        "--database",
        str(service.database),
        "--data-root",
        str(service.data_root),
        "--show-abstract",
        "--json",
    ]
    runner = CliRunner()
    default = runner.invoke(app, arguments)
    assert default.exit_code == 0, default.output
    assert json.loads(default.stdout) == expected
    expanded = runner.invoke(app, [*arguments, "--workflow"])
    assert expanded.exit_code == 0, expanded.output
    payload = json.loads(expanded.stdout)
    workflow = payload.pop("workflow")
    assert payload == expected
    assert workflow["root"]["purpose"] == "unknown"
    assert workflow["screening"] == []
    assert (
        "root_unknown" in workflow["eligibility"]["eligible_for_auto_read"]["reasons"]
    )
    assert "PRIVATE_RAW_FEED" not in default.output + expanded.output
    assert not (service.data_root / "logs").exists()
