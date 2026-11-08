"""Independent D1; synthetic/mock only, never root or live services."""

from __future__ import annotations

import ast
import io
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from scripts import issue167_live_exit_probe as probe
from scripts import issue167_live_owner as live
from scripts import issue167_resolver_owner as base


@pytest.mark.parametrize("phase", ["ready", "terminal"])
def test_missing_worker_reference_is_unknown(phase: str) -> None:
    with pytest.raises(probe.ProbeRejected, match="worker_metadata_unknown"):
        probe.validate_worker({}, "a123456789ab", phase)


def test_worker_bool_cannot_impersonate_count() -> None:
    value = {
        "run_id": "a123456789ab",
        "phase": "terminal",
        "count": True,
        "core_zero": True,
        "no_new_privs": True,
        "caps_zero": True,
    }
    with pytest.raises(probe.ProbeRejected, match="worker_metadata_unknown"):
        probe.validate_worker(value, "a123456789ab", "terminal")


class Fake:
    def __init__(self, fail: str = "") -> None:
        self.fail = fail
        self.events: list[str] = []
        self.seam = SimpleNamespace(
            phase_gate=lambda *args: self.step("exit_gate"),
            wait_exit=lambda: self.step("exit_wait"),
            exit_metadata=live.new_exit_metadata(),
        )
        self.ledger: object = None

    def step(self, stage: str) -> None:
        self.events.append(stage)
        if self.fail == stage:
            raise OSError("external-private-text")

    def preflight(self) -> None:
        self.step("preflight")

    def reserve(self) -> None:
        self.step("reserve")

    def install(self) -> None:
        self.step("install")

    def start(self) -> None:
        self.step("start")

    def checkpoint(self, name: str) -> dict[str, object]:
        self.step(name)
        return {"integrity": "complete", "count": 1}

    def restore(self) -> dict[str, object]:
        self.step("restore")
        return {"unit_absent": True, "cgroup_empty": True}

    def remove_artifacts(self) -> dict[str, object]:
        self.step("remove")
        return {"code_runtime_removed": True, "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        self.step("ledger")
        self.ledger = value


def test_runner_drives_one_gate_and_one_worker_then_restores() -> None:
    ops = Fake()
    result = probe.run_probe(ops)
    assert result["result"] == "observed_expected_and_restored"
    assert ops.events == [
        "preflight",
        "reserve",
        "install",
        "start",
        "ready",
        "terminal",
        "exit_gate",
        "exit_wait",
        "restore",
        "remove",
        "ledger",
    ]
    assert (
        result["auth_model_calls"]
        == result["network_operations"]
        == result["nft_operations"]
        == result["database_operations"]
        == 0
    )
    assert result["old_result_changed"] is False


@pytest.mark.parametrize(
    "stage",
    [
        "install",
        "start",
        "ready",
        "terminal",
        "exit_gate",
        "exit_wait",
        "restore",
        "remove",
        "ledger",
    ],
)
def test_failure_stops_without_retry_and_keeps_unknown(stage: str) -> None:
    ops = Fake(stage)
    result = probe.run_probe(ops)
    assert result["result"] == "unknown"
    assert ops.events.count("start") <= 1
    assert ops.events.count("exit_gate") <= 1
    assert ops.events.count("restore") == ops.events.count("ledger") == 1
    if stage in {"restore", "remove"}:
        assert result["restoration_error"] == "restoration_unknown"
    elif stage == "ledger":
        assert result["ledger_error"] == "permanent_result_unknown"
    else:
        assert result["failure_stage"] == stage
    assert "external-private-text" not in json.dumps(result)


@pytest.mark.parametrize("stage", ["preflight", "reserve"])
def test_failure_before_reservation_does_not_mutate_or_claim_ledger(stage: str) -> None:
    ops = Fake(stage)
    result = probe.run_probe(ops)
    assert result["result"] == "unknown" and result["failure_stage"] == stage
    assert "install" not in ops.events and "ledger" not in ops.events


def test_diagnostic_failure_cannot_skip_restoration_or_ledger() -> None:
    class Bad:
        def keys(self) -> None:
            raise RuntimeError("private-diagnostic-text")

    ops = Fake()
    ops.seam.exit_metadata = Bad()
    result = probe.run_probe(ops)
    assert result["result"] == "unknown"
    assert result["diagnostic_error"] == "exit_metadata_unknown"
    assert ops.events[-3:] == ["restore", "remove", "ledger"]


def manager(**updates: str) -> bytes:
    values = {
        "ActiveState": "active",
        "SubState": "exited",
        "Result": "success",
        "ExecMainCode": "1",
        "ExecMainStatus": "0",
        "MainPID": "0",
        "ControlGroup": "/system.slice/synthetic.service",
    }
    values.update(updates)
    return "\n".join(f"{key}={value}" for key, value in values.items()).encode()


def seam(tmp_path: Path, raw: bytes = b"") -> probe.Seam:
    host = SimpleNamespace(
        case=SimpleNamespace(
            unit="synthetic.service", runtime_root=tmp_path, run_id=probe.RUN
        ),
        plan=SimpleNamespace(cgroup="/system.slice/synthetic.service"),
        commands=SimpleNamespace(unit_state=lambda: SimpleNamespace(pid=123)),
        verify_scope=lambda: None,
        systemctl=lambda *args: raw,
    )
    result = probe.Seam(cast(Any, host))
    result.ready_metadata = {"pid": 123}
    cast(Any, result).phase = SimpleNamespace(
        read_cgroup_state=lambda *a, **kw: SimpleNamespace(pids=frozenset({123}))
    )
    return result


def test_uses_real_existing_methods_without_predicate_copy() -> None:
    assert probe.Seam.phase_gate is live.LiveOperations.phase_gate
    assert probe.Seam.wait_exit is live.LiveOperations.wait_exit
    assert probe.Seam._write is base.LiveOperations._write


def test_real_phase_gate_publishes_exact_reference(tmp_path: Path) -> None:
    ops = seam(tmp_path)
    ops.phase_gate("exit", 7)
    assert json.loads((tmp_path / "gate-exit.json").read_bytes()) == {
        "run_id": probe.RUN,
        "sequence": 7,
    }
    assert ops.exit_metadata["gate_checkpoint"] == "write_complete"


def test_real_gate_write_and_publication_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops = seam(tmp_path)
    original = os.fsync

    def fsync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("private-fsync-text")
        original(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    cast(Any, ops).contract = SimpleNamespace(
        read_metadata=lambda path, **kw: json.loads(path.read_bytes())
    )
    with pytest.raises(OSError, match="private-fsync-text"):
        ops.phase_gate("exit", 7)
    assert ops.exit_metadata["gate_checkpoint"] == "write_intent"
    assert ops.exit_metadata["gate_published"] is True
    assert json.loads((tmp_path / "gate-exit.json").read_bytes()) == {
        "run_id": probe.RUN,
        "sequence": 7,
    }


@pytest.mark.parametrize(
    "updates",
    [
        {"ActiveState": "inactive", "SubState": "dead"},
        {"ExecMainStatus": "1"},
        {"ExecMainCode": "0"},
        {"Result": "timeout"},
        {"MainPID": "123"},
        {"ControlGroup": "/system.slice/foreign.service"},
        {"Result": "private-unknown-value"},
        {"MainPID": "+0"},
    ],
)
def test_real_wait_exit_refuses_relaxed_or_unknown_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, updates: dict[str, str]
) -> None:
    ops = seam(tmp_path, manager(**updates))
    cast(Any, ops).phase = SimpleNamespace(
        read_cgroup_state=lambda *a, **kw: SimpleNamespace(pids=frozenset())
    )
    ticks = iter(range(20))
    monkeypatch.setattr(
        "scripts.issue167_live_owner.time.monotonic", lambda: float(next(ticks))
    )
    monkeypatch.setattr("scripts.issue167_live_owner.time.sleep", lambda seconds: None)
    ops.deadline = 3.0
    with pytest.raises(base.OwnerRejected, match="worker_exit_unknown"):
        ops.wait_exit()
    assert ops.exit_metadata["wait_checkpoint"] == "waiting"
    assert "private-unknown-value" not in json.dumps(ops.exit_metadata)


def test_real_wait_exit_accepts_only_strict_loaded_success(tmp_path: Path) -> None:
    ops = seam(tmp_path, manager())
    cast(Any, ops).phase = SimpleNamespace(
        read_cgroup_state=lambda *a, **kw: SimpleNamespace(pids=frozenset())
    )
    ops.wait_exit()
    assert ops.exit_metadata["wait_checkpoint"] == "complete"
    manager_state = ops.exit_metadata["manager"]
    assert isinstance(manager_state, dict) and manager_state["main_pid_zero"] is True


@pytest.mark.parametrize("mode", ["symlink", "unknown", "hardlink", "fifo"])
def test_cleanup_rejects_alias_and_unknown_without_following(
    tmp_path: Path, mode: str
) -> None:
    root = tmp_path / "root"
    root.mkdir(mode=0o755)
    outside = tmp_path / "outside"
    outside.write_bytes(b"public synthetic sentinel")
    item = root / "member"
    if mode == "symlink":
        item.symlink_to(outside)
    elif mode == "unknown":
        item.write_bytes(b"synthetic")
    elif mode == "hardlink":
        os.link(outside, item)
    else:
        os.mkfifo(item)
    info = root.lstat()
    allowed = {} if mode == "unknown" else {"member": (os.getuid(), False)}
    with pytest.raises(probe.ProbeRejected, match=r"cleanup_(member|boundary)_unknown"):
        probe.remove_flat_tree(
            root, allowed, (info.st_dev, info.st_ino), root_uid=os.getuid()
        )
    assert root.exists() and outside.read_bytes() == b"public synthetic sentinel"


def test_cleanup_only_owned_flat_tree_and_nested_control_files(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir(mode=0o755)
    (root / "worker").mkdir(mode=0o700)
    (root / "worker/ready.json").write_bytes(b"public metadata")
    (root / "worker/ready.json").chmod(0o600)
    info = root.lstat()
    probe.remove_flat_tree(
        root,
        {"worker": (os.getuid(), True), "worker/ready.json": (os.getuid(), False)},
        (info.st_dev, info.st_ino),
        root_uid=os.getuid(),
    )
    assert not root.exists()


def test_unit_and_worker_scope_is_no_network_no_application() -> None:
    unit = probe.render_unit(probe.Case(), "/usr/bin/python3.12")
    for line in [
        "Type=exec",
        "RemainAfterExit=yes",
        "User=1000",
        "Group=1000",
        "LimitCORE=0",
        "NoNewPrivileges=yes",
        "Restart=no",
        "RestrictAddressFamilies=none",
        "SystemCallFilter=~@network-io",
    ]:
        assert line in unit.splitlines()
    worker = probe.worker_source(probe.Case()).decode()
    ast.parse(worker)
    assert "socket" not in worker and "subprocess" not in worker
    assert "auth.json" not in worker and "environ" not in worker


def test_second_start_is_forbidden_before_any_command() -> None:
    ops = cast(Any, object.__new__(probe.HostOperations))
    ops.started = True
    ops.systemctl = lambda *args: pytest.fail("unexpected repeated start")
    with pytest.raises(probe.ProbeRejected, match="restart_forbidden"):
        ops.start()


def test_checkpoint_verifies_ancestor_before_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ops = cast(Any, object.__new__(probe.HostOperations))

    def reject() -> None:
        raise probe.ProbeRejected("worker_root_unknown")

    ops.verify_scope = reject
    monkeypatch.setattr(
        "scripts.issue167_resolver_case.read_metadata",
        lambda *a, **kw: pytest.fail("body read before ancestor check"),
    )
    with pytest.raises(probe.ProbeRejected, match="worker_root_unknown"):
        ops.checkpoint("ready")


@pytest.mark.parametrize(
    "updates",
    [
        {"Id": "foreign.service"},
        {"LoadState": "not-found"},
        {"FragmentPath": "/tmp/foreign.service"},
        {"DropInPaths": "/tmp/foreign.conf"},
        {"User": "0"},
        {"Group": "0"},
        {"ControlGroup": "/system.slice/foreign.service"},
    ],
)
def test_unit_scope_checks_before_stop_or_unlink(
    monkeypatch: pytest.MonkeyPatch, updates: dict[str, str]
) -> None:
    ops = cast(Any, object.__new__(probe.HostOperations))
    ops.case = probe.Case()
    ops.plan = ops.case.plan
    ops.files = {"probe.service": b"public unit"}
    state = {
        "Id": ops.case.unit,
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "123",
        "ControlGroup": ops.plan.cgroup,
        "FragmentPath": str(ops.case.unit_path),
        "DropInPaths": "",
        "User": "1000",
        "Group": "1000",
    }
    state.update(updates)
    ops.systemctl = lambda *args: "\n".join(
        f"{key}={value}" for key, value in state.items()
    ).encode()
    monkeypatch.setattr(
        "scripts.issue167_h1_guardian.protected_path", lambda *a, **kw: None
    )
    monkeypatch.setattr(probe, "read_file", lambda *a, **kw: b"public unit")
    monkeypatch.setattr(os.path, "lexists", lambda path: False)
    with pytest.raises(probe.ProbeRejected, match=r"unit_(scope|metadata)_unknown"):
        ops.check_unit()


def install_ops(tmp_path: Path) -> Any:
    ops = cast(Any, object.__new__(probe.HostOperations))
    unit_parent = tmp_path / "systemd"
    unit_parent.mkdir()
    runtime = tmp_path / "runtime"
    ops.case = SimpleNamespace(
        code_root=tmp_path / "code",
        runtime_root=runtime,
        worker_root=runtime / "worker",
        unit_path=unit_parent / "synthetic.service",
        unit="synthetic.service",
    )
    ops.files = {"probe.service": b"public synthetic unit", "worker.py": b"# synthetic"}
    ops.created = {}
    ops.unit_created = False
    ops.systemctl = lambda *args: pytest.fail("unexpected host command")
    return ops


def test_unprotected_unit_parent_is_rejected_before_file_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops = install_ops(tmp_path)

    def protected(path: Path, **kwargs: object) -> None:
        if path == ops.case.unit_path.parent:
            raise probe.ProbeRejected("unit_parent_unknown")

    monkeypatch.setattr("scripts.issue167_h1_guardian.protected_path", protected)
    monkeypatch.setattr(os, "chown", lambda *args: None)
    with pytest.raises(probe.ProbeRejected, match="unit_parent_unknown"):
        ops.install()
    assert not ops.case.unit_path.exists() and not ops.unit_created


def test_partial_unit_publication_never_claims_restore_or_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = install_ops(tmp_path)
    original = probe.write_new

    def write(path: Path, raw: bytes, mode: int = 0o644) -> None:
        original(path, raw, mode)
        if path == host.case.unit_path:
            raise OSError("synthetic fsync failure after unit publication")

    def check_unit(*, absent: bool = False) -> dict[str, str]:
        assert absent is True
        if host.case.unit_path.exists():
            raise probe.ProbeRejected("unit_not_absent")
        return {}

    host.check_unit = check_unit
    monkeypatch.setattr(probe, "write_new", write)
    monkeypatch.setattr(
        "scripts.issue167_h1_guardian.protected_path", lambda *a, **kw: None
    )
    monkeypatch.setattr(os, "chown", lambda *args: None)
    ops = Fake()
    cast(Any, ops).install = host.install
    cast(Any, ops).restore = host.restore
    result = probe.run_probe(ops)
    assert result["result"] == "unknown"
    assert result["failure_stage"] == "install"
    assert result["restoration_error"] == "restoration_unknown"
    assert result["artifacts"] is None
    assert host.case.unit_path.exists() and host.case.code_root.exists()
    assert "start" not in ops.events and "remove" not in ops.events


def test_permanent_reservation_is_exclusive_and_never_refunded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops = cast(Any, object.__new__(probe.HostOperations))
    ops.case = SimpleNamespace(ledger=tmp_path / "permanent" / "runs" / "once.json")
    monkeypatch.setattr(
        "scripts.issue167_h1_guardian.protected_path", lambda *a, **kw: None
    )
    ops.reserve()
    try:
        before = ops.case.ledger.read_bytes()
        with pytest.raises(FileExistsError):
            ops.reserve()
        assert ops.case.ledger.read_bytes() == before
        assert json.loads(before) == {"run_id": probe.RUN, "state": "reserved_unknown"}
    finally:
        ops.anchor.close()


def test_sealed_literal_loads_real_modules_without_invoking_root_main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    files = {
        name + ".py": (workspace / "scripts" / (name + ".py")).read_bytes()
        for name in probe.MODULE_ORDER
    }
    files["worker.py"] = probe.worker_source(probe.Case())
    files["probe.service"] = probe.render_unit(
        probe.Case(), "/usr/bin/python3"
    ).encode()
    config = {"members": {name: probe.digest(raw) for name, raw in files.items()}}
    driver = probe.render_driver(config, files, "a" * 64)
    literal = driver.split("<<'ROOT_LITERAL' > \"$owner_output\"\n", 1)[1].split(
        "\nROOT_LITERAL", 1
    )[0]
    tree = ast.parse(literal)

    class RemoveOnlyMain(ast.NodeTransformer):
        changed = 0

        def visit_Assign(self, node: ast.Assign) -> Any:
            if (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "root_main"
            ):
                self.changed += 1
                return ast.parse(
                    "assert (module.Seam.phase_gate is "
                    "module.live.LiveOperations.phase_gate)\n"
                    "assert (module.Seam.wait_exit is "
                    "module.live.LiveOperations.wait_exit)\n"
                    "assert module.Seam._write is module.base.LiveOperations._write\n"
                    "status=0\n"
                ).body
            return node

    transform = RemoveOnlyMain()
    transformed = transform.visit(tree)
    assert transform.changed == 1
    result = subprocess.run(
        ["/usr/bin/python3", "-I", "-S", "-B", "-"],
        input=ast.unparse(ast.fix_missing_locations(transformed)).encode(),
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == b""
    syntax = subprocess.run(
        ["bash", "-n"],
        input=driver.encode(),
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert syntax.returncode == 0 and syntax.stdout == syntax.stderr == b""
    assert driver.count("/usr/bin/sudo ") == 1 and "sudo -S" not in driver


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"garbage\n",
        b"1 0 0:1 / relative rw - tmpfs tmpfs rw\n",
        b"1 0 0:1 / / rw ? tmpfs tmpfs rw\n",
        b"1 0 nope / / rw - tmpfs tmpfs rw\n",
        b"1 0 0:1 / / rw - tmpfs tmpfs\n",
        b"1 0 0:1 / / rw - tmpfs tmpfs \xff\n",
    ],
)
def test_missing_or_malformed_mount_reference_blocks_before_unlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
) -> None:
    root = tmp_path / "root"
    root.mkdir(mode=0o755)
    (root / "member").write_bytes(b"public synthetic")
    (root / "member").chmod(0o600)
    before = root.lstat()
    original = Path.open

    def read(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == Path("/proc/self/mountinfo"):
            return io.BytesIO(raw)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", read)
    with pytest.raises(probe.ProbeRejected, match="mount_metadata_unknown"):
        probe.remove_flat_tree(
            root,
            {"member": (os.getuid(), False)},
            (before.st_dev, before.st_ino),
            root_uid=os.getuid(),
        )
    assert (root / "member").exists()


def test_mount_reference_decodes_kernel_escapes_and_rejects_same_device_bind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert probe.mount_points(b"1 0 0:1 / /tmp/A\\040B rw - tmpfs tmpfs rw\n") == {
        Path("/tmp/A B")
    }
    root = tmp_path / "root"
    root.mkdir(mode=0o755)
    before = root.lstat()
    raw = f"1 0 0:1 / {root} rw - tmpfs tmpfs rw\n".encode()
    original = Path.open

    def read(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == Path("/proc/self/mountinfo"):
            return io.BytesIO(raw)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", read)
    with pytest.raises(probe.ProbeRejected, match="artifact_mount_unknown"):
        probe.remove_flat_tree(
            root, {}, (before.st_dev, before.st_ino), root_uid=os.getuid()
        )
    assert root.exists()
