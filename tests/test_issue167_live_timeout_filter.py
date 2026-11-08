"""Independent D1: T1 literal application-visible IPv4 fixtures; no I/O."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

import pytest

from scripts import issue167_live_timeout_filter as duplex

RUN = "36d91a42b7ce"
HOST = {
    "boot_id": "12345678-1234-1234-1234-123456789abc",
    "kernel": "fixture-kernel",
    "machine": "x86_64",
    "hostname_sha256": "c" * 64,
}


def plan() -> duplex.Plan:
    return duplex.Plan(RUN)


def fixture(
    phase: str = "deny",
    *,
    numeric: object | None = None,
    packets: tuple[int, ...] = (0, 0, 0, 0, 0, 0),
    offset: int = 0,
) -> dict[str, Any]:
    """Handwritten JSON layout; deliberately does not consume any renderer."""
    table = "paperradar167_36d91a42b7ce"
    common = {"family": "inet", "table": table}
    rows: list[dict[str, Any]] = [
        {"metainfo": {"version": "fixture", "json_schema_version": 1}},
        {"table": {"family": "inet", "name": table, "handle": 701}},
    ]
    for name, handle, hook in [
        ("out", 10, "output"),
        ("in", 11, "input"),
        ("phase_out", 12, None),
        ("phase_in", 13, None),
    ]:
        data: dict[str, Any] = {**common, "name": name, "handle": handle}
        if hook is not None:
            data.update(type="filter", hook=hook, prio=10, policy="accept")
        rows.append({"chain": data})
    for i, name in enumerate(duplex.COUNTERS, 1):
        rows.append(
            {
                "counter": {
                    **common,
                    "name": name,
                    "handle": i,
                    "packets": packets[i - 1],
                    "bytes": packets[i - 1] * 64,
                }
            }
        )
    for direction, handle in [("out", 20), ("in", 21)]:
        right = (
            "system.slice/paperradar-167-h1net-36d91a42b7ce.service"
            if numeric is None
            else numeric
        )
        rows.append(
            {
                "rule": {
                    **common,
                    "chain": direction,
                    "handle": handle,
                    "comment": f"issue167:{RUN}:t1:scope-{direction}",
                    "expr": [
                        {
                            "match": {
                                "op": "==",
                                "left": {"socket": {"key": "cgroupv2", "level": 2}},
                                "right": right,
                            }
                        },
                        {"jump": {"target": "phase_" + direction}},
                    ],
                }
            }
        )
    next_handle = 30 + offset
    for direction in ["out", "in"]:
        if phase != "deny":
            label = (
                "allowed_" + direction if phase == "allow" else "dropped_" + direction
            )
            rows.append(
                {
                    "rule": {
                        **common,
                        "chain": "phase_" + direction,
                        "handle": next_handle,
                        "comment": f"issue167:{RUN}:t1:{phase}-{direction}",
                        "expr": [
                            {
                                "match": {
                                    "op": "==",
                                    "left": {
                                        "payload": {
                                            "protocol": "ip",
                                            "field": "daddr"
                                            if direction == "out"
                                            else "saddr",
                                        }
                                    },
                                    "right": {"prefix": {"addr": "28.0.0.0", "len": 8}},
                                }
                            },
                            {
                                "match": {
                                    "op": "==",
                                    "left": {
                                        "payload": {
                                            "protocol": "tcp",
                                            "field": "dport"
                                            if direction == "out"
                                            else "sport",
                                        }
                                    },
                                    "right": 443,
                                }
                            },
                            {"counter": label},
                            {"accept" if phase == "allow" else "drop": None},
                        ],
                    }
                }
            )
            next_handle += 1
            for protocol in ("udp", "tcp"):
                rows.append(
                    {
                        "rule": {
                            **common,
                            "chain": "phase_" + direction,
                            "handle": next_handle,
                            "comment": f"issue167:{RUN}:t1:dns-{protocol}-{direction}",
                            "expr": [
                                {
                                    "match": {
                                        "op": "==",
                                        "left": {
                                            "payload": {
                                                "protocol": "ip",
                                                "field": "daddr"
                                                if direction == "out"
                                                else "saddr",
                                            }
                                        },
                                        "right": "192.168.44.1",
                                    }
                                },
                                {
                                    "match": {
                                        "op": "==",
                                        "left": {
                                            "payload": {
                                                "protocol": protocol,
                                                "field": "dport"
                                                if direction == "out"
                                                else "sport",
                                            }
                                        },
                                        "right": 53,
                                    }
                                },
                                {"counter": "allowed_" + direction},
                                {"accept": None},
                            ],
                        }
                    }
                )
                next_handle += 1
        rows.append(
            {
                "rule": {
                    **common,
                    "chain": "phase_" + direction,
                    "handle": next_handle,
                    "comment": f"issue167:{RUN}:t1:unexpected-{direction}",
                    "expr": [{"counter": "unexpected_" + direction}, {"drop": None}],
                }
            }
        )
        next_handle += 1
    return {"nftables": rows}


def binding() -> dict[str, Any]:
    return duplex.make_binding(plan(), fixture(), (30, 888888), host_context=HOST)


def allow() -> tuple[dict[str, Any], dict[str, Any]]:
    b = binding()
    ref = duplex.capture_phase(
        plan(),
        fixture("allow", offset=10),
        phase="allow",
        host_context=HOST,
        binding=b,
        previous_reference=b["initial_reference"],
        previous_counts=duplex.Counts(),
    )
    return b, ref


def verify(
    raw: object,
    b: object,
    ref: object,
    *,
    phase: str = "allow",
    previous: duplex.Counts | None = None,
) -> duplex.Counts:
    return duplex.verify_state(
        plan(),
        raw,
        phase=phase,
        host_context=HOST,
        binding=b,
        phase_reference=ref,
        previous_counts=previous or duplex.Counts(),
    )


def test_closed_plan_and_atomic_duplex_rendering() -> None:
    p = plan()
    assert duplex.render_create(p).startswith("create table inet " + p.table + "\n")
    text = duplex.render_allow(p)
    assert text.startswith(
        f"flush chain inet {p.table} phase_out\nflush chain inet {p.table} phase_in\n"
    )
    assert "ip daddr 28.0.0.0/8 tcp dport 443" in text
    assert "ip saddr 28.0.0.0/8 tcp sport 443" in text
    assert text.count(" accept ") == 6
    stall = duplex.render_stall(p)
    assert (
        "counter name dropped_in drop" in stall
        and "counter name dropped_out drop" in stall
    )
    assert duplex.render_delete(p) == "delete table inet " + p.table + "\n"
    assert all(
        x not in text + stall
        for x in ["meta skuid", "flush ruleset", "127.0.0.1", "0.0.0.0/0", "ip6"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"tls_port": True},
        {"tls_port": 8443},
        {"pool": "0.0.0.0/0"},
        {"dns": "192.168.44.2"},
        {"uid": True},
        {"run_id": "bad; flush ruleset"},
    ],
)
def test_plan_rejects_scope_drift(change: dict[str, Any]) -> None:
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_plan_unknown$"):
        replace(plan(), **change)


def test_independent_binding_and_full_phase_reference_roundtrip() -> None:
    b, ref = allow()
    counts = verify(json.dumps(fixture("allow", offset=10)).encode(), b, ref)
    assert counts == duplex.Counts()
    assert ref["phase"] == "allow" and set(ref["rule_handles"]) == {
        "phase_in",
        "phase_out",
    }
    assert len(ref["structure_sha256"]) == 64


@pytest.mark.parametrize("numeric", [888888, "888888"])
def test_numeric_scope_uses_only_independent_live_inode(numeric: object) -> None:
    b = duplex.make_binding(
        plan(), fixture(numeric=numeric), (30, 888888), host_context=HOST
    )
    assert (
        duplex.verify_state(
            plan(),
            fixture(numeric=numeric),
            phase="deny",
            host_context=HOST,
            binding=b,
            phase_reference=b["initial_reference"],
            previous_counts=duplex.Counts(),
        )
        == duplex.Counts()
    )
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_scope_unknown$"):
        duplex.make_binding(
            plan(), fixture(numeric=numeric), (30, 999999), host_context=HOST
        )


def test_allow_stall_keeps_both_directions_bound_without_resume() -> None:
    b, allowed = allow()
    first = verify(fixture("allow", offset=10, packets=(2, 3, 0, 0, 0, 0)), b, allowed)
    stalled_raw = fixture("stall", offset=20, packets=(2, 3, 1, 1, 0, 0))
    stalled = duplex.capture_phase(
        plan(),
        stalled_raw,
        phase="stall",
        host_context=HOST,
        binding=b,
        previous_reference=allowed,
        previous_counts=first,
    )
    current = verify(stalled_raw, b, stalled, phase="stall", previous=first)
    assert current.dropped_in == current.dropped_out == 1
    duplex.verify_references(
        plan(), [b["initial_reference"], allowed, stalled], host_context=HOST, binding=b
    )
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_transition_unknown$"
    ):
        duplex.capture_phase(
            plan(),
            fixture("allow", offset=30),
            phase="allow",
            host_context=HOST,
            binding=b,
            previous_reference=stalled,
            previous_counts=current,
        )


@pytest.mark.parametrize(
    "drift",
    [
        "half_switch",
        "extra_chain",
        "wrong_hook",
        "scope_wrong_direction",
        "wrong_endpoint",
        "wrong_port",
        "wrong_counter",
        "extra_rule",
        "duplicate_meta",
        "handle_drift",
        "handle_bool",
    ],
)
def test_full_table_shape_or_bound_reference_drift_is_unknown(drift: str) -> None:
    b, ref = allow()
    raw = fixture("allow", offset=10)
    rows = raw["nftables"]
    rules = [r["rule"] for r in rows if "rule" in r]
    if drift == "half_switch":
        rules[-2]["expr"][-1] = {"drop": None}
    elif drift == "extra_chain":
        rows.append(
            {
                "chain": {
                    "family": "inet",
                    "table": plan().table,
                    "name": "foreign",
                    "handle": 999,
                }
            }
        )
    elif drift == "wrong_hook":
        rows[3]["chain"]["hook"] = "forward"
    elif drift == "scope_wrong_direction":
        rules[1]["expr"][-1]["jump"]["target"] = "phase_out"
    elif drift == "wrong_endpoint":
        rules[2]["expr"][0]["match"]["right"] = "127.0.0.2"
    elif drift == "wrong_port":
        rules[2]["expr"][1]["match"]["right"] = 46168
    elif drift == "wrong_counter":
        rules[-2]["expr"][-2] = {"counter": "allowed_out"}
    elif drift == "extra_rule":
        rows.append(copy.deepcopy(rows[-1]))
    elif drift == "duplicate_meta":
        rows.append(copy.deepcopy(rows[0]))
    elif drift == "handle_drift":
        rows[1]["table"]["handle"] = 702
    elif drift == "handle_bool":
        rows[1]["table"]["handle"] = True
    with pytest.raises(
        duplex.DuplexRejected,
        match=r"^timeout_filter_(state|binding|phase_reference)_unknown$",
    ):
        verify(raw, b, ref)


def test_late_packet_and_counter_reset_do_not_become_cleanup_success() -> None:
    b, ref = allow()
    raw = fixture("allow", offset=10, packets=(3, 3, 0, 0, 0, 0))
    last = verify(raw, b, ref)
    assert (
        duplex.verify_quiescent(
            plan(),
            raw,
            phase="allow",
            host_context=HOST,
            binding=b,
            phase_reference=ref,
            previous_counts=last,
        )
        == last
    )
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_late_packet$"):
        duplex.verify_quiescent(
            plan(),
            fixture("allow", offset=10, packets=(4, 3, 0, 0, 0, 0)),
            phase="allow",
            host_context=HOST,
            binding=b,
            phase_reference=ref,
            previous_counts=last,
        )
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_counter_regressed$"
    ):
        verify(
            fixture("allow", offset=10, packets=(2, 3, 0, 0, 0, 0)),
            b,
            ref,
            previous=last,
        )


def test_unexpected_packets_and_boolean_counts_are_blocking() -> None:
    b, ref = allow()
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_unexpected_packet$"
    ):
        verify(fixture("allow", offset=10, packets=(0, 0, 0, 0, 1, 0)), b, ref)
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_counts_unknown$"):
        duplex.Counts(allowed_in=True)


def test_partial_or_duplicate_json_is_not_a_state() -> None:
    b, ref = allow()
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_state_unknown$"):
        verify(b'{"nftables":[],"nftables":[]}', b, ref)
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_state_unknown$"):
        verify({"nftables": fixture("allow", offset=10)["nftables"][:-1]}, b, ref)


def complete_refs() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    b, a = allow()
    s = duplex.capture_phase(
        plan(),
        fixture("stall", offset=20),
        phase="stall",
        host_context=HOST,
        binding=b,
        previous_reference=a,
        previous_counts=duplex.Counts(),
    )
    return b, [b["initial_reference"], a, s]


def test_complete_rule_reference_chain_has_single_cycle_and_predecessors() -> None:
    b, refs = complete_refs()
    duplex.verify_references(plan(), refs, host_context=HOST, binding=b)
    assert [r["sequence"] for r in refs] == [0, 1, 2]
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_transition_unknown$"
    ):
        duplex.capture_phase(
            plan(),
            fixture("stall", offset=40),
            phase="stall",
            host_context=HOST,
            binding=b,
            previous_reference=refs[-1],
            previous_counts=duplex.Counts(),
        )


@pytest.mark.parametrize(
    "change", ["missing", "reordered", "bad_predecessor", "boolean_sequence"]
)
def test_incomplete_or_replayed_reference_chain_is_unknown(change: str) -> None:
    b, refs = complete_refs()
    if change == "missing":
        refs.pop(1)
    elif change == "reordered":
        refs[1], refs[2] = refs[2], refs[1]
    elif change == "bad_predecessor":
        refs[-1]["previous_reference_sha256"] = "f" * 64
    elif change == "boolean_sequence":
        refs[1]["sequence"] = True
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_phase_reference_unknown$"
    ):
        duplex.verify_references(plan(), refs, host_context=HOST, binding=b)


@pytest.mark.parametrize(
    "collision", ["chain_counter", "scope_counter", "dynamic_chain"]
)
def test_table_object_handle_namespace_collisions_are_unknown(collision: str) -> None:
    raw = fixture()
    if collision == "chain_counter":
        raw["nftables"][6]["counter"]["handle"] = 10
    elif collision == "scope_counter":
        raw["nftables"][12]["rule"]["handle"] = 1
    else:
        raw["nftables"][-1]["rule"]["handle"] = 10
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_state_unknown$"):
        duplex.make_binding(plan(), raw, (30, 888888), host_context=HOST)


def test_table_itself_has_separate_handle_namespace() -> None:
    # Linux v7.0 nf_tables_api.c uses table.hgenerator for chains/rules/objects,
    # but the table handle comes from nft_net.table_handle. Do not conflate them.
    raw = fixture()
    raw["nftables"][1]["table"]["handle"] = 1
    b = duplex.make_binding(plan(), raw, (30, 888888), host_context=HOST)
    assert b["handles"]["table"] == b["handles"]["counter_allowed_in"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("cgroup_device", True),
        ("cgroup_inode", 999999),
        ("identity_sha256", "f" * 64),
        ("source", "caller_assertion"),
    ],
)
def test_binding_cannot_be_cloned_or_retyped(field: str, value: object) -> None:
    b, ref = allow()
    b[field] = value
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_binding_unknown$"
    ):
        verify(fixture("allow", offset=10), b, ref)


def test_current_host_and_initial_zero_are_required() -> None:
    b = binding()
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_binding_unknown$"
    ):
        duplex.verify_state(
            plan(),
            fixture(),
            phase="deny",
            host_context={**HOST, "kernel": "other"},
            binding=b,
            phase_reference=b["initial_reference"],
            previous_counts=duplex.Counts(),
        )
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_initial_counts_unknown$"
    ):
        duplex.make_binding(
            plan(), fixture(packets=(1, 0, 0, 0, 0, 0)), (30, 888888), host_context=HOST
        )


def test_counter_bytes_cannot_regress_while_packets_are_unchanged() -> None:
    b, ref = allow()
    raw = fixture("allow", offset=10, packets=(2, 2, 0, 0, 0, 0))
    last = verify(raw, b, ref)
    raw["nftables"][6]["counter"]["bytes"] = 127
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_counter_regressed$"
    ):
        verify(raw, b, ref, previous=last)


@pytest.mark.parametrize("numeric", ["0888888", 888889, True])
def test_unknown_scope_identifier_never_binds(numeric: object) -> None:
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_(scope|state)_unknown$"
    ):
        duplex.make_binding(
            plan(), fixture(numeric=numeric), (30, 888888), host_context=HOST
        )


def test_kernel_may_omit_redundant_socket_level_only() -> None:
    raw = fixture()
    for row in raw["nftables"]:
        if "rule" in row and row["rule"]["chain"] in {"in", "out"}:
            row["rule"]["expr"][0]["match"]["left"]["socket"].pop("level")
    b = duplex.make_binding(plan(), raw, (30, 888888), host_context=HOST)
    assert (
        duplex.verify_state(
            plan(),
            raw,
            phase="deny",
            host_context=HOST,
            binding=b,
            phase_reference=b["initial_reference"],
            previous_counts=duplex.Counts(),
        )
        == duplex.Counts()
    )


def test_no_same_phase_rebinding_after_handle_drift() -> None:
    b, ref = allow()
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_transition_unknown$"
    ):
        duplex.capture_phase(
            plan(),
            fixture("allow", offset=99),
            phase="allow",
            host_context=HOST,
            binding=b,
            previous_reference=ref,
            previous_counts=duplex.Counts(),
        )


def test_stall_changes_only_tls_and_keeps_exact_dns_allow_rules() -> None:
    text = duplex.render_stall(plan())
    assert text.count("flush chain ") == 2
    assert text.count("counter name dropped_") == 2
    assert text.count(" accept ") == 4
    for address, port in (("daddr", "dport"), ("saddr", "sport")):
        assert f"ip {address} 28.0.0.0/8 tcp {port} 443" in text
        for protocol in ("udp", "tcp"):
            assert f"ip {address} 192.168.44.1 {protocol} {port} 53" in text
    assert " reject " not in text and "ct state" not in text


@pytest.mark.parametrize(
    "drift",
    [
        "pool_network",
        "pool_length",
        "router",
        "dns_subnet",
        "dns_port",
        "dns_protocol",
        "dns_drop",
        "dns_catchall",
        "tls_direction",
        "tls_source_port",
        "tls_udp",
        "stall_only_output",
        "blanket_established",
        "uid_scope",
        "policy",
        "priority",
    ],
)
def test_endpoint_dns_or_duplex_stall_drift_is_unknown(drift: str) -> None:
    b, allowed = allow()
    raw = fixture("stall", offset=20)
    rows = raw["nftables"]
    rules = [r["rule"] for r in rows if "rule" in r]
    tls_out, dns_out, tls_in = rules[2], rules[3], rules[6]
    if drift == "pool_network":
        tls_out["expr"][0]["match"]["right"]["prefix"]["addr"] = "29.0.0.0"
    elif drift == "pool_length":
        tls_out["expr"][0]["match"]["right"]["prefix"]["len"] = 7
    elif drift == "router":
        dns_out["expr"][0]["match"]["right"] = "192.168.44.2"
    elif drift == "dns_subnet":
        dns_out["expr"][0]["match"]["right"] = {
            "prefix": {"addr": "192.168.44.0", "len": 24}
        }
    elif drift == "dns_port":
        dns_out["expr"][1]["match"]["right"] = 5353
    elif drift == "dns_protocol":
        dns_out["expr"][1]["match"]["left"]["payload"]["protocol"] = "icmp"
    elif drift == "dns_drop":
        dns_out["expr"][-1] = {"drop": None}
    elif drift == "dns_catchall":
        dns_out["expr"].pop(1)
    elif drift == "tls_direction":
        tls_in["expr"][0]["match"]["left"]["payload"]["field"] = "daddr"
    elif drift == "tls_source_port":
        tls_in["expr"][1]["match"]["left"]["payload"]["field"] = "dport"
    elif drift == "tls_udp":
        tls_in["expr"][1]["match"]["left"]["payload"]["protocol"] = "udp"
    elif drift == "stall_only_output":
        tls_in["expr"][-1] = {"accept": None}
    elif drift == "blanket_established":
        tls_out["expr"] = [{"ct": {"key": "state"}}, {"accept": None}]
    elif drift == "uid_scope":
        rules[0]["expr"][0]["match"]["left"] = {"meta": {"key": "skuid"}}
        rules[0]["expr"][0]["match"]["right"] = 1000
    elif drift == "policy":
        rows[2]["chain"]["policy"] = "drop"
    elif drift == "priority":
        rows[3]["chain"]["prio"] = 0
    reason = "scope" if drift == "uid_scope" else "state"
    with pytest.raises(
        duplex.DuplexRejected, match="^timeout_filter_" + reason + "_unknown$"
    ):
        duplex.capture_phase(
            plan(),
            raw,
            phase="stall",
            host_context=HOST,
            binding=b,
            previous_reference=allowed,
            previous_counts=duplex.Counts(),
        )


def test_no_trigger_reference_prefix_is_valid_but_has_no_stall() -> None:
    b, allowed = allow()
    duplex.verify_references(
        plan(), [b["initial_reference"], allowed], host_context=HOST, binding=b
    )
    assert allowed["phase"] == "allow" and allowed["sequence"] == 1
    with pytest.raises(
        duplex.DuplexRejected, match=r"^timeout_filter_phase_reference_unknown$"
    ):
        duplex.verify_references(
            plan(), [b["initial_reference"]], host_context=HOST, binding=b
        )


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("field", ["packets", "bytes"])
def test_any_post_stop_counter_change_blocks_cleanup(index: int, field: str) -> None:
    b, refs = complete_refs()
    raw = fixture("stall", offset=20, packets=(3, 3, 2, 2, 0, 0))
    current = verify(raw, b, refs[-1], phase="stall")
    raw["nftables"][6 + index]["counter"][field] += 1
    expected = "unexpected_packet" if index >= 4 else "late_packet"
    with pytest.raises(
        duplex.DuplexRejected, match="^timeout_filter_" + expected + "$"
    ):
        duplex.verify_quiescent(
            plan(),
            raw,
            phase="stall",
            host_context=HOST,
            binding=b,
            phase_reference=refs[-1],
            previous_counts=current,
        )


def test_allowed_dns_growth_is_not_tls_or_drop_evidence() -> None:
    b, refs = complete_refs()
    current = verify(
        fixture("stall", offset=20, packets=(4, 5, 0, 0, 0, 0)),
        b,
        refs[-1],
        phase="stall",
    )
    assert current.allowed_in == 4 and current.allowed_out == 5
    assert current.dropped_in == current.dropped_out == 0


def test_counts_dict_exactness_and_bounds() -> None:
    c = duplex.Counts(1, 2, 3, 4, 0, 0, (64, 128, 192, 256, 0, 0))
    assert duplex.Counts.from_dict(c.to_dict()) == c
    for changed in [
        {},
        {**c.to_dict(), "other": {"packets": 0, "bytes": 0}},
        {**c.to_dict(), "allowed_in": {"packets": True, "bytes": 64}},
    ]:
        with pytest.raises(
            duplex.DuplexRejected, match=r"^timeout_filter_counts_unknown$"
        ):
            duplex.Counts.from_dict(changed)
    with pytest.raises(duplex.DuplexRejected, match=r"^timeout_filter_counts_unknown$"):
        duplex.Counts(byte_counts=(0, 0, 0, 0, 0, 2**64))
