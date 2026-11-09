"""准入账本所有者入口;help 不读取配置或账本。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

live_evidence_app = typer.Typer(
    name="live-evidence",
    add_completion=False,
    no_args_is_help=True,
    help="""管理独立准入账本中的分项证据。

当前用途：所有者接收受保护站点回执，或只读查询脱敏摘要。
参数与选项：使用 show/receive --help 查看明确选择。
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
            return
        records = (ledger.show(receipt_id),) if receipt_id else ledger.list_received()
    except LedgerError as error:
        _failure(error.category)
    for record in records:
        typer.echo(
            f"receipt_id={record.receipt_id} "
            f"received_at={record.received_at.isoformat()} evidence_active=false"
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
