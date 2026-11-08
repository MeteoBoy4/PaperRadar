"""Independent D1: no live sockets, services, signals, secrets, or root."""

from __future__ import annotations

import copy
import json
import os
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest

from scripts import issue167_duplex_filter as filtering
from scripts import issue167_duplex_probe as probe
from scripts import issue167_h1_guardian as guardian
from tests.test_issue167_duplex_filter import HOST, fixture
from tests.test_issue167_duplex_filter import RUN as FIXTURE_RUN


def test_missing_reference_is_unknown() -> None:
    with pytest.raises(probe.ProbeRejected, match="report_unknown"):
        probe.validate_report({}, role="client", stage="baseline")


def test_public_frame_codec_supports_fragmentation_and_coalescing() -> None:
    first = probe.frame("main_out", 1)
    second = probe.frame("main_out", 2)
    reader = probe.FrameBuffer()
    assert reader.feed(first[:3]) == []
    assert reader.feed(first[3:] + second) == [("main_out", 1), ("main_out", 2)]


@pytest.mark.parametrize("raw", [b"unexpected\n", b"x" * 257])
def test_unbounded_or_unreferenced_payload_is_unknown(raw: bytes) -> None:
    with pytest.raises(probe.ProbeRejected, match="frame_unknown"):
        probe.FrameBuffer().feed(raw)


def kernel(phase: str, counts: tuple[int, ...], offset: int) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            json.dumps(fixture(phase, packets=counts, offset=offset)).replace(
                FIXTURE_RUN, probe.RUN
            )
        ),
    )


def report(role: str, stage: str, metadata: dict[str, object]) -> dict[str, object]:
    value: dict[str, Any] = {
        "scope": probe.SCOPE,
        "run_id": probe.RUN,
        "role": role,
        "stage": stage,
        "integrity": "complete",
        "metadata": metadata,
    }
    probe.validate_report(value, role=role, stage=stage)
    return value


