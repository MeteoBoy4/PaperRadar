"""Unbound D1: guardian mocks only; no root/services/nft/network/crashes."""

import json
import os
import time
from pathlib import Path

import pytest

from scripts import issue167_h1_guardian as guard
from scripts.issue167_h1_phase import Plan


def plan() -> Plan:
    return Plan("123456abcdef", 1000, 1000)


def file_probe() -> dict[str, object]:
    return {
        "result": "observed_expected",
        "allow_install_read": True,
        "allow_attempt_write": True,
        "deny_install_write": True,
        "deny_cwd_write": True,
        "deny_business_read": True,
        "deny_publisher_read": True,
        "deny_credentials_read": True,
        "history": "observed_mutation",
        "terminal_regular_files": 1,
        "directory_deleted": True,
        "coverage_complete": True,
    }


def done(phase: str) -> dict[str, object]:
    p = plan()
    current, other = (p.port_a, p.port_b) if phase == "a" else (p.port_b, p.port_a)
    rows = []
    for kind, transport, port, expected in (
        ("current-tcp", "tcp", current, "allow"),
        ("other-tcp", "tcp", other, "deny"),
        ("blocked-tcp", "tcp", p.blocked_port, "deny"),
        ("blocked-udp", "udp", p.blocked_port, "deny"),
        ("dns-udp", "udp", 53, "deny"),
    ):
        for family in ("v4", "v6"):
            rows.append(
                {
                    "case": f"{family}-{kind}",
                    "kind": transport,
                    "family": family,
                    "port": port,
                    "expected": expected,
                    "outcome": "allowed" if expected == "allow" else "denied",
                    "errno_category": "none"
                    if expected == "allow"
                    else "admin_unreachable",
                }
            )
    return {"run_id": p.run_id, "phase": phase, "cases": rows}


class FakeOps:
    def __init__(self, fail: str = "") -> None:
        self.events: list[str] = []
        self.fail = fail
        self.phase_name = "deny"
        self.counter_reads: dict[str, int] = {}

    def reserve(self) -> None:
        self.events.append("reserve")
        if self.fail == "reserve":
            raise FileExistsError

    def start_peer(self) -> None:
        self.events.append("peer")

    def wait(self, name: str) -> object:
        self.events.append(name)
        if self.fail == "wait":
            raise RuntimeError("must-not-be-exported")
        if name == "ready.json":
            return {
                "run_id": plan().run_id,
                "pid": 123,
                "uid": 1000,
                "file_probe": file_probe(),
                "core_limits": [0, 0],
                "no_new_privs": True,
                "cap_eff_zero": True,
                "cgroup_matches": True,
            }
        if name == "leftover-ready.json":
            return {"run_id": plan().run_id, "controller_pid": 123, "child_pid": 456}
        value = done(name[0])
        if self.fail == "unknown" and name == "a-done.json":
            value["cases"][2]["outcome"] = "unknown"  # type: ignore[index]
            value["cases"][2]["errno_category"] = "connection_refused"  # type: ignore[index]
        return value

    def members(self, _pid: int) -> frozenset[int]:
        self.events.append("members")
        if "leftover-ready.json" in self.events:
            return (
                frozenset({123}) if self.fail == "leftover" else frozenset({123, 456})
            )
        if self.fail == "descendant" and "a-done.json" in self.events:
            return frozenset({123, 789})
        return frozenset({123})

    def create(self) -> None:
        self.events.append("create")

    def counters(self, phase: str) -> tuple[int, int]:
        self.events.append(f"counter:{phase}")
        count = self.counter_reads.get(phase, 0)
        self.counter_reads[phase] = count + 1
        if self.fail == "counter":
            return 0, 0
        return (0, 0) if count == 0 else (2, 8)

    def phase(self, phase: str) -> None:
        self.events.append(f"phase:{phase}")
        self.phase_name = phase

    def gate(self, phase: str) -> None:
        self.events.append(f"gate:{phase}")

    def cleanup(self) -> bool:
        self.events.append("cleanup")
        return self.fail != "cleanup"


