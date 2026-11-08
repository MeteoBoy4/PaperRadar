"""D1 unbound tests; only temporary, credential-free artifacts are removed."""

from __future__ import annotations

import json
import os
import resource
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import issue167_live_artifact_cleanup as cleanup


def inventory(root: Path) -> dict[str, list[int]]:
    return {
        "": cleanup.identity(root.lstat()),
        **{
            str(path.relative_to(root)): cleanup.identity(path.lstat())
            for path in root.rglob("*")
        },
    }


def fixture_tree(root: Path) -> cleanup.Tree:
    root.mkdir(mode=0o700)
    child = root / "nested"
    child.mkdir(mode=0o700)
    (child / "fixture").write_bytes(b"public synthetic fixture")
    (root / "metadata.json").write_text('{"result":"unknown"}')
    (child / "fixture").chmod(0o600)
    (root / "metadata.json").chmod(0o600)
    return cleanup.Tree(root, inventory(root), os.getuid(), os.getuid())


def host_state(**updates: str) -> bytes:
    state = {
        "Id": cleanup.UNIT,
        "LoadState": "not-found",
        "ActiveState": "inactive",
        "SubState": "dead",
        "MainPID": "0",
        "ControlGroup": "",
        "FragmentPath": "",
        "DropInPaths": "",
    }
    state.update(updates)
    return "\n".join(f"{key}={value}" for key, value in state.items()).encode()


def tables(name: str | None = None) -> bytes:
    return json.dumps(
        {
            "nftables": []
            if name is None
            else [{"table": {"family": "inet", "name": name}}]
        }
    ).encode()


def test_removes_only_two_owned_trees_and_keeps_original_unknown(
    tmp_path: Path,
) -> None:
    trees = (fixture_tree(tmp_path / "runtime"), fixture_tree(tmp_path / "code"))
    ledger = tmp_path / "permanent.json"
    ledger.write_bytes(b'{"result":"unknown","budget":"retained"}\n')
    before = ledger.read_bytes()
    checks: list[bytes] = []

    def verify() -> None:
        checks.append(ledger.read_bytes())
        assert checks[-1] == before

    result = cleanup.perform(trees, verify, {})
    assert checks == [before] * 3
    assert not any(tree.path.exists() for tree in trees)
    assert ledger.read_bytes() == before
    assert result["original_experiment_result"] == "unknown"
    assert result["original_ledger_unchanged"] is True
    assert result["removed_members_including_roots"] == 8
    assert result["auth_model_reexecs"] == result["network_operations"] == 0
    assert result["budget_refund"] == 0


