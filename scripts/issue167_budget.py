"""#167 离线预算原型:持久预占,无网络/认证/执行入口,非产品授权。"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

LAYERS = frozenset({"auth_cli", "prompt", "model_operation", "refresh_http"})


class BudgetRejected(ValueError):
    """仅携带受控拒绝原因。"""


def amounts(values: dict[str, int]) -> str:
    if set(values) != LAYERS or any(
        type(value) is not int or value < 0 for value in values.values()
    ):
        raise BudgetRejected("counts_invalid")
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class FrozenPlan:
    """纯合成案例/上限;计划身份不等于所有者授权。"""

    cases: tuple[str, ...]
    per_case: dict[str, int]
    total: dict[str, int]

    def seal(self) -> str:
        if (
            not self.cases
            or len(set(self.cases)) != len(self.cases)
            or any(not case or not case.isascii() for case in self.cases)
        ):
            raise BudgetRejected("cases_invalid")
        data = [sorted(self.cases), amounts(self.per_case), amounts(self.total)]
        return hashlib.sha256(json.dumps(data).encode()).hexdigest()


class BudgetBook:
    """只操作指定合成数据库。没有自动重建/退款/重试/发送API。"""

    def __init__(self, path: Path, plan: FrozenPlan) -> None:
        self.plan = plan
        self.seal = plan.seal()
        # mode=rw:文件消失后不能隐式创建并重置预算。
        self.connection = sqlite3.connect(
            path.resolve().as_uri() + "?mode=rw", uri=True, isolation_level=None
        )
        try:
            metadata = self.connection.execute(
                "SELECT seal, blocked FROM metadata WHERE singleton = 1"
            ).fetchone()
            if metadata is None or metadata[0] != self.seal:
                raise BudgetRejected("plan_mismatch")
        except (sqlite3.Error, BudgetRejected):
            self.close()
            raise BudgetRejected("ledger_invalid") from None

    @classmethod
    def create(cls, path: Path, plan: FrozenPlan) -> BudgetBook:
        seal = plan.seal()
        # 排他创建;初始化失败保留文件,不得偷偷删除后重新获得余额。
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        with sqlite3.connect(path) as connection:
            connection.executescript(
                "CREATE TABLE metadata (singleton INTEGER PRIMARY KEY, "
                "seal TEXT NOT NULL, blocked INTEGER NOT NULL);"
                "CREATE TABLE reservations (case_id TEXT PRIMARY KEY, "
                "run_id TEXT NOT NULL, settled INTEGER NOT NULL, "
                "actual TEXT);"
            )
            connection.execute("INSERT INTO metadata VALUES (1, ?, 0)", (seal,))
        return cls(path, plan)

    def _plan_unchanged(self) -> bool:
        try:
            return self.plan.seal() == self.seal
        except BudgetRejected:
            return False

    def reserve(self, case: str, run: str) -> None:
        """发送前提交整例上限;任何退出路径都不返还预占。"""
        if not self._plan_unchanged():
            self.connection.execute("UPDATE metadata SET blocked = 1")
            raise BudgetRejected("plan_mutated")
        connection = self.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            if connection.execute("SELECT blocked FROM metadata").fetchone()[0]:
                raise BudgetRejected("ledger_blocked")
            if case not in self.plan.cases or not run:
                raise BudgetRejected("case_unapproved")
            if connection.execute(
                "SELECT 1 FROM reservations WHERE case_id = ?", (case,)
            ).fetchone():
                raise BudgetRejected("case_already_reserved")
            if connection.execute(
                "SELECT 1 FROM reservations WHERE settled = 0"
            ).fetchone():
                raise BudgetRejected("previous_attempt_unsettled")
            count = connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[
                0
            ]
            if any(
                (count + 1) * self.plan.per_case[layer] > self.plan.total[layer]
                for layer in LAYERS
            ):
                raise BudgetRejected("budget_exhausted")
            connection.execute(
                "INSERT INTO reservations VALUES (?, ?, 0, NULL)", (case, run)
            )
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise

    def settle(
        self,
        case: str,
        actual: dict[str, int] | None,
        *,
        cleanup_verified: bool = False,
    ) -> None:
        """未知计数或超限持久阻断;结算不退款,不凭0计数重发。"""
        connection = self.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT settled FROM reservations WHERE case_id = ?", (case,)
            ).fetchone()
            if row is None or row[0]:
                raise BudgetRejected("reservation_not_pending")
            failed = (
                actual is None
                or cleanup_verified is not True
                or not self._plan_unchanged()
            )
            encoded = None
            if actual is not None:
                try:
                    encoded = amounts(actual)
                except BudgetRejected:
                    failed = True
                else:
                    failed = failed or any(
                        actual[layer] > self.plan.per_case[layer] for layer in LAYERS
                    )
            connection.execute(
                "UPDATE reservations SET settled = 1, actual = ? WHERE case_id = ?",
                (encoded, case),
            )
            if failed:
                connection.execute("UPDATE metadata SET blocked = 1")
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        if failed:
            raise BudgetRejected("observation_unknown_or_excess")

    def close(self) -> None:
        self.connection.close()