def test_closed_success_checks_before_gate_and_refuses_leftover_transition() -> None:
    ops = FakeOps()
    result = guard.run_guardian(plan(), ops)
    assert result["result"] == "observed_expected"
    assert result["leftover_refused"] is True
    assert result["cleanup_complete"] is True
    assert ops.events[0] == "reserve"
    assert ops.events[-1] == "cleanup"
    assert ops.events.count("phase:a") == ops.events.count("phase:b") == 1
    assert ops.events.index("counter:a") < ops.events.index("gate:a")
    assert result["auth_calls"] == result["model_calls"] == 0


@pytest.mark.parametrize(
    "failure", ["unknown", "counter", "descendant", "leftover", "cleanup", "wait"]
)
def test_missing_observation_or_cleanup_never_becomes_pass(failure: str) -> None:
    ops = FakeOps(failure)
    result = guard.run_guardian(plan(), ops)
    assert result["result"] == "unknown"
    assert ops.events[-1] == "cleanup"
    assert "must-not-be-exported" not in repr(result)
    if failure in {"unknown", "counter", "descendant", "wait"}:
        assert "gate:b" not in ops.events


def test_consumed_reservation_prevents_all_effects_and_refunds() -> None:
    ops = FakeOps("reserve")
    result = guard.run_guardian(plan(), ops)
    assert result["result"] == "unknown"
    assert ops.events == ["reserve"]


@pytest.mark.parametrize(
    "field", ["coverage_complete", "deny_business_read", "directory_deleted"]
)
def test_file_probe_is_required_before_network(field: str) -> None:
    value = file_probe()
    value[field] = False
    with pytest.raises(guard.GuardianRejected, match=r"^file_probe_unknown$"):
        guard.validate_file_probe(value)


def test_phase_rejects_wrong_identity_shape_and_unsafe_errno() -> None:
    for change in ("run_id", "extra", "errno"):
        value = done("a")
        if change == "run_id":
            value["run_id"] = "different"
        elif change == "extra":
            value["token"] = "not-for-output"
        else:
            value["cases"][2]["errno_category"] = "connection_refused"  # type: ignore[index]
        with pytest.raises(
            guard.GuardianRejected,
            match=r"^phase_(metadata_invalid|observation_unknown)$",
        ):
            guard.reconcile_done(plan(), "a", value)


def test_atomic_metadata_is_complete_and_never_overwrites(tmp_path: Path) -> None:
    ops = guard.LiveOperations(plan(), guard.Commands(plan(), {}))
    path = tmp_path / "go.json"
    ops._write(path, {"phase": "a"})
    assert guard.read_json(path, owner=os.getuid()) == {"phase": "a"}
    with pytest.raises(FileExistsError):
        ops._write(path, {"phase": "b"})
    assert json.loads(path.read_text()) == {"phase": "a"}
    assert list(tmp_path.iterdir()) == [path]


def test_link_publish_window_is_not_read_as_complete(tmp_path: Path) -> None:
    path = tmp_path / "go.json"
    path.write_text('{"phase":"a"}')
    path.chmod(0o600)
    extra = tmp_path / "pending"
    os.link(path, extra)
    with pytest.raises(FileNotFoundError, match=r"^metadata_publishing$"):
        guard.read_json(path, owner=os.getuid())
    extra.unlink()
    assert guard.read_json(path, owner=os.getuid()) == {"phase": "a"}


def test_anchor_survives_runtime_removal_and_blocks_same_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checked = []
    monkeypatch.setattr(
        guard, "protected_path", lambda path, **kwargs: checked.append(path)
    )
    path = tmp_path / "persistent.json"
    anchor = guard.claim_anchor(path, plan().run_id)
    anchor.close()
    assert json.loads(path.read_text())["state"] == "reserved_unknown"
    with pytest.raises(FileExistsError):
        guard.claim_anchor(path, plan().run_id)
    assert checked == [tmp_path, tmp_path]


def test_bootstrap_rejects_nonroot_or_wrong_install_root_before_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    with pytest.raises(guard.GuardianRejected, match=r"^root_installation_required$"):
        guard.bootstrap(Path("/home/paperradar-probes/issue167-123456abcdef"))
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(guard.GuardianRejected, match=r"^root_installation_required$"):
        guard.bootstrap(Path("/tmp/user-controlled"))