@pytest.mark.parametrize(
    "kind", ["symlink", "hardlink", "fifo", "foreign_owner", "setuid", "mount_device"]
)
def test_rejects_boundary_violation_before_removing_anything(
    tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = fixture_tree(tmp_path / "first")
    second = fixture_tree(tmp_path / "second")
    outside = tmp_path / "outside"
    outside.write_bytes(b"must survive")
    item = second.path / "unexpected"
    if kind == "symlink":
        item.symlink_to(outside)
    elif kind == "hardlink":
        os.link(outside, item)
    elif kind == "fifo":
        os.mkfifo(item, 0o600)
    elif kind == "setuid":
        item.write_bytes(b"fixture")
        item.chmod(0o4600)
    elif kind == "foreign_owner":
        second.root_uid = os.getuid() + 1
    else:
        second.expected[""][0] += 1
    with pytest.raises(cleanup.CleanupRejected):
        cleanup.perform((first, second), lambda: None, {})
    assert (first.path / "nested/fixture").is_file()
    assert outside.read_bytes() == b"must survive"
    assert not first.fds and not second.fds


def test_inventory_change_is_not_silently_accepted(tmp_path: Path) -> None:
    tree = fixture_tree(tmp_path / "tree")
    (tree.path / "added").write_bytes(b"unknown")
    (tree.path / "added").chmod(0o600)
    with pytest.raises(cleanup.CleanupRejected, match="inventory_changed"):
        tree.inspect()
    assert tree.path.exists()


@pytest.mark.parametrize("change", ["ledger", "tree"])
def test_second_pass_failure_leaves_both_trees_intact(
    tmp_path: Path, change: str
) -> None:
    trees = (fixture_tree(tmp_path / "one"), fixture_tree(tmp_path / "two"))
    calls = 0

    def verify() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == "ledger":
                raise cleanup.CleanupRejected("original_ledger_changed")
            (trees[1].path / "nested/fixture").write_bytes(b"changed fixture")

    with pytest.raises(cleanup.CleanupRejected):
        cleanup.perform(trees, verify, {})
    assert all((tree.path / "metadata.json").is_file() for tree in trees)


def test_inspection_does_not_read_descendant_file_bodies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = fixture_tree(tmp_path / "tree")

    def denied(*args: Any) -> bytes:
        raise AssertionError("arbitrary child content read")

    monkeypatch.setattr(os, "read", denied)
    try:
        tree.inspect()
        tree.verify()
        assert tree.remove() == 4
    finally:
        tree.close()


def test_link_replacement_after_inspection_does_not_touch_external_target(
    tmp_path: Path,
) -> None:
    tree = fixture_tree(tmp_path / "tree")
    outside = tmp_path / "outside"
    outside.write_bytes(b"preserve")
    try:
        tree.inspect()
        child = tree.path / "nested/fixture"
        child.unlink()
        child.symlink_to(outside)
        with pytest.raises(cleanup.CleanupRejected, match="changed"):
            tree.remove()
        assert outside.read_bytes() == b"preserve"
    finally:
        tree.close()


@pytest.mark.parametrize(
    "updates",
    [
        {"LoadState": "loaded"},
        {"ActiveState": "active"},
        {"MainPID": "123"},
        {"ControlGroup": "/system.slice/foreign.service"},
        {"FragmentPath": "/tmp/foreign.service"},
    ],
)
def test_active_or_uncertain_unit_blocks_cleanup(
    tmp_path: Path, updates: dict[str, str]
) -> None:
    with pytest.raises(cleanup.CleanupRejected, match="unit_not_absent"):
        cleanup.verify_host(
            cleanup.UNIT, host_state(**updates), tables(), tmp_path / "cg"
        )


def test_target_table_presence_blocks_but_unrelated_table_is_untouched(
    tmp_path: Path,
) -> None:
    with pytest.raises(cleanup.CleanupRejected, match="table_still_present"):
        cleanup.verify_host(
            cleanup.UNIT, host_state(), tables(cleanup.TABLE), tmp_path / "cg"
        )
    cleanup.verify_host(
        cleanup.UNIT, host_state(), tables("unrelated"), tmp_path / "cg"
    )


def test_even_empty_cgroup_blocks_cleanup(tmp_path: Path) -> None:
    cgroup = tmp_path / "cg"
    cgroup.mkdir()
    with pytest.raises(cleanup.CleanupRejected, match="cgroup_not_absent"):
        cleanup.verify_host(cleanup.UNIT, host_state(), tables(), cgroup)


@pytest.mark.parametrize("raw", [b"{}", b'{"nftables":[{"chain":{}}]}', b"not json"])
def test_unreadable_or_malformed_host_proof_blocks(tmp_path: Path, raw: bytes) -> None:
    with pytest.raises(cleanup.CleanupRejected, match="host_state_unknown"):
        cleanup.verify_host(cleanup.UNIT, host_state(), raw, tmp_path / "cg")


def test_same_device_bind_mount_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "retained"
    raw = (
        "1 0 1:1 / / rw - tmpfs tmpfs rw\n"
        f"2 1 1:1 / {root}/nested rw - tmpfs tmpfs rw\n"
    )
    with pytest.raises(cleanup.CleanupRejected, match="artifact_mount_unknown"):
        cleanup.check_mounts((root,), cleanup.mount_roots(raw))


def test_fixed_root_scope_rejects_other_paths_before_opening_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(resource, "setrlimit", lambda *args: None)
    config = {
        "run_id": cleanup.RUN,
        "paths": ["/home/foreign", str(cleanup.RUNTIME), str(cleanup.LEDGER)],
        "core_sha256": cleanup.CORE_SHA,
        "ledger_sha256": cleanup.LEDGER_SHA,
    }
    assert cleanup.main(config) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["failure_reason"] == "fixed_scope_changed"
    assert result["cleanup_result"] == result["original_experiment_result"] == "unknown"


def test_known_metadata_read_rejects_link_and_mode_drift(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"{}")
    original.chmod(0o600)
    assert cleanup.record(original, uid=os.getuid(), mode=0o600) == b"{}"
    os.link(original, tmp_path / "alias")
    with pytest.raises(cleanup.CleanupRejected, match="record_metadata_unknown"):
        cleanup.record(original, uid=os.getuid(), mode=0o600)


@pytest.mark.parametrize("replace_after_pin", [False, True])
def test_metadata_ancestor_symlink_never_reads_external_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replace_after_pin: bool,
) -> None:
    tree = fixture_tree(tmp_path / "runtime")
    outside = tmp_path / "external"
    outside.mkdir()
    (outside / "fixture").write_bytes(b"outside data must never be read")
    if replace_after_pin:
        tree.inspect()
    (tree.path / "nested").rename(tree.path / "saved")
    (tree.path / "nested").symlink_to(outside, target_is_directory=True)
    reads: list[int] = []

    def deny_read(fd: int, size: int) -> bytes:
        reads.append(fd)
        raise AssertionError("no body read permitted after ancestor replacement")

    monkeypatch.setattr(os, "read", deny_read)
    try:
        with pytest.raises(cleanup.CleanupRejected):
            if not replace_after_pin:
                tree.inspect()
            tree.read_metadata("nested/fixture", uid=os.getuid(), mode=0o600)
        assert reads == []
    finally:
        tree.close()


def test_replacement_during_metadata_open_is_rejected_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = fixture_tree(tmp_path / "runtime")
    tree.inspect()
    staged = tmp_path / "untrusted-metadata"
    staged.write_bytes(b"unapproved same uid, same mode content")
    staged.chmod(0o600)
    original_open = os.open
    replaced = False
    reads: list[int] = []

    def race_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal replaced
        if path == Path("fixture") and kwargs.get("dir_fd") == tree.fds["nested"]:
            staged.replace(tree.path / "nested/fixture")
            replaced = True
        return original_open(path, flags, *args, **kwargs)

    def denied(fd: int, size: int) -> bytes:
        reads.append(fd)
        raise AssertionError("replacement content must not be read")

    monkeypatch.setattr(os, "open", race_open)
    monkeypatch.setattr(os, "read", denied)
    try:
        with pytest.raises(cleanup.CleanupRejected, match="record_metadata_unknown"):
            tree.read_metadata("nested/fixture", uid=os.getuid(), mode=0o600)
        assert replaced and reads == []
    finally:
        tree.close()


def test_unknown_host_command_does_not_fall_back_to_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        seen.append(args)
        return subprocess.CompletedProcess(args, 1, b"", b"private diagnostic")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(cleanup.CleanupRejected, match="readonly_command_unknown"):
        cleanup.command("/usr/sbin/nft", ["-j", "list", "tables"])
    assert seen == [["/usr/sbin/nft", "-j", "list", "tables"]]
