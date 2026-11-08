"""#167 无凭据H1计划/规则纯逻辑与有界cgroup元数据读取;无宿主执行。"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Phase = Literal["deny", "a", "b"]
NetworkMode = Literal["dual_stack", "ipv4_only"]
_PHASES = frozenset({"deny", "a", "b"})
_MAX_JSON = 16384
_MAX_GROUPS = 32
_MAX_PIDS = 256
_MAX_PROC_BYTES = 16384
_MAX_ENTRIES = 256


class PhaseRejected(ValueError):
    """受控原因;不包含输入、路径或外部异常原文。"""


def _integer(value: object, reason: str) -> int:
    if type(value) is not int:
        raise PhaseRejected(reason)
    return value


def _network_mode(value: object) -> NetworkMode:
    if type(value) is not str or value not in {"dual_stack", "ipv4_only"}:
        raise PhaseRejected("plan_network_mode_invalid")
    return "ipv4_only" if value == "ipv4_only" else "dual_stack"


@dataclass(frozen=True)
class Plan:
    run_id: str
    uid: int
    gid: int
    port_a: int = 38167
    port_b: int = 38169
    blocked_port: int = 38168
    timeout_s: int = 120
    network_mode: NetworkMode = "dual_stack"

    def __post_init__(self) -> None:
        _network_mode(self.network_mode)
        if (
            type(self.run_id) is not str
            or re.fullmatch(r"[a-f0-9]{12}", self.run_id) is None
        ):
            raise PhaseRejected("plan_run_invalid")
        if any(
            type(value) is not int or not 1 <= value <= 2**31 - 1
            for value in (self.uid, self.gid)
        ):
            raise PhaseRejected("plan_identity_invalid")
        if (self.port_a, self.port_b, self.blocked_port) != (
            38167,
            38169,
            38168,
        ) or any(
            type(value) is not int
            for value in (self.port_a, self.port_b, self.blocked_port)
        ):
            raise PhaseRejected("plan_ports_invalid")
        if type(self.timeout_s) is not int or self.timeout_s != 120:
            raise PhaseRejected("plan_timeout_invalid")

    @property
    def unit(self) -> str:
        return f"paperradar-167-h1net-{self.run_id}.service"

    @property
    def guardian_unit(self) -> str:
        return f"paperradar-167-h1guard-{self.run_id}.service"

    @property
    def table(self) -> str:
        return f"paperradar167_{self.run_id}"

    @property
    def install_root(self) -> Path:
        return Path(f"/home/paperradar-probes/issue167-{self.run_id}")

    @property
    def runtime_root(self) -> Path:
        return Path(f"/run/paperradar-issue167-{self.run_id}")

    @property
    def cgroup(self) -> str:
        return f"/system.slice/{self.unit}"

    @property
    def cgroup_level(self) -> int:
        return 2

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "run_id": self.run_id,
            "uid": self.uid,
            "gid": self.gid,
            "unit": self.unit,
            "guardian_unit": self.guardian_unit,
            "table": self.table,
            "install_root": str(self.install_root),
            "runtime_root": str(self.runtime_root),
            "cgroup": self.cgroup,
            "cgroup_level": self.cgroup_level,
            "ports": {"a": self.port_a, "b": self.port_b, "blocked": self.blocked_port},
            "addresses": (
                ["127.0.0.1"]
                if self.network_mode == "ipv4_only"
                else ["127.0.0.1", "::1"]
            ),
            "timeout_s": self.timeout_s,
            "mode": "synthetic_local",
            "authorization": "not_granted",
        }
        # Preserve the exact historical default plan shape. New narrower plans
        # explicitly bind their mode; omitted mode cannot mean IPv4-only.
        if self.network_mode == "ipv4_only":
            value["network_mode"] = self.network_mode
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"

    @classmethod
    def from_dict(cls, value: object) -> Plan:
        if type(value) is not dict:
            raise PhaseRejected("plan_shape_invalid")
        data: dict[object, object] = value
        if any(type(key) is not str for key in data):
            raise PhaseRejected("plan_shape_invalid")
        ports = data.get("ports")
        if type(ports) is not dict or set(ports) != {"a", "b", "blocked"}:
            raise PhaseRejected("plan_ports_invalid")
        run_id = data.get("run_id")
        if type(run_id) is not str:
            raise PhaseRejected("plan_run_invalid")
        plan = cls(
            run_id,
            _integer(data.get("uid"), "plan_identity_invalid"),
            _integer(data.get("gid"), "plan_identity_invalid"),
            _integer(ports.get("a"), "plan_ports_invalid"),
            _integer(ports.get("b"), "plan_ports_invalid"),
            _integer(ports.get("blocked"), "plan_ports_invalid"),
            _integer(data.get("timeout_s"), "plan_timeout_invalid"),
            _network_mode(data.get("network_mode", "dual_stack")),
        )
        expected = plan.to_dict()
        if set(data) != set(expected) or data != expected:
            raise PhaseRejected("plan_binding_mismatch")
        # bool==int must not validate a forged level, even when Python compares equal.
        if type(data.get("cgroup_level")) is not int:
            raise PhaseRejected("plan_binding_mismatch")
        return plan


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PhaseRejected("json_duplicate_key")
        result[key] = value
    return result


def _read_bounded(descriptor: int, limit: int, reason: str) -> bytes:
    result = bytearray()
    while True:
        chunk = os.read(descriptor, limit + 1 - len(result))
        if not chunk:
            return bytes(result)
        result.extend(chunk)
        if len(result) > limit:
            raise PhaseRejected(reason)


def load_plan(path: Path) -> Plan:
    descriptor = -1
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PhaseRejected("plan_file_invalid")
        raw = _read_bounded(descriptor, _MAX_JSON, "plan_file_too_large")
        value = json.loads(raw, object_pairs_hook=_object)
        return Plan.from_dict(value)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise PhaseRejected("plan_file_invalid") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _phase(phase: str) -> Phase:
    if type(phase) is not str or phase not in _PHASES:
        raise PhaseRejected("phase_invalid")
    if phase == "a":
        return "a"
    if phase == "b":
        return "b"
    return "deny"


def _phase_lines(plan: Plan, phase: str) -> list[str]:
    selected = _phase(phase)
    lines = []
    if selected != "deny":
        port = plan.port_a if selected == "a" else plan.port_b
        for protocol, address, tag in _network_destinations(plan):
            lines.append(
                f"add rule inet {plan.table} phase {protocol} daddr {address} "
                f"tcp dport {port} counter name allowed accept "
                f'comment "issue167:{plan.run_id}:{selected}:{tag}"'
            )
    lines.append(
        f"add rule inet {plan.table} phase counter name rejected "
        "reject with icmpx type admin-prohibited "
        f'comment "issue167:{plan.run_id}:reject"'
    )
    return lines


def _network_destinations(plan: Plan) -> tuple[tuple[str, str, str], ...]:
    if plan.network_mode == "ipv4_only":
        return (("ip", "127.0.0.1", "ipv4"),)
    return (("ip", "127.0.0.1", "ipv4"), ("ip6", "::1", "ipv6"))


def render_create(plan: Plan) -> str:
    return "\n".join(
        [
            f"create table inet {plan.table}",
            f"add counter inet {plan.table} allowed {{ packets 0 bytes 0; }}",
            f"add counter inet {plan.table} rejected {{ packets 0 bytes 0; }}",
            f"add chain inet {plan.table} out "
            "{ type filter hook output priority 10; policy accept; }",
            f"add chain inet {plan.table} phase",
            f"add rule inet {plan.table} out socket cgroupv2 level 2 "
            f'"{plan.cgroup[1:]}" '
            f'jump phase comment "issue167:{plan.run_id}:scope"',
            *_phase_lines(plan, "deny"),
            "",
        ]
    )


def render_phase(plan: Plan, phase: str) -> str:
    return "\n".join(
        [f"flush chain inet {plan.table} phase", *_phase_lines(plan, phase), ""]
    )


def render_delete(plan: Plan) -> str:
    return f"delete table inet {plan.table}\n"


def _match(protocol: str, field: str, value: str | int) -> dict[str, object]:
    return {
        "match": {
            "op": "==",
            "left": {"payload": {"protocol": protocol, "field": field}},
            "right": value,
        }
    }


def _expected_rules(plan: Plan, phase: str) -> list[dict[str, object]]:
    selected = _phase(phase)
    rules: list[dict[str, object]] = [
        {
            "family": "inet",
            "table": plan.table,
            "chain": "out",
            "expr": [
                {
                    "match": {
                        "op": "==",
                        "left": {"socket": {"key": "cgroupv2"}},
                        "right": plan.cgroup[1:],
                    }
                },
                {"jump": {"target": "phase"}},
            ],
            "comment": f"issue167:{plan.run_id}:scope",
        },
    ]
    if selected != "deny":
        port = plan.port_a if selected == "a" else plan.port_b
        for protocol, address, tag in _network_destinations(plan):
            rules.append(
                {
                    "family": "inet",
                    "table": plan.table,
                    "chain": "phase",
                    "expr": [
                        _match(protocol, "daddr", address),
                        _match("tcp", "dport", port),
                        {"counter": "allowed"},
                        {"accept": None},
                    ],
                    "comment": f"issue167:{plan.run_id}:{selected}:{tag}",
                }
            )
    rules.append(
        {
            "family": "inet",
            "table": plan.table,
            "chain": "phase",
            "expr": [{"counter": "rejected"}, {"reject": {"type": "icmpx", "expr": 3}}],
            "comment": f"issue167:{plan.run_id}:reject",
        }
    )
    return rules


def _without_handle(value: object) -> dict[str, object]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise PhaseRejected("nft_state_unknown")
    result: dict[str, object] = dict(value)
    if "handle" in result:
        handle = result.pop("handle")
        if type(handle) is not int or handle < 0:
            raise PhaseRejected("nft_state_unknown")
    return result


def _normalize_expression(value: object, depth: int = 0) -> object:
    if depth > 16:
        raise PhaseRejected("nft_state_unknown")
    if type(value) is dict:
        if len(value) > 16 or any(type(key) is not str for key in value):
            raise PhaseRejected("nft_state_unknown")
        result = {
            key: _normalize_expression(item, depth + 1) for key, item in value.items()
        }
        if set(result) == {"socket"} and type(result["socket"]) is dict:
            socket_value = dict(result["socket"])
            if "level" in socket_value:
                level = socket_value.pop("level")
                if type(level) is not int or level != 2:
                    raise PhaseRejected("nft_state_unknown")
            result["socket"] = socket_value
        if set(result) == {"reject"} and type(result["reject"]) is dict:
            reject = dict(result["reject"])
            if (
                reject.get("type") == "icmpx"
                and reject.get("expr") == "admin-prohibited"
            ):
                reject["expr"] = 3
            result["reject"] = reject
        return result
    if type(value) is list:
        if len(value) > 16:
            raise PhaseRejected("nft_state_unknown")
        return [_normalize_expression(item, depth + 1) for item in value]
    if type(value) not in (str, int, type(None)):
        raise PhaseRejected("nft_state_unknown")
    return value


def verify_nft_state(plan: Plan, phase: str, payload: object) -> tuple[int, int]:
    """只接收单独list table的JSON;返回named counter包数,不是HTTP请求数。"""
    selected = _phase(phase)
    try:
        if type(payload) is not dict or set(payload) != {"nftables"}:
            raise PhaseRejected("nft_state_unknown")
        rows = payload["nftables"]
        if type(rows) is not list or len(rows) > 16:
            raise PhaseRejected("nft_state_unknown")
        tables = []
        chains = []
        rules = []
        counters: dict[str, int] = {}
        seen_meta = False
        for row in rows:
            if type(row) is not dict or len(row) != 1:
                raise PhaseRejected("nft_state_unknown")
            kind, item = next(iter(row.items()))
            if kind == "metainfo":
                if (
                    seen_meta
                    or type(item) is not dict
                    or set(item) - {"version", "release_name", "json_schema_version"}
                ):
                    raise PhaseRejected("nft_state_unknown")
                seen_meta = True
                continue
            clean = _without_handle(item)
            _normalize_expression(clean)  # Reject bool/float scalar coercion.
            if kind == "table":
                tables.append(clean)
            elif kind == "chain":
                chains.append(clean)
            elif kind == "rule":
                rules.append(_normalize_expression(clean))
            elif kind == "counter":
                if (
                    set(clean) != {"family", "table", "name", "packets", "bytes"}
                    or clean["family"] != "inet"
                    or clean["table"] != plan.table
                    or clean["name"] not in {"allowed", "rejected"}
                ):
                    raise PhaseRejected("nft_state_unknown")
                values = {
                    key: _integer(clean[key], "nft_state_unknown")
                    for key in ("packets", "bytes")
                }
                if any(not 0 <= value < 2**64 for value in values.values()):
                    raise PhaseRejected("nft_state_unknown")
                name = clean["name"]
                if type(name) is not str or name in counters:
                    raise PhaseRejected("nft_state_unknown")
                counters[name] = values["packets"]
            else:
                raise PhaseRejected("nft_state_unknown")
        expected_chains = [
            {
                "family": "inet",
                "table": plan.table,
                "name": "out",
                "type": "filter",
                "hook": "output",
                "prio": 10,
                "policy": "accept",
            },
            {"family": "inet", "table": plan.table, "name": "phase"},
        ]
        if (
            tables != [{"family": "inet", "name": plan.table}]
            or chains != expected_chains
            or rules != _expected_rules(plan, selected)
            or set(counters) != {"allowed", "rejected"}
        ):
            raise PhaseRejected("nft_state_unknown")
        return counters["allowed"], counters["rejected"]
    except (KeyError, TypeError, ValueError, StopIteration):
        raise PhaseRejected("nft_state_unknown") from None


@dataclass(frozen=True)
class CgroupState:
    exists: bool
    pids: frozenset[int]
    group_count: int


def _open_directory(path: str | Path, *, dir_fd: int | None = None) -> int:
    return os.open(
        path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd
    )


def _read_pids(descriptor: int) -> frozenset[int]:
    handle = os.open(
        "cgroup.procs", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor
    )
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise PhaseRejected("cgroup_unknown")
        raw = _read_bounded(handle, _MAX_PROC_BYTES, "cgroup_limit_exceeded")
    finally:
        os.close(handle)
    rows = raw.splitlines()
    if any(
        not value.isdigit() or len(value) > 10 or not 1 <= int(value) <= 2**31 - 1
        for value in rows
    ):
        raise PhaseRejected("cgroup_unknown")
    pids = frozenset(int(value) for value in rows)
    if len(pids) != len(rows):
        raise PhaseRejected("cgroup_unknown")
    return pids


def read_cgroup_state(
    plan: Plan,
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    allow_absent: bool = False,
    max_groups: int = _MAX_GROUPS,
    max_pids: int = _MAX_PIDS,
) -> CgroupState:
    """fd-relative nofollow递归;读取不全、变化或超过上限均unknown。"""
    if (
        type(allow_absent) is not bool
        or type(max_groups) is not int
        or not 1 <= max_groups <= _MAX_GROUPS
        or type(max_pids) is not int
        or not 1 <= max_pids <= _MAX_PIDS
    ):
        raise PhaseRejected("cgroup_bounds_invalid")
    root_fd = slice_fd = unit_fd = -1
    count = 0
    pids: set[int] = set()

    def visit(descriptor: int) -> None:
        nonlocal count
        count += 1
        if count > max_groups:
            raise PhaseRejected("cgroup_limit_exceeded")
        initial = _read_pids(descriptor)
        if pids.intersection(initial):
            raise PhaseRejected("cgroup_changed")
        pids.update(initial)
        if len(pids) > max_pids:
            raise PhaseRejected("cgroup_limit_exceeded")
        entries = os.listdir(descriptor)
        if len(entries) > _MAX_ENTRIES:
            raise PhaseRejected("cgroup_limit_exceeded")
        children: list[tuple[str, int]] = []
        for name in entries:
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise PhaseRejected("cgroup_unknown")
            if stat.S_ISDIR(info.st_mode):
                children.append((name, info.st_ino))
            elif not stat.S_ISREG(info.st_mode):
                raise PhaseRejected("cgroup_unknown")
        for name, inode in sorted(children):
            child_fd = _open_directory(name, dir_fd=descriptor)
            try:
                if os.fstat(child_fd).st_ino != inode:
                    raise PhaseRejected("cgroup_changed")
                visit(child_fd)
            finally:
                os.close(child_fd)
        final_children = []
        for name in os.listdir(descriptor):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                final_children.append((name, info.st_ino))
            elif not stat.S_ISREG(info.st_mode):
                raise PhaseRejected("cgroup_changed")
        if (
            sorted(children) != sorted(final_children)
            or _read_pids(descriptor) != initial
        ):
            raise PhaseRejected("cgroup_changed")

    try:
        for parent in (cgroup_root, *cgroup_root.parents):
            if not stat.S_ISDIR(parent.lstat().st_mode):
                raise PhaseRejected("cgroup_unknown")
        root_fd = _open_directory(cgroup_root)
        slice_fd = _open_directory("system.slice", dir_fd=root_fd)
        try:
            unit_fd = _open_directory(plan.unit, dir_fd=slice_fd)
        except FileNotFoundError:
            if allow_absent:
                return CgroupState(False, frozenset(), 0)
            raise PhaseRejected("cgroup_missing") from None
        visit(unit_fd)
        return CgroupState(True, frozenset(pids), count)
    except OSError:
        raise PhaseRejected("cgroup_unknown") from None
    finally:
        for descriptor in (unit_fd, slice_fd, root_fd):
            if descriptor >= 0:
                os.close(descriptor)


def read_cgroup_pids(
    plan: Plan,
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    allow_absent: bool = False,
    max_groups: int = _MAX_GROUPS,
    max_pids: int = _MAX_PIDS,
) -> frozenset[int]:
    return read_cgroup_state(
        plan,
        cgroup_root=cgroup_root,
        allow_absent=allow_absent,
        max_groups=max_groups,
        max_pids=max_pids,
    ).pids
