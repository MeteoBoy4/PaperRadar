"""Screening 只读失败查询与显式恢复;执行由所属工作流负责。"""

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from paper_radar.screening_tasks import ScreeningTasks

import typer

from paper_radar.backup.cli_support import BatchCommand, BatchGroup

HELP = """\
用途：查询全库当前指纹最新代际的模型失败队列；显式 retry 只登记唯一后继。
参数：failures 必填 --database、--snapshot；retry PAPER_ID 另需
--request-id、--reason、--actor，可用 --stage boundary/value 消除歧义。
reclaim RECEIPT_ID 必填 --database，显式结算过期租约为 outcome_unknown。
副作用：failures 只读，不结算、不退款、不续租、不建日志；retry/reclaim 写既有库，
不执行模型。帮助不联网、不开库、不建目录。命令对 experiment/production/unknown 根中性。
自动配额：0；retry 不领取尝试或自动名额。
输出去向：标准输出安全 JSON；错误至标准错误，不含自由理由或模型内容。
常见失败：未失败/歧义/请求冲突/可见性拒绝请先 paper trace 回查；
第二次 lease_expired 必须先 reclaim，再 retry，最后显式执行后继回执。
退出码：成功 0；受控拒绝及参数错误 2；中断 130。
示例：paper-radar screening failures --database /tmp/root/paper-radar.sqlite3
  --snapshot SNAPSHOT
示例：paper-radar screening reclaim RECEIPT --database /tmp/root/paper-radar.sqlite3
示例：paper-radar screening retry PAPER --database /tmp/root/paper-radar.sqlite3 \
--snapshot SNAPSHOT --request-id retry-1 --reason 所有者选择重试 --actor owner
示例：paper-radar experiment screen --root /tmp/root --selection-id SELECTION \
--snapshot SNAPSHOT --credentials-dir /tmp/credentials --material-root /tmp/materials \
--install-root /tmp/pi --receipt-id SUCCESSOR_RECEIPT
boundary 恢复成功且未登记 value 时，显式 experiment screen ... --continue-value。
"""


class ScreeningGroup(BatchGroup):
    parameter_error = "Screening 参数不正确；请运行 paper-radar screening --help"
    unknown_command_error = "Screening 子命令不受支持；请使用 failures/retry/reclaim"


class ScreeningCommand(BatchCommand):
    parameter_error = "Screening 参数不正确；请查看该命令 --help"


screening_app = typer.Typer(
    cls=ScreeningGroup, help=HELP, no_args_is_help=True, rich_markup_mode=None
)
Database = Annotated[Path, typer.Option("--database", help="既有数据库路径")]
Snapshot = Annotated[str, typer.Option("--snapshot", help="明确的历史配置快照 ID")]


def _tasks(database: Path) -> "ScreeningTasks":
    from paper_radar.screening_tasks import ScreeningTasks

    return ScreeningTasks(database, clock=lambda: datetime.now(UTC))


def _run(operation: Callable[[], object]) -> None:
    from paper_radar.config import ConfigError
    from paper_radar.papers import PaperError
    from paper_radar.screening_tasks import TaskError
    from paper_radar.storage.errors import StorageError

    try:
        result = operation()
        typer.echo(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    except (ConfigError, PaperError, TaskError, StorageError) as error:
        typer.echo(
            f"Screening 拒绝 [{error.reason.value}]；"
            "请回查 paper trace 或 --help 后显式继续。",
            err=True,
        )
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "Screening 中断 [interrupted]；请只读查询原回执后显式继续。", err=True
        )
        raise typer.Exit(130) from None


@screening_app.command("failures", cls=ScreeningCommand, help=HELP)
def failures_command(database: Database, snapshot: Snapshot) -> None:
    def operation() -> dict[str, object]:
        tasks = _tasks(database)
        from paper_radar.body import BodyService

        root = BodyService(database, database.parent).root()
        return dict(
            snapshot_id=snapshot,
            root_purpose=root.purpose,
            failures=[asdict(item) for item in tasks.failures(snapshot_id=snapshot)],
        )

    _run(operation)


@screening_app.command("retry", cls=ScreeningCommand, help=HELP)
def retry_command(
    paper_id: Annotated[str, typer.Argument(help="当前失败的论文 ID")],
    database: Database,
    snapshot: Snapshot,
    request_id: Annotated[str, typer.Option("--request-id", help="唯一幂等请求")],
    reason: Annotated[str, typer.Option("--reason", help="所有者的非空重试理由")],
    actor: Annotated[str, typer.Option("--actor", help="非空操作者说明")],
    stage: Annotated[
        str | None, typer.Option("--stage", help="boundary 或 value")
    ] = None,
) -> None:
    _run(
        lambda: asdict(
            _tasks(database).retry_failed(
                paper_id=paper_id,
                snapshot_id=snapshot,
                request_id=request_id,
                reason=reason,
                actor=actor,
                stage=stage,
            )
        )
    )


@screening_app.command("reclaim", cls=ScreeningCommand, help=HELP)
def reclaim_command(
    receipt_id: Annotated[str, typer.Argument(help="需要显式结算的原回执 ID")],
    database: Database,
) -> None:
    _run(lambda: asdict(_tasks(database).reclaim(receipt_id)))
