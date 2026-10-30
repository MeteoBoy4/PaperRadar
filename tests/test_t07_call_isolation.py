"""T07 独立缺口证据。当前 boundary/value 公共调用边界。"""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.config import StageName, compile_config, load_config_snapshot
from paper_radar.llm import (
    CallDescriptionError,
    DescriptionReason,
    build_call,
    render_request,
)
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import FailureReceipt, ScreeningTasks
from paper_radar.stage_inputs import (
    ReuseFacts,
    ScreeningFacts,
    SelectedExcerpt,
    SourceSnapshotRef,
    build_stage_input,
)
from tests.a8_call_support import archive, prepare_call, request_for
from tests.a8_rpc_support import FakeFactory
from tests.a8_rpc_task_support import run_attempt
from tests.config_projection_support import full_inputs, new_yaml_version
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


@pytest.mark.parametrize("stage", [StageName.BOUNDARY, StageName.VALUE])
def test_stage_payload_has_closed_keys_and_only_value_has_topics(
    tmp_path: Path, stage: StageName
) -> None:
    data = archive(tmp_path)
    snapshot = load_config_snapshot(data.database, data.snapshot_id)
    bound = build_stage_input(
        snapshot,
        stage,
        ScreeningFacts(
            title="THIS_PAPER", abstract="THIS_ABSTRACT", abstract_truncated=False
        ),
    )
    payload = json.loads(
        render_request(build_call(bound, snapshot, snapshot)).split(b"\n", 1)[1]
    )
    expected = {"stage", "prompt", "profile", "contract", "paper", "correction"}
    if stage is StageName.VALUE:
        expected.add("topics")
        assert {topic["id"] for topic in payload["topics"]} == {"alpha", "zeta"}
    assert set(payload) == expected
    assert set(payload["paper"]) == {"title", "abstract", "abstract_truncated"}
    assert payload["paper"] == {
        "title": "THIS_PAPER",
        "abstract": "THIS_ABSTRACT",
        "abstract_truncated": False,
    }
    assert payload["correction"] is None
    assert "HIDDEN_TOPIC_SECRET" not in json.dumps(payload)


def test_correction_is_scoped_to_one_paper_stage_and_attempt(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    first = tasks.register(request_for(data))
    factory = FakeFactory(raw="INVALID_RESPONSE_SECRET")
    assert isinstance(
        run_attempt(tasks, first.receipt_id, factory, clock=factory.clock),
        FailureReceipt,
    )
    assert isinstance(
        run_attempt(tasks, first.receipt_id, factory, clock=factory.clock),
        FailureReceipt,
    )
    other = PaperFacts(data.database, data.data_root).submit(
        observation(
            doi="10.1234/t07-other", fields=screening_fields(title="OTHER_PAPER")
        )
    )
    second = tasks.register(request_for(data, paper_id=other.paper_id))
    run_attempt(tasks, second.receipt_id, factory, clock=factory.clock)
    value = tasks.register(request_for(data, stage="value", original_title_is_zh=False))
    run_attempt(tasks, value.receipt_id, factory, clock=factory.clock)
    payloads = [
        json.loads(session.commands[-1]["message"].split("\n", 1)[1])
        for session in factory.sessions
    ]
    assert len(factory.sessions) == 4 and len({id(s) for s in factory.sessions}) == 4
    assert all(s.closed and s.terminated for s in factory.sessions)
    assert [p["correction"] is None for p in payloads] == [True, False, True, True]
    assert [p["stage"] for p in payloads] == [
        "boundary",
        "boundary",
        "boundary",
        "value",
    ]
    assert [p["paper"]["title"] for p in payloads] == [
        "Title",
        "Title",
        "OTHER_PAPER",
        "Title",
    ]
    assert "INVALID_RESPONSE_SECRET" not in json.dumps(payloads)
    assert tasks.status(first.receipt_id).used_attempts == 2


def test_other_profile_does_not_replace_first_frozen_semantics(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    first = tasks.register(request_for(data))
    original = prepare_call(tasks, first.receipt_id)
    new_yaml_version(
        data.settings,
        "profile",
        lambda profile: profile.update(background="OTHER_PROFILE_SECRET"),
    )
    newer = compile_config(data.settings, data.database)
    other = tasks.register(request_for(data, snapshot_id=newer.snapshot_id))
    assert other.budget_id != first.budget_id
    assert (
        "OTHER_PROFILE_SECRET"
        in render_request(prepare_call(tasks, other.receipt_id)).decode()
    )
    frozen = prepare_call(tasks, first.receipt_id)
    assert frozen.semantic_snapshot_id == data.snapshot_id
    assert render_request(frozen) == render_request(original)
    assert "OTHER_PROFILE_SECRET" not in render_request(frozen).decode()


@pytest.mark.parametrize("stage", [StageName.REUSE, StageName.READ])
def test_reuse_and_read_are_invalid_context(tmp_path: Path, stage: StageName) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    if stage is StageName.REUSE:
        bound = build_stage_input(
            snapshot,
            stage,
            ReuseFacts(
                excerpts=[
                    SelectedExcerpt(
                        excerpt_id="e1",
                        kind="availability",
                        text="REUSE_SECRET",
                        source=SourceSnapshotRef(
                            content_sha256="1" * 64, locator=["data"]
                        ),
                    )
                ]
            ),
        )
    else:
        # 当前无 Read builder。只探测 stage 早期拒绝。
        bound = copy.copy(
            build_stage_input(
                snapshot,
                StageName.BOUNDARY,
                ScreeningFacts(
                    title="Title", abstract="Abstract", abstract_truncated=False
                ),
            )
        )
        object.__setattr__(bound, "stage", StageName.READ)
    with pytest.raises(CallDescriptionError) as failure:
        build_call(bound, snapshot, snapshot)
    assert failure.value.reason is DescriptionReason.INVALID_CONTEXT
    assert "REUSE_SECRET" not in str(failure.value)
