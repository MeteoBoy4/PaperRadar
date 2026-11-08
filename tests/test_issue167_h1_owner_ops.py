"""Independent D1 owner-helper tests; temp files/mock commands only."""

import json
from pathlib import Path
from typing import ClassVar, cast

import pytest

from scripts import issue167_h1_owner_ops as owner
from scripts.issue167_h1_guardian import Commands, GuardianRejected
from scripts.issue167_h1_phase import Plan
from tests.test_issue167_h1_phase import nft_fixture
from tests.test_issue167_h1_phase import plan as sample_plan


class TestPlan(Plan):
    __test__ = False
    fixture_root: Path

    @property
    def install_root(self) -> Path:
        return self.fixture_root / "code"

    @property
    def runtime_root(self) -> Path:
        return self.fixture_root / "runtime"


class FakeCommands:
    tools: ClassVar[dict[str, Path]] = {
        "systemctl": Path("/usr/bin/systemctl"),
        "nft": Path("/usr/sbin/nft"),
    }

    def __init__(self, plan: Plan, *, present: bool = False) -> None:
        self.plan = plan
        self.present = present
        self.events: list[str] = []

    def _run(self, argv: tuple[str, ...], data: bytes = b"") -> bytes:
        if "stop" in argv:
            self.events.append("stop:" + argv[-1])
        elif "daemon-reload" in argv:
            self.events.append("reload")
        elif argv[-2:] == ("list", "tables"):
            rows = (
                [{"table": {"family": "inet", "name": self.plan.table}}]
                if self.present
                else []
            )
            return json.dumps({"nftables": rows}).encode()
        elif "table" in argv:
            return json.dumps(nft_fixture("b")).encode()
        return b""

    def delete(self) -> None:
        self.events.append("delete-table")
        self.present = False


def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestPlan:
    base = sample_plan()
    plan = TestPlan(base.run_id, base.uid, base.gid)
    object.__setattr__(plan, "fixture_root", tmp_path)
    plan.install_root.mkdir()
    units = tmp_path / "units"
    units.mkdir()
    monkeypatch.setattr(owner, "UNIT_ROOT", units)
    monkeypatch.setattr(owner, "UNIT_SEARCH", (units,))
    monkeypatch.setattr(owner, "protected_path", lambda *args, **kwargs: None)
    for unit in (plan.unit, plan.guardian_unit):
        (units / unit).write_text("expected-unit")
        (plan.install_root / unit).write_text("expected-unit")
    monkeypatch.setattr(
        owner,
        "manager_scope",
        lambda _commands, unit: {
            "LoadState": "loaded",
            "FragmentPath": str(units / unit),
            "DropInPaths": "",
        },
    )
    return plan


def test_restore_parses_actual_json_bytes_and_stops_before_table_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = fixture(tmp_path, monkeypatch)
    commands = FakeCommands(plan, present=True)
    monkeypatch.setattr(
        owner, "require_empty", lambda _plan: commands.events.append("empty")
    )
    result = owner.restore(plan, cast(Commands, commands))
    assert result["result"] == "host_policy_restored"
    assert commands.events[:4] == [
        "stop:" + plan.unit,
        "stop:" + plan.guardian_unit,
        "empty",
        "delete-table",
    ]
    assert not (owner.UNIT_ROOT / plan.unit).exists()


def test_changed_unit_is_refused_before_any_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = fixture(tmp_path, monkeypatch)
    commands = FakeCommands(plan)
    (owner.UNIT_ROOT / plan.unit).write_text("foreign-unit")
    with pytest.raises(GuardianRejected, match=r"^installed_unit_changed$"):
        owner.restore(plan, cast(Commands, commands))
    assert commands.events == []


def test_dropin_and_manager_path_drift_are_refused_before_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = fixture(tmp_path, monkeypatch)
    commands = FakeCommands(plan)
    (owner.UNIT_ROOT / (plan.guardian_unit + ".d")).mkdir()
    with pytest.raises(GuardianRejected, match=r"^unit_dropin_changed$"):
        owner.restore(plan, cast(Commands, commands))
    assert commands.events == []


