"""B-E15 独立 D1: 请求/attempt 各自历史依据与合法后续推进。"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.papers import PaperFacts
from paper_radar.read_tasks import ReadTasks
from paper_radar.screening_tasks import FailureKind, FailureReport, ScreeningTasks
from paper_radar.storage.artifacts import ArtifactStore
from tests.artifact_support import fail_sql
from tests.config_test_support import value_inputs
from tests.experiment_read_support import read_fixture
from tests.experiment_screen_support import screen_fixture
from tests.exposure_support import backup, initialized, payload
from tests.test_experiment_accept_cli import accept
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_exposure_cli import export
from tests.test_experiment_pdf_cli import attach
from tests.test_experiment_reports_cli import report
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation
from tests.test_version_relations import relation


def test_screening_requests_and_inflight_attempt_keep_their_own_version_basis(
    tmp_path: Path,
) -> None:
    root = initialized(tmp_path / "experiment")
    settings, _ = value_inputs(root.root)
    snapshot = compile_config(settings, root.database)
    papers = PaperFacts(root.database, root.data_root)
    pre = papers.submit(
        observation(doi="10.1/pre", version_kind="preprint", fields=screening_fields())
    )
    assert pre.paper_id
    tasks = ScreeningTasks(
        root.database, root.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    request = {
        "paper_id": pre.paper_id,
        "snapshot_id": snapshot.snapshot_id,
        "stage": "boundary",
        "source": "scheduled",
        "scheduled_day": "2026-01-01",
    }
    before = tasks.register(request)
    journal = papers.submit(
        observation(
            doi="10.1/journal",
            fields=screening_fields(),
            payload=b"journal",
            relations=relation("has-preprint"),
        )
    )
    claim = tasks.claim(before.receipt_id)
    assert claim.version_id == journal.version_id != before.version_id
    first, content, original = payload(root)
    assert content["papers"] == [
        {
            "doi": "10.1/journal",
            "version_kind": "journal",
            "categories": ["screening_attempt"],
        },
        {
            "doi": "10.1/pre",
            "version_kind": "preprint",
            "categories": ["screening_request"],
        },
    ]
    tasks.fail(claim, FailureReport(FailureKind.TIMEOUT))
    after = tasks.register(request)
    assert after.task_id == before.task_id and after.version_id == journal.version_id
    second, content, _ = payload(root)
    assert second["export_id"] != first["export_id"]
    assert content["papers"][0]["categories"] == [
        "screening_attempt",
        "screening_request",
    ]
    assert (root.views / first["relative_path"]).read_bytes() == original
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output


def test_read_request_without_attempt_is_explicitly_paper_level_across_versions(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    with fail_sql("INSERT INTO read_attempts"):
        interrupted = fixture.read()
    assert interrupted.exit_code == 2, interrupted.output
    first, original_content, original = payload(root)
    assert "read_request" in original_content["papers"][0]["categories"]
    assert "read_attempt" not in original_content["papers"][0]["categories"]
    papers = PaperFacts(root.database, root.data_root)
    added = papers.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            fields=screening_fields(),
            payload=b"preprint",
            relations=(
                {
                    "kind": "is-preprint-of",
                    "source_doi": "10.1/pre",
                    "target_doi": "10.1029/synthetic1",
                    "locator": "authoritative/relation",
                },
            ),
        )
    )
    assert added.paper_id == fixture.layout.extraction.prepared.paper_id
    second, content, _ = payload(root)
    assert content["papers"][0] == {
        "doi": "10.1/pre",
        "version_kind": "preprint",
        "categories": ["read_request"],
    }
    assert "read_attempt" not in json.dumps(content)
    artifacts = ArtifactStore(root.database, root.data_root)
    audits = [
        json.loads(artifacts.read_artifact(a.artifact_id)["audit"])
        for a in artifacts.list_artifacts()
        if a.kind == "exposure_manifest"
    ]
    assert all(a["read_request_precision"] == "paper" for a in audits)
    for audit in audits:
        registrations = next(
            p["rows"] for p in audit["pages"] if p["table"] == "read_registrations"
        )
        assert len(registrations) == 1 and "version_id" not in registrations[0]
        assert (
            next(p["rows"] for p in audit["pages"] if p["table"] == "read_attempts")
            == []
        )
    (task,) = ReadTasks(root.database, root.data_root).history(added.paper_id)
    finished = fixture.read(request=None, task=task.task_id)
    assert finished.exit_code == 0, finished.output
    third, content, _ = payload(root)
    assert content["papers"][0]["categories"] == ["read_request"]
    assert "read_attempt" in content["papers"][1]["categories"]
    assert len({first["export_id"], second["export_id"], third["export_id"]}) == 3
    assert (root.views / first["relative_path"]).read_bytes() == original
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output


def test_confirmation_is_exposed_before_attachment_and_old_export_survives_resume(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    root = ExperimentRoot(prepared.root)
    with fail_sql("INSERT INTO body_pdfs"):
        interrupted = attach(prepared, tmp_path)
    assert interrupted.exit_code == 2, interrupted.output
    first, content, original = payload(root)
    assert content["papers"][0]["categories"] == [
        "decision",
        "pdf_confirmation",
        "screening_attempt",
        "screening_request",
        "selection_authorization",
    ]
    assert attach(prepared, tmp_path).exit_code == 0
    second, content, _ = payload(root)
    assert "pdf_attachment" in content["papers"][0]["categories"]
    assert second["export_id"] != first["export_id"]
    assert (root.views / first["relative_path"]).read_bytes() == original
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output


def test_prepared_report_member_remains_exposed_after_publication(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    assert fixture.read().exit_code == 0
    root = fixture.layout.extraction.root
    original_replace = os.replace

    def interrupted(source: str | Path, target: str | Path) -> None:
        original_replace(source, target)
        if str(target).endswith(".md"):
            raise RuntimeError("PRIVATE_REPORT_CRASH")

    options = ("--date", "2026-11-14", "--timezone", "UTC")
    with monkeypatch.context() as crash:
        crash.setattr(os, "replace", interrupted)
        planned = report(root.root, "render", *options)
    assert planned.exit_code == 2 and "PRIVATE_REPORT_CRASH" not in planned.output
    first, content, original = payload(root)
    assert content["papers"][0]["categories"] == [
        "decision",
        "pdf_attachment",
        "pdf_confirmation",
        "read_attempt",
        "read_request",
        "report_member",
        "screening_attempt",
        "screening_request",
        "selection_authorization",
    ]
    assert report(root.root, "render", *options).exit_code == 0
    second = export(root.root)
    assert second == first
    assert (root.views / first["relative_path"]).read_bytes() == original
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output
