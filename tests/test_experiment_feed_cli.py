"""B 独立 D1:显式实验根与生产 Feed CLI,仅临时根及 HTTP 替身。"""

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app


def invoke(*args: str) -> Result:
    return CliRunner().invoke(app, ["experiment", *args])


def test_init_registers_one_experiment_and_replays_same_root(tmp_path: Path) -> None:
    root = tmp_path / "explicit"
    first = invoke("init", "--root", str(root))
    assert first.exit_code == 0, first.output
    original = json.loads(first.stdout)
    assert original["purpose"] == "experiment"
    assert original["database"] == "paper-radar.sqlite3"
    assert original["data_root"] == "."
    assert original["blobs"] == "blobs/sha256"
    assert (root / "paper-radar.sqlite3").is_file()
    assert (root / "config").is_dir() and (root / "views").is_dir()
    second = invoke("init", "--root", str(root))
    assert second.exit_code == 0, second.output
    assert json.loads(second.stdout) == original
    assert not (root / "logs/runtime.jsonl").exists()


def test_feed_fetch_selects_v2_and_keeps_sensitive_text_in_business_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.screening_tasks import ScreeningTasks
    from tests.test_audit_http import FakeClock

    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    main = (
        "PRIVATE_SYNTHETIC_ABSTRACT atmospheric observations and reproducible "
        "scientific methods produce complete results across controlled experiments."
    )
    note = "Journal of Synthetic Atmospheres, Volume 9, Issue 2, Pages 1-8."
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "showFeed" in str(request.url):
            return httpx.Response(
                200,
                text=(
                    '<rss xmlns:dc="http://purl.org/dc/elements/1.1/" '
                    'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
                    "<item><guid>entry-1</guid><title>PRIVATE_SYNTHETIC_TITLE</title>"
                    "<dc:identifier>10.1029/synthetic</dc:identifier>"
                    f"<description>{note}</description><content:encoded><![CDATA["
                    f"<h2>Abstract</h2><p>{main}</p>]]></content:encoded>"
                    "</item></channel></rss>"
                ),
            )
        if "doiRA" in str(request.url):
            return httpx.Response(
                200, json=[{"DOI": "10.1029/synthetic", "RA": "Crossref"}]
            )
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1029/synthetic",
                        "title": ["PRIVATE_SYNTHETIC_TITLE"],
                        "abstract": main,
                        "type": "journal-article",
                    }
                },
            )
        return httpx.Response(403)

    clock = FakeClock()
    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(respond),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor", lambda: executor
    )
    result = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "first",
        "--contact-email",
        "contact@example.org",
    )
    assert result.exit_code == 0, result.output
    value = json.loads(result.stdout)
    assert value["reason"] == "acquired" and value["status_code"] == 200
    assert value["parser_identity"] == "jgr-feed-parser-v2"
    assert value["abstract_rules_version"] == "audit-abstract-v2"
    (item,) = value["items"]
    assert item["language"]["policy_version"] == "v1"
    assert item["language"]["original_title_is_zh"] is False
    metadata = JGRMetadata(root / "paper-radar.sqlite3", root)
    content = metadata.content(item["metadata_request_key"])
    assert content.abstract == main
    assert {route.abstract_rules_version for route in content.result.routes} == {
        "audit-abstract-v2"
    }
    tasks = ScreeningTasks(root / "paper-radar.sqlite3", root)
    assert (
        tasks.language_observations(item["paper_id"])[0]["original_title_is_zh"]
        is False
    )
    count = len(calls)
    replay = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "first",
        "--contact-email",
        "contact@example.org",
    )
    assert replay.exit_code == 0, replay.output
    assert json.loads(replay.stdout) == value
    assert len(calls) == count
    log = (root / "logs/runtime.jsonl").read_text()
    for forbidden in (
        main,
        note,
        "PRIVATE_SYNTHETIC_TITLE",
        "contact@example.org",
        str(root),
    ):
        assert forbidden not in result.output + log
    events = [json.loads(line) for line in log.splitlines()]
    assert events[0]["event"] == "run_started"
    assert events[-1]["event"] == "run_finished"
    # HTTP 304 保留原检查身份及成员,不能投影为零候选。
    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor",
        lambda: SourceHTTPExecutor(
            transport=httpx.MockTransport(lambda request: httpx.Response(304)),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ),
    )

    # 首次响应没有 ETag,故先显式取得一个带条件标识的完整检查。
    def tagged(request: httpx.Request) -> httpx.Response:
        response = respond(request)
        if "showFeed" in str(request.url):
            response.headers["ETag"] = '"synthetic"'
        return response

    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor",
        lambda: SourceHTTPExecutor(
            transport=httpx.MockTransport(tagged),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ),
    )
    tagged_result = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "tagged",
        "--contact-email",
        "contact@example.org",
    )
    assert tagged_result.exit_code == 0, tagged_result.output
    tagged_value = json.loads(tagged_result.stdout)
    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor",
        lambda: SourceHTTPExecutor(
            transport=httpx.MockTransport(lambda request: httpx.Response(304)),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ),
    )
    cached = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "cached",
        "--contact-email",
        "contact@example.org",
    )
    assert cached.exit_code == 0, cached.output
    cached_value = json.loads(cached.stdout)
    assert cached_value["status_code"] == 304
    assert cached_value["outcome"] == "not_modified"
    assert cached_value["source_check_id"] == tagged_value["check_id"]
    assert cached_value["items"] == tagged_value["items"]


