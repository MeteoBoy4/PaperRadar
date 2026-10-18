"""供给公共服务; 延迟 I/O 实现使帮助无需数据库或网络模块。"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING

from paper_radar.pi_supply.cleanup_models import CleanupPlan
from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.models import (
    Activation,
    DoctorReport,
    InstallInstance,
    PrepareResult,
    SupplyRecord,
    VerificationResult,
)

if TYPE_CHECKING:
    from paper_radar.pi_supply.export import ExportResult
    from paper_radar.pi_supply.protection import InstallUse, ProtectionObservation
    from paper_radar.pi_supply.transport import Downloader, Runner

__all__ = [
    "SupplyError",
    "acquire_install",
    "activate_supply",
    "activation_history",
    "available_installs",
    "create_cleanup_plan",
    "doctor_supply",
    "exclusive_install",
    "export_supply",
    "list_cleanup_plans",
    "list_supplies",
    "prepare_supply",
    "probe_install",
    "rebuild_supply",
    "show_cleanup_plan",
    "show_supply",
    "use_install",
    "verify_supply",
]


def export_supply(database: Path, supply_id: str, target: Path) -> ExportResult:
    from paper_radar.pi_supply.export import export_supply as export

    return export(database, supply_id, target)


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


def activate_supply(
    database: Path, supply_id: str, snapshot_reference: str
) -> Activation:
    from paper_radar.pi_supply.execution import activate_supply as activate

    return activate(database, supply_id, snapshot_reference)


def activation_history(database: Path) -> tuple[Activation, ...]:
    from paper_radar.pi_supply.execution import activation_history as history

    return history(database)


def doctor_supply(database: Path, snapshot_reference: str) -> DoctorReport:
    from paper_radar.pi_supply.execution import doctor_supply as diagnose

    return diagnose(database, snapshot_reference)


def use_install(
    database: Path, snapshot_reference: str
) -> AbstractContextManager[InstallUse]:
    from paper_radar.pi_supply.protection import use_install as use

    return use(database, snapshot_reference)


def acquire_install(
    database: Path, supply_id: str, install_id: str
) -> AbstractContextManager[InstallUse]:
    from paper_radar.pi_supply.protection import acquire_install as acquire

    return acquire(database, supply_id, install_id)


def exclusive_install(
    database: Path, supply_id: str, install_id: str
) -> AbstractContextManager[InstallUse]:
    from paper_radar.pi_supply.protection import exclusive_install as exclusive

    return exclusive(database, supply_id, install_id)


def probe_install(
    database: Path, supply_id: str, install_id: str
) -> ProtectionObservation:
    from paper_radar.pi_supply.protection import probe_install as probe

    return probe(database, supply_id, install_id)


def create_cleanup_plan(
    database: Path, *, data_root: Path, config_root: Path, material_root: Path
) -> CleanupPlan:
    from paper_radar.pi_supply.cleanup import create_cleanup_plan as create

    return create(
        database,
        data_root=data_root,
        config_root=config_root,
        material_root=material_root,
    )


def show_cleanup_plan(database: Path, plan_id: str) -> CleanupPlan:
    from paper_radar.pi_supply.cleanup import show_cleanup_plan as show

    return show(database, plan_id)


def list_cleanup_plans(database: Path) -> tuple[CleanupPlan, ...]:
    from paper_radar.pi_supply.cleanup import list_cleanup_plans as discover

    return discover(database)
