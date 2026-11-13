"""B-E3 独立 D1: CLI 候选事实冻结与私有展示。"""

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

import httpx
import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner, Result

from paper_radar.calibration.visibility import HiddenCondition, Visibility
from paper_radar.cli import app
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from tests.test_audit_http import FakeClock

MAIN = (
    "PRIVATE_SYNTHETIC_ABSTRACT Complete atmospheric observations and reproducible "
    "methods support a detailed analysis of controlled scientific experiments."
)


class FeedState(TypedDict):
    order: list[int]
    cached: bool
    missing: bool
    conflict: bool


class FeedItemReceipt(TypedDict):
    paper_id: str | None
    conflict_id: str | None


class FeedReceipt(TypedDict):
    check_id: str
    items: list[FeedItemReceipt]


type FeedFixture = tuple[Path, FeedState, Callable[[str], FeedReceipt]]


def invoke(*arguments: str) -> Result:
    return CliRunner().invoke(app, ["experiment", *arguments])


@pytest.fixture
def feed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FeedFixture:
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    state: FeedState = {
        "order": list(range(1, 8)),
        "cached": False,
        "missing": False,
        "conflict": False,
    }
    clock = FakeClock()

    def respond(request: httpx.Request) -> httpx.Response:
        if "showFeed" in str(request.url):
            if state["cached"]:
                return httpx.Response(304)
            items = "".join(
                f"<item><guid>entry-{number}</guid>"
                f"<title>PRIVATE_SYNTHETIC_TITLE {number}</title>"
                f"<doi>10.1029/"
                f"{'conflicting' if state['conflict'] else 'synthetic'}{number}</doi>"
                f"<link>https://agupubs.onlinelibrary.wiley.com/doi/10.1029/"
                f"{'conflicting' if state['conflict'] else 'synthetic'}{number}</link>"
                + (
                    ""
                    if state["missing"]
                    else "<content:encoded><![CDATA[<h2>Abstract</h2>"
                    f"<p>{MAIN}</p>]]></content:encoded>"
                )
                + "</item>"
                for number in state["order"]
            )
            return httpx.Response(
                200,
                text=f'<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>{items}</channel></rss>',
                headers={"ETag": '"synthetic"'},
            )
        if state["missing"]:
            return httpx.Response(403)
        if "doiRA" in str(request.url):
            return httpx.Response(
                200,
                json=[{"DOI": str(request.url).split("doiRA/")[-1], "RA": "Crossref"}],
            )
        if request.url.host == "api.crossref.org":
            doi = str(request.url).split("/works/")[-1]
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": doi,
                        "title": [
                            "PRIVATE_SYNTHETIC_TITLE "
                            + doi.removeprefix("10.1029/synthetic")
                        ],
                        "URL": "https://agupubs.onlinelibrary.wiley.com/doi/" + doi,
                        "abstract": MAIN,
                        "type": "journal-article",
                    }
                },
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

    def fetch(request_id: str) -> FeedReceipt:
        result = invoke(
            "feed-fetch",
            "--root",
            str(root),
            "--request-id",
            request_id,
            "--contact-email",
            "contact@example.org",
        )
        assert result.exit_code in {0, 2}, result.output
        return TypeAdapter(FeedReceipt).validate_json(result.stdout)

    return root, state, fetch


def test_candidates_keep_all_members_full_abstract_and_private_output(
    feed: FeedFixture,
) -> None:
    root, _state, fetch = feed
    check = fetch("first")
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["count"] == 7
    view = root / receipt["view"]
    text = view.read_text()
    assert MAIN in text
    assert "PRIVATE_SYNTHETIC_TITLE 1" in text
    assert "## 7." in text
    assert "10.1029/synthetic7" in text
    assert "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/synthetic7" in text
    assert "最低元数据：就绪" in text
    assert "主摘要：非截断" in text
    assert "语言：resolved" in text
    assert "PRIVATE_SYNTHETIC" not in result.output
    before = view.read_bytes()
    rebuilt = invoke("candidates", "--root", str(root), "--view-id", receipt["view_id"])
    assert rebuilt.exit_code == 0, rebuilt.output
    assert json.loads(rebuilt.stdout) == receipt
    assert view.read_bytes() == before
    repeated = invoke(
        "candidates", "--root", str(root), "--check-id", check["check_id"]
    )
    assert json.loads(repeated.stdout) == receipt


