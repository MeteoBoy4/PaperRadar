"""安装清理历史的数据库安全视图和纯语义回放;不依赖现场或应用服务。"""

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from pydantic import JsonValue, ValidationError
from sqlalchemy import Connection, select

from paper_radar.config.identity import canonical_json, sha256
from paper_radar.pi_supply import tables
from paper_radar.pi_supply.cleanup_models import CleanupPlan, ProtectionReason
from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.models import Activation, SupplyRecord
from paper_radar.pi_supply.retention import protection_reasons

SAFETY_TABLES = (
    tables.database_identity,
    tables.roots,
    tables.supplies,
    tables.installs,
    tables.checks,
    tables.activations,
    tables.current_selection,
    tables.retirements,
)


def safety_facts(connection: Connection) -> dict[str, JsonValue]:
    """完整规范安全视图,不含计划自身;不能以 MAX(id) 代替。"""
    result: dict[str, JsonValue] = {}
    for table in SAFETY_TABLES:
        rows: list[JsonValue] = []
        for row in connection.execute(select(table)).mappings():
            values: dict[str, JsonValue] = {}
            for key, value in row.items():
                # 材料内容由既有回放验证;清单以摘要参与安全版本。
                values[str(key)] = sha256(value) if isinstance(value, bytes) else value
            rows.append(values)
        result[table.name] = sorted(rows, key=canonical_json)
    return result


def validate_plan_history(
    rows: list[dict[str, object]],
    facts: dict[str, JsonValue],
    records: tuple[SupplyRecord, ...],
) -> tuple[CleanupPlan, ...]:
    """仅回放数据库事实和历史字节;备份恢复不依赖安装现场。"""
    plans = []
    identities = {i.install_id: (r, i) for r in records for i in r.installs}
    try:
        for row in rows:
            raw = row["payload"]
            if not isinstance(raw, bytes):
                raise ValueError
            plan = CleanupPlan.model_validate_json(raw)
            if (
                plan.canonical_bytes != raw
                or plan.plan_id != row["plan_id"]
                or plan.created_at != row["created_at"]
            ):
                raise ValueError
            if datetime.fromisoformat(plan.created_at).tzinfo is None:
                raise ValueError
            if set(plan.facts) != set(facts):
                raise ValueError
            for name, values in plan.facts.items():
                current = facts[name]
                if not isinstance(values, list) or not isinstance(current, list):
                    raise ValueError
                if name == tables.current_selection.name:
                    continue  # singleton 会合法前移;事件保持不可变。
                if any(
                    canonical_json(value) not in {canonical_json(v) for v in current}
                    for value in values
                ):
                    raise ValueError
            if plan.facts[tables.database_identity.name] != [
                {"singleton": 1, "database_id": plan.database_id}
            ]:
                raise ValueError
            installed_facts = plan.facts[tables.installs.name]
            if not isinstance(installed_facts, list) or {
                i.install_id for i in plan.items
            } != {v["install_id"] for v in installed_facts if isinstance(v, dict)}:
                raise ValueError
            historical_reasons = _historical_reasons(plan, records)
            _validate_layout(plan)
            for item in plan.items:
                record, instance = identities[item.install_id]
                relative = (
                    f".trash/{item.install_id}"
                    if item.relative_path.startswith(".trash/")
                    else f"{record.supply_id}/{instance.install_id}"
                )
                if (
                    item.supply_id != record.supply_id
                    or item.root_id != instance.root_id
                    or item.root_path != str(instance.path.parent.parent)
                    or item.relative_path != relative
                    or item.expected_tree_hash != record.manifest.expected_tree
                ):
                    raise ValueError
                if item.protection != historical_reasons[item.install_id]:
                    raise ValueError
                if item.disposition == "candidate" and (
                    item.protection
                    or item.actual_tree_hash is None
                    or item.observation != "idle"
                ):
                    raise ValueError
            plans.append(plan)
        plan_map = {p.plan_id: p for p in plans}
        retired = facts[tables.retirements.name]
        if not isinstance(retired, list):
            raise ValueError
        for event in retired:
            if not isinstance(event, dict) or not isinstance(event["plan_id"], str):
                raise ValueError
            source = plan_map[event["plan_id"]]
            if (
                event["install_id"] not in {i.install_id for i in source.candidates}
                or not isinstance(event["created_at"], str)
                or datetime.fromisoformat(event["created_at"]).tzinfo is None
            ):
                raise ValueError
        return tuple(plans)
    except (ValidationError, ValueError, TypeError, KeyError):
        raise SupplyError("cleanup_plan_invalid") from None


