"""Independent E01 closed evidence D1; all identities and metadata are synthetic."""

import json
from typing import Any

import pytest

from scripts import issue167_live_ipc as ipc
from scripts import issue167_live_signal_case as case
from tests.test_issue167_live_batch import auth_metadata
from tests.test_issue167_live_batch import cell as previous_cell

FP = "a" * 64


def plan() -> case.Case:
    return case.Case(
        case.RUN, 1000, 1000, "b" * 64, "c" * 64, "d" * 64, case_fingerprint=FP
    )


def snapshot(*, near_cap: bool = False) -> dict[str, Any]:
    def build(width: int) -> dict[str, Any]:
        names = [
            ".",
            "auth.json",
            "models-store.json",
            "exp2-installation-id",
            "node-compile-cache",
        ]
        if near_cap:
            names += ["node-compile-cache/v1"]
            names += [
                "node-compile-cache/v1/" + f"{i:02d}" + "x" * width for i in range(58)
            ]
        nodes = {
            name: {
                "inode": i + 1,
                "size": 2 if name == "models-store.json" else 4096,
                "mtime_ns": 1000000000 + i,
                "ctime_ns": 1000000000 + i,
            }
            for i, name in enumerate(names)
        }
        return {
            "scope": "bounded_auth_and_cache_metadata_only",
            "integrity": "complete",
            "nodes": nodes,
            "node_count": len(nodes),
            "max_nodes": 64,
            "max_depth": 6,
            "regular_contents_read": False,
            "marker_content_used_as_authority": False,
            "write_history": "not_assessed",
            "writer_identity": "not_assessed",
        }

    value = build(1)
    if near_cap:
        for width in range(2, 254):
            candidate = build(width)
            if len(json.dumps(candidate, sort_keys=True).encode()) > 16384:
                break
            value = candidate
    case.validate_snapshot(value)
    return value


def persistent_auth(*, near_cap: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "scope": "persistent_auth_directory_separate_from_model",
        "history": "not_assessed",
        "lifecycle": "persistent_not_deleted",
        "input_source": "new_owner_current_input_declaration",
        "execution_interval": {
            "scope": "public_prepare_launch_including_auth",
            "started_at_utc": "2026-11-08T00:00:01+00:00",
            "returned_at_utc": "2026-11-08T00:00:02+00:00",
            "outcome": "returned_prepared",
            "exact_cli_pid_or_writer_attribution": "not_assessed",
        },
    }
    for phase, seconds in [("before", 0), ("after", 3)]:
        result[phase] = {
            "scope": "persistent_auth_metadata_checkpoint",
            "run_id": case.RUN,
            "sequence": 1,
            "phase": phase,
            "result": "metadata_verified"
            if phase == "before"
            else "authentication_completed",
            "refresh": "possible_not_independently_observed",
            "metadata": auth_metadata(),
            "filesystem_snapshot": {
                "snapshot": snapshot(near_cap=near_cap),
                "started_at_utc": f"2026-11-08T00:00:0{seconds}+00:00",
                "finished_at_utc": f"2026-11-08T00:00:0{seconds}+00:00",
            },
        }
    return result


def preflight() -> dict[str, Any]:
    return {
        "result": "observed_expected",
        "ipc_integrity": "complete",
        "synthetic_snapshots_registered": 1,
        "credential_contents_read": False,
        "observer_backend_initialized": True,
        "ipc": {
            "scope": "self_owned_synthetic_ipc_matrix",
            "result": "observed_expected",
            "integrity": "complete",
            "counts_semantics": "entered_bounded_probe_not_syscall_or_process_success",
            "pair_entries": 7,
            "peer_operations_entered": 14,
            "limits": dict(ipc.LIMITS),
            "steps": [
                {
                    "sequence": i,
                    "category": name,
                    "control": "observed_allowed",
                    "denial": "observed_permission_denial",
                    "control_errno_category": "none",
                    "denial_errno_category": "permission",
                    "cleanup_complete": True,
                }
                for i, name in enumerate(ipc.CATEGORIES, 1)
            ],
        },
    }


