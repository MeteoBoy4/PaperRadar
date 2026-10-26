"""来源审计命令;只有显式 run 执行来源工作。"""

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
当前用途：显式 run 固定选样并执行摘要矩阵；list/show 只读查询材料哈希和安全计数。
参数：run 需 --database、--data-root、--contact-email，--count 为全轮 N=5–10；
list 接受 --database；show 另需 PLAN_ID；--json 输出结构化事实。
副作用：list/show 只读，不迁移、不联网、不创建目录或执行锁；帮助不访问任何业务资源。
自动配额：0 次模型调用；run 全轮串行、按主机限速；run 先验证邮箱和提交计划再联网。
邮箱仅用于如实请求标识，不保存；run 不启动模型、浏览器或生产论文流程。
输出去向：计划、执行状态和材料哈希写标准输出；受控错误写标准错误，失败退出 1。
未结算的 started 路线请求数是未知；未安装与未执行分列，不证明来源稳定或阶段 A 通过。
常见失败：数据库缺失时先显式 db upgrade；不能以查询替代真实来源审计。
示例：paper-radar audit run --database DB --data-root ROOT
      --contact-email audit@example.org --count 5
示例：paper-radar audit list --database data/paper-radar.sqlite3 --json
示例：paper-radar audit show PLAN_ID --database data/paper-radar.sqlite3 --json
"""


class AuditGroup(BatchGroup):
    parameter_error = "审计参数不正确；请查看 paper-radar audit --help"
    unknown_command_error = "审计子命令尚未交付；当前使用 run/list/show"


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


@audit_app.command(
    "run", cls=AuditCommand, help="显式取得四刊固定成员及摘要矩阵。\n\n" + HELP
)
def run_command(
    database: Database,
    data_root: Annotated[Path, typer.Option("--data-root", help="既有制品数据根")],
    contact_email: Annotated[
        str | None, typer.Option("--contact-email", help="仅用于请求标识的显式联系邮箱")
    ] = None,
    target_count: Annotated[
        int, typer.Option("--count", help="整轮每刊目标 N=5–10")
    ] = 5,
    json_output: Annotated[
        bool, typer.Option("--json", help="输出安全结构化 JSON")
    ] = False,
) -> None:
    from paper_radar.fixture_audit import FixtureAudit

    _query(
        lambda: FixtureAudit(database, data_root).run_audit(
            contact_email=contact_email, target_count=target_count
        ),
        json_output,
    )