def _historical_reasons(
    plan: CleanupPlan, records: tuple[SupplyRecord, ...]
) -> dict[str, tuple[ProtectionReason, ...]]:
    def rows(name: str) -> list[dict[str, JsonValue]]:
        values = plan.facts[name]
        if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
            raise ValueError
        return [v for v in values if isinstance(v, dict)]

    events = sorted(
        rows(tables.activations.name), key=lambda v: int(str(v["activation_id"]))
    )
    selected = rows(tables.current_selection.name)
    if selected != (
        [{"singleton": 1, "activation_id": events[-1]["activation_id"]}]
        if events
        else []
    ):
        raise ValueError
    history = tuple(
        Activation(
            int(str(v["activation_id"])),
            str(v["supply_id"]),
            str(v["install_id"]),
            str(v["snapshot_id"]),
            str(v["root_id"]),
            Path(str(v["root_path"])),
            str(v["created_at"]),
        )
        for v in events
    )
    supplied = {v["supply_id"] for v in rows(tables.supplies.name)}
    rooted = {v["root_id"] for v in rows(tables.roots.name)}
    installed = rows(tables.installs.name)
    checked = rows(tables.checks.name)
    for instance in installed:
        if instance["supply_id"] not in supplied or instance["root_id"] not in rooted:
            raise ValueError
        if not any(
            c["install_id"] == instance["install_id"] and c["passed"] == 1
            for c in checked
        ):
            raise ValueError
    if any(
        c["install_id"] not in {i["install_id"] for i in installed} for c in checked
    ):
        raise ValueError
    for event in events:
        if not any(
            i["install_id"] == event["install_id"]
            and i["supply_id"] == event["supply_id"]
            and i["root_id"] == event["root_id"]
            for i in installed
        ):
            raise ValueError
    check_ids = {v["check_id"] for v in checked}
    install_ids = {v["install_id"] for v in rows(tables.installs.name)}
    previous = tuple(
        replace(
            r,
            installs=tuple(
                replace(i, checks=tuple(c for c in i.checks if c.check_id in check_ids))
                for i in r.installs
                if i.install_id in install_ids
            ),
        )
        for r in records
    )
    return protection_reasons(
        previous, history, {i.install_id: i.observation for i in plan.items}
    )


def _validate_layout(plan: CleanupPlan) -> None:
    def rows(name: str) -> list[dict[str, JsonValue]]:
        value = plan.facts[name]
        if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
            raise ValueError
        return [v for v in value if isinstance(v, dict)]

    roots = {str(r["root_id"]): str(r["path"]) for r in rows(tables.roots.name)}
    retired = {str(r["install_id"]) for r in rows(tables.retirements.name)}
    activated = {str(r["install_id"]) for r in rows(tables.activations.name)}
    for value in (
        plan.data_root,
        plan.config_root,
        plan.material_root,
        *roots.values(),
    ):
        path = Path(value)
        if not path.is_absolute() or str(path) != value or ".." in path.parts:
            raise ValueError
    if any(Path(root) == Path("/") for root in roots.values()):
        raise ValueError
    for item in plan.items:
        if item.disposition == "candidate":
            guarded = tuple(
                Path(v)
                for v in (
                    item.root_path,
                    plan.data_root,
                    plan.config_root,
                    plan.material_root,
                )
            )
            for index, root in enumerate(guarded):
                if root == Path("/") or any(
                    root.is_relative_to(other) or other.is_relative_to(root)
                    for other in guarded[index + 1 :]
                ):
                    raise ValueError
        if item.root_path != roots[item.root_id] or item.ever_activated != (
            item.install_id in activated
        ):
            raise ValueError
        if (item.state == "retired_pending") != (item.install_id in retired):
            raise ValueError
        if item.relative_path.startswith(".trash/") and item.state != "retired_pending":
            raise ValueError
        if item.disposition in {"candidate", "protected"}:
            if (
                item.present is not True
                or item.actual_tree_hash is None
                or item.allocated_bytes is None
                or item.logical_bytes is None
            ):
                raise ValueError
            if bool(item.protection) != (item.disposition == "protected"):
                raise ValueError
            if item.reason != (
                "passed"
                if item.actual_tree_hash == item.expected_tree_hash
                else "tree_mismatch"
            ):
                raise ValueError
        elif (
            item.actual_tree_hash is not None
            or item.allocated_bytes is not None
            or item.logical_bytes is not None
        ):
            raise ValueError
        if item.disposition == "absent" and item.present is not False:
            raise ValueError
    for manual in plan.manual:
        path = Path(manual.relative_path)
        if (
            manual.root_id not in roots
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != manual.relative_path
        ):
            raise ValueError
