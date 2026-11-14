"""#187 后续独立 D1:实际实验根与供给/模型/任务组合。"""

import json
from pathlib import Path

import pytest

from tests.experiment_screen_support import screen_fixture
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed


def test_initialized_root_can_supply_probe_and_consume_same_artifacts(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    probe = invoke(
        "probe-models",
        "--root",
        str(prepared.root),
        "--snapshot",
        prepared.snapshot,
        "--slot",
        "screening",
        "--credentials-dir",
        str(prepared.credentials),
        "--material-root",
        str(prepared.materials),
        "--install-root",
        str(prepared.install),
    )
    assert probe.exit_code == 0, probe.output
    assert json.loads(probe.stdout)[0]["state"] == "mapping_settable"
    result = prepared.screen()
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "succeeded"
    assert receipt["boundary"]["attempts"] == receipt["value"]["attempts"] == 1
    replay = prepared.screen()
    assert replay.exit_code == 0 and json.loads(replay.stdout)["state"] == "replayed"
    assert (prepared.root / "data/blobs/sha256").is_dir()
    assert (prepared.root / "data/tmp").is_dir()
    assert not (prepared.root / "blobs").exists()


@pytest.mark.parametrize("legacy", ["blobs", "tmp"])
def test_nonempty_legacy_layout_is_rejected_without_ignoring_or_deleting(
    tmp_path: Path, legacy: str
) -> None:
    root = tmp_path / "legacy"
    first = invoke("init", "--root", str(root))
    assert first.exit_code == 0, first.output
    (root / "data").rmdir()
    old = root / legacy / "sha256" / "old-object"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"synthetic historical artifact; preserve")
    database_before = (root / "paper-radar.sqlite3").read_bytes()
    for command in ("init", "egress-status"):
        result = invoke(command, "--root", str(root))
        assert result.exit_code == 2 and "legacy_layout" in result.output
    assert old.read_bytes() == b"synthetic historical artifact; preserve"
    assert (root / "paper-radar.sqlite3").read_bytes() == database_before
    assert not (root / "data").exists()


def test_registration_only_legacy_root_prepares_data_without_moving_database(
    tmp_path: Path,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.storage.database import upgrade_database

    root = tmp_path / "registered"
    root.mkdir()
    database = root / "paper-radar.sqlite3"
    upgrade_database(database)
    registered = BodyService(database, root).register_root("experiment")
    (root / "blobs").mkdir()
    (root / "tmp").mkdir()
    inode = database.stat().st_ino
    result = invoke("init", "--root", str(root))
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["root_id"] == registered.root_id
    assert database.stat().st_ino == inode
    assert BodyService(database, root / "data").root() == registered
    assert (root / "data").is_dir()
    assert not (root / "data/paper-radar.sqlite3").exists()


@pytest.mark.parametrize("relative", ["data", "data/blobs", "data/tmp"])
@pytest.mark.parametrize("kind", ["symlink", "file"])
def test_new_data_layout_refuses_links_and_wrong_types_without_writes(
    tmp_path: Path, relative: str, kind: str
) -> None:
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "marker"
    protected.write_bytes(b"preserve outside")
    target = root / relative
    if target.is_dir():
        target.rmdir()
    if kind == "symlink":
        target.symlink_to(outside, target_is_directory=True)
    else:
        target.write_bytes(b"wrong type")
    database_before = (root / "paper-radar.sqlite3").read_bytes()
    for command in ("init", "egress-status"):
        result = invoke(command, "--root", str(root))
        assert result.exit_code == 2 and "unsafe_layout" in result.output
    assert (root / "paper-radar.sqlite3").read_bytes() == database_before
    assert list(outside.iterdir()) == [protected]
    assert protected.read_bytes() == b"preserve outside"
