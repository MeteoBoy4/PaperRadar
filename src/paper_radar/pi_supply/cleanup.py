"""只生成和读取计划;现场探测永远不构成删除授权。"""

from __future__ import annotations

import os
import re
import stat
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import JsonValue
from sqlalchemy import insert, select

from paper_radar.config.identity import canonical_json, sha256
from paper_radar.pi_supply import tables
from paper_radar.pi_supply.cleanup_history import (
    completed_installs,
    safety_facts,
    validate_plan_history,
)
from paper_radar.pi_supply.cleanup_models import (
    CleanupItem,
    CleanupPlan,
    ManualCleanup,
)
from paper_radar.pi_supply.errors import SupplyError, SupplyReason
from paper_radar.pi_supply.filesystem import (
    local_filesystem,
    no_symlink_components,
    safe_roots,
    tree_entries,
    tree_hash,
)
from paper_radar.pi_supply.models import SupplyRecord
from paper_radar.pi_supply.protection import check_root_marker, probe_install
from paper_radar.pi_supply.repository import database_engine, now, read_state
from paper_radar.pi_supply.retention import protection_reasons


def read_cleanup_facts(database: Path) -> dict[str, JsonValue]:
    with database_engine(database) as engine, engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")
        return safety_facts(connection)


@dataclass(frozen=True)
class Occupancy:
    allocated: int
    logical: int
    links: int
    directory: bool


def _occupancy(
    path: Path,
) -> tuple[dict[tuple[int, int], Occupancy], Counter[tuple[int, int]]]:
    nodes = [path]
    if stat.S_ISDIR(path.lstat().st_mode):
        nodes.extend(tree_entries(path))
    inodes = {}
    counts: Counter[tuple[int, int]] = Counter()
    for node in nodes:
        info = node.lstat()
        identity = (info.st_dev, info.st_ino)
        counts[identity] += 1
        inodes[identity] = Occupancy(
            info.st_blocks * 512,
            info.st_size,
            info.st_nlink,
            stat.S_ISDIR(info.st_mode),
        )
    return inodes, counts


def check_cleanup_root(
    database: Path, root: Path, root_id: str, data: Path, config: Path, material: Path
) -> None:
    safe_roots(database, root, data, config, material)
    local_filesystem(root)
    check_root_marker(database, root, root_id)


