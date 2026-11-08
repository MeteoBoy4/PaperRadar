"""Closed, separately authorized service DNS/TLS preflight contract."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from scripts import issue167_resolver_case as base
from scripts.issue167_dns_tls import SocketOperations, pool_address

CaseRejected = base.CaseRejected
read_metadata = base.read_metadata
current_host_context = base.current_host_context
validate_ready = base.validate_ready
READY_FIELDS = base.READY_FIELDS
LIMITS = {
    "dns_queries": 5,
    "dns_udp_sends": 3,
    "dns_tcp_connection_attempts": 3,
    "tls_tcp_connection_attempts": 2,
    "tls_handshakes": 2,
    "http_requests": 0,
    "auth_cli": 0,
    "model_prompts": 0,
    "node_pi": False,
    "ipv6_probes": 0,
    "new_crashes": 0,
    "retries": 0,
    "fallbacks": 0,
}


@dataclass(frozen=True)
class Case(base.Case):
    worker_timeout_s: int = 70
    owner_timeout_s: int = 120

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
            or self.worker_timeout_s != 70
            or type(self.owner_timeout_s) is not int
            or self.owner_timeout_s != 120
        ):
            raise CaseRejected("case_deadline_unknown")

    def to_dict(self) -> dict[str, object]:
        value = super().to_dict()
        for key in (
            "network_operations",
            "synthetic_auth_execs",
            "synthetic_model_execs",
        ):
            value.pop(key)
        value.update(
            kind="h1_service_network_preflight",
            network_limits=dict(LIMITS),
            owner_configuration_confirmation="external_entry_flag_required",
        )
        return value


def load_case(path: Path, *, owner: int = 0) -> Case:
    return cast(Case, Case.from_dict(read_metadata(path, owner=owner)))


def render_unit(case: base.Case) -> str:
    return (
        base.render_unit(case)
        .replace(
            "no-network resolver/window preflight", "bounded service DNS/TLS preflight"
        )
        .replace("issue167_resolver_worker.py", "network-worker-entry.py")
        .replace("RuntimeMaxSec=50s", "RuntimeMaxSec=80s")
        .replace("RestrictAddressFamilies=none", "RestrictAddressFamilies=AF_INET")
        .replace(
            "IPAddressDeny=any",
            "IPAddressDeny=any\nIPAddressAllow=28.0.0.0/8 192.168.44.1/32",
        )
    )


def verify_installation(
    root: Path, expected_sha: str | None = None
) -> tuple[base.Case, dict[str, Path], str]:
    value = base.verify_installation(root, expected_sha, case_loader=load_case)
    manifest = read_metadata(root / "manifest.json", owner=0)
    assert isinstance(manifest, dict)
    if not {
        "issue167_service_network_case.py",
        "issue167_service_network_worker.py",
        "issue167_service_network_owner.py",
        "issue167_dns_tls.py",
        "issue167_resolver_owner.py",
        "network-worker-entry.py",
    } <= set(manifest["members"]):
        raise CaseRejected("network_members_missing")
    profile = read_metadata(root / "profile.json", owner=0)
    if type(profile) is not dict:
        raise CaseRejected("network_trust_unknown")
    try:
        sha = profile["candidate_probe"]["tls_trust"]["sha256"]
    except (KeyError, TypeError):
        raise CaseRejected("network_trust_unknown") from None
    if type(sha) is not str or re.fullmatch("[a-f0-9]{64}", sha) is None:
        raise CaseRejected("network_trust_unknown")
    try:
        SocketOperations(sha)._context()
    except (OSError, ValueError):
        raise CaseRejected("network_trust_changed") from None
    return value


def validate_deny(run_id: str, sequence: int, value: object) -> dict[str, object]:
    if type(sequence) is not int or sequence not in {1, 2}:
        raise CaseRejected("deny_observation_unknown")
    expected = {
        "run_id": run_id,
        "sequence": sequence,
        "category": "deny_tcp_connect" if sequence == 1 else "deny_udp_A",
        "attempts": 1,
        "result": "denied_or_timeout",
        "cleanup_complete": True,
    }
    if json.dumps(value, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise CaseRejected("deny_observation_unknown")
    return cast(dict[str, object], value)


def _number(value: object) -> float:
    if type(value) not in (float, int) or not math.isfinite(cast(float, value)):
        raise CaseRejected("tls_timing_unknown")
    return float(cast(float, value))


def validate_probe(value: object) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value)
        != {
            "scope",
            "result",
            "OS_ACL_assessed",
            "ipv6",
            "exit_identity_claim",
            "counts_semantics",
            "dns_operations_entered",
            "tls_operations_entered",
            "http_requests",
            "auth_cli",
            "model_prompts",
            "cleanup_complete",
            "steps",
        }
        or value.get("counts_semantics") != "entered_bounded_operation_not_wire_count"
    ):
        raise CaseRejected("network_probe_unknown")
    if (
        value.get("scope") != "ordinary_user_predeployment_metadata_only"
        or value.get("result") != "observed_expected"
        or value.get("OS_ACL_assessed") is not False
        or value.get("exit_identity_claim") is not False
        or value.get("ipv6") != "not_assessed"
        or value.get("cleanup_complete") is not True
        or type(value.get("dns_operations_entered")) is not int
        or value["dns_operations_entered"] != 4
        or type(value.get("tls_operations_entered")) is not int
        or value["tls_operations_entered"] != 2
        or any(
            type(value.get(k)) is not int or value[k] != 0
            for k in ("http_requests", "auth_cli", "model_prompts")
        )
    ):
        raise CaseRejected("network_probe_unknown")
    rows = value.get("steps")
    if type(rows) is not list or len(rows) != 6:
        raise CaseRejected("network_probe_unknown")
    for offset, role in ((0, "api"), (3, "auth")):
        dns = rows[offset : offset + 2]
        tls = rows[offset + 2]
        for i, transport in enumerate(("udp", "tcp")):
            row = dns[i]
            if (
                type(row) is not dict
                or set(row)
                != {
                    "sequence",
                    "role",
                    "category",
                    "transport",
                    "outcome",
                    "address",
                    "ttl",
                    "received_monotonic",
                }
                or type(row["sequence"]) is not int
                or row["sequence"] != offset + i + 1
                or row["role"] != role
                or row["category"] != "dns_A"
                or row["transport"] != transport
                or row["outcome"] != "observed"
                or type(row["ttl"]) is not int
                or row["ttl"] <= 0
            ):
                raise CaseRejected("network_probe_unknown")
            pool_address(row["address"])
            _number(row["received_monotonic"])
        if (
            type(tls) is not dict
            or set(tls)
            != {
                "sequence",
                "role",
                "category",
                "outcome",
                "tls_version",
                "chain_checked",
                "hostname_checked",
                "address",
                "dns_expiry_monotonic",
                "started_monotonic",
                "completed_monotonic",
            }
            or type(tls["sequence"]) is not int
            or tls["sequence"] != offset + 3
            or tls["role"] != role
            or tls["category"] != "tls_handshake"
            or tls["outcome"] != "observed"
            or tls["tls_version"] not in {"TLSv1.2", "TLSv1.3"}
            or tls["chain_checked"] is not True
            or tls["hostname_checked"] is not True
            or tls["address"] != dns[0]["address"]
            or tls["address"] != dns[1]["address"]
        ):
            raise CaseRejected("network_probe_unknown")
        expiry = min(_number(row["received_monotonic"]) + row["ttl"] for row in dns)
        start = _number(tls["started_monotonic"])
        end = _number(tls["completed_monotonic"])
        if (
            _number(tls["dns_expiry_monotonic"]) != expiry
            or not max(row["received_monotonic"] for row in dns)
            <= start
            <= end
            < expiry
        ):
            raise CaseRejected("tls_timing_unknown")
    return cast(dict[str, object], value)


def validate_result(case: base.Case, value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != READY_FIELDS | {
        "result",
        "scope",
        "denials",
        "probe",
        "node_pi",
        "auth_calls",
        "model_calls",
    }:
        raise CaseRejected("worker_result_unknown")
    validate_ready(case, {key: value[key] for key in READY_FIELDS})
    if (
        value["result"] != "observed_expected"
        or value["scope"] != "service_network_metadata"
        or value["node_pi"] is not False
        or any(
            type(value[k]) is not int or value[k] != 0
            for k in ("auth_calls", "model_calls")
        )
        or type(value["denials"]) is not list
        or len(value["denials"]) != 2
    ):
        raise CaseRejected("worker_result_unknown")
    for sequence, item in enumerate(value["denials"], 1):
        validate_deny(case.run_id, sequence, item)
    validate_probe(value["probe"])
    return cast(dict[str, object], value)
