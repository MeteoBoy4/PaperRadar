"""配置日志汇不会让公共只读边界创建 logs 或改变既有字节。"""

from datetime import UTC, datetime
from pathlib import Path

import httpx
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.feed_ingestion import JGRFeed
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.fixture_audit import FixtureAudit
from paper_radar.papers import PaperFacts
from paper_radar.runtime_logging import FileSink
from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate, SuccessReceipt
from tests.a7_registration_support import archive, request_for
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service
from tests.test_feed_ingestion import FEED, feed_service
from tests.test_feed_metadata import setup_metadata


def tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_task_paper_queries_and_help_keep_root_bytes_unchanged(tmp_path: Path) -> None:
    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    baseline = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = baseline.register(request_for(data))
    result = baseline.run_once(
        receipt.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Atmospheric observations."}'
        ),
    )
    assert isinstance(result, SuccessReceipt)
    before = tree(data.data_root), data.database.read_bytes()
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: now, sink=FileSink(data.data_root)
    )
    assert service.status(receipt.receipt_id).state == "succeeded"
    service.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    service.load_success(result.success_id)
    service.load_input(receipt.receipt_id)
    service.validate_all()
    papers = PaperFacts(data.database, data.data_root)
    papers.show(data.paper_id)
    papers.trace(data.paper_id)
    runner = CliRunner()
    for command in [
        ["paper", "show", data.paper_id],
        ["paper", "trace", data.paper_id],
    ]:
        assert (
            runner.invoke(
                app,
                [
                    *command,
                    "--database",
                    str(data.database),
                    "--data-root",
                    str(data.data_root),
                ],
            ).exit_code
            == 0
        )
    for command in [[], ["audit"], ["audit", "run"], ["audit", "resume"], ["doctor"]]:
        assert runner.invoke(app, [*command, "--help"]).exit_code == 0
    # doctor 的已交付只读错误路径也不能初始化日志。
    runner.invoke(app, ["doctor", "--database", str(data.database)])
    assert (tree(data.data_root), data.database.read_bytes()) == before
    assert not (data.data_root / "logs").exists()


def test_audit_readonly_paths_do_not_emit_or_create_directories(tmp_path: Path) -> None:
    baseline = sampling_service(tmp_path, MatrixSources())
    assert baseline.data_root is not None
    result = baseline.run_audit(contact_email="audit@example.org", code_identity=CODE)
    before = tree(tmp_path)
    service = FixtureAudit(
        baseline.database, baseline.data_root, sink=FileSink(baseline.data_root)
    )
    service.list_audits()
    service.show_audit(result.plan.plan_id)
    service.replay_audit(result.plan.plan_id)
    service.validate_all()
    runner = CliRunner()
    for command in ["list", "show", "replay"]:
        args = [
            "audit",
            command,
            *([] if command == "list" else [result.plan.plan_id]),
            "--database",
            str(baseline.database),
        ]
        if command == "replay":
            args += ["--data-root", str(baseline.data_root)]
        assert runner.invoke(app, args).exit_code == 0
    assert tree(tmp_path) == before
    assert not (baseline.data_root / "logs").exists()


def test_feed_metadata_readers_leave_existing_root_unchanged(tmp_path: Path) -> None:
    feed_root, metadata_root = tmp_path / "feed", tmp_path / "metadata"
    feed_root.mkdir()
    metadata_root.mkdir()
    papers, feed, baseline_feed = feed_service(
        feed_root, lambda _: httpx.Response(200, content=FEED)
    )
    check = baseline_feed.check(
        feed.feed_id, request_id="one", contact_email="contact@example.org"
    )
    metadata_papers, paper_id, baseline_metadata = setup_metadata(
        metadata_root, lambda _: httpx.Response(404)
    )
    result = baseline_metadata.enrich(
        paper_id, request_id="one", contact_email="contact@example.org"
    )
    assert papers.data_root is not None and metadata_papers.data_root is not None
    before = tree(tmp_path)
    logged_feed = JGRFeed(
        papers.database, papers.data_root, sink=FileSink(papers.data_root)
    )
    logged_feed.replay(check.check_id)
    logged_feed.view(feed.feed_id)
    logged_feed.validate_all()
    logged_metadata = JGRMetadata(
        metadata_papers.database,
        metadata_papers.data_root,
        sink=FileSink(metadata_papers.data_root),
    )
    logged_metadata.replay(result.request_key)
    logged_metadata.requests(paper_id)
    logged_metadata.content(result.request_key)
    logged_metadata.validate_all()
    assert tree(tmp_path) == before
    assert not (papers.data_root / "logs").exists()
    assert not (metadata_papers.data_root / "logs").exists()
