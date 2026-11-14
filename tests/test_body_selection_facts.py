"""D1: 正文选择服务故障、只追加历史与当前绑定。"""

import json
import sqlite3
from itertools import chain
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, event
from sqlalchemy.exc import OperationalError

from paper_radar.body import BodyService
from paper_radar.body.models import BodyError
from paper_radar.body.selection import BodySelections
from paper_radar.experiment.body_selection import SelectBody
from paper_radar.experiment.layout import LayoutBody, Materials
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.papers import PaperFacts
from tests.artifact_support import fail_sql
from tests.body_selection_support import choose, second_body
from tests.experiment_layout_support import layout_fixture
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed


def test_exact_replay_supersession_append_only_and_old_veto_are_preserved(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    body = BodyService(root.database, root.data_root)
    old = fixture.identity
    fixture.review(passed=False, request="old-veto")
    new = second_body(fixture)
    before = body.extractions(fixture.extraction.prepared.paper_id)
    fixture.identity = new
    first = choose(fixture)
    assert first.exit_code == 0, first.output
    replay = choose(fixture)
    assert replay.exit_code == 0, replay.output
    original = json.loads(first.stdout)
    repeated = json.loads(replay.stdout)
    assert original | {"replayed": True} == repeated
    fixture.identity = old
    conflict = choose(fixture)
    assert conflict.exit_code == 2 and "request_conflict" in conflict.output
    assert choose(fixture, request="choose-old").exit_code == 0
    assert body.current_body(fixture.extraction.prepared.paper_id).identity == old
    denied = invoke(
        *fixture.args("layout-review"),
        "--reviewer",
        "owner",
        "--recorder",
        "agent",
        "--request-id",
        "cannot-clear",
        *chain.from_iterable(
            (
                ["--" + c, "true"]
                for c in [
                    "body-boundary",
                    "reading-order",
                    "sections",
                    "headers-footers",
                    "provenance",
                    "restricted-content",
                ]
            ),
        ),
    )
    assert denied.exit_code == 2 and "layout_conflict" in denied.output
    fixture.identity = new
    assert choose(fixture, request="choose-new-again").exit_code == 0
    assert body.extractions(fixture.extraction.prepared.paper_id) == before
    selections = BodySelections(root.database, root.data_root).history()
    assert [r.sequence for r in selections] == [1, 2, 3]
    assert [r.identity for r in selections] == [new, old, new]
    assert body.current_body(fixture.extraction.prepared.paper_id).identity == new
    for statement in (
        "UPDATE body_selections SET recorder='agent'",
        "DELETE FROM body_selections",
        "INSERT OR REPLACE INTO body_selections SELECT * FROM body_selections",
    ):
        with (
            sqlite3.connect(root.database) as connection,
            pytest.raises(sqlite3.IntegrityError, match="append_only"),
        ):
            connection.execute(statement)
    body.validate_all()


def test_materials_and_owner_review_consume_selected_identity_without_pdf_parser(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.experiment import layout_rendering

    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    old = fixture.identity
    fixture.identity = second_body(fixture)
    assert choose(fixture).exit_code == 0
    seen = []

    def render(root: ExperimentRoot, body: LayoutBody) -> str:
        seen.append(body.view.identity)
        assert body.loaded.context.identity == fixture.identity
        return "layout-synthetic/index.html"

    monkeypatch.setattr(layout_rendering, "render_materials", render)
    Materials(fixture.extraction.root).generate(
        fixture.extraction.prepared.paper_id, fixture.identity
    )
    assert seen == [fixture.identity]
    review = fixture.review()
    assert review["fingerprint"] == fixture.identity.extraction_fingerprint
    fixture.identity = old
    wrong = invoke(*fixture.args("layout-materials"))
    assert wrong.exit_code == 2 and "body_identity_mismatch" in wrong.output
    assert seen != [old]


@pytest.mark.parametrize("failure", ["insert", "commit"])
def test_selection_write_fault_rolls_back_entire_fact(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root

    def commit(connection: Connection) -> None:
        if connection.exec_driver_sql(
            "SELECT count(*) FROM body_selections"
        ).scalar_one():
            raise OperationalError("commit", {}, Exception("PRIVATE_COMMIT_FAILURE"))

    if failure == "insert":
        with fail_sql("INSERT INTO body_selections"):
            result = choose(fixture)
    else:
        event.listen(Engine, "commit", commit)
        try:
            result = choose(fixture)
        finally:
            event.remove(Engine, "commit", commit)
    assert result.exit_code == 2 and "database_failed" in result.output
    assert "PRIVATE_COMMIT_FAILURE" not in result.output
    assert BodySelections(root.database, root.data_root).history() == ()
    assert choose(fixture).exit_code == 0


def test_invalid_identity_roles_visibility_and_corrupt_members_never_append(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.calibration.visibility import (
        Visibility,
        VisibilityCapability,
        VisibilityPermission,
    )
    from paper_radar.reading.context import ExtractionIdentity
    from paper_radar.storage.artifact_contract import blob_relative_path

    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    body = BodyService(root.database, root.data_root)
    original = fixture.identity
    for identity in (
        ExtractionIdentity(
            "f" * 64, original.reading_sha256, original.evidence_map_sha256
        ),
        ExtractionIdentity(
            original.extraction_fingerprint, "f" * 64, original.evidence_map_sha256
        ),
    ):
        fixture.identity = identity
        rejected = choose(fixture)
        assert rejected.exit_code == 2 and "facts_changed" in rejected.output
    fixture.identity = original
    for selector, recorder in (("agent", "agent"), ("owner", "owner")):
        rejected = invoke(
            *fixture.args("body-select"),
            "--selector",
            selector,
            "--recorder",
            recorder,
            "--request-id",
            "invalid-role",
        )
        assert (
            rejected.exit_code == 2
            and "owner_authorization_required" in rejected.output
        )
    original_permission = Visibility.permission

    def denied(
        self: Visibility, capability: VisibilityCapability
    ) -> VisibilityPermission:
        return (
            VisibilityPermission.DENIED
            if capability is VisibilityCapability.SET_DECISION
            else original_permission(self, capability)
        )

    with monkeypatch.context() as hidden:
        hidden.setattr(Visibility, "permission", denied)
        result = choose(fixture)
    assert result.exit_code == 2 and "visibility_denied" in result.output
    view = body.extraction(original.extraction_fingerprint)
    assert view and view.artifact_id
    artifact = body.store.get_artifact(view.artifact_id)
    member = next(m for m in artifact.members if m.role == "reading")
    path = root.data_root / blob_relative_path(member.sha256)
    before = path.read_bytes()
    mode = path.stat().st_mode
    path.chmod(0o600)
    path.write_bytes(b"damaged synthetic member")
    rejected = choose(fixture)
    assert rejected.exit_code == 2 and "corrupt_reference" in rejected.output
    path.write_bytes(before)
    path.chmod(mode)
    assert BodySelections(root.database, root.data_root).history() == ()
    assert choose(fixture).exit_code == 0


def test_metadata_revision_invalidates_binding_without_changing_history(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    fixture.identity = second_body(fixture)
    assert choose(fixture).exit_code == 0
    history = BodySelections(root.database, root.data_root).history()
    paper = fixture.extraction.prepared.paper_id
    papers = PaperFacts(root.database, root.data_root)
    current = papers.show(paper)
    assert (
        papers.correct(
            dict(
                version_id=current.version_id,
                request_id="revision",
                actor="owner",
                reason="synthetic correction",
                fields={
                    "title": {"value": "Corrected title", "locator": "manual/title"}
                },
            )
        ).status
        == "retained"
    )
    assert (
        BodyService(root.database, root.data_root).current_body(paper).reason
        == "ambiguous_extractions"
    )
    assert BodySelections(root.database, root.data_root).history() == history
    rejected = choose(fixture, request="after-change")
    assert rejected.exit_code == 2 and "frozen_version_changed" in rejected.output


@pytest.mark.parametrize("change", ["selection", "revision", "visibility"])
def test_selection_rechecks_current_facts_after_lock_wait(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    from paper_radar.calibration.visibility import (
        Visibility,
        VisibilityCapability,
        VisibilityPermission,
    )
    from paper_radar.experiment.pdf import PdfError
    from tests.test_experiment_selection_cli import select

    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
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
            "body-select"
        ):
            waiting.set()
            assert release.wait(30)

    event.listen(Engine, "before_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(1, thread_name_prefix="body-select") as pool:
            future = pool.submit(
                SelectBody(root).record,
                fixture.extraction.prepared.paper_id,
                fixture.identity,
                selector="owner",
                recorder="agent",
                request_id="waiting",
            )
            try:
                assert waiting.wait(30)
                if change == "selection":
                    replaced = select(
                        root.root,
                        fixture.extraction.prepared.view_id,
                        "replacement",
                        "--position",
                        "2",
                        "--replaces",
                        fixture.extraction.prepared.selection_id,
                        "--replacement-reason",
                        "synthetic replacement",
                    )
                    assert replaced.exit_code == 0, replaced.output
                elif change == "revision":
                    papers = PaperFacts(root.database, root.data_root)
                    current = papers.show(fixture.extraction.prepared.paper_id)
                    assert (
                        papers.correct(
                            dict(
                                version_id=current.version_id,
                                request_id="revision",
                                actor="owner",
                                reason="synthetic correction",
                                fields={
                                    "title": {
                                        "value": "Corrected title",
                                        "locator": "manual/title",
                                    }
                                },
                            )
                        ).status
                        == "retained"
                    )
                else:
                    original = Visibility.permission

                    def hidden(
                        self: Visibility, capability: VisibilityCapability
                    ) -> VisibilityPermission:
                        return (
                            VisibilityPermission.DENIED
                            if capability is VisibilityCapability.SET_DECISION
                            else original(self, capability)
                        )

                    monkeypatch.setattr(Visibility, "permission", hidden)
            finally:
                release.set()
            with pytest.raises((PdfError, BodyError)) as error:
                future.result(timeout=30)
            assert isinstance(error.value, PdfError | BodyError)
            assert (
                error.value.reason
                == {
                    "selection": "selection_changed",
                    "revision": "frozen_version_changed",
                    "visibility": "visibility_denied",
                }[change]
            )
    finally:
        event.remove(Engine, "before_cursor_execute", pause)
    assert BodySelections(root.database, root.data_root).history() == ()


def test_failed_extraction_and_replaced_pdf_cannot_be_selected(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.docling_execution.models import WorkerResponse
    from paper_radar.reading.context import ExtractionIdentity
    from tests.body_selection_support import configure_another_extraction
    from tests.experiment_extract_support import executor
    from tests.experiment_layout_support import synthetic_pdf
    from tests.test_experiment_pdf_cli import attach

    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    body = BodyService(root.database, root.data_root)
    old = fixture.identity
    assert choose(fixture).exit_code == 0
    history = BodySelections(root.database, root.data_root).history()
    configure_another_extraction(fixture)
    executor(monkeypatch, WorkerResponse(failure="timeout"))
    failed = fixture.extraction.extract()
    assert failed.exit_code == 2 and "timeout" in failed.output
    views = body.extractions(fixture.extraction.prepared.paper_id)
    failure = next(v for v in views if v.fingerprint != old.extraction_fingerprint)
    assert failure.identity is None and failure.remaining_attempts == 1
    fixture.identity = ExtractionIdentity(
        failure.fingerprint, old.reading_sha256, old.evidence_map_sha256
    )
    refused = choose(fixture, request="failed-extraction")
    assert refused.exit_code == 2 and "facts_changed" in refused.output
    fixture.identity = old
    changed = attach(
        fixture.extraction.prepared,
        tmp_path,
        request="replacement-pdf",
        raw=synthetic_pdf() + b"% another synthetic PDF\n",
    )
    assert changed.exit_code == 0, changed.output
    refused = choose(fixture, request="wrong-pdf")
    assert refused.exit_code == 2 and "facts_changed" in refused.output
    assert (
        body.current_body(fixture.extraction.prepared.paper_id).reason
        == "extraction_absent"
    )
    assert BodySelections(root.database, root.data_root).history() == history
    assert body.extraction(failure.fingerprint) == failure


def test_concurrent_exact_requests_append_once_and_sequence_ignores_wall_clock(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime

    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    service = SelectBody(root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))

    def record() -> dict[str, object]:
        return service.record(
            fixture.extraction.prepared.paper_id,
            fixture.identity,
            selector="owner",
            recorder="agent",
            request_id="same-request",
        )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: record(), range(2)))
    assert [r["replayed"] for r in results] in ([False, True], [True, False])
    first = BodySelections(root.database, root.data_root).history()
    assert len(first) == 1 and first[0].sequence == 1
    earlier = SelectBody(root, clock=lambda: datetime(2000, 1, 1, tzinfo=UTC)).record(
        fixture.extraction.prepared.paper_id,
        fixture.identity,
        selector="owner",
        recorder="agent",
        request_id="earlier-time",
    )
    history = BodySelections(root.database, root.data_root).history()
    assert earlier["sequence"] == 2
    assert history[-1].selected_at < history[0].selected_at
    assert [r.sequence for r in history] == [1, 2]
