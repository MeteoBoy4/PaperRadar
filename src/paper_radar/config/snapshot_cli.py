"""配置快照发现的薄 CLI。查询与引用规则由公共服务负责。"""

from pathlib import Path
from typing import Annotated, Any

import typer
from typer.core import TyperCommand

from paper_radar.config.errors import ConfigError

SNAPSHOTS_HELP = """只读发现历史配置快照。

参数与选项：list 必须提供 --database，以选择档案库；详情见 list --help。
副作用：不建库、不迁移、不联网或调用模型；帮助不打开数据库，消耗 0 次自动配额。
输出去向：终端；成功返回 0，参数或数据库错误返回 2。
常见失败：缺库或未迁移时，须先通过 db upgrade 显式初始化；不隐式修复数据库。
示例：paper-radar config snapshots list --database data/paperradar.sqlite3
"""

SNAPSHOT_LIST_HELP = """只读发现指定数据库内的历史配置快照。

数据库选择档案库，快照引用选择其中的历史配置。
必须显式提供 --database；不读取当前配置或凭据，不联网、不调用模型，消耗 0 次配额。
列表展示完整 ID、查询时唯一的短前缀、已记录创建时间与声明版本摘要，不输出配置正文。
不验证快照完整性，不表示已启用；不建库、不迁移、不补写时间、不保存缓存。
结果写入终端，成功返回 0，输入或数据库错误返回 2。
示例：paper-radar config snapshots list --database data/paperradar.sqlite3
再比较：paper-radar config diff <before-reference> <after-reference>
        --database data/paperradar.sqlite3
"""

snapshots_app = typer.Typer(
    help=SNAPSHOTS_HELP, no_args_is_help=True, rich_markup_mode="markdown"
)


class _SnapshotListCommand(TyperCommand):
    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except (typer.Exit, typer.Abort):
            raise
        except Exception:
            typer.echo(
                "快照列表参数错误：必须显式提供 --database 路径，不接受其他参数；"
                "参见 paper-radar config snapshots list --help。",
                err=True,
            )
            raise typer.Exit(2) from None


@snapshots_app.command(
    "list",
    cls=_SnapshotListCommand,
    help=SNAPSHOT_LIST_HELP
    + "\n前缀从 8 位开始按需延长，无法在 63 位内唯一时展示完整 ID。"
    "新增快照可能使旧前缀不再唯一，使用时重新解析；长期记录、脚本和审计请保留完整 ID。",
)
def snapshots_list(
    database: Annotated[
        Path,
        typer.Option("--database", help="必填的既有 SQLite 档案库路径；只读打开。"),
    ],
) -> None:
    from paper_radar.config import list_config_snapshots

    try:
        summaries = list_config_snapshots(database)
    except ConfigError as error:
        typer.echo(f"快照列表失败：{error}", err=True)
        raise typer.Exit(2) from None
    if not summaries:
        typer.echo("暂无已保存快照")
        return
    typer.echo("已保存快照（发现记录，未验证完整性，不表示已启用）：")
    for summary in summaries:
        typer.echo(f"完整 ID：{summary.snapshot_id}")
        typer.echo(f"便捷引用（查询时唯一）：{summary.short_reference}")
        created_at = summary.created_at.isoformat() if summary.created_at else "未记录"
        typer.echo(f"创建时间：{created_at}")
        typer.echo("声明版本摘要：")
        if not summary.versions:
            typer.echo("  无已选配置")
        for version in summary.versions:
            typer.echo(f"  {version.kind.value}.{version.name}：{version.version}")