@pytest.mark.parametrize("damage", ["abstract", "metadata_readiness"])
def test_snapshot_format_rejects_forged_display_content(
    feed: FeedFixture, damage: str
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore

    root, _state, fetch = feed
    check = fetch("first")
    first = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    receipt = json.loads(first.stdout)
    store = ArtifactStore(root / "paper-radar.sqlite3", root)
    payload = json.loads(store.read_artifact(receipt["view_id"])["payload"])
    if damage == "abstract":
        payload["items"][0]["abstract"] = "PRIVATE_SYNTHETIC_FORGED"
    else:
        payload["items"][0]["metadata"]["minimum_complete"] = False
    damaged = store.publish_single(
        "candidate_snapshot",
        [
            json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ],
    )
    result = invoke("candidates", "--root", str(root), "--view-id", damaged.artifact_id)
    assert result.exit_code == 2, result.output
    assert "registration_corrupt" in result.output
    assert "PRIVATE_SYNTHETIC" not in result.output
    assert not (root / "views/candidates" / f"{damaged.artifact_id}.md").exists()


def test_later_metadata_revision_creates_new_identity_and_keeps_old_bytes(
    feed: FeedFixture,
) -> None:
    from paper_radar.papers import PaperFacts

    root, _state, fetch = feed
    check = fetch("first")
    first = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    old = json.loads(first.stdout)
    path = root / old["view"]
    original = path.read_bytes()
    papers = PaperFacts(root / "paper-radar.sqlite3", root)
    paper_id = check["items"][0]["paper_id"]
    assert paper_id is not None
    current = papers.show(paper_id)
    corrected = papers.correct(
        dict(
            version_id=current.version_id,
            request_id="supplement",
            actor="synthetic-owner",
            reason="synthetic metadata correction",
            fields={
                "abstract": {
                    "value": {
                        "text": MAIN + " NEW_SYNTHETIC_SUPPLEMENT",
                        "is_truncated": False,
                        "rule": "synthetic",
                    },
                    "locator": "manual/abstract",
                }
            },
        )
    )
    assert corrected.status == "retained"
    new_result = invoke(
        "candidates", "--root", str(root), "--check-id", check["check_id"]
    )
    assert new_result.exit_code == 0, new_result.output
    new = json.loads(new_result.stdout)
    assert new["view_id"] != old["view_id"]
    assert "NEW_SYNTHETIC_SUPPLEMENT" in (root / new["view"]).read_text()
    path.unlink()
    rebuilt = invoke("candidates", "--root", str(root), "--view-id", old["view_id"])
    assert rebuilt.exit_code == 0, rebuilt.output
    assert path.read_bytes() == original


def test_304_and_reordered_feed_replay_original_positions(feed: FeedFixture) -> None:
    root, state, fetch = feed
    original = fetch("first")
    first = json.loads(
        invoke(
            "candidates", "--root", str(root), "--check-id", original["check_id"]
        ).stdout
    )
    old = (root / first["view"]).read_bytes()
    state["cached"] = True
    cached = fetch("cached")
    result = invoke("candidates", "--root", str(root), "--check-id", cached["check_id"])
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["source_check_id"] == original["check_id"]
    assert receipt["count"] == 7
    assert "## 1. PRIVATE_SYNTHETIC_TITLE 1" in (root / receipt["view"]).read_text()
    state["cached"] = False
    state["order"] = list(range(7, 0, -1))
    reorder = fetch("reordered")
    result = invoke(
        "candidates", "--root", str(root), "--check-id", reorder["check_id"]
    )
    assert result.exit_code == 0, result.output
    assert (
        "## 1. PRIVATE_SYNTHETIC_TITLE 7"
        in (root / json.loads(result.stdout)["view"]).read_text()
    )
    rebuilt = invoke("candidates", "--root", str(root), "--view-id", first["view_id"])
    assert rebuilt.exit_code == 0, rebuilt.output
    assert (root / first["view"]).read_bytes() == old


def test_missing_abstract_is_explicit_without_invented_text_or_logs(
    feed: FeedFixture,
) -> None:
    root, state, fetch = feed
    state["order"] = [1]
    state["missing"] = True
    check = fetch("missing")
    before = (root / "logs/runtime.jsonl").read_bytes()
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert result.exit_code == 0, result.output
    text = (root / json.loads(result.stdout)["view"]).read_text()
    assert "PRIVATE_SYNTHETIC_TITLE 1" in text
    assert "未取得主摘要；不生成替代文本。" in text
    assert "no_abstract" in text and "下一步" in text
    assert "就绪：否" in text
    assert MAIN not in text
    assert (root / "logs/runtime.jsonl").read_bytes() == before


@pytest.mark.parametrize(
    "arguments", [[], ["--check-id", "private", "--view-id", "private"]]
)
def test_invalid_arguments_have_controlled_private_safe_exit(
    tmp_path: Path, arguments: list[str]
) -> None:
    result = invoke(
        "candidates", "--root", str(tmp_path / "PRIVATE_SYNTHETIC_ROOT"), *arguments
    )
    assert result.exit_code == 2
    assert "invalid_arguments" in result.output
    assert "PRIVATE_SYNTHETIC" not in result.output


def test_candidates_help_is_chinese_and_has_no_io(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "experiment",
            "candidates",
            "--help",
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for fragment in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "130",
        "--check-id",
        "--view-id",
    ):
        assert fragment in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_each_render_calls_shared_visibility_and_creates_no_execution_log(
    feed: FeedFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.calibration import visibility

    root, state, fetch = feed
    state["order"] = [1]
    check = fetch("first")
    calls: list[frozenset[HiddenCondition]] = []
    original = visibility.evaluate_visibility

    def observe(hidden: frozenset[HiddenCondition]) -> Visibility:
        calls.append(hidden)
        return original(hidden)

    monkeypatch.setattr(visibility, "evaluate_visibility", observe)
    before = (root / "logs/runtime.jsonl").read_bytes()
    first = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert first.exit_code == 0, first.output
    second = invoke(
        "candidates",
        "--root",
        str(root),
        "--view-id",
        json.loads(first.stdout)["view_id"],
    )
    assert second.exit_code == 0, second.output
    assert calls == [frozenset(), frozenset()]
    assert (root / "logs/runtime.jsonl").read_bytes() == before


def test_unregistered_root_is_refused_without_creating_files(tmp_path: Path) -> None:
    root = tmp_path / "unknown"
    result = invoke("candidates", "--root", str(root), "--check-id", "synthetic")
    assert result.exit_code == 2 and "root_unknown" in result.output
    assert not root.exists()


def test_symlink_view_directory_cannot_escape_private_root(
    feed: FeedFixture, tmp_path: Path
) -> None:
    root, state, fetch = feed
    state["order"] = [1]
    check = fetch("first")
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "views/candidates").symlink_to(outside, target_is_directory=True)
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert result.exit_code == 2, result.output
    assert "unsafe_layout" in result.output
    assert list(outside.iterdir()) == []


def test_candidate_snapshot_survives_backup_restore_without_view_files(
    feed: FeedFixture, tmp_path: Path
) -> None:
    root, state, fetch = feed
    state["order"] = [1]
    check = fetch("first")
    first = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert first.exit_code == 0, first.output
    receipt = json.loads(first.stdout)
    expected = (root / receipt["view"]).read_bytes()
    runner = CliRunner()
    backups = tmp_path / "backups"
    backup = runner.invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root / "paper-radar.sqlite3"),
            "--data-root",
            str(root),
            "--output",
            str(backups),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = backups.iterdir()
    restored = tmp_path / "restored"
    result = runner.invoke(
        app, ["restore", "verify", str(batch), "--target", str(restored)]
    )
    assert result.exit_code == 0, result.output
    # 只验证恢复的业务闭包可重建候选;不把布局转换冒充恢复 manifest 再校验。
    # #201 承接 manifest 固定布局与独立 replay 输出区的公共组合。
    working = tmp_path / "working-copy"
    working.mkdir()
    shutil.copyfile(restored / "database.sqlite3", working / "paper-radar.sqlite3")
    shutil.copytree(restored / "blobs", working / "blobs")
    result = invoke(
        "candidates", "--root", str(working), "--view-id", receipt["view_id"]
    )
    assert result.exit_code == 0, result.output
    assert (working / receipt["view"]).read_bytes() == expected
    assert not (working / "logs").exists()


