"""B-E11 独立 D1:显式提取、资源拒绝及安全历史投影。"""

import json
from pathlib import Path

import pytest

from tests.config_test_support import run_cli
from tests.experiment_extract_support import executor, extract_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def test_extract_help_is_cold_and_complete(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "experiment", "extract", "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for text in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "130",
        "32",
        "cgroup",
    ):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_unbounded_cgroup_refuses_before_lock_or_budget(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    (prepared.group / "memory.max").write_text("max")
    result = prepared.extract()
    assert result.exit_code == 2, result.output
    assert "cgroup_limit_invalid" in result.output
    assert not (prepared.root.data_root / ".body-docling.lock").exists()


def test_success_records_distinct_peaks_and_caches_without_read(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from paper_radar import docling_executor
    from paper_radar.docling_execution.models import WorkerRequest, WorkerResponse
    from tests.test_fulltext_artifacts import document

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    requests: list[WorkerRequest] = []

    class Executor:
        def execute(self, request: WorkerRequest) -> WorkerResponse:
            requests.append(request)
            assert request.timeout_seconds == 300
            assert request.threads == 4
            assert request.memory_limit_bytes == 34359738368
            assert Path(request.model_root).is_dir()
            return WorkerResponse(
                document=document(),
                document_json='{"synthetic":true}',
                peak_memory_bytes=4096,
            )

    monkeypatch.setattr(docling_executor, "DoclingProcess", Executor)
    monkeypatch.setattr(
        docling_executor,
        "probe_docling_runtime",
        lambda *_args, **_kwargs: SimpleNamespace(passed=True),
    )
    result = prepared.extract()
    assert result.exit_code == 0, result.output
    output = json.loads(result.stdout)
    assert output["attempts"][0]["worker_ru_maxrss_bytes"] == 4096
    assert output["executions"][0]["cgroup_memory_peak_bytes"] == 123456789
    assert output["host_memory_disclosure"] == 1024
    assert output["cached"] is False
    (prepared.group / "memory.peak").write_text("999999999")
    repeated = prepared.extract()
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.stdout)["cached"] is True
    assert json.loads(repeated.stdout)["executions"] == output["executions"]
    assert len(requests) == 1
    assert "PRIVATE_SYNTHETIC_ABSTRACT" not in requests[0].model_dump_json()
    assert "10.1029/" not in requests[0].model_dump_json()


def test_restore_keeps_bounded_execution_and_exact_evidence_without_models(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import subprocess
    import sys

    from typer.testing import CliRunner

    from paper_radar.cli import app

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    executor(monkeypatch)
    extracted = prepared.extract()
    assert extracted.exit_code == 0, extracted.output
    root = prepared.root
    args = [
        "paper",
        "trace",
        prepared.prepared.paper_id,
        "--database",
        str(root.database),
        "--data-root",
        str(root.data_root),
        "--snapshot",
        prepared.snapshot,
        "--json",
    ]
    trace = CliRunner().invoke(app, args)
    assert trace.exit_code == 0, trace.output
    payload = json.loads(trace.stdout)["workflow"]
    assert payload["extractions"][0]["attempts"][0]["worker_ru_maxrss_bytes"] == 4096
    assert payload["bounded_executions"][0]["cgroup_memory_peak_bytes"] == 123456789
    logged = (root.root / "logs/runtime.jsonl").read_bytes()
    assert json.loads(logged.splitlines()[-2])["event"] == "run_started"
    assert json.loads(logged.splitlines()[-1])["event"] == "run_finished"
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
    restore = subprocess.run(
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
    assert restore.returncode == 0, restore.stdout + restore.stderr
    for path in (
        root.root,
        prepared.models,
        prepared.prepared.credentials,
        tmp_path / "synthetic.pdf",
    ):
        if path.exists():
            path.rename(path.with_name(path.name + "-unavailable"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.experiment_extract_recovery_worker",
            str(restored),
            prepared.prepared.paper_id,
            prepared.snapshot,
        ],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == json.loads(trace.stdout)


@pytest.mark.parametrize("corruption", ["resource", "peak", "sample", "audit"])
def test_backup_rejects_broken_bounded_execution_closure(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    import sqlite3

    from typer.testing import CliRunner

    from paper_radar.cli import app

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    executor(monkeypatch)
    assert prepared.extract().exit_code == 0
    root = prepared.root
    with sqlite3.connect(root.database) as connection:
        if corruption == "peak":
            connection.execute("DROP TRIGGER experiment_extraction_peaks_no_update")
            connection.execute(
                "UPDATE experiment_extraction_peaks SET cgroup_peak_bytes=-1"
            )
        elif corruption == "audit":
            connection.execute(
                "UPDATE body_extraction_attempts SET executor_audit_json=NULL"
            )
        else:
            connection.execute("DROP TRIGGER experiment_extractions_no_update")
            if corruption == "sample":
                connection.execute(
                    "UPDATE experiment_extractions SET sample_id='unknown'"
                )
            else:
                connection.execute("UPDATE experiment_extractions SET record_json='{}'")
    result = CliRunner().invoke(
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
    expected = "database_invalid" if corruption == "sample" else "registration_invalid"
    assert result.exit_code == 2 and expected in result.output, result.output


@pytest.mark.parametrize("case", ["no_text", "quality"])
def test_actual_automatic_quality_failure_is_permanent(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from paper_radar.docling_execution.models import WorkerResponse
    from tests.test_fulltext_artifacts import document

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    raw = document().model_dump(mode="json")
    if case == "no_text":
        raw["has_text_layer"] = False
    else:
        raw["blocks"][1]["orig"] = "Exact source \ufffd = 2."
    from paper_radar.fulltext.canonical import CanonicalDocument

    doc = CanonicalDocument.model_validate_json(json.dumps(raw))
    requests = executor(
        monkeypatch,
        WorkerResponse(
            document=doc, document_json='{"synthetic":true}', peak_memory_bytes=7777
        ),
    )
    result = prepared.extract()
    assert result.exit_code == 2, result.output
    payload = json.loads(result.stdout)
    assert payload["artifact_id"] is not None
    assert payload["permanent_failure"] is True
    assert payload["quality_failure"] == (
        "pdf_text_layer" if case == "no_text" else "text_integrity"
    )
    assert prepared.extract().exit_code == 2
    assert len(requests) == 1


@pytest.mark.parametrize("phase", ["claim", "settle"])
def test_execution_fact_write_failure_is_atomic_with_body(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.experiment.extraction import Extractions
    from tests.artifact_support import fail_sql

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    requests = executor(monkeypatch)
    statement = (
        "INSERT INTO experiment_extractions"
        if phase == "claim"
        else "INSERT INTO experiment_extraction_peaks"
    )
    with fail_sql(statement):
        result = prepared.extract()
    assert result.exit_code == 2, result.output
    body = BodyService(prepared.root.database, prepared.root.data_root)
    views = body.extractions(prepared.prepared.paper_id)
    if phase == "claim":
        assert views == ()
        assert requests == []
    else:
        assert views[0].attempts[0].settled_at is None
        assert (
            Extractions(prepared.root.database, prepared.root.data_root).history()[0][
                "cgroup_memory_peak_bytes"
            ]
            == "unknown"
        )
    assert prepared.extract().exit_code == 0
    assert len(requests) == (1 if phase == "claim" else 2)
    if phase == "settle":
        views = body.extractions(prepared.prepared.paper_id)
        assert views[0].attempts[0].failure == "outcome_unknown"
        assert views[0].remaining_attempts == 0


def test_bounded_execution_tables_are_append_only(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    executor(monkeypatch)
    assert prepared.extract().exit_code == 0
    with sqlite3.connect(prepared.root.database) as connection:
        for table in ("experiment_extractions", "experiment_extraction_peaks"):
            for statement in (
                f"UPDATE {table} SET attempt_id=attempt_id",
                f"DELETE FROM {table}",
                f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
            ):
                with pytest.raises(sqlite3.IntegrityError, match="append_only"):
                    connection.execute(statement)


@pytest.mark.parametrize(
    "case",
    [
        "too_large",
        "swap",
        "missing",
        "duplicate",
        "traversal",
        "symlink",
        "mount_missing",
        "mount_ambiguous",
    ],
)
def test_current_cgroup_must_be_unambiguous_and_bounded(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.experiment import extraction

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    requests = executor(monkeypatch)
    if case == "too_large":
        (prepared.group / "memory.max").write_text("8589934593")
    elif case == "swap":
        (prepared.group / "memory.swap.max").write_text("1")
    elif case == "missing":
        (prepared.group / "memory.swap.max").unlink()
    elif case == "duplicate":
        prepared.proc.write_text("0::/user/synthetic\n0::/user/synthetic\n")
    elif case == "traversal":
        prepared.proc.write_text("0::/../synthetic\n")
    elif case == "symlink":
        (prepared.group / "memory.max").unlink()
        (prepared.group / "memory.max").symlink_to(prepared.group / "memory.swap.max")
    else:
        mounts = tmp_path / "mountinfo"
        mounts.write_text(
            ""
            if case == "mount_missing"
            else f"1 0 0:1 / {prepared.group.parent.parent} rw - cgroup2 cgroup rw\n"
            * 2
        )
        monkeypatch.setattr(
            extraction,
            "RESOURCE_PATHS",
            extraction.ResourcePaths(
                prepared.proc,
                prepared.group.parent.parent,
                prepared.meminfo,
                mounts,
                extraction.RESOURCE_PATHS.user_scope_properties,
            ),
        )
    result = prepared.extract()
    assert result.exit_code == 2 and "cgroup_limit_invalid" in result.output, (
        result.output
    )
    assert requests == []
    assert (
        BodyService(prepared.root.database, prepared.root.data_root).extractions(
            prepared.prepared.paper_id
        )
        == ()
    )
    assert not (prepared.root.data_root / ".body-docling.lock").exists()


@pytest.mark.parametrize(
    "failure,permanent",
    [
        ("timeout", False),
        ("resource_exhausted", False),
        ("extraction_failed_no_text_layer", True),
        ("extraction_failed_quality_gate", True),
    ],
)
def test_failure_stops_and_preserves_authoritative_budget(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    permanent: bool,
) -> None:
    from paper_radar.docling_execution.models import WorkerResponse
    from paper_radar.read_tasks import ReadTasks

    prepared = extract_fixture(feed, tmp_path, monkeypatch)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Read must not run")

    monkeypatch.setattr(ReadTasks, "run_once", forbidden)
    response = WorkerResponse.model_validate(
        dict(failure=failure, peak_memory_bytes=8192)
    )
    requests = executor(monkeypatch, response)
    first = prepared.extract()
    assert first.exit_code == 2, first.output
    payload = json.loads(first.stdout)
    assert payload["attempts"][0]["failure"] == failure
    assert payload["permanent_failure"] is permanent
    assert payload["automatic_quality"] == "unknown"
    second = prepared.extract()
    third = prepared.extract()
    assert second.exit_code == third.exit_code == 2
    assert len(requests) == (1 if permanent else 2)
    assert json.loads(third.stdout)["remaining_attempts"] == (1 if permanent else 0)
    logged = (prepared.root.root / "logs/runtime.jsonl").read_text()
    assert all(
        secret not in first.output + second.output + logged
        for secret in (
            "PRIVATE_SYNTHETIC_ABSTRACT",
            "PRIVATE_OWNER_REASON",
            "oauth-test-only-sensitive-sentinel",
            str(prepared.models),
        )
    )


@pytest.mark.parametrize(
    "case", ["unknown_host_and_peak", "invalid_host_encoding", "mount_root"]
)
def test_optional_memory_unknown_and_namespaced_mount_root(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from paper_radar.experiment import extraction

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    executor(monkeypatch)
    if case == "unknown_host_and_peak":
        prepared.meminfo.unlink()
        (prepared.group / "memory.peak").unlink()
    elif case == "invalid_host_encoding":
        prepared.meminfo.write_bytes(b"\xff")
    else:
        membership = prepared.proc.read_text().strip().removeprefix("0::")
        mounts = tmp_path / "mountinfo"
        mounts.write_text(
            f"1 0 0:1 {membership.rsplit('/app.slice/', 1)[0]} "
            f"{prepared.group.parent.parent} "
            "rw - cgroup2 cgroup rw\n"
        )
        monkeypatch.setattr(
            extraction,
            "RESOURCE_PATHS",
            extraction.ResourcePaths(
                prepared.proc,
                prepared.group.parent.parent,
                prepared.meminfo,
                mounts,
                extraction.RESOURCE_PATHS.user_scope_properties,
            ),
        )
    result = prepared.extract()
    assert result.exit_code == 0, result.output
    if case == "unknown_host_and_peak":
        output = json.loads(result.stdout)
        assert output["host_memory_disclosure"] == "unknown"
        assert output["executions"][0]["cgroup_memory_peak_bytes"] == "unknown"
    elif case == "invalid_host_encoding":
        assert json.loads(result.stdout)["host_memory_disclosure"] == "unknown"


@pytest.mark.parametrize(
    "case",
    ["changed_sample", "changed_cgroup", "model_hash", "disk", "invalid_runtime"],
)
def test_preflight_failure_or_change_never_claims(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    import os
    from types import SimpleNamespace

    from paper_radar.body import BodyService
    from paper_radar.papers import PaperFacts

    prepared = extract_fixture(feed, tmp_path, monkeypatch)

    def change() -> None:
        if case == "changed_cgroup":
            (prepared.group / "memory.max").write_text("max")
        elif case == "changed_sample":
            paper = PaperFacts(prepared.root.database, prepared.root.data_root).show(
                prepared.prepared.paper_id
            )
            PaperFacts(prepared.root.database, prepared.root.data_root).correct(
                dict(
                    version_id=paper.version_id,
                    request_id="changed",
                    actor="owner",
                    reason="synthetic",
                    fields={
                        "title": {"value": "Changed title", "locator": "manual/title"}
                    },
                )
            )

    requests = executor(monkeypatch, on_probe=change)
    expected = (
        "frozen_version_changed" if case == "changed_sample" else "cgroup_limit_invalid"
    )
    if case == "model_hash":
        next(path for path in prepared.models.rglob("config.json")).write_bytes(
            b"corrupt"
        )
        expected = "model_deployment_invalid"
    elif case == "disk":
        monkeypatch.setattr(
            os,
            "statvfs",
            lambda _: SimpleNamespace(f_bavail=0, f_frsize=4096),
        )
        expected = "model_snapshot_space_insufficient"
    elif case == "invalid_runtime":
        from tests.test_experiment_candidates_cli import invoke

        result = invoke(
            "extract",
            prepared.prepared.paper_id,
            "--root",
            str(prepared.root.root),
            "--snapshot",
            prepared.snapshot,
            "--model-root",
            str(prepared.models),
            "--timeout-seconds",
            "-1",
            "--threads",
            "4",
        )
        assert result.exit_code == 2 and "runtime_selection_invalid" in result.output
        return
    result = prepared.extract()
    assert result.exit_code == 2 and expected in result.output, result.output
    assert requests == []
    assert (
        BodyService(prepared.root.database, prepared.root.data_root).extractions(
            prepared.prepared.paper_id
        )
        == ()
    )


@pytest.mark.parametrize("change", ["cgroup", "selection"])
def test_waiting_extraction_rechecks_resources_and_current_selection(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    import fcntl
    import io
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from paper_radar.body import BodyService
    from paper_radar.experiment.extraction import ExtractionError, extract_once
    from paper_radar.experiment.pdf import PdfError
    from tests.test_experiment_selection_cli import select

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    requests = executor(monkeypatch)
    waiting = Event()

    class WaitOutput(io.StringIO):
        def write(self, value: str) -> int:
            if "另一个 Docling 转换正在进行" in value:
                waiting.set()
            return super().write(value)

    monkeypatch.setattr(sys, "stderr", WaitOutput())
    root = prepared.root
    with (
        (root.data_root / ".body-docling.lock").open("w") as lock,
        ThreadPoolExecutor(1) as pool,
    ):
        fcntl.flock(lock, fcntl.LOCK_EX)
        future = pool.submit(
            extract_once,
            root,
            paper_id=prepared.prepared.paper_id,
            snapshot=prepared.snapshot,
            model_root=prepared.models,
            timeout_seconds=300,
            threads=4,
        )
        try:
            assert waiting.wait(20)
            if change == "cgroup":
                (prepared.group / "memory.max").write_text("max")
            else:
                selected = select(
                    root.root,
                    prepared.prepared.view_id,
                    "replace-while-waiting",
                    "--position",
                    "2",
                    "--replaces",
                    prepared.prepared.selection_id,
                    "--replacement-reason",
                    "synthetic owner replacement",
                )
                assert selected.exit_code == 0, selected.output
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
        with pytest.raises((ExtractionError, PdfError)) as error:
            future.result(timeout=20)
    assert isinstance(error.value, (ExtractionError, PdfError))
    assert error.value.reason == (
        "cgroup_limit_invalid" if change == "cgroup" else "selection_changed"
    )
    assert requests == []
    assert (
        BodyService(root.database, root.data_root).extractions(
            prepared.prepared.paper_id
        )
        == ()
    )
