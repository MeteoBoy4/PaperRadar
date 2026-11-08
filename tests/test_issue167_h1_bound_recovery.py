"""Independent D1: live identity capture and post-stop cleanup, mocks only."""

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from scripts import issue167_h1_guardian as guard
from scripts import issue167_h1_owner_ops as owner
from scripts.issue167_h1_phase import CgroupState, PhaseRejected, Plan, verify_nft_state
from tests.test_issue167_h1_owner_ops import fixture as owner_fixture
from tests.test_issue167_h1_phase import nft_fixture
from tests.test_issue167_h1_phase import plan as sample_plan


def test_live_create_publishes_binding_before_any_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = sample_plan()
    commands = guard.Commands(plan, {})
    events: list[str] = []
    monkeypatch.setattr(commands, "create", lambda: events.append("create"))
    monkeypatch.setattr(commands, "counters", lambda _phase: (4, 7))
    monkeypatch.setattr(
        commands, "snapshot", lambda: nft_fixture("deny"), raising=False
    )

    def identity(_plan: Plan) -> tuple[int, int]:
        events.append("identity")
        return 55, 844648

    monkeypatch.setattr(guard, "read_cgroup_identity", identity, raising=False)
    operations = guard.LiveOperations(plan, commands)
    published: list[tuple[Path, object, int]] = []
    monkeypatch.setattr(
        operations,
        "_write",
        lambda path, value, mode=0o644: published.append((path, value, mode)),
    )
    operations.create()
    assert events == ["identity", "create", "identity"]
    assert len(published) == 1
    assert published[0][0] == plan.runtime_root / "table-binding.json"
    assert published[0][2] == 0o600
    value = cast(dict[str, object], published[0][1])
    assert value["cgroup_inode"] == 844648


def test_bound_cleanup_accepts_only_saved_identity_after_mocked_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = sample_plan()
    commands = guard.Commands(plan, {})
    payload = nft_fixture("deny")
    events: list[str] = []
    monkeypatch.setattr(commands, "create", lambda: None)
    monkeypatch.setattr(
        commands, "snapshot", lambda: copy.deepcopy(payload), raising=False
    )
    monkeypatch.setattr(
        commands, "_run", lambda argv, data=b"": json.dumps(payload).encode()
    )
    commands.tools = {"nft": Path("/usr/sbin/nft")}
    monkeypatch.setattr(
        guard, "read_cgroup_identity", lambda _plan: (55, 844648), raising=False
    )
    operations = guard.LiveOperations(plan, commands)
    monkeypatch.setattr(operations, "_write", lambda *args, **kwargs: None)
    operations.create()

    def stop() -> None:
        events.append("stop")
        rows = cast(list[dict[str, object]], payload["nftables"])
        scope = cast(dict[str, object], rows[6]["rule"])
        expressions = cast(list[dict[str, object]], scope["expr"])
        match = cast(dict[str, object], expressions[0]["match"])
        match["right"] = "844648"

    monkeypatch.setattr(commands, "stop", stop)
    monkeypatch.setattr(commands, "delete", lambda: events.append("delete"))
    monkeypatch.setattr(
        guard,
        "read_cgroup_state",
        lambda *args, **kwargs: CgroupState(False, frozenset(), 0),
    )
    assert operations.cleanup() is True
    assert events == ["stop", "delete"]


def table_with_right(right: object, phase: str = "a") -> dict[str, object]:
    payload = nft_fixture(phase)
    rows = cast(list[dict[str, object]], payload["nftables"])
    rule = cast(dict[str, object], rows[6]["rule"])
    expressions = cast(list[dict[str, object]], rule["expr"])
    cast(dict[str, object], expressions[0]["match"])["right"] = right
    return payload


def binding(plan: Plan | None = None) -> dict[str, object]:
    return guard.make_table_binding(
        plan or sample_plan(), nft_fixture("deny"), (55, 844648)
    )


@pytest.mark.parametrize("phase", ["deny", "a", "b"])
@pytest.mark.parametrize("right", [844648, "844648"])
def test_only_independently_bound_numeric_identity_can_be_verified(
    phase: str,
    right: object,
) -> None:
    payload = table_with_right(right, phase)
    with pytest.raises(PhaseRejected, match=r"^nft_state_unknown$"):
        verify_nft_state(sample_plan(), phase, payload)
    assert guard.verify_bound_nft_state(sample_plan(), phase, payload, binding()) == (
        4,
        7,
    )
    # The original evidence is not mutated for the structural verifier.
    assert payload == table_with_right(right, phase)


@pytest.mark.parametrize(
    "right", [844649, "844649", True, 844648.0, "0844648", "other.service"]
)
def test_binding_does_not_normalize_foreign_or_coerced_identity(right: object) -> None:
    with pytest.raises(guard.GuardianRejected, match=r"^table_binding_unknown$"):
        guard.verify_bound_nft_state(
            sample_plan(), "a", table_with_right(right), binding()
        )


@pytest.mark.parametrize("row_index", [1, 2, 3, 4, 5, 6])
def test_recreated_table_scope_chains_or_counters_are_not_equivalent(
    row_index: int,
) -> None:
    payload = table_with_right("844648")
    rows = cast(list[dict[str, object]], payload["nftables"])
    item = cast(dict[str, object], next(iter(rows[row_index].values())))
    item["handle"] = 999
    with pytest.raises(guard.GuardianRejected, match=r"^table_binding_unknown$"):
        guard.verify_bound_nft_state(sample_plan(), "a", payload, binding())