def test_strong_conflict_keeps_original_title_abstract_and_position(
    feed: FeedFixture,
) -> None:
    root, state, fetch = feed
    state["order"] = [1]
    fetch("first")
    state["conflict"] = True
    check = fetch("conflict")
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert result.exit_code == 0, result.output
    text = (root / json.loads(result.stdout)["view"]).read_text()
    assert "## 1. PRIVATE_SYNTHETIC_TITLE 1" in text
    assert MAIN in text
    assert "identity_conflict" in text and "就绪：否" in text
    conflict_id = check["items"][0]["conflict_id"]
    assert conflict_id is not None
    assert conflict_id in text
    assert "10.1029/conflicting1" in text


def test_truncated_abstract_is_preserved_and_blocked(feed: FeedFixture) -> None:
    from paper_radar.papers import PaperFacts

    root, state, fetch = feed
    state["order"] = [1]
    check = fetch("first")
    papers = PaperFacts(root / "paper-radar.sqlite3", root)
    paper_id = check["items"][0]["paper_id"]
    assert paper_id is not None
    current = papers.show(paper_id)
    corrected = papers.correct(
        dict(
            version_id=current.version_id,
            request_id="truncated",
            actor="synthetic-owner",
            reason="synthetic correction",
            fields={
                "abstract": {
                    "value": {
                        "text": "SYNTHETIC_TRUNCATED...",
                        "is_truncated": True,
                        "rule": "synthetic",
                    },
                    "locator": "manual/abstract",
                }
            },
        )
    )
    assert corrected.status == "retained"
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert result.exit_code == 0, result.output
    text = (root / json.loads(result.stdout)["view"]).read_text()
    assert "SYNTHETIC_TRUNCATED..." in text
    assert "suspected_truncated" in text and "就绪：否" in text


