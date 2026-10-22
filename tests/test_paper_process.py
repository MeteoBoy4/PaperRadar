"""公共服务的确定进程交错、强杀、忙锁和一致读。"""

import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from tests.a3_process_support import paused_subprocess
from tests.test_paper_service import observation

WRITE = (
    "from pathlib import Path; import sys; from paper_radar.papers im"
    "port PaperFacts; from tests.test_paper_service import observatio"
    "n; print(PaperFacts(Path(sys.argv[1]),Path(sys.argv[2])).submit("
    "observation()).model_dump_json())"
)
READ = (
    "from pathlib import Path; import sys; from paper_radar.papers imp"
    "ort PaperFacts; print(PaperFacts(Path(sys.argv[1]),Path(sys.argv["
    "2])).trace(sys.argv[3]).model_dump_json())"
)


def paused(database: Path, phase: str, *, paper_id: str | None = None):  # type: ignore[no-untyped-def]
    return paused_subprocess(
        [
            sys.executable,
            "-c",
            READ if paper_id else WRITE,
            str(database),
            str(database.parent / "data"),
            *([paper_id] if paper_id else []),
        ],
        Path(__file__).parent / "paper_process",
        {"PAPER_PAUSE": phase},
        "论文进程未到达屏障",
        "论文进程提前退出",
    )


def test_two_processes_register_one_complete_identity(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    with (
        paused(database, "begin") as (one, release_one),
        paused(database, "begin") as (two, release_two),
    ):
        os.write(release_one, b"G")
        os.write(release_two, b"G")
        outputs = [process.communicate(timeout=20) for process in (one, two)]
        assert one.returncode == two.returncode == 0, outputs
    first, second = [json.loads(output[0]) for output in outputs]
    assert first == second
    trace = PaperFacts(database, tmp_path / "data").trace(first["paper_id"])
    assert (
        len(trace.versions)
        == len(trace.observations)
        == len(trace.revisions)
        == len(trace.selections)
        == 1
    )


@pytest.mark.parametrize("phase", ["published", "middle", "committed"])
def test_kill_at_each_publication_boundary_recovers_without_half_facts(
    tmp_path: Path, phase: str
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    with paused(database, phase) as (process, _):
        assert len(ArtifactStore(database, tmp_path / "data").list_artifacts()) == 1
        process.kill()
        process.wait(timeout=15)
    PaperFacts(database, tmp_path / "data").validate_all()
    result = PaperFacts(database, tmp_path / "data").submit(observation())
    assert result.status == "retained" and result.paper_id
    trace = PaperFacts(database, tmp_path / "data").trace(
        result.paper_id, verify_source_bytes=True
    )
    assert (
        len(trace.versions)
        == len(trace.observations)
        == len(trace.revisions)
        == len(trace.selections)
        == 1
    )


def test_other_process_write_lock_returns_database_busy_and_can_retry(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    # The separate child has reached the write boundary before the owner takes
    # the lock; the handshake removes timing guesses and needs no sleep.
    with (
        paused(database, "begin") as (process, release),
        closing(sqlite3.connect(database)) as owner,
    ):
        owner.execute("BEGIN IMMEDIATE")
        os.write(release, b"G")
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert json.loads(stdout)["reason"] == "database_busy"
        assert owner.execute("SELECT count(*) FROM papers").fetchone() == (0,)
        owner.rollback()
    assert (
        PaperFacts(database, tmp_path / "data").submit(observation()).status
        == "retained"
    )


def test_read_view_does_not_mix_a_commit_between_its_selects(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    result = service.submit(observation())
    assert result.paper_id
    with paused(database, "read", paper_id=result.paper_id) as (reader, release):
        updated = service.submit(
            observation(
                observed_at=datetime(2026, 1, 2, tzinfo=UTC),
                payload=b"updated",
                fields={"title": {"value": "New title", "locator": "title"}},
            )
        )
        assert updated.status == "retained"
        os.write(release, b"G")
        stdout, stderr = reader.communicate(timeout=15)
        assert reader.returncode == 0, stderr
        frozen = json.loads(stdout)
    assert frozen["current"]["revision_no"] == 1
    assert len(frozen["observations"]) == 1
    assert service.show(result.paper_id).revision_no == 2
