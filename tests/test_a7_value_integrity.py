"""两阶段 A1 安全路径的恢复完整性仍受所属阶段约束。"""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.screening_tasks import (
    FailureReceipt,
    ScreeningTasks,
    SuccessCandidate,
    TaskError,
    TaskReason,
)
from tests.a7_registration_support import archive, request_for


@pytest.mark.parametrize(
    ("stage", "foreign_location"),
    [("boundary", "$.research_value"), ("value", "$.boundary")],
)
def test_failure_paths_from_other_stage_are_not_valid_history(
    tmp_path: Path, stage: str, foreign_location: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    request = request_for(data, stage=stage)
    if stage == "value":
        request["original_title_is_zh"] = False
    receipt = service.register(request)
    failed = service.run_once(receipt.receipt_id, lambda *_: SuccessCandidate(b"{}"))
    assert isinstance(failed, FailureReceipt)
    service.validate_all()
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute(
            "UPDATE screening_failures SET issues_json=?",
            (
                json.dumps(
                    [{"location": foreign_location, "category": "missing_field"}],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()
        before = tuple(connection.iterdump())
    with pytest.raises(TaskError) as invalid:
        service.validate_all()
    assert invalid.value.reason == TaskReason.CORRUPT_REFERENCE
    with closing(sqlite3.connect(data.database)) as connection:
        assert tuple(connection.iterdump()) == before
