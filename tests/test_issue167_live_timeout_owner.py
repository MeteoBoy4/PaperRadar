"""Independent D1 T1 owner: no root, services, signals, sockets or real auth."""

from __future__ import annotations

import copy
import errno
import json
import types
from pathlib import Path
from typing import Any

import pytest

from scripts import issue167_live_timeout_case as contract
from scripts import issue167_live_timeout_filter as filtering
from scripts import issue167_live_timeout_owner as owner
from scripts import issue167_resolver_owner as base
from scripts.issue167_resolver_case import READY_FIELDS
from tests.test_issue167_live_signal_case import complete_worker as earlier_worker
from tests.test_issue167_live_signal_owner import FakeOperations as EarlierOps
from tests.test_issue167_live_timeout_case import FP, marker, plan, row, timed
from tests.test_issue167_live_timeout_filter import HOST, RUN, fixture


def delivery(*, expected: bool = True) -> dict[str, Any]:
    return {
        "category": "project_duplex_drop",
        "sequence": 1,
        "attempted_count": int(expected),
        "completed_count": int(expected),
        "marker_reference": marker() if expected else None,
        "intent_monotonic": 16.0 if expected else None,
        "confirmed_monotonic": 16.2 if expected else None,
        "before_counts": filtering.Counts().to_dict() if expected else None,
        "after_counts": filtering.Counts(
            dropped_in=4, dropped_out=4, byte_counts=(0, 0, 256, 256, 0, 0)
        ).to_dict()
        if expected
        else None,
        "target_reference": {
            "pid": 1234,
            "starttime": 10,
            "cgroup_device": 20,
            "cgroup_inode": 844648,
        }
        if expected
        else None,
    }


def test_complete_cut_requires_two_directions_and_original_deadline() -> None:
    assert (
        owner.reconcile_cut(
            delivery(), timed(), worker_outcome="observed_expected", fingerprint=FP
        )
        == "observed_expected"
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("attempted_count", True),
        ("completed_count", 0),
        ("intent_monotonic", float("nan")),
        ("confirmed_monotonic", 314.0),
        ("confirmed_monotonic", float("inf")),
    ],
)
def test_bad_cut_never_becomes_timeout_success(name: str, value: object) -> None:
    value_row = delivery()
    value_row[name] = value
    with pytest.raises(
        contract.CaseRejected, match=r"timeout_(switch|condition)_unknown"
    ):
        owner.reconcile_cut(
            value_row, timed(), worker_outcome="observed_expected", fingerprint=FP
        )


@pytest.mark.parametrize("direction", ["dropped_in", "dropped_out"])
def test_one_sided_drop_is_unknown(direction: str) -> None:
    value = delivery()
    value["after_counts"][direction] = {"packets": 0, "bytes": 0}
    with pytest.raises(contract.CaseRejected, match="timeout_condition_unknown"):
        owner.reconcile_cut(
            value, timed(), worker_outcome="observed_expected", fingerprint=FP
        )


def test_untriggered_does_not_require_expired_token_or_packets() -> None:
    assert (
        owner.reconcile_cut(
            delivery(expected=False),
            timed(reason="candidate", marked=False),
            worker_outcome="not_triggered",
            fingerprint=FP,
        )
        == "not_triggered"
    )


def worker(*, expected: bool = True) -> dict[str, Any]:
    from scripts import issue167_live_signal_case as earlier

    value = json.loads(
        json.dumps(earlier_worker())
        .replace(earlier.RUN, contract.RUN)
        .replace(earlier.SCOPE, contract.SCOPE)
    )
    value["limits"] = dict(contract.LIMITS)
    value["case"] = row(reason="timeout" if expected else "candidate", marked=expected)
    value["result"] = value["case"]["result"]
    value["auth_metadata_journal"] = [
        contract.auth_reference(value["case"]["persistent_auth"][k])
        for k in ("before", "after")
    ]
    return contract.validate_result(plan(), value)


