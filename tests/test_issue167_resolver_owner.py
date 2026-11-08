"""Independent D1: no privileged/service/nft/network operations are executed."""

import copy
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts.issue167_resolver_case import (
    Case,
    CaseRejected,
    load_case,
    read_metadata,
    render_unit,
    validate_ready,
    validate_result,
)
from scripts.issue167_resolver_owner import (
    LiveOperations,
    OwnerRejected,
    owner_envelope,
    run_owner,
)


def case() -> Case:
    return Case("c123456789ab", os.getuid(), os.getgid(), "a" * 64, "b" * 64, "c" * 64)


def ready() -> dict[str, object]:
    return {
        "run_id": case().run_id,
        "pid": 12345,
        "uid": case().uid,
        "core_limits": [0, 0],
        "no_new_privs": True,
        "cap_eff_zero": True,
        "cgroup_matches": True,
        "resolver_sha256": case().resolver_sha256,
        "mount_namespace": "mnt:[2]",
        "pid_namespace": "pid:[1]",
    }


def worker_result() -> dict[str, object]:
    from scripts.issue167_resolver_case import CHAIN_FIELDS

    return {
        **ready(),
        "result": "observed_expected",
        "network_operations": 0,
        "node_pi": False,
        "auth_calls": 0,
        "model_calls": 0,
        "synthetic_auth_execs": 1,
        "synthetic_model_execs": 1,
        "synthetic_chain": dict.fromkeys(CHAIN_FIELDS, True),
        "window": {
            "scope": "fork_observation_prototype",
            "source": "kernel_own_cgroup_metadata",
            "event_source": "inotify",
            "run_id": case().run_id,
            "result": "window_complete",
            "history": "observed_mutation",
            "mutation_events": 2,
            "terminal_status": "synthetic_snapshot",
            "terminal_regular_files": 1,
            "terminal_other_entries": 1,
            "directory_deleted": True,
            "post_terminal_mutation_events": 0,
            "reasons": [],
        },
    }


def test_case_closed_schema_and_derived_scope() -> None:
    value = case().to_dict()
    assert Case.from_dict(value) == case()
    assert "addresses" not in value and "ports" not in value
    assert value["network_operations"] == 0
    body = render_unit(case())
    assert "RestrictAddressFamilies=none\n" in body
    assert "IPAddressDeny=any\n" in body and "IPAddressAllow=" not in body
    assert (
        f"BindReadOnlyPaths={case().install_root}/resolv.conf:/etc/resolv.conf\n"
        in body
    )
    assert "[Install]" not in body and "AmbientCapabilities=\n" in body


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("run_id", "../escape"),
        ("uid", True),
        ("gid", 0),
        ("network_operations", 1),
        ("node_pi", True),
        ("auth_calls", False),
        ("worker_timeout_s", 41),
        ("owner_timeout_s", 90.0),
        ("install_root", "/tmp/unbound"),
        ("profile_sha256", "no-digest"),
    ],
)
def test_case_rejects_policy_or_type_drift(key: str, value: object) -> None:
    payload = {**case().to_dict(), key: value}
    with pytest.raises(
        CaseRejected, match=r"^case_(identity|deadline|digest|binding|shape)_unknown$"
    ):
        Case.from_dict(payload)


def test_metadata_publication_intermediate_is_bounded_wait_not_partial_read(
    tmp_path: Path,
) -> None:
    target = tmp_path / "ready.json"
    target.write_text('{"incomplete":')
    os.link(target, tmp_path / "publishing.json")
    with pytest.raises(FileNotFoundError, match=r"^metadata_publishing$"):
        read_metadata(target, owner=os.getuid())


def test_case_loader_reads_only_fixed_fixture(tmp_path: Path) -> None:
    target = tmp_path / "plan.json"
    target.write_text(json.dumps(case().to_dict()))
    target.chmod(0o600)
    assert load_case(target, owner=os.getuid()) == case()


