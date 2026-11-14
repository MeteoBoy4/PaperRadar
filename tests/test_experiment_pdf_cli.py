"""B-E10 独立 D1:所有者 PDF 确认、附加与冻结的产品入口。"""

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from paper_radar.experiment.root import ExperimentRoot
from tests.experiment_screen_support import ScreenFixture, screen_fixture
from tests.test_experiment_accept_cli import accept
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed

PDF = b"%PDF-1.7\nSynthetic PDF: no DOI inference.\n" + b"x" * 1100


def attach(
    prepared: ScreenFixture,
    tmp_path: Path,
    *,
    request: str = "pdf-1",
    raw: bytes = PDF,
    extra: tuple[str, ...] = (),
) -> Result:
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(raw)
    selected = ExperimentRoot(prepared.root)
    from paper_radar.papers import PaperFacts

    version = (
        PaperFacts(selected.database, selected.data_root)
        .show(prepared.paper_id)
        .version_id
    )
    return invoke(
        "attach-pdf",
        prepared.paper_id,
        "--root",
        str(prepared.root),
        "--selection-id",
        prepared.selection_id,
        "--version-id",
        version,
        "--pdf",
        str(path),
        "--sha256",
        hashlib.sha256(raw).hexdigest(),
        "--owner-confirmed",
        "--actor",
        "agent",
        "--request-id",
        request,
        *extra,
    )


def test_confirmation_attachment_and_sample_are_distinct_safe_trace_facts(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    accepted = accept(prepared)
    assert accepted.exit_code == 0, accepted.output
    result = attach(prepared, tmp_path)
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["owner"] == "owner" and receipt["actor"] == "agent"
    assert receipt["acceptance_id"] == json.loads(accepted.stdout)["acceptance_id"]
    repeated = attach(prepared, tmp_path)
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.stdout) == {**receipt, "replayed": True}
    selected = ExperimentRoot(prepared.root)
    log = selected.root / "logs/runtime.jsonl"
    logged = log.read_bytes()
    events = [json.loads(line) for line in logged.splitlines()]
    assert [e["event"] for e in events[-2:]] == ["run_started", "run_finished"]
    assert all(e["component"] == "experiment" for e in events[-2:])
    result_trace = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            prepared.paper_id,
            "--database",
            str(selected.database),
            "--data-root",
            str(selected.data_root),
            "--snapshot",
            prepared.snapshot,
            "--json",
        ],
    )
    assert result_trace.exit_code == 0, result_trace.output
    workflow = json.loads(result_trace.stdout)["workflow"]
    assert (
        workflow["pdf_confirmations"][0]["confirmation_id"]
        == receipt["confirmation_id"]
    )
    assert workflow["frozen_samples"][0]["sample_id"] == receipt["sample_id"]
    assert workflow["pdfs"][0]["pdf_sha256"] == hashlib.sha256(PDF).hexdigest()
    assert "PRIVATE_SYNTHETIC_ABSTRACT" not in result.output + result_trace.output
    assert log.read_bytes() == logged
    assert (
        "PRIVATE_OWNER_REASON"
        not in result.output + result_trace.output + logged.decode()
    )
    assert (
        str(tmp_path / "synthetic.pdf")
        not in result.output + result_trace.output + logged.decode()
    )