def test_commands_use_only_fixed_argv_and_plan_rendering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = {"nft": Path("/usr/sbin/nft"), "systemctl": Path("/usr/bin/systemctl")}
    commands = guard.Commands(plan(), tools)
    seen = []

    def fake(argv: tuple[str, ...], data: bytes = b"") -> bytes:
        seen.append((argv, data))
        return b'{"nftables":[]}'

    monkeypatch.setattr(commands, "_run", fake)
    commands.create()
    commands.phase("a")
    commands.stop()
    commands.delete()
    assert seen[0][0] == ("/usr/sbin/nft", "-j", "list", "tables")
    assert seen[1][0] == ("/usr/sbin/nft", "-f", "-")
    assert seen[3][0] == ("/usr/bin/systemctl", "stop", plan().unit)
    assert all("shell" not in str(row) for row in seen)
    with pytest.raises(guard.GuardianRejected, match=r"^phase_invalid$"):
        commands.phase("a; arbitrary-command")


def test_cleanup_stops_and_observes_empty_before_removing_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.issue167_h1_phase import CgroupState

    commands = guard.Commands(plan(), {})
    calls = []
    monkeypatch.setattr(commands, "stop", lambda: calls.append("stop"))

    def counters(_phase: str) -> tuple[int, int]:
        calls.append("verify")
        return 0, 0

    monkeypatch.setattr(commands, "counters", counters)
    monkeypatch.setattr(commands, "delete", lambda: calls.append("delete"))

    def empty(*args: object, **kwargs: object) -> CgroupState:
        calls.append("empty")
        return CgroupState(False, frozenset(), 0)

    monkeypatch.setattr(guard, "read_cgroup_state", empty)
    ops = guard.LiveOperations(plan(), commands)
    ops.table_created = True
    assert ops.cleanup() is True
    assert calls == ["stop", "empty", "verify", "delete"]


def test_uncertain_creation_keeps_table_even_after_empty_cgroup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.issue167_h1_phase import CgroupState

    commands = guard.Commands(plan(), {})
    monkeypatch.setattr(commands, "stop", lambda: None)
    monkeypatch.setattr(
        guard,
        "read_cgroup_state",
        lambda *args, **kwargs: CgroupState(False, frozenset(), 0),
    )

    def forbidden() -> None:
        pytest.fail("uncertain table must remain for owner")

    monkeypatch.setattr(commands, "delete", forbidden)
    ops = guard.LiveOperations(plan(), commands)
    ops.create_uncertain = True
    assert ops.cleanup() is False


