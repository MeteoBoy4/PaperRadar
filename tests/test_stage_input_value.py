"""价值预测阶段输入与同源输出验证上下文。"""

import hashlib
import json
from pathlib import Path

import pytest

from paper_radar.config import (
    StageName,
    compile_config,
    load_config_snapshot,
    project_config,
)
from paper_radar.screening import (
    OutputValidationError,
    ValuePredictionOutput,
    validate_output,
)
from paper_radar.stage_inputs import (
    BuildReason,
    InputField,
    ReplayReason,
    ScreeningFacts,
    StageInputError,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)
from tests.config_projection_support import full_inputs, new_yaml_version


def test_value_input_replays_and_derives_context_for_authoritative_validation(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    compiled = compile_config(settings, database)
    snapshot = load_config_snapshot(database, compiled.snapshot_id)
    facts = ScreeningFacts(
        title="Synthetic title",
        abstract="Synthetic abstract\n",
        abstract_truncated=False,
    )
    value = build_stage_input(snapshot, StageName.VALUE, facts)
    replayed = replay_stage_input(
        value.payload_bytes, value.fingerprint, snapshot=snapshot
    )
    context = replayed.value_prediction_context(snapshot, original_title_is_zh=False)
    assert context.enabled_topic_ids == frozenset({"active"})
    payload = _valid_value_payload()
    output = validate_output("value_prediction", payload, context)
    assert isinstance(output, ValuePredictionOutput)
    assert output.topic_ids == ["active"]
    assert compare_stage_inputs(value, replayed).status == "same"
    boundary = build_stage_input(snapshot, StageName.BOUNDARY, facts)
    assert boundary.fingerprint != value.fingerprint
    assert compare_stage_inputs(boundary, value).reason == "different_stage"


def _valid_value_payload() -> dict[str, object]:
    return {
        "research_value": 4,
        "research_value_reason_zh": "该方法能改进区域降水诊断。",
        "reuse_feasibility": 3,
        "reuse_feasibility_reason_zh": "需要调整现有数据处理流程。",
        "reuse_feasibility_inferable": True,
        "value_types": ["method"],
        "topic_ids": ["active"],
        "abstract_brief_zh": "研究提出新的降水诊断方法。",
        "why_it_may_matter_zh": "可改进当前的区域降水分析。",
    }


@pytest.mark.parametrize("language", [True, False])
def test_title_language_changes_context_but_not_value_identity(
    tmp_path: Path, language: bool
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ScreeningFacts(
        title="SECRET_TITLE", abstract="SECRET_ABSTRACT", abstract_truncated=False
    )
    value = build_stage_input(snapshot, StageName.VALUE, facts)
    fingerprint = value.fingerprint
    before_database = database.read_bytes()
    context = value.value_prediction_context(snapshot, original_title_is_zh=language)
    payload = _valid_value_payload()
    payload["display_title_zh"] = "合成中文标题"
    if language:
        with pytest.raises(OutputValidationError):
            validate_output("value_prediction", payload, context)
    else:
        assert (
            validate_output("value_prediction", payload, context).display_title_zh
            == "合成中文标题"
        )
    assert value.fingerprint == fingerprint
    assert "original_title_is_zh" not in json.loads(value.payload_bytes)["facts"]
    assert database.read_bytes() == before_database


@pytest.mark.parametrize("invalid", [1, 0, "SECRET_LANGUAGE", None, [], {}])
def test_context_rejects_invalid_language_without_raw_validation_errors(
    tmp_path: Path, invalid: object
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    value = build_stage_input(
        snapshot,
        StageName.VALUE,
        ScreeningFacts(
            title="SECRET_TITLE", abstract="SECRET_ABSTRACT", abstract_truncated=False
        ),
    )
    with pytest.raises(StageInputError) as caught:
        value.value_prediction_context(snapshot, original_title_is_zh=invalid)
    assert caught.value.reason is BuildReason.INVALID_CONTEXT
    assert caught.value.field is InputField.TITLE_LANGUAGE
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value) + repr(caught.value)


def test_context_is_bound_to_the_explicit_value_projection_and_freezes_topic_ids(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    original = compile_config(settings, database)
    value = build_stage_input(
        original,
        StageName.VALUE,
        ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
    )
    replayed = replay_stage_input(value.payload_bytes, value.fingerprint)
    context = replayed.value_prediction_context(original, original_title_is_zh=False)
    caller_ids = set(context.enabled_topic_ids)
    caller_ids.add("unrelated")
    assert context.enabled_topic_ids == frozenset({"active"})
    new_yaml_version(
        settings, "topics", lambda c: c["topics"][0].update(id="replacement")
    )
    changed = compile_config(settings, database)
    assert context.enabled_topic_ids == frozenset({"active"})
    with pytest.raises(StageInputError) as caught:
        replayed.value_prediction_context(changed, original_title_is_zh=False)
    assert caught.value.reason is BuildReason.PROJECTION_MISMATCH
    with pytest.raises(StageInputError) as replay_error:
        replay_stage_input(value.payload_bytes, value.fingerprint, snapshot=changed)
    assert replay_error.value.reason is ReplayReason.PROJECTION_MISMATCH
    invalid_payload = _valid_value_payload()
    invalid_payload["topic_ids"] = ["replacement"]
    with pytest.raises(OutputValidationError):
        validate_output("value_prediction", invalid_payload, context)
    assert (
        replayed.value_prediction_context(
            load_config_snapshot(database, original.snapshot_id),
            original_title_is_zh=False,
        )
        == context
    )


def test_boundary_cannot_derive_value_context_or_receive_an_independent_topic_set(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    boundary = build_stage_input(snapshot, StageName.BOUNDARY, facts)
    with pytest.raises(StageInputError) as caught:
        boundary.value_prediction_context(snapshot, original_title_is_zh=False)
    assert caught.value.reason is BuildReason.INVALID_CONTEXT
    value = build_stage_input(snapshot, StageName.VALUE, facts)
    with pytest.raises(StageInputError) as caught:
        value.value_prediction_context(
            snapshot, original_title_is_zh=False, enabled_topic_ids={"SECRET_TOPIC"}
        )
    assert caught.value.field is InputField.CONTEXT
    assert "SECRET" not in repr(caught.value)


@pytest.mark.parametrize("field", ["id", "name", "description", "enabled"])
def test_enabled_topic_semantics_propagate_only_to_value(
    tmp_path: Path, field: str
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings,
        "topics",
        lambda c: c["topics"][0].update(
            {field: False if field == "enabled" else "changed"}
        ),
    )
    after = compile_config(settings, database)
    facts = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    for stage in (StageName.BOUNDARY, StageName.VALUE):
        first = build_stage_input(before, stage, facts)
        second = build_stage_input(after, stage, facts)
        assert (first.fingerprint != second.fingerprint) == (stage is StageName.VALUE)
        assert (first.fingerprint != second.fingerprint) == (
            project_config(before).projections[stage].projection_id
            != project_config(after).projections[stage].projection_id
        )
        assert compare_stage_inputs(first, second).changed_components == (
            ("config_projection",) if stage is StageName.VALUE else ()
        )


def test_configured_empty_topics_are_valid_but_missing_topics_are_not(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    new_yaml_version(settings, "topics", lambda c: c.update(topics=[]))
    snapshot = compile_config(settings, database)
    facts = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    value = build_stage_input(snapshot, StageName.VALUE, facts)
    context = value.value_prediction_context(snapshot, original_title_is_zh=False)
    assert context.enabled_topic_ids == frozenset()
    payload = _valid_value_payload()
    payload["topic_ids"] = []
    assert validate_output("value_prediction", payload, context).topic_ids == []
    settings.write_text(settings.read_text().replace("topics: topics-v2\n", ""))
    missing = compile_config(settings, database)
    with pytest.raises(StageInputError) as caught:
        build_stage_input(missing, StageName.VALUE, facts)
    assert caught.value.reason is BuildReason.NOT_READY
    assert caught.value.readiness is missing.stages[StageName.VALUE]
    assert "topics" in caught.value.readiness.missing


def test_value_does_not_require_boundary_result_or_ready_boundary_configuration(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    (tmp_path / "prompts/screening/boundary-v2.md").write_text("...\n")
    settings.write_text(settings.read_text().replace("boundary: v1", "boundary: v2", 1))
    snapshot = compile_config(settings, database)
    assert snapshot.stages[StageName.BOUNDARY].status == "not_ready"
    value = build_stage_input(
        snapshot,
        StageName.VALUE,
        ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
    )
    assert value.stage is StageName.VALUE


def test_value_matches_independent_literal_vector_and_historical_replay(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    fixture = Path(__file__).parent / "fixtures/stage_inputs"
    payload = (fixture / "value-v1.json").read_bytes()
    fingerprint = (fixture / "value-v1.sha256").read_text().strip()
    assert (
        fingerprint
        == "c8d68282f6366900ebadc342034b6ac9272bccbecd7a766e50bd480210533db0"
    )
    assert hashlib.sha256(payload).hexdigest() == fingerprint
    value = build_stage_input(
        snapshot,
        StageName.VALUE,
        ScreeningFacts(
            title="Synthetic title",
            abstract="Synthetic abstract\n",
            abstract_truncated=False,
        ),
    )
    assert value.payload_bytes == payload
    assert value.fingerprint == fingerprint
    assert (
        replay_stage_input(
            payload,
            fingerprint,
            snapshot=load_config_snapshot(database, snapshot.snapshot_id),
        )
        == value
    )


def test_value_context_does_not_use_a_new_projection_format_as_historical_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config import projections

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    value = build_stage_input(
        snapshot,
        StageName.VALUE,
        ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
    )
    versions = dict(projections.PROJECTION_FORMAT_VERSIONS)
    versions[StageName.VALUE] = 2
    monkeypatch.setattr(projections, "PROJECTION_FORMAT_VERSIONS", versions)
    with pytest.raises(StageInputError) as caught:
        value.value_prediction_context(snapshot, original_title_is_zh=False)
    assert caught.value.reason is BuildReason.PROJECTION_FORMAT_UNVERIFIABLE


@pytest.mark.parametrize(
    "extra",
    [
        "boundary_output",
        "session_id",
        "artifact_id",
        "authors",
        "original_title_is_zh",
        "enabled_topic_ids",
    ],
)
def test_value_facts_reject_implicit_previous_results_and_metadata(extra: str) -> None:
    with pytest.raises(StageInputError) as caught:
        ScreeningFacts(
            title="T", abstract="A", abstract_truncated=False, **{extra: "SECRET_VALUE"}
        )
    assert caught.value.reason is BuildReason.INVALID_FACTS
    assert caught.value.field is InputField.FACTS
    assert "SECRET" not in repr(caught.value)


def test_value_context_requires_explicit_title_language(tmp_path: Path) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    value = build_stage_input(
        snapshot,
        StageName.VALUE,
        ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
    )
    with pytest.raises(StageInputError) as caught:
        value.value_prediction_context(snapshot)
    assert caught.value.reason is BuildReason.INVALID_CONTEXT
    assert caught.value.field is InputField.TITLE_LANGUAGE


def test_value_context_rejects_invalid_snapshot_with_build_reason(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    value = build_stage_input(
        snapshot,
        StageName.VALUE,
        ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
    )
    with pytest.raises(StageInputError) as caught:
        value.value_prediction_context(
            {"PRIVATE_SNAPSHOT": "PRIVATE_VALUE"},  # type: ignore[arg-type]
            original_title_is_zh=False,
        )
    assert caught.value.reason is BuildReason.INVALID_SNAPSHOT
    assert caught.value.field is InputField.SNAPSHOT
    assert caught.value.__context__ is None
    assert "PRIVATE" not in str(caught.value) + repr(caught.value)