def test_help_is_cold_and_complete(tmp_path: Path) -> None:
    from tests.config_test_support import run_cli

    result = run_cli(tmp_path, "experiment", "attach-pdf", "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for text in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "130",
        "1024",
        "合法",
    ):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "case,reason",
    [
        ("unconfirmed", "owner_confirmation_required"),
        ("signature", "invalid_pdf"),
        ("small", "invalid_pdf"),
        ("hash", "invalid_pdf"),
        ("accepted_missing", "acceptance_missing"),
        ("version", "confirmation_mismatch"),
        ("actor", "invalid_request"),
        ("changed", "frozen_version_changed"),
    ],
)
def test_rejected_pdf_never_attaches_or_confirms(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    reason: str,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.experiment.pdf import PdfSamples
    from paper_radar.papers import PaperFacts

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    if case != "accepted_missing":
        assert prepared.screen().exit_code == 0
        assert accept(prepared).exit_code == 0
    selected = ExperimentRoot(prepared.root)
    paper = PaperFacts(selected.database, selected.data_root).show(prepared.paper_id)
    if case == "changed":
        correction = PaperFacts(selected.database, selected.data_root).correct(
            dict(
                version_id=paper.version_id,
                request_id="change",
                actor="owner",
                reason="synthetic",
                fields={
                    "title": {"value": "Corrected title", "locator": "manual/title"}
                },
            )
        )
        assert correction.status == "retained"
    raw = b"z" * 1200 if case == "signature" else b"%PDF-x" if case == "small" else PDF
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(raw)
    args = [
        "attach-pdf",
        prepared.paper_id,
        "--root",
        str(prepared.root),
        "--selection-id",
        prepared.selection_id,
        "--version-id",
        "wrong-version" if case == "version" else paper.version_id,
        "--pdf",
        str(path),
        "--sha256",
        "0" * 64 if case == "hash" else hashlib.sha256(raw).hexdigest(),
        "--actor",
        "intruder" if case == "actor" else "agent",
        "--request-id",
        "reject",
    ]
    if case != "unconfirmed":
        args.append("--owner-confirmed")
    result = invoke(*args)
    assert result.exit_code == 2 and reason in result.output, result.output
    assert PdfSamples(selected.database, selected.data_root).history() == ()
    assert (
        BodyService(selected.database, selected.data_root).pdfs(prepared.paper_id) == ()
    )
    assert (
        BodyService(selected.database, selected.data_root).samples(prepared.paper_id)
        == ()
    )


@pytest.mark.parametrize(
    "stop",
    [
        "INSERT INTO body_pdfs",
        "INSERT INTO body_samples",
        "INSERT INTO experiment_frozen_samples",
    ],
)
def test_partial_confirmation_resumes_without_unconfirmed_attachment(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.experiment.pdf import PdfSamples
    from tests.artifact_support import fail_sql

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    selected = ExperimentRoot(prepared.root)
    with fail_sql(stop):
        failed = attach(prepared, tmp_path)
    assert failed.exit_code == 2, failed.output
    assert "database_failed" in failed.output or "execution_failed" in failed.output
    pdfs = PdfSamples(selected.database, selected.data_root)
    confirmations = pdfs.history()
    assert len(confirmations) == 1
    assert pdfs.samples() == ()
    assert (
        BodyService(selected.database, selected.data_root).pdfs(prepared.paper_id) == ()
    )
    assert (
        BodyService(selected.database, selected.data_root).samples(prepared.paper_id)
        == ()
    )
    resumed = attach(prepared, tmp_path)
    assert resumed.exit_code == 0, resumed.output
    assert (
        json.loads(resumed.stdout)["confirmation_id"]
        == confirmations[0].confirmation_id
    )
    assert pdfs.history() == confirmations and len(pdfs.samples()) == 1


def test_replacing_pdf_keeps_screening_fingerprints_and_rechecks_current_sample(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from paper_radar.body import BodyService
    from paper_radar.experiment.pdf import PdfError, PdfSamples
    from paper_radar.screening_tasks import ScreeningTasks

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    root = ExperimentRoot(prepared.root)
    tasks = ScreeningTasks(
        root.database, root.data_root, clock=lambda: datetime.now(UTC)
    )
    before = [
        tasks.query(
            paper_id=prepared.paper_id, stage=stage, snapshot_id=prepared.snapshot
        )
        for stage in ("boundary", "value")
    ]
    first = attach(prepared, tmp_path)
    assert first.exit_code == 0, first.output
    service = PdfSamples(root.database, root.data_root)
    first_sample = service.require_current_sample(prepared.paper_id)
    body = BodyService(root.database, root.data_root)
    new_pdf = PDF + b"new PDF bytes"
    body.attach_pdf(
        prepared.paper_id,
        new_pdf,
        request_id="historical-body-interface",
        version_id=first_sample.version_id,
    )
    with pytest.raises(PdfError) as error:
        service.require_current_sample(prepared.paper_id)
    assert error.value.reason == "sample_mismatch"
    assert "sample_mismatch" in attach(prepared, tmp_path).output
    second = attach(prepared, tmp_path, request="pdf-2", raw=new_pdf)
    assert second.exit_code == 0, second.output
    assert (
        service.require_current_sample(prepared.paper_id).sample_id
        != first_sample.sample_id
    )
    assert len(service.samples()) == 2
    assert [
        tasks.query(
            paper_id=prepared.paper_id, stage=stage, snapshot_id=prepared.snapshot
        )
        for stage in ("boundary", "value")
    ] == before
    facts = body.facts(prepared.paper_id)
    assert not facts.eligible
    assert "extraction_absent" in {r.value for r in facts.reasons}


@pytest.mark.parametrize("when", [1, 2, 3])
def test_visibility_blocks_each_write_boundary(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, when: int
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.calibration import visibility
    from paper_radar.experiment.pdf import PdfSamples

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    original = visibility.evaluate_visibility
    calls = 0

    def hide(hidden: frozenset[visibility.HiddenCondition]) -> visibility.Visibility:
        nonlocal calls
        calls += 1
        return original(
            frozenset({visibility.HiddenCondition.UNREVEALED})
            if calls >= when
            else hidden
        )

    monkeypatch.setattr(visibility, "evaluate_visibility", hide)
    result = attach(prepared, tmp_path)
    assert result.exit_code == 2 and "visibility_denied" in result.output, result.output
    root = ExperimentRoot(prepared.root)
    assert len(PdfSamples(root.database, root.data_root).history()) == (
        1 if when == 3 else 0
    )
    assert BodyService(root.database, root.data_root).pdfs(prepared.paper_id) == ()


def test_restore_cold_process_replays_confirmation_pdf_sample_without_original_roots(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import subprocess
    import sys

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    attached = attach(prepared, tmp_path)
    assert attached.exit_code == 0, attached.output
    root = ExperimentRoot(prepared.root)
    before = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            prepared.paper_id,
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--snapshot",
            prepared.snapshot,
            "--json",
        ],
    )
    assert before.exit_code == 0, before.output
    output = tmp_path / "backups"
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(output),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = output.iterdir()
    restored = tmp_path / "restored"
    restored_cli = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(restored),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restored_cli.returncode == 0, restored_cli.stdout + restored_cli.stderr
    for path in (
        prepared.root,
        prepared.credentials,
        prepared.install,
        prepared.materials,
        tmp_path / "synthetic.pdf",
    ):
        if path.exists():
            path.rename(path.with_name(path.name + "-unavailable"))
        assert not path.exists()
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.experiment_pdf_recovery_worker",
            str(restored),
            prepared.paper_id,
            prepared.snapshot,
        ],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout) == json.loads(before.stdout)
    assert "oauth-test-only-sensitive-sentinel" not in process.stdout + process.stderr


@pytest.mark.parametrize(
    "corruption", ["confirmation", "association", "pdf_marker", "sample_reason"]
)
def test_backup_rejects_broken_pdf_closure(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    import sqlite3

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    result = attach(prepared, tmp_path)
    assert result.exit_code == 0, result.output
    root = ExperimentRoot(prepared.root)
    # 仅故障注入,绕过只追加保护来模拟离线介质损坏。
    with sqlite3.connect(root.database) as connection:
        if corruption == "confirmation":
            connection.execute("DROP TRIGGER experiment_pdf_confirmations_no_update")
            connection.execute(
                "UPDATE experiment_pdf_confirmations SET record_json='{}'"
            )
        elif corruption == "association":
            connection.execute("DROP TRIGGER experiment_frozen_samples_no_delete")
            connection.execute("DELETE FROM experiment_frozen_samples")
        else:
            connection.execute(
                "UPDATE body_pdfs SET confirmation_id=NULL"
                if corruption == "pdf_marker"
                else "UPDATE body_samples SET reason='tampered'"
            )
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code != 0 and "registration_invalid" in backup.output, (
        backup.output
    )


def test_concurrent_identical_pdf_request_has_one_confirmation_attachment_sample(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from paper_radar.body import BodyService
    from paper_radar.experiment.pdf import FrozenSample, PdfConfirmation, PdfSamples
    from paper_radar.papers import PaperFacts

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    root = ExperimentRoot(prepared.root)
    version = (
        PaperFacts(root.database, root.data_root).show(prepared.paper_id).version_id
    )
    start = Barrier(2)

    def execute() -> tuple[PdfConfirmation, FrozenSample, bool]:
        start.wait(timeout=15)
        return PdfSamples(root.database, root.data_root).attach(
            root,
            paper_id=prepared.paper_id,
            version_id=version,
            selection_id=prepared.selection_id,
            pdf=PDF,
            pdf_sha256=hashlib.sha256(PDF).hexdigest(),
            request_id="concurrent-pdf",
            owner_confirmed=True,
            actor="agent",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(execute), pool.submit(execute)
        first, second = a.result(timeout=60), b.result(timeout=60)
    assert first[:2] == second[:2] and sorted([first[2], second[2]]) == [False, True]
    assert len(PdfSamples(root.database, root.data_root).history()) == 1
    assert len(BodyService(root.database, root.data_root).pdfs(prepared.paper_id)) == 1
    assert (
        len(BodyService(root.database, root.data_root).samples(prepared.paper_id)) == 1
    )


def test_interrupt_during_final_association_retains_only_resumable_confirmation(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import Connection, Engine, event

    from paper_radar.body import BodyService
    from paper_radar.experiment.pdf import PdfSamples

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0

    def interrupted(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.startswith("INSERT INTO experiment_frozen_samples"):
            raise KeyboardInterrupt("PRIVATE_INTERRUPT_PAYLOAD")

    event.listen(Engine, "before_cursor_execute", interrupted)
    try:
        failed = attach(prepared, tmp_path)
    finally:
        event.remove(Engine, "before_cursor_execute", interrupted)
    assert failed.exit_code == 130 and "interrupted" in failed.output
    assert "PRIVATE_INTERRUPT_PAYLOAD" not in failed.output
    root = ExperimentRoot(prepared.root)
    assert len(PdfSamples(root.database, root.data_root).history()) == 1
    assert BodyService(root.database, root.data_root).pdfs(prepared.paper_id) == ()
    resumed = attach(prepared, tmp_path)
    assert resumed.exit_code == 0, resumed.output


def test_same_request_changed_bytes_conflicts_without_second_confirmation(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.experiment.pdf import PdfSamples

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    first = attach(prepared, tmp_path)
    assert first.exit_code == 0, first.output
    conflict = attach(prepared, tmp_path, raw=PDF + b"changed")
    assert conflict.exit_code == 2 and "request_conflict" in conflict.output
    root = ExperimentRoot(prepared.root)
    assert len(PdfSamples(root.database, root.data_root).history()) == 1


@pytest.mark.parametrize(
    "change,reason",
    [("revision", "frozen_version_changed"), ("selection", "selection_changed")],
)
def test_change_during_blob_publication_never_attaches_to_stale_selection(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    import os

    from paper_radar.body import BodyService
    from paper_radar.experiment.pdf import PdfSamples
    from paper_radar.papers import PaperFacts
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    root = ExperimentRoot(prepared.root)
    link = os.link
    changed = False

    def raced(source: Path, target: Path) -> None:
        nonlocal changed
        link(source, target)
        if target.name != hashlib.sha256(PDF).hexdigest() or changed:
            return
        changed = True
        if change == "revision":
            papers = PaperFacts(root.database, root.data_root)
            paper = papers.show(prepared.paper_id)
            corrected = papers.correct(
                dict(
                    version_id=paper.version_id,
                    request_id="raced-correction",
                    actor="owner",
                    reason="synthetic",
                    fields={
                        "title": {
                            "value": "Changed at publication",
                            "locator": "manual/title",
                        }
                    },
                )
            )
            assert corrected.status == "retained"
        else:
            replaced = select(
                prepared.root,
                prepared.view_id,
                "raced-selection",
                "--position",
                "2",
                "--replaces",
                prepared.selection_id,
                "--replacement-reason",
                "更换合成样本",
            )
            assert replaced.exit_code == 0, replaced.output

    monkeypatch.setattr("paper_radar.storage.blob_store.os.link", raced)
    failed = attach(prepared, tmp_path)
    assert changed and failed.exit_code == 2 and reason in failed.output, failed.output
    assert len(PdfSamples(root.database, root.data_root).history()) == 1
    assert BodyService(root.database, root.data_root).pdfs(prepared.paper_id) == ()
    assert PdfSamples(root.database, root.data_root).samples() == ()
