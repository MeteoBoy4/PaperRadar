"""受保护事件流上的证据激活、不可逆撤销与恢复屏障。"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from paper_radar.live_evidence.evaluator import evaluate_admission
from paper_radar.live_evidence.evidence import (
    CapabilityClaim,
    CapabilityEvidence,
    ExecutionBinding,
)
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.receipt import UseId, WireModel
from paper_radar.live_evidence.registry import INITIAL_REGISTRY
from paper_radar.live_evidence.time_policy import clock_reason
from paper_radar.live_evidence.types import (
    AdmissionUse,
    BindingComponent,
    Capability,
    Requirement,
)


class LifecyclePayload(WireModel):
    """schema1 events.reason 中新动作的封闭载荷;不改变既有事件意义。"""

    use_id: UseId
    registry_version: str
    capabilities: tuple[Capability, ...]
    cause: Literal["owner", "binding_drift", "capability_failed", "unknown_impact"]


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    evidence: tuple[CapabilityEvidence, ...]
    watermark: datetime | None
    pending_revocation: bool
    sources: tuple[tuple[AdmissionUse, Capability, str], ...]


@dataclass(frozen=True, slots=True)
class ActivationReview:
    receipt_id: str
    use_id: UseId
    binding: ExecutionBinding
    checked_components: frozenset[BindingComponent]
    reviewed_at: datetime
    eligible: tuple[Capability, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class ActivationResult:
    receipt_id: str
    capabilities: tuple[Capability, ...]
    duplicate: bool


def use_for_id(use_id: str) -> AdmissionUse:
    for entry in INITIAL_REGISTRY.uses:
        use = entry.use
        if f"{use.consumer.value}-{use.thinking_level.value}" == use_id:
            return use
    raise LedgerError("admission_use_undefined")


def use_id_for(use: AdmissionUse) -> UseId:
    for value in (
        "boundary-low",
        "boundary-high",
        "value-low",
        "value-high",
        "read-low",
        "read-high",
    ):
        if use_for_id(value) == use:
            # Literal 校验由同一个内部 wire model 完成。
            return LifecyclePayload.model_validate(
                {
                    "use_id": value,
                    "registry_version": INITIAL_REGISTRY.version,
                    "capabilities": [],
                    "cause": "owner",
                }
            ).use_id
    raise LedgerError("admission_use_undefined")


class EvidenceLifecycle:
    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    def snapshot(self, *, now: datetime) -> EvidenceSnapshot:
        with self.ledger.connection() as connection:
            watermark = self.ledger.watermark(connection)
            invalid = clock_reason(now, watermark)
            if invalid is not None:
                raise LedgerError.clock(invalid)
            events = connection.execute(
                "SELECT sequence,action,subject_id,reason FROM events ORDER BY sequence"
            ).fetchall()
            received = self.ledger.received_in(connection)
        restored = max(
            (row[0] for row in events if row[1] == "evidence_restored"), default=0
        )
        active: set[tuple[str, str, str, Capability]] = set()
        revoked: set[tuple[str, str, Capability]] = set()
        pending = False
        for sequence, action, subject, reason in events:
            if action not in {
                "evidence_activated",
                "evidence_revoked",
                "evidence_marked",
            }:
                continue
            try:
                payload = LifecyclePayload.model_validate_json(reason)
            except (ValidationError, TypeError) as error:
                raise LedgerError("ledger_untrusted") from error
            for capability in payload.capabilities:
                key = (subject, payload.use_id, capability)
                if action == "evidence_activated" and sequence > restored:
                    active.add(
                        (subject, payload.use_id, payload.registry_version, capability)
                    )
                elif action in {"evidence_revoked", "evidence_marked"}:
                    revoked.add(key)
            pending = pending or action == "evidence_marked"
        # 每格每能力只消费最新接收事实;失败/unknown 重验不回退到旧授予。
        indexed: dict[tuple[AdmissionUse, Capability], CapabilityEvidence] = {}
        sources: dict[tuple[AdmissionUse, Capability], str] = {}
        received_sequences = {
            subject: sequence
            for sequence, action, subject, _ in events
            if action == "received"
        }
        for _sequence, action, subject, reason in events:
            if action == "history_received":
                try:
                    original_sequence = json.loads(reason)["original_sequence"]
                    if type(original_sequence) is not int or original_sequence < 1:
                        raise ValueError("history_sequence_invalid")
                except (TypeError, ValueError, KeyError) as error:
                    raise LedgerError("ledger_untrusted") from error
                received_sequences.setdefault(subject, original_sequence)
        if any(record.receipt_id not in received_sequences for record in received):
            raise LedgerError("ledger_untrusted")
        for record in sorted(
            received,
            key=lambda record: (
                record.received_at,
                received_sequences[record.receipt_id],
            ),
        ):
            receipt = record.receipt
            binding = ExecutionBinding(tuple(receipt.binding.items()))
            for claim in receipt.claims:
                use = use_for_id(claim.use_id)
                sources[(use, claim.capability)] = record.receipt_id
                indexed[(use, claim.capability)] = CapabilityEvidence(
                    claim.capability,
                    use,
                    receipt.registry_version,
                    binding,
                    CapabilityClaim(
                        claim.status,
                        claim.basis,
                        claim.scope,
                        claim.verified_at,
                        claim.evidence_at,
                    ),
                    True,
                    (
                        record.receipt_id,
                        claim.use_id,
                        receipt.registry_version,
                        claim.capability,
                    )
                    in active,
                    (record.receipt_id, claim.use_id, claim.capability) in revoked,
                )
        return EvidenceSnapshot(
            tuple(indexed.values()),
            watermark,
            pending,
            tuple((use, cap, value) for (use, cap), value in sources.items()),
        )

    def review(
        self,
        receipt_id: str,
        use_id: UseId,
        *,
        binding: ExecutionBinding,
        checked_components: frozenset[BindingComponent],
        now: datetime,
    ) -> ActivationReview:
        use = use_for_id(use_id)
        record = self.ledger.show(receipt_id)
        snapshot = self.snapshot(now=now)
        sources = {(use, cap): identifier for use, cap, identifier in snapshot.sources}
        selected = tuple(
            item
            for item in snapshot.evidence
            if item.use == use and sources[(use, item.capability)] == receipt_id
        )
        # 仅为审阅暂时移除“尚未激活”维度;其余资格和原始时间仍全部判定。
        from dataclasses import replace

        decision = evaluate_admission(
            INITIAL_REGISTRY,
            use,
            tuple(replace(item, evidence_active=True) for item in selected),
            binding=binding,
            now=now,
            checked_components=checked_components,
            ledger_watermark=snapshot.watermark,
        )
        eligible = tuple(
            item.capability
            for item in decision.capabilities
            if item.requirement is Requirement.REQUIRED and item.qualified
        )
        lines = [
            record.receipt.model_dump_json(indent=2),
            f"receipt_id={receipt_id} use={use_id} "
            f"registry_version={INITIAL_REGISTRY.version}",
        ]
        for item in decision.capabilities:
            if item.claim is not None:
                reasons = ",".join(reason.token for reason in item.reasons) or "none"
                lines.append(
                    f"capability={item.capability.value} "
                    f"evidence={item.claim.status.value} "
                    f"verified_at={item.claim.verified_at} "
                    f"expires_at={item.expires_at} "
                    f"eligible={str(item.capability in eligible).lower()} "
                    f"reason={reasons}"
                )
        return ActivationReview(
            receipt_id,
            use_id,
            binding,
            checked_components,
            now,
            eligible,
            "\n".join(lines),
        )

    def activate(
        self,
        review: ActivationReview,
        *,
        confirmation: str,
        now: datetime,
    ) -> ActivationResult:
        self.ledger._writer()
        if confirmation != review.receipt_id:
            raise LedgerError("activation_confirmation_mismatch")
        invalid = clock_reason(now, review.reviewed_at)
        if invalid is not None:
            raise LedgerError.clock(invalid)
        if now - review.reviewed_at > timedelta(seconds=60):
            raise LedgerError("observation_stale")
        with self.ledger.connection(writable=True) as connection:
            current = self.review(
                review.receipt_id,
                review.use_id,
                binding=review.binding,
                checked_components=review.checked_components,
                now=now,
            )
            if not current.eligible:
                raise LedgerError("activation_empty")
            snapshot = self.snapshot(now=now)
            existing = {
                item.capability
                for item in snapshot.evidence
                if item.use == use_for_id(review.use_id)
                and item.evidence_active
                and not item.revoked
                and dict(item.binding.components) == dict(review.binding.components)
            }
            duplicate = set(current.eligible) <= existing
            if not duplicate:
                payload = LifecyclePayload(
                    use_id=review.use_id,
                    registry_version=INITIAL_REGISTRY.version,
                    capabilities=current.eligible,
                    cause="owner",
                )
                self.ledger._event(
                    connection,
                    "evidence_activated",
                    review.receipt_id,
                    now,
                    payload.model_dump_json(),
                )
            return ActivationResult(review.receipt_id, current.eligible, duplicate)

    def tighten(
        self,
        receipt_id: str,
        use_id: UseId,
        *,
        now: datetime,
        components: frozenset[BindingComponent] | None = None,
        failed_capabilities: frozenset[Capability] = frozenset(),
        pending: bool = False,
    ) -> tuple[Capability, ...]:
        """组件影响未知时撤销本格全部主张;空的已知变化不产生授予。"""
        with self.ledger.connection(writable=True) as connection:
            self.snapshot(now=now)
            record = self.ledger.show(receipt_id)
            rules = INITIAL_REGISTRY.requirements_for(use_for_id(use_id))
            claimed = {
                claim.capability
                for claim in record.receipt.claims
                if claim.use_id == use_id
            }
            affected = tuple(
                rule.capability
                for rule in rules
                if rule.capability in claimed
                and (
                    components is None
                    or rule.capability in failed_capabilities
                    or bool(rule.dependencies & components)
                )
            )
            payload = LifecyclePayload(
                use_id=use_id,
                registry_version=INITIAL_REGISTRY.version,
                capabilities=affected,
                cause="unknown_impact"
                if components is None
                else "capability_failed"
                if failed_capabilities
                else "binding_drift",
            )
            self.ledger._event(
                connection,
                "evidence_marked" if pending else "evidence_revoked",
                receipt_id,
                now,
                payload.model_dump_json(),
            )
            return affected

    def record_restore(self, *, now: datetime) -> None:
        """只能在特权恢复入口调用;追加屏障,历史及撤销保持。"""
        with self.ledger.connection(writable=True) as connection:
            self.ledger._event(connection, "evidence_restored", "ledger", now)

    def tick(self, *, now: datetime) -> None:
        with self.ledger.connection(writable=True) as connection:
            self.ledger._event(connection, "evidence_tick", "ledger", now)

    def backup(self, destination: Path) -> None:
        """特权离线快照;来源 inbox 必须随部署另行保留。"""
        self.ledger._writer()
        self.ledger._protected(destination.absolute().parent)
        try:
            fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            with (
                self.ledger.connection() as source,
                closing(sqlite3.connect(destination)) as target,
            ):
                source.backup(target)
        except (OSError, sqlite3.Error) as error:
            raise LedgerError("ledger_untrusted") from error

    def restore(self, source: Path, *, now: datetime) -> None:
        """只合并受保护历史,保留当前尾部收紧事件,并失效全部既有激活。"""
        self.ledger._writer()
        source = source.absolute()
        self.ledger._protected(source)
        info = source.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise LedgerError("ledger_untrusted")
        if any(
            os.path.lexists(str(source) + suffix)
            for suffix in ("-journal", "-wal", "-shm")
        ):
            raise LedgerError("ledger_untrusted")
        try:
            with closing(
                sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
            ) as historical:
                historical.execute("PRAGMA query_only=ON")
                if (
                    historical.execute("PRAGMA quick_check").fetchall() != [("ok",)]
                    or historical.execute("PRAGMA journal_mode").fetchone()
                    != ("delete",)
                    or historical.execute("PRAGMA user_version").fetchone() != (1,)
                ):
                    raise LedgerError("ledger_untrusted")
                old_watermark = self.ledger.watermark(historical)
                invalid = clock_reason(now, old_watermark)
                if invalid is not None:
                    raise LedgerError.clock(invalid)
                plans = historical.execute("SELECT * FROM plans").fetchall()
                receipts = historical.execute("SELECT * FROM receipts").fetchall()
                events = historical.execute(
                    "SELECT * FROM events ORDER BY sequence"
                ).fetchall()
            # 在任何修改前校验当前信任根和两个时间下限;不覆盖损坏的在线库。
            self.snapshot(now=now)
            with self.ledger.connection(writable=True) as connection:
                for table, rows, key in (
                    ("plans", plans, "plan_id"),
                    ("receipts", receipts, "receipt_id"),
                ):
                    for row in rows:
                        existing = connection.execute(
                            f"SELECT * FROM {table} WHERE {key}=?", (row[0],)
                        ).fetchone()
                        if existing is not None and existing != row:
                            raise LedgerError("ledger_untrusted")
                        if existing is None:
                            placeholders = ",".join("?" for _ in row)
                            connection.execute(
                                f"INSERT INTO {table} VALUES({placeholders})", row
                            )
                # 在同一事务内重新核验已恢复来源、摘要与计划,异常整体回滚。
                for row in receipts:
                    self.ledger._verified_receipt(connection, row[0])
                for sequence, action, subject, recorded_at, reason in events:
                    if action in {"evidence_revoked", "evidence_marked"}:
                        self.ledger._event(connection, action, subject, now, reason)
                    elif action in {"received", "history_received"}:
                        original_sequence = (
                            sequence
                            if action == "received"
                            else json.loads(reason)["original_sequence"]
                        )
                        self.ledger._event(
                            connection,
                            "history_received",
                            subject,
                            now,
                            json.dumps(
                                {
                                    "recorded_at": recorded_at,
                                    "original_sequence": original_sequence,
                                },
                                sort_keys=True,
                            ),
                        )
                    else:
                        self.ledger._event(
                            connection,
                            "history_" + action,
                            subject,
                            now,
                            json.dumps(
                                {"recorded_at": recorded_at, "reason": reason},
                                sort_keys=True,
                            ),
                        )
                self.ledger._event(connection, "evidence_restored", "ledger", now)
        except sqlite3.Error as error:
            raise LedgerError("ledger_untrusted") from error
