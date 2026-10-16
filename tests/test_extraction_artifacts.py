"""完整正文制品的多角色持久化与故障恢复承诺。"""

import json
from pathlib import Path

import pytest

from paper_radar.storage.artifact_contract import ArtifactError, artifact_manifest
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from tests.artifact_support import registration_facts
from tests.extraction_support import PAYLOADS, chunked


def test_complete_extraction_uses_the_previously_frozen_identity(
    tmp_path: Path,
) -> None:
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    saved = store.publish_artifact(
        "extraction",
        {
            "reading": [b"abc"],
            "manifest": [b""],
            "document": [b"a", b"bc"],
            "evidence_map": [b""],
        },
    )
    assert (
        saved.artifact_id
        == "b461c859afffb63c837b556746fd0ab9cfe892bcd1a58a912da46799b1738d87"
    )
    assert store.read_artifact(saved.artifact_id) == {
        "document": b"abc",
        "evidence_map": b"",
        "manifest": b"",
        "reading": b"abc",
    }


@pytest.mark.parametrize("index", range(6))
def test_independent_fixed_member_and_role_variants_keep_expected_identity(
    tmp_path: Path, index: int
) -> None:
    vectors = json.loads(
        (
            Path(__file__).parent / "fixtures/extraction_artifact_vectors.json"
        ).read_bytes()
    )
    expected = vectors[index]
    values = {role: bytes.fromhex(raw) for role, raw in expected["payload_hex"].items()}
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    record = store.publish_artifact("extraction", chunked(values))
    assert record.artifact_id == expected["artifact_id"]
    assert (
        artifact_manifest(record.kind, record.members).canonical_json
        == expected["canonical_json"]
    )
    before = registration_facts(database)
    assert (
        store.publish_artifact(
            "extraction", chunked(dict(reversed(tuple(values.items()))))
        )
        == record
    )
    assert registration_facts(database) == before
    assert store.read_artifact(record.artifact_id) == values


def test_roles_and_kinds_share_content_but_keep_all_references(tmp_path: Path) -> None:
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    values = {
        "document": b"abc",
        "evidence_map": b"",
        "manifest": b"",
        "reading": b"abc",
    }
    first = store.publish_artifact("extraction", chunked(values))
    single = store.publish_single("source_snapshot", [b"abc"])
    values["manifest"] = b"new"
    second = store.publish_artifact("extraction", chunked(values))
    assert first.artifact_id != second.artifact_id
    assert store.read_artifact(first.artifact_id)["reading"] == b"abc"
    assert store.read_artifact(single.artifact_id) == {"payload": b"abc"}
    assert tuple(map(len, registration_facts(database))) == (3, 3, 9)
    assert len(store.list_artifacts()) == 3
    first_record, blobs = store.artifact_blobs(first.artifact_id)
    assert tuple(member.role for member in first_record.members) == (
        "document",
        "evidence_map",
        "manifest",
        "reading",
    )
    assert blobs[0] == blobs[3]
    assert blobs[1] == blobs[2]


@pytest.mark.parametrize(
    "damage",
    ["missing", "extra", "unknown", "duplicate", "bad_hash", "wrong_hash", "nonbytes"],
)
def test_incomplete_or_invalid_member_input_never_registers_half_a_collection(
    tmp_path: Path, damage: str
) -> None:
    from collections.abc import Iterable, Iterator, Mapping

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    members = chunked(PAYLOADS)
    expected_hash: dict[str, str] | None = None
    if damage == "missing":
        members.pop("reading")
    elif damage == "extra":
        members["other"] = [b"extra"]
    elif damage == "unknown":
        members["other"] = members.pop("reading")
    elif damage == "bad_hash":
        expected_hash = {"reading": "../PRIVATE_HASH"}
    elif damage == "wrong_hash":
        expected_hash = {"reading": "0" * 64}
    elif damage == "nonbytes":
        members["reading"] = [True]  # type: ignore[list-item]
    if damage == "duplicate":

        class DuplicatedRole(Mapping[str, Iterable[bytes]]):
            def __iter__(self) -> Iterator[str]:
                return iter((*members, "reading"))

            def __len__(self) -> int:
                return 5

            def __getitem__(self, key: str) -> Iterable[bytes]:
                return members[key]

        provided: Mapping[str, Iterable[bytes]] = DuplicatedRole()
    else:
        provided = members
    with pytest.raises(ArtifactError):
        store.publish_artifact("extraction", provided, expected_sha256=expected_hash)
    assert store.list_artifacts() == ()
    assert tuple(map(len, registration_facts(database))) == (0, 0, 0)


