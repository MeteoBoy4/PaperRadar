"""独立D1:诊断专用原安装只读投影与OFD,仅/tmp合成实例。"""

import fcntl
import hashlib
import json
import os
import selectors
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from paper_radar.pi_supply.filesystem import tree_hash
from scripts import issue167_node_diag_supply as supply

Fixture = tuple[Path, Path, str, str]


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


@pytest.fixture
def instance(tmp_path: Path) -> tuple[Path, Path, str, str]:
    root = tmp_path / "install"
    root.mkdir(mode=0o700)
    (root / ".locks").mkdir(mode=0o700)
    install_id = "b" * 32
    staged = root / "staged"
    entries = (
        "node/bin/node",
        "node/lib/node_modules/npm/bin/npm-cli.js",
        "app/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
    )
    for name in entries:
        p = staged / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"synthetic-public-file")
        p.chmod(0o555 if name == entries[0] else 0o444)
    (staged / "internal-link").symlink_to("node/bin/node")
    staged.chmod(0o755)
    manifest = {
        "expected_tree": tree_hash(staged),
        "node_entry": entries[0],
        "npm_entry": entries[1],
        "pi_entry": entries[2],
        "node_version": "22.23.4",
        "npm_version": "10.9.9",
        "pi_version": "1.4.0",
        "platform": {"os": "linux", "arch": "x86_64", "libc": "glibc"},
        "libc_version": (os.confstr("CS_GNU_LIBC_VERSION") or "glibc 0").split()[1],
        "node_sha256": "f" * 64,
    }
    raw = canonical(manifest)
    sid = hashlib.sha256(raw).hexdigest()
    (root / sid).mkdir()
    staged.rename(root / sid / install_id)
    (root / ".locks" / f"{install_id}.lock").touch(mode=0o600)
    marker = root / ".paper-radar-install-root"
    marker.write_bytes(canonical({"database_id": "d" * 32, "root_id": "e" * 32}))
    marker.chmod(0o600)
    db = tmp_path / "metadata.sqlite3"
    with sqlite3.connect(db) as con:
        con.executescript("""
CREATE TABLE pi_supply_database(singleton INTEGER,database_id TEXT);
CREATE TABLE pi_supply_roots(root_id TEXT,path TEXT);
CREATE TABLE pi_supplies(supply_id TEXT,manifest BLOB);
CREATE TABLE pi_install_instances(install_id TEXT,supply_id TEXT,root_id TEXT);
CREATE TABLE pi_install_checks(
check_id INTEGER,install_id TEXT,scope TEXT,passed INTEGER,reason TEXT);
CREATE TABLE pi_install_retirements(install_id TEXT);
CREATE TABLE pi_activation_events(
activation_id INTEGER,supply_id TEXT,install_id TEXT,
snapshot_id TEXT,root_id TEXT,root_path TEXT);
CREATE TABLE pi_current_selection(singleton INTEGER,activation_id INTEGER);
CREATE TABLE business(secret TEXT);
INSERT INTO business VALUES('synthetic-private-row-never-read');
""")
        con.execute("INSERT INTO pi_supply_database VALUES(1,?)", ("d" * 32,))
        con.execute("INSERT INTO pi_supply_roots VALUES(?,?)", ("e" * 32, str(root)))
        con.execute("INSERT INTO pi_supplies VALUES(?,?)", (sid, raw))
        con.execute(
            "INSERT INTO pi_install_instances VALUES(?,?,?)",
            (install_id, sid, "e" * 32),
        )
        con.execute(
            "INSERT INTO pi_install_checks VALUES(1,?,'install_check',1,'passed')",
            (install_id,),
        )
        con.execute(
            "INSERT INTO pi_activation_events VALUES(1,?,?,?,?,?)",
            (sid, install_id, "a" * 64, "e" * 32, str(root)),
        )
        con.execute("INSERT INTO pi_current_selection VALUES(1,1)")
    db.chmod(0o600)
    return db, root, sid, install_id


def prepare(instance: tuple[Path, Path, str, str]) -> dict[str, Any]:
    return supply.prepare_binding(*instance)


