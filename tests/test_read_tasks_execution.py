"""D1外部执行类型、独立串行资源与安全日志。"""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from paper_radar.read_tasks import (
    ReadAnalysis,
    ReadHandle,
    ReadTask,
    ReadTaskError,
    ReadTasks,
)
from paper_radar.read_tasks.pi_rpc import PiReadCandidate
from paper_radar.runtime_logging import Sink
from paper_radar.screening_tasks import PiRpcExecutionAudit
from tests.a8_call_support import Archive
from tests.read_tasks_support import ready, valid_candidate


def pi_candidate(service: ReadTasks, raw: bytes) -> PiReadCandidate:
    from paper_radar.pi_supply import available_installs, list_supplies

    supply = list_supplies(service.database)[0]
    install = available_installs(service.database, supply.supply_id)[0]
    return PiReadCandidate(
        raw,
        PiRpcExecutionAudit(
            supply_id=supply.supply_id,
            install_id=install.install_id,
            pi_version="1.4.0",
            node_version="22.19.0",
            adapter_version="transport-v1",
            protocol_profile="pi-rpc-1.4.0-v1",
            launch_policy_version="pi-launch-v1",
            isolation_policy_version="landlock-v1",
            channel="prompt_only",
            auth_mode="chatgpt_subscription",
            credential_provider="openai",
            credential_source="owner_provisioned_dir",
            proxy_used=False,
            proxy_port=None,
        ),
        reported_provider="openai",
        reported_model="real-model",
        input_tokens=42,
        output_tokens=7,
    )


def setup(root: Path, sink: Sink | None = None) -> tuple[Archive, ReadTasks, ReadTask]:
    data, _, extraction = ready(root)
    service = ReadTasks(data.database, data.data_root, sink=sink)
    task = service.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    return data, service, task


def test_test_port_cannot_claim_production_kind_or_pi_audit(tmp_path: Path) -> None:
    _, service, task = setup(tmp_path)
    candidate: Any = pi_candidate(service, valid_candidate())
    handle = service.claim(task.task_id)
    with pytest.raises(ReadTaskError, match="invalid_request"):
        service.submit_test(handle, candidate)
    assert service.task(task.task_id).status == "running"
    result = service.submit_test(handle, valid_candidate())
    assert isinstance(result, ReadAnalysis)
    assert result.executor_kind == "test"


def test_dedicated_pi_port_binds_historical_supply_and_observed_model(
    tmp_path: Path,
) -> None:
    _, service, task = setup(tmp_path)
    result = service.run_pi_once(
        task.task_id, lambda _: pi_candidate(service, valid_candidate())
    )
    assert isinstance(result, ReadAnalysis)
    assert result.executor_kind == "pi_rpc" and result.attempt_ordinal == 1
    service.validate_all()
    with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
        service.analysis(result.analysis_id, ordinary=True)


def test_pi_observed_model_mismatch_is_failure_without_analysis(tmp_path: Path) -> None:
    _, service, task = setup(tmp_path)
    result = service.run_pi_once(
        task.task_id,
        lambda _: replace(
            pi_candidate(service, valid_candidate()), reported_model="other"
        ),
    )
    assert isinstance(result, ReadTask)
    assert (
        result.attempts[-1].failure == "model_mismatch" and result.analysis_id is None
    )


def test_null_sink_creates_no_log_and_captured_events_never_include_business_text(
    tmp_path: Path,
) -> None:
    class Capture:
        def __init__(self) -> None:
            self.events: list[dict[str, object]] = []

        def emit(self, event: Mapping[str, object]) -> None:
            self.events.append(dict(event))

    sink = Capture()
    data, service, task = setup(tmp_path, sink)
    assert sink.events == []
    service.run_once(
        task.task_id, lambda _: valid_candidate(next_action="PRIVATE RESPONSE SENTINEL")
    )
    assert [e["event"] for e in sink.events] == ["claimed", "succeeded"]
    assert all(e["component"] == "read" and e["stage"] == "read" for e in sink.events)
    import json

    rendered = json.dumps(sink.events)
    assert all(
        secret not in rendered
        for secret in (
            "PRIVATE RESPONSE SENTINEL",
            "Exact source",
            "Read synthetic prompt",
            "chatgpt_subscription",
            "real-model",
        )
    )
    assert not tuple(data.data_root.rglob("*.jsonl"))


def test_executor_interrupt_keeps_spent_unsettled_lease(tmp_path: Path) -> None:
    _, service, task = setup(tmp_path)

    def interrupt(_: ReadHandle) -> bytes:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        service.run_once(task.task_id, interrupt)
    assert service.task(task.task_id).status == "running"
    assert service.task(task.task_id).remaining_attempts == 1
