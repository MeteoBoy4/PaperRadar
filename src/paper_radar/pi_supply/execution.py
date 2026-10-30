"""唯一执行选择与只读现场诊断;不运行程序,不授予业务资格。"""

import stat
from contextlib import ExitStack
from pathlib import Path
from typing import Literal

from paper_radar.config.readiness import configuration_missing
from paper_radar.pi_supply.errors import SupplyError, SupplyReason
from paper_radar.pi_supply.filesystem import (
    no_symlink_components,
)
from paper_radar.pi_supply.models import (
    Activation,
    DoctorReport,
    InstanceDiagnosis,
    RetentionProtection,
    SupplyRecord,
)
from paper_radar.pi_supply.protection import (
    acquire_install,
    check_platform,
    inspect_instance,
    probe_install,
)
from paper_radar.pi_supply.repository import commit_activation, read_state
from paper_radar.pi_supply.retention import protection_reasons
from paper_radar.pi_supply.retention import (
    retention_protection as _retention_protection,
)
from paper_radar.pi_supply.selection import (
    load_snapshot,
    match_snapshot,
    selected_pi_version,
)
from paper_radar.pi_supply.service import (
    available_installs,
    show_supply,
)


def activate_supply(
    database: Path, supply_id: str, snapshot_reference: str
) -> Activation:
    record = show_supply(database, supply_id)
    snapshot = load_snapshot(database, snapshot_reference)
    match_snapshot(snapshot, record.manifest.pi_version)
    check_platform(record.manifest)
    for instance in available_installs(database, supply_id):
        with ExitStack() as resources:
            try:
                handle = resources.enter_context(
                    acquire_install(database, supply_id, instance.install_id)
                )
            except (SupplyError, OSError):
                continue
            return commit_activation(
                database, handle.record, handle.instance, snapshot.snapshot_id
            )
    raise SupplyError("install_unavailable")


def activation_history(database: Path) -> tuple[Activation, ...]:
    return read_state(database)[1]


def retention_protection(
    records: tuple[SupplyRecord, ...], history: tuple[Activation, ...]
) -> RetentionProtection:
    """库级纯查询:当前加最近三个不同旧实例,叠加已实施scope最近通过对象。"""
    return _retention_protection(records, history)


def doctor_supply(database: Path, snapshot_reference: str) -> DoctorReport:
    records, history, current = read_state(database)
    snapshot = load_snapshot(database, snapshot_reference)
    blockers: list[SupplyReason] = []
    try:
        selected_pi_version(snapshot)
    except SupplyError as error:
        blockers.append(error.reason)
    if current is None:
        blockers.append("selection_missing")
    protection_inventory = retention_protection(records, history)
    retained = protection_inventory.retained_install_ids
    acceptance = protection_inventory.acceptance_install_ids
    observations = {
        i.install_id: probe_install(database, r.supply_id, i.install_id)
        for r in records
        for i in r.installs
    }
    protections = protection_reasons(
        records, history, {key: value.state for key, value in observations.items()}
    )
    diagnoses = []
    d5 = None
    for record in records:
        is_current_supply = (
            current is not None and current.supply_id == record.supply_id
        )
        if is_current_supply:
            d5 = record.manifest.d5
            try:
                match_snapshot(snapshot, record.manifest.pi_version)
                check_platform(record.manifest)
            except SupplyError as error:
                blockers.append(error.reason)
        for instance in record.installs:
            present = None
            reason: SupplyReason | Literal["passed"] = "passed"
            try:
                no_symlink_components(instance.path)
                try:
                    present = stat.S_ISDIR(
                        instance.path.stat(follow_symlinks=False).st_mode
                    )
                except FileNotFoundError:
                    present = False
                inspect_instance(database, record, instance)
            except SupplyError as error:
                reason = error.reason
            except OSError:
                reason = "tree_invalid"
            if (
                current is not None
                and instance.install_id == current.install_id
                and reason != "passed"
            ):
                blockers.append(reason)
            protection = protections[instance.install_id]
            observation = observations[instance.install_id]
            if (
                current is not None
                and instance.install_id == current.install_id
                and observation.state == "unknown"
            ):
                blockers.append("protection_unknown")
            diagnoses.append(
                InstanceDiagnosis(
                    record.supply_id,
                    instance.install_id,
                    reason,
                    present,
                    tuple(protection),
                    observation.state,
                    observation.reason,
                )
            )
    present_count = sum(item.present is True for item in diagnoses)
    if present_count > 4:
        blockers.append("retention_exceeded")
    return DoctorReport(
        not blockers,
        current,
        tuple(dict.fromkeys(blockers)),
        configuration_missing(snapshot),
        tuple(
            slot
            for slot in ("screening", "reuse_assessment", "reading")
            if slot not in snapshot.adapter_selections
        ),
        tuple(diagnoses),
        retained,
        acceptance,
        present_count,
        d5,
    )
