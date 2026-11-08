"""Closed contract for one separately approved six-cell experimental batch."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from scripts import issue167_resolver_case as base
from scripts import issue167_service_network_case as network

CaseRejected = base.CaseRejected
read_metadata = base.read_metadata
current_host_context = base.current_host_context
validate_ready = base.validate_ready
READY_FIELDS = base.READY_FIELDS
ORDER = (
    "boundary-low",
    "boundary-high",
    "value-low",
    "value-high",
    "read-low",
    "read-high",
)
LIMITS = {
    "auth_cli_upper": 6,
    "explicit_prompts_upper": 6,
    "model_execs_upper": 6,
    "node_execs_upper": 12,
    "application_retries": 0,
    "model_http": "unknown",
    "refresh_http": "unknown",
    "first_auth_logical_refresh_planned": 1,
    "later_auth_logical_refreshes": "unknown",
    "os_dns_queries": "unknown",
    "os_dns_wire_qname": "unknown",
    "os_tcp_fallback_attempts": "unknown",
    "token_authority": "pi_reported_usage",
    "ipv6_network_connections": 0,
    "new_crashes": 0,
}

AUTH_INPUT_DECLARATION = {
    "source": "owner_readonly_structure_review",
    "provider": "openai",
    "credential_type": "oauth",
    "subscription_scope": "chatgpt.tokens.use.direct",
    "extra_providers": False,
    "command_credentials": False,
    "models_configuration": "absent",
    "models_store_at_owner_review": "empty_object",
    "compile_cache_at_owner_review": "present",
    "expires_unit": "milliseconds",
    "access_at_owner_review": "expired",
    "first_auth_cli": "network_refresh_planned",
    "agent_content_verification": False,
    "directory_lifecycle": "persistent_separate_from_model_attempt",
}

CONTEXT_LIMIT = 8 * 1024 * 1024


@dataclass(frozen=True)
class Case(base.Case):
    worker_timeout_s: int = 2520
    owner_timeout_s: int = 2700

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
            type(self.worker_timeout_s) is not int
            or self.worker_timeout_s != 2520
            or type(self.owner_timeout_s) is not int
            or self.owner_timeout_s != 2700
        ):
            raise CaseRejected("case_deadline_unknown")

    def to_dict(self) -> dict[str, object]:
        value = super().to_dict()
        for key in (
            "network_operations",
            "node_pi",
            "synthetic_auth_execs",
            "synthetic_model_execs",
            "auth_calls",
            "model_calls",
        ):
            value.pop(key)
        value.update(
            kind="h1_live_six_normal_batch",
            limits=dict(LIMITS),
            cases=list(ORDER),
            external_execution_authorization_required=True,
            observation_choice="S",
            auth_input_declaration=dict(AUTH_INPUT_DECLARATION),
        )
        return value


def load_case(path: Path, *, owner: int = 0) -> Case:
    return cast(Case, Case.from_dict(read_metadata(path, owner=owner)))


def render_unit(case: base.Case) -> str:
    return (
        network.render_unit(case)
        .replace("bounded service DNS/TLS preflight", "six-cell controlled Pi batch")
        .replace("network-worker-entry.py", "live-worker-entry.py")
        .replace("RuntimeMaxSec=80s", "RuntimeMaxSec=2580s")
        .replace("TimeoutStopSec=10s", "TimeoutStopSec=60s")
    )


def verify_installation(
    root: Path, expected_sha: str | None = None
) -> tuple[base.Case, dict[str, Path], str]:
    result = base.verify_installation(root, expected_sha, case_loader=load_case)
    manifest = read_metadata(root / "manifest.json", owner=0)
    if type(manifest) is not dict or not {
        "issue167_live_case.py",
        "issue167_live_worker.py",
        "issue167_live_owner.py",
        "issue167_live_runtime.py",
        "issue167_live_resources.py",
        "issue167_live_ipc.py",
        "issue167_session_observation.py",
        "live-context.json",
        "materials.zip",
        "live-worker-entry.py",
    } <= set(manifest["members"]):
        raise CaseRejected("live_members_missing")
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
        or context["kind"] != "live_six_public_bindings"
        or context["hostname_contains_dot"] is not False
        or context["observation_choice"] != "S"
        or json.dumps(context["auth_input_declaration"], sort_keys=True)
        != json.dumps(AUTH_INPUT_DECLARATION, sort_keys=True)
    ):
        raise CaseRejected("live_context_unknown")
    check_site(root)
    return result


def check_site(root: Path) -> None:
    context = read_metadata(root / "live-context.json", owner=0, limit=CONTEXT_LIMIT)
    if type(context) is not dict or "." in os.uname().nodename:
        raise CaseRejected("live_site_unknown")
    fd = os.open("/etc/nsswitch.conf", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        raw = source.read(16385)
    if len(raw) > 16384 or base.digest(raw) != context["nsswitch_sha256"]:
        raise CaseRejected("live_site_unknown")


def validate_window(value: object, *, run_id: str) -> dict[str, object]:
    required = {
        "scope",
        "run_id",
        "source",
        "event_source",
        "result",
        "category",
        "sequence",
        "session_history",
        "session_mutation_events",
        "session_integrity",
        "guard_integrity",
        "unknown_mutation_events",
        "known_non_session_history",
        "non_session_event_lower_bounds",
        "event_count_semantics",
        "terminal_status",
        "terminal_inventory",
        "terminal_integrity",
        "directory_deleted",
        "cleanup_integrity",
        "post_terminal_write_events",
        "reasons",
        "settings_semantics",
    }
    if (
        type(value) is not dict
        or set(value) != required
        or value["scope"] != "classified_session_observation"
        or value["run_id"] != run_id
        or type(value["run_id"]) is not str
        or value["result"] != "session_window_complete"
        or value["source"] != "kernel_own_cgroup_metadata"
        or value["event_source"] != "inotify"
        or value["category"] != "attempt_files"
        or type(value["sequence"]) is not int
        or value["sequence"] != 1
        or value["session_history"] != "zero_observed"
        or any(
            value[k] != "complete"
            for k in (
                "session_integrity",
                "guard_integrity",
                "terminal_integrity",
                "cleanup_integrity",
            )
        )
        or any(
            type(value[k]) is not int or value[k] != 0
            for k in (
                "session_mutation_events",
                "unknown_mutation_events",
                "post_terminal_write_events",
            )
        )
        or value["known_non_session_history"] != "not_assessed"
        or value["event_count_semantics"]
        != "observed_inotify_records_lower_bound_not_write_count"
        or value["terminal_status"] != "classified_snapshot"
        or value["directory_deleted"] is not True
        or value["settings_semantics"] is not True
        or value["reasons"] != []
    ):
        raise CaseRejected("live_file_facts_unknown")
    counts = value["non_session_event_lower_bounds"]
    if (
        type(counts) is not dict
        or set(counts)
        != {
            "auth_store",
            "model_store",
            "store_lock",
            "compile_cache",
            "control_settings",
        }
        or any(type(x) is not int or not 0 <= x <= 100000 for x in counts.values())
    ):
        raise CaseRejected("live_file_facts_unknown")
    if sum(counts.values()) > 100000:
        raise CaseRejected("live_file_facts_unknown")
    inventory = value["terminal_inventory"]
    if type(inventory) is not dict or set(inventory) != {
        "baseline",
        "auth_store",
        "model_store",
        "store_lock",
        "compile_cache",
        "session",
        "unknown",
    }:
        raise CaseRejected("live_file_facts_unknown")
    for name, row in inventory.items():
        if (
            type(row) is not dict
            or set(row) != {"regular", "directory", "other"}
            or any(type(x) is not int or not 0 <= x <= 100000 for x in row.values())
            or row["other"] != 0
            or (name in {"session", "unknown"} and any(row.values()))
        ):
            raise CaseRejected("live_file_facts_unknown")
    if inventory["baseline"] != {"regular": 1, "directory": 3, "other": 0}:
        raise CaseRejected("live_file_facts_unknown")
    for name in ("auth_store", "model_store"):
        if inventory[name]["regular"] > 1 or inventory[name]["directory"] != 0:
            raise CaseRejected("live_file_facts_unknown")
    if (
        inventory["store_lock"]["regular"] != 0
        or inventory["store_lock"]["directory"] > 3
    ):
        raise CaseRejected("live_file_facts_unknown")
    if sum(sum(row.values()) for row in inventory.values()) > 100000:
        raise CaseRejected("live_file_facts_unknown")
    if (
        inventory["compile_cache"]["regular"]
        and not inventory["compile_cache"]["directory"]
    ):
        raise CaseRejected("live_file_facts_unknown")
    return cast(dict[str, object], value)


def validate_cell(sequence: int, value: object, *, run_id: str) -> dict[str, object]:
    keys = {
        "case",
        "sequence",
        "result",
        "auth_cli_completed",
        "model_factory_entered",
        "explicit_prompt_completed",
        "rpc_initial_state_clean",
        "rpc_commands_empty",
        "rpc_settled",
        "rpc_exit_zero",
        "public_terminate_returned",
        "business_validated",
        "model_identity_matches",
        "tokens",
        "request_counts",
        "window",
        "protocol_metadata",
        "started_at_utc",
        "verified_at_utc",
        "started_monotonic",
        "verified_monotonic",
        "elapsed_seconds",
        "persistent_auth",
    }
    if (
        type(sequence) is not int
        or not 1 <= sequence <= 6
        or type(value) is not dict
        or set(value) != keys
    ):
        raise CaseRejected("live_cell_unknown")
    if (
        value["case"] != ORDER[sequence - 1]
        or type(value["sequence"]) is not int
        or value["sequence"] != sequence
        or value["result"] != "observed_expected"
    ):
        raise CaseRejected("live_cell_unknown")
    for key in keys - {
        "case",
        "sequence",
        "result",
        "tokens",
        "request_counts",
        "window",
        "protocol_metadata",
        "started_at_utc",
        "verified_at_utc",
        "started_monotonic",
        "verified_monotonic",
        "elapsed_seconds",
        "persistent_auth",
    }:
        if value[key] is not True:
            raise CaseRejected("live_cell_unknown")
    tokens = value["tokens"]
    if (
        type(tokens) is not dict
        or set(tokens) != {"input", "output", "cacheRead", "cacheWrite", "totalTokens"}
        or any(type(v) is not int or v < 0 for v in tokens.values())
        or tokens["totalTokens"] <= 0
        or tokens["totalTokens"]
        != sum(tokens[k] for k in ("input", "output", "cacheRead", "cacheWrite"))
    ):
        raise CaseRejected("live_usage_unknown")
    if json.dumps(value["request_counts"], sort_keys=True) != json.dumps(
        {
            "model_http_lower_bound": 0,
            "model_http_upper": "unknown",
            "refresh_http_lower_bound": 0,
            "refresh_http_upper": "unknown",
            "meaning": "no_independent_HTTP_sender_observation",
        },
        sort_keys=True,
    ):
        raise CaseRejected("live_request_counts_unknown")
    validate_protocol(value["protocol_metadata"])
    validate_persistent_auth(value["persistent_auth"], sequence=sequence, run_id=run_id)
    validate_window(value["window"], run_id=run_id)
    validate_timing(value)
    return cast(dict[str, object], value)


def validate_auth_metadata(value: object) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value)
        != {
            "scope",
            "directory_private_owned",
            "auth_regular_private_owned",
            "models_configuration_absent",
            "models_store",
            "compile_cache",
            "contents_read",
            "content_shape_verified_by_agent",
        }
        or value["scope"] != "fixed_auth_metadata_paths_only"
        or any(
            value[k] is not True
            for k in (
                "directory_private_owned",
                "auth_regular_private_owned",
                "models_configuration_absent",
            )
        )
        or value["models_store"] not in {"absent", "regular_private_owned"}
        or value["compile_cache"] not in {"absent", "directory_owned"}
        or value["contents_read"] is not False
        or value["content_shape_verified_by_agent"] is not False
    ):
        raise CaseRejected("live_auth_metadata_unknown")
    return cast(dict[str, object], value)


def validate_auth_checkpoint(
    value: object, *, sequence: int, phase: str, run_id: str
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value)
        != {
            "scope",
            "run_id",
            "sequence",
            "phase",
            "result",
            "first_network_refresh_planned",
            "metadata",
        }
        or value["scope"] != "persistent_auth_metadata_checkpoint"
        or value["run_id"] != run_id
        or type(value["run_id"]) is not str
        or type(value["sequence"]) is not int
        or value["sequence"] != sequence
        or phase not in {"before", "after"}
        or value["phase"] != phase
        or value["result"]
        != ("metadata_verified" if phase == "before" else "authentication_completed")
        or value["first_network_refresh_planned"] is not (sequence == 1)
    ):
        raise CaseRejected("live_auth_checkpoint_unknown")
    validate_auth_metadata(value["metadata"])
    return cast(dict[str, object], value)


def validate_persistent_auth(
    value: object, *, sequence: int, run_id: str
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value)
        != {"scope", "history", "lifecycle", "input_source", "before", "after"}
        or value["scope"] != "persistent_auth_directory_separate_from_model"
        or value["history"] != "not_assessed"
        or value["lifecycle"] != "persistent_not_deleted"
        or value["input_source"] != "owner_readonly_structure_review"
    ):
        raise CaseRejected("live_auth_checkpoint_unknown")
    for phase in ("before", "after"):
        validate_auth_checkpoint(
            value[phase], sequence=sequence, phase=phase, run_id=run_id
        )
    return cast(dict[str, object], value)


def validate_timing(value: dict[str, object]) -> None:
    try:
        times = []
        for key in ("started_at_utc", "verified_at_utc"):
            raw = value[key]
            if type(raw) is not str:
                raise ValueError
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
                raise ValueError
            times.append(parsed)
        numbers = []
        for key in ("started_monotonic", "verified_monotonic", "elapsed_seconds"):
            number = value[key]
            if type(number) not in (int, float) or not math.isfinite(
                cast(float, number)
            ):
                raise ValueError
            numbers.append(cast(float, number))
        start, end, elapsed = numbers
        if times[1] < times[0] or not 0 <= start <= end or elapsed != end - start:
            raise ValueError
    except (KeyError, ValueError, TypeError, OverflowError):
        raise CaseRejected("live_verification_time_unknown") from None


def validate_result(case: base.Case, value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != READY_FIELDS | {
        "scope",
        "result",
        "cases",
        "limits",
        "selection_restoration",
        "preflight",
        "selection_journal",
        "auth_metadata_journal",
    }:
        raise CaseRejected("worker_result_unknown")
    validate_ready(case, {k: value[k] for k in READY_FIELDS})
    if (
        value["scope"] != "live_six_normal_batch"
        or value["result"] != "observed_expected"
        or json.dumps(value["limits"], sort_keys=True)
        != json.dumps(LIMITS, sort_keys=True)
        or json.dumps(value["selection_restoration"], sort_keys=True)
        != json.dumps(
            {
                "result": "original_selection_restored",
                "append_only_history_retained": True,
            },
            sort_keys=True,
        )
        or type(value["cases"]) is not list
        or len(value["cases"]) != 6
    ):
        raise CaseRejected("worker_result_unknown")
    for sequence, row in enumerate(value["cases"], 1):
        validate_cell(sequence, row, run_id=case.run_id)
    auth = value["auth_metadata_journal"]
    if type(auth) is not list or len(auth) != 12:
        raise CaseRejected("live_auth_checkpoint_unknown")
    for index, checkpoint in enumerate(auth):
        sequence, phase = index // 2 + 1, "before" if index % 2 == 0 else "after"
        validate_auth_checkpoint(
            checkpoint, sequence=sequence, phase=phase, run_id=case.run_id
        )
        if checkpoint != value["cases"][sequence - 1]["persistent_auth"][phase]:
            raise CaseRejected("live_auth_checkpoint_unknown")
    validate_preflight(value["preflight"])
    journal = value["selection_journal"]
    if type(journal) is not list or len(journal) != 8:
        raise CaseRejected("live_selection_journal_unknown")
    for sequence, row in enumerate(journal):
        validate_receipt_journal_entry(sequence, row, run_id=case.run_id)
        if row["action"] != (
            "original"
            if sequence == 0
            else "restore_activation"
            if sequence == 7
            else "batch_activation"
        ):
            raise CaseRejected("live_selection_journal_unknown")
    return cast(dict[str, object], value)


def validate_preflight(value: object) -> dict[str, object]:
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
        or value["result"] != "observed_expected"
        or value["ipc_integrity"] != "complete"
        or type(value["synthetic_snapshots_registered"]) is not int
        or value["synthetic_snapshots_registered"] != 2
        or value["credential_contents_read"] is not False
        or value["observer_backend_initialized"] is not True
    ):
        raise CaseRejected("live_preflight_unknown")
    r = value["ipc"]
    if (
        type(r) is not dict
        or set(r) != ipc.RECEIPT_FIELDS
        or r["scope"] != "self_owned_synthetic_ipc_matrix"
        or r["result"] != "observed_expected"
        or r["integrity"] != "complete"
        or r["counts_semantics"]
        != "entered_bounded_probe_not_syscall_or_process_success"
        or type(r["pair_entries"]) is not int
        or r["pair_entries"] != 7
        or type(r["peer_operations_entered"]) is not int
        or r["peer_operations_entered"] != 14
        or json.dumps(r["limits"], sort_keys=True)
        != json.dumps(ipc.LIMITS, sort_keys=True)
        or type(r["steps"]) is not list
        or len(r["steps"]) != 7
    ):
        raise CaseRejected("live_preflight_unknown")
    for seq, (row, category) in enumerate(
        zip(r["steps"], ipc.CATEGORIES, strict=True), 1
    ):
        expected = {
            "sequence": seq,
            "category": category,
            "control": "observed_allowed",
            "denial": "observed_permission_denial",
            "control_errno_category": "none",
            "denial_errno_category": "permission",
            "cleanup_complete": True,
        }
        if json.dumps(row, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise CaseRejected("live_preflight_unknown")
    return cast(dict[str, object], value)


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
    if type(value) is not dict or set(value) != {
        "event_counts",
        "total_records",
        "prompt_frames_completed",
        "prompt_ack_count",
        "first_prompt_ack_sequence",
        "first_agent_start_sequence",
    }:
        raise CaseRejected("live_protocol_metadata_unknown")
    counts = value["event_counts"]
    if (
        type(counts) is not dict
        or set(counts) != names
        or any(type(v) is not int or not 0 <= v <= 50000 for v in counts.values())
    ):
        raise CaseRejected("live_protocol_metadata_unknown")
    required = {
        "response": 9,
        "agent_start": 1,
        "turn_start": 1,
        "message_start": 3,
        "message_end": 3,
        "turn_end": 1,
        "agent_end": 1,
        "agent_settled": 1,
    }
    if any(counts[k] != v for k, v in required.items()):
        raise CaseRejected("live_protocol_metadata_unknown")
    total = value["total_records"]
    if (
        type(total) is not int
        or total != sum(counts.values())
        or not 1 <= total <= 50000
    ):
        raise CaseRejected("live_protocol_metadata_unknown")
    if any(
        type(value[k]) is not int or value[k] != 1
        for k in ("prompt_frames_completed", "prompt_ack_count")
    ):
        raise CaseRejected("live_protocol_metadata_unknown")
    if (
        any(
            type(value[k]) is not int or not 1 <= value[k] <= total
            for k in ("first_prompt_ack_sequence", "first_agent_start_sequence")
        )
        or value["first_prompt_ack_sequence"] == value["first_agent_start_sequence"]
    ):
        raise CaseRejected("live_protocol_metadata_unknown")


def _validate_journal_entry(
    sequence: int, value: object, *, run_id: str, root_field: str
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"run_id", "sequence", "action", "selection"}
        or value["run_id"] != run_id
        or type(value["sequence"]) is not int
        or value["sequence"] != sequence
        or (
            value["action"]
            not in {"original", "batch_activation", "restore_activation"}
            or (sequence == 0) != (value["action"] == "original")
        )
    ):
        raise CaseRejected("live_selection_journal_unknown")
    row = value["selection"]
    if (
        type(row) is not dict
        or set(row)
        != {
            "activation_id",
            "supply_id",
            "install_id",
            "snapshot_id",
            "root_id",
            root_field,
        }
        or type(row["activation_id"]) is not int
        or row["activation_id"] < 1
    ):
        raise CaseRejected("live_selection_journal_unknown")
    for key, length in (
        ("supply_id", 64),
        ("install_id", 32),
        ("snapshot_id", 64),
        ("root_id", 32),
    ):
        v = row[key]
        if (
            type(v) is not str
            or len(v) != length
            or any(c not in "0123456789abcdef" for c in v)
        ):
            raise CaseRejected("live_selection_journal_unknown")
    if root_field == "root_path":
        if (
            type(row[root_field]) is not str
            or not Path(row[root_field]).is_absolute()
            or ".." in Path(row[root_field]).parts
            or str(Path(row[root_field])) != row[root_field]
        ):
            raise CaseRejected("live_selection_journal_unknown")
    elif (
        type(row[root_field]) is not str
        or len(row[root_field]) != 64
        or any(c not in "0123456789abcdef" for c in row[root_field])
    ):
        raise CaseRejected("live_selection_journal_unknown")
    return cast(dict[str, object], value)


def validate_journal_entry(
    sequence: int, value: object, *, run_id: str
) -> dict[str, object]:
    """Private control record; its real path is required for CAS and recovery."""
    return _validate_journal_entry(
        sequence, value, run_id=run_id, root_field="root_path"
    )


def validate_receipt_journal_entry(
    sequence: int, value: object, *, run_id: str
) -> dict[str, object]:
    return _validate_journal_entry(
        sequence, value, run_id=run_id, root_field="root_path_identity"
    )


def project_journal_entry(
    sequence: int, value: object, *, run_id: str
) -> dict[str, object]:
    raw = validate_journal_entry(sequence, value, run_id=run_id)
    selection = dict(cast(dict[str, object], raw["selection"]))
    root_path = cast(str, selection.pop("root_path"))
    selection["root_path_identity"] = base.digest(root_path.encode())
    projected = {**raw, "selection": selection}
    return validate_receipt_journal_entry(sequence, projected, run_id=run_id)