def test_bound_identity_does_not_weaken_full_phase_rules() -> None:
    payload = table_with_right("844648")
    raw = json.dumps(payload).replace('"right": 38167', '"right": 38169')
    with pytest.raises(PhaseRejected, match=r"^nft_state_unknown$"):
        guard.verify_bound_nft_state(sample_plan(), "a", json.loads(raw), binding())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "foreign"),
        ("plan_sha256", "0" * 64),
        ("host_context", {}),
        ("cgroup", "/system.slice/other.service"),
        ("cgroup_inode", True),
        ("cgroup_inode", 2**64),
        ("cgroup_device", -1),
        ("schema", True),
        ("extra", "unreviewed"),
        ("handles", {"table": 10}),
    ],
)
def test_binding_drift_is_unknown(field: str, value: object) -> None:
    saved = binding()
    saved[field] = value
    with pytest.raises(guard.GuardianRejected, match=r"^table_binding_unknown$"):
        guard.verify_bound_nft_state(
            sample_plan(), "a", table_with_right("844648"), saved
        )


def test_creation_race_never_publishes_a_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = sample_plan()
    commands = guard.Commands(plan, {})
    monkeypatch.setattr(commands, "create", lambda: None)
    monkeypatch.setattr(commands, "snapshot", lambda: nft_fixture("deny"))
    identities = iter([(55, 844648), (55, 844649)])
    monkeypatch.setattr(guard, "read_cgroup_identity", lambda _plan: next(identities))
    operations = guard.LiveOperations(plan, commands)
    published: list[object] = []
    monkeypatch.setattr(
        operations, "_write", lambda *args, **kwargs: published.append(args)
    )
    with pytest.raises(guard.GuardianRejected, match=r"^cgroup_identity_unknown$"):
        operations.create()
    assert not published
    assert operations.table_binding is None


def test_numeric_rule_cannot_be_its_own_binding_source() -> None:
    with pytest.raises(PhaseRejected, match=r"^nft_state_unknown$"):
        guard.make_table_binding(
            sample_plan(), table_with_right("844648", "deny"), (55, 844648)
        )


def test_owner_restore_uses_protected_saved_binding_after_stopping_both_groups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = owner_fixture(tmp_path, monkeypatch)
    saved = binding(plan)
    commands = guard.Commands(
        plan, {"nft": Path("/usr/sbin/nft"), "systemctl": Path("/usr/bin/systemctl")}
    )
    events: list[str] = []

    def run(argv: tuple[str, ...], data: bytes = b"") -> bytes:
        assert not data
        if "stop" in argv:
            events.append("stop:" + argv[-1])
        elif argv[-2:] == ("list", "tables"):
            return json.dumps(
                {"nftables": [{"table": {"family": "inet", "name": plan.table}}]}
            ).encode()
        elif "table" in argv:
            return json.dumps(table_with_right("844648", "b")).encode()
        elif "daemon-reload" in argv:
            events.append("reload")
        return b""

    monkeypatch.setattr(commands, "_run", run)
    monkeypatch.setattr(commands, "delete", lambda: events.append("delete"))
    monkeypatch.setattr(owner, "require_empty", lambda _plan: events.append("empty"))
    monkeypatch.setattr(owner, "read_table_binding", lambda _plan: saved)
    result = owner.restore(plan, commands)
    assert result["result"] == "host_policy_restored"
    assert events == [
        "stop:" + plan.unit,
        "stop:" + plan.guardian_unit,
        "empty",
        "delete",
        "reload",
    ]
    assert not (owner.UNIT_ROOT / plan.unit).exists()


def test_missing_binding_keeps_numeric_table_and_units(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = owner_fixture(tmp_path, monkeypatch)
    commands = guard.Commands(
        plan, {"nft": Path("/usr/sbin/nft"), "systemctl": Path("/usr/bin/systemctl")}
    )
    events: list[str] = []

    def run(argv: tuple[str, ...], data: bytes = b"") -> bytes:
        if argv[-2:] == ("list", "tables"):
            return json.dumps(
                {"nftables": [{"table": {"family": "inet", "name": plan.table}}]}
            ).encode()
        if "table" in argv:
            return json.dumps(table_with_right("844648")).encode()
        return b""

    def missing(_plan: Plan) -> dict[str, object]:
        raise FileNotFoundError

    monkeypatch.setattr(commands, "_run", run)
    monkeypatch.setattr(commands, "delete", lambda: events.append("delete"))
    monkeypatch.setattr(owner, "require_empty", lambda _plan: None)
    monkeypatch.setattr(owner, "read_table_binding", missing)
    with pytest.raises(guard.GuardianRejected, match=r"^table_ownership_unknown$"):
        owner.restore(plan, commands)
    assert not events
    assert (owner.UNIT_ROOT / plan.unit).exists()


@pytest.mark.parametrize("mode", [0o644, 0o666])
def test_binding_reader_requires_private_metadata_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
) -> None:
    plan = owner_fixture(tmp_path, monkeypatch)
    plan.runtime_root.mkdir()
    path = plan.runtime_root / "table-binding.json"
    path.write_text(json.dumps(binding(plan)))
    path.chmod(mode)
    monkeypatch.setattr(guard, "protected_path", lambda *_args, **_kwargs: None)
    reads: list[object] = []
    monkeypatch.setattr(guard, "read_json", lambda *args, **kwargs: reads.append(args))
    with pytest.raises(guard.GuardianRejected, match=r"^table_binding_unknown$"):
        guard.read_table_binding(plan)
    assert not reads


@pytest.mark.parametrize("reason", ["cgroup_identity_unknown", "table_binding_unknown"])
def test_binding_failure_reasons_remain_controlled(reason: str) -> None:
    assert guard.failure_reason(guard.GuardianRejected(reason)) == reason