class FakeOps:
    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.calls: list[str] = []
        self.gates: dict[str, dict[str, Any]] = {}
        self.plan = probe.Case().plan
        self.binding: dict[str, Any] | None = None
        self.reference: dict[str, Any] | None = None
        self.phase = "deny"
        self.offset = 0
        self.counts = filtering.Counts()
        self.refs: list[dict[str, Any]] = []
        self.ledger: dict[str, Any] | None = None

    def called(self, name: str) -> None:
        self.calls.append(name)
        if self.failure == name:
            raise probe.ProbeRejected("metadata_unknown")

    def preflight(self) -> None:
        self.called("preflight")

    def reserve(self) -> None:
        self.called("reserve")

    def install(self) -> None:
        self.called("install")

    def start_peer(self) -> dict[str, object]:
        self.called("peer")
        return {
            "uid": 1000,
            "gid": 1000,
            "outside_target_cgroup": True,
            "core_zero": True,
            "no_new_privs": True,
            "integrity": "complete",
        }

    def start_client(self) -> dict[str, object]:
        self.called("client")
        return {
            "uid": 1000,
            "gid": 1000,
            "inside_target_cgroup": True,
            "peer_outside_target_cgroup": True,
            "core_zero": True,
            "no_new_privs": True,
            "integrity": "complete",
        }

    def create_filter(self) -> dict[str, object]:
        self.called("filter")
        raw = kernel("deny", (0,) * 6, 0)
        self.binding = filtering.make_binding(
            self.plan, raw, (30, 777), host_context=HOST
        )
        self.reference = self.binding["initial_reference"]
        self.refs = [self.reference]
        return self.observation(raw, "created_deny")

    def observation(self, raw: dict[str, Any], label: str) -> dict[str, object]:
        return {
            "stage": label,
            "phase": self.phase,
            "binding": copy.deepcopy(self.binding),
            "phase_reference": copy.deepcopy(self.reference),
            "counts": self.counts.to_dict(),
            "kernel_state": raw,
        }

    def switch(self, phase: str) -> dict[str, object]:
        self.called("switch_" + phase)
        self.offset += 10
        raw = kernel(phase, self.counts.packet_values(), self.offset)
        self.reference = filtering.capture_phase(
            self.plan,
            raw,
            phase=phase,
            host_context=HOST,
            binding=self.binding,
            previous_reference=self.reference,
            previous_counts=self.counts,
        )
        self.refs.append(self.reference)
        self.phase = phase
        self.counts = filtering.verify_state(
            self.plan,
            raw,
            phase=phase,
            host_context=HOST,
            binding=self.binding,
            phase_reference=self.reference,
            previous_counts=self.counts,
        )
        return self.observation(raw, "transaction_" + phase)

    def gate(self, name: str, extra: dict[str, object] | None = None) -> str:
        self.called("gate_" + name)
        value = {
            "scope": probe.SCOPE,
            "run_id": probe.RUN,
            "stage": name,
            "phase_reference": copy.deepcopy(self.reference),
            **(extra or {}),
        }
        self.gates[name] = value
        return probe.digest(probe.encoded(value))

    def reports(self, stage: str) -> dict[str, Any]:
        self.called(stage)
        rows = {}
        reference = probe.digest(
            probe.encoded(
                self.gates[
                    {
                        "baseline": "baseline",
                        "negative": "stall",
                        "resumed": "resume",
                    }.get(stage, "close")
                ]
            )
        )
        for role in ("client", "peer"):
            if stage == "baseline":
                metadata = {
                    "gate_reference_sha256": reference,
                    "main_socket": {
                        "local_address": "127.0.0.1",
                        "peer_address": "127.0.0.1",
                        "local_port": 53000 if role == "client" else 46167,
                        "peer_port": 46167 if role == "client" else 53000,
                        "socket_inode": 101 if role == "client" else 102,
                    },
                    "connect_entries": 1,
                    "main_received_A": True,
                    "main_send_entries": 1,
                    "control_roundtrip": role == "peer",
                    "pending_payload_bytes": 0,
                    "accept_entries": 0 if role == "client" else 2,
                }
            elif stage == "negative":
                metadata = {
                    "gate_reference_sha256": reference,
                    "main_B_send_entries": 1,
                    "main_B_received": False,
                    "new_main_payload_bytes_observed": 0,
                    "pending_main_payload_bytes": 0,
                    "control_roundtrip_during_stall": role == "peer",
                    "negative_end_monotonic_ns": self.gates["stall"][
                        "negative_end_monotonic_ns"
                    ],
                    "negative_started_monotonic_ns": self.gates["stall"][
                        "negative_not_before_monotonic_ns"
                    ]
                    + 1,
                    "negative_finished_monotonic_ns": self.gates["stall"][
                        "negative_end_monotonic_ns"
                    ]
                    + 1,
                }
            elif stage == "resumed":
                metadata = {
                    "gate_reference_sha256": reference,
                    "main_B_received_without_resend": True,
                    "main_B_read_monotonic_ns": self.gates["resume"][
                        "allow_intent_monotonic_ns"
                    ]
                    + 1,
                    "main_application_send_entries": 2,
                    "control_roundtrip_after_resume": role == "peer",
                    "send_entries": 2 if role == "client" else 8,
                    "connect_entries": 1,
                    "accept_entries": 0 if role == "client" else 2,
                }
            else:
                metadata = {
                    "all_sockets_closed": True,
                    "send_entries": 2 if role == "client" else 8,
                    "connect_entries": 1,
                    "accept_entries": 0 if role == "client" else 2,
                }
            rows[role] = report(role, stage, metadata)
        return rows

    def snapshot(self, label: str) -> dict[str, object]:
        self.called(label)
        packets = {
            "baseline_complete": (2, 2, 0, 0, 0, 0),
            "negative_complete": (2, 2, 1, 1, 0, 0),
            "before_exit": (4, 4, 1, 1, 0, 0),
        }[label]
        raw = kernel(self.phase, packets, self.offset)
        self.counts = filtering.verify_state(
            self.plan,
            raw,
            phase=self.phase,
            host_context=HOST,
            binding=self.binding,
            phase_reference=self.reference,
            previous_counts=self.counts,
        )
        return self.observation(raw, label)

    def exit(self) -> dict[str, object]:
        self.called("exit")
        filtering.verify_references(
            self.plan, self.refs, host_context=HOST, binding=self.binding
        )
        return {
            "strict_controller_exit": True,
            "cgroup_empty": True,
            "peer_exit_zero": True,
        }

    def restore(self) -> dict[str, object]:
        self.called("restore")
        return {
            "unit_absent": True,
            "table_absent": True,
            "cgroup_empty": True,
            "peer_reaped": True,
            "ledger_retained": True,
        }

    def remove_artifacts(self) -> dict[str, object]:
        self.called("artifacts")
        return {"code_runtime_removed": True, "ledger_retained": True}

    def close_peer(self) -> None:
        self.called("close_peer")

    def write_ledger(self, value: object) -> None:
        self.called("ledger")
        self.ledger = json.loads(json.dumps(value))


