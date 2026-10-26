"""少量同库事实证明真实旧schema五类非空历史升级。"""

from pathlib import Path

import pytest

from tests.a10_recovery_support import upgraded_legacy


def test_real_a704_config_pi_paper_screening_success_failure_retry_upgrade(
    tmp_path: Path,
) -> None:
    database, data_root, ids = upgraded_legacy(tmp_path / "original")
    assert database.exists() and data_root.exists() and len(ids["receipts"]) == 3


def test_mixed_wal_history_restores_with_denied_sources_and_moves_between_processes(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import json
    import os
    import shutil
    import sqlite3
    import subprocess
    import sys
    from contextlib import closing

    import httpx

    from paper_radar.backup import create_backup, verify_backup
    from paper_radar.fixture_audit.pdf_models import PdfBackendRegistration
    from paper_radar.papers import PaperFacts
    from paper_radar.screening_tasks import ScreeningTasks
    from paper_radar.storage.artifacts import ArtifactStore
    from tests.a10_recovery_support import (
        NOW,
        audit_projection,
        audit_service,
        old_projection,
    )
    from tests.audit_matrix_support import MatrixSources
    from tests.audit_sampling_support import CODE
    from tests.fixture_pdf_support import PDF_BYTES, PDF_SHA256
    from tests.paper_recovery_support import tree_hash
    from tests.test_audit_reinterpret import SyntheticV2
    from tests.test_fixture_audit_references import audit_declaration
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    class MixedSources(MatrixSources):
        phase = "sampling"

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.path == "/doiRA/10.1029/jgr.synthetic"
                and self.phase == "sampling"
            ):
                return httpx.Response(
                    429,
                    headers={"Retry-After": "120", "Set-Cookie": "SESSION-107-private"},
                    text="DENIED-107-secret",
                )
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                if self.phase == "interrupt":
                    raise KeyboardInterrupt
                if self.phase == "bad":
                    return httpx.Response(503, text="DENIED-107-secret")
            if (
                request.url.host == "rmets.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                return httpx.Response(
                    404,
                    headers={"Set-Cookie": "SESSION-107-private"},
                    text="DENIED-107-secret",
                )
            response = super().__call__(request)
            response.headers["Set-Cookie"] = "SESSION-107-private"
            return response

    original = tmp_path / "original"
    database, data_root, ids = upgraded_legacy(original)
    sources = MixedSources()
    service = audit_service(database, data_root, sources)
    declaration = original / "history.json"
    declaration.write_bytes(
        (Path(__file__).parents[1] / "fixtures/a10/historical-v1.json").read_bytes()
    )
    historical = service.register(declaration)
    record = next(
        item
        for item in historical.entries
        if item.entry.purpose == "pdf" and item.entry.journal == "jgr"
    )
    pdf_source = original / "synthetic.pdf"
    pdf_source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record.record_id,
        pdf_source,
        request_key="first",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    service.register_pdf_backend(
        PdfBackendRegistration.model_validate(
            {
                "request_key": "backend",
                "pdf_id": pdf.pdf_id,
                "pdf_sha256": PDF_SHA256,
                "backend_component": "docling",
                "backend_version": "synthetic-v1",
                "extraction_fingerprint": "a" * 64,
                "reading_sha256": "b" * 64,
                "methods_data": {
                    "state": "located",
                    "locator": "section 2",
                    "inspection_basis": "synthetic inspection",
                },
                "availability_open_research": {
                    "state": "confirmed_absent",
                    "inspection_basis": "synthetic absence inspection",
                },
            }
        )
    )
    pdf_source.write_bytes(PDF_BYTES + b"replacement\n")
    service.register_pdf(
        record.record_id,
        pdf_source,
        request_key="second",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
        replaces=pdf.pdf_id,
        replacement_reason="新字节独立保留旧期望",
    )
    partial = service.run_audit(
        contact_email="contact107@example.org", code_identity=CODE
    )
    assert (
        partial.status == "partial" and partial.sampling[1].status == "blocked_pending"
    )
    sources.phase = "interrupt"
    with pytest.raises(KeyboardInterrupt):
        service.resume_audit(
            partial.plan.plan_id,
            contact_email="contact107@example.org",
            code_identity=CODE,
        )
    assert any(
        value.settlement is None
        for value in service.show_audit(partial.plan.plan_id).executions
    )
    sources.phase = "bad"
    bad = service.resume_audit(
        partial.plan.plan_id, contact_email="contact107@example.org", code_identity=CODE
    )
    assert bad.status == "complete"
    assert any(value.reason == "outcome_unknown" for value in bad.executions)
    assert any(value.reason == "agency_unsupported" for value in bad.executions)
    assert any(value.reason == "channel_not_installed" for value in bad.executions)
    declaration.write_bytes(audit_declaration(service, bad.plan.plan_id))
    old = service.register(declaration)
    interpretation = service.reinterpret_audit(
        bad.plan.plan_id, parser=SyntheticV2(), request_key="v2"
    )
    old_summary = service.replay_audit(bad.plan.plan_id).semantic_sha256
    sources.phase = "success"
    current = service.resume_audit(
        bad.plan.plan_id, contact_email="contact107@example.org", code_identity=CODE
    )
    assert current.status == "complete" and current != bad
    updated = json.loads(audit_declaration(service, current.plan.plan_id))
    updated["declared_version"] = "v2"
    for entry, previous in zip(updated["entries"], old.entries, strict=True):
        entry.update(
            replaces=previous.record_id, replacement_reason="显式继续后的新汇总"
        )
    declaration.write_text(json.dumps(updated, ensure_ascii=False))
    service.register(declaration)
    sources.phase = "sampling"
    pending = service.run_audit(
        contact_email="contact107@example.org", code_identity=CODE
    )
    assert pending.status == "partial"
    store = ArtifactStore(database, data_root)
    source = next(
        value
        for value in current.executions
        if value.settlement and value.settlement.artifact_id
    )
    assert source.settlement and source.settlement.artifact_id
    shared = PaperFacts(database, data_root).submit(
        observation(
            doi="10.1234/shared-audit",
            payload=store.read_artifact(source.settlement.artifact_id)["payload"],
            fields=screening_fields(),
        )
    )
    assert shared.paper_id
    assert (
        PaperFacts(database, data_root)
        .trace(shared.paper_id)
        .observations[0]
        .artifact_id
        == source.settlement.artifact_id
    )
    ids["papers"].append(shared.paper_id)
    unbound = [
        store.publish_single(kind, (raw,)).artifact_id
        for kind, raw in (
            ("source_snapshot", b"unreferenced but complete audit material"),
            ("original_pdf", PDF_BYTES + b"unreferenced"),
        )
    ]
    ids.update(
        interpretation=[current.plan.plan_id, interpretation.interpretation_id],
        summary=[current.plan.plan_id, old_summary],
        unbound=unbound,
    )
    markers = (b"contact107@example.org", b"SESSION-107-private", b"DENIED-107-secret")
    with closing(sqlite3.connect(database)) as reader:
        reader.execute("PRAGMA journal_mode=WAL")
        reader.execute("PRAGMA wal_autocheckpoint=0")
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM screening_requests").fetchone()
        tasks = ScreeningTasks(database, data_root, clock=lambda: NOW)
        tasks.register(
            {
                "paper_id": ids["papers"][0],
                "snapshot_id": ids["snapshot"],
                "stage": "boundary",
                "source": "scheduled",
                "scheduled_day": "2026-01-02",
            }
        )
        assert database.with_name(database.name + "-wal").stat().st_size > 0
        expected = {
            "old": old_projection(database, data_root, ids),
            "audit": audit_projection(service),
        }
        with closing(sqlite3.connect(database)) as committed:
            before = tuple(committed.iterdump())
        batch = create_backup(database, data_root, tmp_path / "backups")
        with closing(sqlite3.connect(database)) as committed:
            assert tuple(committed.iterdump()) == before
        # 在钉住reader、WAL仍活跃时检查数据库和日志,不只检查checkpoint后的主库。
        for path in (database, database.with_name(database.name + "-wal")):
            assert all(marker not in path.read_bytes() for marker in markers), (
                "private transport marker in active SQLite/WAL"
            )
    assert verify_backup(batch.batch_dir) == batch
    for root in (original, batch.batch_dir):
        for path in root.rglob("*"):
            if path.is_file() and path != pdf_source:
                assert all(marker not in path.read_bytes() for marker in markers), (
                    "private transport marker persisted"
                )
    portable = tmp_path / "portable" / batch.batch_dir.name
    portable.parent.mkdir()
    shutil.copytree(batch.batch_dir, portable)
    original_backups = batch.batch_dir.parent
    forbidden = [
        str(original),
        str(original.rename(tmp_path / "unavailable")),
        str(original_backups),
        str(original_backups.rename(tmp_path / "old-backups")),
    ]
    target = tmp_path / "restored"
    request: dict[str, object] = {
        "root": str(target),
        "ids": ids,
        "expected": expected,
        "forbidden": forbidden,
        "markers": [marker.decode() for marker in markers],
    }
    repo = Path(__file__).parents[1]
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": os.pathsep.join((str(repo / "tests/deny_network"), str(repo))),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    batch_hash = tree_hash(portable)
    locks = tmp_path / ".paper-radar-audit-locks"
    locks_before = tree_hash(locks)
    first = subprocess.run(
        [sys.executable, "-m", "tests.a10_recovery_reader", str(portable)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        cwd=tmp_path,
        timeout=60,
    )
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout) == {
        "read_only": True,
        "v2": "available_material_reparsed",
    }
    assert tree_hash(portable) == batch_hash
    assert tree_hash(locks) == locks_before
    moved = target.rename(tmp_path / "moved")
    request["root"] = str(moved)
    request["forbidden"] = [*forbidden, str(target), str(portable)]
    env["PYTHONHASHSEED"] = "107"
    second = subprocess.run(
        [sys.executable, "-m", "tests.a10_recovery_reader"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        cwd=tmp_path,
        timeout=60,
    )
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    assert tree_hash(portable) == batch_hash
    assert tree_hash(locks) == locks_before
    assert all(marker.decode() not in caplog.text for marker in markers)
