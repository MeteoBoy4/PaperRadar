"""value 候选通过真实任务、历史同源上下文和唯一权威接收。"""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.screening import ValuePredictionOutput
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    SuccessReceipt,
)
from tests.a7_value_support import value_payload
from tests.a8_call_support import archive, request_for
from tests.a8_rpc_support import FakeFactory
from tests.a8_rpc_task_support import run_attempt
from tests.config_projection_support import new_yaml_version
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("is_zh", [True, False])
def test_value_uses_historical_context_and_language_without_sending_language_marker(
    tmp_path: Path, is_zh: bool
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=is_zh)
    )
    frozen = tasks.load_input(receipt.receipt_id)
    new_yaml_version(
        data.settings, "topics", lambda value: value["topics"][0].update(id="new-topic")
    )
    new_yaml_version(
        data.settings,
        "models",
        lambda value: value["screening"].update(model="current-model"),
    )
    current = compile_config(data.settings, data.database)
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    raw = (
        b" \n"
        + value_payload(
            topic_ids=["alpha"], display_title_zh=None if is_zh else "天气诊断方法"
        )
        + b"\n "
    )
    factory = FakeFactory(raw=raw.decode())
    result = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert isinstance(result, SuccessReceipt)
    assert result.executor_kind == "test" and result.stage == "value"
    loaded = tasks.load_success(result.success_id)
    assert loaded.raw_response == raw
    assert isinstance(loaded.output, ValuePredictionOutput)
    assert loaded.output.research_value == 4 and loaded.output.topic_ids == ["alpha"]
    assert loaded.output.display_title_zh == (None if is_zh else "天气诊断方法")
    assert loaded.audit["input_tokens"] == 5 and loaded.audit["output_tokens"] == 2
    assert loaded.audit["provider_request_id"] is None
    assert (
        tasks.load_input(receipt.receipt_id).stage_input.payload_bytes
        == frozen.stage_input.payload_bytes
    )
    for snapshot, applicability in (
        (data.snapshot_id, "current"),
        (current.snapshot_id, "historical"),
    ):
        assert (
            tasks.query_successes(
                paper_id=data.paper_id, stage="value", snapshot_id=snapshot
            )[0].applicability
            == applicability
        )
    sent = factory.sessions[0].commands[-1]["message"]
    assert "original_title_is_zh" not in sent and "current-model" not in sent
    assert "new-topic" not in sent and "HIDDEN_TOPIC_SECRET" not in sent
    assert factory.sessions[0].description.model == "real-model"
    tasks.validate_all()


@pytest.mark.parametrize(
    "changes,is_zh,category,location",
    [
        ({"research_value": 0}, False, "business_rule", "$.research_value"),
        ({"reuse_feasibility": 6}, False, "business_rule", "$.reuse_feasibility"),
        ({"topic_ids": ["unknown"]}, False, "business_rule", "$.topic_ids[0]"),
        ({"topic_ids": ["hidden"]}, False, "business_rule", "$.topic_ids[0]"),
        ({"topic_ids": ["alpha", "alpha"]}, False, "business_rule", "$.topic_ids[1]"),
        (
            {"display_title_zh": "PRIVATE_TRANSLATED_TITLE"},
            True,
            "context_mismatch",
            "$.display_title_zh",
        ),
        ({"display_title_zh": "暂无"}, False, "invalid_text", "$.display_title_zh"),
    ],
)
def test_value_business_rules_are_owned_by_a1_a7_and_leave_no_candidate_artifact(
    tmp_path: Path,
    changes: dict[str, object],
    is_zh: bool,
    category: str,
    location: str,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=is_zh)
    )
    before = {
        str(path): path.read_bytes()
        for path in data.data_root.rglob("*")
        if path.is_file()
    }
    raw = value_payload(**changes)
    factory = FakeFactory(raw=raw.decode())
    result = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert (
        isinstance(result, FailureReceipt) and result.kind is FailureKind.OUTPUT_INVALID
    )
    assert (category, location) in [
        (issue.category.value, issue.location) for issue in result.issues
    ]
    assert tasks.status(receipt.receipt_id).remaining_attempts == 1
    assert (
        tasks.query_successes(
            paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
        )
        == ()
    )
    assert {
        str(path): path.read_bytes()
        for path in data.data_root.rglob("*")
        if path.is_file()
    } == before
    assert "PRIVATE_TRANSLATED_TITLE" not in repr(result)
    tasks.validate_all()