def test_nonregular_metadata_never_blocks_or_reads(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    os.mkfifo(target, 0o600)
    with pytest.raises(CaseRejected, match=r"^metadata_unknown$"):
        read_metadata(target, owner=os.getuid())


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("uid", True),
        ("core_limits", [False, False]),
        ("cap_eff_zero", 1),
        ("mount_namespace", "unknown"),
        ("pid_namespace", "mnt:[1]"),
    ],
)
def test_ready_fields_do_not_coerce_types(key: str, value: object) -> None:
    with pytest.raises(CaseRejected, match=r"^worker_identity_unknown$"):
        validate_ready(case(), {**ready(), key: value})


def test_worker_acceptance_requires_kernel_labels_and_complete_window() -> None:
    assert validate_result(case(), worker_result())["result"] == "observed_expected"
    value = worker_result()
    window = value["window"]
    assert isinstance(window, dict)
    window["source"] = "synthetic_cgroup_fixture"
    with pytest.raises(CaseRejected, match=r"^window_unknown$"):
        validate_result(case(), value)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("network_operations", False),
        ("network_operations", 1),
        ("node_pi", 0),
        ("auth_calls", 1),
        ("synthetic_model_execs", 2),
    ],
)
def test_real_call_counts_and_synthetic_limits_are_distinct(
    key: str, value: object
) -> None:
    with pytest.raises(CaseRejected, match=r"^worker_result_unknown$"):
        validate_result(case(), {**worker_result(), key: value})


class FakeOperations:
    def __init__(self, failure: str = "") -> None:
        self.failure = failure
        self.events: list[str] = []
        self.ledger: list[object] = []
        self.malformed_restore = False

    def event(self, name: str) -> None:
        self.events.append(name)
        if name == self.failure:
            raise OwnerRejected("synthetic_failure")

    def preflight(self) -> None:
        self.event("preflight")

    def reserve(self) -> None:
        self.event("reserve")

    def install(self) -> None:
        self.event("install")

    def start(self) -> None:
        self.event("start")

    def ready(self) -> dict[str, object]:
        self.event("ready")
        return ready()

    def exercise_rules(self) -> dict[str, object]:
        self.event("rules")
        return {"switches": 3}

    def gate(self, sequence: int) -> None:
        self.event("gate" + str(sequence))

    def collect(self) -> dict[str, object]:
        self.event("collect")
        return worker_result()

    def wait_exit(self) -> None:
        self.event("exit")

    def restore(self) -> dict[str, object]:
        self.event("restore")
        return {
            "result": "host_policy_restored",
            "global_resolver_unchanged": True,
            "ledger_retained": 1 if self.malformed_restore else True,
            "table_absent": True,
            "unit_absent": True,
        }

    def finish(self) -> dict[str, object]:
        self.event("finish")
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        self.event("ledger")
        self.ledger.append(copy.deepcopy(value))


def test_one_case_accepts_only_after_restoration_and_artifact_cleanup() -> None:
    ops = FakeOperations()
    result = run_owner(case(), ops)
    assert result["result"] == "observed_expected_and_restored"
    assert ops.events == [
        "preflight",
        "reserve",
        "install",
        "start",
        "ready",
        "rules",
        "gate1",
        "collect",
        "gate2",
        "exit",
        "restore",
        "ledger",
        "finish",
        "ledger",
    ]
    assert ops.ledger[-1] == result


@pytest.mark.parametrize("failure", ["preflight", "reserve"])
def test_preflight_or_reservation_failure_never_installs_or_restores(
    failure: str,
) -> None:
    ops = FakeOperations(failure)
    result = run_owner(case(), ops)
    assert result["result"] == "unknown"
    assert "install" not in ops.events and "restore" not in ops.events
    assert ops.ledger == []


@pytest.mark.parametrize(
    "failure",
    ["install", "start", "ready", "rules", "gate1", "collect", "gate2", "exit"],
)
def test_failure_consumes_case_and_attempts_only_scoped_recovery(failure: str) -> None:
    ops = FakeOperations(failure)
    result = run_owner(case(), ops)
    assert result["result"] == "unknown"
    assert "restore" in ops.events and "finish" not in ops.events
    assert ops.ledger and ops.ledger[-1] == result


