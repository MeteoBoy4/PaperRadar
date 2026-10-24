"""A8 独立离线组与实际固定范围。"""

from pathlib import Path

from scripts.a2_full_acceptance import acceptance_groups


def test_a8_is_required_and_binds_all_actual_same_run_predecessors() -> None:
    group = next(group for group in acceptance_groups() if group.name == "A8")
    assert group.required is True
    assert group.dependencies == ("A1", "完整 A2", "A3", "A5", "A6", "A7")
    assert group.suffix == ".a8.json"
    assert next(group for group in acceptance_groups() if group.name == "A4").required


def test_a8_records_production_formats_and_only_offline_capabilities(
    tmp_path: Path,
) -> None:
    from tests.a8_acceptance_support import conclude, same_a8_run

    path, result = conclude(tmp_path, same_a8_run(tmp_path))
    assert result["status"] == "passed", result["reasons"]
    assert result["a8_verified"] is True
    assert result["migration_revision"] == "a704_screening_retry"
    assert (result["format_version"], result["issue"], result["parent_issue"]) == (
        1,
        85,
        85,
    )
    assert result["scope"] == "a8_rpc_offline_protocol_tasks"
    assert (
        result["rpc_verified"]
        is result["live_verified"]
        is result["stage_a_verified"]
        is False
    )
    assert result["format_versions"] == {
        "render": 1,
        "protocol_profiles": {"1.4.0": "pi-rpc-1.4.0-v1"},
        "screening_tasks": 1,
        "task_reason_catalog": 1,
        "task_query_result": 1,
        "stage_inputs": {"boundary": 1, "value": 1},
        "backup": 1,
    }
    assert len(result["test_execution"]) >= 14
    assert all(row["result"] == "passed" for row in result["test_execution"])
    assert set(result["capability_evidence"]) == set(result["capabilities"])
    assert all(value == "passed" for value in result["capabilities"].values())
    assert {
        "rpc_compatibility",
        "pi_execution",
        "original_title_language_production_source",
        "effective_system_instructions_cwd",
        "production_parameter_mapping",
        "provider_retry",
        "cache_warming",
        "automatic_network_activity",
        "actual_session_resource_permission_isolation",
        "derived_rules_live_verification",
        "stage_a",
        "live",
    } <= set(result["not_assessed"])
    assert path.name.endswith(".a8.json")
