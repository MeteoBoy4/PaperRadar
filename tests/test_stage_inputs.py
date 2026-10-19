"""四阶段输入公共边界。规范事实、指纹与只读解释。"""

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from paper_radar.config import StageName, compile_config, project_config
from paper_radar.stage_inputs import (
    BuildReason,
    InputField,
    ScreeningFacts,
    StageInputError,
    build_stage_input,
    replay_stage_input,
)
from tests.config_projection_support import full_inputs


def test_boundary_uses_exact_text_and_its_own_projection(tmp_path: Path) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ScreeningFacts(
        title="Synthetic title",
        abstract="Synthetic abstract\n",
        abstract_truncated=False,
    )
    result = build_stage_input(snapshot, StageName.BOUNDARY, facts)
    payload = json.loads(result.payload_bytes)
    assert payload == {
        "kind": "stage_input",
        "stage": "boundary",
        "format_version": 1,
        "config_projection": {
            "format_version": 1,
            "projection_id": project_config(snapshot)
            .projections[StageName.BOUNDARY]
            .projection_id,
        },
        "facts": {
            "title": "Synthetic title",
            "abstract": "Synthetic abstract\n",
            "abstract_truncated": False,
        },
    }
    assert result.fingerprint == hashlib.sha256(result.payload_bytes).hexdigest()
    assert (
        replay_stage_input(result.payload_bytes, result.fingerprint, snapshot=snapshot)
        == result
    )


@pytest.mark.parametrize(
    ("override", "reason", "location"),
    [
        ({"title": ""}, BuildReason.INVALID_TEXT, InputField.TITLE),
        ({"title": " \t\n"}, BuildReason.INVALID_TEXT, InputField.TITLE),
        ({"abstract": None}, BuildReason.INVALID_TEXT, InputField.ABSTRACT),
        ({"abstract": 12}, BuildReason.INVALID_TEXT, InputField.ABSTRACT),
        (
            {"abstract_truncated": 1},
            BuildReason.INVALID_FACTS,
            InputField.ABSTRACT_TRUNCATED,
        ),
        (
            {"abstract_truncated": "false"},
            BuildReason.INVALID_FACTS,
            InputField.ABSTRACT_TRUNCATED,
        ),
        ({"title": "secret\ud800"}, BuildReason.INVALID_ENCODING, InputField.TITLE),
        (
            {"abstract": "secret\ud800"},
            BuildReason.INVALID_ENCODING,
            InputField.ABSTRACT,
        ),
        (
            {"secret-extra-name": "secret-extra-value"},
            BuildReason.INVALID_FACTS,
            InputField.FACTS,
        ),
    ],
)
def test_strict_fact_rejections_are_safe(
    override: dict[str, object], reason: BuildReason, location: InputField
) -> None:
    values: dict[str, object] = {
        "title": "secret title",
        "abstract": "secret abstract",
        "abstract_truncated": False,
    }
    values.update(override)
    with pytest.raises(StageInputError) as caught:
        ScreeningFacts(**values)
    assert caught.value.reason is reason
    assert caught.value.field is location
    assert "secret" not in str(caught.value) + repr(caught.value)
    assert caught.value.__context__ is None


def test_facts_and_result_are_frozen_and_do_not_print_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    settings, database = full_inputs(tmp_path)
    facts = ScreeningFacts(
        title="SECRET_TITLE", abstract="SECRET_ABSTRACT", abstract_truncated=False
    )
    result = build_stage_input(
        compile_config(settings, database), StageName.BOUNDARY, facts
    )
    for item, field_name in ((facts, "title"), (result, "payload_bytes")):
        with pytest.raises(dataclasses.FrozenInstanceError) as caught:
            setattr(item, field_name, "SECRET_NEW_VALUE")
        assert "SECRET" not in str(caught.value)
    assert "SECRET" not in repr(facts) + repr(result)
    assert capsys.readouterr() == ("", "")
    assert not caplog.records


def test_missing_configuration_keeps_existing_readiness(tmp_path: Path) -> None:
    from tests.config_projection_support import empty_inputs

    settings, database = empty_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ScreeningFacts(title="...", abstract="REQUIRED", abstract_truncated=False)
    with pytest.raises(StageInputError) as caught:
        build_stage_input(snapshot, StageName.BOUNDARY, facts)
    assert caught.value.reason is BuildReason.NOT_READY
    assert caught.value.readiness == snapshot.stages[StageName.BOUNDARY]


@pytest.mark.parametrize(
    "stage", [StageName.VALUE, StageName.READ, StageName.SUGGESTION, "secret-stage", {}]
)
def test_unclaimed_stages_are_controlled_rejections(
    tmp_path: Path, stage: object
) -> None:
    settings, database = full_inputs(tmp_path)
    with pytest.raises(StageInputError) as caught:
        build_stage_input(
            compile_config(settings, database),
            stage,  # type: ignore[arg-type]
            ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
        )
    assert caught.value.reason is BuildReason.UNSUPPORTED_STAGE
    assert "secret" not in str(caught.value)


def test_public_result_cannot_be_constructed_with_unvalidated_mutable_fields() -> None:
    from paper_radar.stage_inputs import StageInput

    with pytest.raises(StageInputError):
        StageInput(
            stage=StageName.BOUNDARY,
            format_version=1,
            projection_format_version=1,
            projection_id="0" * 64,
            facts={},
            payload_bytes=bytearray(b"secret"),
        )
