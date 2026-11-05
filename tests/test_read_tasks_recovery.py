"""D1 Read业务闭包、规则回放、异地恢复及故障。"""

import sqlite3
from pathlib import Path

import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.read_tasks import ReadAnalysis, ReadTaskError
from tests.artifact_support import fail_sql
from tests.no_extra_runtime import no_extra_python as no_extra_python
from tests.read_tasks_support import valid_candidate
from tests.test_read_tasks_leases import registered


def test_backup_revalidates_persistent_candidate_context_and_final_ordinal(
    tmp_path: Path,
) -> None:
    data, service, task, _ = registered(tmp_path / "source")
    bad = valid_candidate(
        main_findings=[
            {"statement": "错误项。", "evidence": [{"evidence_id": "bad"}]},
            {"statement": "有效项。", "evidence": [{"evidence_id": "e000002"}]},
        ]
    )
    service.submit_test(service.claim(task.task_id), bad)
    analysis = service.submit_test(service.claim(task.task_id), bad)
    assert isinstance(analysis, ReadAnalysis)
    service.validate_all()
    backup = create_backup(data.database, data.data_root, tmp_path / "backups")
    assert backup.manifest.counts.artifacts > 0
    assert service.analysis(analysis.analysis_id).discards[0]["ordinal"] == 1


@pytest.mark.parametrize(
    "damage",
    ["ordinal", "discards", "output", "evidence", "rule", "payload", "requests"],
)
def test_backup_rejects_tampered_read_business_facts(
    tmp_path: Path, damage: str
) -> None:
    data, service, task, _ = registered(tmp_path / "source")
    service.submit_test(service.claim(task.task_id), valid_candidate())
    sql = {
        "ordinal": "UPDATE read_analyses SET attempt_ordinal=2",
        "discards": "UPDATE read_analyses SET discards_json='[{}]'",
        "output": "UPDATE read_analyses SET output_json='{}'",
        "evidence": "DELETE FROM read_evidence",
        "rule": "UPDATE read_analyses SET evidence_rule_version='future'",
        "payload": "UPDATE read_budgets SET payload=x'7b7d'",
        "requests": "DELETE FROM read_registrations",
    }[damage]
    with sqlite3.connect(data.database) as connection:
        connection.execute(sql)
    with pytest.raises(BackupError) as error:
        create_backup(data.database, data.data_root, tmp_path / "backups")
    assert error.value.reason == (
        "unsupported_rule_version" if damage == "rule" else "registration_invalid"
    )


def test_failed_success_transaction_keeps_spent_attempt_without_half_analysis(
    tmp_path: Path,
) -> None:
    data, service, task, _time = registered(tmp_path)
    handle = service.claim(task.task_id)
    with (
        fail_sql("INSERT INTO read_evidence"),
        pytest.raises(ReadTaskError, match="database_failed"),
    ):
        service.submit_test(handle, valid_candidate())
    assert service.task(task.task_id).status == "running"
    assert service.analyses(data.paper_id) == ()
    assert service.task(task.task_id).remaining_attempts == 1
    analysis = service.submit_test(handle, valid_candidate())
    assert isinstance(analysis, ReadAnalysis)
    assert len(service.analyses(data.paper_id)) == 1
    assert analysis.attempt_ordinal == 1


def test_read_history_restores_in_moved_cold_process_without_extra(
    tmp_path: Path,
    no_extra_python: Path,
) -> None:
    import json
    import os
    import subprocess

    data, service, task, _time = registered(tmp_path / "source")
    service.fail(service.claim(task.task_id), "timeout")
    service.fail(service.claim(task.task_id), "executor_error")
    child = service.retry(
        task.task_id, request_id="retry", reason="controlled retry", actor="human"
    )
    analysis = service.submit_test(service.claim(child.task_id), valid_candidate())
    assert isinstance(analysis, ReadAnalysis)
    # 另一语言保持未结算租约;恢复/只读不得回收它。
    other = service.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=analysis.identity.extraction_fingerprint,
        request_id="english",
        output_language="en",
    )
    service.claim(other.task_id)
    expected = {
        "paper": data.paper_id,
        "analysis": analysis.analysis_id,
        "candidate": analysis.raw_candidate.hex(),
        "discards": list(analysis.discards),
        "history": [
            [t.generation, t.remaining_attempts, t.status]
            for t in service.history(data.paper_id)
        ],
    }
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(expected))
    backup = create_backup(data.database, data.data_root, tmp_path / "backups")
    original = tmp_path / "source"
    unavailable = tmp_path / "source-unavailable"
    original.rename(unavailable)
    result = subprocess.run(
        [
            str(no_extra_python),
            "-m",
            "tests.read_tasks_recovery_worker",
            str(backup.batch_dir),
            str(tmp_path / "restore"),
            str(tmp_path / "moved"),
            str(path),
            str(original),
            str(unavailable),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).parents[1])
            + os.pathsep
            + str(Path(__file__).parents[1] / "src"),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "read recovered without extra" in result.stdout


