"""Independent D1: strict cleanup diagnostics with mocked commands only."""

import json
from pathlib import Path
from typing import cast

import pytest

from scripts import issue167_h1_guardian as guard
from scripts import issue167_h1_owner_ops as owner
from scripts.issue167_h1_phase import CgroupState, PhaseRejected, verify_nft_state
from tests.test_issue167_h1_owner_ops import fixture as owner_fixture
from tests.test_issue167_h1_phase import nft_fixture
from tests.test_issue167_h1_phase import plan as sample_plan


def scope_payload(right: object, phase: str = "a") -> dict[str, object]:
    payload = nft_fixture(phase)
    rows = cast(list[dict[str, object]], payload["nftables"])
    for row in rows:
        if "rule" not in row:
            continue
        rule = cast(dict[str, object], row["rule"])
        if rule["chain"] != "out":
            continue
        expressions = cast(list[dict[str, object]], rule["expr"])
        match = cast(dict[str, object], expressions[0]["match"])
        match["right"] = right
    return payload


@pytest.mark.parametrize("phase", ["deny", "a", "b"])
@pytest.mark.parametrize("right", [123456, "123456", "system.slice/other.service"])
def test_unbound_scope_identity_stays_unknown(phase: str, right: object) -> None:
    """A number alone is not evidence that the original cgroup was matched."""
    with pytest.raises(PhaseRejected, match=r"^nft_state_unknown$"):
        verify_nft_state(sample_plan(), phase, scope_payload(right, phase))


def test_path_to_numeric_after_mocked_stop_keeps_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model the possible formatting change; assert no unsafe deletion follows."""
    plan = sample_plan()
    commands = guard.Commands(plan, {"nft": Path("/usr/sbin/nft")})
    payload = nft_fixture("a")
    events: list[str] = []

    def run(_argv: tuple[str, ...], data: bytes = b"") -> bytes:
        assert not data
        events.append("list")
        return json.dumps(payload).encode()

    def stop() -> None:
        nonlocal payload
        events.append("stop")
        payload = scope_payload(123456)

    def empty(*_args: object, **_kwargs: object) -> CgroupState:
        events.append("empty")
        return CgroupState(False, frozenset(), 0)

    monkeypatch.setattr(commands, "_run", run)
    monkeypatch.setattr(commands, "stop", stop)
    monkeypatch.setattr(commands, "delete", lambda: events.append("delete"))
    monkeypatch.setattr(guard, "read_cgroup_state", empty)
    assert commands.counters("a") == (4, 7)
    ops = guard.LiveOperations(plan, commands)
    ops.table_created = True
    ops.current_phase = "a"
    assert ops.cleanup() is False
    assert ops.table_created is True
    assert events == ["list", "stop", "empty", "list"]


def test_restore_refuses_numeric_scope_even_when_both_groups_are_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty groups do not prove the numeric rule belongs to this run."""
    plan = owner_fixture(tmp_path, monkeypatch)
    commands = guard.Commands(
        plan, {"nft": Path("/usr/sbin/nft"), "systemctl": Path("/usr/bin/systemctl")}
    )
    events: list[str] = []

    def run(argv: tuple[str, ...], data: bytes = b"") -> bytes:
        assert not data
        if "stop" in argv:
            events.append("stop:" + argv[-1])
            return b""
        if argv[-2:] == ("list", "tables"):
            return json.dumps(
                {
                    "nftables": [
                        {
                            "table": {
                                "family": "inet",
                                "name": plan.table,
                            }
                        }
                    ]
                }
            ).encode()
        assert argv[-4:] == ("list", "table", "inet", plan.table)
        return json.dumps(scope_payload(123456)).encode()

    monkeypatch.setattr(commands, "_run", run)
    monkeypatch.setattr(commands, "delete", lambda: events.append("delete"))
    monkeypatch.setattr(owner, "require_empty", lambda _plan: events.append("empty"))
    with pytest.raises(guard.GuardianRejected, match=r"^table_ownership_unknown$"):
        owner.restore(plan, commands)
    assert events == ["stop:" + plan.unit, "stop:" + plan.guardian_unit, "empty"]
    assert (owner.UNIT_ROOT / plan.unit).exists()
    assert (owner.UNIT_ROOT / plan.guardian_unit).exists()
