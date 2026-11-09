"""独立准入账本的受保护接收与只读查询;不连接业务数据库。"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    EvidenceReceipt,
    canonical_bytes,
    content_sha256,
    validate_against_plan,
)

LEDGER_ROOT = Path("/var/lib/paperradar/live-evidence")
LEDGER_SCHEMA_VERSION = 1
MAX_SOURCE_BYTES = 1024 * 1024

LedgerCategory = Literal[
    "ledger_untrusted",
    "ledger_schema_unsupported",
    "protected_entry_required",
    "source_untrusted",
    "source_integrity",
    "receipt_invalid",
    "plan_missing",
    "plan_conflict",
    "plan_mismatch",
    "plan_budget_exceeded",
    "plan_round_conflict",
    "plan_stopped",
    "receipt_conflict",
    "receipt_missing",
    "evidence_time_future",
]


class LedgerError(ValueError):
    def __init__(self, category: LedgerCategory) -> None:
        self.category = category
        self.reason = (
            "ledger_untrusted"
            if category
            in {
                "source_untrusted",
                "source_integrity",
                "ledger_schema_unsupported",
            }
            else category
        )
        super().__init__(category)


@dataclass(frozen=True, slots=True)
class LedgerTrust:
    """操作系统信任边界;产品使用默认 root;替换策略仅供离线 OS fixture。"""

    owner_uid: int = 0
    product_uid: int | None = None
    anchor: Path = Path("/")


@dataclass(frozen=True, slots=True)
class ReceiveResult:
    receipt_id: str
    duplicate: bool


@dataclass(frozen=True, slots=True)
class ReceivedEvidence:
    receipt_id: str
    receipt: EvidenceReceipt
    received_at: datetime
    evidence_active: bool = False


@dataclass(frozen=True, slots=True)
class AuditEvent:
    sequence: int
    action: str
    subject_id: str
    recorded_at: datetime
    reason: str | None


_SCHEMA = """
CREATE TABLE plans(plan_id TEXT PRIMARY KEY,
 digest TEXT NOT NULL, payload BLOB NOT NULL);
CREATE TABLE receipts(receipt_id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
 payload BLOB NOT NULL, source_name TEXT UNIQUE NOT NULL, source_digest TEXT NOT NULL,
 plan_id TEXT NOT NULL REFERENCES plans(plan_id), round_number INTEGER NOT NULL,
 received_at TEXT NOT NULL, UNIQUE(plan_id, round_number));
CREATE TABLE events(sequence INTEGER PRIMARY KEY, action TEXT NOT NULL,
 subject_id TEXT NOT NULL, recorded_at TEXT NOT NULL, reason TEXT);
