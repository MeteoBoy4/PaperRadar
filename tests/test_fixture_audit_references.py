"""完成审计的声明只登记可回放引用,不复制审计事实。"""

import json
from pathlib import Path

import pytest

from paper_radar.fixture_audit import FixtureAudit, FixtureError
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def audit_declaration(service: FixtureAudit, plan_id: str) -> bytes:
    replay = service.replay_audit(plan_id)
    feeds = {
        state.journal: state.feed.payload_sha256
        for state in replay.view.sampling
        if state.feed is not None
    }
    return json.dumps(
        {
            "format_version": 1,
            "declaration_key": "completed-audit",
            "declared_version": "v1",
            "entries": [
                {
                    "key": "feed",
                    "purpose": "feed",
                    "journal": "jgr",
                    "basis": "acquired",
                    "source_basis": "已完成审计引用",
                    "audit_reference": {
                        "plan_id": plan_id,
                        "summary_sha256": replay.semantic_sha256,
                        "feed_sha256": feeds["jgr"],
                    },
                },
                {
                    "key": "whole-plan",
                    "purpose": "abstract_audit",
                    "journal": None,
                    "basis": "acquired",
                    "source_basis": "整计划四刊审计引用",
                    "audit_reference": {
                        "plan_id": plan_id,
                        "summary_sha256": replay.semantic_sha256,
                        "feed_snapshots": feeds,
                    },
                },
            ],
        },
        ensure_ascii=False,
    ).encode()


