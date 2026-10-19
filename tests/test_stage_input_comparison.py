"""研究边界的精确文本与只读差异行为。"""

import builtins
from pathlib import Path

import pytest

from paper_radar.config import StageName, compile_config
from paper_radar.stage_inputs import (
    BuildReason,
    ChangeComponent,
    ComparisonReason,
    ScreeningFacts,
    StageInputError,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)
from tests.config_projection_support import full_inputs, new_yaml_version
from tests.config_test_support import boundary_inputs


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("café", "cafe\u0301"),
        ("a\r\nb", "a\nb"),
        ("content", " content"),
        ("content", "content "),
        ("Content", "content"),
    ],
)
@pytest.mark.parametrize("field", ["title", "abstract"])
@pytest.mark.parametrize("stage", [StageName.BOUNDARY, StageName.VALUE])
def test_text_is_preserved_without_hidden_normalization(
    tmp_path: Path, first: str, second: str, field: str, stage: StageName
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    common = {"title": "T", "abstract": "A", "abstract_truncated": False}
    before = build_stage_input(
        snapshot, stage, ScreeningFacts(**{**common, field: first})
    )
    after = build_stage_input(
        snapshot, stage, ScreeningFacts(**{**common, field: second})
    )
    assert before.fingerprint != after.fingerprint
    assert compare_stage_inputs(before, after).changed_components == (field,)
    assert (
        getattr(
            replay_stage_input(before.payload_bytes, before.fingerprint).facts, field
        )
        == first
    )


def test_comparison_has_fixed_safe_component_order_and_no_business_effects(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    before = build_stage_input(
        snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(
            title="SECRET_TITLE", abstract="SECRET_ABSTRACT", abstract_truncated=False
        ),
    )
    new_yaml_version(
        settings, "profile", lambda c: c.update(background="SECRET_PROFILE")
    )
    after_snapshot = compile_config(settings, database)
    after = build_stage_input(
        after_snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(
            title="SECRET_NEW_TITLE",
            abstract="SECRET_NEW_ABSTRACT",
            abstract_truncated=True,
        ),
    )
    database_before = database.read_bytes()
    diff = compare_stage_inputs(before, after)
    assert diff.status == "changed"
    assert diff.changed_components == (
        ChangeComponent.CONFIG_PROJECTION,
        ChangeComponent.TITLE,
        ChangeComponent.ABSTRACT,
        ChangeComponent.ABSTRACT_TRUNCATED,
    )
    assert "SECRET" not in repr(diff)
    assert database.read_bytes() == database_before
    assert compare_stage_inputs(before, before).status == "same"
    assert not compare_stage_inputs(before, before).changed_components


@pytest.mark.parametrize("stage", [StageName.BOUNDARY, StageName.VALUE])
def test_truncated_flag_changes_identity_while_placeholders_remain_exact_text(
    tmp_path: Path,
    stage: StageName,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    before = build_stage_input(
        snapshot,
        stage,
        ScreeningFacts(title="REQUIRED", abstract="...", abstract_truncated=False),
    )
    after = build_stage_input(
        snapshot,
        stage,
        ScreeningFacts(title="REQUIRED", abstract="...", abstract_truncated=True),
    )
    assert before.fingerprint != after.fingerprint
    assert compare_stage_inputs(before, after).changed_components == (
        "abstract_truncated",
    )


def test_ready_historical_snapshot_without_adapter_and_mapping_order_are_supported(
    tmp_path: Path,
) -> None:
    settings, database = boundary_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    assert snapshot.adapters["screening"] is None
    first = {"title": "T", "abstract": "A", "abstract_truncated": False}
    second = {key: first[key] for key in reversed(first)}
    before = build_stage_input(snapshot, StageName.BOUNDARY, ScreeningFacts(**first))
    after = build_stage_input(snapshot, StageName.BOUNDARY, ScreeningFacts(**second))
    assert before == after


def test_placeholder_configuration_preserves_existing_missing_reason(
    tmp_path: Path,
) -> None:
    settings, database = boundary_inputs(tmp_path)
    prompt = tmp_path / "prompts/screening/boundary-v2.md"
    prompt.write_text("...\n")
    settings.write_text(settings.read_text().replace("boundary: v1", "boundary: v2", 1))
    snapshot = compile_config(settings, database)
    assert "boundary_prompt_placeholder" in snapshot.stages[StageName.BOUNDARY].missing
    with pytest.raises(StageInputError) as caught:
        build_stage_input(
            snapshot,
            StageName.BOUNDARY,
            ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
        )
    assert caught.value.reason is BuildReason.NOT_READY
    assert caught.value.readiness is snapshot.stages[StageName.BOUNDARY]


def test_input_operations_need_no_current_files_database_or_artifact_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)

    def forbid_io(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected I/O")

    monkeypatch.setattr(builtins, "open", forbid_io)
    monkeypatch.setattr(Path, "open", forbid_io)
    result = build_stage_input(snapshot, StageName.BOUNDARY, facts)
    replayed = replay_stage_input(
        result.payload_bytes, result.fingerprint, snapshot=snapshot
    )
    assert compare_stage_inputs(result, replayed).status == "same"


def test_compare_rejects_untyped_values_without_echoing_them() -> None:
    result = compare_stage_inputs("SECRET_INPUT", {})  # type: ignore[arg-type]
    assert result.status == "incomparable"
    assert result.reason is ComparisonReason.INVALID_INPUT
    assert "SECRET" not in repr(result)


def test_future_stage_input_format_is_not_comparable_to_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 仅合成未来格式的纯 fixture。不登记假生产格式。
    from paper_radar.stage_inputs import service

    settings, database = boundary_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    before = build_stage_input(snapshot, StageName.BOUNDARY, facts)
    monkeypatch.setattr(service, "STAGE_INPUT_FORMAT_VERSIONS", {StageName.BOUNDARY: 2})
    after = build_stage_input(snapshot, StageName.BOUNDARY, facts)
    assert before.fingerprint != after.fingerprint
    diff = compare_stage_inputs(before, after)
    assert diff.status == "incomparable"
    assert diff.reason is ComparisonReason.INCOMPATIBLE_FORMAT
