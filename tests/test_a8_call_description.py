"""冻结调用描述 seam:真实配置、论文事实和任务回执。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.screening_tasks import ScreeningTasks
from tests.a8_call_support import archive, prepare_call, request_for


def test_prepare_uses_frozen_semantics_and_separate_system_input(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    description = prepare_call(tasks, receipt.receipt_id)
    assert description.pi_version == "1.4.0"
    assert description.adapter_version == "transport-v1"
    assert description.provider == "provider-a"
    assert description.model == "real-model"
    assert description.thinking_level == "low"
    assert description.temperature == 0.0 and description.top_p == 1.0
    assert description.system_prompt == b"Frozen effective Pi system prompt\n"
    from paper_radar.llm import render_request

    request = render_request(description)
    assert request.startswith(b"PaperRadar bounded-rpc-v1\n{")
    assert b"Boundary prompt\\n" in request
    assert b'"title":"Title"' in request
    assert b"Frozen effective Pi system prompt" not in request
    assert b"topics" not in request
    assert tasks.status(receipt.receipt_id).used_attempts == 0
    data.settings.unlink()
    assert prepare_call(tasks, receipt.receipt_id) == description


def test_receipt_audit_upgrade_keeps_first_semantics_and_same_budget(
    tmp_path: Path,
) -> None:
    from paper_radar.config import compile_config
    from paper_radar.llm import render_request

    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    first = tasks.register(request_for(data))
    original = prepare_call(tasks, first.receipt_id)
    adapter = data.settings.parent / "adapters/pi-v1.yaml"
    newer = data.settings.parent / "adapters/pi-v2.yaml"
    newer.write_text(
        adapter.read_text()
        .replace("version: pi-v1", "version: pi-v2")
        .replace("transport-v1", "transport-v2")
    )
    data.settings.write_text(
        data.settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
    )
    snapshot = compile_config(data.settings, data.database)
    second = tasks.register(request_for(data, snapshot_id=snapshot.snapshot_id))
    upgraded = prepare_call(tasks, second.receipt_id)
    assert first.budget_id == second.budget_id
    assert upgraded.semantic_snapshot_id == data.snapshot_id
    assert upgraded.audit_snapshot_id == snapshot.snapshot_id
    assert upgraded.adapter_version == "transport-v2"
    assert upgraded.pi_version == "1.4.0"
    assert render_request(upgraded) == render_request(original)


def test_unregistered_pi_version_is_rejected_before_claim(tmp_path: Path) -> None:

    from paper_radar.screening_tasks import TaskError, TaskReason

    data = archive(tmp_path, pi_version="1.3.0")
    tasks = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    before = data.database.read_bytes()
    with pytest.raises(TaskError) as failure:
        prepare_call(tasks, receipt.receipt_id)
    assert failure.value.reason is TaskReason.INVALID_CONTEXT
    assert failure.value.field is None and failure.value.build_reason is None
    assert tasks.status(receipt.receipt_id).used_attempts == 0
    assert data.database.read_bytes() == before


def test_mutated_input_cannot_supply_facts_outside_frozen_payload(
    tmp_path: Path,
) -> None:
    import copy

    from paper_radar.llm import CallDescriptionError, DescriptionReason, build_call
    from paper_radar.stage_inputs import ScreeningFacts

    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(request_for(data))
    frozen = tasks.load_input(receipt.receipt_id)
    changed = copy.copy(frozen.stage_input)
    object.__setattr__(
        changed,
        "facts",
        ScreeningFacts(
            title="INJECTED_SECRET", abstract="OTHER", abstract_truncated=False
        ),
    )
    with pytest.raises(CallDescriptionError) as failure:
        build_call(changed, frozen.snapshot, frozen.snapshot)
    assert failure.value.reason is DescriptionReason.CORRUPT_REFERENCE
    assert "INJECTED_SECRET" not in str(failure.value)


def test_call_repr_hides_all_model_input_and_model_names(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dataclasses import FrozenInstanceError, fields

    from paper_radar.llm import render_request

    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    description = prepare_call(tasks, receipt.receipt_id)
    request = render_request(description, "上次执行超时,请在受支持的执行时限内完成。")
    assert b'"topics":[{"description":"A semantic topic","id":"alpha"' in request
    for marker in (
        "Title",
        "Abstract",
        "climate",
        "Frozen effective Pi system prompt",
        "Value prompt",
        "provider-a",
        "real-model",
        "主题一",
    ):
        assert marker not in repr(description)
    for attribute in fields(description):
        with pytest.raises(FrozenInstanceError):
            setattr(description, attribute.name, getattr(description, attribute.name))
    assert not caplog.records
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_new_receipt_pi_version_is_used_even_when_budget_snapshot_is_older(
    tmp_path: Path,
) -> None:
    from paper_radar.config import compile_config

    data = archive(tmp_path, pi_version="1.3.0")
    tasks = ScreeningTasks(data.database)
    first = tasks.register(request_for(data))
    adapter = data.settings.parent / "adapters/pi-v1.yaml"
    newer = data.settings.parent / "adapters/pi-v2.yaml"
    newer.write_text(
        adapter.read_text()
        .replace("version: pi-v1", "version: pi-v2")
        .replace("1.3.0", "1.4.0")
    )
    data.settings.write_text(
        data.settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
    )
    snapshot = compile_config(data.settings, data.database)
    second = tasks.register(request_for(data, snapshot_id=snapshot.snapshot_id))
    assert first.budget_id == second.budget_id
    description = prepare_call(tasks, second.receipt_id)
    assert description.pi_version == "1.4.0"
    assert description.semantic_snapshot_id == data.snapshot_id
    assert description.audit_snapshot_id == snapshot.snapshot_id
