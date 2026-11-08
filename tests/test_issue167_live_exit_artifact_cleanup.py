"""Independent D1; all deletion tests use temporary synthetic trees only."""

from __future__ import annotations

import io
import json
import os
import resource
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import issue167_live_artifact_cleanup as boundary
from scripts import issue167_live_exit_artifact_cleanup as cleanup


def record(root: str = "/", point: str = "/outside", fs: str = "nsfs") -> bytes:
    return f"71 62 0:4 {root} {point} rw - {fs} nsfs rw\n".encode()


def test_observed_nsfs_mnt_root_is_not_a_mountpoint() -> None:
    assert cleanup.mount_points(record("mnt:[4026531840]")) == {Path("/outside")}


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\n",
        b"bad\n",
        b"\xff",
        record("unobserved:[1]"),
        record("net:[1]"),
        record("mnt:[0]"),
        record("mnt:[01]"),
        record("mnt:[1]", fs="tmpfs"),
        record("mnt:[1]", point="relative"),
        record("garbage"),
        record("/bad\x00root"),
        record("/", point="/bad\x00point"),
        record("/", point="/bad\\777point"),
        record("/", point="/bad/../point"),
        record("/", point="/bad/./point"),
        record("/bad/./root"),
        record("/bad/../root"),
        record().replace(b"71 62", "٧١ 62".encode()),
        record().replace(b"0:4", "0:٤".encode()),
        record("//bad-root"),
        record("/", point="//bad-point"),
    ],
)
def test_missing_or_unknown_mount_reference_blocks(raw: bytes) -> None:
    with pytest.raises(boundary.CleanupRejected, match="mount_metadata_unknown"):
        cleanup.mount_points(raw)


def test_mountpoint_escapes_are_decoded_before_boundary_check() -> None:
    assert cleanup.mount_points(record("/", "/outside\\040space")) == {
        Path("/outside space")
    }


@pytest.mark.parametrize(
    "error,expected",
    [
        (boundary.CleanupRejected("exit_gate_changed"), "exit_gate_changed"),
        (
            boundary.CleanupRejected("private unexpected value"),
            "cleanup_operation_unknown",
        ),
        (OSError("private unexpected value"), "cleanup_operation_unknown"),
    ],
)
def test_failure_reasons_are_closed(error: BaseException, expected: str) -> None:
    assert cleanup.closed_reason(error) == expected


