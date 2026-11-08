"""Offline #167 service-egress seam; never runs a host command or network I/O.

The inherited H1 Plan contributes only run/unit/cgroup identity. Its historical
loopback ports and addresses are neither exported nor used by this profile.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import cast

from scripts.issue167_h1_phase import (
    PhaseRejected,
    Plan,
    _normalize_expression,
    _without_handle,
    render_phase,
    verify_nft_state,
)
from scripts.issue167_h1_phase import (
    render_create as render_deny_create,
)
from scripts.issue167_h1_phase import (
    render_delete as render_h1_delete,
)

_HANDLES = {
    "table",
    "chain_out",
    "chain_phase",
    "counter_allowed",
    "counter_rejected",
    "scope",
}


class EgressRejected(ValueError):
    """Closed reason only; caller data and external exception text are omitted."""


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EgressRejected("egress_profile_unknown")
        result[key] = value
    return result


def _host(value: object) -> tuple[tuple[str, str], ...]:
    if (
        type(value) is not dict
        or set(value) != {"boot_id", "kernel", "machine", "hostname_sha256"}
        or any(type(item) is not str or not item for item in value.values())
        or re.fullmatch(
            r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", value["boot_id"]
        )
        is None
        or value["machine"] != "x86_64"
        or re.fullmatch(r"[a-f0-9]{64}", value["hostname_sha256"]) is None
    ):
        raise EgressRejected("egress_host_unknown")
    return tuple(sorted(cast(dict[str, str], value).items()))


@dataclass(frozen=True)
class FrozenEgress:
    process: Plan
    profile_sha256: str
    host: tuple[tuple[str, str], ...]
    pool: str
    resolver: str

    def __post_init__(self) -> None:
        try:
            if (
                type(self.process) is not Plan
                or self.process.network_mode != "ipv4_only"
                or type(self.profile_sha256) is not str
                or re.fullmatch(r"[a-f0-9]{64}", self.profile_sha256) is None
                or self.pool != "28.0.0.0/8"
                or self.resolver != "192.168.44.1"
                or type(self.host) is not tuple
                or self.host != _host(dict(self.host))
            ):
                raise ValueError
        except (TypeError, ValueError):
            raise EgressRejected("egress_profile_unknown") from None

    @classmethod
    def from_profile(
        cls, process: Plan, raw: bytes, expected_sha256: str, host_context: object
    ) -> FrozenEgress:
        if (
            type(process) is not Plan
            or process.network_mode != "ipv4_only"
            or type(expected_sha256) is not str
            or re.fullmatch(r"[a-f0-9]{64}", expected_sha256) is None
            or type(raw) is not bytes
            or len(raw) > 65536
            or hashlib.sha256(raw).hexdigest() != expected_sha256
        ):
            raise EgressRejected("egress_profile_unknown")
        try:
            value = json.loads(raw, object_pairs_hook=_object)
            owner = value["owner_report"]
            policy = value["accepted_policy"]
            pool, resolver = policy["pool_cidr"], owner["router"]
            if (
                value["kind"] != "issue167_real_exit_review_plan"
                or pool != "28.0.0.0/8"
                or resolver != "192.168.44.1"
                or owner["pool_config_raw"] != "28.0.0.1/8"
                or owner["mode"] != "fake-ip"
                or owner["software"] != "OpenClash"
                or owner["sniffer_override_destination"] is not True
                or type(owner["forwarded_tcp_redirect_port"]) is not int
                or owner["forwarded_tcp_redirect_port"] != 7892
                or owner["lan_dns_hijack_transports"] != ["tcp", "udp"]
                or owner["dns_hijack_target"] != "router"
                or owner["tls_intermediary_absent"] is not True
                or policy["decision"] != "A"
                or policy["ipv6"] != "not_assessed"
                or type(policy["ipv6_probe_limit"]) is not int
                or policy["ipv6_probe_limit"] != 0
                or any(
                    policy[key] is not False
                    for key in (
                        "api_auth_separation_claim",
                        "configuration_installed",
                        "exit_identity_claim",
                        "reported_A_is_allowlist",
                        "upstream_mapping_verified",
                    )
                )
                or policy["scope"] != "project_exact_cgroup_only_pending_H1"
                or _digest(policy["allow"])
                != _digest(
                    [
                        {
                            "family": "ipv4",
                            "transport": "tcp",
                            "destination": pool,
                            "ports": [443],
                        },
                        {
                            "family": "ipv4",
                            "transport": "udp",
                            "destination": resolver,
                            "ports": [53],
                        },
                        {
                            "family": "ipv4",
                            "transport": "tcp",
                            "destination": resolver,
                            "ports": [53],
                        },
                    ]
                )
            ):
                raise EgressRejected("egress_profile_unknown")
        except (KeyError, TypeError, UnicodeError, ValueError, RecursionError):
            raise EgressRejected("egress_profile_unknown") from None
        return cls(process, expected_sha256, _host(host_context), pool, resolver)

    def check_current(self, raw: bytes, host_context: object) -> None:
        if (
            type(raw) is not bytes
            or len(raw) > 65536
            or hashlib.sha256(raw).hexdigest() != self.profile_sha256
        ):
            raise EgressRejected("egress_profile_unknown")
        if _host(host_context) != self.host:
            raise EgressRejected("egress_host_unknown")

    def identity(self) -> dict[str, object]:
        return {
            "kind": "issue167_service_egress_review_only",
            "run_id": self.process.run_id,
            "uid": self.process.uid,
            "gid": self.process.gid,
            "unit": self.process.unit,
            "guardian_unit": self.process.guardian_unit,
            "table": self.process.table,
            "cgroup": self.process.cgroup,
            "profile_sha256": self.profile_sha256,
            "host_context": dict(self.host),
            "ipv6": "not_assessed",
            "authorization": "not_granted",
        }


def render_create(profile: FrozenEgress) -> str:
    """Exclusive table creation stays deny-only until a separately gated switch."""
    return render_deny_create(profile.process)


def render_activate(profile: FrozenEgress) -> str:
    p = profile.process
    lines = [f"flush chain inet {p.table} phase"]
    for address, transport, port, label in (
        (profile.pool, "tcp", 443, "pool-tls"),
        (profile.resolver, "udp", 53, "router-dns-udp"),
        (profile.resolver, "tcp", 53, "router-dns-tcp"),
    ):
        lines.append(
            f"add rule inet {p.table} phase ip daddr {address} "
            f"{transport} dport {port} counter name allowed accept "
            f'comment "issue167:{p.run_id}:egress:{label}"'
        )
    # Reuse the closed deny rule and its already reviewed comment/verdict shape.
    lines.extend(render_phase(p, "deny").splitlines()[1:])
    return "\n".join([*lines, ""])


def render_clear(profile: FrozenEgress) -> str:
    return render_phase(profile.process, "deny")


def render_delete(profile: FrozenEgress) -> str:
    return render_h1_delete(profile.process)


def network_fragments(profile: FrozenEgress) -> dict[str, str]:
    common = f"IPAddressDeny=any\nIPAddressAllow={profile.pool} {profile.resolver}/32\n"
    return {
        "worker": common + "RestrictAddressFamilies=AF_INET\n",
        "guardian": common + "RestrictAddressFamilies=AF_UNIX AF_NETLINK AF_INET\n",
    }


def _match(protocol: str, field: str, right: object) -> dict[str, object]:
    return {
        "match": {
            "op": "==",
            "left": {"payload": {"protocol": protocol, "field": field}},
            "right": right,
        }
    }


def _allows(profile: FrozenEgress) -> list[dict[str, object]]:
    p = profile.process
    prefix = {"prefix": {"addr": profile.pool.split("/")[0], "len": 8}}
    return [
        {
            "family": "inet",
            "table": p.table,
            "chain": "phase",
            "expr": [
                _match("ip", "daddr", address),
                _match(transport, "dport", port),
                {"counter": "allowed"},
                {"accept": None},
            ],
            "comment": f"issue167:{p.run_id}:egress:{label}",
        }
        for address, transport, port, label in (
            (prefix, "tcp", 443, "pool-tls"),
            (profile.resolver, "udp", 53, "router-dns-udp"),
            (profile.resolver, "tcp", 53, "router-dns-tcp"),
        )
    ]


def _snapshot(
    payload: object,
) -> tuple[dict[str, object], dict[str, int], dict[str, object]]:
    try:
        if type(payload) is bytes:
            if len(payload) > 65536:
                raise ValueError
            payload = json.loads(payload, object_pairs_hook=_object)
        if type(payload) is not dict or set(payload) != {"nftables"}:
            raise ValueError
        value = copy.deepcopy(payload)
        rows = value["nftables"]
        if type(rows) is not list or len(rows) > 16:
            raise ValueError
        handles: dict[str, int] = {}
        scope = None
        for row in rows:
            if type(row) is not dict or len(row) != 1:
                raise ValueError
            kind, item = next(iter(row.items()))
            if type(item) is not dict:
                raise ValueError
            if kind == "metainfo":
                if set(item) - {"version", "release_name", "json_schema_version"}:
                    raise ValueError
                if any(
                    type(v) is not str
                    for k, v in item.items()
                    if k != "json_schema_version"
                ):
                    raise ValueError
                if "json_schema_version" in item and (
                    type(item["json_schema_version"]) is not int
                    or item["json_schema_version"] != 1
                ):
                    raise ValueError
                continue
            handle = item.get("handle")
            if type(handle) is not int or not 0 < handle < 2**64:
                raise ValueError
            label = None
            if kind == "table":
                label = "table"
            elif kind == "chain" and item.get("name") in {"out", "phase"}:
                label = "chain_" + str(item["name"])
            elif kind == "counter" and item.get("name") in {"allowed", "rejected"}:
                label = "counter_" + str(item["name"])
            elif kind == "rule" and item.get("chain") == "out":
                label = "scope"
                scope = item["expr"][0]["match"]
            if label is not None:
                if label in handles:
                    raise ValueError
                handles[label] = handle
        if set(handles) != _HANDLES or type(scope) is not dict:
            raise ValueError
        return value, handles, scope
    except (KeyError, TypeError, ValueError, IndexError, UnicodeError, RecursionError):
        raise EgressRejected("egress_state_unknown") from None


def make_binding(
    profile: FrozenEgress,
    payload: object,
    identity: tuple[int, int],
    *,
    host_context: object,
) -> dict[str, object]:
    """Caller supplies an independently read live cgroup2 identity, never rule data."""
    verify_state(profile, payload, enabled=False, host_context=host_context)
    if type(identity) is not tuple or len(identity) != 2:
        raise EgressRejected("egress_binding_unknown")
    device, inode = identity
    if (
        type(device) is not int
        or device < 0
        or type(inode) is not int
        or not 0 < inode < 2**64
    ):
        raise EgressRejected("egress_binding_unknown")
    _value, handles, _scope = _snapshot(payload)
    return {
        "schema": 1,
        "source": "independent_live_cgroup2_identity",
        "identity_sha256": _digest(profile.identity()),
        "cgroup_device": device,
        "cgroup_inode": inode,
        "handles": handles,
    }


def verify_state(
    profile: FrozenEgress,
    payload: object,
    *,
    enabled: bool,
    host_context: object,
    binding: object | None = None,
) -> tuple[int, int]:
    """Reuse H1's complete deny scaffold validation after exact allow matching."""
    if type(enabled) is not bool:
        raise EgressRejected("egress_state_unknown")
    if _host(host_context) != profile.host:
        raise EgressRejected("egress_host_unknown")
    value, handles, scope = _snapshot(payload)
    if binding is not None:
        if (
            type(binding) is not dict
            or set(binding)
            != {
                "schema",
                "source",
                "identity_sha256",
                "cgroup_device",
                "cgroup_inode",
                "handles",
            }
            or type(binding["schema"]) is not int
            or binding["schema"] != 1
            or binding["source"] != "independent_live_cgroup2_identity"
            or binding["identity_sha256"] != _digest(profile.identity())
            or type(binding["cgroup_device"]) is not int
            or binding["cgroup_device"] < 0
            or type(binding["cgroup_inode"]) is not int
            or not 0 < binding["cgroup_inode"] < 2**64
            or type(binding["handles"]) is not dict
            or set(binding["handles"]) != _HANDLES
            or any(
                type(item) is not int or not 0 < item < 2**64
                for item in binding["handles"].values()
            )
            or _digest(binding["handles"]) != _digest(handles)
        ):
            raise EgressRejected("egress_binding_unknown")
        right = scope.get("right")
        inode = binding["cgroup_inode"]
        if right == profile.process.cgroup[1:] and type(right) is str:
            pass
        elif (type(right) is int and right == inode) or (
            type(right) is str and right == str(inode)
        ):
            scope["right"] = profile.process.cgroup[1:]
        else:
            raise EgressRejected("egress_binding_unknown")
    rows = cast(list[dict[str, object]], value["nftables"])
    rules = [(i, row["rule"]) for i, row in enumerate(rows) if "rule" in row]
    try:
        if len(rules) != (5 if enabled else 2):
            raise ValueError
        if enabled:
            actual = [
                _normalize_expression(_without_handle(row)) for _, row in rules[1:4]
            ]
            if actual != _allows(profile):
                raise ValueError
            remove = {i for i, _ in rules[1:4]}
            value["nftables"] = [row for i, row in enumerate(rows) if i not in remove]
        return verify_nft_state(profile.process, "deny", value)
    except (ValueError, PhaseRejected):
        raise EgressRejected("egress_state_unknown") from None