def test_complete_real_runner_uses_four_bound_phases_and_exact_budget() -> None:
    ops = FakeOps()
    value = cast(dict[str, Any], probe.run_owner(ops))
    assert value["result"] == "observed_expected_and_restored"
    assert ops.ledger == value
    assert ops.calls.count("peer") == ops.calls.count("client") == 1
    assert ops.calls.count("switch_allow") == 2 and ops.calls.count("switch_stall") == 1
    assert ops.calls.index("close_peer") < ops.calls.index("ledger")
    assert value["limits"]["active_connect_entries"] == 2
    assert value["limits"]["expected_application_send_entries"] == 10
    assert value["limits"]["node_pi_auth_model_calls"] == 0


@pytest.mark.parametrize(
    "stage",
    [
        "peer",
        "client",
        "filter",
        "switch_allow",
        "baseline",
        "switch_stall",
        "negative",
        "resumed",
        "finished",
        "exit",
        "restore",
        "artifacts",
        "close_peer",
    ],
)
def test_failure_never_retries_or_claims_success(stage: str) -> None:
    ops = FakeOps(stage)
    value = cast(dict[str, Any], probe.run_owner(ops))
    assert value["result"] == "unknown"
    assert ops.calls.count("peer") <= 1 and ops.calls.count("client") <= 1
    assert ops.ledger == value
    if stage not in {"restore", "artifacts", "close_peer"}:
        assert value["failure_reason"] == "metadata_unknown"
    assert "ledger" in ops.calls


def test_bad_observation_is_not_a_successful_negative() -> None:
    class Bad(FakeOps):
        def reports(self, stage: str) -> dict[str, Any]:
            rows = super().reports(stage)
            if stage == "negative":
                rows["client"]["metadata"]["new_main_payload_bytes_observed"] = 1
            return rows

    ops = Bad()
    value = cast(dict[str, Any], probe.run_owner(ops))
    assert value["result"] == "unknown" and value["failure_stage"] == "negative"
    assert value["failure_reason"] == "negative_unknown"
    assert ops.calls.count("switch_allow") == 1


def test_missing_gate_reference_blocks_before_resume() -> None:
    class Bad(FakeOps):
        def reports(self, stage: str) -> dict[str, Any]:
            rows = super().reports(stage)
            if stage == "baseline":
                rows["client"]["metadata"]["gate_reference_sha256"] = "f" * 64
            return rows

    value = probe.run_owner(Bad())
    assert (
        value["result"] == "unknown"
        and value["failure_reason"] == "gate_reference_unknown"
    )


def test_sender_close_failure_is_reflected_in_serialized_permanent_result() -> None:
    ops = FakeOps("close_peer")
    value = cast(dict[str, Any], probe.run_owner(ops))
    assert value["result"] == "unknown"
    assert value["peer_close_error"] == "peer_descriptor_unknown"
    assert ops.ledger == value


def test_controller_frame_parser_does_not_store_external_text_in_errors() -> None:
    with pytest.raises(probe.ProbeRejected, match="frame_unknown") as error:
        probe.FrameBuffer().feed(b"public-unexpected-frame\n")
    assert str(error.value) == "frame_unknown"


def test_actual_pump_rejects_partial_B_bytes_during_stall() -> None:
    role: Any = object.__new__(probe.Role)
    main = object()
    role.main = main
    role.listener = None
    role.stage = "stall"
    role.deadline = float("inf")
    role.selector = SimpleNamespace(
        select=lambda _timeout: [(SimpleNamespace(fileobj=main), 1)]
    )
    transport = SimpleNamespace(received_bytes=0, eof=set())

    def read(_sock: object) -> list[tuple[str, int]]:
        transport.received_bytes = 1
        return []

    transport.read = read
    role.transport = transport
    with pytest.raises(probe.ProbeRejected, match="stall_payload_arrived_unknown"):
        role.pump(0)


