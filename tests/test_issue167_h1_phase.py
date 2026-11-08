"""独立D1:计划/渲染/闭集nft元数据及临时cgroup树,不调用宿主工具。"""

import copy
import json
from pathlib import Path

import pytest

from scripts.issue167_h1_phase import (
    PhaseRejected,
    Plan,
    load_plan,
    read_cgroup_pids,
    read_cgroup_state,
    render_create,
    render_delete,
    render_phase,
    verify_nft_state,
)

RUN = "0123456789ab"
TABLE = "paperradar167_0123456789ab"
UNIT = "paperradar-167-h1net-0123456789ab.service"


def plan() -> Plan:
    return Plan(RUN, 1000, 1000)


def test_plan_roundtrip_has_exact_review_paths_and_no_authorization(
    tmp_path: Path,
) -> None:
    frozen = plan()
    assert frozen.unit == UNIT
    assert frozen.table == TABLE
    assert str(frozen.install_root) == "/home/paperradar-probes/issue167-0123456789ab"
    assert str(frozen.runtime_root) == "/run/paperradar-issue167-0123456789ab"
    assert frozen.cgroup == f"/system.slice/{UNIT}"
    assert frozen.cgroup_level == 2
    assert frozen.to_dict()["authorization"] == "not_granted"
    path = tmp_path / "plan.json"
    path.write_text(frozen.to_json())
    assert load_plan(path) == frozen == Plan.from_dict(frozen.to_dict())


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("run_id", "abc;delete ruleset", "plan_run_invalid"),
        ("uid", True, "plan_identity_invalid"),
        ("gid", 0, "plan_identity_invalid"),
        ("timeout_s", 121, "plan_timeout_invalid"),
        ("cgroup_level", 2.0, "plan_binding_mismatch"),
        ("unit", "ssh.service", "plan_binding_mismatch"),
        ("install_root", "/home/owner/replaceable", "plan_binding_mismatch"),
        ("runtime_root", "/tmp/runtime", "plan_binding_mismatch"),
        ("authorization", "approved", "plan_binding_mismatch"),
        ("addresses", ["127.0.0.0/8", "::1"], "plan_binding_mismatch"),
        ("extra", "unreviewed", "plan_binding_mismatch"),
    ],
)
def test_plan_rejects_drift_and_injection(
    field: str, value: object, reason: str
) -> None:
    data = plan().to_dict()
    data[field] = value
    with pytest.raises(PhaseRejected, match=rf"^{reason}$"):
        Plan.from_dict(data)


def test_plan_refuses_changed_ports_and_duplicate_json_key(tmp_path: Path) -> None:
    data = plan().to_dict()
    data["ports"] = {"a": 443, "b": 38169, "blocked": 38168}
    with pytest.raises(PhaseRejected, match=r"^plan_ports_invalid$"):
        Plan.from_dict(data)
    path = tmp_path / "plan.json"
    path.write_text('{"run_id":"one","run_id":"two"}')
    with pytest.raises(PhaseRejected, match=r"^json_duplicate_key$"):
        load_plan(path)
    path.write_text("x" * 16385)
    with pytest.raises(PhaseRejected, match=r"^plan_file_too_large$"):
        load_plan(path)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(PhaseRejected, match=r"^plan_file_invalid$"):
        load_plan(link)


def test_render_scope_initial_deny_and_atomic_phase_transactions() -> None:
    frozen = plan()
    create = render_create(frozen)
    assert create.startswith(f"create table inet {TABLE}\n")
    assert f'out socket cgroupv2 level 2 "system.slice/{UNIT}" jump phase' in create
    assert "policy accept" in create  # Unrelated groups are not changed by this table.
    assert "daddr" not in create
    assert "counter name rejected reject with icmpx type admin-prohibited" in create
    assert "flush ruleset" not in create
    for phase, port in (("a", 38167), ("b", 38169)):
        rendered = render_phase(frozen, phase)
        assert rendered.startswith(f"flush chain inet {TABLE} phase\n")
        assert f"ip daddr 127.0.0.1 tcp dport {port}" in rendered
        assert f"ip6 daddr ::1 tcp dport {port}" in rendered
        assert "udp" not in rendered
        assert "counter name allowed accept" in rendered
        assert "delete table" not in rendered and "flush counter" not in rendered
    assert "daddr" not in render_phase(frozen, "deny")
    assert render_delete(frozen) == f"delete table inet {TABLE}\n"
    with pytest.raises(PhaseRejected, match=r"^phase_invalid$"):
        render_phase(frozen, "a; flush ruleset")