def row(*, expected: bool = True, near_cap: bool = False) -> dict[str, Any]:
    old = previous_cell(1)
    window = old["window"]
    window["run_id"] = case.RUN
    protocol = old["protocol_metadata"]
    if expected:
        protocol["event_counts"]["agent_settled"] = 0
        protocol["total_records"] -= 1
    result = {
        "scope": case.SCOPE,
        "run_id": case.RUN,
        "case": "value-low-E01",
        "result": "observed_expected" if expected else "not_triggered",
        "signal": {
            "phase": "complete",
            "marker_publications": 1 if expected else 0,
            "sigint_received": 1 if expected else 0,
            "effective_sigint_received": 1 if expected else 0,
            "late_sigint_received": 0,
            "same_keyboard_interrupt_propagated": expected,
            "partial_candidate_accepted": False,
            "public_terminate_returned": True,
            "model_factory_count": 1,
        },
        "window": window,
        "candidate_committed": False,
        "auth_cli_completed": True,
        "fingerprint": FP,
        "requested_identity": {
            "provider": "openai",
            "model": "gpt-6.1-sol",
            "stage": "value",
            "thinking_level": "low",
            "protocol": "prompt_only",
            "sampling": "provider_default",
            "temperature": None,
            "top_p": None,
            "auth_mode": "chatgpt_subscription",
        },
        "rpc_initial_state_clean": True,
        "rpc_commands_empty": True,
        "normal_candidate_validated": not expected,
        "normal_completion": None
        if expected
        else {
            "candidate_validated": True,
            "response_identity_matches": True,
            "agent_settled": True,
            "stdout_eof": True,
            "stderr_eof": True,
            "exit_zero": True,
            "public_terminate_returned": True,
        },
        "protocol_metadata": protocol,
        "persistent_auth": persistent_auth(near_cap=near_cap),
        "tokens": None
        if expected
        else {
            "input": 10,
            "output": 3,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 13,
        },
        "token_status": "unknown" if expected else "pi_reported",
        "request_counts": {
            "model_http_lower_bound": 0,
            "model_http_upper": "unknown",
            "refresh_http_lower_bound": 0,
            "refresh_http_upper": "unknown",
            "meaning": "no_independent_HTTP_sender_observation",
        },
        "started_at_utc": "2026-11-08T00:00:00+00:00",
        "verified_at_utc": "2026-11-08T00:00:05+00:00",
        "started_monotonic": 10.0,
        "verified_monotonic": 15.0,
        "elapsed_seconds": 5.0,
    }
    case.validate_row(result, run_id=case.RUN)
    return result


def complete_worker(*, expected: bool = True, near_cap: bool = False) -> dict[str, Any]:
    result_row = row(expected=expected, near_cap=near_cap)
    journals = []
    for i, action in enumerate(["original", "batch_activation", "restore_activation"]):
        journals.append(
            {
                "run_id": case.RUN,
                "sequence": i,
                "action": action,
                "selection": {
                    "activation_id": 8 + i,
                    "supply_id": "1" * 64,
                    "install_id": "2" * 32,
                    "snapshot_id": ("3" if i != 1 else "4") * 64,
                    "root_id": "5" * 32,
                    "root_path_identity": "6" * 64,
                },
            }
        )
    result = {
        "run_id": case.RUN,
        "pid": 1234,
        "uid": 1000,
        "core_limits": [0, 0],
        "no_new_privs": True,
        "cap_eff_zero": True,
        "cgroup_matches": True,
        "resolver_sha256": "c" * 64,
        "mount_namespace": "mnt:[20]",
        "pid_namespace": "pid:[30]",
        "scope": case.SCOPE,
        "result": result_row["result"],
        "limits": dict(case.LIMITS),
        "preflight": preflight(),
        "case": result_row,
        "selection_restoration": {
            "result": "original_selection_restored",
            "append_only_history_retained": True,
        },
        "auth_metadata_journal": [
            case.auth_reference(result_row["persistent_auth"][p])
            for p in ["before", "after"]
        ],
        "selection_journal": journals,
    }
    case.validate_result(plan(), result)
    return result


def test_complete_case_and_worker_schema_accept_only_the_distinct_results() -> None:
    for expected in [True, False]:
        case.validate_result(plan(), complete_worker(expected=expected))


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "sum",
        "duplicate_start",
        "missing_start",
        "settled_interruption",
        "normal_proof",
        "snapshot_extra",
        "snapshot_phase",
        "auth_reference",
    ],
)
def test_missing_or_conflicting_evidence_is_unknown(mutation: str) -> None:
    value = complete_worker()
    r = value["case"]
    if mutation == "extra":
        r["raw_stream"] = "synthetic-forbidden"
    elif mutation == "missing":
        del r["persistent_auth"]
    elif mutation == "sum":
        r.update(
            tokens={
                "input": 2,
                "output": 1,
                "cacheRead": 0,
                "cacheWrite": 0,
                "totalTokens": 99,
            },
            token_status="pi_reported",
        )
    elif mutation == "duplicate_start":
        r["protocol_metadata"]["event_counts"]["agent_start"] = 2
        r["protocol_metadata"]["total_records"] += 1
    elif mutation == "missing_start":
        r["protocol_metadata"]["event_counts"]["agent_start"] = 0
        r["protocol_metadata"]["total_records"] -= 1
    elif mutation == "settled_interruption":
        r["protocol_metadata"]["event_counts"]["agent_settled"] = 1
        r["protocol_metadata"]["total_records"] += 1
    elif mutation == "normal_proof":
        r["normal_completion"] = {"candidate_validated": True}
    elif mutation == "snapshot_extra":
        r["persistent_auth"]["before"]["filesystem_snapshot"]["snapshot"]["nodes"][
            "auth.json"
        ]["mode"] = 0o600
    elif mutation == "snapshot_phase":
        r["persistent_auth"]["before"]["phase"] = "after"
    else:
        value["auth_metadata_journal"][0]["snapshot_node_count"] += 1
    reason = {
        "extra": "signal_result_unknown",
        "missing": "signal_result_unknown",
        "sum": "signal_usage_unknown",
        "duplicate_start": "signal_protocol_unknown",
        "missing_start": "signal_protocol_unknown",
        "settled_interruption": "signal_protocol_unknown",
        "normal_proof": "signal_not_proven",
        "snapshot_extra": "signal_auth_snapshot_unknown",
        "snapshot_phase": "signal_auth_observation_unknown",
        "auth_reference": "signal_result_unknown",
    }[mutation]
    with pytest.raises(case.CaseRejected, match=reason):
        case.validate_result(plan(), value)


