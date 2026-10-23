"""适用性只由当前论文事实与显式snapshot派生。"""

from datetime import UTC, datetime
from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    SuccessView,
)
from tests.a7_registration_support import archive, request_for
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)
RAW = b'{"boundary":"in_scope","reason_zh":"Atmospheric models are studied."}'


def test_parser_removal_and_other_source_restore_reactivate_original_success(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    papers = PaperFacts(data.database, data.data_root)
    receipt = service.register(request_for(data))
    success = service.submit(service.claim(receipt.receipt_id), SuccessCandidate(RAW))
    assert isinstance(success, SuccessReceipt)

    def view() -> SuccessView:
        return service.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )[0]

    assert view().applicability == "current"
    removed = papers.submit(
        observation(
            parser_version=2,
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"title": screening_fields()["title"]},
        )
    )
    assert removed.status == "retained"
    assert (view().applicability, view().paper_reason) == (
        "undeterminable",
        "missing_abstract",
    )
    assert service.load_success(success.success_id).raw_response == RAW
    restored = papers.submit(
        observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1234/abc",
            target_paper_id=data.paper_id,
            target_version_id=data.version_id,
            payload=b"replacement",
            observed_at=datetime(2026, 1, 3, tzinfo=UTC),
            fields=screening_fields(),
        )
    )
    assert restored.status == "retained"
    assert (view().applicability, view().paper_reason) == ("current", None)
    assert service.get_receipt(receipt.receipt_id) == receipt
    service.validate_all()


def test_changed_text_is_historical_unknown_snapshot_is_undeterminable(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = service.register(request_for(data))
    claim = service.claim(registered.receipt_id)
    # 已领取输入可以在当前论文变化后成功;提交不把新的论文修订当成冻结依据。
    assert (
        PaperFacts(data.database, data.data_root)
        .correct(
            {
                "version_id": data.version_id,
                "request_id": "title-change",
                "actor": "local",
                "reason": "correction",
                "fields": {
                    "title": {
                        "value": "Different atmospheric research",
                        "locator": "title",
                    }
                },
            }
        )
        .status
        == "retained"
    )
    success = service.submit(claim, SuccessCandidate(RAW))
    assert isinstance(success, SuccessReceipt)
    view = service.query_successes(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )[0]
    assert (view.applicability, view.paper_reason) == ("historical", None)
    unknown = service.query_successes(
        paper_id=data.paper_id, stage="boundary", snapshot_id="0" * 64
    )[0]
    assert (unknown.applicability, unknown.paper_reason) == (
        "undeterminable",
        "snapshot_not_found",
    )
    service.validate_all()


def test_same_text_new_version_and_unrelated_config_keep_success_current(
    tmp_path: Path,
) -> None:
    from tests.config_projection_support import full_inputs, new_yaml_version
    from tests.test_version_relations import relation

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    papers = PaperFacts(database, tmp_path / "data")
    preprint = papers.submit(
        observation(
            doi="10.1/pre",
            payload=b"preprint",
            version_kind="preprint",
            fields=screening_fields(),
        )
    )
    assert preprint.paper_id
    service = ScreeningTasks(database, tmp_path / "data", clock=lambda: NOW)
    request = {
        "paper_id": preprint.paper_id,
        "snapshot_id": snapshot.snapshot_id,
        "stage": "boundary",
        "source": "manual",
        "request_id": "old",
        "actor": "local",
        "reason": "check",
    }
    before = service.register(request)
    success = service.submit(service.claim(before.receipt_id), SuccessCandidate(RAW))
    assert isinstance(success, SuccessReceipt)
    journal = papers.submit(
        observation(
            doi="10.1/journal",
            payload=b"journal",
            fields=screening_fields(),
            relations=relation("has-preprint"),
        )
    )
    assert journal.paper_id == preprint.paper_id
    new_yaml_version(
        settings,
        "models",
        lambda value: value["reading"].update(model="unrelated-read"),
    )
    reading = compile_config(settings, database)
    new_yaml_version(
        settings, "journals", lambda value: value["journals"][0].update(tier="low")
    )
    journals = compile_config(settings, database)
    for current in (snapshot, reading, journals):
        views = service.query_successes(
            paper_id=preprint.paper_id,
            stage="boundary",
            snapshot_id=current.snapshot_id,
        )
        assert views[0].applicability == "current"
        hit = service.register(
            {
                **request,
                "request_id": current.snapshot_id,
                "snapshot_id": current.snapshot_id,
            }
        )
        assert (
            hit.version_id != before.version_id
            and hit.cached_success_id == success.success_id
        )
    assert service.register(request) == before
    service.validate_all()


def test_mapping_readiness_and_unknown_truncation_keep_precise_paper_reason(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(request_for(data))
    success = service.submit(service.claim(receipt.receipt_id), SuccessCandidate(RAW))
    assert isinstance(success, SuccessReceipt)
    data.settings.write_text(data.settings.read_text().replace("  boundary: v1\n", ""))
    not_ready = compile_config(data.settings, data.database)
    view = service.query_successes(
        paper_id=data.paper_id, stage="boundary", snapshot_id=not_ready.snapshot_id
    )[0]
    assert (view.applicability, view.paper_reason) == (
        "undeterminable",
        "config_not_ready",
    )
    assert (
        PaperFacts(data.database, data.data_root)
        .correct(
            {
                "version_id": data.version_id,
                "request_id": "unknown-truncation",
                "actor": "local",
                "reason": "复核摘要边界",
                "fields": {"abstract": screening_fields(truncated=None)["abstract"]},
            }
        )
        .status
        == "retained"
    )
    unknown = service.query_successes(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )[0]
    assert (unknown.applicability, unknown.paper_reason) == (
        "undeterminable",
        "truncation_unknown",
    )
    assert service.load_success(success.success_id).raw_response == RAW
    assert service.status(receipt.receipt_id).used_attempts == 1
    service.validate_all()
