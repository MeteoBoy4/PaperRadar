"""B-E15 独立 D1:强身份暴露导出的真实 CLI 接缝。"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed


def export(root: Path) -> dict[str, Any]:
    result = invoke("export-exposure", "--root", str(root))
    assert result.exit_code == 0, result.output
    return TypeAdapter(dict[str, Any]).validate_json(result.stdout)


def test_candidates_alone_export_empty_frozen_manifest(feed: FeedFixture) -> None:
    root, state, fetch = feed
    state["order"] = [1, 2]
    check = fetch("exposure-candidates")
    candidates = invoke(
        "candidates", "--root", str(root), "--check-id", check["check_id"]
    )
    assert candidates.exit_code == 0, candidates.output
    receipt = export(root)
    path = root / "views" / "exposure" / f"{receipt['export_id']}.json"
    payload = json.loads(path.read_bytes())
    assert payload == {
        "domain": "paper-radar.exposure",
        "format_version": 1,
        "root_id": receipt["root_id"],
        "papers": [],
        "relations": [],
    }
    assert export(root) == receipt
    assert "PRIVATE_" not in path.read_text()


def test_replaced_and_failed_samples_remain_exposed(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.experiment_screen_support import screen_fixture
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch, mode="output_invalid")
    failed = prepared.screen()
    assert failed.exit_code == 4, failed.output
    first = export(prepared.root)
    original = (prepared.root / "views" / first["relative_path"]).read_bytes()
    chosen = select(
        prepared.root,
        prepared.view_id,
        "replacement",
        "--position",
        "2",
        "--replaces",
        prepared.selection_id,
        "--replacement-reason",
        "PRIVATE_REPLACEMENT_REASON",
    )
    assert chosen.exit_code == 0, chosen.output
    second = export(prepared.root)
    payload = json.loads(
        (prepared.root / "views" / second["relative_path"]).read_bytes()
    )
    assert payload["papers"] == [
        {
            "doi": "10.1029/synthetic1",
            "version_kind": "journal",
            "categories": [
                "screening_attempt",
                "screening_request",
                "selection_authorization",
            ],
        },
        {
            "doi": "10.1029/synthetic2",
            "version_kind": "journal",
            "categories": ["selection_authorization"],
        },
    ]
    assert first["export_id"] != second["export_id"]
    assert (prepared.root / "views" / first["relative_path"]).read_bytes() == original
    from typer.testing import CliRunner

    from paper_radar.cli import app

    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(prepared.root / "paper-radar.sqlite3"),
            "--data-root",
            str(prepared.root / "data"),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 0, backup.output
    public = (
        failed.output
        + chosen.output
        + (prepared.root / "logs/runtime.jsonl").read_text()
    )
    assert "PRIVATE_" not in public
    assert "PRIVATE_" not in json.dumps(payload)
