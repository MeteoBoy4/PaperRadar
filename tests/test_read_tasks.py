"""D1 Read登记及有限预算,通过真实公共服务组合验收。"""

from pathlib import Path
from typing import Any

import pytest

from paper_radar.read_tasks import ReadAnalysis, ReadTask, ReadTasks
from tests.read_tasks_support import ready


def test_registration_is_durable_idempotent_and_claim_spends_budget(
    tmp_path: Path,
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    first = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    assert first.generation == 1 and first.remaining_attempts == 2
    again = ReadTasks(data.database, data.data_root).register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="again",
    )
    assert again.task_id == first.task_id
    handle = tasks.claim(first.task_id)
    assert handle.ordinal == 1
    assert tasks.task(first.task_id).remaining_attempts == 1


def test_invalid_pointer_then_final_degradation_uses_persisted_ordinal(
    tmp_path: Path,
) -> None:
    from tests.read_tasks_support import valid_candidate

    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    bad = valid_candidate(
        main_findings=[
            {
                "statement": "错误引用内容。",
                "evidence": [{"evidence_id": "private-bad-id"}],
            },
            {"statement": "有效内容。", "evidence": [{"evidence_id": "e000002"}]},
        ]
    )
    first = tasks.claim(task.task_id)
    failed = tasks.submit_test(first, bad)
    assert isinstance(failed, ReadTask)
    assert failed.attempts[0].failure == "output_invalid"
    assert failed.analysis_id is None
    second = tasks.claim(task.task_id)
    assert second.correction is not None
    assert second.ordinal == 2 and "unknown_evidence" in second.correction
    assert "private-bad-id" not in second.correction
    analysis = tasks.submit_test(second, bad)
    assert isinstance(analysis, ReadAnalysis)
    assert analysis.attempt_ordinal == 2 and len(analysis.discards) == 1
    assert len(analysis.output.main_findings) == 1
    assert tasks.task(task.task_id).status == "succeeded"
    repeated = tasks.submit_test(second, bad)
    assert repeated.analysis_id == analysis.analysis_id
    assert (
        tasks.evidence(analysis.analysis_id, "e000002")[0].text == "Exact source α = 2."
    )


@pytest.mark.parametrize(
    ("changes", "category"),
    [
        (
            {
                "main_findings": [
                    {"statement": "丢弃后为空。", "evidence": [{"evidence_id": "bad"}]}
                ]
            },
            "output_without_support",
        ),
        (
            {
                "research_value_reason": {
                    "statement": "评分理由不得降级。",
                    "evidence": [{"evidence_id": "bad"}],
                }
            },
            "unknown_evidence",
        ),
    ],
)
def test_final_attempt_never_accepts_empty_support_or_invalid_score_reason(
    tmp_path: Path, changes: dict[str, Any], category: str
) -> None:
    from tests.read_tasks_support import valid_candidate
    from tests.test_read_tasks_leases import registered

    _, service, task, _ = registered(tmp_path)
    service.fail(service.claim(task.task_id), "timeout")
    result = service.submit_test(
        service.claim(task.task_id), valid_candidate(**changes)
    )
    assert isinstance(result, ReadTask) and result.status == "failed"
    assert (
        result.analysis_id is None and result.attempts[-1].failure == "output_invalid"
    )
    assert category in {i.category.value for i in result.attempts[-1].issues}


def test_candidate_cannot_supply_attempt_identity_as_extra_json_field(
    tmp_path: Path,
) -> None:
    from tests.read_tasks_support import valid_candidate
    from tests.test_read_tasks_leases import registered

    _, service, task, _ = registered(tmp_path)
    result = service.submit_test(
        service.claim(task.task_id), valid_candidate(attempt_ordinal=2)
    )
    assert isinstance(result, ReadTask) and result.analysis_id is None
    assert "extra_field" in {i.category.value for i in result.attempts[-1].issues}
