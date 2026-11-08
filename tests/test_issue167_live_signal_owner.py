"""Independent E01 sender D1: injected descriptors/syscalls, no actual signal."""

from typing import Any

import pytest

from scripts import issue167_live_signal_case as contract
from scripts import issue167_live_signal_owner as owner


def observed() -> dict[str, Any]:
    return {
        "phase": "complete",
        "marker_publications": 1,
        "sigint_received": 1,
        "effective_sigint_received": 1,
        "late_sigint_received": 0,
        "same_keyboard_interrupt_propagated": True,
        "partial_candidate_accepted": False,
        "public_terminate_returned": True,
        "model_factory_count": 1,
    }


def marker() -> dict[str, Any]:
    return {
        "scope": contract.SCOPE,
        "run_id": contract.RUN,
        "category": "decoded_protocol_signal_window",
        "sequence": 1,
        "count": 1,
        "fingerprint": "a" * 64,
        "prompt_frames_completed": 1,
        "prompt_ack_count": 1,
        "agent_settled": False,
        "closing": False,
        "integrity": "complete",
        "prompt_ack_sequence": 9,
        "agent_start_sequence": 10,
    }


def target() -> dict[str, int]:
    return {"pid": 1234, "starttime": 10, "cgroup_device": 20, "cgroup_inode": 844648}


def delivery() -> dict[str, Any]:
    return {
        "category": "external_sigint_delivery",
        "sequence": 1,
        "attempted_count": 1,
        "syscall_returned": True,
        "not_delivered_exited": False,
        "target": "pidfd_bound_controller_only",
        "target_reference": target(),
        "marker_reference": marker(),
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("sequence", True),
        ("attempted_count", True),
        ("syscall_returned", 1),
        ("not_delivered_exited", 0),
    ],
)
def test_delivery_does_not_accept_bool_integer_coercion(key: str, value: Any) -> None:
    row = delivery()
    row[key] = value
    with pytest.raises(contract.CaseRejected, match="signal_delivery_unknown"):
        owner.reconcile_delivery(row, observed(), normal_complete=False)


def test_normal_complete_is_an_actual_boolean() -> None:
    late = observed()
    late.update(
        effective_sigint_received=0,
        late_sigint_received=1,
        same_keyboard_interrupt_propagated=False,
    )
    with pytest.raises(contract.CaseRejected, match="signal_delivery_unknown"):
        owner.reconcile_delivery(delivery(), late, normal_complete="yes")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "key,value",
    [
        ("pid", True),
        ("pid", 1),
        ("starttime", True),
        ("starttime", 0),
        ("cgroup_device", False),
        ("cgroup_inode", 0),
    ],
)
def test_bad_identity_rejected_before_any_pidfd_open(key: str, value: Any) -> None:
    values = {"pid": 123, "starttime": 10, "cgroup_device": 30, "cgroup_inode": 44}
    values[key] = value
    called = []

    def opened(pid: int) -> int:
        called.append(pid)
        return 5

    with pytest.raises(contract.CaseRejected, match="signal_target_unknown"):
        identity = owner.ControllerIdentity(**values)
        owner.PinnedSender(
            identity,
            lambda: identity,
            opener=opened,
            closer=lambda _fd: None,
            alive=lambda _fd: True,
        )
    assert called == []


def test_sent_but_missing_handler_reference_is_unknown() -> None:
    row = observed()
    row.update(
        sigint_received=0,
        effective_sigint_received=0,
        same_keyboard_interrupt_propagated=False,
    )
    with pytest.raises(contract.CaseRejected, match="signal_delivery_unknown"):
        owner.reconcile_delivery(delivery(), row, normal_complete=True)


def test_complete_matching_delivery_and_effective_handler_is_expected() -> None:
    assert (
        owner.reconcile_delivery(delivery(), observed(), normal_complete=False)
        == "observed_expected"
    )


def test_late_signal_needs_a_valid_complete_normal_candidate() -> None:
    row = observed()
    row.update(
        effective_sigint_received=0,
        late_sigint_received=1,
        same_keyboard_interrupt_propagated=False,
    )
    assert (
        owner.reconcile_delivery(delivery(), row, normal_complete=True)
        == "not_triggered"
    )
    with pytest.raises(contract.CaseRejected, match="signal_delivery_unknown"):
        owner.reconcile_delivery(delivery(), row, normal_complete=False)