def nft_fixture(phase: str = "a") -> dict[str, object]:
    base = {"family": "inet", "table": TABLE}
    rows: list[dict[str, object]] = [
        {"metainfo": {"version": "fixture", "json_schema_version": 1}},
        {"table": {"family": "inet", "name": TABLE, "handle": 10}},
        {
            "counter": {
                **base,
                "name": "allowed",
                "handle": 11,
                "packets": 4,
                "bytes": 200,
            }
        },
        {
            "counter": {
                **base,
                "name": "rejected",
                "handle": 12,
                "packets": 7,
                "bytes": 400,
            }
        },
        {
            "chain": {
                **base,
                "name": "out",
                "handle": 13,
                "type": "filter",
                "hook": "output",
                "prio": 10,
                "policy": "accept",
            }
        },
        {"chain": {**base, "name": "phase", "handle": 14}},
        {
            "rule": {
                **base,
                "chain": "out",
                "handle": 15,
                "expr": [
                    {
                        "match": {
                            "op": "==",
                            "left": {"socket": {"key": "cgroupv2"}},
                            "right": f"system.slice/{UNIT}",
                        }
                    },
                    {"jump": {"target": "phase"}},
                ],
                "comment": f"issue167:{RUN}:scope",
            }
        },
    ]
    if phase != "deny":
        port = {"a": 38167, "b": 38169}[phase]
        for protocol, address, label in (
            ("ip", "127.0.0.1", "ipv4"),
            ("ip6", "::1", "ipv6"),
        ):
            rows.append(
                {
                    "rule": {
                        **base,
                        "chain": "phase",
                        "expr": [
                            {
                                "match": {
                                    "op": "==",
                                    "left": {
                                        "payload": {
                                            "protocol": protocol,
                                            "field": "daddr",
                                        }
                                    },
                                    "right": address,
                                }
                            },
                            {
                                "match": {
                                    "op": "==",
                                    "left": {
                                        "payload": {"protocol": "tcp", "field": "dport"}
                                    },
                                    "right": port,
                                }
                            },
                            {"counter": "allowed"},
                            {"accept": None},
                        ],
                        "comment": f"issue167:{RUN}:{phase}:{label}",
                    }
                }
            )
    rows.append(
        {
            "rule": {
                **base,
                "chain": "phase",
                "expr": [
                    {"counter": "rejected"},
                    {"reject": {"type": "icmpx", "expr": "admin-prohibited"}},
                ],
                "comment": f"issue167:{RUN}:reject",
            }
        }
    )
    return {"nftables": rows}


@pytest.mark.parametrize("phase", ["deny", "a", "b"])
def test_verify_nft_state_accepts_only_bound_shape_and_counter_values(
    phase: str,
) -> None:
    assert verify_nft_state(plan(), phase, nft_fixture(phase)) == (4, 7)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "wide_address",
        "wrong_port",
        "phase",
        "counter_bool",
        "counter_duplicate",
        "float_priority",
        "float_reject",
        "level",
        "bad_handle",
    ],
)
def test_nft_mismatch_never_returns_counts(mutation: str) -> None:
    data = copy.deepcopy(nft_fixture())
    # JSON keeps these nested test shapes independent from production renderer.
    raw = json.dumps(data)
    if mutation == "extra":
        data = json.loads(raw[:-2] + ', {"set": {}}]}')
    elif mutation == "wide_address":
        data = json.loads(raw.replace('"127.0.0.1"', '"127.0.0.0/8"'))
    elif mutation == "wrong_port":
        data = json.loads(raw.replace("38167", "38169"))
    elif mutation == "phase":
        data = json.loads(raw.replace(f"issue167:{RUN}:a:", f"issue167:{RUN}:b:"))
    elif mutation == "counter_bool":
        data = json.loads(raw.replace('"packets": 4', '"packets": true'))
    elif mutation == "counter_duplicate":
        data = json.loads(raw.replace('"name": "rejected"', '"name": "allowed"'))
    elif mutation == "float_priority":
        data = json.loads(raw.replace('"prio": 10', '"prio": 10.0'))
    elif mutation == "float_reject":
        data = json.loads(raw.replace('"expr": "admin-prohibited"', '"expr": 3.0'))
    elif mutation == "level":
        data = json.loads(
            raw.replace('"key": "cgroupv2"', '"key": "cgroupv2", "level": 1')
        )
    else:
        data = json.loads(raw.replace('"handle": 10', '"handle": true'))
    with pytest.raises(PhaseRejected, match=r"^nft_state_unknown$"):
        verify_nft_state(plan(), "a", data)