def test_nonempty_cgroup_never_deletes_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = fixture(tmp_path, monkeypatch)
    commands = FakeCommands(plan, present=True)

    def occupied(_plan: Plan) -> None:
        raise GuardianRejected("cgroup_not_empty")

    monkeypatch.setattr(owner, "require_empty", occupied)
    with pytest.raises(GuardianRejected, match=r"^cgroup_not_empty$"):
        owner.restore(plan, cast(Commands, commands))
    assert "delete-table" not in commands.events
    assert (owner.UNIT_ROOT / plan.unit).exists()


def test_finish_keeps_artifacts_when_ledger_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = fixture(tmp_path, monkeypatch)
    plan.runtime_root.mkdir()
    commands = FakeCommands(plan)
    monkeypatch.setattr(owner, "check_units", lambda *args, **kwargs: set())
    monkeypatch.setattr(owner, "require_empty", lambda _plan: None)
    monkeypatch.setattr(owner, "LEDGER_ROOT", tmp_path / "missing-ledger")
    value = {
        "scope": "h1_synthetic_local_only",
        "run_id": plan.run_id,
        "result": "observed_expected",
        "cleanup_complete": True,
        "table_may_remain": False,
    }

    def guarded_read(path: Path, **kwargs: object) -> object:
        if path.name == "guardian-result.json":
            return value
        raise FileNotFoundError

    monkeypatch.setattr(owner, "read_json", guarded_read)
    with pytest.raises(FileNotFoundError):
        owner.remove_successful_artifacts(plan, cast(Commands, commands))
    assert plan.install_root.is_dir() and plan.runtime_root.is_dir()


def test_mountinfo_includes_same_device_bind_mounts() -> None:
    points = owner.mountpoints("27 20 0:1 / /run/probe/worker rw - tmpfs tmpfs rw\n")
    assert points == (Path("/run/probe/worker"),)


def test_inventory_duplicate_key_is_unknown_not_last_value() -> None:
    plan = sample_plan()
    raw = (
        '{"nftables":[{"table":{"family":"inet","name":"foreign",'
        '"name":"' + plan.table + '"}}]}'
    ).encode()
    with pytest.raises(GuardianRejected, match=r"^table_inventory_unknown$"):
        owner.table_present(plan, raw)


def test_main_refuses_plan_for_a_different_installed_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import resource
    import sys

    monkeypatch.setattr(owner, "_root", tmp_path, raising=False)
    monkeypatch.setattr(resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(owner, "bootstrap", lambda _path: {})
    monkeypatch.setattr(owner, "load_plan", lambda _path: sample_plan())
    monkeypatch.setattr(sys, "argv", ["owner.py", "install"])
    with pytest.raises(GuardianRejected, match=r"^plan_root_mismatch$"):
        owner.main()


def test_finish_refuses_same_filesystem_bind_mount_before_any_tree_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = fixture(tmp_path, monkeypatch)
    plan.runtime_root.mkdir()
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    (ledger_root / f"issue167-{plan.run_id}.json").write_text("retained")
    monkeypatch.setattr(owner, "LEDGER_ROOT", ledger_root)
    monkeypatch.setattr(owner, "require_empty", lambda _plan: None)
    monkeypatch.setattr(owner, "check_units", lambda *args, **kwargs: set())
    value = {
        "scope": "h1_synthetic_local_only",
        "run_id": plan.run_id,
        "result": "observed_expected",
        "cleanup_complete": True,
        "table_may_remain": False,
    }
    monkeypatch.setattr(owner, "read_json", lambda *args, **kwargs: value)
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda _path: f"27 20 0:1 / {plan.runtime_root}/worker rw - tmpfs tmpfs rw\n",
    )
    with pytest.raises(GuardianRejected, match=r"^artifact_mount_unknown$"):
        owner.remove_successful_artifacts(plan, cast(Commands, FakeCommands(plan)))
    assert plan.install_root.is_dir() and plan.runtime_root.is_dir()