def test_prepare_is_metadata_only_and_original_tree_rule_matches(
    instance: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        supply, "_tree_hash", lambda _: pytest.fail("prepare_must_not_hash_tree")
    )
    monkeypatch.setattr(
        fcntl, "flock", lambda *_: pytest.fail("prepare_must_not_take_lock")
    )
    b = prepare(instance)
    assert b["kind"] == supply.KIND
    assert b["whole_tree_checked_during_prepare"] is False
    assert b["node_sha256"] != "f" * 64


def test_readonly_authorizer_denies_business_and_writes(instance: Fixture) -> None:
    with supply._connect(instance[0]) as con:
        with pytest.raises(sqlite3.DatabaseError, match="prohibited"):
            con.execute("SELECT secret FROM business").fetchall()
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            con.execute("DELETE FROM pi_current_selection")


def test_failed_check_raw_reason_is_projected_to_closed_category(
    instance: Fixture,
) -> None:
    raw = "synthetic-private-diagnostic-never-copied"
    with sqlite3.connect(instance[0]) as con:
        con.execute(
            "INSERT INTO pi_install_checks VALUES(2,?,'install_check',0,?)",
            (instance[3], raw),
        )
    b = prepare(instance)
    assert raw.encode() not in canonical(b)
    assert b["registration"]["checks"][1] == {
        "check_id": 2,
        "scope": "install_check",
        "passed": 0,
        "reason_category": "recorded_failure",
    }


@pytest.mark.parametrize("change", ["missing", "retired", "selection", "marker"])
def test_unusable_public_registration_or_marker_is_rejected(
    instance: Fixture, change: str
) -> None:
    db, root, _, iid = instance
    if change == "marker":
        (root / ".paper-radar-install-root").write_bytes(
            canonical({"database_id": "f" * 32, "root_id": "e" * 32})
        )
    else:
        with sqlite3.connect(db) as con:
            if change == "missing":
                con.execute("DELETE FROM pi_install_instances")
            elif change == "retired":
                con.execute("INSERT INTO pi_install_retirements VALUES(?)", (iid,))
            else:
                con.execute("UPDATE pi_current_selection SET activation_id=2")
    with pytest.raises(
        supply.SupplyRejected,
        match=r"supply_registration_unknown|supply_marker_unknown",
    ):
        prepare(instance)


@pytest.mark.parametrize("change", ["extra", "bool_uid", "bool_inode", "derived_path"])
def test_binding_is_closed_and_rejects_boolean_integers(
    instance: Fixture, tmp_path: Path, change: str
) -> None:
    b = prepare(instance)
    if change == "extra":
        b["raw"] = "forbidden"
    elif change == "bool_uid":
        b["uid"] = True
    elif change == "bool_inode":
        b["lock"]["inode"] = True
    else:
        b["node"] = "/tmp/other-node"
    p = tmp_path / "binding.json"
    p.write_bytes(canonical(b))
    p.chmod(0o600)
    with pytest.raises(supply.SupplyRejected, match="supply_binding_unknown"):
        supply.load_binding(p)


