"""A7-04 成功和受控输出失败经只读恢复闭包重验。"""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.a7_registration_support import archive, request_for

NOW = datetime(2026, 1, 1, tzinfo=UTC)
RAW = b'{"boundary":"in_scope","reason_zh":"Atmospheric models are evaluated."}'


@pytest.mark.parametrize(
    "damage",
    [
        "structure",
        "raw_reference",
        "executor_kind",
        "double_settlement",
        "success_time",
    ],
)
def test_invalid_success_is_rejected_read_only(tmp_path: Path, damage: str) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(request_for(data))
    success = service.submit(service.claim(receipt.receipt_id), SuccessCandidate(RAW))
    assert isinstance(success, SuccessReceipt)
    replacement = ArtifactStore(data.database, data.data_root).publish_single(
        "model_success_response",
        (b'{"boundary":"uncertain","reason_zh":"Atmospheric evidence is limited."}',),
    )
    with closing(sqlite3.connect(data.database)) as connection:
        if damage == "structure":
            connection.execute("UPDATE screening_successes SET structured_json='{}'")
        elif damage == "raw_reference":
            connection.execute(
                "UPDATE screening_successes SET artifact_id=?",
                (replacement.artifact_id,),
            )
        elif damage == "executor_kind":
            audit = json.loads(
                connection.execute(
                    "SELECT audit_json FROM screening_successes"
                ).fetchone()[0]
            )
            audit["executor_kind"] = "production"
            connection.execute(
                "UPDATE screening_successes SET audit_json=?",
                (
                    json.dumps(
                        audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ),
                ),
            )
        elif damage == "double_settlement":
            connection.execute(
                "INSERT INTO screening_failures"
                "(task_id,attempt_no,kind,origin,settled_at) "
                "VALUES (?,1,'timeout','executor',?)",
                (success.task_id, NOW.isoformat(timespec="microseconds")),
            )
        else:
            connection.execute(
                "UPDATE screening_successes SET "
                "settled_at='2025-12-31T23:59:59.000000+00:00'"
            )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        before = tuple(connection.iterdump())
    with pytest.raises(TaskError) as error:
        service.validate_all()
    assert error.value.reason == TaskReason.CORRUPT_REFERENCE
    with closing(sqlite3.connect(data.database)) as connection:
        assert tuple(connection.iterdump()) == before


@pytest.mark.parametrize("damage", ["location", "guidance", "audit", "missing_issues"])
def test_output_failure_cannot_smuggle_private_text_into_safe_projection(
    tmp_path: Path, damage: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(request_for(data))
    service.submit(service.claim(receipt.receipt_id), SuccessCandidate(b"{"))
    with closing(sqlite3.connect(data.database)) as connection:
        if damage in {"location", "guidance"}:
            issues = json.loads(
                connection.execute(
                    "SELECT issues_json FROM screening_failures"
                ).fetchone()[0]
            )
            issues[0]["location" if damage == "location" else "guidance_zh"] = (
                "PRIVATE_FAILURE_OUTPUT_SENTINEL"
            )
            connection.execute(
                "UPDATE screening_failures SET issues_json=?",
                (
                    json.dumps(
                        issues,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            )
        elif damage == "audit":
            connection.execute("UPDATE screening_failures SET audit_json='{}'")
        else:
            connection.execute("UPDATE screening_failures SET issues_json=NULL")
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        before = tuple(connection.iterdump())
    with pytest.raises(TaskError) as error:
        service.validate_all()
    assert error.value.reason == TaskReason.CORRUPT_REFERENCE
    assert "PRIVATE_FAILURE_OUTPUT_SENTINEL" not in str(error.value)
    with closing(sqlite3.connect(data.database)) as connection:
        assert tuple(connection.iterdump()) == before


@pytest.mark.parametrize(
    "damage", ["success_id", "impossible_cache_hit", "failure_digest", "failure_model"]
)
def test_new_success_facts_have_safe_identity_and_possible_history(
    tmp_path: Path, damage: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = service.register(request_for(data))
    if damage.startswith("failure"):
        service.submit(
            service.claim(registered.receipt_id),
            SuccessCandidate(RAW, reported_model="wrong-model"),
        )
    else:
        success = service.submit(
            service.claim(registered.receipt_id), SuccessCandidate(RAW)
        )
        assert isinstance(success, SuccessReceipt)
    with closing(sqlite3.connect(data.database)) as connection:
        if damage == "success_id":
            connection.execute(
                "UPDATE screening_successes SET success_id='PRIVATE_SENTINEL'"
            )
        elif damage == "impossible_cache_hit":
            connection.execute(
                "UPDATE screening_requests SET cached_success_id="
                "(SELECT success_id FROM screening_successes)"
            )
        elif damage == "failure_digest":
            connection.execute(
                "UPDATE screening_failures SET submission_sha256='PRIVATE_SENTINEL'"
            )
        else:
            audit = json.loads(
                connection.execute(
                    "SELECT audit_json FROM screening_failures"
                ).fetchone()[0]
            )
            audit["reported_model"] = "real-model"
            connection.execute(
                "UPDATE screening_failures SET audit_json=?",
                (json.dumps(audit, sort_keys=True, separators=(",", ":")),),
            )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    with pytest.raises(TaskError) as error:
        service.validate_all()
    assert error.value.reason == TaskReason.CORRUPT_REFERENCE
    assert "PRIVATE_SENTINEL" not in str(error.value)


@pytest.mark.parametrize("field", ["audit_json", "settled_at"])
def test_explicit_success_load_wraps_corrupt_text_safely(
    tmp_path: Path, field: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = service.register(request_for(data))
    success = service.submit(
        service.claim(registered.receipt_id), SuccessCandidate(RAW)
    )
    assert isinstance(success, SuccessReceipt)
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute(f"UPDATE screening_successes SET {field}='PRIVATE_SENTINEL'")
        connection.commit()
    with pytest.raises(TaskError) as error:
        service.load_success(success.success_id)
    assert error.value.reason == TaskReason.CORRUPT_REFERENCE
    assert "PRIVATE_SENTINEL" not in str(error.value)


def test_candidate_repr_hides_even_invalid_audit() -> None:
    from typing import Any

    private: Any = "PRIVATE_SENTINEL"
    assert private not in repr(
        SuccessCandidate(b"PRIVATE_SENTINEL", executor_kind=private)
    )