def test_near_cap_snapshots_are_real_structured_values_not_padding() -> None:
    worker = complete_worker(near_cap=True)
    snapshots = [
        worker["case"]["persistent_auth"][p]["filesystem_snapshot"]["snapshot"]
        for p in ["before", "after"]
    ]
    assert all(
        16000 <= len(json.dumps(v, sort_keys=True).encode()) <= 16384 for v in snapshots
    )
    assert len(json.dumps(worker).encode()) < 65536
    assert all(len(ref) == 8 for ref in worker["auth_metadata_journal"])


@pytest.mark.parametrize("kind", ["duplicate_inode", "long_component", "surrogate"])
def test_snapshot_schema_rejects_alias_or_unrepresentable_path(kind: str) -> None:
    value = snapshot()
    if kind == "duplicate_inode":
        value["nodes"]["auth.json"]["inode"] = value["nodes"]["."]["inode"]
    else:
        name = "node-compile-cache/" + (
            "x" * 256 if kind == "long_component" else "\udcff"
        )
        value["nodes"][name] = {"inode": 999, "size": 0, "mtime_ns": 1, "ctime_ns": 1}
        value["node_count"] += 1
    with pytest.raises(case.CaseRejected, match="signal_auth_snapshot_unknown"):
        case.validate_snapshot(value)


def test_auth_snapshot_interval_must_belong_to_this_case() -> None:
    value = row()
    for phase in ("before", "after"):
        captured = value["persistent_auth"][phase]["filesystem_snapshot"]
        for key in ("started_at_utc", "finished_at_utc"):
            captured[key] = captured[key].replace("2026", "2025")
    interval = value["persistent_auth"]["execution_interval"]
    for key in ("started_at_utc", "returned_at_utc"):
        interval[key] = interval[key].replace("2026", "2025")
    with pytest.raises(case.CaseRejected, match="signal_auth_observation_unknown"):
        case.validate_row(value, run_id=case.RUN)


@pytest.mark.parametrize("length", [2, 3])
def test_restore_journal_must_end_at_original_semantics(length: int) -> None:
    value = complete_worker()
    value["selection_journal"] = value["selection_journal"][:length]
    value["selection_journal"][-1]["selection"]["snapshot_id"] = "9" * 64
    with pytest.raises(case.CaseRejected, match="signal_selection_restore_unknown"):
        case.validate_result(plan(), value)


def test_prompt_ack_cannot_exist_without_a_response_record() -> None:
    value = row()
    protocol = value["protocol_metadata"]
    protocol["total_records"] -= protocol["event_counts"]["response"]
    protocol["event_counts"]["response"] = 0
    with pytest.raises(case.CaseRejected, match="signal_protocol_unknown"):
        case.validate_row(value, run_id=case.RUN)


@pytest.mark.parametrize("kind", ["root_replaced", "marker_modified"])
def test_auth_metadata_delta_rejects_unexpected_root_or_marker_changes(
    kind: str,
) -> None:
    value = persistent_auth()
    nodes = value["after"]["filesystem_snapshot"]["snapshot"]["nodes"]
    if kind == "root_replaced":
        nodes["."]["inode"] = 999
    else:
        nodes["exp2-installation-id"]["ctime_ns"] += 1
    with pytest.raises(case.CaseRejected, match="signal_auth_observation_unknown"):
        case.validate_persistent_auth(value, run_id=case.RUN)


def test_auth_file_atomic_replacement_is_recorded_without_claiming_history() -> None:
    value = persistent_auth()
    snapshot_after = value["after"]["filesystem_snapshot"]["snapshot"]
    snapshot_after["nodes"]["auth.json"]["inode"] = 999
    case.validate_persistent_auth(value, run_id=case.RUN)
    assert snapshot_after["write_history"] == "not_assessed"