def test_root_can_load_shape_but_cannot_touch_actual_supply(
    instance: Fixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    b = prepare(instance)
    p = tmp_path / "binding.json"
    p.write_bytes(canonical(b))
    p.chmod(0o600)
    monkeypatch.setattr(os, "getuid", lambda: 0)
    monkeypatch.setattr(
        supply, "_read_registration", lambda *_: pytest.fail("root_db_forbidden")
    )
    assert supply.load_binding(p) == b
    with (
        pytest.raises(supply.SupplyRejected, match="supply_uid_unknown"),
        supply.supply_use(b),
    ):
        pass


def test_valid_supply_matches_public_tree_and_holds_one_original_fd(
    instance: Fixture,
) -> None:
    b = prepare(instance)
    assert supply._tree_hash(Path(b["install"])) == tree_hash(Path(b["install"]))
    with supply.supply_use(b) as h:
        assert h.node == Path(b["node"]) and h.install == Path(b["install"])
        assert len(h.pass_fds) == 1
        assert os.fstat(h.pass_fds[0]).st_ino == b["lock"]["inode"]
        assert h.identity_metadata["whole_tree_checked_under_lock"] is True


@pytest.mark.parametrize("change", ["missing", "replaced", "symlink"])
def test_old_lock_cannot_be_recreated_or_replaced(
    instance: Fixture, change: str
) -> None:
    b = prepare(instance)
    lock = Path(b["lock"]["path"])
    lock.unlink()
    if change == "replaced":
        lock.touch(mode=0o600)
    elif change == "symlink":
        lock.symlink_to("missing")
    with (
        pytest.raises(supply.SupplyRejected, match="supply_lock_unknown"),
        supply.supply_use(b),
    ):
        pass
    if change == "missing":
        assert not lock.exists()


def test_busy_original_lock_is_not_unlocked_by_failed_acquire(
    instance: Fixture,
) -> None:
    b = prepare(instance)
    fd = os.open(b["lock"]["path"], os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (
            pytest.raises(supply.SupplyRejected, match="supply_install_busy"),
            supply.supply_use(b),
        ):
            pass
    finally:
        os.close(fd)


@pytest.mark.parametrize(
    "change", ["file", "external_link", "special", "missing_entry"]
)
def test_tree_changes_or_unsafe_members_block_before_use(
    instance: Fixture, tmp_path: Path, change: str
) -> None:
    b = prepare(instance)
    tree = Path(b["install"])
    if change == "file":
        (tree / "changed").write_text("changed")
    elif change == "external_link":
        (tree / "external").symlink_to(tmp_path / "outside")
    elif change == "special":
        os.mkfifo(tree / "fifo")
    else:
        (tree / b["registration"]["pi_entry"]).unlink()
    with (
        pytest.raises(
            supply.SupplyRejected,
            match=r"supply_tree_unknown|supply_tree_mismatch|supply_entry_unknown",
        ),
        supply.supply_use(b),
    ):
        pass


def test_scope_exit_rechecks_tree_and_closes_fd_on_drift(instance: Fixture) -> None:
    b = prepare(instance)
    with (
        pytest.raises(supply.SupplyRejected, match="supply_tree_mismatch"),
        supply.supply_use(b),
    ):
        (Path(b["install"]) / "changed").write_text("changed")
    fd = os.open(b["lock"]["path"], os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


def test_child_inherits_original_ofd_and_parent_close_does_not_unlock(
    instance: Fixture,
) -> None:
    b = prepare(instance)
    child = None
    try:
        with supply.supply_use(b) as h:
            code = (
                "import os,sys;os.fstat(int(sys.argv[1]));"
                "print('ready',flush=True);sys.stdin.buffer.read(1)"
            )
            child = subprocess.Popen(
                [sys.executable, "-I", "-S", "-B", "-c", code, str(h.pass_fds[0])],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={},
                pass_fds=h.pass_fds,
            )
            assert child.stdout is not None
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                assert selector.select(5), "synthetic_child_timeout"
                assert child.stdout.readline() == b"ready\n"
        fd = os.open(b["lock"]["path"], os.O_RDONLY)
        try:
            with pytest.raises(
                BlockingIOError, match="Resource temporarily unavailable"
            ):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    finally:
        if child is not None:
            assert child.stdin is not None
            child.stdin.close()
            child.wait(timeout=5)
            assert child.stdout is not None
            child.stdout.close()


@pytest.mark.parametrize("when", ["before", "exit"])
def test_target_selection_drift_blocks_even_when_instance_is_unchanged(
    instance: Fixture, when: str
) -> None:
    b = prepare(instance)

    def drift() -> None:
        with sqlite3.connect(instance[0]) as con:
            con.execute(
                "INSERT INTO pi_activation_events VALUES(2,?,?,?,?,?)",
                (instance[2], instance[3], "f" * 64, "e" * 32, str(instance[1])),
            )
            con.execute("UPDATE pi_current_selection SET activation_id=2")

    if when == "before":
        drift()
    with (
        pytest.raises(supply.SupplyRejected, match="supply_binding_drift"),
        supply.supply_use(b),
    ):
        if when == "exit":
            drift()
