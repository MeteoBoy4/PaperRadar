"""库级跨供给的纯保留规则;scope 输入仅来自调用方已验证事实。"""

from datetime import datetime
from typing import Literal

from paper_radar.pi_supply.cleanup_models import ProtectionReason
from paper_radar.pi_supply.models import Activation, SupplyRecord


def protection_reasons(
    records: tuple[SupplyRecord, ...],
    history: tuple[Activation, ...],
    observations: dict[str, Literal["idle", "in_flight", "unknown"]],
) -> dict[str, tuple[ProtectionReason, ...]]:
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
            scope_reasons: tuple[tuple[str, ProtectionReason], ...] = (
                ("install_check", "latest_install_check"),
                ("rpc_compatibility", "latest_rpc_compatibility"),
            )
            for scope, reason in scope_reasons:
                if scope in latest and latest[scope][2] == identity:
                    reasons.append(reason)
            observation = observations.get(identity)
            if observation == "in_flight":
                reasons.append("in_flight")
            elif observation == "unknown":
                reasons.append("protection_unknown")
            result[identity] = tuple(reasons)
    return result
