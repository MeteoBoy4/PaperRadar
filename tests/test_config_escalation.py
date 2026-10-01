"""A2-04 参数 Contract 的集合语义和受控身份。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    SuggestionRuleVersion,
    check_config,
    compile_config,
)
from tests.config_reuse_support import reuse_inputs
from tests.config_test_support import imported_modules


@pytest.mark.parametrize("triggers", ["[3]", "[2, 3]", "[3, 2]", "[1, 2, 3, 4, 5]"])
def test_legal_research_value_sets_are_compiled_without_threshold_conversion(
    tmp_path: Path, triggers: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = tmp_path / "config/screening/reuse-escalation-v1.yaml"
    path.write_text(path.read_text().replace("[3]", triggers))
    result = compile_config(settings, db)
    assert result.escalation is not None
    expected = {
        "[3]": (3,),
        "[2, 3]": (2, 3),
        "[3, 2]": (2, 3),
        "[1, 2, 3, 4, 5]": (1, 2, 3, 4, 5),
    }[triggers]
    assert result.escalation.reuse_escalation_research_values == expected
    assert result.escalation.excerpt_priority == ("availability", "methods")
    assert result.escalation.excerpt_selector_version == "v1"
    assert result.escalation.suggestion_rule_version == "v1"
    with pytest.raises(FrozenInstanceError):
        result.escalation.suggestion_rule_version = SuggestionRuleVersion.V1  # type: ignore[misc]


def test_omitted_research_value_set_has_explicit_v1_default(tmp_path: Path) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = tmp_path / "config/screening/reuse-escalation-v1.yaml"
    path.write_text(
        path.read_text().replace("reuse_escalation_research_values: [3]\n", "")
    )
    result = check_config(settings, db)
    assert result.escalation is not None
    assert result.escalation.reuse_escalation_research_values == (3,)


@pytest.mark.parametrize(
    "triggers",
    [
        "[]",
        "null",
        "3",
        "[3, 3]",
        "[0]",
        "[6]",
        "[true]",
        "[false, 3]",
        "[3.0]",
        "['3']",
    ],
)
def test_invalid_research_value_sets_fail_with_sanitized_field_path(
    tmp_path: Path, triggers: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = tmp_path / "config/screening/reuse-escalation-v1.yaml"
    path.write_text(path.read_text().replace("[3]", triggers))
    for operation in (check_config, compile_config):
        with pytest.raises(
            ConfigError, match=r"escalation\.reuse_escalation_research_values"
        ):
            operation(settings, db)


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        (
            "excerpt_selector_version: v1",
            "excerpt_selector_version: secret-marker",
            "excerpt_selector_version",
        ),
        (
            "suggestion_rule_version: v1",
            "suggestion_rule_version: secret-marker",
            "suggestion_rule_version",
        ),
        (
            "excerpt_selector_version: v1",
            "excerpt_selector_version: true",
            "excerpt_selector_version",
        ),
        (
            "suggestion_rule_version: v1",
            "suggestion_rule_version: null",
            "suggestion_rule_version",
        ),
        ("[availability, methods]", "[methods, availability]", "excerpt_priority"),
        ("[availability, methods]", "[availability, availability]", "excerpt_priority"),
        ("[availability, methods]", "[]", "excerpt_priority"),
        (
            "[availability, methods]",
            "[availability, secret-marker]",
            "excerpt_priority",
        ),
        ("version: reuse-escalation-v1", "version: wrong-version", "version"),
        ("version: reuse-escalation-v1\n", "", "version"),
        ("excerpt_priority: [availability, methods]\n", "", "excerpt_priority"),
        ("excerpt_selector_version: v1\n", "", "excerpt_selector_version"),
        ("suggestion_rule_version: v1\n", "", "suggestion_rule_version"),
        ("[3]", "[3]\nresearch_value_triggers: [2]", "research_value_triggers"),
        (
            "[3]",
            "[3]\nreuse_escalation_research_value: 3",
            "reuse_escalation_research_value",
        ),
        ("[3]", "[3]\napi_key: secret-marker", "api_key"),
    ],
)
def test_fixed_priority_controlled_versions_and_closed_fields(
    tmp_path: Path, old: str, new: str, field: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = tmp_path / "config/screening/reuse-escalation-v1.yaml"
    path.write_text(path.read_text().replace(old, new))
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=rf"escalation\.{field}") as error:
            operation(settings, db)
        assert "secret-marker" not in str(error.value)


@pytest.mark.parametrize("version", ["../outside", "V1", " v1", "secret-marker/value"])
def test_escalation_selector_has_controlled_version_format(
    tmp_path: Path, version: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    settings.write_text(
        settings.read_text().replace("reuse-escalation-v1", f"'{version}'")
    )
    with pytest.raises(ConfigError, match=r"settings\.escalation") as error:
        check_config(settings, db)
    assert version not in str(error.value)


def test_new_parameter_versions_can_share_set_semantics_with_distinct_raw_identity(
    tmp_path: Path,
) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = tmp_path / "config/screening/reuse-escalation-v1.yaml"
    path.write_text(path.read_text().replace("[3]", "[2, 3]"))
    first = compile_config(settings, db)
    raw_v2 = (
        path.read_text()
        .replace("reuse-escalation-v1", "reuse-escalation-v2")
        .replace("[2, 3]", "[3, 2]")
    )
    (path.parent / "reuse-escalation-v2.yaml").write_text(raw_v2)
    settings.write_text(
        settings.read_text().replace("reuse-escalation-v1", "reuse-escalation-v2")
    )
    second = compile_config(settings, db)
    assert first.snapshot_id != second.snapshot_id
    assert first.escalation == second.escalation
    assert second.escalation is not None
    assert second.escalation.reuse_escalation_research_values == (2, 3)
    first_entry = next(
        m
        for m in json.loads(first.payload_json)["materials"]
        if m["kind"] == "escalation"
    )
    second_entry = next(
        m
        for m in json.loads(second.payload_json)["materials"]
        if m["kind"] == "escalation"
    )
    assert first_entry["raw_sha256"] != second_entry["raw_sha256"]
    assert first_entry["version"] == "reuse-escalation-v1"
    assert second_entry["version"] == "reuse-escalation-v2"


def test_ordered_fixture_hash_keeps_list_order() -> None:
    from paper_radar.config.identity import canonical_json

    # 隔离的有序列表 fixture。不把反转摘录顺序变成合法生产配置。
    first = canonical_json({"sequence_fixture": ["a", "b"]})
    second = canonical_json({"sequence_fixture": ["b", "a"]})
    assert first == b'{"sequence_fixture":["a","b"]}'
    assert second == b'{"sequence_fixture":["b","a"]}'
    assert hashlib.sha256(first).digest() != hashlib.sha256(second).digest()


def test_escalation_types_have_no_yaml_database_or_cli_dependencies() -> None:
    module = (
        Path(__file__).resolve().parents[1] / "src/paper_radar/config/escalation.py"
    )
    imports = imported_modules(module)
    assert not imports & {"yaml", "sqlite3", "sqlalchemy", "alembic", "typer"}
    assert not any(name.startswith("paper_radar.storage") for name in imports)
