"""Independent T1 contract; preparation is never execution authorization."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import issue167_live_case as previous
from scripts import issue167_resolver_case as base

CaseRejected = base.CaseRejected
read_metadata = base.read_metadata
current_host_context = base.current_host_context
RUN = "8b31f0a9d672"
SCOPE = "live_value_low_project_duplex_timeout_only"
AUTH_REFRESH_PLAN = "conditional_zero_or_one"
CASE_NAME = "value-low-T1"
MATERIAL_KIND = "synthetic_T1_value_low_only"
LIMITS = {
    "auth_cli_upper": 1,
    "explicit_prompts_upper": 1,
    "model_execs_upper": 1,
    "node_execs_upper": 2,
    "application_retries": 0,
    "external_signals": 0,
    "model_http_lower_bound": 0,
    "model_http_upper": "unknown",
    "refresh_http_lower_bound": 0,
    "refresh_http_upper": "unknown",
    "auth_logical_refresh_plan": AUTH_REFRESH_PLAN,
    "logical_refresh_observation": "not_independently_observed",
    "os_dns_queries": "unknown",
    "os_tcp_fallback_attempts": "unknown",
    "token_authority": "pi_reported_usage_or_unknown",
    "ipv6_network_connections": 0,
    "new_crashes": 0,
    "public_total_seconds": 300,
    "duplex_switch_upper": 1,
}
AUTH_INPUT_REQUIREMENTS = {
    "source": "conditional_H2_plan_requires_separate_owner_approval",
    "provider": "openai",
    "credential_type": "oauth",
    "subscription_scope": "chatgpt.tokens.use.direct",
    "extra_providers": False,
    "command_credentials": False,
    "models_configuration": "absent",
    "models_store_at_owner_review": "no_new_content_claim",
    "compile_cache_at_owner_review": "no_new_content_claim",
    "expires_unit": "milliseconds",
    "current_access_expiry": "not_read_or_inferred",
    "next_auth_logical_refresh_plan": AUTH_REFRESH_PLAN,
    "refresh_may_network_and_persist": True,
    "agent_content_verification": False,
    "directory_lifecycle": "persistent_separate_from_model_attempt",
}
CONTEXT_LIMIT = 8 * 1024 * 1024


@dataclass(frozen=True)
class Case(base.Case):
    worker_timeout_s: int = 720
    owner_timeout_s: int = 900
    case_fingerprint: str = field(kw_only=True)

    def __post_init__(self) -> None:
        base.Case(
            self.run_id,
            self.uid,
            self.gid,
            self.profile_sha256,
            self.resolver_sha256,
            self.apport_sha256,
        )
        if (
            self.run_id != RUN
            or type(self.worker_timeout_s) is not int
            or self.worker_timeout_s != 720
            or type(self.owner_timeout_s) is not int
            or self.owner_timeout_s != 900
            or type(self.case_fingerprint) is not str
            or re.fullmatch(r"[a-f0-9]{64}", self.case_fingerprint) is None
        ):
            raise CaseRejected("timeout_case_binding_unknown")

    def to_dict(self) -> dict[str, object]:
        value = super().to_dict()
        for key in (
            "network_operations",
            "node_pi",
            "auth_calls",
            "model_calls",
            "synthetic_auth_execs",
            "synthetic_model_execs",
        ):
            value.pop(key)
        value.update(
            kind="h1_live_t1_duplex_timeout",
            scope=SCOPE,
            limits=dict(LIMITS),
            consumer="value",
            thinking="low",
            observation_choice="S",
            auth_input_requirements=dict(AUTH_INPUT_REQUIREMENTS),
            external_execution_authorization_required=True,
            binding_phase="preparation_snapshot_activation_time_recheck_required",
            case_fingerprint=self.case_fingerprint,
        )
        return value

    @classmethod
    def from_dict(cls, value: object) -> Case:
        if type(value) is not dict:
            raise CaseRejected("timeout_case_binding_unknown")
        try:
            result = cls(
                **{
                    key: value[key]
                    for key in (
                        "run_id",
                        "uid",
                        "gid",
                        "profile_sha256",
                        "resolver_sha256",
                        "apport_sha256",
                        "worker_timeout_s",
                        "owner_timeout_s",
                        "case_fingerprint",
                    )
                }
            )
        except (KeyError, TypeError):
            raise CaseRejected("timeout_case_binding_unknown") from None
        if not _same(result.to_dict(), value):
            raise CaseRejected("timeout_case_binding_unknown")
        return result


def render_unit(case: Case) -> str:
    return (
        previous.render_unit(case)
        .replace("six-cell controlled Pi batch", "single T1 duplex timeout")
        .replace("live-worker-entry.py", "timeout-worker-entry.py")
        .replace("RuntimeMaxSec=2580s", "RuntimeMaxSec=780s")
    )


def load_case(path: Path, *, owner: int = 0) -> Case:
    return Case.from_dict(read_metadata(path, owner=owner))


def verify_installation(
    root: Path, expected_sha: str | None = None
) -> tuple[base.Case, dict[str, Path], str]:
    result = base.verify_installation(root, expected_sha, case_loader=load_case)
    manifest = read_metadata(root / "manifest.json", owner=0)
    if type(manifest) is not dict or not {
        "issue167_live_timeout_case.py",
        "issue167_live_timeout_worker.py",
        "issue167_live_timeout_owner.py",
        "issue167_live_timeout_cleanup.py",
        "issue167_live_worker.py",
        "issue167_live_runtime.py",
        "issue167_live_resources.py",
        "issue167_live_ipc.py",
        "issue167_session_observation.py",
        "timeout-worker-entry.py",
        "live-context.json",
        "materials.zip",
    } <= set(manifest["members"]):
        raise CaseRejected("timeout_members_missing")
    context = read_metadata(root / "live-context.json", owner=0, limit=CONTEXT_LIMIT)
    if (
        type(context) is not dict
        or set(context)
        != {
            "kind",
            "supply",
            "synthetic_manifest_sha256",
            "nsswitch_sha256",
            "hostname_contains_dot",
            "application_runtime",
            "auth_input_declaration",
            "observation_choice",
        }
        or context["kind"]
        != "live_t1_preparation_snapshot_activation_time_recheck_required"
        or context["hostname_contains_dot"] is not False
        or context["observation_choice"] != "S"
        or not _same(context["auth_input_declaration"], AUTH_INPUT_REQUIREMENTS)
    ):
        raise CaseRejected("timeout_context_unknown")
    previous.check_site(root)
    return result


def _utc(value: object) -> datetime:
    try:
        if type(value) is not str or len(value) > 64:
            raise ValueError
        stamp = datetime.fromisoformat(value)
        offset = stamp.utcoffset()
        if stamp.tzinfo is None or offset is None or offset.total_seconds() != 0:
            raise ValueError
        return stamp
    except (ValueError, TypeError, AttributeError):
        raise CaseRejected("timeout_auth_observation_unknown") from None


def validate_snapshot(value: object) -> dict[str, Any]:
    if (
        type(value) is not dict
        or set(value)
        != {
            "scope",
            "integrity",
            "nodes",
            "node_count",
            "max_nodes",
            "max_depth",
            "regular_contents_read",
            "marker_content_used_as_authority",
            "write_history",
            "writer_identity",
        }
        or not _same(
            {k: value[k] for k in value if k not in {"nodes", "node_count"}},
            {
                "scope": "bounded_auth_and_cache_metadata_only",
                "integrity": "complete",
                "max_nodes": 64,
                "max_depth": 6,
                "regular_contents_read": False,
                "marker_content_used_as_authority": False,
                "write_history": "not_assessed",
                "writer_identity": "not_assessed",
            },
        )
    ):
        raise CaseRejected("timeout_auth_snapshot_unknown")
    nodes = value["nodes"]
    top = {
        ".",
        "auth.json",
        "models-store.json",
        "exp2-installation-id",
        "node-compile-cache",
    }
    if (
        type(nodes) is not dict
        or not top <= set(nodes)
        or type(value["node_count"]) is not int
        or value["node_count"] != len(nodes)
        or not 5 <= len(nodes) <= 64
    ):
        raise CaseRejected("timeout_auth_snapshot_unknown")
    for name, row in nodes.items():
        if (
            type(name) is not str
            or (name not in top and not name.startswith("node-compile-cache/"))
            or "\x00" in name
        ):
            raise CaseRejected("timeout_auth_snapshot_unknown")
        if name != ".":
            parts = name.split("/")
            try:
                components_valid = all(len(p.encode()) <= 255 for p in parts)
            except UnicodeError:
                components_valid = False
            if (
                len(parts) > 6
                or not components_valid
                or any(p in {"", ".", ".."} for p in parts)
                or (len(parts) > 1 and "/".join(parts[:-1]) not in nodes)
            ):
                raise CaseRejected("timeout_auth_snapshot_unknown")
        if (
            type(row) is not dict
            or set(row) != {"inode", "size", "mtime_ns", "ctime_ns"}
            or any(type(v) is not int or v < 0 for v in row.values())
            or row["inode"] == 0
        ):
            raise CaseRejected("timeout_auth_snapshot_unknown")
    if len({row["inode"] for row in nodes.values()}) != len(nodes):
        raise CaseRejected("timeout_auth_snapshot_unknown")
    if len(json.dumps(value, sort_keys=True).encode()) > 16384:
        raise CaseRejected("timeout_auth_snapshot_unknown")
    return value


def auth_reference(value: object) -> dict[str, object]:
    if type(value) is not dict or type(value.get("filesystem_snapshot")) is not dict:
        raise CaseRejected("timeout_auth_observation_unknown")
    captured = value["filesystem_snapshot"]
    snapshot = validate_snapshot(captured.get("snapshot"))
    return {
        "scope": "persistent_auth_checkpoint_reference",
        "run_id": value["run_id"],
        "sequence": value["sequence"],
        "phase": value["phase"],
        "result": value["result"],
        "started_at_utc": captured["started_at_utc"],
        "finished_at_utc": captured["finished_at_utc"],
        "snapshot_node_count": snapshot["node_count"],
    }


def validate_persistent_auth(value: object, *, run_id: str) -> None:
    if (
        type(value) is not dict
        or set(value)
        != {
            "scope",
            "history",
            "lifecycle",
            "input_source",
            "before",
            "after",
            "execution_interval",
        }
        or not _same(
            {
                k: value.get(k)
                for k in ("scope", "history", "lifecycle", "input_source")
            },
            {
                "scope": "persistent_auth_directory_separate_from_model",
                "history": "not_assessed",
                "lifecycle": "persistent_not_deleted",
                "input_source": "conditional_H2_plan",
            },
        )
    ):
        raise CaseRejected("timeout_auth_observation_unknown")
    for phase in ("before", "after"):
        row = value[phase]
        if (
            type(row) is not dict
            or set(row)
            != {
                "scope",
                "run_id",
                "sequence",
                "phase",
                "result",
                "refresh",
                "metadata",
                "filesystem_snapshot",
            }
            or not _same(
                {
                    k: row[k]
                    for k in row
                    if k not in {"metadata", "filesystem_snapshot"}
                },
                {
                    "scope": "persistent_auth_metadata_checkpoint",
                    "run_id": run_id,
                    "sequence": 1,
                    "phase": phase,
                    "result": "metadata_verified"
                    if phase == "before"
                    else "authentication_completed",
                    "refresh": "possible_not_independently_observed",
                },
            )
        ):
            raise CaseRejected("timeout_auth_observation_unknown")
        previous.validate_auth_metadata(row["metadata"])
        captured = row["filesystem_snapshot"]
        if (
            type(captured) is not dict
            or set(captured) != {"snapshot", "started_at_utc", "finished_at_utc"}
            or _utc(captured["started_at_utc"]) > _utc(captured["finished_at_utc"])
        ):
            raise CaseRejected("timeout_auth_snapshot_unknown")
        validate_snapshot(captured["snapshot"])
    interval = value["execution_interval"]
    if (
        type(interval) is not dict
        or set(interval)
        != {
            "scope",
            "started_at_utc",
            "returned_at_utc",
            "outcome",
            "exact_cli_pid_or_writer_attribution",
        }
        or interval["scope"] != "public_prepare_launch_including_auth"
        or interval["outcome"] != "returned_prepared"
        or interval["exact_cli_pid_or_writer_attribution"] != "not_assessed"
    ):
        raise CaseRejected("timeout_auth_observation_unknown")
    times = [
        _utc(t)
        for t in (
            value["before"]["filesystem_snapshot"]["finished_at_utc"],
            interval["started_at_utc"],
            interval["returned_at_utc"],
            value["after"]["filesystem_snapshot"]["started_at_utc"],
        )
    ]
    if times != sorted(times):
        raise CaseRejected("timeout_auth_observation_unknown")
    before_nodes = value["before"]["filesystem_snapshot"]["snapshot"]["nodes"]
    after_nodes = value["after"]["filesystem_snapshot"]["snapshot"]["nodes"]
    if before_nodes["."]["inode"] != after_nodes["."]["inode"] or not _same(
        before_nodes["exp2-installation-id"], after_nodes["exp2-installation-id"]
    ):
        raise CaseRejected("timeout_auth_observation_unknown")


validate_ready = base.validate_ready


def validate_preflight(value: object) -> dict[str, Any]:
    from scripts import issue167_live_ipc as ipc

    if (
        type(value) is not dict
        or set(value)
        != {
            "result",
            "ipc_integrity",
            "ipc",
            "synthetic_snapshots_registered",
            "credential_contents_read",
            "observer_backend_initialized",
        }
        or not _same(
            {k: value[k] for k in value if k != "ipc"},
            {
                "result": "observed_expected",
                "ipc_integrity": "complete",
                "synthetic_snapshots_registered": 1,
                "credential_contents_read": False,
                "observer_backend_initialized": True,
            },
        )
    ):
        raise CaseRejected("timeout_preflight_unknown")
    row = value["ipc"]
    if (
        type(row) is not dict
        or set(row) != ipc.RECEIPT_FIELDS
        or not _same(
            {k: row[k] for k in row if k != "steps"},
            {
                "scope": "self_owned_synthetic_ipc_matrix",
                "result": "observed_expected",
                "integrity": "complete",
                "counts_semantics": (
                    "entered_bounded_probe_not_syscall_or_process_success"
                ),
                "pair_entries": 7,
                "peer_operations_entered": 14,
                "limits": ipc.LIMITS,
            },
        )
        or type(row["steps"]) is not list
        or len(row["steps"]) != 7
    ):
        raise CaseRejected("timeout_preflight_unknown")
    for i, (step, name) in enumerate(zip(row["steps"], ipc.CATEGORIES, strict=True), 1):
        if not _same(
            step,
            {
                "sequence": i,
                "category": name,
                "control": "observed_allowed",
                "denial": "observed_permission_denial",
                "control_errno_category": "none",
                "denial_errno_category": "permission",
                "cleanup_complete": True,
            },
        ):
            raise CaseRejected("timeout_preflight_unknown")
    return value


def validate_result(case: base.Case, value: object) -> dict[str, Any]:
    if (
        type(value) is not dict
        or set(value)
        != base.READY_FIELDS
        | {
            "scope",
            "result",
            "limits",
            "preflight",
            "case",
            "selection_restoration",
            "auth_metadata_journal",
            "selection_journal",
        }
        or value["scope"] != SCOPE
        or value["result"] not in {"observed_expected", "not_triggered"}
        or not _same(value["limits"], LIMITS)
    ):
        raise CaseRejected("timeout_result_unknown")
    base.validate_ready(case, {k: value[k] for k in base.READY_FIELDS})
    validate_preflight(value["preflight"])
    row = validate_row(value["case"], run_id=case.run_id)
    if (
        row["result"] != value["result"]
        or row["fingerprint"] != getattr(case, "case_fingerprint", None)
        or not _same(
            value["selection_restoration"],
            {
                "result": "original_selection_restored",
                "append_only_history_retained": True,
            },
        )
        or not _same(
            value["auth_metadata_journal"],
            [auth_reference(row["persistent_auth"][k]) for k in ("before", "after")],
        )
    ):
        raise CaseRejected("timeout_result_unknown")
    journal = value["selection_journal"]
    if type(journal) is not list or len(journal) not in {2, 3}:
        raise CaseRejected("timeout_selection_restore_unknown")
    for i, entry in enumerate(journal):
        previous.validate_receipt_journal_entry(i, entry, run_id=case.run_id)
    if (
        journal[0]["action"] != "original"
        or journal[1]["action"] != "batch_activation"
        or (len(journal) == 3 and journal[2]["action"] != "restore_activation")
    ):
        raise CaseRejected("timeout_selection_restore_unknown")
    if not _same(
        {k: v for k, v in journal[-1]["selection"].items() if k != "activation_id"},
        {k: v for k, v in journal[0]["selection"].items() if k != "activation_id"},
    ):
        raise CaseRejected("timeout_selection_restore_unknown")
    return value


def preparation_blockers() -> tuple[str, ...]:
    return ("single_case_external_H1_H2_H3_required",)


def _same(value: object, expected: object) -> bool:
    return json.dumps(value, sort_keys=True) == json.dumps(expected, sort_keys=True)


def _finite(value: object, *, positive: bool = False) -> bool:
    import math

    if type(value) is not int and type(value) is not float:
        return False
    return math.isfinite(value) and (value > 0 if positive else value >= 0)


def validate_marker(value: object, *, run_id: str, fingerprint: str) -> dict[str, Any]:
    expected = {
        "scope": SCOPE,
        "run_id": run_id,
        "category": "decoded_nonempty_text_duplex_window",
        "sequence": 1,
        "count": 1,
        "fingerprint": fingerprint,
        "prompt_frames_completed": 1,
        "prompt_ack_count": 1,
        "agent_settled": False,
        "closing": False,
        "integrity": "complete",
    }
    sequence_keys = (
        "prompt_ack_sequence",
        "agent_start_sequence",
        "text_delta_sequence",
    )
    if (
        type(value) is not dict
        or set(value) != {*expected, *sequence_keys, "observed_monotonic"}
        or not _same({k: value.get(k) for k in expected}, expected)
        or type(fingerprint) is not str
        or re.fullmatch(r"[a-f0-9]{64}", fingerprint) is None
        or any(
            type(value[k]) is not int or not 0 < value[k] <= 50000
            for k in sequence_keys
        )
        or len({value[k] for k in sequence_keys}) != 3
        or value["text_delta_sequence"] <= max(value[k] for k in sequence_keys[:2])
        or not _finite(value["observed_monotonic"], positive=True)
    ):
        raise CaseRejected("timeout_marker_unknown")
    return value


def validate_timeout(value: object, *, run_id: str, fingerprint: str) -> dict[str, Any]:
    fields = {
        "phase",
        "marker_publications",
        "marker",
        "public_reason",
        "public_started_monotonic",
        "public_returned_monotonic",
        "public_elapsed_seconds",
        "model_factory_count",
        "public_terminate_returned",
        "owner_reconciliation_required",
        "model_error_terminal_count",
        "factory_entered_monotonic",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or value["phase"] != "complete"
        or type(value["marker_publications"]) is not int
        or value["marker_publications"] not in (0, 1)
        or type(value["model_factory_count"]) is not int
        or value["model_factory_count"] != 1
        or value["public_terminate_returned"] is not True
        or value["owner_reconciliation_required"] is not True
        or type(value["model_error_terminal_count"]) is not int
        or value["model_error_terminal_count"] not in (0, 1)
        or value["public_reason"]
        not in {"candidate", "timeout", "model_rejected", "stop_reason"}
        or any(
            not _finite(value[k], positive=True)
            for k in (
                "public_started_monotonic",
                "public_returned_monotonic",
                "public_elapsed_seconds",
                "factory_entered_monotonic",
            )
        )
        or abs(
            value["public_returned_monotonic"]
            - value["public_started_monotonic"]
            - value["public_elapsed_seconds"]
        )
        > 1e-6
    ):
        raise CaseRejected("timeout_observation_unknown")
    if (
        not value["public_started_monotonic"]
        <= value["factory_entered_monotonic"]
        <= value["public_returned_monotonic"]
    ):
        raise CaseRejected("timeout_observation_unknown")
    if value["marker_publications"]:
        marker = validate_marker(
            value["marker"], run_id=run_id, fingerprint=fingerprint
        )
        if (
            not value["factory_entered_monotonic"]
            <= marker["observed_monotonic"]
            <= value["public_returned_monotonic"]
        ):
            raise CaseRejected("timeout_observation_unknown")
    elif value["marker"] is not None:
        raise CaseRejected("timeout_observation_unknown")
    if (
        value["public_reason"] == "timeout" and value["public_elapsed_seconds"] < 300
    ) or (
        value["public_reason"] == "stop_reason"
        and value["model_error_terminal_count"] != 1
    ):
        raise CaseRejected("timeout_not_proven")
    return value


def validate_protocol(value: object) -> None:
    names = {
        "response",
        "agent_start",
        "turn_start",
        "message_start",
        "message_update",
        "message_end",
        "turn_end",
        "agent_end",
        "agent_settled",
        "thinking_level_changed",
    }
    fields = {
        "event_counts",
        "total_records",
        "prompt_frames_completed",
        "prompt_ack_count",
        "first_prompt_ack_sequence",
        "first_agent_start_sequence",
    }
    if type(value) is not dict or set(value) != fields:
        raise CaseRejected("timeout_protocol_unknown")
    counts = value["event_counts"]
    if (
        type(counts) is not dict
        or set(counts) != names
        or any(type(v) is not int or not 0 <= v <= 50000 for v in counts.values())
        or type(value["total_records"]) is not int
        or not 0 < value["total_records"] == sum(counts.values()) <= 50000
        or type(value["prompt_frames_completed"]) is not int
        or value["prompt_frames_completed"] != 1
        or type(value["prompt_ack_count"]) is not int
        or value["prompt_ack_count"] not in (0, 1)
        or counts["agent_start"] not in (0, 1)
        or counts["agent_settled"] not in (0, 1)
    ):
        raise CaseRejected("timeout_protocol_unknown")
    for key, count in (
        ("first_prompt_ack_sequence", value["prompt_ack_count"]),
        ("first_agent_start_sequence", counts["agent_start"]),
    ):
        if (count == 0 and value[key] is not None) or (
            count == 1
            and (
                type(value[key]) is not int
                or not 0 < value[key] <= value["total_records"]
            )
        ):
            raise CaseRejected("timeout_protocol_unknown")


def validate_row(value: object, *, run_id: str) -> dict[str, Any]:
    fields = {
        "scope",
        "run_id",
        "case",
        "result",
        "timeout",
        "window",
        "candidate_committed",
        "auth_cli_completed",
        "protocol_metadata",
        "persistent_auth",
        "tokens",
        "token_status",
        "request_counts",
        "fingerprint",
        "requested_identity",
        "rpc_initial_state_clean",
        "rpc_commands_empty",
        "normal_candidate_validated",
        "normal_completion",
        "started_at_utc",
        "verified_at_utc",
        "started_monotonic",
        "verified_monotonic",
        "elapsed_seconds",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or value["scope"] != SCOPE
        or value["run_id"] != run_id
        or value["case"] != CASE_NAME
        or value["auth_cli_completed"] is not True
        or value["candidate_committed"] is not False
        or value["rpc_initial_state_clean"] is not True
        or value["rpc_commands_empty"] is not True
        or type(value["normal_candidate_validated"]) is not bool
        or value["result"] not in {"observed_expected", "not_triggered"}
        or not _same(
            value["requested_identity"],
            {
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
        )
        or not _same(
            value["request_counts"],
            {
                "model_http_lower_bound": 0,
                "model_http_upper": "unknown",
                "refresh_http_lower_bound": 0,
                "refresh_http_upper": "unknown",
                "meaning": "no_independent_HTTP_sender_observation",
            },
        )
    ):
        raise CaseRejected("timeout_result_unknown")
    timed = validate_timeout(
        value["timeout"], run_id=run_id, fingerprint=value["fingerprint"]
    )
    validate_protocol(value["protocol_metadata"])
    protocol = value["protocol_metadata"]
    if timed["marker_publications"]:
        marker = timed["marker"]
        if (
            marker["prompt_ack_sequence"] != protocol["first_prompt_ack_sequence"]
            or marker["agent_start_sequence"] != protocol["first_agent_start_sequence"]
            or marker["text_delta_sequence"] > protocol["total_records"]
            or protocol["event_counts"]["message_update"] < 1
        ):
            raise CaseRejected("timeout_protocol_unknown")
    expected = timed["public_reason"] == "timeout" and timed["marker_publications"] == 1
    if (value["result"] == "observed_expected") != expected:
        raise CaseRejected("timeout_not_proven")
    if expected and (
        protocol["prompt_ack_count"] != 1
        or protocol["event_counts"]["agent_start"] != 1
        or protocol["event_counts"]["agent_settled"] != 0
        or timed["model_error_terminal_count"] != 0
    ):
        raise CaseRejected("timeout_not_proven")
    if timed["public_reason"] == "candidate":
        if value["normal_candidate_validated"] is not True or not _same(
            value["normal_completion"],
            {
                "candidate_validated": True,
                "response_identity_matches": True,
                "agent_settled": True,
                "stdout_eof": True,
                "stderr_eof": True,
                "exit_zero": True,
                "public_terminate_returned": True,
            },
        ):
            raise CaseRejected("timeout_normal_completion_unknown")
    elif (
        value["normal_candidate_validated"] is not False
        or value["normal_completion"] is not None
    ):
        raise CaseRejected("timeout_normal_completion_unknown")
    previous.validate_window(value["window"], run_id=run_id)
    validate_persistent_auth(value["persistent_auth"], run_id=run_id)
    previous.validate_timing(value)
    auth = value["persistent_auth"]
    if not (
        _utc(value["started_at_utc"])
        <= _utc(auth["before"]["filesystem_snapshot"]["started_at_utc"])
        <= _utc(auth["before"]["filesystem_snapshot"]["finished_at_utc"])
        <= _utc(auth["execution_interval"]["started_at_utc"])
        <= _utc(auth["execution_interval"]["returned_at_utc"])
        <= _utc(auth["after"]["filesystem_snapshot"]["started_at_utc"])
        <= _utc(auth["after"]["filesystem_snapshot"]["finished_at_utc"])
        <= _utc(value["verified_at_utc"])
    ) or not (
        value["started_monotonic"]
        <= timed["public_started_monotonic"]
        <= timed["public_returned_monotonic"]
        <= value["verified_monotonic"]
    ):
        raise CaseRejected("timeout_auth_observation_unknown")
    tokens = value["tokens"]
    if tokens is None:
        if value["token_status"] != "unknown":
            raise CaseRejected("timeout_usage_unknown")
    elif (
        type(tokens) is not dict
        or set(tokens) != {"input", "output", "cacheRead", "cacheWrite", "totalTokens"}
        or any(type(v) is not int or v < 0 for v in tokens.values())
        or tokens["totalTokens"] <= 0
        or tokens["totalTokens"]
        != sum(tokens[k] for k in ("input", "output", "cacheRead", "cacheWrite"))
        or value["token_status"] != "pi_reported"
    ):
        raise CaseRejected("timeout_usage_unknown")
    return value