@pytest.mark.parametrize("purpose", ["unknown", "production"])
def test_existing_nonexperiment_database_is_refused_without_reassignment(
    tmp_path: Path, purpose: str
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.storage.database import upgrade_database

    root = tmp_path / "existing"
    root.mkdir()
    database = root / "paper-radar.sqlite3"
    upgrade_database(database)
    service = BodyService(database, root)
    if purpose != "unknown":
        service.register_root(purpose)
    before = service.root()
    for command in (
        ["init"],
        ["feed-fetch", "--request-id", "one", "--contact-email", "contact@example.org"],
    ):
        result = invoke(*command, "--root", str(root))
        assert result.exit_code == 2
        assert (
            "root_unknown" if purpose == "unknown" else "root_not_experiment"
        ) in result.output
        assert str(root) not in result.output
        assert service.root() == before
    assert not (root / "logs").exists()


@pytest.mark.parametrize("arguments", [[], ["init"], ["feed-fetch"]])
def test_experiment_help_is_chinese_and_has_no_external_io(
    tmp_path: Path, arguments: list[str]
) -> None:
    import os
    import subprocess
    import sys

    environment = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "experiment",
            *arguments,
            "--help",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for fragment in ("参数", "副作用", "自动配额", "输出去向", "常见失败", "示例"):
        assert fragment in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "arguments",
    [
        ["init"],
        ["feed-fetch", "--root", "PRIVATE_SYNTHETIC_ROOT"],
        ["init", "--root", "PRIVATE_SYNTHETIC_ROOT", "--PRIVATE_SYNTHETIC_TOKEN"],
    ],
)
def test_argument_errors_are_controlled_and_do_not_echo_private_values(
    arguments: list[str],
) -> None:
    result = invoke(*arguments)
    assert result.exit_code == 2
    assert "invalid_arguments" in result.output
    assert "PRIVATE_SYNTHETIC" not in result.output


@pytest.mark.parametrize(
    "status,body,reason",
    [
        (403, "PRIVATE_SYNTHETIC_RESPONSE", "access_blocked_403"),
        (200, "not xml PRIVATE_SYNTHETIC_RESPONSE", "invalid_feed"),
        (
            200,
            "<rss><channel><item><title>PRIVATE_SYNTHETIC_TITLE</title></item></channel></rss>",
            "missing_entry_id",
        ),
    ],
)
def test_http_and_item_failures_remain_observable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int, body: str, reason: str
) -> None:
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from tests.test_audit_http import FakeClock

    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    clock = FakeClock()
    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, text=body)
        ),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor", lambda: executor
    )
    result = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "failed",
        "--contact-email",
        "contact@example.org",
    )
    assert result.exit_code == 2, result.output
    value = json.loads(result.stdout)
    assert value["reason"] == reason or value["items"][0]["reason"] == reason
    assert "无新论文" not in value["scope"]
    assert value["next_action"]
    assert (
        "PRIVATE_SYNTHETIC"
        not in result.output + (root / "logs/runtime.jsonl").read_text()
    )


