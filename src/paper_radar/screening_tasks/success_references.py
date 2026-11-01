"""成功来源与供给、安装、本次回执的只读一致性核对。"""

import json
from pathlib import Path

from sqlalchemy import Connection, select

from paper_radar.config import ConfigError, load_config_snapshot
from paper_radar.config.adapters import PiAdapter
from paper_radar.config.compile import MaterialKind
from paper_radar.execution_history import require_supply_reference
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.pi_rpc_audit import PiRpcExecutionAudit
from paper_radar.screening_tasks.repository import receipt_row
from paper_radar.screening_tasks.tables import attempts


def validate_execution_reference(
    database: Path,
    connection: Connection,
    *,
    task_id: str,
    attempt_no: int,
    audit: PiRpcExecutionAudit,
    reason: TaskReason,
) -> None:
    """只核对恢复库登记与本 attempt 回执 snapshot;不读取安装树或 selector。"""
    try:
        require_supply_reference(
            database,
            supply_id=audit.supply_id,
            install_id=audit.install_id,
            pi_version=audit.pi_version,
            node_version=audit.node_version,
        )
        receipt_id = connection.execute(
            select(attempts.c.receipt_id).where(
                attempts.c.task_id == task_id,
                attempts.c.attempt_no == attempt_no,
            )
        ).scalar_one()
        request = receipt_row(connection, receipt_id)
        if request is None:
            raise ValueError
        snapshot = load_config_snapshot(database, request["snapshot_id"])
        models = next(
            json.loads(material.config_json)["screening"]
            for material in snapshot.materials.values()
            if material.kind == MaterialKind.MODELS and material.name == "models"
        )
        if (
            models["provider"] != audit.credential_provider
            or models["protocol"] != audit.protocol
        ):
            raise ValueError
        selected = snapshot.adapter_selections["screening"]
        adapter = PiAdapter.model_validate_json(
            snapshot.materials[(MaterialKind.ADAPTER, "pi-rpc", selected)].config_json
        )
        if (
            adapter.pi_version != audit.pi_version
            or adapter.adapter_version != audit.adapter_version
        ):
            raise ValueError
    except (ConfigError, ValueError, KeyError, TypeError):
        raise TaskError(reason) from None
