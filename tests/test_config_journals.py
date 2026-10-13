"""A2-07 的公共服务登记与规范期刊集合。不改变阶段就绪。"""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from paper_radar.config import check_config, compile_config, load_config_snapshot
from tests.config_journals_support import journal_inputs


def test_journals_are_normalized_sorted_and_replayable(tmp_path: Path) -> None:
    settings, database = journal_inputs(tmp_path)
    settings.write_text(settings.read_text().replace("journals: journals-v1\n", ""))
    previous = compile_config(settings, database)
    settings.write_text(settings.read_text() + "journals: journals-v1\n")
    checked = check_config(settings, database)
    saved = compile_config(settings, database)
    assert saved == checked
    assert saved.snapshot_id != previous.snapshot_id
    assert saved.stages == previous.stages
    payload = json.loads(saved.payload_json)
    assert payload["selectors"]["journals"] == "journals-v1"
    material = next(m for m in payload["materials"] if m["kind"] == "journals")
    assert material["name"] == "journals"
    assert material["version"] == "journals-v1"
    assert material["config"] == {
        "version": "journals-v1",
        "journals": [
            {
                "issn_l": "0035-9009",
                "issns": ["1477-870X"],
                "name": "同名期刊",
                "tier": "low",
            },
            {"issn_l": "1006-9895", "issns": [], "name": "中文期刊", "tier": "normal"},
            {
                "issn_l": "2169-897X",
                "issns": ["2169-897X", "2169-8996"],
                "name": "同名期刊",
                "tier": "preferred",
            },
            {"issn_l": "2769-7525", "issns": [], "name": "电子期刊", "tier": "normal"},
        ],
    }
    assert compile_config(settings, database) == saved
    assert load_config_snapshot(database, saved.snapshot_id) == saved
    assert load_config_snapshot(database, previous.snapshot_id) == previous


@pytest.mark.parametrize("selection", ["absent", "null", "empty", "full"])
def test_public_journal_semantics_distinguish_empty_and_unconfigured(
    tmp_path: Path, selection: str
) -> None:
    settings, database = journal_inputs(tmp_path)
    previous = check_config(settings, database)
    if selection in ("absent", "null"):
        settings.write_text(
            settings.read_text().replace("journals: journals-v1\n", "")
            + ("journals: null\n" if selection == "null" else "")
        )
    elif selection == "empty":
        (settings.parent / "journals/journals-v1.yaml").write_text(
            "version: journals-v1\njournals: []\n"
        )
    saved = compile_config(settings, database)
    assert saved.journals_status == (
        "unconfigured" if selection in ("absent", "null") else "configured"
    )
    assert saved.stages == previous.stages
    if selection == "full":
        assert [(j.issn_l, j.issns, j.name, j.tier) for j in saved.journals] == [
            ("0035-9009", ("1477-870X",), "同名期刊", "low"),
            ("1006-9895", (), "中文期刊", "normal"),
            ("2169-897X", ("2169-897X", "2169-8996"), "同名期刊", "preferred"),
            ("2769-7525", (), "电子期刊", "normal"),
        ]
        with pytest.raises(FrozenInstanceError):
            setattr(saved.journals[0], "tier", "preferred")  # noqa: B010
    else:
        assert saved.journals == ()
    assert load_config_snapshot(database, saved.snapshot_id) == saved