def test_request_parser_conflict_remains_controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.feed_ingestion import JGRFeed
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.papers import PaperFacts
    from paper_radar.sources.feeds import endpoint
    from tests.test_audit_http import FakeClock

    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    clock = FakeClock()
    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="<rss><channel/></rss>")
        ),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    database = root / "paper-radar.sqlite3"
    source = PaperFacts(database, root).register_feed(endpoint("jgr"))
    old = JGRFeed(database, root, http=executor).check(
        source.feed_id,
        request_id="same",
        contact_email="contact@example.org",
        parser_version=1,
    )
    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor", lambda: executor
    )
    result = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "same",
        "--contact-email",
        "contact@example.org",
    )
    assert result.exit_code == 2
    assert "invalid_observation（parser_version）" in result.output
    assert JGRFeed(database, root).replay(old.check_id) == old


def test_init_upgrades_existing_experiment_without_replacing_identity(
    tmp_path: Path,
) -> None:
    import sqlite3
    from contextlib import closing

    from alembic import command
    from alembic.config import Config

    from paper_radar.body import BodyService
    from paper_radar.storage import database as database_module
    from paper_radar.storage.database import DatabaseMode, open_database

    source = tmp_path / "source"
    original = invoke("init", "--root", str(source))
    assert original.exit_code == 0
    root = tmp_path / "old"
    root.mkdir()
    database = root / "paper-radar.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(database, mode=DatabaseMode.CREATE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.upgrade(config, "body01_persistence")
            connection.commit()
    finally:
        engine.dispose()
    # 构造上一 revision 的已登记根材料,不通过被测 CLI 伪造升级结果。
    with (
        closing(sqlite3.connect(source / "paper-radar.sqlite3")) as old,
        closing(sqlite3.connect(database)) as previous,
    ):
        row = old.execute("SELECT * FROM body_root").fetchone()
        assert row is not None
        previous.execute("INSERT INTO body_root VALUES (?,?,?,?,?)", row)
        previous.commit()
    upgraded = invoke("init", "--root", str(root))
    assert upgraded.exit_code == 0, upgraded.output
    assert (
        json.loads(upgraded.stdout)["root_id"] == json.loads(original.stdout)["root_id"]
    )
    assert BodyService(database, root).root().purpose == "experiment"


def test_invalid_contact_keeps_controlled_reason_and_redacts_input(
    tmp_path: Path,
) -> None:
    root = tmp_path / "PRIVATE_SYNTHETIC_ROOT"
    assert invoke("init", "--root", str(root)).exit_code == 0
    result = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "first",
        "--contact-email",
        "PRIVATE_SYNTHETIC_TOKEN",
    )
    assert result.exit_code == 2
    assert "invalid_contact" in result.output
    assert "PRIVATE_SYNTHETIC" not in result.output
    assert "请" in result.output
    assert not (root / "logs").exists()


def test_corrupt_existing_database_has_controlled_redacted_error(
    tmp_path: Path,
) -> None:
    root = tmp_path / "PRIVATE_SYNTHETIC_ROOT"
    root.mkdir()
    (root / "paper-radar.sqlite3").write_bytes(b"PRIVATE_SYNTHETIC_NOT_SQLITE")
    result = invoke("init", "--root", str(root))
    assert result.exit_code == 2
    assert "execution_failed" in result.output
    assert "PRIVATE_SYNTHETIC" not in result.output


