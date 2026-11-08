"""Independent D1 T1 contract; synthetic evidence, no live input reads."""

import copy
import json
from typing import Any

import pytest

from scripts import issue167_live_timeout_case as case
from tests.test_issue167_live_signal_case import persistent_auth as earlier_auth
from tests.test_issue167_live_signal_case import row as earlier_row

FP = "a" * 64


def plan() -> case.Case:
    return case.Case(
        case.RUN, 1000, 1000, "b" * 64, "c" * 64, "d" * 64, case_fingerprint=FP
    )


def marker() -> dict[str, Any]:
    return {
        "scope": case.SCOPE,
        "run_id": case.RUN,
        "category": "decoded_nonempty_text_duplex_window",
        "sequence": 1,
        "count": 1,
        "fingerprint": FP,
        "prompt_frames_completed": 1,
        "prompt_ack_count": 1,
        "agent_settled": False,
        "closing": False,
        "integrity": "complete",
        "prompt_ack_sequence": 9,
        "agent_start_sequence": 10,
        "text_delta_sequence": 11,
        "observed_monotonic": 15.0,
    }


def timed(*, reason: str = "timeout", marked: bool = True) -> dict[str, Any]:
    duration = 300.1 if reason == "timeout" else 1.0
    return {
        "phase": "complete",
        "marker_publications": int(marked),
        "marker": marker() if marked else None,
        "public_reason": reason,
        "public_started_monotonic": 14.0,
        "public_returned_monotonic": 14.0 + duration,
        "factory_entered_monotonic": 14.001,
        "public_elapsed_seconds": duration,
        "model_factory_count": 1,
        "public_terminate_returned": True,
        "owner_reconciliation_required": True,
        "model_error_terminal_count": int(reason == "stop_reason"),
    }


def persistent_auth() -> dict[str, Any]:
    value = earlier_auth()
    value["input_source"] = "conditional_H2_plan"
    for phase in ("before", "after"):
        value[phase]["run_id"] = case.RUN
    return value


def row(*, reason: str = "timeout", marked: bool = True) -> dict[str, Any]:
    value = earlier_row(expected=reason != "candidate")
    del value["signal"]
    value.update(
        scope=case.SCOPE,
        run_id=case.RUN,
        case=case.CASE_NAME,
        timeout=timed(reason=reason, marked=marked),
        result="observed_expected"
        if reason == "timeout" and marked
        else "not_triggered",
        persistent_auth=persistent_auth(),
        verified_monotonic=315.0,
        elapsed_seconds=305.0,
        verified_at_utc="2026-11-08T00:05:05+00:00",
    )
    value["window"]["run_id"] = case.RUN
    # Existing public fixture protocol sequence totals are independent of the
    # new marker; add an actual text observation in the synthetic metadata.
    value["protocol_metadata"]["event_counts"]["message_update"] += 1
    value["protocol_metadata"]["total_records"] += 1
    return value


def test_case_is_independent_and_conditional_refresh_is_not_old_expiry() -> None:
    p = plan()
    payload: Any = p.to_dict()
    assert case.Case.from_dict(payload) == p
    assert (
        payload["auth_input_requirements"]["current_access_expiry"]
        == "not_read_or_inferred"
    )
    assert payload["limits"]["auth_logical_refresh_plan"] == "conditional_zero_or_one"
    assert "expired" not in json.dumps(p.to_dict())
    assert "timeout-worker-entry.py" in case.render_unit(p)


@pytest.mark.parametrize(
    "reason,marked",
    [
        ("timeout", True),
        ("timeout", False),
        ("candidate", False),
        ("candidate", True),
        ("model_rejected", False),
        ("stop_reason", False),
    ],
)
def test_timeout_normal_and_early_known_failure_have_distinct_scope(
    reason: str, marked: bool
) -> None:
    value = row(reason=reason, marked=marked)
    case.validate_row(value, run_id=case.RUN)
    assert value["timeout"]["owner_reconciliation_required"] is True


@pytest.mark.parametrize(
    "key,value",
    [
        ("text_delta_sequence", True),
        ("text_delta_sequence", 10),
        ("observed_monotonic", float("nan")),
        ("count", True),
        ("agent_settled", 0),
        ("fingerprint", "bad"),
        ("category", "packet"),
    ],
)
def test_marker_rejects_missing_or_aliased_reference(key: str, value: Any) -> None:
    m = marker()
    m[key] = value
    with pytest.raises(case.CaseRejected, match="timeout_marker_unknown"):
        case.validate_marker(m, run_id=case.RUN, fingerprint=FP)