class FakeOperations:
    def __init__(
        self,
        *,
        expected: bool = True,
        near_cap: bool = False,
        failure: str | None = None,
    ) -> None:
        import copy

        from tests.test_issue167_live_signal_case import complete_worker

        self.worker = complete_worker(expected=expected, near_cap=near_cap)
        self.failure = failure
        self.calls: list[str] = []
        self.ledger: dict[str, Any] | None = None
        self.exit_metadata: dict[str, object] = {
            "gate_checkpoint": "write_complete",
            "gate_published": True,
            "wait_checkpoint": "complete",
            "cgroup_empty": True,
            "manager": None,
            "failure_reason": None,
        }
        self.expected = expected
        self.copy = copy.deepcopy

    def step(self, name: str) -> None:
        self.calls.append(name)
        if self.failure == name:
            raise contract.CaseRejected("synthetic_failure")

    def preflight(self) -> None:
        self.step("preflight")

    def reserve(self) -> None:
        self.step("reserve")

    def install(self) -> None:
        self.step("install")

    def start(self) -> None:
        self.step("start")

    def ready(self) -> dict[str, object]:
        from scripts.issue167_resolver_case import READY_FIELDS

        self.step("ready")
        return {k: self.worker[k] for k in READY_FIELDS}

    def exercise_rules(self) -> dict[str, object]:
        import hashlib
        import json

        from scripts import issue167_service_egress as egress
        from tests.test_issue167_live_signal_case import plan
        from tests.test_issue167_service_egress import HOST, PROFILE, fixture

        self.step("rules")
        p = plan()
        raw = PROFILE.read_bytes()
        profile = egress.FrozenEgress.from_profile(
            p.base_plan(), raw, hashlib.sha256(raw).hexdigest(), HOST
        )
        stages = []
        binding = None
        for stage, enabled, count in [
            ("created_deny", False, 0),
            ("preauthentication_complete", False, 0),
            ("activated", True, 0),
            ("auth_complete_1", True, 12),
            ("before_external_sigint", True, 12),
            ("after_external_sigint", True, 12),
            ("signal_case_complete", True, 14),
            ("post_stop", True, 14),
        ]:
            payload = json.loads(
                json.dumps(fixture(enabled)).replace("0123456789ab", contract.RUN)
            )
            for row in payload["nftables"]:
                if "counter" in row:
                    c = row["counter"]
                    c["packets"] = count if c["name"] == "allowed" else 0
                    c["bytes"] = c["packets"] * 64
            if binding is None:
                binding = egress.make_binding(
                    profile, payload, (20, 844648), host_context=HOST
                )
            egress.verify_state(
                profile, payload, enabled=enabled, host_context=HOST, binding=binding
            )
            stages.append({"stage": stage, "kernel_state": payload})
        return {
            "scope": "service_network_rule_and_representative_flow",
            "binding": binding,
            "snapshots": stages,
            "counts_semantics": "packet_not_HTTP_or_DNS_query_count",
        }

    def phase_gate(self, category: str, sequence: int) -> None:
        self.step("gate_" + category)

    def preflight_result(self) -> dict[str, object]:
        self.step("preauthentication")
        return self.copy(self.worker["preflight"])

    def activate(self) -> None:
        self.step("activate")

    def auth_ready(self, sequence: int) -> None:
        self.step("auth")

    def signal_or_terminal(self) -> dict[str, object]:
        self.step("signal")
        return {
            "category": "external_sigint_delivery",
            "sequence": 1,
            "attempted_count": int(self.expected),
            "syscall_returned": self.expected,
            "not_delivered_exited": False,
            "target": "pidfd_bound_controller_only",
            "target_reference": target(),
            "marker_reference": marker() if self.expected else None,
        }

    def collect(self) -> dict[str, object]:
        from tests.test_issue167_live_signal_case import plan

        self.step("collect")
        return contract.validate_result(plan(), self.copy(self.worker))

    def wait_exit(self) -> None:
        self.step("exit")

    def restore(self) -> dict[str, object]:
        self.step("restore")
        return {
            "result": "host_policy_restored",
            "global_resolver_unchanged": True,
            "ledger_retained": True,
            "table_absent": True,
            "unit_absent": True,
        }

    def finish(self) -> dict[str, object]:
        self.step("finish")
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        import json

        self.step("ledger")
        self.ledger = json.loads(json.dumps(value))

    def database_restoration(self) -> dict[str, object]:
        self.step("db_restore")
        return {
            "result": "original_selection_restored",
            "append_only_history_retained": True,
            "source": "trusted_worker_public_API_CAS",
        }

    def selection_journal(self) -> dict[str, object]:
        self.step("journal")
        return {
            "source": "trusted_worker_control_journal_receipt_projection",
            "entries": self.copy(self.worker["selection_journal"]),
            "completeness": "captured",
        }

    def close_sender(self) -> None:
        self.step("close_sender")