@pytest.mark.parametrize(
    "raw",
    [
        '{"research_value":4,"research_value":5}',
        '{"research_value":NaN}',
        '{"research_value":Infinity}',
        '{"research_value":',
        "```json\n{}\n```",
        "",
        " \n\t",
    ],
)
def test_value_inner_json_and_empty_text_are_rejected_by_authority(
    tmp_path: Path, raw: str
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    factory = FakeFactory(raw=raw)
    result = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert (
        isinstance(result, FailureReceipt) and result.kind is FailureKind.OUTPUT_INVALID
    )
    assert [(issue.category.value, issue.location) for issue in result.issues] == [
        ("invalid_json", "$")
    ]
    assert tasks.status(receipt.receipt_id).used_attempts == 1


@pytest.mark.parametrize(
    "field,observed",
    [
        ("provider", "OTHER_PROVIDER_SECRET"),
        ("model", "OTHER_MODEL_SECRET"),
        ("responseModel", "real-model-2026-10-24"),
    ],
)
def test_final_model_identity_is_owned_by_a7_and_second_attempt_keeps_model_reason(
    tmp_path: Path, field: str, observed: str
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    raw = value_payload(display_title_zh="天气诊断方法").decode()

    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"][field] = observed
            records[8]["message"]["responseId"] = "RESPONSE_ID_SECRET"
        return records

    before = {
        str(path): path.read_bytes()
        for path in data.data_root.rglob("*")
        if path.is_file()
    }
    failed_factory = FakeFactory(raw=raw, mutate=mutate)
    failed = run_attempt(
        tasks, receipt.receipt_id, failed_factory, clock=failed_factory.clock
    )
    assert (
        isinstance(failed, FailureReceipt) and failed.kind is FailureKind.MODEL_MISMATCH
    )
    assert failed.origin == "executor" and failed.issues == ()
    assert {
        str(path): path.read_bytes()
        for path in data.data_root.rglob("*")
        if path.is_file()
    } == before
    good_factory = FakeFactory(raw=raw)
    result = run_attempt(
        tasks, receipt.receipt_id, good_factory, clock=good_factory.clock
    )
    assert isinstance(result, SuccessReceipt)
    sent = json.loads(
        good_factory.sessions[0].commands[-1]["message"].split("\n", 1)[1]
    )
    assert "模型" in sent["correction"] and "协议" not in sent["correction"]
    assert observed not in sent["correction"] and "RESPONSE_ID_SECRET" not in repr(
        failed
    )
    assert tasks.load_success(result.success_id).audit["provider_request_id"] is None
    assert tasks.status(receipt.receipt_id).used_attempts == 2
    tasks.validate_all()


def test_protocol_failure_does_not_contaminate_another_paper_session(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    first = tasks.register(request_for(data))
    failed_factory = FakeFactory(
        mutate=lambda name, records: (
            [records[0], {"type": "queue_update", "steering": [], "followUp": []}]
            if name == "prompt"
            else records
        )
    )
    failed = run_attempt(
        tasks, first.receipt_id, failed_factory, clock=failed_factory.clock
    )
    assert (
        isinstance(failed, FailureReceipt) and failed.kind is FailureKind.PROTOCOL_ERROR
    )
    second = PaperFacts(data.database, data.data_root).submit(
        observation(
            doi="10.1234/rpc-independent",
            fields=screening_fields(title="Independent pressure analysis"),
        )
    )
    receipt = tasks.register(request_for(data, paper_id=second.paper_id))
    good_factory = FakeFactory()
    success = run_attempt(
        tasks, receipt.receipt_id, good_factory, clock=good_factory.clock
    )
    assert isinstance(success, SuccessReceipt)
    assert good_factory.sessions[0] is not failed_factory.sessions[0]
    assert (
        "Independent pressure analysis"
        in good_factory.sessions[0].commands[-1]["message"]
    )
    assert tasks.status(first.receipt_id).remaining_attempts == 1


def test_success_keeps_only_final_text_and_safe_audit_without_rpc_or_provider_ids(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    raw = value_payload(display_title_zh="天气诊断方法").decode()
    secrets = (
        "THINKING_SECRET",
        "SIGNATURE_SECRET",
        "RESPONSE_ID_SECRET",
        "DIAGNOSTIC_SECRET",
        "STREAM_SECRET",
    )

    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            final = records[8]["message"]
            final.update(
                responseId="RESPONSE_ID_SECRET",
                diagnostics=[{"message": "DIAGNOSTIC_SECRET"}],
                endTurn=True,
            )
            final["content"] = [
                {"type": "text", "text": raw, "textSignature": "SIGNATURE_SECRET"},
                {
                    "type": "thinking",
                    "thinking": "THINKING_SECRET",
                    "thinkingSignature": "SIGNATURE_SECRET",
                },
            ]
            for field in ("input", "output", "cacheRead", "cacheWrite", "totalTokens"):
                final["usage"][field] = 0
            records.insert(
                8,
                {
                    "type": "message_update",
                    "usage": final["usage"],
                    "assistantMessageEvent": {
                        "type": "text_delta",
                        "contentIndex": 0,
                        "delta": "STREAM_SECRET",
                    },
                },
            )
        return records

    factory = FakeFactory(raw=raw, mutate=mutate)
    result = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert isinstance(result, SuccessReceipt)
    loaded = tasks.load_success(result.success_id)
    assert loaded.raw_response == raw.encode()
    assert loaded.audit["provider_request_id"] is None
    assert (
        loaded.audit["input_tokens"] is None and loaded.audit["output_tokens"] is None
    )
    captured = capsys.readouterr()
    diagnostics = (
        repr((result, loaded, factory, factory.sessions[0]))
        + captured.out
        + captured.err
        + caplog.text
    )
    disk = data.database.read_bytes() + b"".join(
        path.read_bytes() for path in data.data_root.rglob("*") if path.is_file()
    )
    for secret in secrets:
        assert secret not in diagnostics and secret.encode() not in disk
    assert b"rpc-9" not in disk
    tasks.validate_all()


def test_rpc_categories_map_only_to_existing_executor_failure_kinds() -> None:
    from paper_radar.llm.rpc_types import RpcCategory
    from tests.a8_rpc_task_support import FAILURE_KINDS

    assert FAILURE_KINDS == {
        RpcCategory.TIMEOUT: FailureKind.TIMEOUT,
        RpcCategory.CANCELLED: FailureKind.CANCELLED,
        RpcCategory.ENVIRONMENT: FailureKind.EXECUTOR_ERROR,
        RpcCategory.PROTOCOL: FailureKind.PROTOCOL_ERROR,
    }
