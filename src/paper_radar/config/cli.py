"""运行配置的薄命令行入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from paper_radar.config.compile import RuntimeConfigSnapshot
from paper_radar.config.errors import ConfigError

DB_HELP = """显式初始化或升级配置数据库。

必须提供 --database；upgrade 可创建数据库并启用 WAL，重复执行保持幂等。
帮助不打开数据库。命令不访问网络、模型，也不消耗自动配额。
错误返回 2；结果写入终端。
示例：paper-radar db upgrade --database data/db.sqlite3
"""
CONFIG_HELP = """检查或编译运行配置快照。

必须显式提供 --settings 与 --database。check 只读；compile 只写既有且已迁移的库。
支持 Profile、主题、models 三槽、boundary/value/reuse/reading 提示词和四份冻结契约。
期刊集合由 settings.journals 选择；校验 ISSN 格式、校验位和规范化标识冲突。
只登记期刊身份、名称和信誉，空集合合法；不进入阶段语义、就绪条件或校准基线。
Read 分块配置由 settings.read 选择，chunking 只接受受控 v1；不执行分块或 Read。
Read 始终 not_ready，缺少权威 Read 契约；仍列出模型、提示词、适配器与分块缺项。
复用升级参数包含非空的 1–5 研究价值集合、固定摘录顺序及受控 v1 算法身份。
boundary、value、复用升级与建议规则分别报告配置就绪及缺项。
正文提取配置登记受控工具链、模型 commit/文件哈希与 normalization 身份。
默认 pypdfium2、Egret medium、TableFormer accurate 和局部公式候选；不执行 PDF 解析。
正文提取配置就绪不证明 fixture gate 或资源检查通过，不验证模型文件存在。
配置就绪不证明模型、摘录、校准或自动精读可运行。空主题集合与全部停用都算已配置。
其他尚未开放的非空选择会拒绝。
adapters 三槽独立选择 Pi 语义材料；冻结系统指令、资源哈希、推理档位和固定隔离策略。
仅登记配置事实，不安装 Pi/Node、不执行 RPC；没有适配器选择时明确显示 unconfigured。
两者均不访问网络、模型或凭据，不消耗自动配额。
帮助不读文件或数据库；错误返回 2，结果只写入终端。
示例：paper-radar config check --settings config/settings.yaml
      --database data/db.sqlite3
"""

db_app = typer.Typer(help=DB_HELP, no_args_is_help=True, rich_markup_mode="markdown")
config_app = typer.Typer(
    help=CONFIG_HELP, no_args_is_help=True, rich_markup_mode="markdown"
)


def _report(snapshot: RuntimeConfigSnapshot) -> None:
    typer.echo(f"快照身份：{snapshot.snapshot_id}")
    typer.echo(f"Profile 槽：{snapshot.profile_status.value}")
    for field, status in snapshot.profile_fields.items():
        typer.echo(f"Profile.{field}：{status.value}")
    for slot, status in snapshot.model_slots.items():
        typer.echo(f"models.{slot}：{status.value}")
    typer.echo(f"主题集合：{snapshot.topics_status.value}")
    typer.echo(f"期刊集合：{snapshot.journals_status.value}")
    for slot, status in snapshot.adapter_slots.items():
        typer.echo(f"adapters.{slot}：{status.value}")
    typer.echo("配置完整性不证明 Pi 执行就绪、校准通过或自动精读资格。")
    for stage, readiness in snapshot.stages.items():
        missing = ", ".join(reason.value for reason in readiness.missing)
        typer.echo(f"{stage.value}：{readiness.status.value}；缺项：{missing}")


@db_app.command(
    "upgrade",
    help=(
        "显式创建或升级数据库；启用 WAL。"
        "示例：paper-radar db upgrade --database data/db.sqlite3"
    ),
)
def db_upgrade(
    database: Annotated[
        Path,
        typer.Option("--database", help="待初始化或升级的 SQLite 路径；必须显式提供。"),
    ],
) -> None:
    from paper_radar.config import upgrade_database

    try:
        revision = upgrade_database(database)
    except ConfigError as error:
        typer.echo(f"数据库升级失败：{error}", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"数据库已升级至 {revision}；WAL 已启用。")


@config_app.command(
    "check",
    help=(
        "只读检查选择和已登记版本；不写数据库。"
        "示例：paper-radar config check --settings config/settings.yaml "
        "--database data/db.sqlite3"
    ),
)
def config_check(
    settings: Annotated[
        Path, typer.Option("--settings", help="明确选择的 settings.yaml 路径。")
    ],
    database: Annotated[
        Path, typer.Option("--database", help="既有且已迁移的 SQLite 路径；只读打开。")
    ],
) -> None:
    from paper_radar.config.service import check_config

    try:
        _report(check_config(settings, database))
    except ConfigError as error:
        typer.echo(f"配置检查失败：{error}", err=True)
        raise typer.Exit(2) from None


@config_app.command(
    "compile",
    help=(
        "原子保存不可变快照；只打开既有数据库。"
        "示例：paper-radar config compile --settings config/settings.yaml "
        "--database data/db.sqlite3"
    ),
)
def config_compile(
    settings: Annotated[
        Path, typer.Option("--settings", help="明确选择的 settings.yaml 路径。")
    ],
    database: Annotated[
        Path, typer.Option("--database", help="既有且已迁移的 SQLite 路径。")
    ],
) -> None:
    from paper_radar.config.service import compile_config

    try:
        _report(compile_config(settings, database))
    except ConfigError as error:
        typer.echo(f"配置编译失败：{error}", err=True)
        raise typer.Exit(2) from None