def test_root_reader_rejects_ancestor_alias_before_any_external_body_read(
    tmp_path: Any,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o755)
    worker = runtime / "worker"
    worker.mkdir(mode=0o700)
    (worker / "client").symlink_to(outside, target_is_directory=True)
    value = report(
        "client",
        "ready",
        {
            "pid": 222,
            "uid": 1000,
            "gid": 1000,
            "core_zero": True,
            "no_new_privs": True,
            "effective_permitted_inheritable_ambient_empty": True,
        },
    )
    p = outside / "ready.json"
    p.write_bytes(probe.encoded(value))
    p.chmod(0o600)
    ops: Any = object.__new__(probe.HostOperations)
    ops.case = SimpleNamespace(runtime=runtime, worker=worker)
    ops.deadline = float("inf")
    ops.peer = None
    ops.created = {runtime: (runtime.stat().st_dev, runtime.stat().st_ino)}
    ops.worker_identities = {}
    with pytest.raises(probe.ProbeRejected, match="metadata_directory_unknown"):
        ops.read_role("client", "ready")


def test_short_stall_window_cannot_claim_declared_one_second() -> None:
    role: Any = object.__new__(probe.Role)
    role.main = object()
    role.main_received = set()
    role.main_bytes_at_stall = 0
    role.transport = SimpleNamespace(
        received_per_socket={role.main: 0},
        buffers={role.main: SimpleNamespace(pending=b"")},
    )
    with pytest.raises(probe.ProbeRejected, match="negative_duration_unknown"):
        role.observe_negative_window(1, 0)


def test_authorized_close_gate_handles_fin_race() -> None:
    role: Any = object.__new__(probe.Role)
    main = object()
    role.main = main
    role.listener = None
    role.stage = "resume"
    role.resumption_validated = True
    role.deadline = float("inf")
    role.selector = SimpleNamespace(
        select=lambda _timeout: [(SimpleNamespace(fileobj=main), 1)],
        unregister=lambda _sock: None,
    )
    role.transport = SimpleNamespace(received_bytes=0, eof=set())

    def read(_sock: object) -> list[tuple[str, int]]:
        role.transport.eof.add(main)
        return []

    role.transport.read = read
    role.gate = lambda _name: {"stage": "close"}
    role.pump(0)
    assert role.stage == "closing"