def test_complete_audit_register_check_show_share_replay_evidence(
    tmp_path: Path,
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    source = tmp_path / "completed.json"
    raw = audit_declaration(service, audit.plan.plan_id)
    source.write_bytes(raw)
    saved = service.register(source)
    assert len(saved.entries) == 2
    assert service.read_declaration(saved.declaration_id) == raw
    assert service.check(source).entries == saved.entries
    assert service.list() == saved.entries
    for record in saved.entries:
        assert service.show(record.record_id) == record
        assert (
            record.audit_verification
            == "frozen_v1_material_and_execution_facts_verified"
        )
        assert record.entry.audit_reference is not None
        assert (
            record.entry.audit_reference.summary_sha256
            == service.replay_audit(audit.plan.plan_id).semantic_sha256
        )
    source.unlink()
    assert service.check(source).status == "source_missing"
    service.validate_all()


def test_reference_replacement_preserves_old_plan_and_original_bytes(
    tmp_path: Path,
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    first = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    source = tmp_path / "completed.json"
    original = audit_declaration(service, first.plan.plan_id)
    source.write_bytes(original)
    old = service.register(source)
    second = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    declaration = json.loads(audit_declaration(service, second.plan.plan_id))
    declaration["declared_version"] = "v2"
    for entry, record in zip(declaration["entries"], old.entries, strict=True):
        entry.update(replaces=record.record_id, replacement_reason="追加新一轮引用")
    replacement = json.dumps(declaration, ensure_ascii=False).encode()
    source.write_bytes(replacement)
    new = service.register(source)
    assert service.list() == new.entries
    assert len(service.list(history=True)) == 4
    assert all(not service.show(record.record_id).current for record in old.entries)
    assert service.read_declaration(old.declaration_id) == original
    assert service.read_declaration(new.declaration_id) == replacement
    assert service.replay_audit(first.plan.plan_id).view == first


def test_reference_without_material_root_reports_its_limited_proof(
    tmp_path: Path,
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    source = tmp_path / "completed.json"
    source.write_bytes(audit_declaration(service, audit.plan.plan_id))
    service.register(source)
    record = FixtureAudit(service.database).list()[0]
    assert record.byte_verified
    assert record.audit_verification == "declaration_and_reference_verified"


@pytest.mark.parametrize(
    "damage",
    ["plan", "summary", "journal", "member", "snapshots", "single", "missing_evidence"],
)
def test_invalid_audit_reference_never_registers(tmp_path: Path, damage: str) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    declaration = json.loads(audit_declaration(service, audit.plan.plan_id))
    entry = declaration["entries"][0]
    if damage == "plan":
        entry["audit_reference"]["plan_id"] = "missing-plan"
    elif damage == "summary":
        entry["audit_reference"]["summary_sha256"] = "0" * 64
    elif damage == "journal":
        entry["journal"] = "dqkx"
    elif damage == "member":
        entry["doi"] = "10.1175/aies.synthetic"
    elif damage == "snapshots":
        del declaration["entries"][1]["audit_reference"]["feed_snapshots"]["dqkx"]
    elif damage == "single":
        declaration["entries"][1]["audit_reference"].pop("feed_snapshots")
        declaration["entries"][1]["audit_reference"]["feed_sha256"] = entry[
            "audit_reference"
        ]["feed_sha256"]
    else:
        entry.pop("audit_reference")
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(declaration))
    with pytest.raises(FixtureError) as caught:
        service.register(source)
    assert caught.value.reason == (
        "evidence_required" if damage == "missing_evidence" else "invalid_reference"
    )
    assert not service.list()


def test_single_frozen_feed_cannot_register_before_whole_plan_completes(
    tmp_path: Path,
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    source = tmp_path / "partial.json"
    declaration = json.loads(audit_declaration(service, plan.plan_id))
    declaration["entries"] = declaration["entries"][:1]
    source.write_text(json.dumps(declaration))
    with pytest.raises(FixtureError) as caught:
        service.register(source)
    assert caught.value.reason == "invalid_reference"
    assert caught.value.path == "entries.audit_reference.summary_sha256"


def test_registered_complete_summary_remains_replayable_after_explicit_resume(
    tmp_path: Path,
) -> None:
    import httpx

    class Recovering(MatrixSources):
        recovered = False

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
                and not self.recovered
            ):
                return httpx.Response(503)
            return super().__call__(request)

    sources = Recovering()
    service = sampling_service(tmp_path, sources)
    first = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert first.status == "complete"
    before = service.replay_audit(first.plan.plan_id)
    source = tmp_path / "completed.json"
    source.write_bytes(audit_declaration(service, first.plan.plan_id))
    saved = service.register(source)
    sources.recovered = True
    after = service.resume_audit(
        first.plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert after != first and after.status == "complete"
    assert service.list() == saved.entries
    assert (
        service.replay_audit(first.plan.plan_id, summary_sha256=before.semantic_sha256)
        == before
    )


def test_whole_plan_scope_rejects_journal_and_feed_requires_journal(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.models import parse_declaration

    for purpose, journal in (("abstract_audit", "jgr"), ("feed", None)):
        raw = json.dumps(
            {
                "format_version": 1,
                "declaration_key": "scope",
                "declared_version": "v1",
                "entries": [
                    {
                        "key": "scope",
                        "purpose": purpose,
                        "journal": journal,
                        "basis": "synthetic",
                        "source_basis": "scope boundary",
                    }
                ],
            }
        ).encode()
        with pytest.raises(FixtureError) as caught:
            parse_declaration(raw)
        assert caught.value.reason == "invalid_declaration"


def test_captured_complete_reference_survives_append_before_short_write(
    tmp_path: Path,
) -> None:
    import httpx

    from tests.config_transaction_support import before_sql

    class Recovering(MatrixSources):
        recovered = False

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
                and not self.recovered
            ):
                return httpx.Response(503)
            return super().__call__(request)

    sources = Recovering()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    expected = service.replay_audit(original.plan.plan_id)
    source = tmp_path / "captured.json"
    source.write_bytes(audit_declaration(service, original.plan.plan_id))
    armed = True

    def append_after_capture(connection: object) -> None:
        nonlocal armed
        if armed:
            armed = False
            sources.recovered = True
            service.resume_audit(
                original.plan.plan_id,
                contact_email="audit@example.org",
                code_identity=CODE,
            )

    with before_sql("BEGIN IMMEDIATE", append_after_capture):
        saved = service.register(source)
    assert not armed
    assert service.show_audit(original.plan.plan_id) != original
    assert (
        service.replay_audit(
            original.plan.plan_id, summary_sha256=expected.semantic_sha256
        )
        == expected
    )
    assert service.list() == saved.entries


def test_checkpoint_and_declaration_rollback_together_when_registration_fails(
    tmp_path: Path,
) -> None:
    from tests.artifact_support import fail_sql

    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    source = tmp_path / "atomic.json"
    source.write_bytes(audit_declaration(service, audit.plan.plan_id))
    digest = service.replay_audit(audit.plan.plan_id).semantic_sha256
    with fail_sql("INSERT INTO fixture_records"), pytest.raises(FixtureError) as caught:
        service.register(source)
    assert caught.value.reason == "corrupt_reference"
    assert service.list() == ()
    with pytest.raises(FixtureError) as missing:
        service.replay_audit(audit.plan.plan_id, summary_sha256=digest)
    assert missing.value.reason == "invalid_reference"
    assert len(service.register(source).entries) == 2


def test_missing_retained_material_cannot_be_registered_as_acquired(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore
    from paper_radar.storage.errors import StorageError

    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    source = tmp_path / "material.json"
    source.write_bytes(audit_declaration(service, audit.plan.plan_id))
    assert service.data_root
    store = ArtifactStore(service.database, service.data_root)
    blob = store.artifact_blobs(store.list_artifacts()[0].artifact_id)[1][0]
    store.verified_blob_path(blob).unlink()
    with pytest.raises(StorageError) as caught:
        service.register(source)
    assert caught.value.reason == "blob_missing"
    assert not service.list()


def test_fixture_cli_matches_reference_proofs_and_replays_selected_summary(
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    from paper_radar.cli import app

    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    source = tmp_path / "cli.json"
    source.write_bytes(audit_declaration(service, audit.plan.plan_id))
    saved = service.register(source)
    runner = CliRunner()
    common = [
        "--database",
        str(service.database),
        "--data-root",
        str(service.data_root),
        "--json",
    ]
    for args in (
        ["fixture", "register", str(source)],
        ["fixture", "check", str(source)],
        ["fixture", "show", saved.entries[0].record_id],
        ["fixture", "list"],
    ):
        result = runner.invoke(app, [*args, *common])
        assert result.exit_code == 0
        value = json.loads(result.stdout)
        records = (
            value["entries"]
            if "entries" in value
            else value
            if isinstance(value, list)
            else [value]
        )
        assert records[0] == saved.entries[0].model_dump(mode="json")
    reference = saved.entries[0].entry.audit_reference
    assert reference
    result = runner.invoke(
        app,
        [
            "audit",
            "replay",
            audit.plan.plan_id,
            "--summary-sha256",
            reference.summary_sha256,
            *common,
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["semantic_sha256"] == reference.summary_sha256


@pytest.mark.parametrize(
    "field,value",
    [
        ("parser_version", "forged-parser"),
        ("conditional_headers", {"if_none_match": "forged-etag"}),
    ],
)
def test_reference_cannot_declare_a_different_parser_or_feed_request(
    tmp_path: Path, field: str, value: object
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    declaration = json.loads(audit_declaration(service, audit.plan.plan_id))
    declaration["entries"][0][field] = value
    source = tmp_path / "wrong-request.json"
    source.write_text(json.dumps(declaration))
    with pytest.raises(FixtureError) as caught:
        service.register(source)
    assert caught.value.reason == "invalid_reference"
    assert caught.value.path == "entries.audit_reference.request"


def test_summary_preserves_unreferenced_started_execution_before_later_settlement(
    tmp_path: Path,
) -> None:
    import httpx

    from paper_radar.fixture_audit.acquisition_models import SourceRequest

    class InterruptUnselected(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/doi/10.1002/unselected":
                raise KeyboardInterrupt
            return super().__call__(request)

    service = sampling_service(tmp_path, InterruptUnselected())
    plan = service.create_audit_plan(
        contact_email="audit@example.org",
        code_identity=CODE,
        plan_key="with-unselected",
    )
    with pytest.raises(KeyboardInterrupt):
        service.acquire_source(
            plan.plan_id,
            request_key="unselected",
            request=SourceRequest(
                journal="qjrms", route="publisher", doi="10.1002/unselected"
            ),
            contact_email="audit@example.org",
        )
    audit = service.run_audit(
        contact_email="audit@example.org",
        code_identity=CODE,
        plan_key="with-unselected",
    )
    assert audit.status == "complete"
    started = next(value for value in audit.executions if value.settlement is None)
    assert all(
        row.acquisition_id != started.execution_id for row in audit.matrix_history
    )
    expected = service.replay_audit(plan.plan_id)
    source = tmp_path / "before-settlement.json"
    source.write_bytes(audit_declaration(service, plan.plan_id))
    saved = service.register(source)
    with service.audit_execution(plan.plan_id) as protection:
        service.acquisitions.close_unknown_source(
            started.execution_id, protection=protection
        )
    assert service.show_audit(plan.plan_id) != audit
    assert (
        service.replay_audit(plan.plan_id, summary_sha256=expected.semantic_sha256)
        == expected
    )
    assert service.list() == saved.entries