def test_root_main_diagnostic_never_calls_exception_string(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class BadString(boundary.CleanupRejected):
        def __str__(self) -> str:
            raise RuntimeError("private unexpected text")

    def failed() -> int:
        raise BadString("private unexpected value")

    monkeypatch.setattr(os, "geteuid", failed)
    assert cleanup.main({}, b"") == 1
    output = json.loads(capsys.readouterr().out)
    assert output["cleanup_result"] == "unknown"
    assert output["failure_reason"] == "cleanup_operation_unknown"
    assert output["failure_stage"] == "initial"


def inventory(root: Path) -> dict[str, list[int]]:
    return {
        "": boundary.identity(root.lstat()),
        **{
            str(p.relative_to(root)): boundary.identity(p.lstat())
            for p in root.rglob("*")
        },
    }


def trees(tmp_path: Path) -> tuple[boundary.Tree, boundary.Tree]:
    runtime = tmp_path / "runtime"
    code = tmp_path / "code"
    runtime.mkdir(mode=0o755)
    code.mkdir(mode=0o755)
    worker = runtime / "worker"
    worker.mkdir(mode=0o700)
    for p in (
        worker / "ready.json",
        worker / "terminal.json",
        runtime / "gate-exit.json",
    ):
        p.write_bytes(b"public metadata\n")
        p.chmod(0o600)
    for number in range(12):
        p = code / f"source-{number}.py"
        p.write_bytes(b"public synthetic source\n")
        p.chmod(0o644)
    return (
        boundary.Tree(runtime, inventory(runtime), os.getuid(), os.getuid()),
        boundary.Tree(code, inventory(code), os.getuid()),
    )


def test_real_two_tree_chain_removes_eighteen_nodes_and_retains_ledger(
    tmp_path: Path,
) -> None:
    pair = trees(tmp_path)
    ledger = tmp_path / "ledger"
    ledger.write_bytes(b'{"result":"unknown"}\n')
    before = ledger.read_bytes()
    calls = []

    def verify() -> None:
        assert ledger.read_bytes() == before
        calls.append("verify")
        boundary.check_mounts(
            tuple(t.path for t in pair), cleanup.mount_points(record("mnt:[7]"))
        )

    def check_records() -> None:
        assert all(t.fds for t in pair)
        assert (
            pair[0].read_metadata("worker/ready.json", uid=os.getuid(), mode=0o600)
            == b"public metadata\n"
        )
        calls.append("records")

    value = cleanup.perform(pair, verify, check_records, {})
    assert calls == ["verify", "verify", "records", "verify"]
    assert value["scope"] == cleanup.SCOPE
    assert value["run_id"] == cleanup.RUN
    assert value["removed_members_including_roots"] == 18
    assert value["original_experiment_result"] == "unknown"
    assert value["original_ledger_unchanged"] is True
    assert value["synthetic_worker_reexecs"] == value["network_operations"] == 0
    assert ledger.read_bytes() == before
    assert not any(t.path.exists() for t in pair)
    assert all(not t.fds for t in pair)


@pytest.mark.parametrize(
    "failure", ["first_mount", "recheck", "record", "changed_tree"]
)
def test_predelete_failure_keeps_both_trees(tmp_path: Path, failure: str) -> None:
    pair = trees(tmp_path)
    checks = 0

    def verify() -> None:
        nonlocal checks
        checks += 1
        if failure == "first_mount" or (failure == "recheck" and checks == 2):
            raise boundary.CleanupRejected("mount_metadata_unknown")

    def records() -> None:
        if failure == "record":
            raise boundary.CleanupRejected("exit_gate_changed")
        if failure == "changed_tree":
            (pair[0].path / "worker/ready.json").write_bytes(b"changed")

    reason = {
        "first_mount": "mount_metadata_unknown",
        "recheck": "mount_metadata_unknown",
        "record": "exit_gate_changed",
        "changed_tree": "tree_changed",
    }[failure]
    with pytest.raises(boundary.CleanupRejected, match=reason):
        cleanup.perform(pair, verify, records, {})
    assert all(t.path.is_dir() for t in pair)
    assert (pair[1].path / "source-0.py").is_file()
    assert all(not t.fds for t in pair)


def test_nsfs_mnt_target_inside_tree_still_blocks_before_unlink(tmp_path: Path) -> None:
    pair = trees(tmp_path)

    def verify() -> None:
        boundary.check_mounts(
            tuple(t.path for t in pair),
            cleanup.mount_points(record("mnt:[7]", str(pair[0].path / "worker"))),
        )

    with pytest.raises(boundary.CleanupRejected, match="artifact_mount_unknown"):
        cleanup.perform(pair, verify, lambda: None, {})
    assert (pair[0].path / "worker/ready.json").exists()
    assert (pair[1].path / "source-0.py").exists()


def test_double_slash_mount_target_is_unknown_before_unlink(tmp_path: Path) -> None:
    pair = trees(tmp_path)

    def verify() -> None:
        target = "/" + str(pair[0].path / "worker")
        boundary.check_mounts(
            tuple(t.path for t in pair), cleanup.mount_points(record("mnt:[7]", target))
        )

    with pytest.raises(boundary.CleanupRejected, match="mount_metadata_unknown"):
        cleanup.perform(pair, verify, lambda: None, {})
    assert (pair[0].path / "worker/ready.json").exists()
    assert (pair[1].path / "source-0.py").exists()


def host_state(**updates: str) -> bytes:
    values = {
        "Id": cleanup.UNIT,
        "LoadState": "not-found",
        "ActiveState": "inactive",
        "SubState": "dead",
        "MainPID": "0",
        "ControlGroup": "",
        "FragmentPath": "",
        "DropInPaths": "",
        "User": "",
        "Group": "",
    }
    values.update(updates)
    return "\n".join(f"{k}={v}" for k, v in values.items()).encode()


@pytest.mark.parametrize(
    "field,value",
    [
        ("Id", "other.service"),
        ("LoadState", "loaded"),
        ("MainPID", "42"),
        ("ControlGroup", "/foreign"),
        ("DropInPaths", "/foreign.conf"),
        ("User", "1000"),
        ("ActiveState", "active"),
        ("FragmentPath", "/unit"),
    ],
)
def test_host_must_be_exactly_absent(tmp_path: Path, field: str, value: str) -> None:
    with pytest.raises(boundary.CleanupRejected, match="unit_not_absent"):
        cleanup.verify_host(host_state(**{field: value}), cgroup=tmp_path / "absent")


def test_cgroup_member_even_without_unit_blocks(tmp_path: Path) -> None:
    cleanup.verify_host(host_state(), cgroup=tmp_path / "absent")
    group = tmp_path / "group"
    group.mkdir()
    with pytest.raises(boundary.CleanupRejected, match="cgroup_not_absent"):
        cleanup.verify_host(host_state(), cgroup=group)


def test_root_wrapper_only_uses_pinned_scope_and_readonly_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pair = trees(tmp_path)
    runtime, code = (t.path for t in pair)
    gate = cleanup.encoded({"run_id": cleanup.RUN, "sequence": 7})
    (runtime / "gate-exit.json").write_bytes(gate)
    (runtime / "gate-exit.json").chmod(0o644)
    ledger = tmp_path / "ledger"
    original = {
        "run_id": cleanup.RUN,
        "result": "unknown",
        "restoration": {"unit_absent": True, "cgroup_empty": True},
        "exit_diagnostics": {"wait_checkpoint": "complete"},
        "padding": "",
    }
    padding = 999 - len(cleanup.encoded(original))
    assert padding > 0
    original["padding"] = "x" * padding
    ledger_raw = cleanup.encoded(original)
    assert len(ledger_raw) == 999
    ledger.write_bytes(ledger_raw)
    ledger.chmod(0o600)
    tools = {}
    for name in ("python", "systemctl", "systemd_analyze"):
        path = tmp_path / name
        path.write_bytes(b"public synthetic executable")
        path.chmod(0o755)
        tools[name] = {"path": str(path), "sha256": boundary.sha(path.read_bytes())}
    host = {
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "kernel": os.uname().release,
        "machine": os.uname().machine,
        "hostname_sha256": boundary.sha(os.uname().nodename.encode()),
    }
    approved = {
        "scope": "independent_synthetic_supervisor_exit_only",
        "run_id": cleanup.RUN,
        "host": host,
        "tools": tools,
        "members": {p.name: boundary.sha(p.read_bytes()) for p in code.iterdir()},
    }
    scope_raw = cleanup.encoded(approved)
    config = {
        "scope": cleanup.SCOPE,
        "run_id": cleanup.RUN,
        "paths": [str(code), str(runtime), str(ledger)],
        "ledger_sha256": boundary.sha(ledger_raw),
        "boundary_sha256": cleanup.BOUNDARY_SHA,
        "original_scope_sha256": boundary.sha(scope_raw),
        "owner_receipt_sha256": cleanup.OWNER_RECEIPT_SHA,
        "host": host,
        "exit_diagnostics": original["exit_diagnostics"],
        "code_inventory": inventory(code),
        "runtime_inventory": inventory(runtime),
        "ledger_identity": boundary.identity(ledger.lstat()),
    }
    original_record = boundary.record
    original_tree = boundary.Tree
    original_open = Path.open
    calls = []
    expected_uid = os.getuid()

    def mapped_record(path: Path, **kwargs: Any) -> bytes:
        assert Path(path).is_relative_to(tmp_path) or kwargs.get("dir_fd") is not None
        assert kwargs["uid"] in {0, 1000}
        kwargs["uid"] = expected_uid
        return original_record(path, **kwargs)

    def mapped_tree(
        path: Path,
        expected: dict[str, list[int]],
        uid: int,
        worker_uid: int | None = None,
    ) -> boundary.Tree:
        assert uid == 0 and worker_uid in {1000, None}
        return original_tree(
            path, expected, expected_uid, expected_uid if worker_uid else None
        )

    def command(path: str, args: list[str]) -> bytes:
        assert path == tools["systemctl"]["path"]
        assert args == [
            "show",
            cleanup.UNIT,
            "--property=Id,LoadState,ActiveState,SubState,MainPID,ControlGroup,FragmentPath,DropInPaths,User,Group",
            "--no-pager",
        ]
        calls.append("show")
        return host_state()

    def opened(path: Path, *args: Any, **kwargs: Any) -> Any:
        if str(path) == "/proc/self/mountinfo":
            return io.BytesIO(record("mnt:[7]"))
        return original_open(path, *args, **kwargs)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("old scope execution forbidden")

    for key, value in {
        "CODE": code,
        "RUNTIME": runtime,
        "LEDGER": ledger,
        "CGROUP": tmp_path / "absent-cgroup",
        "OLD_SCOPE_SHA": boundary.sha(scope_raw),
        "LEDGER_SHA": boundary.sha(ledger_raw),
    }.items():
        monkeypatch.setattr(cleanup, key, value)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "getegid", lambda: 0)
    monkeypatch.setattr(resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(sys, "executable", tools["python"]["path"])
    monkeypatch.setattr(boundary, "protected", lambda *args, **kwargs: None)
    monkeypatch.setattr(boundary, "record", mapped_record)
    monkeypatch.setattr(boundary, "Tree", mapped_tree)
    monkeypatch.setattr(boundary, "command", command)
    monkeypatch.setattr(boundary, "main", forbidden)
    monkeypatch.setattr(boundary, "perform", forbidden)
    monkeypatch.setattr(Path, "open", opened)
    # Explicit absent-path injection avoids touching any actual unit directory.
    lexists = os.path.lexists
    monkeypatch.setattr(
        os.path,
        "lexists",
        lambda path: (
            False
            if str(path).startswith(
                ("/etc/systemd/system/", "/run/systemd/system/", "/sys/fs/cgroup/")
            )
            else lexists(path)
        ),
    )
    assert cleanup.main(config, scope_raw) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["cleanup_result"] == "code_runtime_removed"
    assert value["removed_members_including_roots"] == 18
    assert value["original_experiment_result"] == "unknown"
    assert calls == ["show"] * 3
    assert ledger.read_bytes() == ledger_raw
    assert not runtime.exists() and not code.exists()
