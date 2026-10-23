"""执行编排:事务外映射,数据库短事务串行化领取与租约。"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from typing import Any

from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.papers import PaperError, PaperFacts, resolve_revision
from paper_radar.screening_tasks.attempt_models import (
    Claim,
    Clock,
    FailureKind,
    FailureOrigin,
    FailureReceipt,
    FailureReport,
    TaskStatus,
)
from paper_radar.screening_tasks.attempt_rules import (
    correction_for,
    derive_status,
    digest,
    lease_expiry,
    read_timestamp,
    timestamp,
    utc_now,
)
from paper_radar.screening_tasks.database_errors import database_error
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.models import FrozenInput, RequestReceipt
from paper_radar.screening_tasks.repository import evidence_values, receipt_row
from paper_radar.screening_tasks.success_rules import decode_issues
from paper_radar.screening_tasks.tables import attempts, failures, leases, successes
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


class AttemptService:
    def __init__(self, database: Path, clock: Clock | None) -> None:
        self.database = database
        self.clock = clock

    @contextmanager
    def connection(self, *, write: bool) -> Iterator[Connection]:
        engine = open_database(
            self.database,
            mode=DatabaseMode.READ_WRITE if write else DatabaseMode.READ_ONLY,
        )
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
                yield connection
                if write:
                    connection.commit()
        except SQLAlchemyError as error:
            raise database_error(error) from None
        except (ValueError, TypeError, KeyError, OverflowError):
            raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
        finally:
            engine.dispose()

    def claim(self, receipt: RequestReceipt, frozen: FrozenInput) -> Claim:
        # 时钟错误与指纹变化都先于领取事务,不会占用预算。
        now = utc_now(self.clock)
        mapping = PaperFacts(self.database).map_screening_inputs(
            paper_id=receipt.paper_id, snapshot_id=receipt.snapshot_id
        )
        mapped = mapping.boundary if receipt.stage == "boundary" else mapping.value
        if mapped.reason is not None:
            raise PaperError(mapped.reason)
        if mapped.value is None or mapped.evidence is None:
            raise TaskError(TaskReason.CORRUPT_REFERENCE)
        if mapped.value.fingerprint != frozen.fingerprint:
            raise TaskError(TaskReason.FACTS_CHANGED)
        basis = evidence_values(mapped.evidence)
        credential, renewal = token_hex(32), token_hex(32)
        expires = lease_expiry(now)
        with self.connection(write=True) as connection:
            row = receipt_row(connection, receipt.receipt_id)
            if row is None or row["task_id"] != receipt.task_id:
                raise TaskError(TaskReason.CORRUPT_REFERENCE)
            current = resolve_revision(connection, paper_id=receipt.paper_id)
            if evidence_values(current) != basis:
                raise TaskError(TaskReason.FACTS_CHANGED)
            existing = self._attempt_rows(connection, receipt.task_id)
            now = utc_now(self.clock)
            expires = lease_expiry(now)
            if (
                connection.execute(
                    select(successes.c.success_id).where(
                        successes.c.budget_id == receipt.budget_id
                    )
                ).first()
                is not None
            ):
                raise TaskError(TaskReason.ALREADY_SUCCEEDED)
            if existing and existing[-1]["kind"] is None:
                if now < read_timestamp(existing[-1]["expires_at"]):
                    raise TaskError(TaskReason.TASK_RUNNING)
                self._recover(connection, existing[-1], now)
            number = len(existing) + 1
            if number <= 2:
                if existing and now < read_timestamp(
                    existing[-1]["settled_at"] or timestamp(now)
                ):
                    raise TaskError(TaskReason.INVALID_CLOCK)
                connection.execute(
                    attempts.insert().values(
                        task_id=receipt.task_id,
                        attempt_no=number,
                        receipt_id=receipt.receipt_id,
                        claimed_at=timestamp(now),
                        credential_sha256=digest(credential),
                        renewal_sha256=digest(renewal),
                        **basis,
                    )
                )
                connection.execute(
                    leases.insert().values(
                        task_id=receipt.task_id,
                        attempt_no=number,
                        expires_at=timestamp(expires),
                    )
                )
        # 回收第二次过期尝试必须先提交,再返回预算耗尽。
        if number > 2:
            raise TaskError(TaskReason.BUDGET_EXHAUSTED)
        return Claim(
            task_id=receipt.task_id,
            attempt_no=number,
            receipt_id=receipt.receipt_id,
            claimed_at=now,
            expires_at=expires,
            credential=credential,
            renewal_handle=renewal,
            **basis,
        )

    def status(self, receipt: RequestReceipt) -> TaskStatus:
        now = utc_now(self.clock)
        with self.connection(write=False) as connection:
            rows = self._attempt_rows(connection, receipt.task_id)
            return derive_status(receipt.task_id, rows, now)

    def correction(self, receipt: RequestReceipt) -> str | None:
        with self.connection(write=False) as connection:
            rows = self._attempt_rows(connection, receipt.task_id)
            previous = next(
                (row for row in reversed(rows) if row["kind"] is not None), None
            )
            if previous is None:
                return None
            message = correction_for(FailureKind(previous["kind"]))
            issues = decode_issues(previous["issues_json"])
            if issues:
                message = (
                    (message or "")
                    + " "
                    + "; ".join(
                        f"{issue.location} [{issue.category.value}]" for issue in issues
                    )
                )
            return message

    def renew(self, handle: str) -> datetime:
        self._require_secret(handle)
        with self.connection(write=True) as connection:
            row = connection.execute(
                select(attempts.c.task_id).where(
                    attempts.c.renewal_sha256 == digest(handle)
                )
            ).first()
            if row is None:
                raise TaskError(TaskReason.INVALID_CREDENTIAL)
            rows = self._attempt_rows(connection, row.task_id)
            current = rows[-1]
            if (
                current["renewal_sha256"] != digest(handle)
                or current["kind"] is not None
                or current["success_id"] is not None
            ):
                raise TaskError(TaskReason.INVALID_CREDENTIAL)
            now = utc_now(self.clock)
            self._require_time(current, now)
            expires = lease_expiry(now)
            connection.execute(
                leases.update()
                .where(
                    leases.c.task_id == current["task_id"],
                    leases.c.attempt_no == current["attempt_no"],
                )
                .values(expires_at=timestamp(expires))
            )
            return expires

    def fail(
        self, claim: Claim, report: FailureReport, *, origin: FailureOrigin = "executor"
    ) -> FailureReceipt:
        if type(claim) is not Claim:
            raise TaskError(TaskReason.INVALID_CREDENTIAL)
        self._require_secret(claim.credential)
        allowed = {
            FailureKind.TIMEOUT,
            FailureKind.CANCELLED,
            FailureKind.PROTOCOL_ERROR,
            FailureKind.EXECUTOR_ERROR,
        }
        if (
            type(report) is not FailureReport
            or type(report.kind) is not FailureKind
            or report.kind not in allowed
        ):
            raise TaskError(TaskReason.INVALID_FAILURE)
        with self.connection(write=True) as connection:
            rows = self._attempt_rows(connection, claim.task_id)
            row = next(
                (item for item in rows if item["attempt_no"] == claim.attempt_no), None
            )
            if row is None or row["credential_sha256"] != digest(claim.credential):
                raise TaskError(TaskReason.INVALID_CREDENTIAL)
            if row["success_id"] is not None:
                raise TaskError(TaskReason.SETTLEMENT_CONFLICT)
            # 精确失败重放先于当前持有者检查;回收永不伪装成执行者报告。
            if row["kind"] is not None:
                if row["origin"] == "recovery":
                    raise TaskError(TaskReason.INVALID_CREDENTIAL)
                if row["kind"] != report.kind.value or row["origin"] != origin:
                    raise TaskError(TaskReason.SETTLEMENT_CONFLICT)
                return self._failure_receipt(row)
            if row["attempt_no"] != rows[-1]["attempt_no"]:
                raise TaskError(TaskReason.INVALID_CREDENTIAL)
            now = utc_now(self.clock)
            self._require_time(row, now)
            connection.execute(
                failures.insert().values(
                    task_id=claim.task_id,
                    attempt_no=claim.attempt_no,
                    kind=report.kind.value,
                    origin=origin,
                    settled_at=timestamp(now),
                )
            )
            return FailureReceipt(
                claim.task_id, claim.attempt_no, report.kind, origin, now
            )

    def reclaim(self, receipt: RequestReceipt) -> TaskStatus:
        with self.connection(write=True) as connection:
            now = utc_now(self.clock)
            rows = self._attempt_rows(connection, receipt.task_id)
            if (
                rows
                and rows[-1]["kind"] is None
                and rows[-1]["success_id"] is None
                and now >= read_timestamp(rows[-1]["expires_at"])
            ):
                self._recover(connection, rows[-1], now)
                rows = self._attempt_rows(connection, receipt.task_id)
            return derive_status(receipt.task_id, rows, now)

    @staticmethod
    def _require_secret(value: str) -> None:
        if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise TaskError(TaskReason.INVALID_CREDENTIAL)

    @staticmethod
    def _require_time(row: dict[str, Any], now: datetime) -> None:
        if now < read_timestamp(row["claimed_at"]):
            raise TaskError(TaskReason.INVALID_CLOCK)

    @classmethod
    def _recover(
        cls, connection: Connection, row: dict[str, Any], now: datetime
    ) -> None:
        cls._require_time(row, now)
        connection.execute(
            failures.insert().values(
                task_id=row["task_id"],
                attempt_no=row["attempt_no"],
                kind=FailureKind.OUTCOME_UNKNOWN.value,
                origin="recovery",
                settled_at=timestamp(now),
            )
        )

    @staticmethod
    def _failure_receipt(row: dict[str, Any]) -> FailureReceipt:
        return FailureReceipt(
            row["task_id"],
            row["attempt_no"],
            FailureKind(row["kind"]),
            row["origin"],
            read_timestamp(row["settled_at"]),
            decode_issues(row["issues_json"]),
        )

    @staticmethod
    def _attempt_rows(connection: Connection, task_id: str) -> list[dict[str, Any]]:
        rows = [
            dict(row)
            for row in connection.execute(
                select(
                    attempts,
                    leases.c.expires_at,
                    failures.c.kind,
                    failures.c.origin,
                    failures.c.settled_at,
                    failures.c.issues_json,
                    successes.c.success_id,
                )
                .outerjoin(
                    leases,
                    (leases.c.task_id == attempts.c.task_id)
                    & (leases.c.attempt_no == attempts.c.attempt_no),
                )
                .outerjoin(
                    failures,
                    (failures.c.task_id == attempts.c.task_id)
                    & (failures.c.attempt_no == attempts.c.attempt_no),
                )
                .outerjoin(
                    successes,
                    (successes.c.task_id == attempts.c.task_id)
                    & (successes.c.attempt_no == attempts.c.attempt_no),
                )
                .where(attempts.c.task_id == task_id)
                .order_by(attempts.c.attempt_no)
            ).mappings()
        ]
        if (
            any(row["expires_at"] is None for row in rows)
            or [row["attempt_no"] for row in rows] != list(range(1, len(rows) + 1))
            or len(rows) > 2
        ):
            raise TaskError(TaskReason.CORRUPT_REFERENCE)
        if any(
            row["success_id"] is not None and row["kind"] is not None for row in rows
        ) or any(row["kind"] is None for row in rows[:-1]):
            raise TaskError(TaskReason.CORRUPT_REFERENCE)
        return rows