def fake_cgroup(root: Path, content: str = "101\n") -> Path:
    group = root / "system.slice" / UNIT
    group.mkdir(parents=True)
    (group / "cgroup.procs").write_text(content)
    return group


def test_cgroup_reads_subtree_and_distinguishes_absence(tmp_path: Path) -> None:
    group = fake_cgroup(tmp_path)
    child = group / "synthetic-child"
    child.mkdir()
    (child / "cgroup.procs").write_text("102\n103\n")
    state = read_cgroup_state(plan(), cgroup_root=tmp_path)
    assert state.exists and state.group_count == 2
    assert state.pids == frozenset({101, 102, 103})
    assert read_cgroup_pids(plan(), cgroup_root=tmp_path) == state.pids
    with pytest.raises(PhaseRejected, match=r"^cgroup_missing$"):
        read_cgroup_state(Plan("abcdef012345", 1000, 1000), cgroup_root=tmp_path)
    absent = read_cgroup_state(
        Plan("abcdef012345", 1000, 1000), cgroup_root=tmp_path, allow_absent=True
    )
    assert not absent.exists and absent.group_count == 0 and absent.pids == frozenset()


@pytest.mark.parametrize("content", ["0\n", "-1\n", "1.0\n", "2\n2\n", "99999999999\n"])
def test_cgroup_pid_contents_are_strict(tmp_path: Path, content: str) -> None:
    fake_cgroup(tmp_path, content)
    with pytest.raises(PhaseRejected, match=r"^cgroup_unknown$"):
        read_cgroup_state(plan(), cgroup_root=tmp_path)


def test_cgroup_symlinks_limits_and_partial_reads_are_unknown(tmp_path: Path) -> None:
    group = fake_cgroup(tmp_path)
    (group / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PhaseRejected, match=r"^cgroup_unknown$"):
        read_cgroup_state(plan(), cgroup_root=tmp_path)
    (group / "escape").unlink()
    child = group / "child"
    child.mkdir()
    with pytest.raises(PhaseRejected, match=r"^cgroup_unknown$"):
        read_cgroup_state(plan(), cgroup_root=tmp_path)
    (child / "cgroup.procs").write_text("102\n")
    with pytest.raises(PhaseRejected, match=r"^cgroup_limit_exceeded$"):
        read_cgroup_state(plan(), cgroup_root=tmp_path, max_groups=1)
    with pytest.raises(PhaseRejected, match=r"^cgroup_limit_exceeded$"):
        read_cgroup_state(plan(), cgroup_root=tmp_path, max_pids=1)


@pytest.mark.parametrize("kind", ["plan", "cgroup"])
def test_short_reads_do_not_truncate_plan_or_hide_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    import os

    real_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, limit: real_read(fd, min(limit, 3)))
    if kind == "plan":
        path = tmp_path / "plan.json"
        path.write_text(plan().to_json())
        assert load_plan(path) == plan()
    else:
        fake_cgroup(tmp_path, "101\n102\n")
        assert read_cgroup_pids(plan(), cgroup_root=tmp_path) == {101, 102}


def test_create_transaction_refuses_preexisting_table_atomically() -> None:
    # nft(8): add may reuse an existing table; create must fail on a collision.
    assert render_create(plan()).splitlines()[0] == f"create table inet {TABLE}"