def test_recovery_failure_prevents_artifact_removal() -> None:
    ops = FakeOperations("restore")
    result = run_owner(case(), ops)
    assert (
        result["result"] == "unknown"
        and result["restoration_error"] == "restoration_unknown"
    )
    assert "finish" not in ops.events


def test_typed_restore_metadata_is_not_accepted_as_integer_truth() -> None:
    ops = FakeOperations()
    ops.malformed_restore = True
    result = run_owner(case(), ops)
    assert result["result"] == "unknown"
    assert "finish" not in ops.events


def test_finish_failure_does_not_change_case_to_passed() -> None:
    ops = FakeOperations("finish")
    result = run_owner(case(), ops)
    assert result["result"] == "unknown"
    assert result["failure_reason"] == "artifact_cleanup_unknown"
    assert ops.ledger[-1] == result


@pytest.mark.parametrize("binding", ["valid", "missing", "wrong_run", "wrong_scope"])
def test_outer_driver_identity_does_not_mutate_inner_ledger(binding: str) -> None:
    ops = FakeOperations()
    value = run_owner(case(), ops)
    selected = None if binding == "missing" else case()
    if binding == "wrong_run":
        value["run_id"] = "unbound"
    if binding == "wrong_scope":
        value["scope"] = "unbound"
    before = copy.deepcopy(value)
    outer = owner_envelope(selected, "d" * 64, value)
    assert outer["scope"] == "h1_owner_automation_only"
    assert outer["manifest_sha256"] == "d" * 64
    assert (outer["owner_result"] == "observed_expected_and_restored") is (
        binding == "valid"
    )
    assert value == before
    assert outer["preflight_result"] == value


@pytest.mark.parametrize(
    "changed", [{}, {"ExecMainStatus": "1"}, {"ControlGroup": "/different"}]
)
def test_real_exit_requires_manager_success_and_independent_empty_group(
    monkeypatch: pytest.MonkeyPatch, changed: dict[str, str]
) -> None:
    ops = object.__new__(LiveOperations)
    ops.case = case()
    ops.plan = case().base_plan()
    ops.deadline = 10
    ops.phase = ModuleType("synthetic_phase")
    monkeypatch.setattr(
        ops.phase,
        "read_cgroup_state",
        lambda *_a, **_k: SimpleNamespace(pids=frozenset()),
        raising=False,
    )
    state = {
        "ActiveState": "active",
        "SubState": "exited",
        "Result": "success",
        "ExecMainCode": "1",
        "ExecMainStatus": "0",
        "MainPID": "0",
        "ControlGroup": ops.plan.cgroup,
        **changed,
    }
    monkeypatch.setattr(
        ops,
        "_systemctl",
        lambda *_a: "\n".join(f"{k}={v}" for k, v in state.items()).encode(),
    )
    monkeypatch.setattr("scripts.issue167_resolver_owner.time.monotonic", lambda: 1.0)
    if changed:
        with pytest.raises(OwnerRejected, match=r"^worker_exit_unknown$"):
            ops.wait_exit()
    else:
        ops.wait_exit()