class FakeOperations(EarlierOps):
    def __init__(self, *, expected: bool = True, failure: str | None = None) -> None:
        super().__init__(expected=expected, failure=failure)
        self.worker = worker(expected=expected)
        self.case = plan()
        self.delivery = delivery(expected=expected)
        # Real collect must upgrade the initial copied cut reference using final counts.
        if expected:
            self.delivery["after_counts"] = filtering.Counts().to_dict()
        self.phase_references: list[Any] = []
        self.binding: Any = None
        self.host = HOST
        self.filter_plan = filtering.Plan(contract.RUN)
        self.ready_metadata = {k: self.worker[k] for k in READY_FIELDS}
        self.contract = types.SimpleNamespace(
            validate_result=contract.validate_result, read_metadata=self.read_metadata
        )
        self.worker_accepted = False
        self.duplex_counts = (
            filtering.Counts(
                dropped_in=4, dropped_out=4, byte_counts=(0, 0, 256, 256, 0, 0)
            )
            if expected
            else filtering.Counts()
        )

    def exercise_rules(self) -> dict[str, object]:
        self.step("rules")
        refs: list[Any] = []
        snapshots = []
        previous = filtering.Counts()
        for phase, offset in [
            ("deny", 0),
            ("allow", 100),
            *([("stall", 200)] if self.expected else []),
        ]:
            payload = json.loads(
                json.dumps(fixture(phase, offset=offset)).replace(RUN, contract.RUN)
            )
            if self.binding is None:
                self.binding = filtering.make_binding(
                    self.filter_plan, payload, (20, 844648), host_context=HOST
                )
                reference = self.binding["initial_reference"]
            else:
                reference = filtering.capture_phase(
                    self.filter_plan,
                    payload,
                    phase=phase,
                    host_context=HOST,
                    binding=self.binding,
                    previous_reference=refs[-1],
                    previous_counts=previous,
                )
            refs.append(reference)
            snapshots.append(
                {
                    "phase": phase,
                    "kernel_state": payload,
                    "binding": self.binding,
                    "phase_reference": reference,
                }
            )
        self.phase_references = refs
        return {"binding": self.binding, "snapshots": snapshots}

    def stall_or_terminal(self) -> dict[str, object]:
        self.step("stall")
        return dict(self.delivery)

    def _wait(self, name: str) -> object:
        assert name == "worker-result.json"
        return copy.deepcopy(self.worker)

    def _verify(self, stage: str | None = None) -> filtering.Counts:
        return self.duplex_counts

    def read_metadata(self, path: Path, **_kwargs: Any) -> object:
        if path.name == "case-result-1.json":
            return copy.deepcopy(self.worker["case"])
        for phase in ("before", "after"):
            if path.name == f"auth-metadata-1-{phase}.json":
                return copy.deepcopy(self.worker["case"]["persistent_auth"][phase])
        raise AssertionError("unexpected_control_path")

    def collect(self) -> dict[str, object]:
        self.step("collect")
        return owner.LiveOperations.collect(self)  # type: ignore[arg-type]


@pytest.mark.parametrize("expected", [True, False])
def test_actual_collect_to_owner_preserves_final_cut_counters(expected: bool) -> None:
    ops = FakeOperations(expected=expected)
    # Ready fixture PID must match independently bound controller.
    if expected:
        ops.delivery["target_reference"]["pid"] = ops.ready_metadata["pid"]
    result: Any = owner.run_owner(plan(), ops)
    assert result["result"] == (
        "observed_expected_and_restored" if expected else "not_triggered_and_restored"
    )
    assert ops.ledger == result
    if expected:
        assert result["delivery"]["after_counts"]["dropped_in"]["packets"] == 4
    assert ops.calls.count("start") == ops.calls.count("stall") == 1


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
        "stall",
        "collect",
        "exit",
        "restore",
        "db_restore",
        "finish",
    ],
)
def test_failure_never_retries_or_refunds(stage: str) -> None:
    ops = FakeOperations(failure=stage)
    ops.delivery["target_reference"]["pid"] = ops.ready_metadata["pid"]
    result: Any = owner.run_owner(plan(), ops)
    assert result["result"] == "unknown"
    assert ops.calls.count("start") <= 1 and ops.calls.count("stall") <= 1


def test_auth_success_without_packets_is_allowed() -> None:
    ops: Any = object.__new__(owner.LiveOperations)
    ops.case = plan()
    calls: list[str] = []
    ops._wait = lambda _name: {
        "run_id": contract.RUN,
        "sequence": 1,
        "auth_cli_completed": True,
        "logical_refresh_plan": contract.AUTH_REFRESH_PLAN,
    }

    def verify(stage: str) -> filtering.Counts:
        calls.append(stage)
        return filtering.Counts()

    ops._verify = verify
    owner.LiveOperations.auth_ready(ops, 1)
    assert calls == ["auth_complete_1"]


