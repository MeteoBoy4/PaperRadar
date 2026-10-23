"""冻结输入的唯一历史快照回放链;登记、消费与完整性共用。"""

from pathlib import Path
from typing import Any

from sqlalchemy import Connection, select

from paper_radar.config import load_config_snapshot
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.models import FrozenInput
from paper_radar.screening_tasks.tables import inputs
from paper_radar.stage_inputs import replay_stage_input


def load_frozen(
    database: Path, connection: Connection, budget: dict[str, Any]
) -> FrozenInput:
    row = (
        connection.execute(
            select(inputs).where(inputs.c.fingerprint == budget["fingerprint"])
        )
        .mappings()
        .one()
    )
    snapshot = load_config_snapshot(database, budget["snapshot_id"])
    restored = replay_stage_input(
        row["payload"], budget["fingerprint"], snapshot=snapshot
    )
    if (
        restored.stage.value != budget["stage"]
        or row["stage"] != budget["stage"]
        or row["format_version"] != 1
    ):
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    language = budget["original_title_is_zh"]
    if budget["stage"] == "value":
        restored.value_prediction_context(snapshot, original_title_is_zh=language)
    elif language is not None:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    return FrozenInput(budget["fingerprint"], restored, snapshot, language)
