"""活跃 WAL 组合库在断绝源目录后隔离恢复、搬迁与跨进程历史重建。"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from tests.paper_recovery_reader import digest
from tests.paper_recovery_support import paper_expectations, populated, tree_hash
from tests.test_paper_service import observation


def child(request: dict[str, object], cwd: Path, seed: str) -> dict[str, object]:
    repository = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-m", "tests.paper_recovery_reader"],
        input=json.dumps(request),
        cwd=cwd,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": seed,
            "PYTHONPATH": os.pathsep.join(
                (str(repository / "tests/deny_network"), str(repository))
            ),
        },
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert "PRIVATE-RECOVERY" not in completed.stdout + completed.stderr
    result: dict[str, object] = json.loads(completed.stdout)
    return result


@pytest.mark.parametrize("journal_abstract", [True, False])
def test_complete_wal_history_survives_denied_sources_and_moved_restore(
    tmp_path: Path,
    journal_abstract: bool,
    record_property: Callable[[str, object], None],
) -> None:
    facts = populated(tmp_path / "source", journal_abstract=journal_abstract)
    service = facts.service
    assert service.data_root and facts.pre.paper_id
    with closing(sqlite3.connect(service.database)) as wal:
        wal.execute("PRAGMA wal_autocheckpoint=0")
        wal.execute("SELECT count(*) FROM papers")
        assert (
            service.submit(
                observation(
                    doi="10.74/pre",
                    version_kind="preprint",
                    payload=b"late WAL bibliographic transaction",
                    fields={"volume": {"value": "74", "locator": "volume"}},
                )
            ).status
            == "retained"
        )
        # The final real transaction exists in a live WAL when the online
        # snapshot is made.
        assert (
            service.database.with_name(service.database.name + "-wal").stat().st_size
            > 0
        )
        expected = paper_expectations(facts)
        source_before = digest(tuple(wal.iterdump()))
        batch = create_backup(
            service.database, service.data_root, tmp_path / "source-backups"
        )
        assert verify_backup(batch.batch_dir) == batch
        with closing(
            sqlite3.connect(
                f"file:{batch.batch_dir / 'database.sqlite3'}?mode=ro",
                uri=True,
            )
        ) as copied:
            assert digest(tuple(copied.iterdump())) == source_before
        assert digest(tuple(wal.iterdump())) == source_before
    portable = tmp_path / "portable" / batch.batch_dir.name
    shutil.copytree(batch.batch_dir, portable)
    original = tmp_path / "source"
    inaccessible = tmp_path / "unavailable-source"
    original.rename(inaccessible)
    original_backups = tmp_path / "source-backups"
    unavailable_backups = tmp_path / "unavailable-backups"
    original_backups.rename(unavailable_backups)
    forbidden = [
        str(path)
        for path in (original, inaccessible, original_backups, unavailable_backups)
    ]
    before = tree_hash(portable)
    target = tmp_path / "restored"
    restored = child(
        {
            "mode": "restore",
            "batch": str(portable),
            "target": str(target),
            "forbidden": forbidden,
        },
        tmp_path,
        "5",
    )
    assert restored["manifest"] == batch.manifest_sha256
    moved = tmp_path / "moved"
    target.rename(moved)
    request: dict[str, object] = {
        "mode": "read",
        "root": str(moved),
        "papers": expected,
        "mappings": facts.mappings,
        "forbidden": [
            *forbidden,
            str(portable.parent),
            str(target),
            str(moved / "blobs"),
        ],
    }
    # Child requests have no original title/abstract, payload, candidate text or
    # config object.
    assert "PRIVATE-RECOVERY" not in json.dumps(request)
    with closing(sqlite3.connect(moved / "database.sqlite3")) as connection:
        dump = digest(tuple(connection.iterdump()))
    recovered_before = tree_hash(moved, ignore_sqlite_sidecars=True)
    elsewhere = tmp_path / "unrelated-cwd"
    elsewhere.mkdir()
    first = child(request, tmp_path, "1")
    second = child(request, elsewhere, "999")
    assert first["traces"] == second["traces"]
    assert first["mappings"] == second["mappings"]
    record_property(
        "process_io",
        json.dumps(
            {
                "restore": restored["io"],
                "read_1": first["io"],
                "read_2": second["io"],
            },
            sort_keys=True,
        ),
    )
    assert first["mappings"] == len(facts.mappings)
    with closing(sqlite3.connect(moved / "database.sqlite3")) as connection:
        assert digest(tuple(connection.iterdump())) == dump
    assert tree_hash(portable) == before
    assert tree_hash(moved, ignore_sqlite_sidecars=True) == recovered_before