@pytest.mark.parametrize("expected", [True, False])
def test_full_owner_preserves_distinct_complete_outcomes(expected: bool) -> None:
    from tests.test_issue167_live_signal_case import plan

    ops = FakeOperations(expected=expected)
    out = owner.run_owner(plan(), ops)
    assert out["result"] == (
        "observed_expected_and_restored" if expected else "not_triggered_and_restored"
    )
    assert ops.calls.count("start") == ops.calls.count("signal") == 1
    assert ops.ledger == out


@pytest.mark.parametrize(
    "stage",
    [
        "preflight",
        "reserve",
        "install",
        "start",
        "ready",
        "rules",
        "preauthentication",
        "auth",
        "signal",
        "collect",
        "exit",
        "restore",
        "db_restore",
        "finish",
        "close_sender",
    ],
)
def test_full_owner_failure_never_retries_or_claims_success(stage: str) -> None:
    from tests.test_issue167_live_signal_case import plan

    ops = FakeOperations(failure=stage)
    out = owner.run_owner(plan(), ops)
    assert out["result"] == "unknown"
    assert ops.calls.count("start") <= 1 and ops.calls.count("signal") <= 1
    if stage not in {"preflight", "reserve"}:
        assert ops.ledger == out
    else:
        assert ops.ledger is None


def near_cap_owner_envelope() -> dict[str, Any]:
    from tests.test_issue167_live_signal_case import plan

    ops = FakeOperations(near_cap=True)
    result = owner.run_owner(plan(), ops)
    assert result["result"] == "observed_expected_and_restored"
    return {
        "scope": "h1_owner_automation_only",
        "run_id": contract.RUN,
        "manifest_sha256": "a" * 64,
        "owner_result": result["result"],
        "preflight_result": result,
    }


def test_real_near_cap_owner_envelope_fits_original_driver_cap() -> None:
    import json

    envelope = near_cap_owner_envelope()
    result = envelope["preflight_result"]
    assert len(result["rules"]["snapshots"]) == 8
    assert len(json.dumps(result["worker_result"]).encode()) < 65536
    assert len(json.dumps(envelope).encode()) < 131072


