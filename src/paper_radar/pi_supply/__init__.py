"""供给公共服务; 延迟 I/O 实现使帮助无需数据库或网络模块。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.models import PrepareResult, SupplyRecord

if TYPE_CHECKING:
    from paper_radar.pi_supply.transport import Downloader, Runner

__all__ = ["SupplyError", "list_supplies", "prepare_supply", "show_supply"]


def prepare_supply(
    database: Path,
    snapshot_reference: str,
    adapter_slot: str,
    request_path: Path,
    install_root: Path,
    *,
    data_root: Path,
    config_root: Path,
    material_root: Path,
    downloader: Downloader | None = None,
    runner: Runner | None = None,
    proxy: str | None = None,
) -> PrepareResult:
    from paper_radar.pi_supply.service import prepare_supply as prepare

    return prepare(
        database,
        snapshot_reference,
        adapter_slot,
        request_path,
        install_root,
        data_root=data_root,
        config_root=config_root,
        material_root=material_root,
        downloader=downloader,
        runner=runner,
        proxy=proxy,
    )


def list_supplies(database: Path) -> tuple[SupplyRecord, ...]:
    from paper_radar.pi_supply.service import list_supplies as discover

    return discover(database)


def show_supply(database: Path, supply_id: str) -> SupplyRecord:
    from paper_radar.pi_supply.service import show_supply as show

    return show(database, supply_id)
