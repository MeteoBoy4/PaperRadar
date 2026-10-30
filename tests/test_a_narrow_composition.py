"""A 窄收口的公共组合回归,独立于历史 required 集合。"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.calibration.visibility import (
    HiddenCondition,
    VisibilityCapability,
    VisibilityPermission,
    evaluate_visibility,
)
from paper_radar.cli import app
from paper_radar.eligibility import (
    ArtifactFact,
    Concept,
    MetadataFacts,
    PaperProjection,
    evaluate_concept,
    evaluate_paper,
)
from paper_radar.feed_pipeline import FeedPipeline
from paper_radar.runtime_logging import FileSink
from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate, SuccessReceipt
from tests.a7_registration_support import archive, request_for
from tests.test_feed_pipeline import setup_pipeline


def business_files(root: Path) -> dict[Path, bytes]:
    # SQLite 只读连接允许创建内部 sidecar;业务文件和主库字节仍须相同。
    return {
        p.relative_to(root): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))
    }


def test_root_help_exposes_all_readonly_doctor_scopes() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor --scope basic" in result.output
    assert "doctor --scope config" in result.output
    assert "doctor --scope pi-supply" in result.output


def test_doctor_and_injected_task_queries_preserve_completed_business_bytes(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    raw = b'{"boundary":"in_scope","reason_zh":"PRIVATE_AGENT_REASON"}'
    success = tasks.run_once(receipt.receipt_id, lambda *_: SuccessCandidate(raw))
    assert isinstance(success, SuccessReceipt)
    assert not (data.data_root / "logs").exists()
    before = business_files(tmp_path)
    directories = {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_dir()}
    reader = ScreeningTasks(
        data.database,
        data.data_root,
        sink=FileSink(data.data_root),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert reader.status(receipt.receipt_id).state == "succeeded"
    assert reader.load_success(success.success_id).raw_response == raw
    reader.validate_all()
    for selection in (
        ["--scope", "basic"],
        ["--scope", "config", "--snapshot", data.snapshot_id],
        ["--scope", "config", "--settings", str(tmp_path / "absent-settings.yaml")],
    ):
        result = CliRunner().invoke(
            app, ["doctor", "--database", str(data.database), *selection]
        )
        assert result.exit_code == (2 if "--settings" in selection else 0), (
            result.output
        )
        assert "PRIVATE_AGENT_REASON" not in result.output
    assert business_files(tmp_path) == before
    assert {
        p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_dir()
    } == directories
    assert not (data.data_root / "logs").exists()


@pytest.mark.parametrize("sink_mode", ["default", "file", "unwritable"])
@pytest.mark.parametrize("hidden", [False, True])
def test_feed_task_eligibility_visibility_and_logging_share_public_facts(
    tmp_path: Path,
    sink_mode: str,
    hidden: bool,
) -> None:
    original, feed_id, snapshot_id, calls = setup_pipeline(tmp_path)
    outside = tmp_path / "outside"
    if sink_mode == "unwritable":
        outside.mkdir()
        original.data_root.mkdir()
        (original.data_root / "logs").symlink_to(outside, target_is_directory=True)
    pipeline = FeedPipeline(
        original.database,
        original.data_root,
        http=original.feed.http,
        sink=None if sink_mode == "default" else FileSink(original.data_root),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    prepared = pipeline.prepare(
        feed_id, request_id="composition", contact_email="private@example.org"
    )
    assert len(prepared.items) == 1
    item = prepared.items[0]
    assert item.paper_id is not None and item.metadata is not None
    assert item.metadata.minimum_complete is True
    assert len(calls) == 4
    receipt = pipeline.tasks.register(
        dict(
            paper_id=item.paper_id,
            snapshot_id=snapshot_id,
            stage="boundary",
            source="scheduled",
            scheduled_day="2026-01-01",
        )
    )
    raw = b'{"boundary":"in_scope","reason_zh":"PRIVATE_AGENT_REASON"}'
    success = pipeline.tasks.run_once(
        receipt.receipt_id, lambda *_: SuccessCandidate(raw)
    )
    assert isinstance(success, SuccessReceipt)
    assert pipeline.tasks.status(receipt.receipt_id).state == "succeeded"
    assert pipeline.tasks.status(receipt.receipt_id).used_attempts == 1
    view = pipeline.tasks.load_success(success.success_id)
    assert view.raw_response == raw
    trace = pipeline.trace(item.paper_id)
    assert trace.receipts == (receipt,)
    visibility = evaluate_visibility(
        frozenset({HiddenCondition.UNREVEALED}) if hidden else frozenset()
    )
    facts = PaperProjection(
        paper_id=item.paper_id,
        canonical_id=item.paper_id,
        version_id=trace.version_id,
        current_version_id=trace.version_id,
        revision_no=trace.revision_no,
        metadata=MetadataFacts.from_result(item.metadata),
        screening=ArtifactFact.from_success(
            pipeline.tasks.query_successes(
                paper_id=item.paper_id,
                stage="boundary",
                snapshot_id=snapshot_id,
            )[0],
            version_id=trace.version_id,
        ),
        visibility=visibility,
    )
    single = evaluate_paper(facts)
    assert single[Concept.METADATA_READY].eligible is True
    assert single[Concept.CURRENT_SCREENING_ARTIFACT].eligible is True
    assert single[Concept.WAITING_REPORT].eligible is None
    assert single[Concept.WAITING_REPORT].owner == "B/H"
    for concept in Concept:
        assert evaluate_concept(concept, [facts]) == {item.paper_id: single[concept]}
    assert (
        visibility.permission(VisibilityCapability.TASK_DETAILS)
        == VisibilityPermission.ALLOWED
    )
    assert visibility.permission(VisibilityCapability.AGENT_CONTENT) == (
        VisibilityPermission.DENIED if hidden else VisibilityPermission.ALLOWED
    )
    assert visibility.permission(VisibilityCapability.READING_REQUEST) == (
        VisibilityPermission.DENIED if hidden else VisibilityPermission.ALLOWED
    )
    if sink_mode == "file":
        content = (original.data_root / "logs/runtime.jsonl").read_text()
        logged = [json.loads(line) for line in content.splitlines()]
        assert {event["component"] for event in logged} == {
            "feed",
            "metadata",
            "screening",
        }
        task_events = [event for event in logged if event["component"] == "screening"]
        assert [event["event"] for event in task_events] == ["claimed", "succeeded"]
        assert {event["paper_id"] for event in task_events} == {item.paper_id}
        assert {event["stage"] for event in task_events} == {"boundary"}
        assert (
            "PRIVATE_AGENT_REASON" not in content
            and "private@example.org" not in content
        )
        before = business_files(tmp_path)
        result = CliRunner().invoke(
            app,
            [
                "doctor",
                "--scope",
                "config",
                "--database",
                str(original.database),
                "--snapshot",
                snapshot_id,
            ],
        )
        assert result.exit_code == 0, result.output
        assert business_files(tmp_path) == before
    elif sink_mode == "default":
        assert not (original.data_root / "logs").exists()
    else:
        assert not tuple(outside.iterdir())
