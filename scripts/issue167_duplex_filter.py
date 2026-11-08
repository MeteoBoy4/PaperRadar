"""Pure #167 duplex preparation; no host commands or network I/O.

References record complete observations after declared transactions, not
execution authority. The caller supplies independently observed CG identity.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

COUNTERS = (
    "allowed_in",
    "allowed_out",
    "dropped_in",
    "dropped_out",
    "unexpected_in",
    "unexpected_out",
)
CHAINS = ("out", "in", "phase_out", "phase_in")
PHASES = ("deny", "allow", "stall")
_HANDLES = frozenset(
    {"table", "scope_out", "scope_in"}
    | {"chain_" + n for n in CHAINS}
    | {"counter_" + n for n in COUNTERS}
)
_SEQUENCE = ("deny", "allow", "stall", "allow")


class DuplexRejected(ValueError):
    """Closed metadata reason; never includes external text or rule content."""


def _uint(value: object, *, positive: bool = False, reason: str) -> int:
    if type(value) is not int or not int(positive) <= value < 2**64:
        raise DuplexRejected(reason)
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _host(value: object) -> dict[str, str]:
    if (
        type(value) is not dict
        or set(value) != {"boot_id", "kernel", "machine", "hostname_sha256"}
        or any(type(v) is not str or not v for v in value.values())
        or re.fullmatch(
            r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", value["boot_id"]
        )
        is None
        or value["machine"] != "x86_64"
        or len(value["kernel"]) > 256
        or re.fullmatch(r"[a-f0-9]{64}", value["hostname_sha256"]) is None
    ):
        raise DuplexRejected("duplex_host_unknown")
    return dict(value)


def _phase(value: object) -> str:
    if type(value) is not str or value not in PHASES:
        raise DuplexRejected("duplex_phase_unknown")
    return value


@dataclass(frozen=True)
class Plan:
    run_id: str
    uid: int = 1000
    gid: int = 1000
    address: str = "127.0.0.1"
    port: int = 46167

    def __post_init__(self) -> None:
        if (
            type(self.run_id) is not str
            or re.fullmatch(r"[a-f0-9]{12}", self.run_id) is None
            or type(self.uid) is not int
            or self.uid != 1000
            or type(self.gid) is not int
            or self.gid != 1000
            or type(self.port) is not int
            or self.port != 46167
            or type(self.address) is not str
            or self.address != "127.0.0.1"
        ):
            raise DuplexRejected("duplex_plan_unknown")

    @property
    def table(self) -> str:
        return "paperradar167_" + self.run_id

    @property
    def unit(self) -> str:
        return "paperradar-167-h1net-" + self.run_id + ".service"

    @property
    def cgroup(self) -> str:
        return "/system.slice/" + self.unit

    def identity(self) -> dict[str, object]:
        return {
            "scope": "synthetic_loopback_duplex_only",
            "run_id": self.run_id,
            "uid": self.uid,
            "gid": self.gid,
            "unit": self.unit,
            "cgroup": self.cgroup,
            "table": self.table,
            "address": self.address,
            "port": self.port,
            "model_calls": 0,
            "ipv6": "not_assessed",
        }


@dataclass(frozen=True)
class Counts:
    allowed_in: int = 0
    allowed_out: int = 0
    dropped_in: int = 0
    dropped_out: int = 0
    unexpected_in: int = 0
    unexpected_out: int = 0
    byte_counts: tuple[int, ...] = (0, 0, 0, 0, 0, 0)

    def __post_init__(self) -> None:
        if type(self.byte_counts) is not tuple or len(self.byte_counts) != 6:
            raise DuplexRejected("duplex_counts_unknown")
        for value in (*self.packet_values(), *self.byte_counts):
            _uint(value, reason="duplex_counts_unknown")

    def packet_values(self) -> tuple[int, ...]:
        return tuple(getattr(self, name) for name in COUNTERS)

    @classmethod
    def zero(cls) -> Counts:
        return cls()

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {
            name: {"packets": count, "bytes": size}
            for name, count, size in zip(
                COUNTERS, self.packet_values(), self.byte_counts, strict=True
            )
        }

    @classmethod
    def from_dict(cls, value: object) -> Counts:
        if type(value) is not dict or set(value) != set(COUNTERS):
            raise DuplexRejected("duplex_counts_unknown")
        packets, sizes = [], []
        for name in COUNTERS:
            row = value[name]
            if type(row) is not dict or set(row) != {"packets", "bytes"}:
                raise DuplexRejected("duplex_counts_unknown")
            packets.append(_uint(row["packets"], reason="duplex_counts_unknown"))
            sizes.append(_uint(row["bytes"], reason="duplex_counts_unknown"))
        return cls(
            packets[0],
            packets[1],
            packets[2],
            packets[3],
            packets[4],
            packets[5],
            tuple(sizes),
        )

    def require_at_least(self, previous: Counts) -> None:
        if type(previous) is not Counts:
            raise DuplexRejected("duplex_counts_unknown")
        if any(
            now < before
            for now, before in zip(
                (*self.packet_values(), *self.byte_counts),
                (*previous.packet_values(), *previous.byte_counts),
                strict=True,
            )
        ):
            raise DuplexRejected("duplex_counter_regressed")

    def require_no_unexpected(self) -> None:
        if self.unexpected_in or self.unexpected_out or any(self.byte_counts[4:]):
            raise DuplexRejected("duplex_unexpected_packet")


def _check_plan(plan: Plan) -> None:
    if type(plan) is not Plan:
        raise DuplexRejected("duplex_plan_unknown")
    plan.__post_init__()


def _phase_lines(plan: Plan, phase: str) -> list[str]:
    selected = _phase(phase)
    result = []
    for direction, address_field, port_field in (
        ("out", "daddr", "dport"),
        ("in", "saddr", "sport"),
    ):
        chain = "phase_" + direction
        if selected != "deny":
            counter = ("allowed_" if selected == "allow" else "dropped_") + direction
            verdict = "accept" if selected == "allow" else "drop"
            result.append(
                f"add rule inet {plan.table} {chain} "
                f"ip {address_field} {plan.address} tcp {port_field} {plan.port} "
                f"counter name {counter} {verdict} "
                f'comment "issue167:{plan.run_id}:duplex:{selected}-{direction}"'
            )
        result.append(
            f"add rule inet {plan.table} {chain} "
            f"counter name unexpected_{direction} drop "
            f'comment "issue167:{plan.run_id}:duplex:unexpected-{direction}"'
        )
    return result


def render_create(plan: Plan) -> str:
    _check_plan(plan)
    lines = [f"create table inet {plan.table}"]
    lines += [f"add counter inet {plan.table} {name}" for name in COUNTERS]
    for name, hook in (("out", "output"), ("in", "input")):
        lines.append(
            f"add chain inet {plan.table} {name} "
            f"{{ type filter hook {hook} priority 10; policy accept; }}"
        )
    lines += [
        f"add chain inet {plan.table} {name}" for name in ("phase_out", "phase_in")
    ]
    for direction in ("out", "in"):
        lines.append(
            f"add rule inet {plan.table} {direction} socket cgroupv2 level 2 "
            f'"{plan.cgroup[1:]}" jump phase_{direction} '
            f'comment "issue167:{plan.run_id}:duplex:scope-{direction}"'
        )
    return "\n".join([*lines, *_phase_lines(plan, "deny"), ""])


def _render_switch(plan: Plan, phase: str) -> str:
    _check_plan(plan)
    return "\n".join(
        [
            f"flush chain inet {plan.table} phase_out",
            f"flush chain inet {plan.table} phase_in",
            *_phase_lines(plan, phase),
            "",
        ]
    )


def render_allow(plan: Plan) -> str:
    return _render_switch(plan, "allow")


def render_stall(plan: Plan) -> str:
    return _render_switch(plan, "stall")


def render_delete(plan: Plan) -> str:
    _check_plan(plan)
    return f"delete table inet {plan.table}\n"


def _match(protocol: str, field: str, right: object) -> dict[str, object]:
    return {
        "match": {
            "op": "==",
            "left": {"payload": {"protocol": protocol, "field": field}},
            "right": right,
        }
    }


def _definitions(plan: Plan, phase: str) -> dict[str, Any]:
    """Expected JSON is specified independently of nft text formatting."""
    common = {"family": "inet", "table": plan.table}
    chains: dict[str, dict[str, Any]] = {
        name: {**common, "name": name} for name in CHAINS
    }
    chains["out"].update(type="filter", hook="output", prio=10, policy="accept")
    chains["in"].update(type="filter", hook="input", prio=10, policy="accept")
    rules: dict[str, list[dict[str, Any]]] = {}
    for direction in ("out", "in"):
        rules[direction] = [
            {
                **common,
                "chain": direction,
                "comment": f"issue167:{plan.run_id}:duplex:scope-{direction}",
                "expr": [
                    {
                        "match": {
                            "op": "==",
                            "left": {"socket": {"key": "cgroupv2"}},
                            "right": plan.cgroup[1:],
                        }
                    },
                    {"jump": {"target": "phase_" + direction}},
                ],
            }
        ]
        current: list[dict[str, Any]] = []
        if phase != "deny":
            address_field, port_field = (
                ("daddr", "dport") if direction == "out" else ("saddr", "sport")
            )
            counter = ("allowed_" if phase == "allow" else "dropped_") + direction
            current.append(
                {
                    **common,
                    "chain": "phase_" + direction,
                    "comment": f"issue167:{plan.run_id}:duplex:{phase}-{direction}",
                    "expr": [
                        _match("ip", address_field, plan.address),
                        _match("tcp", port_field, plan.port),
                        {"counter": counter},
                        {"accept" if phase == "allow" else "drop": None},
                    ],
                }
            )
        current.append(
            {
                **common,
                "chain": "phase_" + direction,
                "comment": f"issue167:{plan.run_id}:duplex:unexpected-{direction}",
                "expr": [{"counter": "unexpected_" + direction}, {"drop": None}],
            }
        )
        rules["phase_" + direction] = current
    return {
        "table": {"family": "inet", "name": plan.table},
        "chains": chains,
        "rules": rules,
    }


def _normalize(value: object, depth: int = 0) -> Any:
    if depth > 16:
        raise DuplexRejected("duplex_state_unknown")
    if type(value) is dict:
        if len(value) > 32 or any(type(k) is not str for k in value):
            raise DuplexRejected("duplex_state_unknown")
        result = {k: _normalize(v, depth + 1) for k, v in value.items()}
        if (
            set(result) == {"socket"}
            and type(result["socket"]) is dict
            and "level" in result["socket"]
        ):
            if (
                type(result["socket"]["level"]) is not int
                or result["socket"]["level"] != 2
            ):
                raise DuplexRejected("duplex_state_unknown")
            result["socket"].pop("level")
        return result
    if type(value) is list:
        if len(value) > 32:
            raise DuplexRejected("duplex_state_unknown")
        return [_normalize(v, depth + 1) for v in value]
    if type(value) not in (str, int, type(None)) or (
        type(value) is str and len(value) > 4096
    ):
        raise DuplexRejected("duplex_state_unknown")
    return value


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise DuplexRejected("duplex_state_unknown")
        result[key] = value
    return result


def _structure(
    plan: Plan, phase: str, handles: dict[str, int], dynamic: dict[str, list[int]]
) -> dict[str, Any]:
    expected = _definitions(plan, phase)
    return {
        "table": {**expected["table"], "handle": handles["table"]},
        "chains": {
            name: {**row, "handle": handles["chain_" + name]}
            for name, row in expected["chains"].items()
        },
        "counters": {
            name: {
                "family": "inet",
                "table": plan.table,
                "name": name,
                "handle": handles["counter_" + name],
            }
            for name in COUNTERS
        },
        "rules": {
            name: [
                {**row, "handle": handle}
                for row, handle in zip(
                    rows,
                    [handles["scope_" + name]]
                    if name in {"in", "out"}
                    else dynamic[name],
                    strict=True,
                )
            ]
            for name, rows in expected["rules"].items()
        },
    }


@dataclass(frozen=True)
class _State:
    handles: dict[str, int]
    dynamic: dict[str, list[int]]
    counts: Counts


def _state(plan: Plan, payload: object, phase: str, inode: int) -> _State:
    expected = _definitions(plan, phase)
    try:
        if type(payload) is bytes:
            if len(payload) > 65536:
                raise ValueError
            payload = json.loads(payload, object_pairs_hook=_pairs)
        if type(payload) is not dict or set(payload) != {"nftables"}:
            raise ValueError
        raw_rows = payload["nftables"]
        if type(raw_rows) is not list or not 1 <= len(raw_rows) <= 32:
            raise ValueError
        rows = copy.deepcopy(raw_rows)
        table, chains, counters = [], {}, {}
        rules: dict[str, list[dict[str, Any]]] = {name: [] for name in CHAINS}
        handles: dict[str, int] = {}
        dynamic: dict[str, list[int]] = {"phase_in": [], "phase_out": []}
        rule_handles: list[int] = []
        seen_meta = False
        for row in rows:
            if type(row) is not dict or len(row) != 1:
                raise ValueError
            kind, item = next(iter(row.items()))
            if type(item) is not dict:
                raise ValueError
            if kind == "metainfo":
                if seen_meta or set(item) - {
                    "version",
                    "release_name",
                    "json_schema_version",
                }:
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
                seen_meta = True
                continue
            clean = dict(item)
            handle = _uint(
                clean.pop("handle", None), positive=True, reason="duplex_state_unknown"
            )
            normalized = _normalize(clean)
            if kind == "table":
                table.append(normalized)
                if "table" in handles:
                    raise ValueError
                handles["table"] = handle
            elif kind == "chain":
                name = clean.get("name")
                if type(name) is not str or name not in CHAINS or name in chains:
                    raise ValueError
                chains[name] = normalized
                handles["chain_" + name] = handle
            elif kind == "counter":
                name = clean.get("name")
                if (
                    type(name) is not str
                    or name not in COUNTERS
                    or name in counters
                    or set(clean) != {"family", "table", "name", "packets", "bytes"}
                    or clean["family"] != "inet"
                    or clean["table"] != plan.table
                ):
                    raise ValueError
                counters[name] = {
                    k: _uint(clean[k], reason="duplex_state_unknown")
                    for k in ("packets", "bytes")
                }
                handles["counter_" + name] = handle
            elif kind == "rule":
                name = clean.get("chain")
                if type(name) is not str or name not in rules:
                    raise ValueError
                rule_handles.append(handle)
                if name in {"out", "in"}:
                    if rules[name]:
                        raise ValueError
                    right = normalized["expr"][0]["match"]["right"]
                    if not (type(right) is str and right == plan.cgroup[1:]):
                        if (type(right) is int and right == inode) or (
                            type(right) is str and right == str(inode)
                        ):
                            normalized["expr"][0]["match"]["right"] = plan.cgroup[1:]
                        else:
                            raise DuplexRejected("duplex_scope_unknown")
                    handles["scope_" + name] = handle
                else:
                    dynamic[name].append(handle)
                rules[name].append(normalized)
            else:
                raise ValueError
        if (
            table != [expected["table"]]
            or chains != expected["chains"]
            or rules != expected["rules"]
            or set(counters) != set(COUNTERS)
            or set(handles) != _HANDLES
        ):
            raise ValueError
        # Linux v7.0 nf_tables_api.c uses table.hgenerator for chains, rules
        # and objects (984,2599,4042,7784); table_handle is separate (1559).
        object_handles = [handles["chain_" + n] for n in CHAINS]
        object_handles += [handles["counter_" + n] for n in COUNTERS]
        object_handles += rule_handles
        if len(set(object_handles)) != len(object_handles):
            raise ValueError
        return _State(handles, dynamic, Counts.from_dict(counters))
    except DuplexRejected:
        raise
    except (ValueError, KeyError, TypeError, IndexError, UnicodeError, RecursionError):
        raise DuplexRejected("duplex_state_unknown") from None


def _base_binding(
    plan: Plan, host_context: object, device: int, inode: int, handles: dict[str, int]
) -> dict[str, Any]:
    return {
        "schema": 1,
        "source": "independent_live_cgroup2_identity",
        "identity_sha256": _digest(
            {"plan": plan.identity(), "host": _host(host_context)}
        ),
        "cgroup_device": device,
        "cgroup_inode": inode,
        "handles": handles,
    }


def _reference(
    plan: Plan,
    phase: str,
    state: _State,
    base: dict[str, Any],
    *,
    sequence: int = 0,
    previous: object = None,
) -> dict[str, Any]:
    return {
        "schema": 1,
        "source": "complete_bound_duplex_phase",
        "binding_sha256": _digest(base),
        "phase": phase,
        "sequence": sequence,
        "previous_reference_sha256": None if previous is None else _digest(previous),
        "rule_handles": state.dynamic,
        "structure_sha256": _digest(
            _structure(plan, phase, state.handles, state.dynamic)
        ),
        "counts": state.counts.to_dict(),
    }


def _reference_counts(
    plan: Plan,
    reference: object,
    base: dict[str, Any],
    *,
    expected_phase: str | None = None,
) -> Counts:
    try:
        if (
            type(reference) is not dict
            or set(reference)
            != {
                "schema",
                "source",
                "binding_sha256",
                "phase",
                "sequence",
                "previous_reference_sha256",
                "rule_handles",
                "structure_sha256",
                "counts",
            }
            or type(reference["schema"]) is not int
            or reference["schema"] != 1
            or reference["source"] != "complete_bound_duplex_phase"
            or reference["binding_sha256"] != _digest(base)
        ):
            raise ValueError
        phase = _phase(reference["phase"])
        sequence = reference["sequence"]
        if (
            type(sequence) is not int
            or not 0 <= sequence < 4
            or phase != _SEQUENCE[sequence]
        ):
            raise ValueError
        predecessor = reference["previous_reference_sha256"]
        if sequence == 0:
            if predecessor is not None:
                raise ValueError
        elif (
            type(predecessor) is not str
            or re.fullmatch(r"[a-f0-9]{64}", predecessor) is None
        ):
            raise ValueError
        if expected_phase is not None and phase != expected_phase:
            raise ValueError
        dynamic = reference["rule_handles"]
        if type(dynamic) is not dict or set(dynamic) != {"phase_in", "phase_out"}:
            raise ValueError
        all_handles = [v for k, v in base["handles"].items() if k != "table"]
        for name in ("phase_in", "phase_out"):
            values = dynamic[name]
            if type(values) is not list or len(values) != (1 if phase == "deny" else 2):
                raise ValueError
            all_handles += [
                _uint(v, positive=True, reason="duplex_phase_reference_unknown")
                for v in values
            ]
        if len(set(all_handles)) != len(all_handles) or reference[
            "structure_sha256"
        ] != _digest(_structure(plan, phase, base["handles"], dynamic)):
            raise ValueError
        counts = Counts.from_dict(reference["counts"])
        counts.require_no_unexpected()
        return counts
    except (DuplexRejected, ValueError, KeyError, TypeError):
        raise DuplexRejected("duplex_phase_reference_unknown") from None


def _binding(plan: Plan, value: object, host_context: object) -> dict[str, Any]:
    _check_plan(plan)
    _host(host_context)
    try:
        if type(value) is not dict or set(value) != {
            "schema",
            "source",
            "identity_sha256",
            "cgroup_device",
            "cgroup_inode",
            "handles",
            "initial_reference",
        }:
            raise ValueError
        handles = value["handles"]
        if type(handles) is not dict or set(handles) != _HANDLES:
            raise ValueError
        for handle in handles.values():
            _uint(handle, positive=True, reason="duplex_binding_unknown")
        object_handles = [v for k, v in handles.items() if k != "table"]
        if len(set(object_handles)) != len(object_handles):
            raise ValueError
        device = _uint(value["cgroup_device"], reason="duplex_binding_unknown")
        inode = _uint(
            value["cgroup_inode"], positive=True, reason="duplex_binding_unknown"
        )
        base = {k: value[k] for k in value if k != "initial_reference"}
        if _digest(base) != _digest(
            _base_binding(plan, host_context, device, inode, handles)
        ):
            raise ValueError
        if (
            _reference_counts(
                plan, value["initial_reference"], base, expected_phase="deny"
            )
            != Counts()
        ):
            raise ValueError
        return base
    except (DuplexRejected, ValueError, KeyError, TypeError):
        raise DuplexRejected("duplex_binding_unknown") from None


def make_binding(
    plan: Plan, payload: object, identity: tuple[int, int], *, host_context: object
) -> dict[str, Any]:
    """Bind an exact initial zero/deny snapshot to separately observed CG data."""
    _check_plan(plan)
    _host(host_context)
    if type(identity) is not tuple or len(identity) != 2:
        raise DuplexRejected("duplex_binding_unknown")
    device = _uint(identity[0], reason="duplex_binding_unknown")
    inode = _uint(identity[1], positive=True, reason="duplex_binding_unknown")
    state = _state(plan, payload, "deny", inode)
    if state.counts != Counts():
        raise DuplexRejected("duplex_initial_counts_unknown")
    base = _base_binding(plan, host_context, device, inode, state.handles)
    return {**base, "initial_reference": _reference(plan, "deny", state, base)}


def capture_phase(
    plan: Plan,
    payload: object,
    *,
    phase: str,
    host_context: object,
    binding: object,
    previous_reference: object,
    previous_counts: Counts,
) -> dict[str, Any]:
    """Only call after one declared nft transaction; this function has no I/O."""
    selected = _phase(phase)
    base = _binding(plan, binding, host_context)
    recorded = _reference_counts(plan, previous_reference, base)
    assert isinstance(previous_reference, dict)
    sequence = previous_reference["sequence"] + 1
    if sequence >= 4 or selected != _SEQUENCE[sequence]:
        raise DuplexRejected("duplex_transition_unknown")
    state = _state(plan, payload, selected, base["cgroup_inode"])
    if state.handles != base["handles"]:
        raise DuplexRejected("duplex_binding_unknown")
    state.counts.require_at_least(recorded)
    state.counts.require_at_least(previous_counts)
    state.counts.require_no_unexpected()
    return _reference(
        plan, selected, state, base, sequence=sequence, previous=previous_reference
    )


def verify_state(
    plan: Plan,
    payload: object,
    *,
    phase: str,
    host_context: object,
    binding: object,
    phase_reference: object,
    previous_counts: Counts,
) -> Counts:
    selected = _phase(phase)
    base = _binding(plan, binding, host_context)
    recorded = _reference_counts(plan, phase_reference, base, expected_phase=selected)
    state = _state(plan, payload, selected, base["cgroup_inode"])
    if state.handles != base["handles"]:
        raise DuplexRejected("duplex_binding_unknown")
    assert isinstance(phase_reference, dict)
    if (
        state.dynamic != phase_reference["rule_handles"]
        or _digest(_structure(plan, selected, state.handles, state.dynamic))
        != phase_reference["structure_sha256"]
    ):
        raise DuplexRejected("duplex_phase_reference_unknown")
    state.counts.require_at_least(recorded)
    state.counts.require_at_least(previous_counts)
    state.counts.require_no_unexpected()
    return state.counts


def verify_quiescent(
    plan: Plan,
    payload: object,
    *,
    phase: str,
    host_context: object,
    binding: object,
    phase_reference: object,
    previous_counts: Counts,
) -> Counts:
    current = verify_state(
        plan,
        payload,
        phase=phase,
        host_context=host_context,
        binding=binding,
        phase_reference=phase_reference,
        previous_counts=previous_counts,
    )
    if current != previous_counts:
        raise DuplexRejected("duplex_late_packet")
    return current


def verify_references(
    plan: Plan, references: object, *, host_context: object, binding: object
) -> None:
    """Validate the complete single deny/allow/stall/resume observation chain."""
    base = _binding(plan, binding, host_context)
    if type(references) is not list or len(references) != 4:
        raise DuplexRejected("duplex_phase_reference_unknown")
    assert isinstance(binding, dict)
    if references[0] != binding["initial_reference"]:
        raise DuplexRejected("duplex_phase_reference_unknown")
    previous_counts = Counts()
    for sequence, reference in enumerate(references):
        counts = _reference_counts(
            plan, reference, base, expected_phase=_SEQUENCE[sequence]
        )
        if reference["sequence"] != sequence or (
            sequence
            and reference["previous_reference_sha256"]
            != _digest(references[sequence - 1])
        ):
            raise DuplexRejected("duplex_phase_reference_unknown")
        try:
            counts.require_at_least(previous_counts)
        except DuplexRejected:
            raise DuplexRejected("duplex_phase_reference_unknown") from None
        previous_counts = counts
