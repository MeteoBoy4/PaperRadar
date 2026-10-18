"""库级跨供给的纯保留规则;scope 输入仅来自调用方已验证事实。"""

from datetime import datetime
from typing import Literal

from paper_radar.pi_supply.cleanup_models import ProtectionReason
from paper_radar.pi_supply.models import Activation, RetentionProtection, SupplyRecord

_SCOPE_REASONS: tuple[tuple[str, ProtectionReason], ...] = (
    ("install_check", "latest_install_check"),
    ("rpc_compatibility", "latest_rpc_compatibility"),
)


def _retention_facts(
    records: tuple[SupplyRecord, ...],
    history: tuple[Activation, ...],
) -> tuple[tuple[str, ...], dict[str, str]]:
    retained = tuple(dict.fromkeys(event.install_id for event in reversed(history)))[:4]
    latest: dict[str, tuple[datetime, int, str]] = {}
    for record in records:
        for instance in record.installs:
            for check in instance.checks:
                if check.passed:
                    candidate = (
                        datetime.fromisoformat(check.created_at),
                        check.check_id,
                        instance.install_id,
                    )
                    if check.scope not in latest or candidate > latest[check.scope]:
                        latest[check.scope] = candidate
    return retained, {scope: candidate[2] for scope, candidate in latest.items()}


def retention_protection(
    records: tuple[SupplyRecord, ...], history: tuple[Activation, ...]
) -> RetentionProtection:
    """当前及最近三个不同旧实例,叠加各已知 scope 最近通过对象。"""
    retained, latest = _retention_facts(records, history)
    acceptance = tuple(
        dict.fromkeys(latest[scope] for scope, _ in _SCOPE_REASONS if scope in latest)
    )
    return RetentionProtection(retained, acceptance)


def protection_reasons(
    records: tuple[SupplyRecord, ...],
    history: tuple[Activation, ...],
    observations: dict[str, Literal["idle", "in_flight", "unknown"]],
) -> dict[str, tuple[ProtectionReason, ...]]:
    retained, latest = _retention_facts(records, history)
    result = {}
    for record in records:
        for instance in record.installs:
            reasons: list[ProtectionReason] = []
            identity = instance.install_id
            if identity in retained:
                reasons.append(
                    "current"
                    if history and identity == history[-1].install_id
                    else "recent_activation"
                )
            for scope, reason in _SCOPE_REASONS:
                if latest.get(scope) == identity:
                    reasons.append(reason)
            observation = observations.get(identity)
            if observation == "in_flight":
                reasons.append("in_flight")
            elif observation == "unknown":
                reasons.append("protection_unknown")
            result[identity] = tuple(reasons)
    return result
