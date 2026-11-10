"""准入账本所有者入口;help 不读取配置或账本。"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from paper_radar.live_evidence.ledger import EvidenceLedger

import typer

live_evidence_app = typer.Typer(
    name="live-evidence",
    add_completion=False,
    no_args_is_help=True,
    help="""管理独立准入账本中的分项证据。

当前用途：接收、审阅并显式证据激活，或撤销、只读查询脱敏摘要。
参数与选项：使用 show/receive/activate/revoke --help 查看明确选择。
副作用：show 只读打开账本；receive 仅经所有者 sudo 入口写入，不激活证据。
帮助纯本地，不打开账本，不联网、不认证、不调用模型。
自动配额：0 次模型调用；不修改业务 attempt 或预算。
输出去向：标准输出的脱敏摘要，失败写标准错误。
常见失败：账本或来源不可信时拒绝，请所有者检查封印部署与来源。
示例：paper-radar live-evidence show
""",
)


def _failure(category: str) -> None:
    typer.echo(
        f"准入证据拒绝 [{category}]；请所有者检查受保护账本、批准计划与回执来源。",
        err=True,
    )
    raise typer.Exit(2)


@live_evidence_app.command(
    help="""只读查询准入证据。

当前用途：显示已接收回执的短 ID、原分项状态与接收时间。
参数与选项：--receipt-id 选择回执，--plan-id 选择批准计划；省略时查询全部回执。
副作用：只读打开准入账本，不激活、不认证、不调用模型。
自动配额：0；输出去向：标准输出；常见失败：来源丢失或账本不可信时拒绝。
"""
)
def show(
    receipt_id: Annotated[str | None, typer.Option(help="回执的 16 位短 ID。")] = None,
    plan_id: Annotated[str | None, typer.Option(help="批准计划 ID。")] = None,
) -> None:
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError

    if receipt_id is not None and plan_id is not None:
        _failure("selection_conflict")
    try:
        ledger = EvidenceLedger()
        if plan_id is not None:
            selected_plan = ledger.show_plan(plan_id)
            typer.echo(selected_plan.model_dump_json())
            from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2

            if isinstance(selected_plan, ApprovedPlanV2):
                from paper_radar.live_evidence.collection import ProtectedCollection

                status = ProtectedCollection(ledger).status(plan_id, now=_now())
                typer.echo(
                    json.dumps(asdict(status), ensure_ascii=False, sort_keys=True)
                )
                actions = {
                    "resume": "可从未通过案例继续；仍须核验窗口、绑定与准入。",
                    "complete": "本计划案例已通过；请所有者审阅、接收并显式激活分项。",
                    "owner_review_stop": "已持久停止；请所有者审阅失败，禁止绕过。",
                    "recover_interrupted": "存在未终结轮；持独占锁核对，禁止重放预占。",
                    "approve_current_window": "窗口不适用；请所有者审阅新的明确窗口。",
                    "budget_exhausted": "采集额度或计划轮数已耗尽；不得增加调用。",
                }
                typer.echo("下一动作：" + actions[status.next_action])
            return
        records = (ledger.show(receipt_id),) if receipt_id else ledger.list_received()
        from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

        snapshot = EvidenceLifecycle(ledger).snapshot(now=_now())
        sources = {
            (use, capability): identifier
            for use, capability, identifier in snapshot.sources
        }
        active = {
            (item.use, item.capability)
            for item in snapshot.evidence
            if item.evidence_active and not item.revoked
        }
    except LedgerError as error:
        _failure(error.category)
    for record in records:
        evidence_active = any(sources.get(key) == record.receipt_id for key in active)
        typer.echo(
            f"receipt_id={record.receipt_id} "
            f"received_at={record.received_at.isoformat()} "
            f"evidence_active={str(evidence_active).lower()}"
        )
        for claim in record.receipt.claims:
            typer.echo(
                f"capability={claim.capability.value} use={claim.use_id} "
                f"evidence={claim.status.value} basis={claim.basis} scope={claim.scope}"
            )
    if not records:
        typer.echo("准入账本没有已接收回执。")


@live_evidence_app.command(
    help="""经受保护入口接收准入证据，不激活。

