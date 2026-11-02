"""合成 pi_rpc 来源经公共任务接收与回查;不构成真实执行证明。"""

from pathlib import Path
from typing import Any

import pytest

from paper_radar.screening import ValuePredictionOutput
from paper_radar.screening_tasks import ScreeningTasks, SuccessReceipt
from tests.a8_call_support import request_for
from tests.pi_rpc_source_support import NOW, RAW, candidate, source_archive


def test_pi_rpc_boundary_survives_task_service_restart(tmp_path: Path) -> None:
    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    success = tasks.run_once(receipt.receipt_id, lambda *_: candidate(data, supplied))
    assert isinstance(success, SuccessReceipt)
    assert success.executor_kind == "pi_rpc"
    restarted = ScreeningTasks(data.database, data.data_root)
    content = restarted.load_success(success.success_id)
    assert content.raw_response == RAW
    assert content.audit["supply_id"] == supplied.supply_id
    assert content.audit["format_version"] == 3
    assert content.audit["input_tokens"] == 42
    assert (
        restarted.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )[0].receipt
        == success
    )
    restarted.validate_all()


@pytest.mark.parametrize(
    "field,value",
    [
        ("launch_policy_version", "pi-launch-v2"),
        ("isolation_policy_version", "landlock-v2"),
        ("node_version", "22.20.0"),
        ("adapter_version", "transport-v2"),
        ("install_id", "0" * 32),
    ],
)
def test_pi_rpc_value_is_idempotent_and_changed_execution_audit_conflicts(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    from dataclasses import replace

    import pytest

    from paper_radar.screening_tasks import TaskError, TaskReason
    from tests.a7_value_support import value_payload

    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    claim = tasks.claim(receipt.receipt_id)
    proposed = candidate(data, supplied, value_payload(display_title_zh="大气过程"))
    success = tasks.submit(claim, proposed)
    assert isinstance(success, SuccessReceipt)
    assert tasks.submit(claim, proposed) == success
    assert proposed.execution_audit is not None
    changed = replace(
        proposed,
        execution_audit=proposed.execution_audit.model_copy(update={field: value}),
    )
    with pytest.raises(TaskError) as error:
        tasks.submit(claim, changed)
    assert error.value.reason == TaskReason.SETTLEMENT_CONFLICT
    output = tasks.load_success(success.success_id).output
    assert isinstance(output, ValuePredictionOutput)
    assert output.research_value == 4
    assert (
        len(
            tasks.query_successes(
                paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
            )
        )
        == 1
    )
    tasks.validate_all()


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("reported_provider", "other", "model_mismatch"),
        ("reported_model", "other", "model_mismatch"),
        ("raw_response", b'{"boundary":"unsupported"}', "output_invalid"),
        ("reported_provider", None, "protocol_error"),
        ("reported_model", "", "protocol_error"),
        ("reported_provider", "", "protocol_error"),
        ("reported_model", None, "protocol_error"),
        ("executor_kind", "production", "protocol_error"),
        ("executor_kind", "unknown", "protocol_error"),
        ("executor_kind", [], "protocol_error"),
        ("execution_audit", None, "protocol_error"),
        ("provider_request_id", "rpc-request-123", "protocol_error"),
    ],
)
def test_pi_rpc_authority_rejects_bad_candidates_without_success_raw(
    tmp_path: Path,
    field: str,
    value: Any,
    expected: str,
) -> None:
    from dataclasses import replace

    from paper_radar.screening_tasks import FailureReceipt
    from paper_radar.storage.artifacts import ArtifactStore

    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    proposed = replace(candidate(data, supplied), **{field: value})
    result = tasks.run_once(receipt.receipt_id, lambda *_: proposed)
    assert isinstance(result, FailureReceipt)
    assert result.kind.value == expected
    assert tasks.status(receipt.receipt_id).used_attempts == 1
    assert (
        tasks.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        == ()
    )
    assert not [
        item
        for item in ArtifactStore(data.database, data.data_root).list_artifacts()
        if item.kind == "model_success_response"
    ]
    tasks.validate_all()


@pytest.mark.parametrize(
    "field,value",
    [
        ("supply_id", "0" * 64),
        ("install_id", "0" * 32),
        ("node_version", "22.20.0"),
        ("adapter_version", "transport-v2"),
    ],
)
def test_pi_rpc_forged_execution_reference_never_publishes_success(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    from dataclasses import replace

    from paper_radar.screening_tasks import TaskError, TaskReason
    from paper_radar.storage.artifacts import ArtifactStore

    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    proposed = candidate(data, supplied)
    assert proposed.execution_audit is not None
    proposed = replace(
        proposed,
        execution_audit=proposed.execution_audit.model_copy(update={field: value}),
    )
    with pytest.raises(TaskError) as error:
        tasks.submit(tasks.claim(receipt.receipt_id), proposed)
    assert error.value.reason == TaskReason.INVALID_CANDIDATE
    assert not [
        item
        for item in ArtifactStore(data.database, data.data_root).list_artifacts()
        if item.kind == "model_success_response"
    ]


def test_pi_rpc_audit_binds_attempt_receipt_not_budget_first_snapshot(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from paper_radar.config import compile_config
    from paper_radar.screening_tasks import FailureKind, FailureReport

    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    first = tasks.register(request_for(data))
    tasks.run_once(first.receipt_id, lambda *_: FailureReport(FailureKind.TIMEOUT))
    adapter = data.settings.parent / "adapters/pi-rpc-source-v1.yaml"
    newer = adapter.with_name("pi-rpc-source-v2.yaml")
    newer.write_text(
        adapter.read_text()
        .replace("version: pi-rpc-source-v1", "version: pi-rpc-source-v2")
        .replace("transport-v1", "transport-v2")
    )
    data.settings.write_text(
        data.settings.read_text().replace(
            "screening: pi-rpc-source-v1", "screening: pi-rpc-source-v2"
        )
    )
    snapshot = compile_config(data.settings, data.database)
    later = tasks.register(request_for(data, snapshot_id=snapshot.snapshot_id))
    assert later.budget_id == first.budget_id
    assert tasks.load_input(later.receipt_id).snapshot.snapshot_id == data.snapshot_id
    proposed = candidate(data, supplied)
    assert proposed.execution_audit is not None
    proposed = replace(
        proposed,
        execution_audit=proposed.execution_audit.model_copy(
            update={"adapter_version": "transport-v2"}
        ),
    )
    success = tasks.run_once(later.receipt_id, lambda *_: proposed)
    assert isinstance(success, SuccessReceipt)
    assert success.attempt_no == 2
    restarted = ScreeningTasks(data.database, data.data_root)
    assert (
        restarted.load_success(success.success_id).audit["adapter_version"]
        == "transport-v2"
    )
    restarted.validate_all()
