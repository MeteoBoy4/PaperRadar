"""公开模型标准校验入口不暴露合成输入。"""

import json

import pytest

from paper_radar.papers import CandidateInput, DateValue, PaperError


@pytest.mark.parametrize("entry", ["model_validate_json", "model_validate_strings"])
@pytest.mark.parametrize("shape", ["missing", "nested", "extra"])
def test_public_validation_failure_is_controlled(entry: str, shape: str) -> None:
    sentinel = "PAPER_PRIVACY_SENTINEL"
    model = CandidateInput if shape == "nested" else DateValue
    data: dict[str, object] = {"value": sentinel, "precision": "year"}
    if shape == "missing":
        data = {"value": sentinel}
    elif shape == "extra":
        data["unknown"] = sentinel
    else:
        data = {"value": {"text": sentinel}, "locator": "title"}
    value = json.dumps(data) if entry == "model_validate_json" else data
    with pytest.raises(PaperError, match="invalid_observation") as failure:
        getattr(model, entry)(value)
    assert failure.value.reason == "invalid_observation"
    assert sentinel not in str(failure.value) + repr(failure.value)
    assert not hasattr(failure.value, "errors")
    assert not hasattr(failure.value, "json")


def test_public_json_and_strings_validation_preserve_valid_options() -> None:
    data = {"value": "2026", "precision": "year"}
    json_value = DateValue.model_validate_json(
        json.dumps(data).encode(),
        strict=True,
        extra="forbid",
        context={"source": "fixture"},
        by_alias=True,
        by_name=True,
    )
    strings_value = DateValue.model_validate_strings(
        data,
        strict=False,
        extra="forbid",
        context={"source": "fixture"},
        by_alias=True,
        by_name=True,
    )
    assert json_value == strings_value
    assert json_value.value == "2026" and json_value.precision == "year"
