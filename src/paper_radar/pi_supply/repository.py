"""短事务登记与离线语义回放;不访问本机安装树或网络。"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from pydantic import ValidationError
from sqlalchemy import Connection, Engine, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.config.identity import sha256
from paper_radar.pi_supply import tables
from paper_radar.pi_supply.errors import GUIDANCE, SupplyError, SupplyReason
from paper_radar.pi_supply.materials import derive_lock, object_bytes
from paper_radar.pi_supply.models import (
    Activation,
    InstallCheck,
    InstallInstance,
    RebuildFailure,
    SupplyManifest,
    SupplyRecord,
)
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError, StorageReason

MATERIAL_ROLES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "release.json",
        "SHASUMS256.txt",
        "derived-lock.json",
        "integrity-supplements.json",
    }
)


def now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def database_engine(database: Path, *, write: bool = False) -> Iterator[Engine]:
    try:
        engine = open_database(
            database,
            mode=DatabaseMode.READ_WRITE if write else DatabaseMode.READ_ONLY,
        )
        try:
            require_current_revision(engine)
            yield engine
        finally:
            engine.dispose()
    except StorageError as error:
        if error.reason in {
            StorageReason.UPGRADE_REQUIRED,
            StorageReason.DATABASE_UNINITIALIZED,
        }:
            raise SupplyError("upgrade_required") from None
        raise SupplyError("database_unavailable") from None
    except SQLAlchemyError:
        raise SupplyError("database_unavailable") from None


def ids(database: Path) -> frozenset[str]:
    with database_engine(database) as engine, engine.connect() as connection:
        return frozenset(
            connection.execute(select(tables.supplies.c.supply_id)).scalars()
        )


def _date(value: str) -> None:
    if datetime.fromisoformat(value).tzinfo is None:
        raise ValueError


def read_records(database: Path) -> tuple[SupplyRecord, ...]:
    return read_state(database)[0]


def read_state(
    database: Path,
) -> tuple[tuple[SupplyRecord, ...], tuple[Activation, ...], Activation | None]:
    """重验原材料、派生规则、身份及 D5 闭包,不把自洽的坏清单当成事实。"""
    try:
        with database_engine(database) as engine, engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            from paper_radar.pi_supply.cleanup_history import safety_facts

            cleanup_facts = safety_facts(connection)
            cleanup_rows = [
                dict(row)
                for row in connection.execute(select(tables.cleanup_plans)).mappings()
            ]
            owner_rows = (
                connection.execute(select(tables.database_identity)).mappings().all()
            )
            if (
                len(owner_rows) != 1
                or owner_rows[0]["singleton"] != 1
                or not re.fullmatch(r"[0-9a-f]{32}", owner_rows[0]["database_id"])
            ):
                raise SupplyError("supply_corrupt")
            root_rows = connection.execute(select(tables.roots)).mappings().all()
            roots: dict[str, Path] = {}
            for root in root_rows:
                path = Path(root["path"])
                if (
                    not re.fullmatch(r"[0-9a-f]{32}", root["root_id"])
                    or not path.is_absolute()
                    or str(path) != root["path"]
                    or ".." in path.parts
                    or path == Path("/")
                ):
                    raise SupplyError("supply_corrupt")
                roots[root["root_id"]] = path
            supply_rows = connection.execute(select(tables.supplies)).mappings().all()
            material_rows = (
                connection.execute(select(tables.materials)).mappings().all()
            )
            install_rows = connection.execute(select(tables.installs)).mappings().all()
            check_rows = connection.execute(select(tables.checks)).mappings().all()
            failure_rows = (
                connection.execute(select(tables.rebuild_failures)).mappings().all()
            )
            activation_rows = (
                connection.execute(
                    select(tables.activations).order_by(
                        tables.activations.c.activation_id
                    )
                )
                .mappings()
                .all()
            )
            selection_rows = (
                connection.execute(select(tables.current_selection)).mappings().all()
            )
        result: dict[str, SupplyRecord] = {}
        for row in supply_rows:
            raw = row["manifest"]
            manifest = SupplyManifest.model_validate(object_bytes(raw))
            if (
                manifest.canonical_bytes != raw
                or manifest.supply_id != row["supply_id"]
                or manifest.material_key != row["material_key"]
            ):
                raise SupplyError("supply_corrupt")
            _date(row["created_at"])
            materials = {}
            for item in material_rows:
                if item["supply_id"] == row["supply_id"]:
                    if sha256(item["raw"]) != item["sha256"]:
                        raise SupplyError("supply_corrupt")
                    materials[item["role"]] = item["raw"]
            if {
                key: sha256(value) for key, value in materials.items()
            } != manifest.materials:
                raise SupplyError("supply_corrupt")
            evidence_roles = {
                f"d5-evidence/{item.sha256}.bin"
                for item in manifest.d5.evidence
                if item.kind == "evidence_file"
            }
            if set(materials) != MATERIAL_ROLES | evidence_roles:
                raise SupplyError("supply_corrupt")
            derived, supplements = derive_lock(
                materials["package.json"],
                materials["package-lock.json"],
                materials["release.json"],
                manifest.pi_version,
                manifest.node_version,
            )
            if (
                derived != materials["derived-lock.json"]
                or supplements != materials["integrity-supplements.json"]
            ):
                raise SupplyError("supply_corrupt")
            expected = (
                f"{manifest.node_sha256}  "
                f"node-v{manifest.node_version}-linux-x64.tar.xz"
            )
            if materials["SHASUMS256.txt"].decode().splitlines().count(expected) != 1:
                raise SupplyError("supply_corrupt")
            for entry in (manifest.node_entry, manifest.npm_entry, manifest.pi_entry):
                relative_entry = PurePosixPath(entry)
                if (
                    relative_entry.is_absolute()
                    or ".." in relative_entry.parts
                    or relative_entry.as_posix() != entry
                ):
                    raise SupplyError("supply_corrupt")
            if (
                manifest.node_entry != "node/bin/node"
                or manifest.npm_entry != "node/lib/node_modules/npm/bin/npm-cli.js"
            ):
                raise SupplyError("supply_corrupt")
            if not manifest.pi_entry.startswith(
                "app/node_modules/@earendil-works/pi-coding-agent/"
            ):
                raise SupplyError("supply_corrupt")
            instances = []
            for item in install_rows:
                if item["supply_id"] != row["supply_id"]:
                    continue
                if not re.fullmatch(r"[0-9a-f]{32}", item["install_id"]):
                    raise SupplyError("supply_corrupt")
                _date(item["created_at"])
                checks = []
                for check in check_rows:
                    if check["install_id"] != item["install_id"]:
                        continue
                    _date(check["created_at"])
                    if (
                        check["scope"] != "install_check"
                        or check["passed"] not in (0, 1)
                        or (check["passed"] == 1 and check["reason"] != "passed")
                        or (check["passed"] == 0 and check["reason"] not in GUIDANCE)
                    ):
                        raise SupplyError("supply_corrupt")
                    checks.append(
                        InstallCheck(
                            check["check_id"],
                            check["scope"],
                            bool(check["passed"]),
                            check["reason"],
                            check["created_at"],
                        )
                    )
                if not any(check.passed for check in checks):
                    raise SupplyError("supply_corrupt")
                instances.append(
                    InstallInstance(
                        item["install_id"],
                        item["root_id"],
                        roots[item["root_id"]] / row["supply_id"] / item["install_id"],
                        item["created_at"],
                        tuple(sorted(checks, key=lambda c: c.check_id)),
                    )
                )
            if not instances:
                raise SupplyError("supply_corrupt")
            result[row["supply_id"]] = SupplyRecord(
                row["supply_id"],
                manifest,
                materials,
                tuple(
                    sorted(
                        instances, key=lambda item: (item.created_at, item.install_id)
                    )
                ),
                row["created_at"],
                tuple(
                    RebuildFailure(
                        failure["failure_id"], failure["reason"], failure["created_at"]
                    )
                    for failure in sorted(failure_rows, key=lambda f: f["failure_id"])
                    if failure["supply_id"] == row["supply_id"]
                ),
            )
        for failure in failure_rows:
            _date(failure["created_at"])
            if (
                failure["supply_id"] not in result
                or failure["failure_id"] < 1
                or failure["reason"] not in GUIDANCE
            ):
                raise SupplyError("supply_corrupt")
        # 构造引用 DAG。供给只引用冻结前已经存在的记录。
        visited: set[str] = set()
        first_checks = {
            identity: min(
                check.check_id
                for instance in record.installs
                for check in instance.checks
            )
            for identity, record in result.items()
        }

        def visit(supply_id: str, active: frozenset[str]) -> None:
            if supply_id in active or supply_id not in result:
                raise SupplyError("evidence_unresolved")
            if supply_id in visited:
                return
            record = result[supply_id]
            references = []
            if record.manifest.d5.baseline_supply_id:
                references.append(record.manifest.d5.baseline_supply_id)
            for evidence in record.manifest.d5.evidence:
                other = result.get(evidence.supply_id or supply_id)
                if other is None:
                    raise SupplyError("evidence_unresolved")
                if evidence.kind == "supply_material" and (
                    evidence.material not in other.materials
                    or sha256(other.materials[evidence.material]) != evidence.sha256
                ):
                    raise SupplyError("evidence_unresolved")
                if evidence.check_id is not None and not any(
                    check.check_id == evidence.check_id
                    and check.check_id < first_checks[supply_id]
                    for install in other.installs
                    for check in install.checks
                ):
                    raise SupplyError("evidence_unresolved")
                if evidence.supply_id:
                    references.append(evidence.supply_id)
            for reference in references:
                if (
                    reference not in result
                    or first_checks[reference] >= first_checks[supply_id]
                ):
                    raise SupplyError("evidence_unresolved")
                visit(reference, active | {supply_id})
            visited.add(supply_id)

        for supply_id in result:
            visit(supply_id, frozenset())
        if (
            any(row["supply_id"] not in result for row in material_rows)
            or any(row["supply_id"] not in result for row in install_rows)
            or any(
                row["install_id"] not in {i["install_id"] for i in install_rows}
                for row in check_rows
            )
        ):
            raise SupplyError("supply_corrupt")
        from paper_radar.pi_supply.selection import load_snapshot, match_snapshot

        history = []
        for row in activation_rows:
            _date(row["created_at"])
            record = result[row["supply_id"]]
            instance = next(
                (
                    item
                    for item in record.installs
                    if item.install_id == row["install_id"]
                ),
                None,
            )
            if (
                type(row["activation_id"]) is not int
                or row["activation_id"] < 1
                or not re.fullmatch(r"[0-9a-f]{64}", row["snapshot_id"])
                or instance is None
                or instance.root_id != row["root_id"]
                or str(instance.path.parent.parent) != row["root_path"]
            ):
                raise SupplyError("supply_corrupt")
            try:
                match_snapshot(
                    load_snapshot(database, row["snapshot_id"]),
                    record.manifest.pi_version,
                )
            except SupplyError:
                raise SupplyError("supply_corrupt") from None
            history.append(
                Activation(
                    row["activation_id"],
                    row["supply_id"],
                    row["install_id"],
                    row["snapshot_id"],
                    row["root_id"],
                    Path(row["root_path"]),
                    row["created_at"],
                )
            )
        if bool(history) != bool(selection_rows) or len(selection_rows) > 1:
            raise SupplyError("supply_corrupt")
        current = None
        if selection_rows:
            if (
                selection_rows[0]["singleton"] != 1
                or selection_rows[0]["activation_id"] != history[-1].activation_id
            ):
                raise SupplyError("supply_corrupt")
            current = history[-1]
        from paper_radar.pi_supply.cleanup_history import validate_plan_history

        validate_plan_history(cleanup_rows, cleanup_facts, tuple(result.values()))
        return (
            tuple(
                sorted(result.values(), key=lambda row: (row.created_at, row.supply_id))
            ),
            tuple(history),
            current,
        )
    except (
        ValidationError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        UnicodeError,
        RecursionError,
    ):
        raise SupplyError("supply_corrupt") from None


def commit_supply(
    database: Path,
    manifest: SupplyManifest,
    raw_materials: dict[str, bytes],
    root_id: str,
    install_id: str,
) -> None:
    timestamp = now()
    with (
        database_engine(database, write=True) as engine,
        engine.connect() as connection,
    ):
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            connection.execute(
                insert(tables.supplies).values(
                    supply_id=manifest.supply_id,
                    material_key=manifest.material_key,
                    manifest=manifest.canonical_bytes,
                    created_at=timestamp,
                )
            )
            connection.execute(
                insert(tables.materials),
                [
                    {
                        "supply_id": manifest.supply_id,
                        "role": role,
                        "sha256": sha256(raw),
                        "raw": raw,
                    }
                    for role, raw in raw_materials.items()
                ],
            )
            connection.execute(
                insert(tables.installs).values(
                    install_id=install_id,
                    supply_id=manifest.supply_id,
                    root_id=root_id,
                    created_at=timestamp,
                )
            )
            connection.execute(
                insert(tables.checks).values(
                    install_id=install_id,
                    scope="install_check",
                    passed=1,
                    reason="passed",
                    created_at=timestamp,
                )
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def append_check(database: Path, install_id: str, reason: SupplyReason | None) -> None:
    with database_engine(database, write=True) as engine, engine.begin() as connection:
        connection.execute(
            insert(tables.checks).values(
                install_id=install_id,
                scope="install_check",
                passed=int(reason is None),
                reason=reason or "passed",
                created_at=now(),
            )
        )


def append_rebuild_failure(
    database: Path, supply_id: str, reason: SupplyReason
) -> None:
    with database_engine(database, write=True) as engine, engine.begin() as connection:
        connection.execute(
            insert(tables.rebuild_failures).values(
                supply_id=supply_id, reason=reason, created_at=now()
            )
        )


def commit_install(
    database: Path, manifest: SupplyManifest, root_id: str, install_id: str
) -> None:
    with (
        database_engine(database, write=True) as engine,
        engine.connect() as connection,
    ):
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            stored = connection.execute(
                select(tables.supplies.c.manifest).where(
                    tables.supplies.c.supply_id == manifest.supply_id
                )
            ).scalar_one()
            if stored != manifest.canonical_bytes:
                raise SupplyError("supply_corrupt")
            existing = (
                connection.execute(
                    select(tables.installs).where(
                        tables.installs.c.install_id == install_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if (
                    existing["root_id"] != root_id
                    or existing["supply_id"] != manifest.supply_id
                ):
                    raise SupplyError("publication_conflict")
                return
            timestamp = now()
            connection.execute(
                insert(tables.installs).values(
                    install_id=install_id,
                    supply_id=manifest.supply_id,
                    root_id=root_id,
                    created_at=timestamp,
                )
            )
            connection.execute(
                insert(tables.checks).values(
                    install_id=install_id,
                    scope="install_check",
                    passed=1,
                    reason="passed",
                    created_at=timestamp,
                )
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def commit_activation(
    database: Path, record: SupplyRecord, instance: InstallInstance, snapshot_id: str
) -> Activation:
    """全树核验由调用方在事务外完成;短事务只发布完整事件和唯一选择。"""
    with (
        database_engine(database, write=True) as engine,
        engine.connect() as connection,
    ):
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            stored = connection.execute(
                select(tables.supplies.c.manifest).where(
                    tables.supplies.c.supply_id == record.supply_id
                )
            ).scalar_one()
            registered = connection.execute(
                select(tables.installs.c.install_id).where(
                    tables.installs.c.install_id == instance.install_id,
                    tables.installs.c.supply_id == record.supply_id,
                    tables.installs.c.root_id == instance.root_id,
                )
            ).scalar_one_or_none()
            root_path = connection.execute(
                select(tables.roots.c.path).where(
                    tables.roots.c.root_id == instance.root_id
                )
            ).scalar_one()
            if (
                stored != record.manifest.canonical_bytes
                or registered is None
                or root_path != str(instance.path.parent.parent)
            ):
                raise SupplyError("supply_corrupt")
            timestamp = now()
            inserted = connection.execute(
                insert(tables.activations).values(
                    supply_id=record.supply_id,
                    install_id=instance.install_id,
                    snapshot_id=snapshot_id,
                    root_id=instance.root_id,
                    root_path=str(instance.path.parent.parent),
                    created_at=timestamp,
                )
            )
            key = inserted.inserted_primary_key
            if key is None:
                raise SupplyError("database_unavailable")
            activation_id = key[0]
            assert isinstance(activation_id, int)
            _select_activation(connection, activation_id)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return Activation(
        activation_id,
        record.supply_id,
        instance.install_id,
        snapshot_id,
        instance.root_id,
        instance.path.parent.parent,
        timestamp,
    )


def _select_activation(connection: Connection, activation_id: int) -> None:
    result = connection.execute(
        update(tables.current_selection)
        .where(tables.current_selection.c.singleton == 1)
        .values(activation_id=activation_id)
    )
    if not result.rowcount:
        connection.execute(
            insert(tables.current_selection).values(
                singleton=1, activation_id=activation_id
            )
        )