def near_cap_owner_envelope() -> dict[str, Any]:
    from scripts import issue167_live_signal_case as earlier_case
    from tests.test_issue167_live_signal_case import persistent_auth as earlier_auth

    ops = FakeOperations()
    auth = json.loads(
        json.dumps(earlier_auth(near_cap=True)).replace(earlier_case.RUN, contract.RUN)
    )
    auth["input_source"] = "conditional_H2_plan"
    ops.worker["case"]["persistent_auth"] = auth
    ops.worker["auth_metadata_journal"] = [
        contract.auth_reference(auth[k]) for k in ("before", "after")
    ]
    contract.validate_result(plan(), ops.worker)
    ops.delivery["target_reference"]["pid"] = ops.ready_metadata["pid"]
    out: Any = owner.run_owner(plan(), ops)
    assert out["result"] == "observed_expected_and_restored"
    binding = out["rules"]["binding"]
    references = ops.phase_references
    # Complete original kernel fixtures for every actual declared checkpoint,
    # including post-stop, rather than padding an envelope with ignored data.
    stages = [
        ("created_deny", "deny", 0, 0),
        ("preauthentication_complete", "deny", 0, 0),
        ("transaction_allow", "allow", 100, 0),
        ("auth_complete_1", "allow", 100, 12),
        ("before_duplex_stall", "allow", 100, 16),
        ("transaction_stall", "stall", 200, 16),
        ("before_exit", "stall", 200, 18),
        ("post_stop", "stall", 200, 18),
    ]
    snapshots = []
    for name, phase, offset, allowed in stages:
        packets = (
            allowed,
            allowed,
            4 if phase == "stall" else 0,
            4 if phase == "stall" else 0,
            0,
            0,
        )
        payload = json.loads(
            json.dumps(fixture(phase, offset=offset, packets=packets)).replace(
                RUN, contract.RUN
            )
        )
        counts = filtering.Counts.from_dict(
            {
                r["counter"]["name"]: {
                    "packets": r["counter"]["packets"],
                    "bytes": r["counter"]["bytes"],
                }
                for r in payload["nftables"]
                if "counter" in r
            }
        )
        snapshots.append(
            {
                "stage": name,
                "kernel_state": payload,
                "phase": phase,
                "binding": binding,
                "phase_reference": references[
                    {"deny": 0, "allow": 1, "stall": 2}[phase]
                ],
                "counts": counts.to_dict(),
                "compared_previous_counts": counts.to_dict(),
            }
        )
    out["rules"]["snapshots"] = snapshots
    out["rules"]["phase_references"] = references
    return {
        "scope": "h1_owner_automation_only",
        "run_id": contract.RUN,
        "manifest_sha256": "a" * 64,
        "owner_result": out["result"],
        "preflight_result": out,
    }


@pytest.mark.parametrize("bad", ["none", "short", "alias", "directory_identity"])
def test_real_control_reader_pins_ancestors_and_requires_complete_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    import os
    import stat
    from types import SimpleNamespace

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o755)
    path = runtime / "worker"
    path.mkdir(mode=0o700)
    target = path / "checkpoint.json"
    target.write_bytes(b'{"ok":true}    ')
    target.chmod(0o600)
    real_fstat = os.fstat

    def mapped(fd: int) -> Any:
        value = real_fstat(fd)
        if not stat.S_ISDIR(value.st_mode):
            return value
        leaf = Path(os.readlink(f"/proc/self/fd/{fd}"))
        fields = {
            name: getattr(value, name) for name in dir(value) if name.startswith("st_")
        }
        fields.update(
            st_uid=os.getuid() if leaf == path else 0,
            st_gid=os.getgid() if leaf == path else 0,
            st_mode=value.st_mode & ~0o022,
        )
        return SimpleNamespace(**fields)

    ops: Any = object.__new__(owner.LiveOperations)
    ops.case = SimpleNamespace(uid=os.getuid(), worker_root=path)
    info = path.stat()
    ops.control_directories = {path: (info.st_dev, info.st_ino)}
    monkeypatch.setattr(os, "fstat", mapped)
    if bad == "short":
        real_read = os.read
        reads = 0

        def short(fd: int, size: int) -> bytes:
            nonlocal reads
            reads += 1
            return real_read(fd, 11) if reads == 1 else b""

        monkeypatch.setattr(os, "read", short)
    if bad == "alias":
        other = tmp_path / "other"
        other.write_text("{}")
        target.unlink()
        target.symlink_to(other)
    if bad == "directory_identity":
        ops.control_directories = {path: (info.st_dev, info.st_ino + 1)}
    if bad == "none":
        assert ops._read_metadata(target, owner=os.getuid()) == {"ok": True}
    elif bad == "alias":
        with pytest.raises(OSError) as error:
            ops._read_metadata(target, owner=os.getuid())
        assert error.value.errno == errno.ELOOP
    else:
        with pytest.raises(
            base.OwnerRejected,
            match=r"metadata_(short_or_changed|ancestor_unknown)",
        ):
            ops._read_metadata(target, owner=os.getuid())


