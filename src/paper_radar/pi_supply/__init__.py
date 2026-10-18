"""供给公共服务; 延迟 I/O 实现使帮助无需数据库或网络模块。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.models import (
    InstallInstance,
    PrepareResult,
    SupplyRecord,
    VerificationResult,
)

if TYPE_CHECKING:
    from paper_radar.pi_supply.transport import Downloader, Runner

__all__ = [
    "SupplyError",
    "available_installs",
    "list_supplies",
    "prepare_supply",
    "rebuild_supply",
    "show_supply",
    "verify_supply",
]


def rebuild_supply(
    database: Path,
    supply_id: str,
    install_root: Path,
    *,
    data_root: Path,
    config_root: Path,
    material_root: Path,
    downloader: Downloader | None = None,
    runner: Runner | None = None,
    proxy: str | None = None,
) -> PrepareResult:
    from paper_radar.pi_supply.service import rebuild_supply as rebuild

    return rebuild(
        database,
        supply_id,
        install_root,
        data_root=data_root,
        config_root=config_root,
        material_root=material_root,
        downloader=downloader,
        runner=runner,
        proxy=proxy,
    )


def verify_supply(
    database: Path, supply_id: str, *, runner: Runner | None = None
) -> tuple[VerificationResult, ...]:
    from paper_radar.pi_supply.service import verify_supply as verify

    return verify(database, supply_id, runner=runner)


def available_installs(database: Path, supply_id: str) -> tuple[InstallInstance, ...]:
    from paper_radar.pi_supply.service import available_installs as available

    return available(database, supply_id)


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
