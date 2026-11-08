"""#167 A5:仅内存、合成证据的生命周期原型;不接入产品或认证。"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Literal

Stage = Literal["boundary", "value", "read"]
Level = Literal["low", "high"]
Slot = tuple[Stage, Level]
STAGES: tuple[Stage, ...] = ("boundary", "value", "read")
LEVELS: tuple[Level, ...] = ("low", "high")
SLOTS: frozenset[Slot] = frozenset(
    (stage, level) for stage in STAGES for level in LEVELS
)
CHECKS = frozenset(
    {
        "cwd_ancestors",
        "file_isolation",
        "host_egress_dns_ipv6",
        "core_privacy",
        "rpc_identity_parameters",
        "request_refresh_counts",
        "session_write_history",
        "attempt_terminal_files",
        "attempt_directory_deleted",
        "interrupt_timeout_provider_error",
    }
)


class Rejected(ValueError):
    """只含受控原因,不含原始回执内容。"""


@dataclass(frozen=True)
class Binding:
    supply: str
    install_tree: str
    node_toolchain: str
    pi_version: str
    platform: str
    host: str
    cwd_ancestors: str
    endpoint_policy: str
    launch_policy: str
    isolation_service: str
    observer: str
    config_bundle: str
    slot_config: str
    proxy_policy: str
    core_policy: str
    provider: str
    model: str
    protocol: str
    sampling: str
    auth_mode: str
    temperature: None
    top_p: None
    stage: Stage
    level: Level

    @property
    def slot(self) -> Slot:
        return self.stage, self.level

    def validate(self) -> None:
        if not all(
            type(value) is str and value
            for key, value in asdict(self).items()
            if key not in {"temperature", "top_p"}
        ):
            raise Rejected("binding_incomplete")
        if self.slot not in SLOTS:
            raise Rejected("slot_unsupported")
        if (
            self.pi_version != "1.4.0"
            or self.temperature is not None
            or self.top_p is not None
            or self.provider != "openai"
            or self.model != "gpt-6.1-sol"
            or self.protocol != "prompt_only"
            or self.sampling != "provider_default"
            or self.auth_mode != "chatgpt_subscription"
        ):
            raise Rejected("model_tuple_unsupported")

    def site(self) -> dict[str, str | None]:
        return {
            key: value
            for key, value in asdict(self).items()
            if key not in {"stage", "level", "slot_config"}
        }


@dataclass(frozen=True)
class Receipt:
    collector: str
    plan: str
    run: str
    binding: Binding
    completed: datetime
    passed_checks: frozenset[str]

    def payload(self) -> bytes:
        data = asdict(self)
        data["completed"] = self.completed.isoformat()
        data["passed_checks"] = sorted(self.passed_checks)
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class Envelope:
    receipt: Receipt
    signature: str


def synthetic_collect(receipt: Receipt, key: bytes) -> Envelope:
    """测试采集器签合成回执。签名仅演示完整性;不证明观察事实。"""
    signature = hmac.new(key, receipt.payload(), hashlib.sha256).hexdigest()
    return Envelope(receipt, signature)


def aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Rejected("clock_naive")


class Receiver:
    """可信配置、合成 collector 与显式激活边界的状态模型。无磁盘写入。"""

    def __init__(self, collectors: dict[str, bytes], approved_plan: str) -> None:
        self._collectors = dict(collectors)
        self._plan = approved_plan
        self._accepted: dict[str, Receipt] = {}
        self._active: set[str] = set()
        self._site: dict[str, str | None] | None = None
        self._invalid_after: dict[Slot, datetime] = {}

    def receive(self, envelope: Envelope, now: datetime) -> str:
        aware(now)
        if type(envelope) is not Envelope:
            raise Rejected("envelope_untrusted")
        receipt = envelope.receipt
        if type(receipt) is not Receipt:
            raise Rejected("receipt_invalid")
        key = self._collectors.get(receipt.collector)
        if key is None:
            raise Rejected("collector_untrusted")
        expected = synthetic_collect(receipt, key).signature
        if not hmac.compare_digest(expected, envelope.signature):
            raise Rejected("integrity_invalid")
        receipt.binding.validate()
        aware(receipt.completed)
        if receipt.plan != self._plan or not receipt.run:
            raise Rejected("plan_unapproved")
        if receipt.passed_checks != CHECKS:
            raise Rejected("coverage_incomplete")
        if receipt.completed > now:
            raise Rejected("completion_in_future")
        if now >= receipt.completed + timedelta(days=30):
            raise Rejected("evidence_expired")
        cutoff = self._invalid_after.get(receipt.binding.slot)
        if cutoff is not None and receipt.completed <= cutoff:
            raise Rejected("revalidation_required")
        identity = hashlib.sha256(receipt.payload()).hexdigest()
        self._accepted[identity] = receipt
        return identity

    def activate(
        self, identities: frozenset[str], *, owner_action: str | None, now: datetime
    ) -> None:
        aware(now)
        # 实际产品须由独立本地所有者通道验证操作者,不能信任调用参数。
        if owner_action != "synthetic-owner-approve":
            raise Rejected("owner_activation_required")
        if not identities or not identities <= self._accepted.keys():
            raise Rejected("receipt_unknown")
        receipts = [self._accepted[identity] for identity in identities]
        if (
            self._site != receipts[0].binding.site()
            and {r.binding.slot for r in receipts} != SLOTS
        ):
            raise Rejected("initial_coverage_incomplete")
        if any(r.binding.site() != receipts[0].binding.site() for r in receipts):
            raise Rejected("site_mixed")
        for receipt in receipts:
            self._valid(receipt, now)
        if self._site != receipts[0].binding.site():
            self._active.clear()
        self._site = receipts[0].binding.site()
        self._active.update(identities)

    def _valid(self, receipt: Receipt, now: datetime) -> None:
        if now < receipt.completed:
            raise Rejected("clock_before_completion")
        if now >= receipt.completed + timedelta(days=30):
            raise Rejected("evidence_expired")
        cutoff = self._invalid_after.get(receipt.binding.slot)
        if cutoff is not None and receipt.completed <= cutoff:
            raise Rejected("evidence_revoked")

    def admit(
        self,
        identity: str,
        *,
        current: Binding,
        current_checks: frozenset[str],
        now: datetime,
    ) -> None:
        aware(now)
        current.validate()
        if identity not in self._active:
            raise Rejected("evidence_not_active")
        receipt = self._accepted[identity]
        self._valid(receipt, now)
        if current != receipt.binding:
            self.invalidate(affected=None, observed=now)
            raise Rejected("binding_drift")
        if current_checks != CHECKS:
            self.invalidate(affected=None, observed=now)
            raise Rejected("current_conditions_failed")

    def invalidate(
        self, *, affected: frozenset[Slot] | None, observed: datetime
    ) -> frozenset[Slot]:
        """失败或漂移复用此路径;None 表示影响未知,扩大到全部六槽。"""
        aware(observed)
        slots = SLOTS if affected is None else affected
        if not slots or not slots <= SLOTS:
            raise Rejected("impact_invalid")
        for slot in slots:
            previous = self._invalid_after.get(slot)
            if previous is None or observed > previous:
                self._invalid_after[slot] = observed
        return slots
