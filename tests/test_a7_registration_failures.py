"""失败原因、参数边界与敏感哨兵不进入普通输出。"""

from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.papers import PaperError, PaperFacts
from paper_radar.screening_tasks import ScreeningTasks, TaskError
from paper_radar.storage.errors import StorageError
from tests.a7_registration_support import archive, request_for
from tests.config_test_support import boundary_inputs, value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


@pytest.mark.parametrize(
    "changes",
    [
        {"stage": "read"},
        {"stage": []},
        {"source": "retry"},
        {"source": False},
        {"scheduled_day": None},
        {"scheduled_day": "20260101"},
        {"scheduled_day": "2026-02-30"},
        {"scheduled_day": "2026-01-01T00:00:00"},
        {"actor": "secret-actor"},
        {"request_id": "secret-request"},
        {"secret-extra-field": "secret-value"},
        {"stage": "boundary", "original_title_is_zh": False},
    ],
)
def test_invalid_registration_is_controlled_and_leaves_no_receipt(
    tmp_path: Path,
    changes: dict[str, object],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    with pytest.raises(TaskError) as failure:
        tasks.register(request_for(data, **changes))
    assert failure.value.reason == "invalid_request"
    captured = capsys.readouterr()
    assert (
        "secret"
        not in str(failure.value)
        + repr(failure.value)
        + captured.out
        + captured.err
        + caplog.text
    )
    assert tasks.receipts(data.paper_id) == ()
    tasks.validate_all()


@pytest.mark.parametrize("field", ["request_id", "reason", "actor"])
@pytest.mark.parametrize(
    "invalid", ["", " \t", "<b>secret</b>", "secret\ud800", "中" * 683]
)
def test_manual_audit_text_is_nonempty_plain_utf8_and_bounded(
    tmp_path: Path, field: str, invalid: str
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    raw = request_for(
        data,
        source="manual",
        scheduled_day=None,
        request_id="manual",
        reason="核对输入",
        actor="researcher",
    )
    raw[field] = invalid
    with pytest.raises(TaskError) as failure:
        tasks.register(raw)
    assert failure.value.reason == "invalid_request"
    assert "secret" not in str(failure.value) + repr(failure.value)
    assert tasks.receipts(data.paper_id) == ()


def test_exact_manual_audit_bytes_are_kept_internal(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(
        request_for(
            data,
            source="manual",
            scheduled_day=None,
            request_id="secret-id" + "x" * (2048 - len("secret-id")),
            reason="secret-reason",
            actor="secret-actor",
        )
    )
    assert "secret" not in repr(receipt)
    assert tasks.get_receipt(receipt.receipt_id) == receipt
    tasks.validate_all()


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"volume": {"value": "42", "locator": "volume"}}, "missing_title"),
        ({"title": {"value": "Title", "locator": "title"}}, "missing_abstract"),
        (screening_fields(truncated=None), "truncation_unknown"),
    ],
)
def test_mapping_failures_keep_original_paper_reason(
    tmp_path: Path, fields: dict[str, object], reason: str
) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    saved = PaperFacts(database, tmp_path / "data").submit(observation(fields=fields))
    assert saved.paper_id
    tasks = ScreeningTasks(database)
    with pytest.raises(PaperError) as failure:
        tasks.register(
            {
                "paper_id": saved.paper_id,
                "snapshot_id": snapshot.snapshot_id,
                "stage": "boundary",
                "source": "scheduled",
                "scheduled_day": "2026-01-01",
            }
        )
    assert failure.value.reason == reason
    assert tasks.receipts(saved.paper_id) == ()
    tasks.validate_all()


def test_snapshot_registration_and_stage_readiness_are_independent(
    tmp_path: Path,
) -> None:
    settings, database = boundary_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    saved = PaperFacts(database, tmp_path / "data").submit(
        observation(fields=screening_fields())
    )
    assert saved.paper_id
    tasks = ScreeningTasks(database)
    raw = {
        "paper_id": saved.paper_id,
        "snapshot_id": snapshot.snapshot_id,
        "stage": "boundary",
        "source": "scheduled",
        "scheduled_day": "2026-01-01",
    }
    with pytest.raises(PaperError) as failure:
        tasks.register({**raw, "snapshot_id": "0" * 64})
    assert failure.value.reason == "snapshot_not_found"
    with pytest.raises(PaperError) as failure:
        tasks.register({**raw, "stage": "value", "original_title_is_zh": False})
    assert failure.value.reason == "config_not_ready"
    assert tasks.register(raw).stage == "boundary"


def test_value_can_register_when_boundary_is_not_ready(tmp_path: Path) -> None:
    settings, database = value_inputs(tmp_path)
    settings.write_text(settings.read_text().replace("  boundary: v1\n", ""))
    snapshot = compile_config(settings, database)
    saved = PaperFacts(database, tmp_path / "data").submit(
        observation(fields=screening_fields())
    )
    assert saved.paper_id
    receipt = ScreeningTasks(database).register(
        {
            "paper_id": saved.paper_id,
            "snapshot_id": snapshot.snapshot_id,
            "stage": "value",
            "original_title_is_zh": True,
            "source": "scheduled",
            "scheduled_day": "2026-01-01",
        }
    )
    assert receipt.stage == "value"


def test_missing_database_is_read_only_and_precise(tmp_path: Path) -> None:
    database = tmp_path / "absent.sqlite"
    with pytest.raises(StorageError) as failure:
        ScreeningTasks(database).register(
            {
                "paper_id": "none",
                "snapshot_id": "0" * 64,
                "stage": "boundary",
                "source": "scheduled",
                "scheduled_day": "2026-01-01",
            }
        )
    assert failure.value.reason == "database_missing"
    assert not database.exists()
