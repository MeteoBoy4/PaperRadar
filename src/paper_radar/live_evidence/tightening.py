"""封印 NOPASSWD helper 的有限入口;不能接收、激活、恢复或延长资格。"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.lifecycle import (
    EvidenceLifecycle,
    use_for_id,
    use_id_for,
)
from paper_radar.live_evidence.types import BindingComponent, Capability


def tightening_main(arguments: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    try:
        # 先验证参数再打开固定账本;没有自由路径、SQL、时间或 action 扩展。
        if args == ["tick"]:
            EvidenceLifecycle(EvidenceLedger()).tick(now=datetime.now(UTC))
            return 0
        if len(args) != 5 or args[0] not in {"revoke", "mark"}:
            return 2
        action, receipt_id, use_id, raw_components, raw_failures = args
        if not re.fullmatch(r"[0-9a-f]{16}", receipt_id):
            return 2
        selected_use = use_id_for(use_for_id(use_id))
        components = (
            None
            if raw_components == "unknown"
            else frozenset(
                BindingComponent(value) for value in raw_components.split(",") if value
            )
        )
        failures = frozenset(
            Capability(value) for value in raw_failures.split(",") if value
        )
        EvidenceLifecycle(EvidenceLedger()).tighten(
            receipt_id,
            selected_use,
            now=datetime.now(UTC),
            components=components,
            failed_capabilities=failures,
            pending=action == "mark",
        )
        return 0
    except (LedgerError, ValueError):
        return 2


if __name__ == "__main__":
    raise SystemExit(tightening_main())