def test_incremental_feed_preserves_discoveries_and_conflict_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.feed_ingestion import JGRFeed
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.papers import PaperFacts
    from tests.test_audit_http import FakeClock

    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    body = [
        "<item><guid>stable-entry</guid><title>Synthetic</title>"
        "<doi>10.1029/first</doi></item>"
    ]
    clock = FakeClock()

    def respond(request: httpx.Request) -> httpx.Response:
        if "showFeed" in str(request.url):
            return httpx.Response(
                200, text="<rss><channel>" + body[0] + "</channel></rss>"
            )
        return httpx.Response(403)

    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(respond),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor", lambda: executor
    )

    def fetch(request: str) -> dict:
        result = invoke(
            "feed-fetch",
            "--root",
            str(root),
            "--request-id",
            request,
            "--contact-email",
            "contact@example.org",
        )
        assert result.exit_code == 2, result.output
        value = json.loads(result.stdout)
        assert value["reason"] == "acquired"
        return value

    first = fetch("one")
    repeat = fetch("two")
    paper_id = first["items"][0]["paper_id"]
    assert repeat["items"][0]["paper_id"] == paper_id
    papers = PaperFacts(root / "paper-radar.sqlite3", root)
    assert len(papers.trace(paper_id).discoveries) == 1
    body[0] = (
        "<item><guid>stable-entry</guid><title>Synthetic</title>"
        "<doi>10.1029/conflicting</doi></item>"
        "<item><guid>new-entry</guid><title>New synthetic</title>"
        "<doi>10.1029/new</doi></item>"
    )
    changed = fetch("three")
    conflict, new = changed["items"]
    assert conflict["reason"] == "identity_conflict" and conflict["conflict_id"]
    assert conflict["paper_id"] is None
    assert new["paper_id"] is not None and new["paper_id"] != paper_id
    assert len(papers.trace(paper_id).discoveries) == 1
    assert papers.conflicts()[0].conflict_id == conflict["conflict_id"]
    history = JGRFeed(root / "paper-radar.sqlite3", root).view(changed["feed_id"])
    assert [check.check_id for check in history.checks] == [
        first["check_id"],
        repeat["check_id"],
        changed["check_id"],
    ]
    papers.validate_all()


@pytest.mark.parametrize("boundary", ["registration", "publication"])
def test_init_failure_does_not_expose_unknown_database_and_can_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    from contextlib import nullcontext

    from tests.artifact_support import fail_sql

    root = tmp_path / "experiment"
    with monkeypatch.context() as fault:
        if boundary == "publication":

            def reject(*args: object, **kwargs: object) -> None:
                raise OSError("PRIVATE_SYNTHETIC_IO_ERROR")

            fault.setattr("paper_radar.experiment.root.os.link", reject)
        with (
            fail_sql("INSERT INTO body_root")
            if boundary == "registration"
            else nullcontext()
        ):
            failed = invoke("init", "--root", str(root))
    assert failed.exit_code == 2
    assert (
        "database_failed" if boundary == "registration" else "unsafe_layout"
    ) in failed.output
    assert "PRIVATE_SYNTHETIC" not in failed.output
    assert not (root / "paper-radar.sqlite3").exists()
    complete = invoke("init", "--root", str(root))
    assert complete.exit_code == 0, complete.output
    assert json.loads(complete.stdout)["purpose"] == "experiment"


def test_feed_interrupt_is_130_and_does_not_expose_exception_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor

    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0

    def interrupt(request: httpx.Request) -> httpx.Response:
        raise KeyboardInterrupt("PRIVATE_SYNTHETIC_INTERRUPT")

    executor = SourceHTTPExecutor(transport=httpx.MockTransport(interrupt))
    monkeypatch.setattr(
        "paper_radar.feed_pipeline.service.SourceHTTPExecutor", lambda: executor
    )
    result = invoke(
        "feed-fetch",
        "--root",
        str(root),
        "--request-id",
        "one",
        "--contact-email",
        "contact@example.org",
    )
    assert result.exit_code == 130
    assert "interrupted" in result.output
    assert (
        "PRIVATE_SYNTHETIC"
        not in result.output + (root / "logs/runtime.jsonl").read_text()
    )
