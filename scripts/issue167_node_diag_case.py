"""Separate fixed-Node diagnostic contract; importing performs no probe."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from scripts import issue167_resolver_case as base
from scripts import issue167_service_network_case as network
from scripts.issue167_dns_tls import pool_address

CaseRejected = base.CaseRejected
read_metadata = base.read_metadata
current_host_context = base.current_host_context
validate_ready = base.validate_ready
READY_FIELDS = base.READY_FIELDS
LIMITS = {
    "node_execs": 4,
    "lookup_calls": 2,
    "explicit_reference_dns_queries": 4,
    "reference_udp_sends": 2,
    "reference_tcp_connections": 2,
    "node_tcp53_control_connects": 1,
    "node_tcp53_landlock_connects": 1,
    "node_tls_connections": 2,
    "node_tls_handshakes": 2,
    "os_dns_queries": "unknown",
    "os_dns_wire_qname": "unknown",
    "os_tcp_fallback_attempts": "unknown",
    "application_retries": 0,
    "fallbacks": 0,
    "http_requests": 0,
    "auth_cli": 0,
    "model_prompts": 0,
    "pi_execs": 0,
    "ipv6_network_connections": 0,
    "new_crashes": 0,
}
NODE_FIELDS = {
    "category",
    "result",
    "uid",
    "core_zero",
    "no_new_privs",
    "cap_eff_zero",
    "cgroup_matches",
    "lock_inherited",
    "cleanup_complete",
    "lookup_calls",
    "tls_calls",
    "address",
    "tls_version",
}


@dataclass(frozen=True)
class Case(base.Case):
    worker_timeout_s: int = 100
    owner_timeout_s: int = 150

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
            or self.worker_timeout_s != 100
            or type(self.owner_timeout_s) is not int
            or self.owner_timeout_s != 150
        ):
            raise CaseRejected("case_deadline_unknown")

    def to_dict(self) -> dict[str, object]:
        value = super().to_dict()
        for key in (
            "network_operations",
            "node_pi",
            "synthetic_auth_execs",
            "synthetic_model_execs",
        ):
            value.pop(key)
        value.update(
            kind="h1_fixed_node_diagnostic",
            network_limits=dict(LIMITS),
            owner_configuration_confirmation="external_entry_flag_required",
            owner_unknown_dns_confirmation="scope_A_external_entry_flag_required",
        )
        return value


def load_case(path: Path, *, owner: int = 0) -> Case:
    return cast(Case, Case.from_dict(read_metadata(path, owner=owner)))


def render_unit(case: base.Case) -> str:
    return (
        network.render_unit(case)
        .replace("bounded service DNS/TLS preflight", "fixed Node no-secret diagnostic")
        .replace("network-worker-entry.py", "node-worker-entry.py")
        .replace("RuntimeMaxSec=80s", "RuntimeMaxSec=110s")
    )


def verify_installation(
    root: Path, expected_sha: str | None = None
) -> tuple[base.Case, dict[str, Path], str]:
    result = base.verify_installation(root, expected_sha, case_loader=load_case)
    manifest = read_metadata(root / "manifest.json", owner=0)
    if type(manifest) is not dict or not {
        "issue167_node_diag_case.py",
        "issue167_node_diag_worker.py",
        "issue167_node_diag_owner.py",
        "node-worker-entry.py",
        "node-binding.json",
        "nss-context.json",
        "issue167_node_diag_supply.py",
    } <= set(manifest["members"]):
        raise CaseRejected("node_members_missing")
    import scripts.issue167_node_diag_supply as supply

    supply.load_binding(root / "node-binding.json")
    check_nss(root)
    return result


def check_nss(root: Path) -> None:
    expected = read_metadata(root / "nss-context.json", owner=0)
    if (
        type(expected) is not dict
        or set(expected) != {"nsswitch_sha256", "hostname_contains_dot"}
        or expected["hostname_contains_dot"] is not False
        or "." in os.uname().nodename
    ):
        raise CaseRejected("nss_context_unknown")
    fd = os.open("/etc/nsswitch.conf", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        raw = source.read(16385)
    if len(raw) > 16384 or base.digest(raw) != expected["nsswitch_sha256"]:
        raise CaseRejected("nss_context_unknown")


def validate_node(
    value: object, *, mode: str, uid: int, address: str | None = None
) -> dict[str, object]:
    lookup = mode == "lookup_tls"
    if (
        mode not in {"tcp53_control", "tcp53_landlock", "lookup_tls"}
        or type(value) is not dict
        or set(value) != NODE_FIELDS
    ):
        raise CaseRejected("node_metadata_unknown")
    if (
        value["category"] != mode
        or value["result"] != "observed_expected"
        or type(value["uid"]) is not int
        or value["uid"] != uid
        or any(
            value[k] is not True
            for k in (
                "core_zero",
                "no_new_privs",
                "cap_eff_zero",
                "cgroup_matches",
                "lock_inherited",
                "cleanup_complete",
            )
        )
        or any(
            type(value[k]) is not int or value[k] != int(lookup)
            for k in ("lookup_calls", "tls_calls")
        )
        or value["address"] != (address if lookup else None)
        or (
            value["tls_version"] not in {"TLSv1.2", "TLSv1.3"}
            if lookup
            else value["tls_version"] is not None
        )
    ):
        raise CaseRejected("node_metadata_unknown")
    if lookup:
        pool_address(cast(str, address))
    return cast(dict[str, object], value)


def number(value: object) -> float:
    if type(value) not in (int, float):
        raise CaseRejected("node_ttl_unknown")
    try:
        result = float(cast(float, value))
    except (ValueError, OverflowError):
        raise CaseRejected("node_ttl_unknown") from None
    if not math.isfinite(result):
        raise CaseRejected("node_ttl_unknown")
    return result


def validate_window(
    start: object, end: object, expiry: object, received: list[float]
) -> None:
    a, b, c = number(start), number(end), number(expiry)
    if not max(number(x) for x in received) <= a <= b < c:
        raise CaseRejected("node_ttl_unknown")


def validate_stage(case: base.Case, sequence: int, value: object) -> dict[str, object]:
    if (
        type(value) is not dict
        or value.get("run_id") != case.run_id
        or type(value.get("sequence")) is not int
        or value["sequence"] != sequence
    ):
        raise CaseRejected("node_stage_unknown")
    keys = {"run_id", "sequence", "node", "child_reaped", "supply_protection"}
    if sequence in {3, 4}:
        keys |= {"reference", "started_monotonic", "completed_monotonic"}
    if (
        set(value) != keys
        or value["child_reaped"] is not True
        or value["supply_protection"]
        != "diagnostic_readonly_original_instance_lock_not_product_use_install"
    ):
        raise CaseRejected("node_stage_unknown")
    if sequence in {1, 2}:
        validate_node(
            value["node"],
            mode="tcp53_control" if sequence == 1 else "tcp53_landlock",
            uid=case.uid,
        )
    elif sequence in {3, 4}:
        refs = value["reference"]
        if type(refs) is not list or len(refs) != 2:
            raise CaseRejected("node_reference_unknown")
        for ref, transport in zip(refs, ("udp", "tcp"), strict=True):
            if (
                type(ref) is not dict
                or set(ref) != {"transport", "address", "ttl", "received_monotonic"}
                or ref["transport"] != transport
                or type(ref["ttl"]) is not int
                or ref["ttl"] <= 0
            ):
                raise CaseRejected("node_reference_unknown")
            pool_address(ref["address"])
            number(ref["received_monotonic"])
        if refs[0]["address"] != refs[1]["address"]:
            raise CaseRejected("node_reference_unknown")
        validate_node(
            value["node"], mode="lookup_tls", uid=case.uid, address=refs[0]["address"]
        )
        validate_window(
            value["started_monotonic"],
            value["completed_monotonic"],
            min(number(r["received_monotonic"]) + r["ttl"] for r in refs),
            [r["received_monotonic"] for r in refs],
        )
    else:
        raise CaseRejected("node_stage_unknown")
    return cast(dict[str, object], value)


def validate_result(case: base.Case, value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != READY_FIELDS | {
        "scope",
        "result",
        "stages",
        "limits",
        "pi_execs",
        "auth_calls",
        "model_calls",
    }:
        raise CaseRejected("worker_result_unknown")
    validate_ready(case, {k: value[k] for k in READY_FIELDS})
    if (
        value["scope"] != "fixed_node_no_secret_diagnostic"
        or value["result"] != "observed_expected"
        or json.dumps(value["limits"], sort_keys=True)
        != json.dumps(LIMITS, sort_keys=True)
        or any(
            type(value[k]) is not int or value[k] != 0
            for k in ("pi_execs", "auth_calls", "model_calls")
        )
        or type(value["stages"]) is not list
        or len(value["stages"]) != 4
    ):
        raise CaseRejected("worker_result_unknown")
    for sequence, row in enumerate(value["stages"], 1):
        validate_stage(case, sequence, row)
    return cast(dict[str, object], value)
