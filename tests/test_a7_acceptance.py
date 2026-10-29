"""A7 独立验收公共结论。"""

from pathlib import Path

from scripts.a2_full_acceptance import acceptance_groups


def test_a7_is_required_and_declares_actual_same_run_predecessors() -> None:
    group = next(group for group in acceptance_groups() if group.name == "A7")
    assert group.required is True
    assert group.dependencies == ("A1", "完整 A2", "A3", "A5", "A6")
    assert group.suffix == ".a7.json"
    assert next(group for group in acceptance_groups() if group.name == "A4").required


def test_a7_records_actual_task_formats_and_offline_boundaries(tmp_path: Path) -> None:
    from tests.a7_acceptance_support import conclude, same_a7_run

    _, result = conclude(tmp_path, same_a7_run(tmp_path))
    assert result["status"] == "passed", result["reasons"]
    assert result["a7_verified"] is True
    assert result["migration_revision"] == "feed06_language_provenance"
    assert (result["format_version"], result["issue"], result["parent_issue"]) == (
        1,
        84,
        76,
    )
    assert result["scope"] == "a7_screening_tasks"
    assert (
        result["stage_a_verified"]
        is result["live_verified"]
        is result["rpc_verified"]
        is False
    )
    assert result["format_versions"] == {
        "screening_tasks": 1,
        "task_reason_catalog": 1,
        "task_query_result": 1,
        "stage_inputs": {"boundary": 1, "value": 1},
        "backup": 1,
    }
    assert result["capabilities"] == dict.fromkeys(
        (
            "frozen_input",
            "request_idempotency",
            "budget_scope",
            "atomic_claim",
            "lease",
            "bounded_attempts",
            "authoritative_acceptance",
            "derived_applicability",
            "explicit_retry",
            "shared_query",
            "crash_recovery",
            "migration",
            "isolated_restore",
            "semantic_integrity",
            "privacy",
        ),
        "passed",
    )
    assert set(result["capability_evidence"]) == set(result["capabilities"])
    assert all(row["result"] == "passed" for row in result["test_execution"])
    assert {
        "rpc_compatibility",
        "pi_execution",
        "real_model_usage_cost",
        "original_title_language_production_wiring",
        "metadata_ready",
        "complete_eligibility",
        "daily_quota",
        "two_stage_orchestration",
        "suggestions_decisions",
        "calibration_visibility",
        "reuse_tasks",
        "extraction_tasks",
        "read_tasks",
        "merge_budget",
        "screening_cli",
        "paper_trace_cli",
        "nas_restore",
        "stage_a",
        "live",
    } <= set(result["not_assessed"])
