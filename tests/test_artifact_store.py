"""内容对象与制品公共边界的真实 SQLite/文件系统承诺。"""

from pathlib import Path

import pytest

from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database


def test_zero_bytes_can_be_published_and_read_after_service_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "separate.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "data")
    saved = store.publish_single("source_snapshot", [b"", b""])
    assert (
        saved.members[0].sha256
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert saved.members[0].size_bytes == 0
    assert ArtifactStore(database, tmp_path / "data").read_artifact(
        saved.artifact_id
    ) == {"payload": b""}


def test_republish_does_not_repair_a_registered_missing_file(tmp_path: Path) -> None:
    import pytest

    from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "data")
    saved = store.publish_single("original_pdf", [b"abc"])
    _, blobs = store.artifact_blobs(saved.artifact_id)
    store.verified_blob_path(blobs[0]).unlink()
    with pytest.raises(ArtifactError) as failure:
        store.publish_single("original_pdf", [b"abc"])
    assert failure.value.reason == ArtifactReason.BLOB_MISSING


@pytest.mark.parametrize(
    "kind",
    ["source_snapshot", "original_pdf", "model_success_response", "reference_tei"],
)
def test_segmented_publish_is_idempotent_and_survives_new_process(
    tmp_path: Path, kind: str
) -> None:
    import subprocess
    import sys

    from tests.artifact_support import registration_facts

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    root = tmp_path / "new" / "nested" / "root"
    store = ArtifactStore(database, root)
    saved = store.publish_single(kind, [b"a", b"", b"bc"])
    facts = registration_facts(database)
    assert store.publish_single(kind, [b"abc"]) == saved
    assert registration_facts(database) == facts
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import sys; from paper_radar.stora"
                "ge.artifacts import ArtifactStore; assert ArtifactStore(Path"
                "(sys.argv[1]),Path(sys.argv[2])).read_artifact(sys.argv[3]) "
                "== {'payload': b'abc'}"
            ),
            str(database),
            str(root),
            saved.artifact_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (
        saved.members[0].sha256
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    blob = store.artifact_blobs(saved.artifact_id)[1][0]
    assert store.verified_blob_path(blob).stat().st_mode & 0o777 == 0o400
    assert all(p.stat().st_mode & 0o077 == 0 for p in root.rglob("*") if p.is_dir())


def test_same_blob_can_be_shared_across_kinds_and_concurrent_publishers(
    tmp_path: Path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from tests.artifact_support import registration_facts

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    barrier = Barrier(4)

    def publish() -> str:
        barrier.wait(timeout=15)
        return store.publish_single("source_snapshot", [b"abc"]).artifact_id

    with ThreadPoolExecutor(4) as workers:
        ids = list(workers.map(lambda _: publish(), range(4)))
    assert len(set(ids)) == 1
    other = store.publish_single("original_pdf", [b"abc"])
    assert other.artifact_id != ids[0]
    assert tuple(map(len, registration_facts(database))) == (1, 2, 2)
    assert len(store.list_artifacts()) == 2


@pytest.mark.parametrize(
    "damage", ["missing", "same_length", "member", "location", "layout", "orphan"]
)
def test_corrupt_registered_history_is_rejected_without_repair(
    tmp_path: Path, damage: str
) -> None:
    import sqlite3

    from paper_radar.storage.artifact_contract import ArtifactError
    from tests.artifact_support import registration_facts

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    saved = store.publish_single("source_snapshot", [b"abc"])
    path = store.verified_blob_path(store.artifact_blobs(saved.artifact_id)[1][0])
    if damage == "missing":
        path.unlink()
    elif damage == "same_length":
        path.chmod(0o600)
        path.write_bytes(b"abd")
        path.chmod(0o400)
    else:
        with sqlite3.connect(database) as connection:
            if damage == "member":
                connection.execute("UPDATE artifact_members SET role='unknown'")
            if damage == "location":
                connection.execute(
                    "UPDATE content_objects SET relative_path='../sentinel'"
                )
            if damage == "layout":
                connection.execute("UPDATE content_objects SET layout_version=2")
            if damage == "orphan":
                connection.execute("DELETE FROM content_objects")
    before = registration_facts(database)
    with pytest.raises(ArtifactError):
        store.read_artifact(saved.artifact_id)
    with pytest.raises(ArtifactError):
        store.publish_single("source_snapshot", [b"abc"])
    assert registration_facts(database) == before
    if damage == "same_length":
        assert path.read_bytes() == b"abd"


@pytest.mark.parametrize("component", ["tmp", "blobs", "sha256", "prefix", "file"])
def test_inner_symlinks_cannot_touch_external_sentinels(
    tmp_path: Path, component: str
) -> None:
    from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"keep")
    root = tmp_path / "root"
    root.mkdir()
    relative = {
        "tmp": "tmp",
        "blobs": "blobs",
        "sha256": "blobs/sha256",
        "prefix": "blobs/sha256/ba",
        "file": (
            "blobs/sha256/ba/"
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        ),
    }[component]
    link = root / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(sentinel if component == "file" else outside)
    with pytest.raises(ArtifactError) as failure:
        ArtifactStore(database, root).publish_single("original_pdf", [b"abc"])
    assert failure.value.reason == ArtifactReason.UNSAFE_PATH
    assert {p.name: p.read_bytes() for p in outside.iterdir()} == {"sentinel": b"keep"}


def test_root_symlink_is_resolved_once_and_remains_usable(tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    actual = tmp_path / "actual"
    actual.mkdir()
    root = tmp_path / "root"
    root.symlink_to(actual)
    store = ArtifactStore(database, root)
    root.unlink()
    root.symlink_to(tmp_path / "other")
    saved = store.publish_single("source_snapshot", [b"abc"])
    assert store.read_artifact(saved.artifact_id) == {"payload": b"abc"}
    assert not (tmp_path / "other").exists()


def test_link_failure_is_controlled_and_only_own_temp_is_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason
    from tests.artifact_support import registration_facts

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    root = tmp_path / "root"
    (root / "tmp").mkdir(parents=True)
    abandoned = root / "tmp/abandoned"
    abandoned.write_bytes(b"keep")

    def fail_link(*args: object, **kwargs: object) -> None:
        raise OSError("not supported")

    monkeypatch.setattr(os, "link", fail_link)
    with pytest.raises(ArtifactError) as failure:
        ArtifactStore(database, root).publish_single("original_pdf", [b"abc"])
    assert failure.value.reason == ArtifactReason.PUBLICATION_FAILED
    assert list((root / "tmp").iterdir()) == [abandoned]
    assert tuple(map(len, registration_facts(database))) == (0, 0, 0)


@pytest.mark.parametrize("stop", ["failure", "kill"])
def test_file_publication_before_database_commit_can_be_retried(
    tmp_path: Path, stop: str
) -> None:
    from paper_radar.storage.artifact_contract import ArtifactError
    from tests.artifact_support import fail_sql, paused_operation, registration_facts

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    root = tmp_path / "root"
    store = ArtifactStore(database, root)
    if stop == "failure":
        with fail_sql("INSERT INTO artifact_members"), pytest.raises(ArtifactError):
            store.publish_single("source_snapshot", [b"abc"])
    else:
        code = (
            "from pathlib import Path;import sys;from paper_radar.storage"
            ".artifacts import ArtifactStore;ArtifactStore(Path(sys.argv["
            "1]),Path(sys.argv[2])).publish_single('source_snapshot',[b'a"
            "bc'])"
        )
        with paused_operation(
            code, [str(database), str(root)], "INSERT INTO artifact_members"
        ) as process:
            process.kill()
            process.wait(timeout=15)
    assert tuple(map(len, registration_facts(database))) == (0, 0, 0)
    assert store.list_artifacts() == ()
    assert [p.read_bytes() for p in (root / "blobs").rglob("*") if p.is_file()] == [
        b"abc"
    ]
    saved = store.publish_single("source_snapshot", [b"abc"])
    assert store.read_artifact(saved.artifact_id) == {"payload": b"abc"}


def test_bad_expected_hash_and_extraction_are_rejected_without_registration(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    with pytest.raises(ArtifactError) as mismatch:
        store.publish_single("original_pdf", [b"abc"], expected_sha256="0" * 64)
    assert mismatch.value.reason == ArtifactReason.HASH_MISMATCH
    with pytest.raises(ArtifactError) as unsupported:
        store.publish_artifact("extraction", {})
    assert unsupported.value.reason == ArtifactReason.INVALID_MANIFEST
    assert store.list_artifacts() == ()


def test_existing_matching_writable_blob_is_not_adopted_as_immutable(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    root = tmp_path / "root"
    blob = (
        root / "blobs/sha256/ba/"
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"abc")
    blob.chmod(0o600)
    store = ArtifactStore(database, root)
    with pytest.raises(ArtifactError) as failure:
        store.publish_single("source_snapshot", [b"abc"])
    assert failure.value.reason == ArtifactReason.BLOB_CORRUPT
    assert blob.stat().st_mode & 0o777 == 0o600
    assert store.list_artifacts() == ()


def test_writer_lock_is_bounded_and_returns_controlled_retry_reason(
    tmp_path: Path,
) -> None:
    import sqlite3
    import time

    from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    with sqlite3.connect(database) as owner:
        owner.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        with pytest.raises(ArtifactError) as failure:
            store.publish_single("source_snapshot", [b"abc"])
        elapsed = time.monotonic() - started
    assert failure.value.reason == ArtifactReason.DATABASE_BUSY
    assert 4.5 <= elapsed < 30
    assert store.list_artifacts() == ()
    saved = store.publish_single("source_snapshot", [b"abc"])
    assert store.read_artifact(saved.artifact_id) == {"payload": b"abc"}