@pytest.mark.parametrize("policy", ["numeric_rule_version", "limitation_rule_version"])
def test_unsupported_warning_policy_preserves_record_without_claiming_equivalence(
    tmp_path: Path, policy: str
) -> None:
    data, service, task, _ = registered(tmp_path / "source")
    analysis = service.submit_test(
        service.claim(task.task_id),
        valid_candidate(
            main_findings=[
                {
                    "statement": "结果为99千米。",
                    "evidence": [{"evidence_id": "e000002"}],
                }
            ]
        ),
    )
    assert isinstance(analysis, ReadAnalysis)
    before = service.analysis(analysis.analysis_id)
    assert before.warnings
    with sqlite3.connect(data.database) as connection:
        connection.execute(
            f"UPDATE read_analyses SET {policy}='historical-unsupported'"
        )
    service.validate_all()
    create_backup(data.database, data.data_root, tmp_path / "backups")
    assert service.analysis(analysis.analysis_id).warnings == before.warnings


def test_synthetic_v1_history_replays_using_frozen_v1_acceptance(
    tmp_path: Path,
) -> None:
    from paper_radar.read_tasks.repository import records
    from paper_radar.reading import validate_read_output

    data, service, task, _ = registered(tmp_path / "source")
    analysis = service.submit_test(service.claim(task.task_id), valid_candidate())
    assert isinstance(analysis, ReadAnalysis)
    # 持久化历史fixture,不新增产品历史导入入口。
    result = validate_read_output(
        analysis.raw_candidate, service.prepare(task.task_id).context
    )
    with sqlite3.connect(data.database) as connection:
        connection.execute(
            "UPDATE read_analyses SET evidence_rule_version='read-evidence-v1',"
            "numeric_rule_version='read-numeric-v1',limitation_rule_version='none',"
            "degrade_policy='none',output_json=?,diagnostics_json=?,warnings_json=?",
            (
                result.analysis.model_dump_json(),
                records(result.diagnostics),
                records(result.warnings),
            ),
        )
    service.validate_all()
    create_backup(data.database, data.data_root, tmp_path / "backups")
    assert (
        service.analysis(analysis.analysis_id).evidence_rule_version
        == "read-evidence-v1"
    )


def test_restore_propagates_unsupported_evidence_rule_with_chinese_guidance(
    tmp_path: Path,
) -> None:
    import hashlib
    import json

    from paper_radar.backup import RestoreError, restore_backup

    data, service, task, _ = registered(tmp_path / "source")
    service.submit_test(service.claim(task.task_id), valid_candidate())
    backup = create_backup(data.database, data.data_root, tmp_path / "backups")
    database = backup.batch_dir / "database.sqlite3"
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE read_analyses SET evidence_rule_version='future-evidence'"
        )
    raw = database.read_bytes()
    database.chmod(0o400)
    manifest = backup.batch_dir / "manifest.json"
    value = json.loads(manifest.read_bytes())
    value["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest.chmod(0o600)
    manifest.write_bytes(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        + b"\n"
    )
    manifest.chmod(0o400)
    with pytest.raises(RestoreError) as caught:
        restore_backup(backup.batch_dir, tmp_path / "restore")
    assert caught.value.reason == "unsupported_rule_version"
    assert "历史Read证据规则不受支持" in str(caught.value)
    assert not (tmp_path / "restore").exists()


def test_historical_basis_survives_new_metadata_decision_pdf_and_sample(
    tmp_path: Path,
) -> None:
    import httpx

    from paper_radar.body import BodyService
    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.papers import PaperFacts
    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )
    from tests.body_support import PDF
    from tests.test_paper_service import observation

    data, service, task, _ = registered(tmp_path / "source")
    analysis = service.submit_test(service.claim(task.task_id), valid_candidate())
    assert isinstance(analysis, ReadAnalysis)
    paper = PaperFacts(data.database, data.data_root)
    paper.submit(
        observation(
            query_key="bookkeeping",
            payload=b"bookkeeping",
            fields={
                "volume": {"value": "42", "locator": "volume"},
                "pages": {"value": "1-9", "locator": "pages"},
            },
        )
    )
    metadata = JGRMetadata(
        data.database,
        data.data_root,
        http=SourceHTTPExecutor(
            transport=httpx.MockTransport(lambda _: httpx.Response(403))
        ),
    )
    assert not metadata.enrich(
        data.paper_id, request_id="new-unavailable", contact_email="contact@example.org"
    ).minimum_complete
    body = BodyService(data.database, data.data_root)
    body.decide(
        data.paper_id,
        ScreeningReasonInput(
            result=ScreeningResult.DENIED,
            source=ScreeningSource.DIRECT_MANUAL_DECISION,
            reason=DecisionReason.OUT_OF_SCOPE,
        ),
        request_id="later-deny",
        actor="human",
    )
    pdf = body.attach_pdf(data.paper_id, PDF + b"changed", request_id="new-pdf")
    body.freeze_sample(
        data.paper_id,
        feed_id=body.samples(data.paper_id)[0].feed_id,
        pdf_sha256=pdf.pdf_sha256,
        reason="new explicit sample",
        request_id="new-sample",
    )
    assert (
        service.analysis(analysis.analysis_id).raw_candidate == analysis.raw_candidate
    )
    assert (
        service.task(task.task_id).attempts[0].basis["decision_id"]
        != body.decisions(data.paper_id)[-1].fact.reference
    )
    service.validate_all()
    create_backup(data.database, data.data_root, tmp_path / "backups")


