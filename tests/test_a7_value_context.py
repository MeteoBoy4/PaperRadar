"""value 接收依据来自历史同源快照,查询显式配置的当前适用性。"""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.screening import ValuePredictionOutput
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from tests.a7_registration_support import request_for
from tests.a7_value_support import value_archive, value_payload
from tests.config_projection_support import full_inputs, new_yaml_version
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_claimed_value_uses_frozen_topics_after_configuration_switch_and_removal(
    tmp_path: Path,
) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    request = request_for(data, stage="value", original_title_is_zh=False)
    receipt = service.register(request)
    claim = service.claim(receipt.receipt_id)
    frozen_payload = service.load_input(receipt.receipt_id).stage_input.payload_bytes
    new_yaml_version(
        data.settings,
        "topics",
        lambda content: content["topics"][0].update(id="new-topic"),
    )
    new_yaml_version(
        data.settings,
        "models",
        lambda content: content["screening"].update(model="new-current-model"),
    )
    current = compile_config(data.settings, data.database)
    assert current.snapshot_id != data.snapshot_id
    # 原目录无法读取时,接收和回读不能借助当前文件修复或替代历史依据。
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    raw = value_payload(topic_ids=["extreme-rainfall"])
    success = service.submit(claim, SuccessCandidate(raw, reported_model="real-model"))
    assert isinstance(success, SuccessReceipt)
    content = service.load_success(success.success_id)
    assert isinstance(content.output, ValuePredictionOutput)
    assert content.output.topic_ids == ["extreme-rainfall"]
    assert (
        service.load_input(receipt.receipt_id).stage_input.payload_bytes
        == frozen_payload
    )
    assert (
        service.load_input(receipt.receipt_id).snapshot.snapshot_id == data.snapshot_id
    )
    for snapshot_id, applicability in (
        (data.snapshot_id, "current"),
        (current.snapshot_id, "historical"),
    ):
        assert (
            service.query_successes(
                paper_id=data.paper_id, stage="value", snapshot_id=snapshot_id
            )[0].applicability
            == applicability
        )
    assert service.register(request) == receipt
    fresh = service.register({**request, "snapshot_id": current.snapshot_id})
    assert fresh.cached_success_id is None and fresh.budget_id != receipt.budget_id
    service.validate_all()


def test_newly_enabled_current_topic_cannot_replace_claimed_value_context(
    tmp_path: Path,
) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    claim = service.claim(receipt.receipt_id)
    new_yaml_version(
        data.settings,
        "topics",
        lambda content: content["topics"][1].update(enabled=True),
    )
    compile_config(data.settings, data.database)
    result = service.submit(
        claim, SuccessCandidate(value_payload(topic_ids=["disabled-topic"]))
    )
    assert (
        isinstance(result, FailureReceipt) and result.kind == FailureKind.OUTPUT_INVALID
    )
    assert [(issue.category.value, issue.location) for issue in result.issues] == [
        ("business_rule", "$.topic_ids[0]")
    ]
    assert service.status(receipt.receipt_id).used_attempts == 1
    service.validate_all()


def test_read_journal_and_declared_topic_version_keep_value_success_current(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    papers = PaperFacts(database, tmp_path / "data")
    paper = papers.submit(observation(fields=screening_fields()))
    assert paper.paper_id
    service = ScreeningTasks(database, tmp_path / "data", clock=lambda: NOW)
    request = {
        "paper_id": paper.paper_id,
        "snapshot_id": snapshot.snapshot_id,
        "stage": "value",
        "original_title_is_zh": False,
        "source": "scheduled",
        "scheduled_day": "2026-01-01",
    }
    original = service.register(request)
    success = service.run_once(
        original.receipt_id,
        lambda *_: SuccessCandidate(value_payload(topic_ids=["active"])),
    )
    assert isinstance(success, SuccessReceipt)
    for category, mutate in (
        ("models", lambda value: value["reading"].update(model="unrelated-read")),
        ("journals", lambda value: value["journals"][0].update(tier="low")),
        ("topics", lambda _value: None),
    ):
        new_yaml_version(settings, category, mutate)
        changed = compile_config(settings, database)
        assert changed.snapshot_id != snapshot.snapshot_id
        view = service.query_successes(
            paper_id=paper.paper_id, stage="value", snapshot_id=changed.snapshot_id
        )[0]
        assert view.applicability == "current"
        cached = service.register({**request, "snapshot_id": changed.snapshot_id})
        assert cached.cached_success_id == success.success_id
        assert cached.budget_id == original.budget_id
        assert (
            service.load_input(cached.receipt_id).snapshot.snapshot_id
            == snapshot.snapshot_id
        )
    service.validate_all()


def test_value_language_conflict_after_success_does_not_refresh_budget(
    tmp_path: Path,
) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    request = request_for(data, stage="value", original_title_is_zh=True)
    original = service.register(request)
    success = service.run_once(
        original.receipt_id, lambda *_: SuccessCandidate(value_payload())
    )
    assert isinstance(success, SuccessReceipt)
    with pytest.raises(TaskError) as error:
        service.register(
            {**request, "scheduled_day": "2026-01-02", "original_title_is_zh": False}
        )
    assert error.value.reason == TaskReason.CONTEXT_CONFLICT
    assert service.status(original.receipt_id).used_attempts == 1
    assert service.load_input(original.receipt_id).original_title_is_zh is True
    assert (
        service.query_successes(
            paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
        )[0].receipt
        == success
    )
    service.validate_all()


def test_changed_title_and_missing_current_abstract_preserve_historical_value(
    tmp_path: Path,
) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    claim = service.claim(receipt.receipt_id)
    papers = PaperFacts(data.database, data.data_root)
    papers.correct(
        {
            "version_id": data.version_id,
            "request_id": "new-title",
            "actor": "local",
            "reason": "复核题名",
            "fields": {
                "title": {"value": "Different atmospheric research", "locator": "title"}
            },
        }
    )
    success = service.submit(
        claim, SuccessCandidate(value_payload(topic_ids=["extreme-rainfall"]))
    )
    assert isinstance(success, SuccessReceipt)
    view = service.query_successes(
        paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
    )[0]
    assert view.applicability == "historical"
    papers.submit(
        observation(
            parser_version=2,
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"title": screening_fields()["title"]},
        )
    )
    view = service.query_successes(
        paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
    )[0]
    assert (view.applicability, view.paper_reason) == (
        "undeterminable",
        "missing_abstract",
    )
    assert service.load_success(success.success_id).raw_response == value_payload(
        topic_ids=["extreme-rainfall"]
    )
    service.validate_all()
