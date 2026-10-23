"""公共任务登记 seam;真实论文、历史配置与 SQLite。"""

from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import RequestReceipt, ScreeningTasks
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def test_register_replays_frozen_input_after_current_facts_change(
    tmp_path: Path,
) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    papers = PaperFacts(database, tmp_path / "data")
    paper = papers.submit(observation(fields=screening_fields()))
    assert paper.paper_id
    tasks = ScreeningTasks(database)
    receipt = tasks.register(
        {
            "paper_id": paper.paper_id,
            "snapshot_id": snapshot.snapshot_id,
            "stage": "boundary",
            "source": "manual",
            "request_id": "request-1",
            "actor": "researcher",
            "reason": "建立筛选任务",
        }
    )
    assert receipt.generation == 0
    assert receipt.source == "manual"
    assert receipt.revision_no == 1
    original = tasks.load_input(receipt.receipt_id)
    assert b'"title":"Title"' in original.stage_input.payload_bytes
    papers.submit(observation(parser_version=2, fields=screening_fields("Changed")))
    settings.unlink()
    reopened = ScreeningTasks(database)
    assert reopened.load_input(receipt.receipt_id) == original
    assert reopened.get_receipt(receipt.receipt_id) == receipt
    assert (
        reopened.register(
            {
                "paper_id": paper.paper_id,
                "snapshot_id": snapshot.snapshot_id,
                "stage": "boundary",
                "source": "manual",
                "request_id": "request-1",
                "actor": "researcher",
                "reason": "建立筛选任务",
            }
        )
        == receipt
    )


