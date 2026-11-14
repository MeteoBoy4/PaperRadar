"""D1: 实际 Read claim 统一选择权威,保留在途依据和预算。"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, current_thread

import pytest
from sqlalchemy import Connection, Engine, event

from paper_radar.body import BodyService
from paper_radar.read_tasks import ReadTaskError, ReadTasks
from tests.body_selection_support import choose, second_body
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def test_claim_rechecks_selection_without_spending_attempt_and_inflight_keeps_basis(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    layout = fixture.layout
    root = layout.extraction.root
    paper = layout.extraction.prepared.paper_id
    tasks = ReadTasks(root.database, root.data_root)
    old = layout.identity
    task = tasks.register(
        paper,
        snapshot_id=fixture.snapshot,
        extraction_fingerprint=old.extraction_fingerprint,
        request_id="old-running",
    )
    handle = tasks.claim(task.task_id)
    claimed = tasks.task(task.task_id)
    basis = claimed.attempts[0].basis
    new = second_body(layout)
    assert choose(layout).exit_code == 0
    other = tasks.register(
        paper,
        snapshot_id=fixture.snapshot,
        extraction_fingerprint=old.extraction_fingerprint,
        output_language="en",
        request_id="old-waiting",
    )
    waiting, release = Event(), Event()

    def pause(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement == "BEGIN IMMEDIATE" and current_thread().name.startswith(
            "read-claim"
        ):
            waiting.set()
            assert release.wait(30)

    event.listen(Engine, "before_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(1, thread_name_prefix="read-claim") as pool:
            future = pool.submit(tasks.claim, other.task_id)
            try:
                assert waiting.wait(30)
                layout.identity = new
                assert choose(layout, request="select-new").exit_code == 0
            finally:
                release.set()
            with pytest.raises(ReadTaskError) as error:
                future.result(timeout=30)
            assert error.value.reason == "prerequisites_failed"
            assert "facts_changed" in error.value.reasons
    finally:
        event.remove(Engine, "before_cursor_execute", pause)
    assert tasks.task(other.task_id).attempts == ()
    assert tasks.task(other.task_id).remaining_attempts == 2
    assert tasks.task(task.task_id) == claimed
    settled = tasks.fail(handle, "timeout")
    assert settled.attempts[0].basis == basis
    assert settled.identity == old and settled.remaining_attempts == 1
    body = BodyService(root.database, root.data_root)
    assert body.current_body(paper).identity == new
    assert (
        "ordinary_consumption_denied"
        in body.facts(paper, identity=new, ordinary=True).reasons
    )
    tasks.validate_all()
