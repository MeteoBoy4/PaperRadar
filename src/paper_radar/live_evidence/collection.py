"""root 侧 Live 采集事实状态机;追加、重放与逐外部操作原子预占。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import uuid
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError

from paper_radar.live_evidence.ledger_errors import LedgerError

if TYPE_CHECKING:
    from paper_radar.live_evidence.ledger import EvidenceLedger
from paper_radar.live_evidence.receipt import (
    Digest,
    Identifier,
    WireModel,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.receipt_v2 import (
    DOMAIN_ID,
    SAFETY_REASONS,
    ApprovedPlanV2,
    EvidenceReceiptV2,
    validate_v2_plan,
)
from paper_radar.live_evidence.types import BindingComponent

Operation = Literal["auth", "model", "network"]
_ZERO = "0" * 64
_SCHEMA = """CREATE TABLE collection_facts(
 sequence INTEGER PRIMARY KEY, previous_digest TEXT NOT NULL,
 digest TEXT UNIQUE NOT NULL, payload BLOB NOT NULL)"""


def _bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


@dataclass(frozen=True)
class CollectionRound:
    round_id: str
    plan_id: str
    round_number: int
    case_ids: tuple[str, ...]
    prior_receipts: tuple[str, ...]
    history_sha256: str
    started_at: datetime
    binding: dict[BindingComponent, str]


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    round_id: str
    case_id: str
    operation: Operation


class _InitializeFact(WireModel):
    action: Literal["initialize"]
    domain_id: Literal["live-177"]


class _StartFact(WireModel):
    action: Literal["start"]
    round_id: Identifier
    plan_id: Identifier
    plan_sha256: Digest
    round_number: int = Field(ge=1, le=20, strict=True)
    case_ids: tuple[Identifier, ...]
    prior_receipts: tuple[Digest, ...]
    history_sha256: Digest
    started_at: datetime
    binding: dict[BindingComponent, Digest]


class _ReservationFact(WireModel):
    action: Literal["reserve"]
    reservation_id: Identifier
    round_id: Identifier
    case_id: Identifier
    operation: Operation


class _CompleteFact(WireModel):
    action: Literal["complete"]
    receipt: EvidenceReceiptV2


class _ControlFact(WireModel):
    action: Literal["interrupt", "cancel"]
    round_id: Identifier


_Fact = _InitializeFact | _StartFact | _ReservationFact | _CompleteFact | _ControlFact
_FACT_READER: TypeAdapter[_Fact] = TypeAdapter(
    Annotated[_Fact, Field(discriminator="action")]
)


@dataclass(frozen=True)
class CollectionStatus:
    domain_id: str
    auth_used: int
    independent_network_used: int
    network_used: int
    network_remaining: int
    model_used: int
    model_remaining: int
    failure_chains: tuple[tuple[str, str, int], ...]
    failed_rounds: int
    stopped: bool
    circuit_open: bool
    stop_reason: str | None
    next_action: str
    next_case: str | None
    history_sha256: str


@dataclass
class _State:
    digest: str = _ZERO
    initialized: bool = False
    rounds: dict[str, CollectionRound] = field(default_factory=dict)
    completed: dict[str, EvidenceReceiptV2] = field(default_factory=dict)
    closed: set[str] = field(default_factory=set)
    reservations: dict[str, Reservation] = field(default_factory=dict)
    passed: dict[str, tuple[str, dict[BindingComponent, str]]] = field(
        default_factory=dict
    )
    chains: dict[str, tuple[str, int]] = field(default_factory=dict)
    failed_rounds: int = 0
    stop_reason: str | None = None


class ProtectedCollection:
    """只供封印 root 采集器使用;产品 uid 没有预占或结果写入通道。"""

    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    def initialize(self, *, now: datetime) -> None:
        """显式所有者 cutover;既存谱系只核验,绝不清空或补造。"""
        self.ledger._writer()
        self.ledger._protected(self.ledger.root)
        descriptor = os.open(
            self.ledger.root / "collection.lock",
            os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW,
            0o644,
        )
        os.close(descriptor)
        with self._connection(writable=True) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()
            if version == (1,):
                # 已有版本1账本允许增量迁入;旧原始回执和停止语义不改写。
                if connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='collection_facts'"
                ).fetchone():
                    raise LedgerError("ledger_untrusted")
                if connection.execute(
                    "SELECT 1 FROM events WHERE action LIKE 'collection_%' "
                    "OR action LIKE 'history_collection_%' LIMIT 1"
                ).fetchone():
                    raise LedgerError("ledger_untrusted")
                connection.execute(_SCHEMA)
                connection.execute("PRAGMA user_version=2")
                state = _State()
                self._append(
                    connection,
                    state,
                    {"action": "initialize", "domain_id": DOMAIN_ID},
                    now,
                )
            else:
                self._replay(connection)

    @contextmanager
    def _connection(self, *, writable: bool = False) -> Iterator[sqlite3.Connection]:
        if writable:
            self.ledger._writer()
        lock_path = self.ledger.root / "collection.lock"
        self.ledger._protected(lock_path)
        descriptor = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise LedgerError("ledger_untrusted")
            fcntl.flock(descriptor, fcntl.LOCK_EX if writable else fcntl.LOCK_SH)
            with self.ledger.connection(writable=writable) as connection:
                yield connection
        finally:
            os.close(descriptor)

    def approve_plan(self, plan: ApprovedPlanV2, *, now: datetime) -> None:
        self.ledger.approve_plan(plan, now=now)

    def _plan(self, connection: sqlite3.Connection, plan_id: str) -> ApprovedPlanV2:
        row = connection.execute(
            "SELECT digest,payload FROM plans WHERE plan_id=?", (plan_id,)
        ).fetchone()
        if row is None:
            raise LedgerError("plan_missing")
        try:
            result = ApprovedPlanV2.model_validate_json(row[1])
        except ValidationError as error:
            raise LedgerError("plan_mismatch") from error
        if content_sha256(result) != row[0] or result.plan_id != plan_id:
            raise LedgerError("ledger_untrusted")
        return result

    def _append(
        self,
        connection: sqlite3.Connection,
        state: _State,
        fact: Mapping[str, object],
        now: datetime,
    ) -> None:
        raw = _bytes(fact)
        digest = hashlib.sha256(state.digest.encode() + raw).hexdigest()
        connection.execute(
            "INSERT INTO collection_facts(previous_digest,digest,payload) "
            "VALUES(?,?,?)",
            (state.digest, digest, raw),
        )
        self.ledger._event(
            connection, "collection_" + str(fact["action"]), DOMAIN_ID, now, digest
        )

    def _replay(self, connection: sqlite3.Connection) -> _State:
        if connection.execute("PRAGMA user_version").fetchone() != (2,):
            raise LedgerError("ledger_schema_unsupported")
        expected = [
            ("sequence", "INTEGER", 0, 1),
            ("previous_digest", "TEXT", 1, 0),
            ("digest", "TEXT", 1, 0),
            ("payload", "BLOB", 1, 0),
        ]
        actual = [
            (row[1], row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(collection_facts)")
        ]
        if actual != expected:
            raise LedgerError("ledger_untrusted")
        state = _State()
        try:
            facts = connection.execute(
                "SELECT * FROM collection_facts ORDER BY sequence"
            ).fetchall()
            audit = connection.execute(
                "SELECT action,reason FROM events "
                "WHERE action LIKE 'collection_%' ORDER BY sequence"
            ).fetchall()
            if len(facts) != len(audit):
                raise LedgerError("ledger_untrusted")
            for index, (sequence, previous, digest, raw) in enumerate(facts):
                fact = json.loads(raw)
                if (
                    sequence != index + 1
                    or audit[index] != ("collection_" + fact["action"], digest)
                    or previous != state.digest
                    or _bytes(fact) != raw
                    or hashlib.sha256(previous.encode() + raw).hexdigest() != digest
                ):
                    raise LedgerError("ledger_untrusted")
                self._apply(connection, state, fact)
                state.digest = digest
        except (ValueError, KeyError, TypeError) as error:
            if isinstance(error, LedgerError):
                raise
            raise LedgerError("ledger_untrusted") from error
        if not state.initialized:
            raise LedgerError("ledger_untrusted")
        return state

    def _apply(
        self, connection: sqlite3.Connection, state: _State, fact: Mapping[str, object]
    ) -> None:
        parsed = _FACT_READER.validate_python(fact)
        if isinstance(parsed, _InitializeFact):
            if state.initialized:
                raise LedgerError("ledger_untrusted")
            state.initialized = True
        elif isinstance(parsed, _StartFact):
            run = CollectionRound(
                parsed.round_id,
                parsed.plan_id,
                parsed.round_number,
                parsed.case_ids,
                parsed.prior_receipts,
                parsed.history_sha256,
                parsed.started_at,
                parsed.binding,
            )
            plan = self._plan(connection, run.plan_id)
            self._admit(state, plan, run.started_at)
            cases, prior = self._continuation(state, plan, run.binding)
            if (
                run.round_id in state.rounds
                or run.case_ids != cases
                or not cases
                or run.prior_receipts != prior
                or run.history_sha256 != state.digest
                or parsed.plan_sha256 != content_sha256(plan)
                or run.round_number != self._round_number(state, plan.plan_id)
            ):
                raise LedgerError("ledger_untrusted")
            state.rounds[run.round_id] = run
        elif isinstance(parsed, _ReservationFact):
            item = Reservation(
                parsed.reservation_id, parsed.round_id, parsed.case_id, parsed.operation
            )
            self._check_reservation(connection, state, item)
            state.reservations[item.reservation_id] = item
        elif isinstance(parsed, _CompleteFact):
            receipt = parsed.receipt
            self._check_receipt(connection, state, receipt, now=receipt.completed_at)
            state.completed[receipt.round_id] = receipt
            state.closed.add(receipt.round_id)
            digest = content_sha256(receipt)
            for case in receipt.cases:
                if case.outcome == "passed":
                    state.passed[case.case_id] = digest, receipt.binding
                    state.chains.pop(case.case_id, None)
            if receipt.failure_history:
                failure = receipt.failure_history[0]
                self._failed(state, failure.case_id, failure.reason)
        else:
            identifier = parsed.round_id
            if identifier not in state.rounds or identifier in state.closed:
                raise LedgerError("ledger_untrusted")
            if parsed.action == "cancel" and any(
                item.round_id == identifier for item in state.reservations.values()
            ):
                raise LedgerError("plan_round_conflict")
            state.closed.add(identifier)
            if parsed.action == "interrupt":
                self._failed(state, state.rounds[identifier].case_ids[0], "interrupted")

    @staticmethod
    def _failed(state: _State, case_id: str, reason: str) -> None:
        old_reason, count = state.chains.get(case_id, ("", 0))
        state.chains[case_id] = reason, count + 1 if old_reason == reason else 1
        state.failed_rounds += 1
        if reason in SAFETY_REASONS:
            state.stop_reason = reason
        elif state.chains[case_id][1] >= 3:
            state.stop_reason = "failure_class_stopped"
        elif state.failed_rounds >= 6:
            state.stop_reason = "global_circuit_open"

    @staticmethod
    def _round_number(state: _State, plan_id: str) -> int:
        return 1 + sum(run.plan_id == plan_id for run in state.rounds.values())

    @staticmethod
    def _continuation(
        state: _State, plan: ApprovedPlanV2, binding: dict[BindingComponent, str]
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if set(binding) != set(BindingComponent) or any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            for value in binding.values()
        ):
            raise LedgerError("plan_mismatch")
        remaining: list[str] = []
        prior: list[str] = []
        for case_id in plan.cases:
            passed = state.passed.get(case_id)
            if passed is None or passed[1] != binding:
                remaining.append(case_id)
            elif passed[0] not in prior:
                prior.append(passed[0])
        return tuple(remaining), tuple(prior)

    @staticmethod
    def _admit(state: _State, plan: ApprovedPlanV2, now: datetime) -> None:
        if state.stop_reason is not None:
            raise LedgerError("plan_stopped")
        if now.tzinfo is None or not plan.starts_at <= now <= plan.ends_at:
            raise LedgerError("plan_mismatch")
        if any(key not in state.closed for key in state.rounds):
            raise LedgerError("plan_round_conflict")
        if ProtectedCollection._round_number(state, plan.plan_id) > plan.max_rounds:
            raise LedgerError("plan_budget_exceeded")
        totals = Counter(item.operation for item in state.reservations.values())
        if (plan.max_model_calls > 0 and totals["model"] >= 40) or (
            plan.max_auth_calls + plan.max_network_requests > 0
            and totals["auth"] + totals["network"] >= 40
        ):
            raise LedgerError("plan_budget_exceeded")

    def start_round(
        self, plan_id: str, *, binding: dict[BindingComponent, str], now: datetime
    ) -> CollectionRound:
        with self._connection(writable=True) as connection:
            state = self._replay(connection)
            plan = self._plan(connection, plan_id)
            self._admit(state, plan, now)
            cases, prior = self._continuation(state, plan, binding)
            if not cases:
                raise LedgerError("plan_complete")
            identifier = "round-" + uuid.uuid4().hex
            run = CollectionRound(
                identifier,
                plan_id,
                self._round_number(state, plan_id),
                cases,
                prior,
                state.digest,
                now,
                dict(binding),
            )
            fact = {
                "action": "start",
                "round_id": identifier,
                "plan_id": plan_id,
                "round_number": run.round_number,
                "plan_sha256": content_sha256(plan),
                "case_ids": cases,
                "prior_receipts": prior,
                "history_sha256": state.digest,
                "started_at": now.isoformat(),
                "binding": binding,
            }
            self._append(connection, state, fact, now)
            return run

    def _check_reservation(
        self, connection: sqlite3.Connection, state: _State, item: Reservation
    ) -> None:
        run = state.rounds.get(item.round_id)
        if (
            run is None
            or item.round_id in state.closed
            or state.stop_reason
            or item.reservation_id in state.reservations
            or item.operation not in {"auth", "model", "network"}
            or item.case_id not in run.case_ids
        ):
            raise LedgerError("reservation_invalid")
        plan = self._plan(connection, run.plan_id)
        totals = Counter(value.operation for value in state.reservations.values())
        if (item.operation == "model" and totals["model"] >= 40) or (
            item.operation != "model" and totals["auth"] + totals["network"] >= 40
        ):
            raise LedgerError("plan_budget_exceeded")
        plan_totals = Counter(
            value.operation
            for value in state.reservations.values()
            if state.rounds[value.round_id].plan_id == run.plan_id
        )
        limit = {
            "auth": plan.max_auth_calls,
            "model": plan.max_model_calls,
            "network": plan.max_network_requests,
        }[item.operation]
        if plan_totals[item.operation] >= limit:
            raise LedgerError("plan_budget_exceeded")

    def reserve(
        self, round_id: str, case_id: str, operation: Operation, *, now: datetime
    ) -> Reservation:
        with self._connection(writable=True) as connection:
            state = self._replay(connection)
            item = Reservation("op-" + uuid.uuid4().hex, round_id, case_id, operation)
            self._check_reservation(connection, state, item)
            run = state.rounds[round_id]
            plan = self._plan(connection, run.plan_id)
            if now.tzinfo is None or not plan.starts_at <= now <= plan.ends_at:
                raise LedgerError("plan_mismatch")
            self._append(
                connection,
                state,
                {
                    "action": "reserve",
                    "reservation_id": item.reservation_id,
                    "round_id": round_id,
                    "case_id": case_id,
                    "operation": operation,
                },
                now,
            )
            return item

    def _check_receipt(
        self,
        connection: sqlite3.Connection,
        state: _State,
        receipt: EvidenceReceiptV2,
        *,
        now: datetime,
    ) -> None:
        run = state.rounds.get(receipt.round_id)
        if run is None or receipt.round_id in state.closed:
            raise LedgerError("plan_round_conflict")
        plan = self._plan(connection, run.plan_id)
        try:
            validate_v2_plan(receipt, plan, now=now)
        except ValueError as error:
            raise LedgerError("plan_mismatch") from error
        cases = tuple(case.case_id for case in receipt.cases)
        if (
            receipt.plan_id != run.plan_id
            or receipt.round_number != run.round_number
            or receipt.started_at != run.started_at
            or receipt.binding != run.binding
            or receipt.history_sha256 != run.history_sha256
            or receipt.prior_receipts != run.prior_receipts
            or cases != run.case_ids[: len(cases)]
            or (len(cases) != len(run.case_ids) and not receipt.failure_history)
        ):
            raise LedgerError("collection_history_mismatch")
        reserved = tuple(
            item
            for item in state.reservations.values()
            if item.round_id == run.round_id
        )
        if receipt.reservation_ids != tuple(item.reservation_id for item in reserved):
            raise LedgerError("reservation_invalid")
        for case in receipt.cases:
            counts = Counter(
                item.operation for item in reserved if item.case_id == case.case_id
            )
            if (case.auth_calls, case.model_calls, case.network_requests) != (
                counts["auth"],
                counts["model"],
                counts["network"],
            ):
                raise LedgerError("reservation_invalid")
        if any(item.case_id not in cases for item in reserved):
            raise LedgerError("reservation_invalid")

    def complete_round(self, receipt: EvidenceReceiptV2, *, now: datetime) -> str:
        with self._connection(writable=True) as connection:
            state = self._replay(connection)
            self._check_receipt(connection, state, receipt, now=now)
            self._append(
                connection,
                state,
                {"action": "complete", "receipt": receipt.model_dump(mode="json")},
                now,
            )
            return content_sha256(receipt)

    def verify_completed(
        self, connection: sqlite3.Connection, receipt: EvidenceReceiptV2
    ) -> None:
        """新版接收权威核对受保护采集事实与跨轮来源;不信回执自报。"""
        state = self._replay(connection)
        original = state.completed.get(receipt.round_id)
        if original is None or canonical_bytes(original) != canonical_bytes(receipt):
            raise LedgerError("collection_history_mismatch")
        for digest in receipt.prior_receipts:
            row = connection.execute(
                "SELECT receipt_id FROM receipts WHERE digest=?", (digest,)
            ).fetchone()
            if row is None:
                raise LedgerError("collection_history_mismatch")
            self.ledger._verified_receipt(connection, row[0])

    def completed_case(
        self, case_id: str, *, binding: dict[BindingComponent, str]
    ) -> EvidenceReceiptV2 | None:
        """只读重放已完成采集事实;精确绑定,保留原时间,无需 receive。"""
        with self._connection() as connection:
            state = self._replay(connection)
            passed = state.passed.get(case_id)
            if passed is None or passed[1] != binding:
                return None
            for receipt in state.completed.values():
                if content_sha256(receipt) == passed[0]:
                    return receipt
            raise LedgerError("ledger_untrusted")

    def completed_receipts(self) -> tuple[EvidenceReceiptV2, ...]:
        """受保护完成历史;不含未完成轮或调用方提供的 inbox 候选。"""
        with self._connection() as connection:
            return tuple(self._replay(connection).completed.values())

    def cancel_round(self, round_id: str, *, now: datetime) -> None:
        with self._connection(writable=True) as connection:
            state = self._replay(connection)
            fact = {"action": "cancel", "round_id": round_id}
            self._apply(connection, state, fact)
            self._append(connection, state, fact, now)

    def recover_interrupted(self, *, now: datetime) -> None:
        """调用者必须先持有封印 collector 独占锁;中断永不伪装成普通重试。"""
        with self._connection(writable=True) as connection:
            state = self._replay(connection)
            for identifier in state.rounds.keys() - state.closed:
                fact = {"action": "interrupt", "round_id": identifier}
                self._append(connection, state, fact, now)
                self._apply(connection, state, fact)

    def status(self, plan_id: str, *, now: datetime) -> CollectionStatus:
        with self._connection() as connection:
            state = self._replay(connection)
            plan = self._plan(connection, plan_id)
            totals = Counter(item.operation for item in state.reservations.values())
            remaining = tuple(case for case in plan.cases if case not in state.passed)
            action = "resume" if remaining else "complete"
            if state.stop_reason:
                action = "owner_review_stop"
            elif any(key not in state.closed for key in state.rounds):
                action = "recover_interrupted"
            elif now.tzinfo is None or not plan.starts_at <= now <= plan.ends_at:
                action = "approve_current_window"
            elif remaining and (
                (
                    plan.max_auth_calls + plan.max_network_requests > 0
                    and totals["auth"] + totals["network"] >= 40
                )
                or (plan.max_model_calls > 0 and totals["model"] >= 40)
                or self._round_number(state, plan_id) > plan.max_rounds
            ):
                action = "budget_exhausted"
            return CollectionStatus(
                DOMAIN_ID,
                totals["auth"],
                totals["network"],
                totals["auth"] + totals["network"],
                40 - totals["auth"] - totals["network"],
                totals["model"],
                40 - totals["model"],
                tuple(
                    (case, reason, count)
                    for case, (reason, count) in sorted(state.chains.items())
                ),
                state.failed_rounds,
                state.stop_reason is not None,
                state.failed_rounds >= 6,
                state.stop_reason,
                action,
                remaining[0] if remaining else None,
                state.digest,
            )