@pytest.mark.parametrize("late", ["none", "packets", "bytes"])
def test_actual_post_stop_verifies_and_saves_complete_kernel_state(late: str) -> None:
    fixture_ops = FakeOperations()
    fixture_ops.exercise_rules()
    payload = json.loads(
        json.dumps(fixture("stall", offset=200, packets=(8, 8, 4, 4, 0, 0))).replace(
            RUN, contract.RUN
        )
    )
    op: Any = object.__new__(owner.LiveOperations)
    op.filter_plan = fixture_ops.filter_plan
    op.binding = fixture_ops.binding
    op.phase_reference = fixture_ops.phase_references[-1]
    op.current_phase = "stall"
    op.switch_uncertain = False
    op.snapshots = []
    op.duplex_counts = filtering.Counts(8, 8, 4, 4, 0, 0, (512, 512, 256, 256, 0, 0))
    op.contract = types.SimpleNamespace(current_host_context=lambda: HOST)
    op._identity = lambda **kwargs: None
    if late != "none":
        counter = next(
            r["counter"]
            for r in payload["nftables"]
            if r.get("counter", {}).get("name") == "dropped_in"
        )
        counter[late] += 1
    op._snapshot = lambda: copy.deepcopy(payload)
    if late != "none":
        with pytest.raises(
            filtering.DuplexRejected, match="timeout_filter_late_packet"
        ):
            op._verify("post_stop")
        assert op.snapshots == []
    else:
        before = op.duplex_counts.to_dict()
        assert op._verify("post_stop").to_dict() == before
        assert op.snapshots == [
            {
                "stage": "post_stop",
                "kernel_state": payload,
                "phase": "stall",
                "binding": op.binding,
                "phase_reference": op.phase_reference,
                "counts": before,
                "compared_previous_counts": before,
            }
        ]


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

    from scripts import issue167_live_timeout_bundle as bundle

    name = "scripts.issue167_live_timeout_cleanup"
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
        archive.writestr("value-low-T1/user.txt", b"public synthetic input")
    (code / "materials.zip").chmod(0o644)
    manifest = {"members": {"stub.py": "a" * 64, "materials.zip": "b" * 64}}
    (code / "manifest.json").write_text(json.dumps(manifest))
    (code / "manifest.json").chmod(0o644)
    material = runtime / "worker/materials/value-low-T1"
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
        with pytest.raises(base.OwnerRejected, match="cleanup_member_unknown"):
            op.finish()
        assert code.exists() and runtime.exists()
    else:
        assert op.finish() == {
            "result": "successful_artifacts_removed",
            "ledger_retained": True,
        }
        assert not code.exists() and not runtime.exists()
    assert "verified" in calls and "unit_absent" in calls


def test_inherited_exit_gate_must_not_absorb_late_counts_before_post_stop() -> None:
    fixture_ops = FakeOperations()
    fixture_ops.exercise_rules()
    initial = json.loads(
        json.dumps(fixture("stall", offset=200, packets=(8, 8, 4, 4, 0, 0))).replace(
            RUN, contract.RUN
        )
    )
    late = copy.deepcopy(initial)
    next(
        r["counter"]
        for r in late["nftables"]
        if r.get("counter", {}).get("name") == "dropped_out"
    )["packets"] += 1
    op: Any = object.__new__(owner.LiveOperations)
    op.case = plan()
    op.filter_plan = fixture_ops.filter_plan
    op.binding = fixture_ops.binding
    op.phase_reference = fixture_ops.phase_references[-1]
    op.current_phase = "stall"
    op.switch_uncertain = False
    op.snapshots = []
    op.duplex_counts = filtering.Counts(8, 8, 4, 4, 0, 0, (512, 512, 256, 256, 0, 0))
    op.contract = types.SimpleNamespace(current_host_context=lambda: HOST)
    op._identity = lambda **kwargs: None
    op._snapshot = lambda: copy.deepcopy(initial)
    op._verify("before_exit")
    op.ready_metadata = {"pid": 1234}
    op.plan = types.SimpleNamespace(cgroup="/synthetic/cgroup")
    op.commands = types.SimpleNamespace(
        unit_state=lambda: types.SimpleNamespace(pid=1234)
    )
    op.phase = types.SimpleNamespace(
        read_cgroup_state=lambda _plan: types.SimpleNamespace(pids={1234})
    )
    op.exit_metadata = {}
    written = []
    op._write = lambda *args: written.append(args)
    op._snapshot = lambda: copy.deepcopy(late)
    with pytest.raises(filtering.DuplexRejected, match="timeout_filter_late_packet"):
        owner.LiveOperations.phase_gate(op, "exit", 7)
    assert written == []
    assert op.duplex_counts.dropped_out == 4