def test_value_context_is_frozen_per_budget_and_boundary_forbids_language(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.screening_tasks import TaskError, TaskReason

    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    paper = PaperFacts(database, tmp_path / "data").submit(
        observation(fields=screening_fields())
    )
    assert paper.paper_id
    tasks = ScreeningTasks(database)
    request = {
        "paper_id": paper.paper_id,
        "snapshot_id": snapshot.snapshot_id,
        "stage": "value",
        "source": "scheduled",
        "scheduled_day": "2026-01-01",
    }
    for flag in (None, 0, 1, "false"):
        with pytest.raises(TaskError) as failure:
            tasks.register({**request, "original_title_is_zh": flag})
        assert failure.value.reason == TaskReason.INVALID_CONTEXT
        assert failure.value.build_reason == "invalid_context"
        assert failure.value.field == "original_title_is_zh"
    first = tasks.register({**request, "original_title_is_zh": False})
    with pytest.raises(TaskError) as failure:
        tasks.register({**request, "original_title_is_zh": True})
    assert failure.value.reason == TaskReason.CONTEXT_CONFLICT
    for flag in (None, False):
        with pytest.raises(TaskError) as failure:
            tasks.register(
                {**request, "stage": "boundary", "original_title_is_zh": flag}
            )
        assert failure.value.reason == TaskReason.INVALID_REQUEST
    assert tasks.receipts(paper.paper_id) == (first,)
    frozen = tasks.load_input(first.receipt_id)
    assert frozen.original_title_is_zh is False
    assert b"original_title_is_zh" not in frozen.stage_input.payload_bytes
    assert "original_title_is_zh" not in repr(frozen)


def test_requests_share_budget_across_dates_revisions_and_input_roundtrip(
    tmp_path: Path,
) -> None:
    from tests.a7_registration_support import archive, request_for

    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    papers = PaperFacts(data.database, data.data_root)
    first = tasks.register(request_for(data))
    assert tasks.register(request_for(data)) == first
    tomorrow = tasks.register(request_for(data, scheduled_day="2026-01-02"))
    assert tomorrow.task_id == first.task_id and tomorrow.receipt_id != first.receipt_id
    revised = papers.correct(
        {
            "version_id": data.version_id,
            "request_id": "bookkeeping",
            "actor": "researcher",
            "reason": "补全卷期",
            "fields": {"volume": {"value": "42", "locator": "volume"}},
        }
    )
    assert revised.revision_no == 2
    bibliographic = tasks.register(request_for(data))
    assert bibliographic.task_id == first.task_id
    assert (
        bibliographic.receipt_id != first.receipt_id and bibliographic.revision_no == 2
    )
    for request_id, title in (("new-title", "New title"), ("old-title", "Title")):
        assert (
            papers.correct(
                {
                    "version_id": data.version_id,
                    "request_id": request_id,
                    "actor": "researcher",
                    "reason": "核对原题名",
                    "fields": {"title": {"value": title, "locator": "title"}},
                }
            ).status
            == "retained"
        )
        current = tasks.register(request_for(data))
        if title == "New title":
            assert (
                current.task_id != first.task_id
                and current.budget_id != first.budget_id
            )
        else:
            assert (
                current.task_id == first.task_id
                and current.budget_id == first.budget_id
            )
    tasks.validate_all()
    assert len(tasks.receipts(data.paper_id)) == 5


def test_manual_and_scheduled_share_generation_but_request_ids_are_global(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.screening_tasks import TaskError
    from tests.a7_registration_support import archive, request_for

    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    manual = request_for(
        data,
        source="manual",
        scheduled_day=None,
        request_id="global-id",
        actor="researcher",
        reason="人工登记",
    )
    first = tasks.register(manual)
    scheduled = tasks.register(request_for(data))
    value = tasks.register(request_for(data, stage="value", original_title_is_zh=False))
    assert first.task_id == scheduled.task_id
    assert value.task_id != first.task_id and value.budget_id != first.budget_id
    other_paper = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/other", fields=screening_fields())
    )
    assert other_paper.paper_id
    other = tasks.register(request_for(data, paper_id=other_paper.paper_id))
    assert other.fingerprint == first.fingerprint and other.task_id != first.task_id
    with pytest.raises(TaskError) as failure:
        tasks.register({**manual, "paper_id": other_paper.paper_id})
    assert failure.value.reason == "request_conflict"
    with pytest.raises(TaskError) as failure:
        tasks.register({**manual, "reason": "另一个理由"})
    assert failure.value.reason == "request_conflict"
    tasks.validate_all()


def test_same_input_cross_version_keeps_budget_and_original_basis(
    tmp_path: Path,
) -> None:
    from tests.a7_registration_support import archive, request_for
    from tests.test_version_relations import relation

    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    first = tasks.register(request_for(data))
    assert first.version_id == data.version_id
    # 此场景需从预印本开始,下面独立档案库不复用正式版主体。
    other_root = tmp_path / "preprint"
    other_root.mkdir()
    settings, database = value_inputs(other_root)
    snapshot = compile_config(settings, database)
    papers = PaperFacts(database, other_root / "data")
    preprint = papers.submit(
        observation(doi="10.1/pre", version_kind="preprint", fields=screening_fields())
    )
    assert preprint.paper_id
    pre_tasks = ScreeningTasks(database)
    request = {
        "paper_id": preprint.paper_id,
        "snapshot_id": snapshot.snapshot_id,
        "stage": "boundary",
        "source": "scheduled",
        "scheduled_day": "2026-01-01",
    }
    before = pre_tasks.register(request)
    after_paper = papers.submit(
        observation(
            doi="10.1/journal",
            payload=b"journal",
            fields=screening_fields(),
            relations=relation("has-preprint"),
        )
    )
    assert after_paper.paper_id == preprint.paper_id
    after = pre_tasks.register(request)
    assert after.version_id != before.version_id
    assert after.fingerprint == before.fingerprint and after.task_id == before.task_id
    assert pre_tasks.get_receipt(before.receipt_id) == before
    pre_tasks.validate_all()


def test_unrelated_read_and_journal_snapshots_share_both_stage_budgets(
    tmp_path: Path,
) -> None:
    from tests.config_projection_support import full_inputs, new_yaml_version

    settings, database = full_inputs(tmp_path)
    original = compile_config(settings, database)
    paper = PaperFacts(database, tmp_path / "data").submit(
        observation(fields=screening_fields())
    )
    assert paper.paper_id
    tasks = ScreeningTasks(database)

    def register(snapshot_id: str, stage: str) -> RequestReceipt:
        return tasks.register(
            {
                "paper_id": paper.paper_id,
                "snapshot_id": snapshot_id,
                "stage": stage,
                "source": "scheduled",
                "scheduled_day": "2026-01-01",
                **({"original_title_is_zh": False} if stage == "value" else {}),
            }
        )

    originals = {
        stage: register(original.snapshot_id, stage) for stage in ("boundary", "value")
    }
    new_yaml_version(
        settings,
        "models",
        lambda value: value["reading"].update(model="read-only-change"),
    )
    read_changed = compile_config(settings, database)
    new_yaml_version(
        settings, "journals", lambda value: value["journals"][0].update(tier="low")
    )
    journal_changed = compile_config(settings, database)
    for snapshot in (read_changed, journal_changed):
        for stage, first in originals.items():
            current = register(snapshot.snapshot_id, stage)
            assert current.task_id == first.task_id
            assert current.receipt_id != first.receipt_id
    tasks.validate_all()
