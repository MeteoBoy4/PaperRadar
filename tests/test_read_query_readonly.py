"""D1 真只读连接、共享visibility及历史资格分离。"""

import hashlib
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, event

from paper_radar.calibration import visibility
from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadTaskError, ReadTasks
from tests.pi_rpc_source_support import NOW
from tests.read_queries_support import successful
from tests.read_tasks_support import ready


def test_all_query_entries_use_visibility_and_zero_write_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root, clock=lambda: NOW)
    result = successful(tasks, data, extraction.fingerprint, "read")
    pending = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="pending",
        output_language="en",
    )
    tasks.claim(pending.task_id)
    before_task = tasks.task(pending.task_id)
    before_hash = hashlib.sha256(data.database.read_bytes()).hexdigest()
    assembled: list[frozenset[visibility.HiddenCondition]] = []
    shared = visibility.evaluate_visibility

    def observe(hidden: frozenset[visibility.HiddenCondition]) -> visibility.Visibility:
        assembled.append(hidden)
        return shared(hidden)

    monkeypatch.setattr(visibility, "evaluate_visibility", observe)
    original = sqlite3.connect
    opened: list[str] = []

    def readonly(database: str, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        assert "mode=ro" in database
        opened.append(database)
        connection = original(database, *args, **kwargs)
        assert isinstance(connection, sqlite3.Connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", readonly)

    def sql_guard(
        _connection: object, _cursor: object, statement: str, *_args: object
    ) -> None:
        assert statement.lstrip().split()[0].upper() not in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "ALTER",
            "DROP",
            "REPLACE",
            "VACUUM",
            "ATTACH",
        }

    event.listen(Engine, "before_cursor_execute", sql_guard)
    try:
        query = ReadQueries(data.database, data.data_root)
        operations: list[Callable[[], object]] = [
            lambda: query.current(data.paper_id, snapshot_id=data.snapshot_id),
            lambda: query.analysis(result.analysis_id, snapshot_id=data.snapshot_id),
            lambda: query.history(data.paper_id),
            lambda: query.old_configurations(
                (data.paper_id,), snapshot_id=data.snapshot_id
            ),
            lambda: query.evidence(result.analysis_id, "e000002"),
        ]
        for operation in operations:
            assembled.clear()
            operation()
            assert assembled and all(h == frozenset() for h in assembled)
        denied: list[Callable[[], object]] = [
            lambda: query.current(data.paper_id, ordinary=True),
            lambda: query.analysis(result.analysis_id, ordinary=True),
            lambda: query.history(data.paper_id, ordinary=True),
            lambda: query.old_configurations((data.paper_id,), ordinary=True),
            lambda: query.evidence(result.analysis_id, "e000002", ordinary=True),
        ]
        for operation in denied:
            with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
                operation()
        assert tasks.task(pending.task_id) == before_task
        assert opened
    finally:
        event.remove(Engine, "before_cursor_execute", sql_guard)
    assert hashlib.sha256(data.database.read_bytes()).hexdigest() == before_hash


def test_later_decision_quality_and_metadata_do_not_erase_legal_history(
    tmp_path: Path,
) -> None:
    import httpx

    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.papers import PaperFacts
    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )
    from tests.body_support import CHECKS, PDF, Parser
    from tests.test_paper_service import observation

    data, body, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    analysis = successful(tasks, data, extraction.fingerprint, "read")
    query = ReadQueries(data.database, data.data_root)
    PaperFacts(data.database, data.data_root).submit(
        observation(
            query_key="bookkeeping",
            payload=b"bookkeeping",
            fields={
                "volume": {"value": "42", "locator": "volume"},
                "pages": {"value": "1-9", "locator": "pages"},
            },
        )
    )
    assert query.current(data.paper_id).analyses[0].body_status == "current"
    metadata = JGRMetadata(
        data.database,
        data.data_root,
        http=SourceHTTPExecutor(
            transport=httpx.MockTransport(lambda _: httpx.Response(403))
        ),
    )
    assert not metadata.enrich(
        data.paper_id, request_id="later-metadata", contact_email="contact@example.org"
    ).minimum_complete
    body.decide(
        data.paper_id,
        ScreeningReasonInput(
            result=ScreeningResult.DENIED,
            source=ScreeningSource.DIRECT_MANUAL_DECISION,
            reason=DecisionReason.OUT_OF_SCOPE,
        ),
        request_id="later-deny",
        actor="human",
    )
    assert extraction.identity is not None
    body.review_layout(
        extraction.identity,
        passed=False,
        checks={**CHECKS, "provenance": False},
        note="later veto",
        actor="human",
        request_id="later-veto",
    )
    assert query.analysis(analysis.analysis_id).body_status == "current"
    assert query.analysis(analysis.analysis_id).quality_basis == "failed"
    pdf = body.attach_pdf(data.paper_id, PDF + b"updated", request_id="new-pdf")
    body.freeze_sample(
        data.paper_id,
        feed_id=body.samples(data.paper_id)[0].feed_id,
        pdf_sha256=pdf.pdf_sha256,
        reason="new sample",
        request_id="later-sample",
    )
    second = body.extract(data.paper_id, snapshot_id=data.snapshot_id, parser=Parser())
    assert second.identity is not None and second.identity != extraction.identity
    assert query.current(data.paper_id).state == "no_analysis"
    historical = query.analysis(analysis.analysis_id, snapshot_id=data.snapshot_id)
    assert (
        historical.body_status == "historical" and historical.config_status == "current"
    )
    assert query.history(data.paper_id)[0].analysis_id == analysis.analysis_id
    assert (
        query.evidence(analysis.analysis_id, "e000002")[0].text == "Exact source α = 2."
    )
    body.attach_pdf(data.paper_id, PDF, request_id="return-to-old-pdf")
    assert query.current(data.paper_id).analyses[0].analysis_id == analysis.analysis_id
    tasks.validate_all()
