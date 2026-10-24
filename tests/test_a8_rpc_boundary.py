"""通过真实任务接收 seam 证明完整 RPC 候选仍为 test 筛选制品。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from paper_radar.llm.rpc_types import RpcLimits
from paper_radar.screening import BoundaryOutput
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    SuccessReceipt,
)
from tests.a8_call_support import archive, request_for
from tests.a8_rpc_support import BOUNDARY_RAW, COMMANDS, FakeFactory
from tests.a8_rpc_task_support import run_attempt


def test_rpc_boundary_reaches_authoritative_acceptance_and_keeps_raw(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    factory = FakeFactory(fragment=7)
    result = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert isinstance(result, SuccessReceipt)
    content = tasks.load_success(result.success_id)
    assert content.raw_response == BOUNDARY_RAW.encode()
    assert isinstance(content.output, BoundaryOutput)
    assert content.output.boundary == "in_scope"
    assert result.executor_kind == "test"
    startup = factory.sessions[0].description
    assert startup.system_prompt == b"Frozen effective Pi system prompt\n"
    assert (startup.provider, startup.model, startup.thinking_level) == (
        "provider-a",
        "real-model",
        "low",
    )
    assert (startup.temperature, startup.top_p) == (0.0, 1.0)
    assert [c["type"] for c in factory.sessions[0].commands] == list(COMMANDS)
    assert factory.sessions[0].closed and not factory.sessions[0].terminated
    assert tasks.status(receipt.receipt_id).used_attempts == 1
    tasks.validate_all()


@pytest.mark.parametrize(
    ("raw", "category"),
    [
        ("```json\n{}\n```", "invalid_json"),
        (
            '{"boundary":"in_scope","reason_zh":"合理研究依据。","secret":true}',
            "extra_field",
        ),
    ],
)
def test_rpc_business_output_is_rejected_only_by_authoritative_receiver(
    tmp_path: Path,
    raw: str,
    category: str,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    factory = FakeFactory(raw=raw)
    result = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert isinstance(result, FailureReceipt)
    assert result.kind is FailureKind.OUTPUT_INVALID
    assert any(issue.category.value == category for issue in result.issues)
    assert tasks.status(receipt.receipt_id).remaining_attempts == 1
    assert (
        tasks.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        == ()
    )
    assert raw not in repr(result)


@pytest.mark.parametrize(
    ("scenario", "kind"),
    [
        ("initialization", FailureKind.EXECUTOR_ERROR),
        ("ack_only", FailureKind.TIMEOUT),
        ("model", FailureKind.MODEL_MISMATCH),
    ],
)
def test_rpc_controlled_failure_is_settled_with_correct_budget_kind(
    tmp_path: Path,
    scenario: str,
    kind: FailureKind,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))

    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "new_session" and scenario == "initialization":
            records[-1]["data"]["cancelled"] = True
        elif name == "prompt" and scenario == "ack_only":
            return records[:1]
        elif name == "prompt" and scenario == "model":
            for record in records:
                if (
                    record["type"] in {"message_end", "turn_end"}
                    and record["message"]["role"] == "assistant"
                ):
                    record["message"]["responseModel"] = "MODEL_SECRET"
                elif record["type"] == "agent_end":
                    record["messages"][-1]["responseModel"] = "MODEL_SECRET"
        return records

    factory = FakeFactory(mutate=mutate)
    result = run_attempt(
        tasks,
        receipt.receipt_id,
        factory,
        clock=factory.clock,
        limits=RpcLimits(total=0.2, initialization=0.1, close=0.05, terminate=0.05),
    )
    assert isinstance(result, FailureReceipt)
    assert result.kind is kind and result.origin == "executor"
    assert tasks.status(receipt.receipt_id).remaining_attempts == 1
    assert "MODEL_SECRET" not in repr(result)
    assert (
        tasks.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        == ()
    )


def test_rpc_failure_diagnostics_do_not_log_input_or_upstream_error(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))

    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "set_model":
            records[-1].update(success=False, error="UPSTREAM_CREDENTIAL_SECRET")
        return records

    factory = FakeFactory(mutate=mutate)
    result = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    captured = capsys.readouterr()
    diagnostics = (
        repr(result)
        + repr(factory)
        + repr(factory.sessions[0])
        + caplog.text
        + captured.out
        + captured.err
    )
    for secret in (
        "UPSTREAM_CREDENTIAL_SECRET",
        "Frozen effective Pi system prompt",
        "Boundary prompt",
        "Weather prediction",
    ):
        assert secret not in diagnostics
    assert "UPSTREAM_CREDENTIAL_SECRET" not in data.database.read_bytes().decode(
        errors="ignore"
    )