def create_cleanup_plan(
    database: Path, *, data_root: Path, config_root: Path, material_root: Path
) -> CleanupPlan:
    try:
        for actual_root in (data_root, config_root, material_root):
            str(actual_root).encode("utf-8", errors="strict")
    except UnicodeError:
        raise SupplyError("unsafe_path") from None
    before = read_cleanup_facts(database)
    records, history, _ = read_state(database)
    if read_cleanup_facts(database) != before:
        raise SupplyError("cleanup_facts_changed")
    with database_engine(database) as engine, engine.connect() as connection:
        completed = completed_installs(connection)
    observations = {
        i.install_id: probe_install(database, r.supply_id, i.install_id).state
        for r in records
        for i in r.installs
    }
    reasons = protection_reasons(records, history, observations)
    retired_rows = before[tables.retirements.name]
    assert isinstance(retired_rows, list)
    retired = {str(r["install_id"]) for r in retired_rows if isinstance(r, dict)}
    root_rows = before[tables.roots.name]
    assert isinstance(root_rows, list)
    roots = {
        str(r["root_id"]): Path(str(r["path"]))
        for r in root_rows
        if isinstance(r, dict)
    }
    safe: dict[str, bool] = {}
    root_errors: dict[str, SupplyReason] = {}
    manual = []
    for identity, root in sorted(roots.items()):
        try:
            check_cleanup_root(
                database, root, identity, data_root, config_root, material_root
            )
            safe[identity] = True
        except (SupplyError, OSError) as error:
            safe[identity] = False
            root_errors[identity] = (
                error.reason if isinstance(error, SupplyError) else "tree_invalid"
            )
            manual.append(
                ManualCleanup(
                    root_id=identity, relative_path=".", reason="root_unverifiable"
                )
            )
    items = []
    all_inodes: dict[tuple[int, int], Occupancy] = {}
    candidate_counts: Counter[tuple[int, int]] = Counter()
    candidate_inodes: set[tuple[int, int]] = set()
    unknown = False
    for record in records:
        for instance in record.installs:
            state: Literal["installed", "retired_pending"] = (
                "retired_pending" if instance.install_id in retired else "installed"
            )
            path = instance.path
            collision = False
            if state == "retired_pending" and safe[instance.root_id]:
                trash_path = path.parent.parent / ".trash" / instance.install_id
                if os.path.lexists(trash_path):
                    collision = os.path.lexists(path)
                    if collision:
                        manual.append(
                            ManualCleanup(
                                root_id=instance.root_id,
                                relative_path=f".trash/{instance.install_id}",
                                reason="unknown_trash",
                            )
                        )
                    else:
                        path = trash_path
            disposition: Literal["candidate", "protected", "unverifiable", "absent"] = (
                "unverifiable"
            )
            reason: SupplyReason | Literal["passed"] = root_errors.get(
                instance.root_id, "unsafe_root"
            )
            actual = None
            present = None
            allocated = logical = None
            protection = reasons[instance.install_id]
            if safe[instance.root_id]:
                try:
                    no_symlink_components(path)
                    if collision:
                        present = stat.S_ISDIR(path.lstat().st_mode)
                        raise SupplyError("publication_conflict")
                    if not os.path.lexists(path):
                        disposition, reason = "absent", "install_unavailable"
                        present = False
                    else:
                        present = stat.S_ISDIR(path.lstat().st_mode)
                        if instance.install_id in completed:
                            manual.append(
                                ManualCleanup(
                                    root_id=instance.root_id,
                                    relative_path=path.relative_to(
                                        roots[instance.root_id]
                                    ).as_posix(),
                                    reason="unknown_trash"
                                    if path.parent.name == ".trash"
                                    else "unknown_entry",
                                )
                            )
                            raise SupplyError("cleanup_tree_changed")
                        actual = tree_hash(path)
                        inodes, counts = _occupancy(path)
                        allocated = sum(v.allocated for v in inodes.values())
                        logical = sum(v.logical for v in inodes.values())
                        all_inodes.update(inodes)
                        disposition = "protected" if protection else "candidate"
                        reason = (
                            "tree_mismatch"
                            if actual != record.manifest.expected_tree
                            else "passed"
                        )
                        if disposition == "candidate":
                            candidate_counts.update(counts)
                            candidate_inodes.update(inodes)
                except SupplyError as error:
                    reason = error.reason
                    actual = allocated = logical = None
                except OSError:
                    reason = "tree_invalid"
                    actual = allocated = logical = None
            if disposition == "unverifiable":
                unknown = True
            items.append(
                CleanupItem(
                    supply_id=record.supply_id,
                    install_id=instance.install_id,
                    root_id=instance.root_id,
                    root_path=str(instance.root),
                    relative_path=path.relative_to(instance.root).as_posix(),
                    state=state,
                    disposition=disposition,
                    protection=protection,
                    ever_activated=any(
                        event.install_id == instance.install_id for event in history
                    ),
                    observation=observations[instance.install_id],
                    reason=reason,
                    expected_tree_hash=record.manifest.expected_tree,
                    present=present,
                    actual_tree_hash=actual,
                    allocated_bytes=allocated,
                    logical_bytes=logical,
                )
            )
    for identity, root in sorted(roots.items()):
        if safe[identity]:
            manual.extend(_manual(root, identity, records, retired))
    observed_manual = []
    for entry in manual:
        observed, inodes = _manual_occupancy(roots[entry.root_id], entry)
        observed_manual.append(observed)
        all_inodes.update(inodes)
    manual = observed_manual
    present_count = sum(item.present is True for item in items)
    owner = before[tables.database_identity.name]
    assert isinstance(owner, list) and isinstance(owner[0], dict)
    database_id = owner[0]["database_id"]
    assert isinstance(database_id, str)
    plan = CleanupPlan(
        created_at=now(),
        database_id=database_id,
        data_root=os.path.abspath(data_root),
        config_root=os.path.abspath(config_root),
        material_root=os.path.abspath(material_root),
        facts_version=sha256(canonical_json(before)),
        facts=before,
        items=tuple(items),
        manual=tuple(manual),
        present_count=present_count,
        over_limit=present_count > 4,
        allocated_bytes=sum(v.allocated for v in all_inodes.values()),
        reclaimable_bytes=sum(
            all_inodes[k].allocated
            for k in candidate_inodes
            if all_inodes[k].directory or candidate_counts[k] >= all_inodes[k].links
        ),
        occupancy_unknown=unknown
        or any(entry.allocated_bytes is None for entry in manual),
    )
    with (
        database_engine(database, write=True) as engine,
        engine.connect() as connection,
    ):
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            if safety_facts(connection) != before:
                raise SupplyError("cleanup_facts_changed")
            connection.execute(
                insert(tables.cleanup_plans).values(
                    plan_id=plan.plan_id,
                    payload=plan.canonical_bytes,
                    created_at=plan.created_at,
                )
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return plan


def _manual(
    root: Path, root_id: str, records: tuple[SupplyRecord, ...], retired: set[str]
) -> list[ManualCleanup]:
    known = {
        i.path.relative_to(root).as_posix()
        for r in records
        for i in r.installs
        if i.root == root
    }
    control_files = {".root.lock"} | {
        f".prepare-{r.manifest.material_key}.lock" for r in records
    }
    result = []
    try:
        for path in sorted(root.iterdir()):
            name = path.name
            name.encode("utf-8", errors="strict")
            if name == ".paper-radar-install-root":
                continue
            if name == ".locks" and path.is_dir() and not path.is_symlink():
                continue
            if name in control_files and stat.S_ISREG(path.lstat().st_mode):
                continue
            if name == ".trash" and path.is_dir() and not path.is_symlink():
                for entry in sorted(path.iterdir()):
                    entry.name.encode("utf-8", errors="strict")
                    if entry.name not in retired:
                        result.append(
                            ManualCleanup(
                                root_id=root_id,
                                relative_path=f".trash/{entry.name}",
                                reason="unknown_trash",
                            )
                        )
            elif (
                name in {record.supply_id for record in records}
                and path.is_dir()
                and not path.is_symlink()
            ):
                for entry in sorted(path.iterdir()):
                    entry.name.encode("utf-8", errors="strict")
                    if f"{name}/{entry.name}" not in known:
                        result.append(
                            ManualCleanup(
                                root_id=root_id,
                                relative_path=f"{name}/{entry.name}",
                                reason="unknown_entry",
                            )
                        )
            else:
                result.append(
                    ManualCleanup(
                        root_id=root_id,
                        relative_path=name,
                        reason="unknown_staging"
                        if name.startswith(".staging-")
                        else "unknown_entry",
                    )
                )
    except (OSError, UnicodeError):
        result.append(
            ManualCleanup(
                root_id=root_id, relative_path=".", reason="root_unverifiable"
            )
        )
    return result


def list_cleanup_plans(database: Path) -> tuple[CleanupPlan, ...]:
    before = read_cleanup_facts(database)
    records = read_state(database)[0]
    with database_engine(database) as engine, engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")
        rows = [
            dict(r) for r in connection.execute(select(tables.cleanup_plans)).mappings()
        ]
        facts = safety_facts(connection)
        if facts != before:
            raise SupplyError("cleanup_facts_changed")
        return validate_plan_history(rows, facts, records)


def show_cleanup_plan(database: Path, plan_id: str) -> CleanupPlan:
    if not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise SupplyError("cleanup_plan_missing")
    for plan in list_cleanup_plans(database):
        if plan.plan_id == plan_id:
            return plan
    raise SupplyError("cleanup_plan_missing")


def _manual_occupancy(
    root: Path, entry: ManualCleanup
) -> tuple[ManualCleanup, dict[tuple[int, int], Occupancy]]:
    if entry.reason == "root_unverifiable":
        return entry, {}
    path = root / entry.relative_path
    try:
        no_symlink_components(path)
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            tree_hash(path)
        elif not stat.S_ISREG(mode):
            raise SupplyError("tree_special_file")
        inodes, _ = _occupancy(path)
        return entry.model_copy(
            update={
                "allocated_bytes": sum(v.allocated for v in inodes.values()),
                "logical_bytes": sum(v.logical for v in inodes.values()),
                "occupancy_reason": "passed",
            }
        ), inodes
    except SupplyError as error:
        reason = error.reason
    except (OSError, UnicodeError):
        reason = "tree_invalid"
    return entry.model_copy(update={"occupancy_reason": reason}), {}