def test_unknown_cgroup_does_not_remove_table(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.issue167_h1_phase import CgroupState

    commands = guard.Commands(plan(), {})
    monkeypatch.setattr(commands, "stop", lambda: None)
    monkeypatch.setattr(
        guard,
        "read_cgroup_state",
        lambda *args, **kwargs: CgroupState(True, frozenset({123}), 1),
    )
    ticks = iter([0.0, 0.0, 0.0, 11.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks))

    def forbidden() -> None:
        pytest.fail("active descendant must keep rules")

    monkeypatch.setattr(commands, "delete", forbidden)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    ops = guard.LiveOperations(plan(), commands)
    ops.table_created = True
    assert ops.cleanup() is False


def test_result_never_writes_into_unowned_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ops = guard.LiveOperations(plan(), guard.Commands(plan(), {}))
    ops.anchor = (tmp_path / "anchor.json").open("w+")

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("runtime was not created by this reservation")

    monkeypatch.setattr(ops, "_write", forbidden)
    ops.write_result({"result": "unknown"})
    assert json.loads((tmp_path / "anchor.json").read_text())["result"] == "unknown"


def test_controlled_failure_reason_never_preserves_arbitrary_text() -> None:
    assert (
        guard.failure_reason(guard.GuardianRejected("peer_not_ready"))
        == "peer_not_ready"
    )
    assert (
        guard.failure_reason(guard.GuardianRejected("raw-secret-sentinel"))
        == "observer_failure"
    )
    assert (
        guard.failure_reason(RuntimeError("raw-secret-sentinel")) == "observer_failure"
    )


@pytest.mark.parametrize(
    "field", ["core_limits", "no_new_privs", "cap_eff_zero", "cgroup_matches"]
)
def test_actual_worker_metadata_must_match_before_rule_creation(field: str) -> None:
    class WrongReady(FakeOps):
        def wait(self, name: str) -> object:
            value = super().wait(name)
            if name == "ready.json":
                assert isinstance(value, dict)
                value[field] = [0, -1] if field == "core_limits" else False
            return value

    ops = WrongReady()
    result = guard.run_guardian(plan(), ops)
    assert result["result"] == "unknown"
    assert result["failure_reason"] == "worker_identity_unknown"
    assert "create" not in ops.events


def test_metadata_rejects_duplicate_fields_before_consumption(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"run_id":"untrusted","run_id":"123456abcdef"}')
    path.chmod(0o600)
    with pytest.raises(guard.GuardianRejected, match=r"^metadata_invalid$"):
        guard.read_json(path, owner=os.getuid())


def test_manifest_hashes_are_checked_before_sibling_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib
    import re

    root = tmp_path
    context = {
        "boot_id": "01234567-89ab-cdef-0123-456789abcdef",
        "kernel": "fixed-kernel",
        "machine": "fixed-machine",
        "hostname_sha256": "a" * 64,
    }
    members = {
        name: hashlib.sha256(b"fixed-code").hexdigest()
        for name in (
            "plan.json",
            "host-context.json",
            "issue167_h1_guardian.py",
            "issue167_h1_phase.py",
            "issue167_h1_network_worker.py",
            "synthetic-python",
        )
    }
    for name in members:
        (root / name).write_bytes(b"fixed-code")
    (root / "host-context.json").write_text(json.dumps(context))
    members["host-context.json"] = hashlib.sha256(
        (root / "host-context.json").read_bytes()
    ).hexdigest()
    tools = {
        "python": {
            "path": str(root / "synthetic-python"),
            "sha256": members["synthetic-python"],
        },
        "nft": {
            "path": "/usr/sbin/nft",
            "sha256": hashlib.sha256(b"fixed-tool").hexdigest(),
        },
        "systemctl": {
            "path": "/usr/bin/systemctl",
            "sha256": hashlib.sha256(b"fixed-tool").hexdigest(),
        },
    }
    manifest = {"kind": "h1_synthetic_local_review", "members": members, "tools": tools}
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "manifest.json").chmod(0o600)
    original_match = re.fullmatch
    original_bytes = Path.read_bytes
    checked = []
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(guard, "current_host_context", lambda: context)
    monkeypatch.setattr(os, "access", lambda *_args: True)
    monkeypatch.setattr(
        guard, "read_json", lambda path, **kwargs: json.loads(path.read_text())
    )
    monkeypatch.setattr(
        guard, "protected_path", lambda path, **kwargs: checked.append(path)
    )
    monkeypatch.setattr(
        re,
        "fullmatch",
        lambda pattern, text: (
            True
            if pattern.startswith("/home/paperradar-probes/") and text == str(root)
            else original_match(pattern, text)
        ),
    )
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: (
            b"fixed-tool"
            if str(path) in {"/usr/sbin/nft", "/usr/bin/systemctl"}
            else original_bytes(path)
        ),
    )
    assert guard.bootstrap(root)["python"] == root / "synthetic-python"
    assert root / "issue167_h1_phase.py" in checked
    (root / "issue167_h1_phase.py").write_bytes(b"changed")
    with pytest.raises(guard.GuardianRejected, match=r"^member_changed$"):
        guard.bootstrap(root)

    (root / "issue167_h1_phase.py").write_bytes(b"fixed-code")
    monkeypatch.setattr(
        guard, "current_host_context", lambda: {**context, "kernel": "drift"}
    )
    with pytest.raises(guard.GuardianRejected, match=r"^host_context_mismatch$"):
        guard.bootstrap(root)


@pytest.mark.parametrize(
    "field,value",
    [
        ("uid", 1000.0),
        ("pid", 123.0),
        ("core_limits", [False, False]),
        ("core_limits", [0.0, 0.0]),
        ("no_new_privs", 1),
        ("cap_eff_zero", 1.0),
        ("cgroup_matches", 1),
    ],
)
def test_ready_rejects_numeric_coercion_before_effects(
    field: str, value: object
) -> None:
    class CoercedReady(FakeOps):
        def wait(self, name: str) -> object:
            item = super().wait(name)
            if name == "ready.json":
                assert isinstance(item, dict)
                item[field] = value
            return item

    ops = CoercedReady()
    result = guard.run_guardian(plan(), ops)
    assert result["result"] == "unknown"
    assert result["failure_reason"] == "worker_identity_unknown"
    assert "create" not in ops.events
    assert "gate:a" not in ops.events