@pytest.mark.parametrize("damage", ["sample", "review", "metadata"])
def test_backup_rejects_missing_historical_qualification_basis(
    tmp_path: Path, damage: str
) -> None:
    data, service, task, _ = registered(tmp_path / "source")
    service.submit_test(service.claim(task.task_id), valid_candidate())
    with sqlite3.connect(data.database) as connection:
        if damage == "sample":
            connection.execute("DELETE FROM body_samples")
        elif damage == "review":
            connection.execute("DELETE FROM body_layout_reviews")
        else:
            connection.execute("DELETE FROM feed_metadata_routes")
            connection.execute("DELETE FROM feed_metadata_requests")
    with pytest.raises(BackupError) as caught:
        create_backup(data.database, data.data_root, tmp_path / "backups")
    assert caught.value.reason == "registration_invalid"


@pytest.mark.parametrize("consumer", ["validate", "backup"])
def test_historical_metadata_cannot_borrow_a_later_acquisition(
    tmp_path: Path, consumer: str
) -> None:
    import json

    import httpx

    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.papers import PaperError, PaperFacts

    data, service, task, _ = registered(tmp_path / "source")
    # ready 已通过真实 metadata 路线取得完整旧修订;先保存它的合法领取依据。
    earlier = PaperFacts(data.database).show(data.paper_id).revision_no
    service.fail(service.claim(task.task_id), "timeout")

    def respond(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": "10.1234/abc", "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1234/abc",
                        "title": ["Later synthetic title"],
                        "abstract": (
                            "A later complete atmospheric abstract with changed "
                            "observations and methods."
                        ),
                        "type": "journal-article",
                    }
                },
            )
        return httpx.Response(403)

    result = JGRMetadata(
        data.database,
        data.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    ).enrich(
        data.paper_id, request_id="later-metadata", contact_email="contact@example.org"
    )
    assert result.minimum_complete and result.revision_no > earlier
    handle = service.claim(task.task_id)
    # 两个真实完整修订的正常历史与新领取都可验证。
    service.validate_all()
    create_backup(data.database, data.data_root, tmp_path / "legal-backups")
    with sqlite3.connect(data.database) as connection:
        saved = json.loads(
            connection.execute(
                "SELECT metadata_json FROM read_attempts WHERE attempt_id=?",
                (handle.attempt_id,),
            ).fetchone()[0]
        )
        assert saved["revision_no"] == result.revision_no
        saved["revision_no"] = earlier
        connection.execute(
            "UPDATE read_attempts SET metadata_json=? WHERE attempt_id=?",
            (json.dumps(saved), handle.attempt_id),
        )
    if consumer == "validate":
        with pytest.raises(PaperError) as caught:
            service.validate_all()
        assert caught.value.reason == "corrupt_reference"
    else:
        with pytest.raises(BackupError) as caught_backup:
            create_backup(data.database, data.data_root, tmp_path / "bad-backups")
        assert caught_backup.value.reason == "registration_invalid"