@pytest.mark.parametrize(
    "reason", ["transport_error", "startup_error", "close_timeout", "event_sequence"]
)
def test_engineering_failure_never_becomes_not_triggered(reason: str) -> None:
    with pytest.raises(case.CaseRejected, match="timeout_observation_unknown"):
        case.validate_timeout(
            timed(reason=reason, marked=False), run_id=case.RUN, fingerprint=FP
        )


def test_sub_300_public_timeout_cannot_prove_deadline() -> None:
    value = timed()
    value["public_elapsed_seconds"] = 299.9
    value["public_returned_monotonic"] = 313.9
    with pytest.raises(case.CaseRejected, match="timeout_not_proven"):
        case.validate_timeout(value, run_id=case.RUN, fingerprint=FP)


def test_stop_reason_without_observed_error_enum_is_unknown() -> None:
    value = timed(reason="stop_reason", marked=False)
    value["model_error_terminal_count"] = 0
    with pytest.raises(case.CaseRejected, match="timeout_not_proven"):
        case.validate_timeout(value, run_id=case.RUN, fingerprint=FP)


def test_marker_must_follow_factory_before_public_return() -> None:
    value = timed()
    value["factory_entered_monotonic"] = 16.0
    with pytest.raises(case.CaseRejected, match="timeout_observation_unknown"):
        case.validate_timeout(value, run_id=case.RUN, fingerprint=FP)


def test_owner_switch_cannot_be_inferred_by_removing_reconciliation() -> None:
    value = row()
    value["timeout"]["owner_reconciliation_required"] = False
    with pytest.raises(case.CaseRejected, match="timeout_observation_unknown"):
        case.validate_row(value, run_id=case.RUN)


def test_auth_metadata_delta_does_not_rebind_old_owner_declaration() -> None:
    value = row()
    value["persistent_auth"]["input_source"] = "new_owner_current_input_declaration"
    with pytest.raises(case.CaseRejected, match="timeout_auth_observation_unknown"):
        case.validate_row(value, run_id=case.RUN)


def test_changed_installation_marker_is_unknown() -> None:
    value = row()
    value["persistent_auth"] = copy.deepcopy(value["persistent_auth"])
    value["persistent_auth"]["after"]["filesystem_snapshot"]["snapshot"]["nodes"][
        "exp2-installation-id"
    ]["ctime_ns"] += 1
    with pytest.raises(case.CaseRejected, match="timeout_auth_observation_unknown"):
        case.validate_row(value, run_id=case.RUN)


@pytest.mark.parametrize(
    "change", ["ack", "start", "text_out_of_range", "no_message_update"]
)
def test_marker_protocol_references_must_close(change: str) -> None:
    value = row()
    if change == "ack":
        value["timeout"]["marker"]["prompt_ack_sequence"] = 8
    elif change == "start":
        value["timeout"]["marker"]["agent_start_sequence"] = 8
    elif change == "text_out_of_range":
        value["timeout"]["marker"]["text_delta_sequence"] = 50000
    else:
        protocol = value["protocol_metadata"]
        protocol["total_records"] -= protocol["event_counts"]["message_update"]
        protocol["event_counts"]["message_update"] = 0
    with pytest.raises(case.CaseRejected, match="timeout_protocol_unknown"):
        case.validate_row(value, run_id=case.RUN)


def complete_worker(*, reason: str = "timeout", marked: bool = True) -> dict[str, Any]:
    from tests.test_issue167_live_signal_case import complete_worker as earlier_complete

    value = earlier_complete(expected=reason != "candidate")
    value.update(
        scope=case.SCOPE,
        run_id=case.RUN,
        limits=dict(case.LIMITS),
        case=row(reason=reason, marked=marked),
    )
    value["result"] = value["case"]["result"]
    value["auth_metadata_journal"] = [
        case.auth_reference(value["case"]["persistent_auth"][k])
        for k in ("before", "after")
    ]
    for entry in value["selection_journal"]:
        entry["run_id"] = case.RUN
    return value


@pytest.mark.parametrize(
    "reason", ["timeout", "candidate", "model_rejected", "stop_reason"]
)
def test_complete_worker_closes_auth_selection_and_timeout_references(
    reason: str,
) -> None:
    value = complete_worker(reason=reason, marked=reason == "timeout")
    case.validate_result(plan(), value)


def test_complete_worker_rejects_changed_original_selection() -> None:
    value = complete_worker()
    value["selection_journal"][-1]["selection"]["snapshot_id"] = "f" * 64
    with pytest.raises(case.CaseRejected, match="timeout_selection_restore_unknown"):
        case.validate_result(plan(), value)
