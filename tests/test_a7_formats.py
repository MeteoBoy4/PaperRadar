"""A7 使用生产格式;同时保留原来的四份 Frozen Contract。"""

from dataclasses import fields


def test_task_query_has_explicit_production_format_and_kind() -> None:
    from paper_radar.screening_tasks.errors import REASON_CATALOG_VERSION
    from paper_radar.screening_tasks.models import TASKS_FORMAT_VERSION
    from paper_radar.screening_tasks.query_models import (
        TASK_QUERY_FORMAT_VERSION,
        TaskQueryResult,
    )

    for version in (
        TASKS_FORMAT_VERSION,
        REASON_CATALOG_VERSION,
        TASK_QUERY_FORMAT_VERSION,
    ):
        assert type(version) is int and version == 1
    defaults = {field.name: field for field in fields(TaskQueryResult)}
    assert defaults["kind"].default == "task_query_result"
    assert defaults["kind"].init is False
    assert type(defaults["format_version"].default) is int
    assert defaults["format_version"].default == 1
    assert defaults["format_version"].init is False


def test_a7_keeps_contract_set_and_does_not_hash_its_own_scope() -> None:
    from scripts.a7_scope import REQUIRED_SOURCE_MODULES, REQUIRED_TEST_CASE_COUNTS
    from scripts.offline_evidence import CONTRACT_NAMES

    assert CONTRACT_NAMES == (
        "boundary",
        "value-prediction",
        "reuse-assessment",
        "decision-reasons",
    )
    paths = {path for path, _ in REQUIRED_SOURCE_MODULES}
    assert "scripts/a7_scope.py" not in paths
    assert "src/paper_radar/screening/validation.py" in paths
    assert REQUIRED_TEST_CASE_COUNTS["tests/test_screening_strict_json.py"] == 93
