"""A6 独立验收公共结论。"""

from pathlib import Path

from scripts.a2_full_acceptance import acceptance_groups


def test_a6_is_required_and_declares_actual_same_run_predecessors() -> None:
    group = next(group for group in acceptance_groups() if group.name == "A6")
    assert group.required is True
    assert group.dependencies == ("A1", "完整 A2", "A3", "A5")
    assert group.suffix == ".a6.json"


def test_a6_records_actual_facts_formats_and_offline_boundaries(tmp_path: Path) -> None:
    from tests.a6_acceptance_support import conclude, same_a6_run

    _, result = conclude(tmp_path, same_a6_run(tmp_path))
    assert result["status"] == "passed", result["reasons"]
    assert result["a6_verified"] is True
    assert result["migration_revision"] == "a703_screening_success"
    assert (result["format_version"], result["issue"], result["parent_issue"]) == (
        1,
        75,
        67,
    )
    assert result["scope"] == "a6_paper_facts"
    assert (
        result["stage_a_verified"]
        is result["live_verified"]
        is result["rpc_verified"]
        is False
    )
    assert result["format_versions"] == {
        "paper_facts": 1,
        "doi_rules": 1,
        "text_norm": 1,
        "feed_item_fingerprint": 1,
        "reason_catalog": 1,
        "mapping_result": 1,
        "stage_inputs": {"boundary": 1, "value": 1},
        "backup": 1,
    }
    assert result["capabilities"] == dict.fromkeys(
        (
            "doi_identity",
            "feed_discovery",
            "version_selection",
            "field_arbitration",
            "consistent_read",
            "input_mapping",
            "historical_rebuild",
            "concurrency",
            "crash_recovery",
            "migration",
            "cli",
            "isolated_restore",
        ),
        "passed",
    )
    assert set(result["capability_evidence"]) == set(result["capabilities"])
    assert all(row["result"] == "passed" for row in result["test_execution"])

    assert {
        "merge_undo",
        "arxiv_pmid",
        "real_source_authenticity",
        "source_assumptions_guid_landing_page_elocator_entry_stability_crossref",
        "parser_completeness_and_stage_c_fixed_sample_upgrade_gate",
        "stage_c_strong_conflict_persistence_gate",
        "truncation_detection",
        "metadata_ready",
        "eligibility",
        "task_budget",
        "complete_visibility",
        "rpc_compatibility",
        "docling_execution",
        "nas_restore",
        "stage_a",
        "live",
    } <= set(result["not_assessed"])
    assert "paper_fact_mapping" not in result["not_assessed"]