@pytest.mark.parametrize("drift", ["none", "numeric", "unit"])
def test_live_restore_stops_before_bound_rule_delete_and_refuses_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    from scripts import issue167_h1_owner_ops as old_owner
    from scripts import issue167_service_egress as egress
    from scripts.issue167_h1_phase import Plan
    from tests.test_issue167_service_egress import (
        HOST,
        bind,
        fixture,
        match,
        profile,
        rules,
    )

    code = tmp_path / "code"
    code.mkdir()
    units = tmp_path / "units"
    units.mkdir()
    p = profile().process
    c = Case(p.run_id, p.uid, p.gid, "a" * 64, "b" * 64, "c" * 64)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    baseline_sha = "d" * 64
    baseline = runtime / "resolver-baseline.json"
    baseline.write_text(json.dumps({"run_id": c.run_id, "sha256": baseline_sha}))
    baseline.chmod(0o600)
    monkeypatch.setattr(Case, "runtime_root", property(lambda _self: runtime))
    (code / c.unit).write_text("owned")
    (units / c.unit).write_text("drift" if drift == "unit" else "owned")
    monkeypatch.setattr(Plan, "install_root", property(lambda _self: code))
    monkeypatch.setattr(old_owner, "UNIT_ROOT", units)
    monkeypatch.setattr(old_owner, "UNIT_SEARCH", (units,))
    monkeypatch.setattr(old_owner, "protected_path", lambda *_a, **_k: None)
    monkeypatch.setattr(
        old_owner,
        "manager_scope",
        lambda _commands, unit: {
            "LoadState": "loaded" if (units / unit).exists() else "not-found",
            "FragmentPath": str(units / unit) if (units / unit).exists() else "",
            "DropInPaths": "",
        },
    )
    events: list[str] = []
    present = True
    payload = fixture(True)
    rows = payload["nftables"]
    assert isinstance(rows, list)
    for item in rows:
        if "counter" in item:
            item["counter"]["packets"] = 0
            item["counter"]["bytes"] = 0
    match(rules(payload)[0])["right"] = "844648" if drift != "numeric" else "844649"

    def command(argv: tuple[str, ...], data: bytes = b"") -> bytes:
        assert not data
        if "stop" in argv:
            events.append("stop")
        if "reset-failed" in argv:
            events.append("reset")
        if "daemon-reload" in argv:
            events.append("reload")
        if "show" in argv:
            return b"ActiveState=inactive\nSubState=dead\nMainPID=0\nControlGroup=\n"
        if argv[-2:] == ("list", "tables"):
            return json.dumps(
                {
                    "nftables": [{"table": {"family": "inet", "name": p.table}}]
                    if present
                    else []
                }
            ).encode()
        return b""

    def delete() -> None:
        nonlocal present
        events.append("delete")
        present = False

    def empty(*_a: object, **_k: object) -> SimpleNamespace:
        events.append("empty")
        return SimpleNamespace(pids=frozenset())

    ops = object.__new__(LiveOperations)
    ops.case = c
    ops.plan = p
    ops.profile = profile()
    ops.binding = bind()
    ops.table_created = True
    ops.create_uncertain = False
    ops.enabled = True
    ops.unit_owned = True
    ops.global_resolver_sha = baseline_sha
    ops.snapshots = []
    ops.owner = old_owner
    ops.egress = egress
    ops.phase = ModuleType("fake_phase")
    monkeypatch.setattr(ops.phase, "read_cgroup_state", empty, raising=False)
    ops.contract = ModuleType("fake_contract")
    monkeypatch.setattr(
        ops.contract, "current_host_context", lambda: HOST, raising=False
    )
    monkeypatch.setattr(
        ops.contract,
        "read_metadata",
        lambda path, **_kw: json.loads(path.read_text()),
        raising=False,
    )
    ops.commands = SimpleNamespace(
        tools={"systemctl": Path("/usr/bin/systemctl"), "nft": Path("/usr/sbin/nft")},
        _run=command,
        snapshot=lambda: payload,
        delete=delete,
    )
    monkeypatch.setattr(ops, "_resolver_digest", lambda: baseline_sha)
    if drift == "none":
        assert ops.restore()["result"] == "host_policy_restored"
        assert events[:3] == ["stop", "empty", "delete"]
        assert not (units / c.unit).exists()
        assert ops.snapshots[0]["stage"] == "post_stop"
    else:
        with pytest.raises(
            ValueError, match=r"^(egress_binding_unknown|installed_unit_changed)$"
        ):
            ops.restore()
        assert "delete" not in events
        assert (units / c.unit).exists()
        if drift == "unit":
            assert "stop" not in events