def test_bounded_stream_inputs_are_consumed_as_segments(tmp_path: Path) -> None:
    from collections.abc import Iterator
    from io import BytesIO

    class BoundedReader(BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            assert size is not None and 0 < size <= 4096, "禁止无界读取"
            return super().read(size)

    def segments(stream: BoundedReader) -> Iterator[bytes]:
        while raw := stream.read(4096):
            yield raw

    values = {role: raw * 1000 for role, raw in PAYLOADS.items()}
    streams = {role: BoundedReader(raw) for role, raw in values.items()}
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    saved = store.publish_artifact(
        "extraction", {role: segments(stream) for role, stream in streams.items()}
    )
    assert store.read_artifact(saved.artifact_id) == values
    assert all(stream.tell() == len(values[role]) for role, stream in streams.items())


@pytest.mark.parametrize("variant", [False, True])
def test_independent_processes_publish_complete_shared_collections_concurrently(
    tmp_path: Path, variant: bool
) -> None:
    import os

    from tests.extraction_support import paused_extraction

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    root = tmp_path / "root"
    store = ArtifactStore(database, root)
    with (
        paused_extraction(database, root, "before_registration") as (
            first,
            release_first,
        ),
        paused_extraction(database, root, "before_registration", variant=variant) as (
            second,
            release_second,
        ),
    ):
        assert store.list_artifacts() == ()
        os.write(release_first, b"G")
        os.write(release_second, b"G")
        first_output, first_errors = first.communicate(timeout=15)
        second_output, second_errors = second.communicate(timeout=15)
        assert first.returncode == 0, first_errors
        assert second.returncode == 0, second_errors
    first_saved = json.loads(first_output)
    second_saved = json.loads(second_output)
    if variant:
        assert first_saved["artifact_id"] != second_saved["artifact_id"]
    else:
        assert first_saved == second_saved
    assert tuple(map(len, registration_facts(database))) == (
        (5, 2, 8) if variant else (4, 1, 4)
    )
    assert store.read_artifact(first_saved["artifact_id"]) == PAYLOADS
    expected_second = dict(PAYLOADS)
    if variant:
        expected_second["reading"] = b"PRIVATE_OTHER_READING"
    assert store.read_artifact(second_saved["artifact_id"]) == expected_second
    before = registration_facts(database)
    assert (
        store.publish_artifact("extraction", chunked(PAYLOADS)).created_at
        == first_saved["created_at"]
    )
    assert registration_facts(database) == before


@pytest.mark.parametrize(
    "phase",
    [
        "temporary",
        "partial_files",
        "before_registration",
        "member_rows",
        "before_commit",
    ],
)
@pytest.mark.parametrize("stop", ["exception", "kill"])
def test_every_multifile_interruption_preserves_history_and_allows_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    phase: str,
    stop: str,
) -> None:
    import os
    from collections.abc import Iterator
    from contextlib import nullcontext

    from tests.extraction_support import failed_registration, paused_extraction

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    root = tmp_path / "root"
    store = ArtifactStore(database, root)
    historical = store.publish_single("original_pdf", [b"PRIVATE_OLDER_PDF"])
    old_facts = registration_facts(database)
    error_text = ""
    if stop == "kill":
        with paused_extraction(database, root, phase) as (process, _):
            process.kill()
            process.wait(timeout=15)
    else:
        members = chunked(PAYLOADS)
        if phase == "temporary":

            def failing_chunks() -> Iterator[bytes]:
                yield b"PRI"
                raise OSError("PRIVATE_INPUT_FAILURE")

            members["document"] = failing_chunks()
        if phase == "partial_files":
            original_link = os.link
            calls = 0

            def fail_second_link(source: str | Path, target: str | Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("PRIVATE_LINK_FAILURE")
                original_link(source, target)

            monkeypatch.setattr(os, "link", fail_second_link)
        with (
            failed_registration(phase)
            if phase in ("before_registration", "member_rows", "before_commit")
            else nullcontext()
        ):
            with pytest.raises(ArtifactError) as failure:
                store.publish_artifact("extraction", members)
            error_text = str(failure.value)
        monkeypatch.undo()
    # 使用重开的服务查询持久化事实;所有旧事实与审计时间保持原值。
    restarted = ArtifactStore(database, root)
    published_files = [path for path in (root / "blobs").rglob("*") if path.is_file()]
    assert len(published_files) == {"temporary": 1, "partial_files": 2}.get(phase, 5)
    assert all(path.stat().st_mode & 0o777 == 0o400 for path in published_files)
    assert registration_facts(database) == old_facts
    assert restarted.list_artifacts() == (historical,)
    assert restarted.read_artifact(historical.artifact_id) == {
        "payload": b"PRIVATE_OLDER_PDF"
    }
    saved = restarted.publish_artifact("extraction", chunked(PAYLOADS))
    assert restarted.read_artifact(saved.artifact_id) == PAYLOADS
    assert tuple(map(len, registration_facts(database))) == (5, 2, 5)
    after = registration_facts(database)
    assert restarted.publish_artifact("extraction", chunked(PAYLOADS)) == saved
    assert registration_facts(database) == after
    assert "PRIVATE_" not in caplog.text + error_text


@pytest.mark.parametrize(
    "damage", ["missing", "same_length", "missing_role", "role", "hash", "symlink"]
)
def test_any_damaged_member_prevents_returning_the_collection_and_repair(
    tmp_path: Path, damage: str
) -> None:
    import sqlite3

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    root = tmp_path / "root"
    store = ArtifactStore(database, root)
    saved = store.publish_artifact("extraction", chunked(PAYLOADS))
    registered, blobs = store.artifact_blobs(saved.artifact_id)
    final_blob = blobs[-1]
    final_path = store.verified_blob_path(final_blob)
    assert registered.members[-1].role == "reading"
    sentinel = tmp_path / "outside"
    sentinel.write_bytes(b"PRIVATE_SENTINEL")
    if damage == "missing":
        final_path.unlink()
    elif damage == "same_length":
        final_path.chmod(0o600)
        final_path.write_bytes(b"X" * len(PAYLOADS["reading"]))
        final_path.chmod(0o400)
    elif damage == "symlink":
        final_path.unlink()
        final_path.symlink_to(sentinel)
    else:
        with sqlite3.connect(database) as connection:
            if damage == "missing_role":
                connection.execute("DELETE FROM artifact_members WHERE role='reading'")
            elif damage == "role":
                connection.execute(
                    "UPDATE artifact_members SET role='other' WHERE role='reading'"
                )
            elif damage == "hash":
                connection.execute(
                    "UPDATE artifact_members SET sha256=? WHERE role='reading'",
                    ("0" * 64,),
                )
    before = registration_facts(database)
    result = None
    with pytest.raises(ArtifactError):
        result = store.read_artifact(saved.artifact_id)
    assert result is None
    with pytest.raises(ArtifactError):
        store.publish_artifact("extraction", chunked(PAYLOADS))
    assert registration_facts(database) == before
    assert sentinel.read_bytes() == b"PRIVATE_SENTINEL"
    if damage == "missing":
        assert not final_path.exists()
    elif damage == "same_length":
        assert final_path.read_bytes() == b"X" * len(PAYLOADS["reading"])
    elif damage == "symlink":
        assert final_path.is_symlink()
