"""受保护准入账本与采集状态机共用的受控错误。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from paper_radar.live_evidence.reasons import ReasonCode

LedgerCategory = Literal[
    "ledger_untrusted",
    "clock_rollback",
    "evidence_time_invalid",
    "admission_use_undefined",
    "evidence_activation_confirmation_mismatch",
    "evidence_activation_empty",
    "observation_stale",
    "observation_invalid",
    "observation_changed",
    "pending_revocation_unavailable",
    "binding_observation_unavailable",
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
    "plan_complete",
    "reservation_invalid",
    "collection_history_mismatch",
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

    @classmethod
    def clock(cls, reason: ReasonCode) -> LedgerError:
        from paper_radar.live_evidence.reasons import ReasonCode

        if reason is ReasonCode.CLOCK_ROLLBACK:
            return cls("clock_rollback")
        if reason is ReasonCode.TIME_INVALID:
            return cls("evidence_time_invalid")
        if reason is ReasonCode.TIME_FUTURE:
            return cls("evidence_time_future")
        return cls("ledger_untrusted")
