"""领取的当前性仅比较请求 snapshot 下输入指纹,保留两套依据。"""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.papers import PaperError, PaperFacts
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReport,
    ScreeningTasks,
    TaskError,
    TaskReason,
)
from tests.a7_registration_support import archive, request_for
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation
from tests.test_version_relations import relation


def test_old_receipt_can_claim_new_revision_with_unchanged_fingerprint(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    PaperFacts(data.database, data.data_root).correct(
        {
            "version_id": data.version_id,
            "request_id": "volume",
            "actor": "researcher",
            "reason": "补卷期",
            "fields": {"volume": {"value": "42", "locator": "volume"}},
        }
    )
    claim = service.claim(receipt.receipt_id)
    assert claim.version_id == receipt.version_id
    assert (receipt.revision_no, claim.revision_no) == (1, 2)
    assert service.get_receipt(receipt.receipt_id) == receipt
    service.validate_all()


def test_old_receipt_can_claim_same_text_new_version(tmp_path: Path) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    papers = PaperFacts(database, tmp_path / "data")
    preprint = papers.submit(
        observation(doi="10.1/pre", version_kind="preprint", fields=screening_fields())
    )
    assert preprint.paper_id
    service = ScreeningTasks(database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    receipt = service.register(
        {
            "paper_id": preprint.paper_id,
            "snapshot_id": snapshot.snapshot_id,
            "stage": "boundary",
            "source": "scheduled",
            "scheduled_day": "2026-01-01",
        }
    )
    journal = papers.submit(
        observation(
            doi="10.1/journal",
            payload=b"journal",
            fields=screening_fields(),
            relations=relation("has-preprint"),
        )
    )
    claim = service.claim(receipt.receipt_id)
    assert claim.version_id == journal.version_id
    assert claim.version_id != receipt.version_id
    service.validate_all()


def test_changed_fingerprint_does_not_consume_and_roundtrip_does_not_refill(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 2, tzinfo=UTC)
    )
    papers = PaperFacts(data.database, data.data_root)
    receipt = service.register(request_for(data))
    first = service.claim(receipt.receipt_id)
    service.fail(first, FailureReport(FailureKind.TIMEOUT))
    papers.correct(
        {
            "version_id": data.version_id,
            "request_id": "change",
            "actor": "researcher",
            "reason": "修订",
            "fields": {"title": {"value": "Changed", "locator": "title"}},
        }
    )
    with pytest.raises(TaskError) as changed:
        service.claim(receipt.receipt_id)
    assert changed.value.reason == TaskReason.FACTS_CHANGED
    assert service.status(receipt.receipt_id).used_attempts == 1
    different = service.register(request_for(data, scheduled_day="2026-01-02"))
    assert service.claim(different.receipt_id).attempt_no == 1
    papers.correct(
        {
            "version_id": data.version_id,
            "request_id": "restore",
            "actor": "researcher",
            "reason": "核对",
            "fields": {"title": {"value": "Title", "locator": "title"}},
        }
    )
    tomorrow = service.register(request_for(data, scheduled_day="2026-01-03"))
    assert tomorrow.task_id == receipt.task_id
    second = service.claim(tomorrow.receipt_id)
    assert second.attempt_no == 2
    service.fail(second, FailureReport(FailureKind.CANCELLED))
    reopened = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 3, tzinfo=UTC)
    )
    with pytest.raises(TaskError) as exhausted:
        reopened.claim(receipt.receipt_id)
    assert exhausted.value.reason == TaskReason.BUDGET_EXHAUSTED
    assert reopened.get_receipt(receipt.receipt_id) == receipt
    reopened.validate_all()


@pytest.mark.parametrize(
    "now",
    [datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=8)))],
)
def test_invalid_clock_does_not_consume_attempt(tmp_path: Path, now: datetime) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, clock=lambda: now)
    receipt = service.register(request_for(data))
    with pytest.raises(TaskError) as invalid:
        service.claim(receipt.receipt_id)
    assert invalid.value.reason == TaskReason.INVALID_CLOCK
    valid = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert valid.status(receipt.receipt_id).used_attempts == 0


def test_missing_current_input_preserves_mapping_reason_without_consumption(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    changed = PaperFacts(data.database, data.data_root).submit(
        observation(
            parser_version=2,
            fields={"title": {"value": "Title", "locator": "title"}},
        )
    )
    assert changed.status == "retained"
    with pytest.raises(PaperError) as missing:
        service.claim(receipt.receipt_id)
    assert missing.value.reason == "missing_abstract"
    assert service.status(receipt.receipt_id).used_attempts == 0
