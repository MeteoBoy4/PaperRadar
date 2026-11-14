"""按事实拥有者声明的持久主键固定完整历史范围;不依赖墙钟或物理 rowid。"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Connection, Table, select, tuple_

# 仅内部审计键;不会进入跨库 payload。
type HistoryKeys = tuple[tuple[str | int, ...], ...]


class HistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    table: str
    identities: HistoryKeys
    rows: tuple[dict[str, Any], ...]


class HistoryBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    identities: HistoryKeys


def boundary(connection: Connection, table: Table) -> HistoryBoundary:
    keys = tuple(table.primary_key.columns)
    return HistoryBoundary(
        identities=tuple(
            tuple(row) for row in connection.execute(select(*keys).order_by(*keys))
        )
    )


def history_page(
    connection: Connection,
    table: Table,
    columns: tuple[str, ...],
    *,
    through: Mapping[str, HistoryKeys] | None = None,
    hashed: tuple[str, ...] = (),
) -> HistoryPage:
    """事实组件指定表和安全字段;私有原文列仅保存摘要。"""
    identities = (
        boundary(connection, table).identities
        if through is None
        else through[table.name]
    )
    keys = tuple(table.primary_key.columns)
    if len(identities) != len(set(identities)) or any(
        len(key) != len(keys) for key in identities
    ):
        raise ValueError("invalid_history_boundary")
    statement = (
        select(*(table.c[c] for c in columns))
        .where(tuple_(*keys).in_(identities))
        .order_by(*keys)
    )
    rows = []
    for item in connection.execute(statement).mappings():
        record = dict(item)
        for key in hashed:
            value = record.pop(key)
            record[f"{key}_sha256"] = hashlib.sha256(
                json.dumps(
                    value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
        rows.append(record)
    if len(rows) != len(identities):
        raise ValueError("history_reference_missing")
    return HistoryPage(table=table.name, identities=identities, rows=tuple(rows))


def history_boundaries(
    connection: Connection, tables: tuple[Table, ...]
) -> dict[str, HistoryBoundary]:
    return {table.name: boundary(connection, table) for table in tables}
