"""唯一执行选择与只读现场诊断;不运行程序,不授予业务资格。"""

import stat
from datetime import datetime
from pathlib import Path
from typing import Literal

from paper_radar.pi_supply.errors import SupplyError, SupplyReason
from paper_radar.pi_supply.filesystem import (
    local_filesystem,
    no_symlink_components,
    tree_hash,
)
from paper_radar.pi_supply.models import (
    Activation,
    DoctorReport,
    InstallInstance,
    InstanceDiagnosis,
    RetentionProtection,
    SupplyRecord,
)
from paper_radar.pi_supply.repository import commit_activation, read_state
from paper_radar.pi_supply.selection import (
    load_snapshot,
    match_snapshot,
    selected_pi_version,
)
from paper_radar.pi_supply.service import (
    _check_root_marker,
    _platform,
    available_installs,
    show_supply,
)


def inspect_instance(
    database: Path, record: SupplyRecord, instance: InstallInstance
) -> None:
    """静态核验边界;后续实例共享锁应覆盖它与激活提交,不在SQL事务里等锁。"""
    if not instance.path.is_dir():
        raise SupplyError("install_unavailable")
    local_filesystem(instance.path.parent.parent)
    _check_root_marker(database, instance.path.parent.parent, instance.root_id)
    no_symlink_components(instance.path)
    if tree_hash(instance.path) != record.manifest.expected_tree:
        raise SupplyError("tree_mismatch")
    for entry in (record.manifest.node_entry, record.manifest.pi_entry):
        target = instance.path / entry
        if not target.is_file() or not target.resolve().is_relative_to(instance.path):
            raise SupplyError("entry_invalid")


def activate_supply(
    database: Path, supply_id: str, snapshot_reference: str
) -> Activation:
    record = show_supply(database, supply_id)
    snapshot = load_snapshot(database, snapshot_reference)
    match_snapshot(snapshot, record.manifest.pi_version)
    _platform(record.manifest)
    for instance in available_installs(database, supply_id):
        try:
            inspect_instance(database, record, instance)
        except (SupplyError, OSError):
            continue
        return commit_activation(database, record, instance, snapshot.snapshot_id)
    raise SupplyError("install_unavailable")


def activation_history(database: Path) -> tuple[Activation, ...]:
    return read_state(database)[1]


def retention_protection(
    records: tuple[SupplyRecord, ...], history: tuple[Activation, ...]
) -> RetentionProtection:
    """库级纯查询:当前加最近三个不同旧实例,叠加已实施scope最近通过对象。"""
    retained = tuple(dict.fromkeys(item.install_id for item in reversed(history)))[:4]
    # 每个已实施scope最近一次通过的实例。RPC无事实,不虚造保护。
    checks = [
        (datetime.fromisoformat(check.created_at), check.check_id, instance.install_id)
        for record in records
        for instance in record.installs
        for check in instance.checks
        if check.passed
    ]
    acceptance = (max(checks)[2],) if checks else ()
    return RetentionProtection(retained, acceptance)


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
                _platform(record.manifest)
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
            protection = []
            if instance.install_id in retained:
                protection.append(
                    "current"
                    if current is not None and instance.install_id == current.install_id
                    else "recent_activation"
                )
            if instance.install_id in acceptance:
                protection.append("latest_install_check")
            diagnoses.append(
                InstanceDiagnosis(
                    record.supply_id,
                    instance.install_id,
                    reason,
                    present,
                    tuple(protection),
                )
            )
    present_count = sum(item.present is True for item in diagnoses)
    if present_count > 4:
        blockers.append("retention_exceeded")
    missing = {
        reason.value for stage in snapshot.stages.values() for reason in stage.missing
    }
    if snapshot.profile_status.value != "configured":
        missing.add("profile")
    missing.update(
        "model:" + slot
        for slot, state in snapshot.model_slots.items()
        if state.value != "configured"
    )
    return DoctorReport(
        not blockers,
        current,
        tuple(dict.fromkeys(blockers)),
        tuple(sorted(missing)),
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
