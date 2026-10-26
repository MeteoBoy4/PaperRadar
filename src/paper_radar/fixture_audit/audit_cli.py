"""来源审计只读命令;不注册尚未交付的联网工作流。"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from paper_radar.backup.cli_support import BatchCommand, BatchGroup
from paper_radar.fixture_audit.acquisition_models import AuditView
from paper_radar.fixture_audit.errors import FixtureError
from paper_radar.storage.errors import StorageError

HELP = """\
当前用途：只读查询计划、路线执行、固定成员/排除/暂停位置、材料哈希和安全计数。
参数：list 接受 --database；show 另需 PLAN_ID；--json 输出结构化事实。
副作用：list/show 只读，不迁移、不联网、不创建目录或执行锁；帮助不访问任何业务资源。
自动配额：0 次模型调用；来源取得只由显式服务调用推进，当前没有空的 run/resume 命令。
输出去向：计划、执行状态和材料哈希写标准输出；受控错误写标准错误，失败退出 1。
未结算的 started 路线请求数是未知；未安装与未执行分列，不证明来源稳定或阶段 A 通过。
常见失败：数据库缺失时先显式 db upgrade；不能以查询替代真实来源审计。
示例：paper-radar audit list --database data/paper-radar.sqlite3 --json
示例：paper-radar audit show PLAN_ID --database data/paper-radar.sqlite3 --json
"""


class AuditGroup(BatchGroup):
    parameter_error = "审计参数不正确；请查看 paper-radar audit --help"
    unknown_command_error = "审计子命令尚未交付；当前使用 list/show"


class AuditCommand(BatchCommand):
    parameter_error = "审计参数不正确；请查看该命令 --help"


audit_app = typer.Typer(
    cls=AuditGroup, help=HELP, no_args_is_help=True, rich_markup_mode=None
)
Database = Annotated[
    Path, typer.Option("--database", help="既有 SQLite 数据库，不隐式迁移")
]


def audit_projection(view: AuditView) -> dict[str, object]:
    result: dict[str, object] = view.model_dump(mode="json")
    result["executions"] = [
        {
            **execution.model_dump(mode="json"),
            "status": "settled" if execution.settlement else "started",
            "reason": execution.reason,
            "physical_requests": execution.physical_requests,
            "is_failure": execution.is_failure,
        }
        for execution in view.executions
    ]
    return result


def _query(
    operation: Callable[[], tuple[AuditView, ...] | AuditView], json_output: bool
) -> None:
    try:
        value = operation()
    except (FixtureError, StorageError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    result = (
        [audit_projection(item) for item in value]
        if isinstance(value, tuple)
        else audit_projection(value)
    )
    if not json_output:
        typer.echo("审计历史（只读；complete 不代表来源稳定或生产就绪）")
    typer.echo(
        json.dumps(result, ensure_ascii=False, indent=None if json_output else 2)
    )


@audit_app.command("list", cls=AuditCommand, help="只读列出计划及取得事实。\n\n" + HELP)
def list_command(
    database: Database,
    json_output: Annotated[
        bool, typer.Option("--json", help="输出结构化 JSON")
    ] = False,
) -> None:
    from paper_radar.fixture_audit import FixtureAudit

    _query(lambda: FixtureAudit(database).list_audits(), json_output)


@audit_app.command(
    "show", cls=AuditCommand, help="只读查看固定计划及完整路线历史。\n\n" + HELP
)
def show_command(
    plan_id: Annotated[str, typer.Argument(help="已登记计划 ID")],
    database: Database,
    json_output: Annotated[
        bool, typer.Option("--json", help="输出结构化 JSON")
    ] = False,
) -> None:
    from paper_radar.fixture_audit import FixtureAudit

    _query(lambda: FixtureAudit(database).show_audit(plan_id), json_output)
