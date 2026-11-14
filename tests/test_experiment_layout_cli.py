"""B-E12 独立 D1:所有者六项核查与持久版式材料。"""

from pathlib import Path

import pytest

from tests.config_test_support import run_cli
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed

# 新执行入口独立 D1 装配守卫;历史 audit 守卫原字节保持。
DELIVERED_EXECUTION_ENTRIES = ("layout-review",)


@pytest.mark.parametrize("command", ["layout-review", "layout-materials"])
def test_layout_help_is_cold_and_complete(tmp_path: Path, command: str) -> None:
    import os
    import subprocess
    import sys

    result = run_cli(tmp_path, "experiment", command, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for text in ("参数", "副作用", "自动配额", "输出去向", "常见失败", "示例", "130"):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []
    guarded = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
def guard(event, args):
    if (event == 'import'
        and args[0].split('.')[0] in {'docling','torch','pypdfium2','PIL'}):
        raise AssertionError('SDK import forbidden')
    if event in {'sqlite3.connect', 'socket.__new__'}:
        raise AssertionError('external IO forbidden')
sys.addaudithook(guard)
from typer.testing import CliRunner
from paper_radar.cli import app
result = CliRunner().invoke(app, ['experiment', sys.argv[1], '--help'])
assert result.exit_code == 0, (result.output, repr(result.exception))
""",
            command,
        ],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert guarded.returncode == 0, guarded.stderr
    assert list(tmp_path.iterdir()) == []


def test_owner_review_is_structured_and_rejection_is_permanent(
    feed: "FeedFixture", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from tests.experiment_extract_support import executor, extract_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    executor(monkeypatch)
    assert prepared.extract().exit_code == 0
    from paper_radar.body import BodyService

    identity = (
        BodyService(prepared.root.database, prepared.root.data_root)
        .current_body(prepared.prepared.paper_id)
        .identity
    )
    assert identity is not None
    args = [
        "layout-review",
        prepared.prepared.paper_id,
        "--root",
        str(prepared.root.root),
        "--fingerprint",
        identity.extraction_fingerprint,
        "--reading-sha256",
        identity.reading_sha256,
        "--evidence-map-sha256",
        identity.evidence_map_sha256,
        "--reviewer",
        "owner",
        "--recorder",
        "agent",
    ]
    incomplete = invoke(*args, "--request-id", "missing")
    assert incomplete.exit_code == 2
    assert "invalid_arguments" in incomplete.output
    checks = [
        "--body-boundary",
        "true",
        "--reading-order",
        "true",
        "--sections",
        "true",
        "--headers-footers",
        "true",
        "--provenance",
        "true",
        "--restricted-content",
        "false",
    ]
    rejected = invoke(
        *args, "--request-id", "reject", *checks, "--note", "PRIVATE_OWNER_NOTE"
    )
    assert rejected.exit_code == 0, rejected.output
    payload = json.loads(rejected.stdout)
    assert payload["passed"] is False
    assert payload["reviewer"] == "owner" and payload["recorder"] == "agent"
    assert payload["quality"] == "failed"
    assert "PRIVATE_OWNER_NOTE" not in rejected.stdout
    assert (
        json.loads(
            invoke(
                *args, "--request-id", "reject", *checks, "--note", "PRIVATE_OWNER_NOTE"
            ).stdout
        )["replayed"]
        is True
    )
    checks[-1] = "true"
    overwrite = invoke(*args, "--request-id", "pass-after-reject", *checks)
    assert overwrite.exit_code == 2
    assert "layout_conflict" in overwrite.output
    from paper_radar.experiment.layout import LayoutReviews

    history = LayoutReviews(prepared.root.database, prepared.root.data_root).history()
    assert len(history) == 1
    assert "PRIVATE_OWNER_NOTE" not in json.dumps(history)
    assert (
        "PRIVATE_OWNER_NOTE"
        not in (prepared.root.root / "logs/runtime.jsonl").read_text()
    )


def test_materials_show_all_six_comparisons_without_business_writes(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from paper_radar.body import BodyService
    from tests.experiment_extract_support import executor, extract_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    executor(monkeypatch)
    assert prepared.extract().exit_code == 0
    identity = (
        BodyService(prepared.root.database, prepared.root.data_root)
        .current_body(prepared.prepared.paper_id)
        .identity
    )
    assert identity is not None
    from paper_radar.experiment import layout_rendering

    class Renderer:
        def render(self, pdf: bytes, evidence_map: object, directory: Path) -> None:
            assert pdf.startswith(b"%PDF-")
            (directory / "page-1.png").write_bytes(b"synthetic image")

    monkeypatch.setattr(layout_rendering, "PdfRenderer", Renderer)
    before = prepared.root.database.read_bytes()
    logs = (prepared.root.root / "logs/runtime.jsonl").read_bytes()
    args = [
        "layout-materials",
        prepared.prepared.paper_id,
        "--root",
        str(prepared.root.root),
        "--fingerprint",
        identity.extraction_fingerprint,
        "--reading-sha256",
        identity.reading_sha256,
        "--evidence-map-sha256",
        identity.evidence_map_sha256,
    ]
    result = invoke(*args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert len(payload["materials"]) == 6
    assert "Exact source" not in result.output
    assert str(tmp_path) not in result.output
    materials = [prepared.root.root / path for path in payload["materials"]]
    assert all(path.is_file() for path in materials)
    assert "Results" in materials[2].read_text()
    evidence = materials[4].read_text()
    for text in ("Exact source α = 2.", "charspan", "e000002", "bbox", "orig"):
        assert text in evidence
    assert "未覆盖" in materials[5].read_text()
    assert "passed" not in "".join(path.read_text() for path in materials)
    assert invoke(*args).exit_code == 0
    assert prepared.root.database.read_bytes() == before
    assert (prepared.root.root / "logs/runtime.jsonl").read_bytes() == logs


@pytest.mark.parametrize(
    ("rotation", "origin", "size"),
    [(0, "top_left", (720, 45)), (90, "bottom_left", (45, 720))],
)
def test_registered_synthetic_pdf_renders_real_crops_with_rotation_and_origin(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rotation: int,
    origin: str,
    size: tuple[int, int],
) -> None:
    import importlib
    import json

    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = layout_fixture(
        feed, tmp_path, monkeypatch, rotation=rotation, origin=origin
    )
    result = invoke(*prepared.args("layout-materials"))
    assert result.exit_code == 0, result.output
    first = prepared.extraction.root.root / json.loads(result.stdout)["materials"][0]
    imaging = importlib.import_module("PIL.Image")
    with imaging.open(first.parent / "block-1-0.png") as crop:
        assert crop.size == size
        assert crop.convert("RGB").getpixel((size[0] // 2, size[1] // 2)) == (255, 0, 0)
    assert "Results" not in result.output


@pytest.mark.parametrize("command", DELIVERED_EXECUTION_ENTRIES)
def test_all_six_owner_inputs_make_document_gate_and_safe_trace(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    import json

    from paper_radar.body import BodyService
    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    receipt = prepared.review(note="PRIVATE_OWNER_NOTE", command=command)
    assert receipt["passed"] is True
    assert receipt["quality"] == "experiment_document_gate"
    root = prepared.extraction.root
    logged = [
        json.loads(line)
        for line in (root.root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert (
        logged[-2]["event"] == "run_started" and logged[-2]["component"] == "experiment"
    )
    assert (
        logged[-1]["event"] == "run_finished"
        and logged[-1]["component"] == "experiment"
    )
    assert "PRIVATE_OWNER_NOTE" not in (root.root / "logs/runtime.jsonl").read_text()
    from typer.testing import CliRunner

    from paper_radar.cli import app

    traced = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            prepared.extraction.prepared.paper_id,
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--snapshot",
            prepared.extraction.snapshot,
            "--json",
        ],
    )
    assert traced.exit_code == 0, traced.output
    workflow = json.loads(traced.stdout)["workflow"]
    assert workflow["layout_reviews"][0]["checks"]["restricted_content"] is True
    assert workflow["extractions"][0]["quality"] == "experiment_document_gate"
    assert "PRIVATE_OWNER_NOTE" not in traced.output
    body = BodyService(root.database, root.data_root)
    body.validate_all()
    no_owner = invoke(
        *prepared.args("layout-review"),
        "--reviewer",
        "agent",
        "--recorder",
        "agent",
        "--request-id",
        "fake",
        "--body-boundary",
        "true",
        "--reading-order",
        "true",
        "--sections",
        "true",
        "--headers-footers",
        "true",
        "--provenance",
        "true",
        "--restricted-content",
        "true",
    )
    assert no_owner.exit_code == 2 and "owner_conclusions_required" in no_owner.output


def test_layout_backup_and_subprocess_restore_preserve_review_and_exact_evidence(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import os
    import subprocess
    import sys

    from typer.testing import CliRunner

    from paper_radar.cli import app
    from tests.experiment_layout_support import layout_fixture

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    prepared.review(note="PRIVATE_OWNER_NOTE")
    root = prepared.extraction.root
    trace = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            prepared.extraction.prepared.paper_id,
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--snapshot",
            prepared.extraction.snapshot,
            "--json",
        ],
    )
    assert trace.exit_code == 0, trace.output
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
        prepared.extraction.models,
        prepared.extraction.prepared.credentials,
        tmp_path / "synthetic.pdf",
    ):
        if path.exists():
            path.rename(path.with_name(path.name + "-unavailable"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.experiment_layout_recovery_worker",
            str(restored),
            prepared.extraction.prepared.paper_id,
            prepared.extraction.snapshot,
        ],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == json.loads(trace.stdout)
    assert "PRIVATE_OWNER_NOTE" not in result.stdout


@pytest.mark.parametrize(
    "missing",
    [
        "body-boundary",
        "reading-order",
        "sections",
        "headers-footers",
        "provenance",
        "restricted-content",
    ],
)
def test_each_missing_owner_conclusion_refuses_without_creating_root(
    tmp_path: Path, missing: str
) -> None:
    from tests.test_experiment_candidates_cli import invoke

    args = [
        "layout-review",
        "paper",
        "--root",
        str(tmp_path / "absent"),
        "--fingerprint",
        "a" * 64,
        "--reading-sha256",
        "b" * 64,
        "--evidence-map-sha256",
        "c" * 64,
        "--reviewer",
        "owner",
        "--recorder",
        "agent",
        "--request-id",
        "review",
    ]
    for name in [
        "body-boundary",
        "reading-order",
        "sections",
        "headers-footers",
        "provenance",
        "restricted-content",
    ]:
        if name != missing:
            args.extend(["--" + name, "true"])
    result = invoke(*args)
    assert result.exit_code == 2 and "invalid_arguments" in result.output
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("case", ["dependency", "identity", "symlink"])
def test_materials_refuse_missing_renderer_wrong_identity_and_unsafe_view(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    import hashlib
    import importlib
    import json
    from dataclasses import asdict

    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    args = prepared.args("layout-materials")
    expected = "body_identity_mismatch"
    if case == "dependency":
        original = importlib.import_module

        def missing(name: str, package: str | None = None) -> object:
            if name in {"pypdfium2", "PIL.ImageDraw"}:
                raise ImportError("PRIVATE_DEPENDENCY_PATH")
            return original(name, package)

        monkeypatch.setattr(importlib, "import_module", missing)
        expected = "renderer_dependency_missing"
    elif case == "identity":
        args[-1] = "d" * 64
    else:
        identifier = hashlib.sha256(
            json.dumps(asdict(prepared.identity), sort_keys=True).encode()
        ).hexdigest()
        (prepared.extraction.root.views / f"layout-{identifier}").symlink_to(tmp_path)
        expected = "unsafe_material_path"
    before = prepared.extraction.root.database.read_bytes()
    result = invoke(*args)
    assert result.exit_code == 2 and expected in result.output, result.output
    assert "PRIVATE_DEPENDENCY_PATH" not in result.output
    assert prepared.extraction.root.database.read_bytes() == before


@pytest.mark.parametrize(
    "stop",
    ["INSERT INTO body_layout_reviews", "INSERT INTO experiment_layout_recordings"],
)
def test_review_and_owner_record_are_one_atomic_transaction(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.body.extraction import LAYOUT_CHECKS
    from paper_radar.body.models import BodyError
    from paper_radar.experiment.layout import LayoutReviews
    from tests.artifact_support import fail_sql
    from tests.experiment_layout_support import layout_fixture

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    root = prepared.extraction.root
    reviews = LayoutReviews(root.database, root.data_root)
    with fail_sql(stop), pytest.raises(BodyError) as error:
        reviews.record(
            root,
            prepared.extraction.prepared.paper_id,
            prepared.identity,
            checks={key: True for key in LAYOUT_CHECKS},
            reviewer="owner",
            recorder="agent",
            request_id="fault",
        )
    assert error.value.reason == "database_failed"
    assert reviews.history() == ()
    body = BodyService(root.database, root.data_root)
    assert (
        body.extractions(prepared.extraction.prepared.paper_id)[0].quality.basis
        == "absent"
    )
    assert prepared.review(request="fault")["quality"] == "experiment_document_gate"


@pytest.mark.parametrize("case", ["record", "unlinked", "owner", "note"])
def test_backup_rejects_broken_owner_review_closure(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    import sqlite3

    from typer.testing import CliRunner

    from paper_radar.cli import app
    from tests.experiment_layout_support import layout_fixture

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    prepared.review(note="PRIVATE_OWNER_NOTE")
    root = prepared.extraction.root
    with sqlite3.connect(root.database) as connection:
        connection.execute("DROP TRIGGER experiment_layout_recordings_no_update")
        connection.execute("DROP TRIGGER experiment_layout_recordings_no_delete")
        if case == "record":
            connection.execute(
                "UPDATE experiment_layout_recordings SET record_json='{}'"
            )
        elif case == "unlinked":
            connection.execute("DELETE FROM experiment_layout_recordings")
        elif case == "owner":
            connection.execute(
                "UPDATE experiment_layout_recordings SET "
                "record_json=replace(record_json, '\"owner\"', '\"agent\"')"
            )
        else:
            connection.execute(
                "UPDATE body_layout_reviews SET note='PRIVATE_CORRUPTED_NOTE'"
            )
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
    assert result.exit_code == 2 and "registration_invalid" in result.output, (
        result.output
    )
    assert "PRIVATE_OWNER_NOTE" not in result.output
    assert "PRIVATE_CORRUPTED_NOTE" not in result.output


def test_materials_preserve_furniture_hierarchy_and_restricted_source_separation(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from paper_radar.fulltext.canonical import CanonicalBlock, CanonicalProvenance
    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_candidates_cli import invoke
    from tests.test_fulltext_artifacts import document

    canonical = document()
    extra = []
    for index, (label, text, unreliable) in enumerate(
        [
            ("page_header", "PRIVATE_HEADER", False),
            ("formula", "a = b", False),
            ("table", "x 1 y 2", False),
            ("text", "PRIVATE_UNRELIABLE", True),
        ],
        2,
    ):
        extra.append(
            CanonicalBlock(
                ref=f"synthetic-{index}",
                order=(index,),
                label=label,
                orig=text,
                text=text,
                unreliable=unreliable,
                content_layer="furniture" if label == "page_header" else "body",
                provenance=(
                    CanonicalProvenance(
                        page_no=1,
                        bbox=(
                            20.0,
                            float(index * 40 + 20),
                            500.0,
                            float(index * 40 + 50),
                        ),
                        charspan=(0, len(text)),
                    ),
                ),
            )
        )
    extra.append(
        CanonicalBlock(
            ref="generated",
            order=(6,),
            label="formula",
            role="generated",
            generated_text="PRIVATE_LATEX_CANDIDATE",
            provenance=(
                CanonicalProvenance(
                    page_no=1, bbox=(20.0, 300.0, 500.0, 330.0), charspan=(0, 0)
                ),
            ),
        )
    )
    canonical = canonical.model_copy(update={"blocks": canonical.blocks + tuple(extra)})
    prepared = layout_fixture(feed, tmp_path, monkeypatch, canonical=canonical)
    result = invoke(*prepared.args("layout-materials"))
    assert result.exit_code == 0, result.output
    paths = [
        prepared.extraction.root.root / name
        for name in json.loads(result.stdout)["materials"]
    ]
    assert "层级=1" in paths[2].read_text()
    furniture = paths[3].read_text()
    assert (
        "PRIVATE_HEADER" in furniture
        and "去留=furniture" in furniture
        and "去留=保留" in furniture
    )
    restricted = paths[5].read_text()
    for content in (
        "a = b",
        "x 1 y 2",
        "PRIVATE_UNRELIABLE",
        "PRIVATE_LATEX_CANDIDATE",
        "生成候选不可作为原文",
        "降级",
    ):
        assert content in restricted
    evidence = paths[4].read_text()
    assert "PRIVATE_LATEX_CANDIDATE" not in evidence
    assert "PRIVATE_" not in result.output


@pytest.mark.parametrize("change", ["selection", "revision"])
def test_review_rechecks_current_sample_inside_write_transaction(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    from sqlalchemy import Connection, Engine, event

    from paper_radar.body.extraction import LAYOUT_CHECKS
    from paper_radar.experiment.layout import LayoutReviews
    from paper_radar.experiment.pdf import PdfError
    from paper_radar.papers import PaperFacts
    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_selection_cli import select

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    root = prepared.extraction.root
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
            "layout-review"
        ):
            waiting.set()
            assert release.wait(30)

    event.listen(Engine, "before_cursor_execute", pause)
    reviews = LayoutReviews(root.database, root.data_root)
    try:
        with ThreadPoolExecutor(1, thread_name_prefix="layout-review") as pool:
            future = pool.submit(
                reviews.record,
                root,
                prepared.extraction.prepared.paper_id,
                prepared.identity,
                checks={key: True for key in LAYOUT_CHECKS},
                reviewer="owner",
                recorder="agent",
                request_id="waiting",
            )
            try:
                assert waiting.wait(30)
                if change == "selection":
                    changed = select(
                        root.root,
                        prepared.extraction.prepared.view_id,
                        "replacement",
                        "--position",
                        "2",
                        "--replaces",
                        prepared.extraction.prepared.selection_id,
                        "--replacement-reason",
                        "synthetic owner replacement",
                    )
                    assert changed.exit_code == 0, changed.output
                else:
                    papers = PaperFacts(root.database, root.data_root)
                    current = papers.show(prepared.extraction.prepared.paper_id)
                    corrected = papers.correct(
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
                    )
                    assert corrected.status == "retained"
            finally:
                release.set()
            with pytest.raises(PdfError) as error:
                future.result(timeout=30)
            assert error.value.reason == (
                "selection_changed"
                if change == "selection"
                else "frozen_version_changed"
            )
    finally:
        event.remove(Engine, "before_cursor_execute", pause)
    assert reviews.history() == ()


@pytest.mark.parametrize("command", ["layout-materials", "layout-review"])
def test_multiple_successful_body_identities_never_guess_latest(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    import json

    from paper_radar.config import compile_config
    from tests.config_projection_support import new_yaml_version
    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    root = prepared.extraction.root
    new_yaml_version(
        root.settings,
        "extraction",
        lambda c: c["models"]["layout"].update(commit_sha="9" * 40),
    )
    manifest = prepared.extraction.models / "deployment.json"
    deployment = json.loads(manifest.read_text())
    for model in deployment["models"]:
        if "layout" in model["repo_id"]:
            model["commit_sha"] = "9" * 40
    manifest.write_text(json.dumps(deployment))
    prepared.extraction.snapshot = compile_config(
        root.settings, root.database
    ).snapshot_id
    second = prepared.extraction.extract()
    assert second.exit_code == 0, second.output
    args = prepared.args(command)
    if command == "layout-review":
        args += [
            "--reviewer",
            "owner",
            "--recorder",
            "agent",
            "--request-id",
            "ambiguous",
        ]
        for name in [
            "body-boundary",
            "reading-order",
            "sections",
            "headers-footers",
            "provenance",
            "restricted-content",
        ]:
            args += ["--" + name, "true"]
    result = invoke(*args)
    assert result.exit_code == 2 and "ambiguous_extractions" in result.output, (
        result.output
    )


@pytest.mark.parametrize("command", ["layout-review", "layout-materials"])
def test_layout_obeys_visibility_before_business_or_view_writes(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    from paper_radar.calibration.visibility import (
        Visibility,
        VisibilityCapability,
        VisibilityPermission,
    )
    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    original = Visibility.permission

    def denied(
        self: Visibility, capability: VisibilityCapability
    ) -> VisibilityPermission:
        if capability in {
            VisibilityCapability.SET_DECISION,
            VisibilityCapability.AGENT_CONTENT,
        }:
            return VisibilityPermission.DENIED
        return original(self, capability)

    monkeypatch.setattr(Visibility, "permission", denied)
    before = prepared.extraction.root.database.read_bytes()
    args = prepared.args(command)
    if command == "layout-review":
        args += ["--reviewer", "owner", "--recorder", "agent", "--request-id", "hidden"]
        for name in [
            "body-boundary",
            "reading-order",
            "sections",
            "headers-footers",
            "provenance",
            "restricted-content",
        ]:
            args += ["--" + name, "true"]
    result = invoke(*args)
    assert result.exit_code == 2 and "visibility_denied" in result.output, result.output
    assert prepared.extraction.root.database.read_bytes() == before
    assert not list(prepared.extraction.root.views.glob("layout-*"))


@pytest.mark.parametrize("action", ["UPDATE", "DELETE", "REPLACE"])
def test_layout_recordings_are_append_only(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    import sqlite3

    from tests.experiment_layout_support import layout_fixture

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    prepared.review()
    statements = {
        "UPDATE": "UPDATE experiment_layout_recordings SET record_json='{}'",
        "DELETE": "DELETE FROM experiment_layout_recordings",
        "REPLACE": "INSERT OR REPLACE INTO experiment_layout_recordings "
        "SELECT * FROM experiment_layout_recordings",
    }
    with (
        sqlite3.connect(prepared.extraction.root.database) as connection,
        pytest.raises(sqlite3.IntegrityError, match="append_only"),
    ):
        connection.execute(statements[action])


@pytest.mark.parametrize("command", ["layout-materials", "layout-review"])
def test_stale_frozen_revision_reports_controlled_reason_to_owner(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    from paper_radar.papers import PaperFacts
    from tests.experiment_layout_support import layout_fixture
    from tests.test_experiment_candidates_cli import invoke

    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    root = prepared.extraction.root
    papers = PaperFacts(root.database, root.data_root)
    current = papers.show(prepared.extraction.prepared.paper_id)
    corrected = papers.correct(
        dict(
            version_id=current.version_id,
            request_id="stale-revision",
            actor="owner",
            reason="PRIVATE_OWNER_CORRECTION",
            fields={"title": {"value": "Corrected title", "locator": "manual/title"}},
        )
    )
    assert corrected.status == "retained"
    args = prepared.args(command)
    if command == "layout-review":
        args += ["--reviewer", "owner", "--recorder", "agent", "--request-id", "stale"]
        for name in [
            "body-boundary",
            "reading-order",
            "sections",
            "headers-footers",
            "provenance",
            "restricted-content",
        ]:
            args += ["--" + name, "true"]
    result = invoke(*args)
    assert result.exit_code == 2 and "frozen_version_changed" in result.output, (
        result.output
    )
    assert "PRIVATE_OWNER_CORRECTION" not in result.output
