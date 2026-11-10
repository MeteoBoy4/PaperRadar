"""采集预占拒绝的封闭控制流;RPC 不把授权拒绝改写成协议错误。"""

from typing import Literal

CollectionReason = Literal[
    "resource_unavailable",
    "identity_mismatch",
    "isolation_failed",
    "permission_failed",
    "source_untrusted",
    "ledger_untrusted",
    "interrupted",
    "collector_failed",
    "protocol_failed",
]


class DispatchDenied(Exception):
    def __init__(self, reason: CollectionReason) -> None:
        self.reason = reason
        super().__init__(reason)
