"""待登记 DOI 的关系角色在写入和隔离恢复中保持一致。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.backup.restore_contract import RestoreError
from paper_radar.papers import PaperError, PaperFacts, WriteResult
from paper_radar.storage.database import upgrade_database
from tests.test_paper_service import observation


def link(pre: str, journal: str) -> tuple[dict[str, str], ...]:
    return (
        {
            "kind": "is-preprint-of",
            "source_doi": pre,
            "target_doi": journal,
            "locator": "relation",
        },
    )


def pending(service: PaperFacts, pre: str, journal: str) -> WriteResult:
    return service.submit(
        observation(
            doi=pre,
            version_kind="preprint",
            fields={},
            relations=link(pre, journal),
            payload=f"{pre}->{journal}".encode(),
        )
    )


@pytest.fixture
def service(tmp_path: Path) -> PaperFacts:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    return PaperFacts(database, tmp_path / "data")


def business_rows(database: Path) -> list[str]:
    with closing(sqlite3.connect(database)) as connection:
        return [
            line
            for line in connection.iterdump()
            if line.startswith('INSERT INTO "paper')
        ]


@pytest.mark.parametrize("reverse", [False, True])
def test_cross_request_role_conflict_is_atomic_and_original_role_can_register(
    service: PaperFacts,
    reverse: bool,
) -> None:
    first, second = (("10.1/a", "10.1/b"), ("10.1/b", "10.1/c"))
    if reverse:
        first, second = second, first
    retained = pending(service, *first)
    assert retained.status == "retained"
    before = business_rows(service.database)
    rejected = pending(service, *second)
    assert (rejected.status, rejected.reason) == (
        "rejected",
        "invalid_relation",
    )
    assert business_rows(service.database) == before
    registered = service.submit(
        observation(
            doi="10.1/b",
            version_kind="preprint" if reverse else "journal",
            payload=b"B title",
            fields={"title": {"value": "B", "locator": "title"}},
        )
    )
    assert registered.status == "retained" and registered.paper_id
    trace = service.trace(registered.paper_id, verify_source_bytes=True)
    assert len(trace.relations) == 1
    assert trace.relations[0].state == "endpoint_missing"
    service.validate_all()


def test_single_request_chain_stays_rejected(service: PaperFacts) -> None:
    before = business_rows(service.database)
    result = service.submit(
        observation(
            doi="10.1/b",
            version_kind="preprint",
            fields={},
            relations=link("10.1/a", "10.1/b") + link("10.1/b", "10.1/c"),
        )
    )
    assert (result.status, result.reason) == ("rejected", "invalid_relation")
    assert business_rows(service.database) == before


def test_multiple_pending_relations_with_same_role_are_legal(
    service: PaperFacts,
) -> None:
    assert pending(service, "10.1/a", "10.1/b").status == "retained"
    assert pending(service, "10.1/d", "10.1/b").status == "retained"
    registered = service.submit(observation(doi="10.1/b"))
    assert registered.paper_id
    assert len(service.trace(registered.paper_id).relations) == 2
    service.validate_all()


def contradict(database: Path) -> None:
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE paper_version_relations SET journal_doi='10.1/a' "
            "WHERE preprint_doi='10.1/d'"
        )
        connection.execute(
            "UPDATE paper_relation_references SET raw_target_doi='10.1/a' "
            "WHERE raw_source_doi='10.1/d'"
        )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()


def test_pending_role_corruption_is_rejected_without_repair(
    service: PaperFacts,
    tmp_path: Path,
) -> None:
    assert pending(service, "10.1/a", "10.1/b").status == "retained"
    assert pending(service, "10.1/d", "10.1/c").status == "retained"
    assert service.data_root
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    copied = batch.batch_dir / "database.sqlite3"
    contradict(copied)
    manifest_path = batch.batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = copied.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    )
    before = {
        path.relative_to(batch.batch_dir): path.read_bytes()
        for path in batch.batch_dir.rglob("*")
        if path.is_file()
    }
    with pytest.raises(BackupError) as failure:
        verify_backup(batch.batch_dir)
    assert failure.value.reason == "registration_invalid"
    with pytest.raises(RestoreError) as restore_failure:
        restore_backup(batch.batch_dir, tmp_path / "restored")
    assert restore_failure.value.reason == "registration_invalid"
    assert not (tmp_path / "restored").exists()
    assert before == {
        path.relative_to(batch.batch_dir): path.read_bytes()
        for path in batch.batch_dir.rglob("*")
        if path.is_file()
    }
    contradict(service.database)
    original = business_rows(service.database)
    materials = {
        path.relative_to(service.data_root): path.read_bytes()
        for path in service.data_root.rglob("*")
        if path.is_file()
    }
    with pytest.raises(PaperError, match="corrupt_reference") as read_failure:
        service.validate_all()
    assert read_failure.value.reason == "corrupt_reference"
    with pytest.raises(BackupError) as create_failure:
        create_backup(service.database, service.data_root, tmp_path / "bad-backups")
    assert create_failure.value.reason == "registration_invalid"
    assert business_rows(service.database) == original
    assert materials == {
        path.relative_to(service.data_root): path.read_bytes()
        for path in service.data_root.rglob("*")
        if path.is_file()
    }