@pytest.mark.parametrize("boundary", ["registration", "publication"])
def test_snapshot_or_view_failure_is_private_safe_and_resumable(
    feed: FeedFixture, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    from contextlib import nullcontext

    from tests.artifact_support import fail_sql

    root, state, fetch = feed
    state["order"] = [1]
    check = fetch("first")

    def reject(*args: object) -> None:
        raise OSError("PRIVATE_SYNTHETIC_EXCEPTION")

    with monkeypatch.context() as fault:
        if boundary == "publication":
            fault.setattr("paper_radar.experiment.candidates.os.replace", reject)
        with (
            fail_sql("INSERT INTO artifacts")
            if boundary == "registration"
            else nullcontext()
        ):
            failed = invoke(
                "candidates", "--root", str(root), "--check-id", check["check_id"]
            )
    assert failed.exit_code == 2
    assert (
        "database_failed" if boundary == "registration" else "unsafe_layout"
    ) in failed.output
    assert "PRIVATE_SYNTHETIC" not in failed.output
    assert not list((root / "views").rglob("*.md"))
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert result.exit_code == 0, result.output
    assert MAIN in (root / json.loads(result.stdout)["view"]).read_text()


def test_production_root_is_refused(tmp_path: Path) -> None:
    from paper_radar.body import BodyService
    from paper_radar.storage.database import upgrade_database

    root = tmp_path / "production"
    root.mkdir()
    upgrade_database(root / "paper-radar.sqlite3")
    BodyService(root / "paper-radar.sqlite3", root).register_root("production")
    result = invoke("candidates", "--root", str(root), "--check-id", "synthetic")
    assert result.exit_code == 2 and "root_not_experiment" in result.output
    assert not (root / "views").exists()
