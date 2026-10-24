"""描述拒绝使用封闭原因;不改变 A7 预算或领域词汇。"""

from dataclasses import replace
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.llm import CallDescriptionError, DescriptionReason, build_call
from paper_radar.screening_tasks import ScreeningTasks, TaskError, TaskReason
from tests.a8_call_support import archive, prepare_call, request_for


def test_projection_difference_is_not_new_semantics_for_old_input(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(request_for(data))
    frozen = tasks.load_input(receipt.receipt_id)
    original = data.settings.parent / "profiles/profile-v1.yaml"
    changed = data.settings.parent / "profiles/profile-v2.yaml"
    changed.write_text(
        original.read_text()
        .replace("version: profile-v1", "version: profile-v2")
        .replace("core_questions: rain", "core_questions: OTHER_PROFILE_SECRET")
    )
    data.settings.write_text(
        data.settings.read_text().replace("profile: profile-v1", "profile: profile-v2")
    )
    snapshot = compile_config(data.settings, data.database)
    with pytest.raises(CallDescriptionError) as failure:
        build_call(frozen.stage_input, frozen.snapshot, snapshot)
    assert failure.value.reason is DescriptionReason.PROJECTION_MISMATCH
    assert "OTHER_PROFILE_SECRET" not in repr(failure.value)


def test_missing_adapter_and_json_schema_archive_cannot_build_rpc_call(
    tmp_path: Path,
) -> None:
    from paper_radar.config import StageName
    from paper_radar.stage_inputs import ScreeningFacts, build_stage_input
    from tests.config_test_support import value_inputs

    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    stage_input = build_stage_input(
        snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(title="Title", abstract="Abstract", abstract_truncated=False),
    )
    with pytest.raises(CallDescriptionError) as failure:
        build_call(stage_input, snapshot, snapshot)
    assert failure.value.reason is DescriptionReason.INVALID_CONTEXT


def test_corrupt_material_is_rejected_without_original_error(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(request_for(data))
    frozen = tasks.load_input(receipt.receipt_id)
    corrupted = replace(frozen.snapshot, payload_json="BROKEN_MATERIAL_SECRET")
    with pytest.raises(CallDescriptionError) as failure:
        build_call(frozen.stage_input, corrupted, frozen.snapshot)
    assert failure.value.reason is DescriptionReason.CORRUPT_REFERENCE
    assert "BROKEN_MATERIAL_SECRET" not in str(failure.value)
    assert failure.value.__cause__ is None and failure.value.__suppress_context__


def test_unknown_receipt_reuses_existing_reason(tmp_path: Path) -> None:
    data = archive(tmp_path)
    with pytest.raises(TaskError) as failure:
        prepare_call(ScreeningTasks(data.database), "0" * 64)
    assert failure.value.reason is TaskReason.REQUEST_NOT_FOUND


def test_request_limit_is_checked_before_attempt_or_external_session(
    tmp_path: Path,
) -> None:
    from paper_radar.config import StageName, load_config_snapshot
    from paper_radar.llm import MAX_REQUEST_BYTES
    from paper_radar.stage_inputs import ScreeningFacts, build_stage_input

    data = archive(tmp_path)
    snapshot = load_config_snapshot(data.database, data.snapshot_id)
    stage_input = build_stage_input(
        snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(
            title="Title", abstract="x" * MAX_REQUEST_BYTES, abstract_truncated=False
        ),
    )
    with pytest.raises(CallDescriptionError) as failure:
        build_call(stage_input, snapshot, snapshot)
    assert failure.value.reason is DescriptionReason.INVALID_CONTEXT


def test_placeholder_adapter_is_a_description_context_refusal(tmp_path: Path) -> None:
    import hashlib

    from paper_radar.config import load_config_snapshot
    from tests.config_adapter_support import SYSTEM_PROMPT_SHA256, adapter_inputs

    data = archive(tmp_path / "complete")
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(request_for(data))
    frozen = tasks.load_input(receipt.receipt_id)
    settings, adapter, database = adapter_inputs(tmp_path / "placeholder")
    (settings.parent / "prompts/pi-system-v1.md").write_bytes(b"...\n")
    adapter.write_text(
        adapter.read_text()
        .replace(SYSTEM_PROMPT_SHA256, hashlib.sha256(b"...\n").hexdigest())
        .replace("1.1.0", "1.4.0")
    )
    snapshot = compile_config(settings, database)
    historical = load_config_snapshot(database, snapshot.snapshot_id)
    assert historical.adapter_slots["screening"] == "placeholder"
    with pytest.raises(CallDescriptionError) as failure:
        build_call(frozen.stage_input, historical, historical)
    assert failure.value.reason is DescriptionReason.INVALID_CONTEXT


def test_unsupported_stage_is_rejected_by_public_description_service(
    tmp_path: Path,
) -> None:
    import copy

    from paper_radar.config import StageName

    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(request_for(data))
    frozen = tasks.load_input(receipt.receipt_id)
    unsupported = copy.copy(frozen.stage_input)
    object.__setattr__(unsupported, "stage", StageName.EXTRACTION)
    with pytest.raises(CallDescriptionError) as failure:
        build_call(unsupported, frozen.snapshot, frozen.snapshot)
    assert failure.value.reason is DescriptionReason.INVALID_CONTEXT


def test_wrong_protocol_with_present_adapter_is_independently_refused(
    tmp_path: Path,
) -> None:
    import json

    from paper_radar.config import StageName, load_config_snapshot
    from paper_radar.stage_inputs import ScreeningFacts, build_stage_input

    data = archive(tmp_path)
    snapshot = load_config_snapshot(data.database, data.snapshot_id)
    # 故意损坏快照夹具以单独命中描述防护。真实 compile 会更早拒绝此组合。
    envelope = json.loads(snapshot.payload_json)
    for material in envelope["materials"]:
        if material["kind"] == "models":
            material["config"]["screening"]["protocol"] = "json_schema"
    corrupted = replace(snapshot, payload_json=json.dumps(envelope))
    stage_input = build_stage_input(
        corrupted,
        StageName.BOUNDARY,
        ScreeningFacts(title="Title", abstract="Abstract", abstract_truncated=False),
    )
    assert corrupted.adapter_slots["screening"] == "configured"
    with pytest.raises(CallDescriptionError) as failure:
        build_call(stage_input, corrupted, corrupted)
    assert failure.value.reason is DescriptionReason.INVALID_CONTEXT
