"""Independent D1: service-egress pure fixtures, without host or network tools."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from scripts import issue167_service_egress as egress
from scripts.issue167_h1_phase import Plan
from tests.test_issue167_h1_phase import nft_fixture

PROFILE = Path("intent/review/issue-167/real-exit-plan-v1.json")
HOST = {
    "boot_id": "12345678-1234-1234-1234-123456789abc",
    "kernel": "fixture-kernel",
    "machine": "x86_64",
    "hostname_sha256": "f" * 64,
}


def process() -> Plan:
    return Plan("0123456789ab", 1000, 1000, network_mode="ipv4_only")


def profile() -> egress.FrozenEgress:
    raw = PROFILE.read_bytes()
    return egress.FrozenEgress.from_profile(
        process(), raw, hashlib.sha256(raw).hexdigest(), HOST
    )


def fixture(enabled: bool = True) -> dict[str, object]:
    value = nft_fixture("deny")
    rows = cast(list[dict[str, object]], value["nftables"])
    for i, row in enumerate(rows):
        kind, item = next(iter(row.items()))
        if kind != "metainfo":
            cast(dict[str, object], item).setdefault("handle", 100 + i)
    if enabled:
        base = {
            "family": "inet",
            "table": "paperradar167_0123456789ab",
            "chain": "phase",
        }
        allows: list[dict[str, object]] = []
        for index, address, transport, port, tag in (
            (201, {"prefix": {"addr": "28.0.0.0", "len": 8}}, "tcp", 443, "pool-tls"),
            (202, "192.168.44.1", "udp", 53, "router-dns-udp"),
            (203, "192.168.44.1", "tcp", 53, "router-dns-tcp"),
        ):
            allows.append(
                {
                    "rule": {
                        **base,
                        "handle": index,
                        "comment": "issue167:0123456789ab:egress:" + tag,
                        "expr": [
                            {
                                "match": {
                                    "op": "==",
                                    "left": {
                                        "payload": {"protocol": "ip", "field": "daddr"}
                                    },
                                    "right": address,
                                }
                            },
                            {
                                "match": {
                                    "op": "==",
                                    "left": {
                                        "payload": {
                                            "protocol": transport,
                                            "field": "dport",
                                        }
                                    },
                                    "right": port,
                                }
                            },
                            {"counter": "allowed"},
                            {"accept": None},
                        ],
                    }
                }
            )
        rows[-1:-1] = allows
    return value


def rules(value: dict[str, object]) -> list[dict[str, object]]:
    return [
        cast(dict[str, object], row["rule"])
        for row in cast(list[dict[str, object]], value["nftables"])
        if "rule" in row
    ]


def match(rule: dict[str, object], index: int = 0) -> dict[str, object]:
    return cast(
        dict[str, object], cast(list[dict[str, object]], rule["expr"])[index]["match"]
    )


def bind() -> dict[str, object]:
    return egress.make_binding(
        profile(), fixture(False), (20, 844648), host_context=HOST
    )


def test_profile_identity_has_no_legacy_loopback_network_semantics() -> None:
    p = profile()
    value = p.identity()
    assert value["authorization"] == "not_granted"
    assert value["ipv6"] == "not_assessed"
    assert value["cgroup"] == "/system.slice/paperradar-167-h1net-0123456789ab.service"
    assert not {"ports", "addresses", "mode"} & value.keys()
    p.check_current(PROFILE.read_bytes(), HOST)


@pytest.mark.parametrize(
    "path,value",
    [
        (("accepted_policy", "pool_cidr"), "0.0.0.0/0"),
        (("owner_report", "pool_config_raw"), "28.0.0.0/8"),
        (("owner_report", "router"), "192.168.44.0/24"),
        (("owner_report", "mode"), "redir-host"),
        (("owner_report", "forwarded_tcp_redirect_port"), 443),
        (("owner_report", "lan_dns_hijack_transports"), ["udp"]),
        (("accepted_policy", "api_auth_separation_claim"), True),
        (("accepted_policy", "configuration_installed"), True),
        (("accepted_policy", "upstream_mapping_verified"), True),
        (("accepted_policy", "exit_identity_claim"), True),
        (("accepted_policy", "ipv6_probe_limit"), False),
        (("accepted_policy", "allow"), []),
    ],
)
def test_semantic_drift_refused_even_with_recomputed_profile_hash(
    path: tuple[str, str], value: object
) -> None:
    data = json.loads(PROFILE.read_text())
    data[path[0]][path[1]] = value
    raw = json.dumps(data).encode()
    with pytest.raises(egress.EgressRejected, match=r"^egress_profile_unknown$"):
        egress.FrozenEgress.from_profile(
            process(), raw, hashlib.sha256(raw).hexdigest(), HOST
        )


def test_bytes_host_and_constructor_drift_are_fail_closed() -> None:
    p = profile()
    with pytest.raises(egress.EgressRejected, match=r"^egress_profile_unknown$"):
        p.check_current(PROFILE.read_bytes() + b" ", HOST)
    with pytest.raises(egress.EgressRejected, match=r"^egress_host_unknown$"):
        p.check_current(PROFILE.read_bytes(), {**HOST, "kernel": "changed"})
    with pytest.raises(egress.EgressRejected, match=r"^egress_profile_unknown$"):
        replace(p, pool="28.0.0.0/8; flush ruleset")
    with pytest.raises(egress.EgressRejected, match=r"^egress_profile_unknown$"):
        egress.FrozenEgress.from_profile(
            Plan("0123456789ab", 1000, 1000),
            PROFILE.read_bytes(),
            p.profile_sha256,
            HOST,
        )
    with pytest.raises(egress.EgressRejected, match=r"^egress_profile_unknown$"):
        egress.FrozenEgress.from_profile(
            process(),
            b'{"x":1,"x":2}',
            hashlib.sha256(b'{"x":1,"x":2}').hexdigest(),
            HOST,
        )


def test_render_is_initial_deny_then_closed_atomic_activation_and_clear() -> None:
    p = profile()
    initial = egress.render_create(p)
    assert initial.startswith("create table inet paperradar167_0123456789ab\n")
    assert (
        'socket cgroupv2 level 2 "system.slice/'
        'paperradar-167-h1net-0123456789ab.service"' in initial
    )
    assert "policy accept" in initial and "daddr" not in initial
    active = egress.render_activate(p)
    assert active.count("counter name allowed accept") == 3
    assert "ip daddr 28.0.0.0/8 tcp dport 443" in active
    assert "ip daddr 192.168.44.1 udp dport 53" in active
    assert "ip daddr 192.168.44.1 tcp dport 53" in active
    assert all(
        x not in active
        for x in [
            "28.0.5.94",
            "28.0.5.167",
            "7892",
            "ip6",
            "flush ruleset",
            "meta skuid",
        ]
    )
    assert egress.render_clear(p).startswith(
        "flush chain inet paperradar167_0123456789ab phase\n"
    )
    assert "daddr" not in egress.render_clear(p)
    assert egress.render_delete(p) == "delete table inet paperradar167_0123456789ab\n"


def test_network_fragments_constrain_only_declared_families_and_addresses() -> None:
    value = egress.network_fragments(profile())
    assert (
        value["worker"]
        == "IPAddressDeny=any\nIPAddressAllow=28.0.0.0/8 192.168.44.1/32\n"
        "RestrictAddressFamilies=AF_INET\n"
    )
    assert value["guardian"].endswith(
        "RestrictAddressFamilies=AF_UNIX AF_NETLINK AF_INET\n"
    )
    assert all(
        x not in text
        for text in value.values()
        for x in ["AF_INET6", "7892", "127.0.0.1"]
    )


@pytest.mark.parametrize("enabled", [False, True])
def test_valid_state_uses_original_complete_scaffold_and_returns_packet_counters(
    enabled: bool,
) -> None:
    value = fixture(enabled)
    assert egress.verify_state(
        profile(), value, enabled=enabled, host_context=HOST
    ) == (4, 7)
    assert egress.verify_state(
        profile(), json.dumps(value).encode(), enabled=enabled, host_context=HOST
    ) == (4, 7)


@pytest.mark.parametrize(
    "drift",
    [
        "wrong_pool",
        "two_address_allowlist",
        "wide_dns",
        "wrong_scope",
        "unbound_numeric",
        "port7892",
        "dns443",
        "extra_rule",
        "missing_rule",
        "wrong_order",
        "wrong_protocol",
        "wrong_chain_policy",
        "counter_bool",
        "counter_overflow",
        "zero_handle",
        "extra_row",
    ],
)
def test_wrong_kernel_scope_or_allow_semantics_refused(drift: str) -> None:
    value = fixture()
    entries = cast(list[dict[str, object]], value["nftables"])
    r = rules(value)
    if drift == "wrong_pool":
        match(r[1])["right"] = {"prefix": {"addr": "0.0.0.0", "len": 0}}
    elif drift == "two_address_allowlist":
        match(r[1])["right"] = "28.0.5.94"
    elif drift == "wide_dns":
        match(r[2])["right"] = {"prefix": {"addr": "192.168.44.0", "len": 24}}
    elif drift == "wrong_scope":
        match(r[0])["right"] = "system.slice/other.service"
    elif drift == "unbound_numeric":
        match(r[0])["right"] = "844648"
    elif drift == "port7892":
        match(r[1], 1)["right"] = 7892
    elif drift == "dns443":
        match(r[3], 1)["right"] = 443
    elif drift == "wrong_protocol":
        cast(
            dict[str, object],
            cast(dict[str, object], match(r[2], 1)["left"])["payload"],
        )["protocol"] = "tcp"
    elif drift == "extra_rule":
        entries.insert(-1, {"rule": copy.deepcopy(r[1])})
    elif drift == "missing_rule":
        entries.remove(next(row for row in entries if row.get("rule") is r[2]))
    elif drift == "wrong_order":
        r[1]["comment"], r[2]["comment"] = (r[2]["comment"], r[1]["comment"])
    elif drift == "wrong_chain_policy":
        cast(
            dict[str, object],
            next(
                row["chain"]
                for row in entries
                if "chain" in row
                and cast(dict[str, object], row["chain"])["name"] == "out"
            ),
        )["policy"] = "drop"
    elif drift in {"counter_bool", "counter_overflow"}:
        cast(
            dict[str, object],
            next(row["counter"] for row in entries if "counter" in row),
        )["packets"] = True if drift == "counter_bool" else 2**64
    elif drift == "zero_handle":
        r[1]["handle"] = 0
    elif drift == "extra_row":
        entries.append({"set": {"handle": 666}})
    with pytest.raises(egress.EgressRejected, match=r"^egress_state_unknown$"):
        egress.verify_state(profile(), value, enabled=True, host_context=HOST)


@pytest.mark.parametrize("right", [844648, "844648"])
def test_bound_exact_numeric_identity_accepts_but_input_is_not_mutated(
    right: object,
) -> None:
    value = fixture()
    match(rules(value)[0])["right"] = right
    before = copy.deepcopy(value)
    assert egress.verify_state(
        profile(), value, enabled=True, host_context=HOST, binding=bind()
    ) == (4, 7)
    assert value == before


@pytest.mark.parametrize(
    "label",
    [
        "table",
        "chain_out",
        "chain_phase",
        "counter_allowed",
        "counter_rejected",
        "scope",
    ],
)
def test_delete_recreate_stable_handle_drift_refused(label: str) -> None:
    value = fixture()
    for row in cast(list[dict[str, object]], value["nftables"]):
        kind, item_value = next(iter(row.items()))
        item = cast(dict[str, object], item_value)
        candidate = (
            "table"
            if kind == "table"
            else "chain_" + str(item.get("name"))
            if kind == "chain"
            else "counter_" + str(item.get("name"))
            if kind == "counter"
            else "scope"
            if kind == "rule" and item.get("chain") == "out"
            else None
        )
        if candidate == label:
            item["handle"] = cast(int, item["handle"]) + 1000
            break
    with pytest.raises(egress.EgressRejected, match=r"^egress_binding_unknown$"):
        egress.verify_state(
            profile(), value, enabled=True, host_context=HOST, binding=bind()
        )


@pytest.mark.parametrize("right", [844649, "0844648", True, 844648.0])
def test_numeric_coercion_wrong_id_or_missing_binding_refused(right: object) -> None:
    value = fixture()
    match(rules(value)[0])["right"] = right
    with pytest.raises(egress.EgressRejected, match=r"^egress_binding_unknown$"):
        egress.verify_state(
            profile(), value, enabled=True, host_context=HOST, binding=bind()
        )


def test_binding_requires_original_path_and_current_source_host() -> None:
    value = fixture(False)
    match(rules(value)[0])["right"] = "844648"
    with pytest.raises(egress.EgressRejected, match=r"^egress_state_unknown$"):
        egress.make_binding(profile(), value, (20, 844648), host_context=HOST)
    with pytest.raises(egress.EgressRejected, match=r"^egress_host_unknown$"):
        egress.verify_state(
            profile(),
            fixture(),
            enabled=True,
            host_context={**HOST, "kernel": "changed"},
            binding=bind(),
        )
    other = replace(profile(), profile_sha256="a" * 64)
    with pytest.raises(egress.EgressRejected, match=r"^egress_binding_unknown$"):
        egress.verify_state(
            other, fixture(), enabled=True, host_context=HOST, binding=bind()
        )


def test_bad_json_metadata_and_binding_fields_keep_closed_reasons() -> None:
    with pytest.raises(egress.EgressRejected, match=r"^egress_state_unknown$"):
        egress.verify_state(
            profile(), b'{"nftables":[],"nftables":[]}', enabled=True, host_context=HOST
        )
    with pytest.raises(egress.EgressRejected, match=r"^egress_state_unknown$"):
        egress.verify_state(
            profile(), fixture(), enabled=cast(bool, 1), host_context=HOST
        )
    bad = bind()
    cast(dict[str, object], bad["handles"])["scope"] = True
    with pytest.raises(egress.EgressRejected, match=r"^egress_binding_unknown$"):
        egress.verify_state(
            profile(), fixture(), enabled=True, host_context=HOST, binding=bad
        )


@pytest.mark.parametrize("kind", ["profile", "kernel"])
def test_deeply_nested_bytes_keep_controlled_unknown(kind: str) -> None:
    raw = b"[" * 2000 + b"0" + b"]" * 2000
    if kind == "kernel":
        raw = b'{"nftables":[{"table":' + raw + b"}]}"
    original_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(1000)
        if kind == "profile":
            with pytest.raises(
                egress.EgressRejected, match=r"^egress_profile_unknown$"
            ):
                egress.FrozenEgress.from_profile(
                    process(), raw, hashlib.sha256(raw).hexdigest(), HOST
                )
        else:
            with pytest.raises(egress.EgressRejected, match=r"^egress_state_unknown$"):
                egress.verify_state(profile(), raw, enabled=True, host_context=HOST)
    finally:
        sys.setrecursionlimit(original_limit)
