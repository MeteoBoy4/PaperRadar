"""A2-04 公共服务的复用升级与建议规则配置承诺。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_radar.config import check_config, compile_config, load_config_snapshot
from paper_radar.config.compile import MissingReason, StageName
from tests.config_reuse_support import reuse_inputs


def test_reuse_and_suggestion_configuration_ready_without_value_or_pdf(
    tmp_path: Path,
) -> None:
    settings, db = reuse_inputs(tmp_path)
    checked = check_config(settings, db)
    assert checked.stages[StageName.REUSE].status == "ready"
    assert checked.stages[StageName.REUSE].missing == ()
    assert checked.stages[StageName.SUGGESTION].status == "ready"
    assert checked.stages[StageName.SUGGESTION].missing == ()
    assert checked.stages[StageName.VALUE].missing == (
        MissingReason.VALUE_PROMPT,
        MissingReason.VALUE_CONTRACT,
        MissingReason.TOPICS,
    )
    saved = compile_config(settings, db)
    assert saved == checked
    assert compile_config(settings, db) == saved
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    payload = json.loads(saved.payload_json)
    escalation = next(m for m in payload["materials"] if m["kind"] == "escalation")
    assert escalation["config"] == {
        "version": "reuse-escalation-v1",
        "reuse_escalation_research_values": [3],
        "excerpt_priority": ["availability", "methods"],
        "excerpt_selector_version": "v1",
        "suggestion_rule_version": "v1",
    }
    assert payload["selectors"]["escalation"] == "reuse-escalation-v1"


@pytest.mark.parametrize(
    ("removed", "reuse_missing", "suggestion_missing"),
    [
        ("profile: profile-v1\n", (MissingReason.PROFILE,), ()),
        ("  reuse: v1\n", (MissingReason.REUSE_PROMPT,), ()),
        ("  reuse_assessment: v1\n", (MissingReason.REUSE_CONTRACT,), ()),
        (
            "escalation: reuse-escalation-v1\n",
            (MissingReason.EXCERPT_SELECTOR,),
            (MissingReason.SUGGESTION_RULE, MissingReason.ESCALATION_PARAMETERS),
        ),
        (
            "  decision_reasons: v1\n",
            (),
            (MissingReason.DECISION_REASONS_CONTRACT,),
        ),
    ],
)
def test_each_stage_reports_its_own_missing_configuration(
    tmp_path: Path,
    removed: str,
    reuse_missing: tuple[MissingReason, ...],
    suggestion_missing: tuple[MissingReason, ...],
) -> None:
    settings, db = reuse_inputs(tmp_path)
    settings.write_text(settings.read_text().replace(removed, ""))
    checked = check_config(settings, db)
    assert checked.stages[StageName.REUSE].missing == reuse_missing
    assert checked.stages[StageName.SUGGESTION].missing == suggestion_missing
    assert checked.stages[StageName.REUSE].status == (
        "not_ready" if reuse_missing else "ready"
    )
    assert checked.stages[StageName.SUGGESTION].status == (
        "not_ready" if suggestion_missing else "ready"
    )
    saved = compile_config(settings, db)
    assert saved == checked == load_config_snapshot(db, saved.snapshot_id)


@pytest.mark.parametrize("prompt", [b"", b"  \n", b" ... \n"])
def test_placeholder_reuse_prompt_is_saved_as_not_ready(
    tmp_path: Path, prompt: bytes
) -> None:
    settings, db = reuse_inputs(tmp_path)
    (tmp_path / "prompts/screening/reuse-v1.md").write_bytes(prompt)
    saved = compile_config(settings, db)
    assert saved.stages[StageName.REUSE].missing == (
        MissingReason.REUSE_PROMPT_PLACEHOLDER,
    )
    assert saved.stages[StageName.SUGGESTION].status == "ready"
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize(
    ("slot", "reason"),
    [
        ("null", MissingReason.REUSE_MODEL),
        ("{}", MissingReason.REUSE_MODEL),
        (
            "{provider: REQUIRED_FOR_FORMAL_CALIBRATION, "
            "model: real-model, protocol: json_schema}",
            MissingReason.REUSE_MODEL_PLACEHOLDER,
        ),
    ],
)
def test_reuse_model_missing_and_placeholder_do_not_block_suggestion_configuration(
    tmp_path: Path, slot: str, reason: MissingReason
) -> None:
    settings, db = reuse_inputs(tmp_path)
    (tmp_path / "config/models/models-v1.yaml").write_text(
        "version: models-v1\nscreening: null\n"
        f"reuse_assessment: {slot}\nreading: null\n"
    )
    result = check_config(settings, db)
    assert result.stages[StageName.REUSE].missing == (reason,)
    assert result.stages[StageName.SUGGESTION].status == "ready"


@pytest.mark.parametrize("changed_slot", ["screening", "reuse_assessment"])
def test_initially_equal_model_slots_remain_independently_queryable(
    tmp_path: Path, changed_slot: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    first = compile_config(settings, db)
    path = tmp_path / "config/models/models-v1.yaml"
    marker = f"{changed_slot}:\n  provider: provider-a\n  model: real-model"
    (path.parent / "models-v2.yaml").write_text(
        path.read_text()
        .replace("models-v1", "models-v2")
        .replace(marker, marker.replace("real-model", "other-model"))
    )
    settings.write_text(settings.read_text().replace("models-v1", "models-v2"))
    second = compile_config(settings, db)
    assert second.snapshot_id != first.snapshot_id
    for snapshot in (first, second):
        models = next(
            m["config"]
            for m in json.loads(
                load_config_snapshot(db, snapshot.snapshot_id).payload_json
            )["materials"]
            if m["kind"] == "models"
        )
        for slot in ("screening", "reuse_assessment"):
            expected = (
                "other-model"
                if snapshot == second and slot == changed_slot
                else "real-model"
            )
            assert models[slot]["model"] == expected


def test_synthetic_reuse_example_is_ready_and_history_replays(tmp_path: Path) -> None:
    from paper_radar.config import upgrade_database

    examples = Path(__file__).resolve().parents[1] / "examples/config"
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    saved = compile_config(examples / "settings-reuse.yaml", db)
    assert saved.stages[StageName.REUSE].status == "ready"
    assert saved.stages[StageName.SUGGESTION].status == "ready"
    assert load_config_snapshot(db, saved.snapshot_id) == saved
