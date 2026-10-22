"""关系写入的真实进程并发和强杀恢复。"""

import json
import os
import sys
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.a3_process_support import paused_subprocess
from tests.test_paper_service import observation
from tests.test_version_relations import relation

WRITE = (
    "from pathlib import Path; import sys; from paper_radar.papers import PaperFacts; "
    "from tests.test_paper_service import observation; "
    "from tests.test_version_relations import relation; "
    "print(PaperFacts(Path(sys.argv[1]),Path(sys.argv[2])).submit("
    "observation(doi='10.1/journal',relations=relation('has-preprint'))).model_dump_json())"
)


def paused(db: Path, phase: str):  # type: ignore[no-untyped-def]
    return paused_subprocess(
        [sys.executable, "-c", WRITE, str(db), str(db.parent / "data")],
        Path(__file__).parent / "version_relation_process",
        {"RELATION_PAUSE": phase},
        "关系进程未到屏障",
        "关系进程提前退出",
    )


@pytest.mark.parametrize(
    "phase", ["begin", "version", "selection", "relation", "committed"]
)
def test_kill_in_relation_version_or_selection_transaction_is_retry_safe(
    tmp_path: Path, phase: str
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    assert pre.paper_id
    with paused(db, phase) as (process, _):
        process.kill()
        process.wait(timeout=15)
    service.validate_all()
    request = observation(doi="10.1/journal", relations=relation("has-preprint"))
    final = service.submit(request)
    assert final.paper_id == pre.paper_id and final.status == "retained"
    assert service.submit(request) == final
    trace = service.trace(pre.paper_id, verify_source_bytes=True)
    assert len(trace.relations) == 1
    assert len(trace.versions) == len(trace.selections) == 2
    assert trace.current.version_id == final.version_id
    service.validate_all()


def test_concurrent_observers_preserve_single_doi_relation_and_upgrade(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    assert pre.paper_id
    with (
        paused(db, "ready") as (one, release_one),
        paused(db, "ready") as (two, release_two),
    ):
        os.write(release_one, b"G")
        os.write(release_two, b"G")
        outputs = [process.communicate(timeout=20) for process in (one, two)]
        assert one.returncode == two.returncode == 0, outputs
    first, second = (json.loads(output[0]) for output in outputs)
    assert first == second
    trace = service.trace(pre.paper_id)
    assert (
        len(trace.relations) == 1 and len(trace.versions) == len(trace.selections) == 2
    )
    service.validate_all()


def test_relation_lock_wait_is_bounded_and_has_no_partial_success(
    tmp_path: Path,
) -> None:
    import sqlite3
    from contextlib import closing

    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    assert pre.paper_id
    before = service.trace(pre.paper_id)
    with (
        paused(db, "ready") as (process, release),
        closing(sqlite3.connect(db)) as owner,
    ):
        owner.execute("BEGIN IMMEDIATE")
        os.write(release, b"G")
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert json.loads(stdout)["reason"] == "database_busy"
        owner.rollback()
    assert service.trace(pre.paper_id) == before
    assert (
        service.submit(
            observation(doi="10.1/journal", relations=relation("has-preprint"))
        ).paper_id
        == pre.paper_id
    )
