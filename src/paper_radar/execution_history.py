"""执行审计的只读供给身份接缝;不取得安装、网络或进程执行能力。"""

from pathlib import Path

from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.repository import read_records


def require_supply_reference(
    database: Path,
    *,
    supply_id: str,
    install_id: str,
    pi_version: str,
    node_version: str,
) -> None:
    """完整回放冻结供给后核对历史身份;不依赖原安装树或当前选择。"""
    try:
        supply = next(
            (
                record
                for record in read_records(database)
                if record.supply_id == supply_id
            ),
            None,
        )
        if (
            supply is None
            or not any(item.install_id == install_id for item in supply.installs)
            or supply.manifest.pi_version != pi_version
            or supply.manifest.node_version != node_version
        ):
            raise ValueError("execution_reference_invalid")
    except SupplyError:
        raise ValueError("execution_reference_invalid") from None