def test_complete_regular_metadata_cannot_ignore_short_read_tail(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = report(
        "client",
        "ready",
        {
            "pid": 222,
            "uid": 1000,
            "gid": 1000,
            "core_zero": True,
            "no_new_privs": True,
            "effective_permitted_inheritable_ambient_empty": True,
        },
    )
    first = probe.encoded(value)
    path = tmp_path / "ready.json"
    path.write_bytes(first + b" trailing-invalid")
    path.chmod(0o600)
    monkeypatch.setattr(os, "read", lambda _fd, _count: first)
    with pytest.raises(probe.ProbeRejected, match="metadata_unknown"):
        probe.read_metadata(path, uid=os.getuid())


def owned_tree(
    tmp_path: Any,
) -> tuple[Any, dict[str, tuple[int, bool, int]], dict[str, tuple[int, int]]]:
    root = tmp_path / "artifact"
    root.mkdir(mode=0o755)
    worker = root / "worker"
    worker.mkdir(mode=0o700)
    child = worker / "client"
    child.mkdir(mode=0o700)
    p = child / "report.json"
    p.write_bytes(b"{}")
    p.chmod(0o600)
    q = root / "gate.json"
    q.write_bytes(b"{}")
    q.chmod(0o644)
    uid = os.getuid()
    layout = {
        "worker": (uid, True, 0o700),
        "worker/client": (uid, True, 0o700),
        "worker/client/report.json": (uid, False, 0o600),
        "gate.json": (uid, False, 0o644),
    }
    identities = {
        name: (path.stat().st_dev, path.stat().st_ino)
        for name, path in [("worker", worker), ("worker/client", child)]
    }
    return root, layout, identities


def test_actual_pinned_artifact_tree_removes_only_closed_tree(tmp_path: Any) -> None:
    root, layout, ids = owned_tree(tmp_path)
    tree = probe.PinnedArtifactTree(
        root,
        layout,
        (root.stat().st_dev, root.stat().st_ino),
        ids,
        root_uid=os.getuid(),
    )
    try:
        tree.inspect()
        tree.verify()
        assert tree.remove() == 5
        assert not root.exists()
    finally:
        tree.close()


def test_unknown_directory_is_rejected_before_any_stat_inside_it(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, layout, ids = owned_tree(tmp_path)
    unknown = root / "foreign"
    unknown.mkdir()
    (unknown / "never-inspect").write_bytes(b"public")
    real = os.stat
    visited = []

    def watched(path: Any, *args: Any, **kwargs: Any) -> Any:
        if str(path) in {"foreign", "never-inspect"}:
            visited.append(str(path))
        return real(path, *args, **kwargs)

    tree = probe.PinnedArtifactTree(
        root,
        layout,
        (root.stat().st_dev, root.stat().st_ino),
        ids,
        root_uid=os.getuid(),
    )
    monkeypatch.setattr(os, "stat", watched)
    with pytest.raises(probe.ProbeRejected, match="artifact_member_unknown"):
        tree.inspect()
    assert visited == [] and (root / "gate.json").exists()


def test_known_directory_alias_never_scans_external_members(tmp_path: Any) -> None:
    root, layout, ids = owned_tree(tmp_path)
    child = root / "worker/client"
    (child / "report.json").unlink()
    child.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "report.json"
    sentinel.write_bytes(b"public")
    child.symlink_to(outside, target_is_directory=True)
    tree = probe.PinnedArtifactTree(
        root,
        layout,
        (root.stat().st_dev, root.stat().st_ino),
        ids,
        root_uid=os.getuid(),
    )
    with pytest.raises(probe.ProbeRejected, match="artifact_member_unknown"):
        tree.inspect()
    assert sentinel.read_bytes() == b"public" and (root / "gate.json").exists()


def test_stall_byte_proof_is_per_socket_and_control_does_not_pollute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    role: Any = object.__new__(probe.Role)
    main = object()
    control = object()
    role.main = main
    role.main_received = set()
    role.main_bytes_at_stall = 12
    role.transport = SimpleNamespace(
        received_per_socket={main: 12, control: 99},
        buffers={main: SimpleNamespace(pending=b"")},
    )
    values = iter([10, 1_000_000_011, 1_000_000_012])
    monkeypatch.setattr(time, "monotonic_ns", lambda: next(values))
    role.pump = lambda *_args: None
    observed = role.observe_negative_window(1_000_000_010, 1)
    assert observed["new_main_payload_bytes_observed"] == 0
    assert observed["negative_finished_monotonic_ns"] >= 1_000_000_010


@pytest.mark.parametrize("change", ["partial_main", "complete_main", "short_window"])
def test_root_rejects_invalid_negative_evidence(change: str) -> None:
    class Bad(FakeOps):
        def reports(self, stage: str) -> dict[str, Any]:
            values = super().reports(stage)
            if stage == "negative":
                row = values["client"]["metadata"]
                if change == "partial_main":
                    row["new_main_payload_bytes_observed"] = 1
                elif change == "complete_main":
                    row["main_B_received"] = True
                else:
                    row["negative_started_monotonic_ns"] = (
                        row["negative_end_monotonic_ns"] - 1
                    )
            return values

    value = probe.run_owner(Bad())
    assert value["result"] == "unknown" and value["failure_stage"] == "negative"
    assert value["failure_reason"] in {
        "negative_unknown",
        "negative_duration_unknown",
        "duplex_operation_unknown",
    }


def test_eof_without_authorized_close_is_still_unknown() -> None:
    role: Any = object.__new__(probe.Role)
    main = object()
    role.main = main
    role.listener = None
    role.stage = "resume"
    role.resumption_validated = True
    role.deadline = float("inf")
    role.selector = SimpleNamespace(
        select=lambda _timeout: [(SimpleNamespace(fileobj=main), 1)],
        unregister=lambda _sock: None,
    )
    role.transport = SimpleNamespace(received_bytes=0, eof=set())

    def read(_sock: object) -> list[tuple[str, int]]:
        role.transport.eof.add(main)
        return []

    role.transport.read = read
    role.gate = lambda _name: None
    with pytest.raises(probe.ProbeRejected, match="early_eof_unknown"):
        role.pump(0)


def test_unknown_phase_cannot_enter_any_host_command() -> None:
    ops: Any = object.__new__(probe.HostOperations)
    entered = []
    ops.nft = lambda *_args, **_kw: entered.append(True)
    with pytest.raises(probe.ProbeRejected, match="gate_unknown"):
        ops.switch("not-a-phase")
    assert entered == []


def test_gate_extra_cannot_override_scope_before_mutation() -> None:
    ops: Any = object.__new__(probe.HostOperations)
    with pytest.raises(probe.ProbeRejected, match="gate_unknown"):
        ops.gate("baseline", {"scope": "unexpected"})


def filter_host(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, dict[str, Any], list[str]]:
    ops: Any = object.__new__(probe.HostOperations)
    ops.case = probe.Case()
    ops.plan = ops.case.plan
    ops.config = {"host": HOST}
    ops.peer = SimpleNamespace(pid=2003, poll=lambda: 0)
    ops.peer_fd = None
    ops.client_pid = 2004
    ops.binding = None
    ops.phase_reference = None
    ops.phase_references = []
    ops.counts = filtering.Counts()
    ops.current_phase = "deny"
    ops.table_created = False
    ops.create_uncertain = False
    ops.unit_created = False
    ops.unit_attempted = False
    ops.stall_start_counts = filtering.Counts()
    state: dict[str, Any] = {
        "phase": "deny",
        "packets": (0,) * 6,
        "offset": 0,
        "present": False,
    }
    commands = []
    ops.verify_scope = lambda: None
    ops.cg = lambda **_kw: SimpleNamespace(exists=True, pids={2004})
    monkeypatch.setattr(guardian, "read_cgroup_identity", lambda _plan: (30, 777))
    ops.manager = lambda **_kw: {}
    ops.close_peer = lambda: None
    ops.table_present = lambda: state["present"]

    def nft(*args: Any, **kwargs: Any) -> bytes:
        if args == ("-j", "list", "table", "inet", ops.plan.table):
            return probe.encoded(
                kernel(state["phase"], state["packets"], state["offset"])
            )
        assert args == ("-f", "-")
        data = kwargs["data"]
        if data == filtering.render_create(ops.plan).encode():
            state["present"] = True
            commands.append("create")
        elif data == filtering.render_delete(ops.plan).encode():
            state["present"] = False
            commands.append("delete")
        elif data == filtering.render_allow(ops.plan).encode():
            state["phase"] = "allow"
            state["offset"] += 10
            commands.append("allow")
        elif data == filtering.render_stall(ops.plan).encode():
            state["phase"] = "stall"
            state["offset"] += 10
            commands.append("stall")
        else:
            raise AssertionError("unexpected mutation")
        return b""

    ops.nft = nft
    return ops, state, commands


def test_actual_host_uses_atomic_batches_and_complete_phase_reference_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ops, state, commands = filter_host(monkeypatch)
    ops.create_filter()
    ops.switch("allow")
    state["packets"] = (2, 2, 0, 0, 0, 0)
    ops.snapshot("baseline_complete")
    ops.switch("stall")
    state["packets"] = (2, 2, 1, 1, 0, 0)
    ops.snapshot("negative_complete")
    ops.switch("allow")
    state["packets"] = (4, 4, 1, 1, 0, 0)
    ops.snapshot("before_exit")
    filtering.verify_references(
        ops.plan, ops.phase_references, host_context=HOST, binding=ops.binding
    )
    assert commands == ["create", "allow", "stall", "allow"]
    ops.cg = lambda **_kw: SimpleNamespace(exists=False, pids=set())
    restored = ops.restore()
    assert restored["table_absent"] is True and commands[-1] == "delete"


def test_actual_host_late_packet_blocks_table_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ops, state, commands = filter_host(monkeypatch)
    ops.create_filter()
    ops.switch("allow")
    state["packets"] = (2, 2, 0, 0, 0, 0)
    ops.snapshot("baseline_complete")
    ops.switch("stall")
    state["packets"] = (2, 2, 1, 1, 0, 0)
    ops.snapshot("negative_complete")
    ops.switch("allow")
    state["packets"] = (4, 4, 1, 1, 0, 0)
    ops.snapshot("before_exit")
    ops.cg = lambda **_kw: SimpleNamespace(exists=False, pids=set())
    state["packets"] = (4, 5, 1, 1, 0, 0)
    with pytest.raises(filtering.DuplexRejected, match="duplex_late_packet"):
        ops.restore()
    assert "delete" not in commands and state["present"] is True


@pytest.mark.parametrize("direction", ["in", "out"])
def test_missing_one_negative_direction_never_passes(
    monkeypatch: pytest.MonkeyPatch,
    direction: str,
) -> None:
    ops, state, _commands = filter_host(monkeypatch)
    ops.create_filter()
    ops.switch("allow")
    state["packets"] = (2, 2, 0, 0, 0, 0)
    ops.snapshot("baseline_complete")
    ops.switch("stall")
    state["packets"] = (
        2,
        2,
        0 if direction == "in" else 1,
        0 if direction == "out" else 1,
        0,
        0,
    )
    with pytest.raises(probe.ProbeRejected, match="negative_direction_missing"):
        ops.snapshot("negative_complete")


def test_actual_host_cleanup_pins_both_complete_trees_then_removes(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    from scripts.issue167_live_signal_bundle import cleanup_source

    source = cleanup_source()
    module = types.ModuleType("synthetic_duplex_cleanup_boundary")
    sys.modules[module.__name__] = module
    exec(compile(source, "<synthetic-reviewed-cleanup>", "exec"), module.__dict__)
    runtime = tmp_path / "runtime"
    code = tmp_path / "code"
    runtime.mkdir(mode=0o755)
    code.mkdir(mode=0o755)
    worker = runtime / "worker"
    worker.mkdir(mode=0o700)
    ids = {}
    for path in (worker, worker / "client", worker / "peer"):
        if path != worker:
            path.mkdir(mode=0o700)
        ids[str(path.relative_to(runtime))] = (path.stat().st_dev, path.stat().st_ino)
    for name in ("baseline", "stall", "resume", "close", "exit"):
        p = runtime / ("gate-" + name + ".json")
        p.write_bytes(b"{}")
        p.chmod(0o644)
    for role in ("client", "peer"):
        for stage in ("ready", "baseline", "negative", "resumed", "finished"):
            p = worker / role / (stage + ".json")
            p.write_bytes(b"{}")
            p.chmod(0o600)
    files = {n: b"public source" for n in probe.CORE_NAMES}
    config = {
        "scope": probe.SCOPE,
        "run_id": probe.RUN,
        "members": {n: probe.digest(b) for n, b in files.items()},
        "tools": {},
    }
    files["scope.json"] = probe.encoded(config)
    for name, data in {
        **files,
        "manifest.json": probe.installed_manifest(config, files),
    }.items():
        p = code / name
        p.write_bytes(data)
        p.chmod(0o644)
    ledger = tmp_path / "permanent"
    ledger.write_bytes(b"original unknown")
    ops: Any = object.__new__(probe.HostOperations)
    ops.case = SimpleNamespace(runtime=runtime, code=code)
    ops.manager = lambda **_kw: {}
    ops.table_present = lambda: False
    ops.cg = lambda **_kw: SimpleNamespace(pids=set())
    ops.peer = SimpleNamespace(poll=lambda: 0)
    ops.cleanup = module
    ops.files = files
    ops.worker_identities = ids
    ops.created = {p: (p.stat().st_dev, p.stat().st_ino) for p in (runtime, code)}
    ops.mountinfo = lambda: b"1 0 0:1 / / rw - tmpfs tmpfs rw\n"
    actual_tree = probe.PinnedArtifactTree

    def synthetic_uid_tree(root: Any, layout: Any, *args: Any, **kwargs: Any) -> Any:
        return actual_tree(
            root,
            {
                n: (os.getuid() if owner == 0 else owner, directory, mode)
                for n, (owner, directory, mode) in layout.items()
            },
            *args,
            root_uid=os.getuid(),
            **kwargs,
        )

    monkeypatch.setattr(probe, "PinnedArtifactTree", synthetic_uid_tree)
    assert ops.remove_artifacts() == {
        "code_runtime_removed": True,
        "ledger_retained": True,
    }
    assert (
        not runtime.exists()
        and not code.exists()
        and ledger.read_bytes() == b"original unknown"
    )
    sys.modules.pop(module.__name__)