"""


class EvidenceLedger:
    def __init__(
        self, root: Path = LEDGER_ROOT, *, trust: LedgerTrust | None = None
    ) -> None:
        self.root = root.absolute()
        self.trust = trust or LedgerTrust()
        self.database = self.root / "ledger.sqlite3"

    def _protected(self, path: Path, *, source: bool = False) -> None:
        category: LedgerCategory = "source_untrusted" if source else "ledger_untrusted"
        anchor = self.trust.anchor.absolute()
        if not path.is_absolute() or not path.is_relative_to(anchor):
            raise LedgerError(category)
        current = path
        while True:
            try:
                info = current.lstat()
            except OSError as error:
                raise LedgerError(category) from error
            if (
                stat.S_ISLNK(info.st_mode)
                or info.st_uid != self.trust.owner_uid
                or info.st_mode & 0o022
                or (current != path and not stat.S_ISDIR(info.st_mode))
            ):
                raise LedgerError(category)
            if current == anchor:
                break
            current = current.parent

    def _writer(self) -> None:
        if (
            os.geteuid() != self.trust.owner_uid
            or self.trust.product_uid == os.geteuid()
        ):
            raise LedgerError("protected_entry_required")

    def _read_source(self, source: Path) -> bytes:
        if source.parent != self.root / "inbox" or source.suffix != ".json":
            raise LedgerError("source_untrusted")
        self._protected(source, source=True)
        try:
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_size > MAX_SOURCE_BYTES
                ):
                    raise LedgerError("source_untrusted")
                data = stream.read(MAX_SOURCE_BYTES + 1)
        except OSError as error:
            raise LedgerError("source_untrusted") from error
        if len(data) > MAX_SOURCE_BYTES:
            raise LedgerError("source_untrusted")
        return data

    def initialize(self) -> None:
        """仅特权部署入口在已受保护目录内建立空账本。"""
        self._writer()
        self._protected(self.root)
        self._protected(self.root / "inbox")
        try:
            fd = os.open(self.database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            os.close(fd)
        except FileExistsError:
            with self.connection():
                return
        try:
            with closing(sqlite3.connect(self.database)) as connection:
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.executescript(_SCHEMA)
                connection.execute(f"PRAGMA user_version={LEDGER_SCHEMA_VERSION}")
        except sqlite3.Error as error:
            raise LedgerError("ledger_untrusted") from error
        finally:
            os.chmod(self.database, 0o644)

    @contextmanager
    def connection(self, *, writable: bool = False) -> Iterator[sqlite3.Connection]:
        """供后继准入服务复用的受保护事务边界;产品无法取得写连接。"""
        if writable:
            self._writer()
        self._protected(self.database)
        if not self.database.is_file() or self.database.stat().st_nlink != 1:
            raise LedgerError("ledger_untrusted")
        for suffix in ("-journal", "-wal", "-shm"):
            if os.path.lexists(str(self.database) + suffix):
                raise LedgerError("ledger_untrusted")
        connection: sqlite3.Connection | None = None
        try:
            mode = "rw" if writable else "ro"
            connection = sqlite3.connect(
                f"{self.database.as_uri()}?mode={mode}", uri=True
            )
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA foreign_keys=ON")
            if not writable:
                connection.execute("PRAGMA query_only=ON")
            if connection.execute("PRAGMA journal_mode").fetchone() != ("delete",):
                raise LedgerError("ledger_untrusted")
            if connection.execute("PRAGMA user_version").fetchone() != (
                LEDGER_SCHEMA_VERSION,
            ):
                raise LedgerError("ledger_schema_unsupported")
            if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise LedgerError("ledger_untrusted")
            # 固定必需列在打开时即核对;空库或替换表不会被当作缺证据。
            connection.execute("SELECT plan_id,digest,payload FROM plans LIMIT 0")
            connection.execute(
                "SELECT receipt_id,digest,payload,source_name,source_digest,"
                "plan_id,round_number,received_at FROM receipts LIMIT 0"
            )
            connection.execute(
                "SELECT sequence,action,subject_id,recorded_at,reason "
                "FROM events LIMIT 0"
            )
            with connection:
                if writable:
                    connection.execute("BEGIN IMMEDIATE")
                yield connection
        except sqlite3.Error as error:
            raise LedgerError("ledger_untrusted") from error
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        action: str,
        subject: str,
        now: datetime,
        reason: str | None = None,
    ) -> None:
        if now.tzinfo is None:
            raise LedgerError("evidence_time_future")
        connection.execute(
            "INSERT INTO events(action,subject_id,recorded_at,reason) VALUES(?,?,?,?)",
            (action, subject, now.isoformat(), reason),
        )

    def approve_plan_source(self, source: Path, *, now: datetime) -> None:
        self._writer()
        data = self._read_source(source.absolute())
        try:
            plan = ApprovedPlan.model_validate_json(data)
        except ValidationError as error:
            raise LedgerError("receipt_invalid") from error
        if canonical_bytes(plan) != data:
            raise LedgerError("source_integrity")
        self.approve_plan(plan, now=now)

    def approve_plan(self, plan: ApprovedPlan, *, now: datetime) -> None:
        """所有者保护入口登记批准计划;不从回执自行批准计划。"""
        with self.connection(writable=True) as connection:
            row = connection.execute(
                "SELECT digest FROM plans WHERE plan_id=?", (plan.plan_id,)
            ).fetchone()
            digest = content_sha256(plan)
            if row is not None and row != (digest,):
                raise LedgerError("plan_conflict")
            if row is None:
                connection.execute(
                    "INSERT INTO plans VALUES(?,?,?)",
                    (plan.plan_id, digest, canonical_bytes(plan)),
                )
                self._event(connection, "plan_approved", plan.plan_id, now)

    def receive(self, source: Path, *, now: datetime) -> ReceiveResult:
        self._writer()
        try:
            data = self._read_source(source.absolute())
            try:
                receipt = EvidenceReceipt.model_validate_json(data)
            except ValidationError as error:
                raise LedgerError("receipt_invalid") from error
            if canonical_bytes(receipt) != data:
                raise LedgerError("source_integrity")
            digest = content_sha256(receipt)
            with self.connection(writable=True) as connection:
                existing = connection.execute(
                    "SELECT digest FROM receipts WHERE receipt_id=?",
                    (receipt.receipt_id,),
                ).fetchone()
                if existing is not None:
                    if existing != (digest,):
                        raise LedgerError("receipt_conflict")
                    self._verified_receipt(connection, receipt.receipt_id)
                    self._event(
                        connection, "receive_duplicate", receipt.receipt_id, now
                    )
                    return ReceiveResult(receipt.receipt_id, True)
                plan_row = connection.execute(
                    "SELECT payload FROM plans WHERE plan_id=?", (receipt.plan_id,)
                ).fetchone()
                if plan_row is None:
                    raise LedgerError("plan_missing")
                try:
                    plan = ApprovedPlan.model_validate_json(plan_row[0])
                    validate_against_plan(receipt, plan, now=now)
                except (ValueError, ValidationError) as error:
                    raise LedgerError("plan_mismatch") from error
                previous = connection.execute(
                    "SELECT payload FROM receipts WHERE plan_id=? "
                    "ORDER BY round_number",
                    (plan.plan_id,),
                ).fetchall()
                if receipt.round_number != len(previous) + 1:
                    raise LedgerError("plan_round_conflict")
                if any(
                    EvidenceReceipt.model_validate_json(row[0]).failure_history
                    for row in previous
                ):
                    raise LedgerError("plan_stopped")
                connection.execute(
                    "INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)",
                    (
                        receipt.receipt_id,
                        digest,
                        data,
                        source.name,
                        hashlib.sha256(data).hexdigest(),
                        plan.plan_id,
                        receipt.round_number,
                        now.isoformat(),
                    ),
                )
                self._event(connection, "received", receipt.receipt_id, now)
                return ReceiveResult(receipt.receipt_id, False)
        except LedgerError as error:
            # 拒绝也追加受控审计;账本本身不可信时绝不尝试修复或写入。
            if error.category not in {"ledger_untrusted", "ledger_schema_unsupported"}:
                with self.connection(writable=True) as connection:
                    self._event(
                        connection, "receive_rejected", "receipt", now, error.category
                    )
            raise

    def _verified_receipt(
        self, connection: sqlite3.Connection, receipt_id: str
    ) -> ReceivedEvidence:
        row = connection.execute(
            "SELECT digest,payload,source_name,source_digest,received_at "
            "FROM receipts WHERE receipt_id=?",
            (receipt_id,),
        ).fetchone()
        if row is None:
            raise LedgerError("receipt_missing")
        try:
            receipt = EvidenceReceipt.model_validate_json(row[1])
            source = self._read_source(self.root / "inbox" / row[2])
            if (
                content_sha256(receipt) != row[0]
                or receipt.receipt_id != receipt_id
                or hashlib.sha256(source).hexdigest() != row[3]
                or source != row[1]
            ):
                raise LedgerError("source_integrity")
            plan_row = connection.execute(
                "SELECT digest,payload FROM plans WHERE plan_id=?", (receipt.plan_id,)
            ).fetchone()
            if plan_row is None:
                raise LedgerError("ledger_untrusted")
            plan = ApprovedPlan.model_validate_json(plan_row[1])
            if (
                content_sha256(plan) != plan_row[0]
                or receipt.plan_sha256 != plan_row[0]
            ):
                raise LedgerError("ledger_untrusted")
            return ReceivedEvidence(receipt_id, receipt, datetime.fromisoformat(row[4]))
        except (ValidationError, TypeError, ValueError) as error:
            if isinstance(error, LedgerError):
                raise
            raise LedgerError("ledger_untrusted") from error

    def show_plan(self, plan_id: str) -> ApprovedPlan:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT digest,payload FROM plans WHERE plan_id=?", (plan_id,)
            ).fetchone()
            if row is None:
                raise LedgerError("plan_missing")
            try:
                plan = ApprovedPlan.model_validate_json(row[1])
            except ValidationError as error:
                raise LedgerError("ledger_untrusted") from error
            if plan.plan_id != plan_id or content_sha256(plan) != row[0]:
                raise LedgerError("ledger_untrusted")
            return plan

    def show(self, receipt_id: str) -> ReceivedEvidence:
        with self.connection() as connection:
            return self._verified_receipt(connection, receipt_id)

    def list_received(self) -> tuple[ReceivedEvidence, ...]:
        with self.connection() as connection:
            ids = connection.execute(
                "SELECT receipt_id FROM receipts ORDER BY received_at,receipt_id"
            ).fetchall()
            return tuple(self._verified_receipt(connection, row[0]) for row in ids)

    def audit(self) -> tuple[AuditEvent, ...]:
        with self.connection() as connection:
            return tuple(
                AuditEvent(
                    row[0], row[1], row[2], datetime.fromisoformat(row[3]), row[4]
                )
                for row in connection.execute("SELECT * FROM events ORDER BY sequence")
            )
