"""retry 历史的持久化约束与受控只读语义校验。"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.screening_tasks import ScreeningTasks, TaskError
from tests.a7_registration_support import archive, request_for
from tests.a7_retry_support import exhaust, retry_for


def test_invalid_persisted_retry_audit_is_corruption_not_caller_error(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    initial = service.register(request_for(data))
    exhaust(service, initial)
    successor = service.retry(retry_for(data, initial))
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute(
            "UPDATE screening_requests SET reason=' ' WHERE receipt_id=?",
            (successor.receipt_id,),
        )
        connection.commit()
    with pytest.raises(TaskError) as error:
        service.validate_all()
    assert error.value.reason == "corrupt_reference"
