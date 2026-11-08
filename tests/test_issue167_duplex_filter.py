"""Independent D1: literal kernel-shaped fixtures, no host commands or sockets."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

import pytest

from scripts import issue167_duplex_filter as duplex

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
                    "comment": f"issue167:{RUN}:duplex:scope-{direction}",
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
                        "comment": f"issue167:{RUN}:duplex:{phase}-{direction}",
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
                                    "right": "127.0.0.1",
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
                                    "right": 46167,
                                }
                            },
                            {"counter": label},
                            {"accept" if phase == "allow" else "drop": None},
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
                    "comment": f"issue167:{RUN}:duplex:unexpected-{direction}",
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
    assert "ip daddr 127.0.0.1 tcp dport 46167" in text
    assert "ip saddr 127.0.0.1 tcp sport 46167" in text
    assert text.count(" accept ") == 2
    stall = duplex.render_stall(p)
    assert (
        "counter name dropped_in drop" in stall
        and "counter name dropped_out drop" in stall
    )
    assert duplex.render_delete(p) == "delete table inet " + p.table + "\n"
    assert all(
        x not in text + stall
        for x in ["meta skuid", "flush ruleset", "28.0.0.0", "0.0.0.0/0", "ip6"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"port": True},
        {"port": 443},
        {"address": "127.0.0.0/8"},
        {"uid": True},
        {"run_id": "bad; flush ruleset"},
    ],
)
def test_plan_rejects_scope_drift(change: dict[str, Any]) -> None:
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_plan_unknown$"):
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
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_scope_unknown$"):
        duplex.make_binding(
            plan(), fixture(numeric=numeric), (30, 999999), host_context=HOST
        )


def test_allow_stall_resume_tracks_rule_handles_and_monotonic_both_directions() -> None:
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
    resumed_raw = fixture("allow", offset=30, packets=(4, 5, 1, 1, 0, 0))
    resumed = duplex.capture_phase(
        plan(),
        resumed_raw,
        phase="allow",
        host_context=HOST,
        binding=b,
        previous_reference=stalled,
        previous_counts=current,
    )
    final = verify(resumed_raw, b, resumed, previous=current)
    assert final.allowed_in == 4 and final.allowed_out == 5
    with pytest.raises(
        duplex.DuplexRejected, match=r"^duplex_phase_reference_unknown$"
    ):
        verify(resumed_raw, b, allowed, previous=current)


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
        duplex.DuplexRejected, match=r"^duplex_(state|binding|phase_reference)_unknown$"
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
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_late_packet$"):
        duplex.verify_quiescent(
            plan(),
            fixture("allow", offset=10, packets=(4, 3, 0, 0, 0, 0)),
            phase="allow",
            host_context=HOST,
            binding=b,
            phase_reference=ref,
            previous_counts=last,
        )
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_counter_regressed$"):
        verify(
            fixture("allow", offset=10, packets=(2, 3, 0, 0, 0, 0)),
            b,
            ref,
            previous=last,
        )


def test_unexpected_packets_and_boolean_counts_are_blocking() -> None:
    b, ref = allow()
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_unexpected_packet$"):
        verify(fixture("allow", offset=10, packets=(0, 0, 0, 0, 1, 0)), b, ref)
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_counts_unknown$"):
        duplex.Counts(allowed_in=True)


def test_partial_or_duplicate_json_is_not_a_state() -> None:
    b, ref = allow()
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_state_unknown$"):
        verify(b'{"nftables":[],"nftables":[]}', b, ref)
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_state_unknown$"):
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
    end = duplex.capture_phase(
        plan(),
        fixture("allow", offset=30),
        phase="allow",
        host_context=HOST,
        binding=b,
        previous_reference=s,
        previous_counts=duplex.Counts(),
    )
    return b, [b["initial_reference"], a, s, end]


def test_complete_rule_reference_chain_has_single_cycle_and_predecessors() -> None:
    b, refs = complete_refs()
    duplex.verify_references(plan(), refs, host_context=HOST, binding=b)
    assert [r["sequence"] for r in refs] == [0, 1, 2, 3]
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_transition_unknown$"):
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
        refs.pop(2)
    elif change == "reordered":
        refs[1], refs[2] = refs[2], refs[1]
    elif change == "bad_predecessor":
        refs[-1]["previous_reference_sha256"] = "f" * 64
    elif change == "boolean_sequence":
        refs[1]["sequence"] = True
    with pytest.raises(
        duplex.DuplexRejected, match=r"^duplex_phase_reference_unknown$"
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
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_state_unknown$"):
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
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_binding_unknown$"):
        verify(fixture("allow", offset=10), b, ref)


def test_current_host_and_initial_zero_are_required() -> None:
    b = binding()
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_binding_unknown$"):
        duplex.verify_state(
            plan(),
            fixture(),
            phase="deny",
            host_context={**HOST, "kernel": "other"},
            binding=b,
            phase_reference=b["initial_reference"],
            previous_counts=duplex.Counts(),
        )
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_initial_counts_unknown$"):
        duplex.make_binding(
            plan(), fixture(packets=(1, 0, 0, 0, 0, 0)), (30, 888888), host_context=HOST
        )


def test_counter_bytes_cannot_regress_while_packets_are_unchanged() -> None:
    b, ref = allow()
    raw = fixture("allow", offset=10, packets=(2, 2, 0, 0, 0, 0))
    last = verify(raw, b, ref)
    raw["nftables"][6]["counter"]["bytes"] = 127
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_counter_regressed$"):
        verify(raw, b, ref, previous=last)


@pytest.mark.parametrize("numeric", ["0888888", 888889, True])
def test_unknown_scope_identifier_never_binds(numeric: object) -> None:
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_(scope|state)_unknown$"):
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
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_transition_unknown$"):
        duplex.capture_phase(
            plan(),
            fixture("allow", offset=99),
            phase="allow",
            host_context=HOST,
            binding=b,
            previous_reference=ref,
            previous_counts=duplex.Counts(),
        )


def test_counts_dict_exactness_and_bounds() -> None:
    c = duplex.Counts(1, 2, 3, 4, 0, 0, (64, 128, 192, 256, 0, 0))
    assert duplex.Counts.from_dict(c.to_dict()) == c
    for changed in [
        {},
        {**c.to_dict(), "other": {"packets": 0, "bytes": 0}},
        {**c.to_dict(), "allowed_in": {"packets": True, "bytes": 64}},
    ]:
        with pytest.raises(duplex.DuplexRejected, match=r"^duplex_counts_unknown$"):
            duplex.Counts.from_dict(changed)
    with pytest.raises(duplex.DuplexRejected, match=r"^duplex_counts_unknown$"):
        duplex.Counts(byte_counts=(0, 0, 0, 0, 0, 2**64))