当前用途：所有者通过 sudo 接收固定 inbox 中的规范回执。
参数与选项：--source 指定受保护回执；首次可用 --plan 明确批准受保护计划。
副作用：写接收/拒绝审计，不安装、不认证、不调用模型、不访问网络。
自动配额：0；输出去向：标准输出；常见失败：普通用户可写来源不受信，请使用封印采集器。
"""
)
def receive(
    source: Annotated[Path, typer.Option(help="固定准入账本 inbox 内的回执 JSON。")],
    plan: Annotated[
        Path | None, typer.Option(help="所有者明确批准的受保护计划 JSON。")
    ] = None,
) -> None:
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError

    try:
        ledger = EvidenceLedger()
        now = datetime.now(UTC)
        if plan is not None:
            ledger.approve_plan_source(plan, now=now)
        result = ledger.receive(source, now=now)
    except LedgerError as error:
        _failure(error.category)
    outcome = "existing" if result.duplicate else "received"
    typer.echo(f"receipt_id={result.receipt_id} result={outcome} evidence_active=false")


def _owner_ledger() -> EvidenceLedger:
    from paper_radar.live_evidence.ledger import EvidenceLedger

    return EvidenceLedger()


def _now() -> datetime:
    return datetime.now(UTC)


def _refresh_current_observation() -> None:
    """只调用已部署的固定root冻结采集器,不接收路径或自由参数。"""
    from paper_radar.live_evidence.ledger import LedgerError

    try:
        result = subprocess.run(
            ["/usr/libexec/paperradar/live-evidence-collect"],
            env={},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise LedgerError("binding_observation_unavailable") from error
    if result.returncode != 0:
        raise LedgerError("binding_observation_unavailable")


@live_evidence_app.command(
    help="""所有者审阅回执并显式证据激活。

当前用途：只激活已接收、本格 verified、有效且当前适用的必需分项。
参数与选项：--receipt-id 回执短 ID，--use-id 六格准入用途之一。
副作用：仅经所有者输密码授权的封印 sudo 入口追加激活；产品不能自行激活。
确认前展示完整脱敏回执、绑定、原时点与期限，要求输入回执短 ID。
确认后调用固定封印采集器刷新当前观察，同一审核内容才写入；阅读不受60秒限制。
自动配额：0；不认证、不联网、不调用模型。采集失败或事实改变时拒绝，请重新审阅。
"""
)
def activate(
    receipt_id: Annotated[str, typer.Option(help="要审阅的 16 位回执短 ID。")],
    use_id: Annotated[
        str, typer.Option(help="boundary/value/read 与 low/high 的准入用途。")
    ],
) -> None:
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.lifecycle import (
        EvidenceLifecycle,
        use_for_id,
        use_id_for,
    )
    from paper_radar.live_evidence.observation import load_current_observation

    try:
        ledger = _owner_ledger()
        ledger._writer()
        selected_use = use_id_for(use_for_id(use_id))
        observation = load_current_observation(ledger, now=_now())
        lifecycle = EvidenceLifecycle(ledger)
        review = lifecycle.review(
            receipt_id,
            selected_use,
            binding=ExecutionBinding(tuple(observation.binding.items())),
            checked_components=frozenset(observation.checked_components),
            now=_now(),
        )
        typer.echo(review.summary)
        if not review.eligible:
            raise LedgerError("evidence_activation_empty")
        confirmation = typer.prompt("请审阅上方脱敏回执，输入回执短 ID 确认证据激活")
        if confirmation != review.receipt_id:
            raise LedgerError("evidence_activation_confirmation_mismatch")
        refresh_started = _now()
        _refresh_current_observation()
        current = load_current_observation(ledger, now=_now())
        if (
            current.observed_at < refresh_started
            or current.binding != observation.binding
            or frozenset(current.checked_components)
            != frozenset(observation.checked_components)
        ):
            raise LedgerError("observation_changed")
        evidence_activation_now = _now()
        current.validate_time(now=evidence_activation_now)
        result = lifecycle.activate(
            review, confirmation=confirmation, now=evidence_activation_now
        )
    except LedgerError as error:
        _failure(error.category)
    typer.echo(
        f"receipt_id={result.receipt_id} "
        f"result={'existing' if result.duplicate else 'activated'} "
        f"capabilities={','.join(item.value for item in result.capabilities)}"
    )


@live_evidence_app.command(
    help="""不可逆地撤销本格证据资格。

当前用途：所有者通过封印 sudo 入口撤销指定回执、本准入用途的全部分项。
参数与选项：--receipt-id 回执短 ID，--use-id 准入用途。
副作用：追加持久收紧事实；不会授予、恢复或延长任何资格。
自动配额：0；输出去向：标准输出；失败请检查账本信任根。
"""
)
def revoke(
    receipt_id: Annotated[str, typer.Option(help="要撤销的回执短 ID。")],
    use_id: Annotated[str, typer.Option(help="要撤销的准入用途。")],
) -> None:
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.lifecycle import (
        EvidenceLifecycle,
        use_for_id,
        use_id_for,
    )

    try:
        result = EvidenceLifecycle(_owner_ledger()).tighten(
            receipt_id, use_id_for(use_for_id(use_id)), now=_now()
        )
    except LedgerError as error:
        _failure(error.category)
    typer.echo(
        f"receipt_id={receipt_id} evidence_revoked=true "
        f"capabilities={','.join(item.value for item in result)}"
    )