@pytest.mark.parametrize("unknown", [False, True])
def test_actual_owner_finish_uses_generated_tree_and_rejects_unknown_members(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, unknown: bool
) -> None:
    import json
    import os
    import sys
    import types
    import zipfile
    from pathlib import Path
    from types import SimpleNamespace

    from scripts import issue167_live_signal_bundle as bundle

    name = "scripts.issue167_live_signal_cleanup"
    cleanup = types.ModuleType(name)
    monkeypatch.setitem(sys.modules, name, cleanup)
    exec(
        compile(bundle.cleanup_source(), "<generated-boundary>", "exec"),
        cleanup.__dict__,
    )
    code = tmp_path / "code"
    runtime = tmp_path / "runtime"
    code.mkdir(mode=0o755)
    runtime.mkdir(mode=0o755)
    (runtime / "worker").mkdir(mode=0o700)
    (code / "stub.py").write_bytes(b"public synthetic source")
    (code / "stub.py").chmod(0o644)
    with zipfile.ZipFile(code / "materials.zip", "w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("value-low-E01/user.txt", b"public synthetic input")
    (code / "materials.zip").chmod(0o644)
    manifest = {"members": {"stub.py": "a" * 64, "materials.zip": "b" * 64}}
    (code / "manifest.json").write_text(json.dumps(manifest))
    (code / "manifest.json").chmod(0o644)
    material = runtime / "worker/materials/value-low-E01"
    material.mkdir(parents=True)
    (material / "user.txt").write_bytes(b"public synthetic input")
    (material.parent / "manifest.json").write_bytes(b"{}")
    (runtime / "worker/worker-result.json").write_bytes(b"{}")
    for path in runtime.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    if unknown:
        (runtime / "worker/unexpected").write_bytes(b"synthetic unknown")
    calls = []
    op: Any = owner.LiveOperations.__new__(owner.LiveOperations)
    op.case = SimpleNamespace(uid=os.getuid(), runtime_root=runtime, install_root=code)
    op.worker_accepted = op.restoration_accepted = True
    op.table_created = op.create_uncertain = False
    op.plan = object()
    op.commands = SimpleNamespace(tools={"nft": Path("/synthetic/nft")})

    def absent(*_args: Any, **_kwargs: Any) -> set[str]:
        calls.append("unit_absent")
        return set()

    op.owner = SimpleNamespace(
        check_units=absent,
        table_present=lambda *_args: False,
    )
    op.phase = SimpleNamespace(
        read_cgroup_state=lambda *_args, **_kwargs: SimpleNamespace(pids=set())
    )
    op.contract = SimpleNamespace(
        verify_installation=lambda *_args: calls.append("verified"),
        read_metadata=lambda *_args, **_kwargs: manifest,
    )
    op.manifest_sha = "a" * 64
    op._run = lambda *_args: b"{}"
    if unknown:
        with pytest.raises(owner.base.OwnerRejected, match="cleanup_member_unknown"):  # type: ignore[attr-defined]
            op.finish()
        assert code.exists() and runtime.exists()
    else:
        assert op.finish() == {
            "result": "successful_artifacts_removed",
            "ledger_retained": True,
        }
        assert not code.exists() and not runtime.exists()
    assert "verified" in calls and "unit_absent" in calls


def test_pinned_sender_persists_exact_lifecycle_reference_without_reopening() -> None:
    ident = owner.ControllerIdentity.from_reference(target())
    opened: list[int] = []
    closed: list[int] = []
    sent: list[tuple[int, int]] = []
    intents: list[dict[str, object]] = []

    def opener(pid: int) -> int:
        opened.append(pid)
        return 77

    sender = owner.PinnedSender(
        ident,
        lambda: ident,
        opener=opener,
        closer=closed.append,
        alive=lambda _fd: True,
        sender=lambda fd, sig: sent.append((fd, sig)),
    )
    out = sender.deliver(
        marker(),
        run_id=contract.RUN,
        fingerprint="a" * 64,
        persist_intent=intents.append,
    )
    assert out["target_reference"] == intents[0]["target_reference"] == target()
    assert out["marker_reference"] == intents[0]["marker_reference"] == marker()
    assert opened == [target()["pid"]] and len(sent) == 1
    with pytest.raises(contract.CaseRejected, match="signal_retry_forbidden"):
        sender.deliver(
            marker(),
            run_id=contract.RUN,
            fingerprint="a" * 64,
            persist_intent=intents.append,
        )
    sender.close()
    assert closed == [77] and len(sent) == 1


@pytest.mark.parametrize("kind", ["pid", "cgroup", "fingerprint"])
def test_actual_owner_checks_delivery_references_against_bound_worker(
    kind: str,
) -> None:
    from tests.test_issue167_live_signal_case import plan

    ops = FakeOperations()
    original = ops.signal_or_terminal

    def wrong() -> dict[str, object]:
        out: dict[str, Any] = original()
        if kind == "pid":
            out["target_reference"]["pid"] += 1
        elif kind == "cgroup":
            out["target_reference"]["cgroup_inode"] += 1
        else:
            out["marker_reference"]["fingerprint"] = "b" * 64
        return out

    ops.signal_or_terminal = wrong  # type: ignore[method-assign]
    value = owner.run_owner(plan(), ops)
    assert value["result"] == "unknown" and value["failure_stage"] == "worker_result"
    assert "finish" not in ops.calls and ops.ledger == value