@pytest.mark.parametrize("count", [True, 1.0])
def test_terminal_member_count_rejects_bool_and_float(count: object) -> None:
    item = file_probe()
    item["terminal_regular_files"] = count
    with pytest.raises(guard.GuardianRejected, match=r"^file_probe_unknown$"):
        guard.validate_file_probe(item)


@pytest.mark.parametrize(
    "field,value", [("controller_pid", 123.0), ("child_pid", 456.0)]
)
def test_leftover_process_identity_rejects_float(field: str, value: float) -> None:
    class CoercedLeftover(FakeOps):
        def wait(self, name: str) -> object:
            item = super().wait(name)
            if name == "leftover-ready.json":
                assert isinstance(item, dict)
                item[field] = value
            return item

    result = guard.run_guardian(plan(), CoercedLeftover())
    assert result["result"] == "unknown"
    assert result["failure_reason"] == "leftover_metadata_invalid"
    assert result["leftover_refused"] is False


def test_per_case_port_rejects_equal_float() -> None:
    item = done("a")
    item["cases"][0]["port"] = float(plan().port_a)  # type: ignore[index]
    with pytest.raises(guard.GuardianRejected, match=r"^phase_metadata_invalid$"):
        guard.reconcile_done(plan(), "a", item)


def test_commands_counters_decodes_actual_json_bytes_before_strict_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_issue167_h1_phase import nft_fixture
    from tests.test_issue167_h1_phase import plan as fixture_plan

    frozen = fixture_plan()
    commands = guard.Commands(frozen, {"nft": Path("/usr/sbin/nft")})
    payload = json.dumps(nft_fixture("a")).encode()
    monkeypatch.setattr(commands, "_run", lambda _argv: payload)
    assert commands.counters("a") == (4, 7)


@pytest.mark.parametrize(
    "payload", [b"not-json", b'{"nftables":[],"nftables":[]}', b"\xff"]
)
def test_commands_counters_rejects_invalid_or_duplicate_json_bytes(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    commands = guard.Commands(plan(), {"nft": Path("/usr/sbin/nft")})
    monkeypatch.setattr(commands, "_run", lambda _argv: payload)
    with pytest.raises(guard.GuardianRejected, match=r"^nft_state_unknown$"):
        commands.counters("deny")


@pytest.mark.parametrize("field", ["boot_id", "kernel", "machine", "hostname_sha256"])
def test_frozen_host_binding_rejects_each_drift_before_operations(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    context = {
        "boot_id": "01234567-89ab-cdef-0123-456789abcdef",
        "kernel": "kernel",
        "machine": "machine",
        "hostname_sha256": "a" * 64,
    }
    monkeypatch.setattr(guard, "current_host_context", lambda: context)
    guard.verify_host_context(context)
    with pytest.raises(guard.GuardianRejected, match=r"^host_context_mismatch$"):
        guard.verify_host_context({**context, field: "changed"})


def test_unknown_host_metadata_never_defaults_to_a_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_path: Path, **kwargs: object) -> str:
        raise PermissionError("external-private-path-must-not-escape")

    monkeypatch.setattr(Path, "read_text", unavailable)
    with pytest.raises(
        guard.GuardianRejected, match=r"^host_context_unknown$"
    ) as rejected:
        guard.current_host_context()
    assert "external-private" not in str(rejected.value)


def test_create_refuses_duplicate_table_inventory_before_loading_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = guard.Commands(plan(), {"nft": Path("/usr/sbin/nft")})
    table = {"family": "inet", "name": plan().table}
    payload = (
        '{"nftables":' + json.dumps([{"table": table}]) + ',"nftables":[]}'
    ).encode()
    calls = []

    def fake(argv: tuple[str, ...], data: bytes = b"") -> bytes:
        calls.append(argv)
        return payload

    monkeypatch.setattr(commands, "_run", fake)
    with pytest.raises(guard.GuardianRejected, match=r"^table_inventory_unknown$"):
        commands.create()
    assert calls == [("/usr/sbin/nft", "-j", "list", "tables")]
