"""供给的中文薄 CLI 与参数脱敏; 帮助不加载执行服务。"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer
from typer.core import TyperCommand, TyperGroup


@contextmanager
def _arguments() -> Iterator[None]:
    try:
        yield
    except (typer.Exit, typer.Abort):
        raise
    except Exception:
        typer.echo("供给参数无效；请查看 paper-radar pi supply --help。", err=True)
        raise typer.Exit(2) from None


class SupplyGroup(TyperGroup):
    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        with _arguments():
            return super().parse_args(ctx, args)

    def get_command(self, ctx: Any, cmd_name: str) -> Any:
        command = super().get_command(ctx, cmd_name)
        if command is None:
            typer.echo("供给命令无效；请查看 paper-radar pi supply --help。", err=True)
            raise typer.Exit(2)
        return command


class SupplyCommand(TyperCommand):
    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        with _arguments():
            return super().parse_args(ctx, args)


COMMON = """
自动配额：消耗 0 次 Screening、复用升级或精读配额，不调用模型。
输出去向：终端仅显示身份、版本和检查范围；失败输出受控原因与下一步，返回 2。
帮助不读配置或凭据、不联网、不连接数据库、不创建文件。中断返回 130。
"""
GROUP_HELP = (
    """管理项目独立 Pi 固定供给。

当前用途：prepare 准备且冻结固定材料和安装实例；list/show 只读回查。
参数与选项：数据库、快照、adapter 槽及根目录由子命令显式指定，无隐式最新。
副作用：仅 prepare 下载并安装，不激活；list/show 不检查现场，不需要 Pi、平台或网络。
"""
    + COMMON
    + """
常见失败：请求无效、官方材料或完整性冲突、平台不支持、安装失败、根冲突。
示例：paper-radar pi supply list --database data/paperradar.sqlite3
"""
)
PREPARE_HELP = (
    """下载、校验、安装并冻结一份 Pi 供给（不激活）。

参数与选项：--database 为已升级库；--snapshot 为显式完整或唯一短快照引用；
--adapter-slot 选 screening/reuse_assessment/reading；--request 为严格 YAML/JSON；
--install-root、--data-root、--config-root、--material-root 必须显式提供且互不包含。
--proxy 可选，必须是无 userinfo 的 http/https URL，不继承环境代理、不入库。
副作用：从固定官方来源下载，在 install-root 的私有 staging 安装 Node 和 bundled npm/Pi，
成功发布只读完整树并登记材料/检查；不会修改配置或 materials 根，不会激活或调用模型。
"""
    + COMMON
    + """
常见失败：仅支持 Linux x86_64/glibc；重复材料请用后续 rebuild，不能靠改 D5 重冻；
失败不覆盖旧树，未知残留保留人工处理。未验证 RPC、语义与校准。
示例：paper-radar pi supply prepare --database data/paperradar.sqlite3 --snapshot <id>
  --adapter-slot screening --request supply.json --install-root .tools/pi
  --data-root data --config-root config --material-root tools/pi
"""
)

pi_app = typer.Typer(
    cls=SupplyGroup, help=GROUP_HELP, no_args_is_help=True, add_completion=False
)
supply_app = typer.Typer(
    cls=SupplyGroup, help=GROUP_HELP, no_args_is_help=True, add_completion=False
)
pi_app.add_typer(supply_app, name="supply")


@supply_app.command("prepare", cls=SupplyCommand, help=PREPARE_HELP)
def prepare_command(
    database: Annotated[Path, typer.Option("--database", help="已显式迁移的数据库。")],
    snapshot: Annotated[str, typer.Option("--snapshot", help="完整或唯一短快照引用。")],
    adapter_slot: Annotated[
        str, typer.Option("--adapter-slot", help="所依据的 adapter 槽。")
    ],
    request: Annotated[Path, typer.Option("--request", help="严格供给请求文件。")],
    install_root: Annotated[
        Path, typer.Option("--install-root", help="项目独立安装根。")
    ],
    data_root: Annotated[
        Path, typer.Option("--data-root", help="实际数据根，用于重叠检查。")
    ],
    config_root: Annotated[
        Path, typer.Option("--config-root", help="实际配置根，用于重叠检查。")
    ],
    material_root: Annotated[
        Path, typer.Option("--material-root", help="固定材料输出根，用于重叠检查。")
    ],
    proxy: Annotated[
        str | None, typer.Option("--proxy", help="显式无凭据代理；不保存。")
    ] = None,
) -> None:
    from paper_radar.pi_supply import SupplyError, prepare_supply

    try:
        result = prepare_supply(
            database,
            snapshot,
            adapter_slot,
            request,
            install_root,
            data_root=data_root,
            config_root=config_root,
            material_root=material_root,
            proxy=proxy,
        )
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("供给准备中断；旧安装保留，请检查残留后重试。", err=True)
        raise typer.Exit(130) from None
    typer.echo(
        f"supply_id={result.supply_id} install_id={result.install_id} "
        "scope=install_check result=passed"
    )
    typer.echo("已准备，尚未激活；RPC、模型语义与校准尚未验收。")


@supply_app.command(
    "list",
    cls=SupplyCommand,
    help="""只读列出固定供给及历史检查范围。

参数与选项：--database 为既有数据库；无隐式快照选择。
副作用：只读库内事实，不检查现场，不联网，不执行 Pi/Node，不迁移。
"""
    + COMMON
    + """
常见失败：数据库未升级或固定事实损坏时返回 2，请 db upgrade 或检查历史材料。
示例：paper-radar pi supply list --database data/paperradar.sqlite3
""",
)
def list_command(
    database: Annotated[Path, typer.Option("--database", help="既有数据库。")],
) -> None:
    from paper_radar.pi_supply import SupplyError, list_supplies

    try:
        for record in list_supplies(database):
            typer.echo(
                f"supply_id={record.supply_id} pi={record.manifest.pi_version} "
                f"instances={len(record.installs)} scope=install_check"
            )
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None


@supply_app.command(
    "show",
    cls=SupplyCommand,
    help="""显式回查供给清单（含 D5 审计原文）与安装检查。

参数与选项：<supply-id> 为完整供给 ID；--database 为既有数据库。
副作用：只读数据库材料与记录，不读取安装树、不执行 Pi、不联网，不宣称现场可用。
"""
    + COMMON
    + """
常见失败：未知 ID、损坏或引用不可回查返回 2；请从 list 复制完整 ID 并检查库。
示例：paper-radar pi supply show <supply-id> --database data/paperradar.sqlite3
""",
)
def show_command(
    supply_id: str,
    database: Annotated[Path, typer.Option("--database", help="既有数据库。")],
) -> None:
    from paper_radar.pi_supply import SupplyError, show_supply

    try:
        record = show_supply(database, supply_id)
        typer.echo(record.manifest.canonical_bytes.decode())
        for install in record.installs:
            for check in install.checks:
                typer.echo(
                    f"install_id={install.install_id} check_id={check.check_id} "
                    f"scope={check.scope} passed={str(check.passed).lower()} "
                    f"reason={check.reason}"
                )
        typer.echo("以上为历史 install_check；未核验现场，尚无 RPC 或校准结论。")
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
