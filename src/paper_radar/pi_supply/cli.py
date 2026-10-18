"""供给的中文薄 CLI 与参数脱敏; 帮助不加载执行服务。"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer
from typer.core import TyperCommand, TyperGroup

from paper_radar.pi_supply.cleanup_models import CleanupExecution, CleanupPlan
from paper_radar.pi_supply.models import Decision


def _d5_guidance(decision: Decision) -> None:
    if decision in {"may_change", "unknown"}:
        typer.echo(
            "D5：需要后续相关语义评估；安装检查不代表校准兼容，不自动判定 minor/major。"
        )


@contextmanager
def _arguments(command: str = "paper-radar pi supply") -> Iterator[None]:
    try:
        yield
    except (typer.Exit, typer.Abort):
        raise
    except Exception:
        typer.echo(f"参数无效；请查看 {command} --help。", err=True)
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


class DoctorCommand(TyperCommand):
    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        with _arguments("paper-radar doctor"):
            return super().parse_args(ctx, args)


COMMON = """
自动配额：消耗 0 次 Screening、复用升级或精读配额，不调用模型。
输出去向：终端仅显示身份、版本和检查范围；失败输出受控原因与下一步，返回 2。
帮助不读配置或凭据、不联网、不连接数据库、不创建文件。中断返回 130。
"""
GROUP_HELP = (
    """管理项目独立 Pi 固定供给。

当前用途：prepare 准备；verify 逐实例核验；rebuild 联网重建；
activate 显式切换唯一选择；list/show 只读回查；export 导出固定材料；
gc --dry-run 保存计划，gc --execute <plan-id> 显式清理；show-plan 回查。
参数与选项：数据库、快照、adapter 槽及根目录由子命令显式指定，无隐式最新。
副作用：prepare/rebuild 下载并安装，verify 运行无模型检查，均不激活；
list/show/export 不检查现场。
"""
    + COMMON
    + """
常见失败：请求无效、官方材料或完整性冲突、平台不支持、安装失败、根冲突。
示例：paper-radar pi supply list --database data/paperradar.sqlite3
"""
)
PI_HELP = (
    """管理项目独立 Pi 的本地命令组。

当前用途：supply 管理固定供给；具体操作请查看 paper-radar pi supply --help。
参数与选项：由 supply 子命令显式指定数据库、快照与根目录。
副作用：本命令组只分派操作，具体下载、核验或清理由子命令说明。
"""
    + COMMON
    + """
常见失败：未知命令请查看 paper-radar pi --help。
示例：paper-radar pi supply --help
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
常见失败：仅支持 Linux x86_64/glibc；重复材料请用 rebuild，不能靠改 D5 重冻；
失败不覆盖旧树，未知残留保留人工处理。未验证 RPC、语义与校准。
示例：paper-radar pi supply prepare --database data/paperradar.sqlite3
  --snapshot <id>
  --adapter-slot screening --request supply.json --install-root .tools/pi
  --data-root data --config-root config --material-root tools/pi
"""
)

pi_app = typer.Typer(
    cls=SupplyGroup, help=PI_HELP, no_args_is_help=True, add_completion=False
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
        typer.echo("以上实例计数为历史登记；未核验现场，不代表当前可用。")
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
        _d5_guidance(record.manifest.d5.decision)
        for install in record.installs:
            for check in install.checks:
                typer.echo(
                    f"install_id={install.install_id} check_id={check.check_id} "
                    f"scope={check.scope} passed={str(check.passed).lower()} "
                    f"reason={check.reason}"
                )
        for failure in record.rebuild_failures:
            typer.echo(
                f"failure_id={failure.failure_id} operation=rebuild "
                f"reason={failure.reason} created_at={failure.created_at}"
            )
        typer.echo("以上为历史 install_check；未核验现场，尚无 RPC 或校准结论。")
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None


@supply_app.command(
    "verify",
    cls=SupplyCommand,
    help="""逐一核验供给的全部已登记实例。

参数与选项：<supply-id> 为完整供给 ID；--database 为已升级库。
副作用：逐实例全树哈希、明确 Node/npm 版本和 Pi 无模型启动检查；每次追加 install_check。
损坏树先拒绝执行，单实例失败后仍检查其他实例；不下载、不修复树、不改预期或激活。
"""
    + COMMON
    + """
常见失败：Linux x86_64/glibc 与冻结版本必须匹配；坏树或版本不符请 rebuild。
示例：paper-radar pi supply verify <supply-id> --database data/paperradar.sqlite3
""",
)
def verify_command(
    supply_id: str,
    database: Annotated[Path, typer.Option("--database", help="已升级数据库。")],
) -> None:
    from paper_radar.pi_supply import SupplyError, verify_supply

    try:
        results = verify_supply(database, supply_id)
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("供给核验中断；历史检查保留，请重试。", err=True)
        raise typer.Exit(130) from None
    for item in results:
        typer.echo(
            f"install_id={item.install_id} scope=install_check "
            f"passed={str(item.passed).lower()} reason={item.reason}"
        )
    if any(not item.passed for item in results):
        typer.echo("部分实例核验失败；请保留现场并运行 rebuild 重建新实例。", err=True)
        raise typer.Exit(2)
    typer.echo("全部实例通过 install_check；RPC、模型语义与校准尚未验收。")


@supply_app.command(
    "rebuild",
    cls=SupplyCommand,
    help="""按库内历史固定材料联网重建新实例（不激活）。

参数与选项：<supply-id> 为完整供给 ID；--database 为已升级库；
四个根须显式提供且互不包含。
--proxy 为可选无 userinfo 的 http/https 代理，不继承环境或保存。
副作用：重新联网下载固定 Node 归档和 npm 包，核对原工具链、派生锁、入口与预期树；
不是脱网重建。不重取 package/lock/release/SHASUMS 或 D5，
不重新解析依赖、不更新供给身份。
成功登记随机新实例与 install_check；失败追加供给级审计，不覆盖旧实例、不修改当前选择。
"""
    + COMMON
    + """
常见失败：仅支持匹配冻结 libc 的 Linux x86_64/glibc；材料缺失、摘要或树漂移立即拒绝。
强杀后可重试完成可靠发布意图；未知 staging 或未登记树保留人工处理，不自动清理。
示例：paper-radar pi supply rebuild <supply-id> --database data/paperradar.sqlite3
  --install-root .tools/pi --data-root data --config-root config
  --material-root tools/pi
""",
)
def rebuild_command(
    supply_id: str,
    database: Annotated[Path, typer.Option("--database", help="已升级数据库。")],
    install_root: Annotated[
        Path, typer.Option("--install-root", help="项目独立安装根。")
    ],
    data_root: Annotated[Path, typer.Option("--data-root", help="实际数据根。")],
    config_root: Annotated[Path, typer.Option("--config-root", help="实际配置根。")],
    material_root: Annotated[
        Path, typer.Option("--material-root", help="固定材料根。")
    ],
    proxy: Annotated[
        str | None, typer.Option("--proxy", help="显式无凭据代理；不保存。")
    ] = None,
) -> None:
    from paper_radar.pi_supply import SupplyError, rebuild_supply

    try:
        result = rebuild_supply(
            database,
            supply_id,
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
        typer.echo("供给重建中断；旧实例保留，请检查残留后重试。", err=True)
        raise typer.Exit(130) from None
    typer.echo(
        f"supply_id={result.supply_id} install_id={result.install_id} "
        "scope=install_check result=passed"
    )
    typer.echo("已重建，尚未激活；RPC、模型语义与校准尚未验收。")
    if result.residuals:
        typer.echo(
            "安装已成功登记；本次清理未完成，请保留残留人工检查，可重试可靠发布意图。"
        )


@supply_app.command(
    "activate",
    cls=SupplyCommand,
    help="""显式将供给激活为每库唯一当前执行选择。

参数与选项：<supply-id> 为完整供给ID；--database 为既有库；--snapshot 必须显式给出。
所给快照至少选择一个adapter槽，全部已选槽Pi版本必须匹配；混用版本不能激活。
副作用：只做全树哈希，不运行Node/npm/Pi；选最近通过且现场可用实例，短事务追加激活事件。
不改selector、预算、enable或校准；回退也须显式匹配快照，无自动fallback。
"""
    + COMMON
    + """
常见失败：无可用实例时请 rebuild 后再 activate；准备与重建不会自动切换当前选择。
示例：paper-radar pi supply activate <supply-id> --database data/paperradar.sqlite3
  --snapshot <id>
""",
)
def activate_command(
    supply_id: str,
    database: Annotated[Path, typer.Option("--database", help="已升级数据库。")],
    snapshot: Annotated[
        str, typer.Option("--snapshot", help="显式完整或唯一短快照引用。")
    ],
) -> None:
    from paper_radar.pi_supply import SupplyError, activate_supply

    try:
        result = activate_supply(database, supply_id, snapshot)
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("激活中断；请只读检查当前选择后重试。", err=True)
        raise typer.Exit(130) from None
    typer.echo(
        f"activation_id={result.activation_id} supply_id={result.supply_id} "
        f"install_id={result.install_id} snapshot_id={result.snapshot_id}"
    )
    typer.echo(
        "已更新唯一执行选择；RPC、模型、隔离、校准与自动精读未验证，不产生启用资格。"
    )


DOCTOR_HELP = """只读诊断显式选定的范围，目前仅支持 pi-supply。

参数与选项：--scope pi-supply、--database 和 --snapshot 均必填，无默认scope或隐式最新。
副作用：只读库内全量材料/引用闭包与现场全树哈希；不运行程序、不联网、不写检查或激活事实。
输出去向：终端分别显示当前匹配、配置缺项、历史现场、保留保护与未验证能力。
供给必需项缺失、损坏或实际树超过四棵时返回2；0仅表示该scope通过。
Profile/模型/Read配置缺项单独披露，不代表全项目就绪；不授予模型或校准资格。
自动配额：消耗0次Screening、复用升级或精读配额。帮助不创建文件或连接数据库。
常见失败：当前实例不可用请 rebuild 后再 activate；历史坏树/缺根单列，不自动回退。
示例：paper-radar doctor --scope pi-supply --database data/paperradar.sqlite3
  --snapshot <id>
"""


def doctor_command(
    scope: Annotated[str, typer.Option("--scope", help="显式范围，仅pi-supply。")],
    database: Annotated[
        Path, typer.Option("--database", help="既有数据库，只读打开。")
    ],
    snapshot: Annotated[
        str, typer.Option("--snapshot", help="显式完整或唯一短快照引用。")
    ],
) -> None:
    from paper_radar.pi_supply import SupplyError, doctor_supply
    from paper_radar.pi_supply.errors import GUIDANCE

    if scope != "pi-supply":
        typer.echo("诊断范围无效；请显式使用 --scope pi-supply。", err=True)
        raise typer.Exit(2)
    try:
        report = doctor_supply(database, snapshot)
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("只读诊断中断；请重试。", err=True)
        raise typer.Exit(130) from None
    typer.echo(f"scope=pi-supply result={'passed' if report.passed else 'failed'}")
    if report.current:
        typer.echo(
            f"当前选择 activation_id={report.current.activation_id} "
            f"supply_id={report.current.supply_id} "
            f"install_id={report.current.install_id}"
        )
    for reason in report.blockers:
        typer.echo(f"[{reason}] {GUIDANCE[reason]}")
    typer.echo("adapter未配置槽：" + (", ".join(report.adapter_unconfigured) or "无"))
    typer.echo(
        "业务配置缺项（独立披露）：" + (", ".join(report.configuration_missing) or "无")
    )
    if report.d5:
        typer.echo(f"D5原文 decision={report.d5.decision} basis={report.d5.basis}")
        _d5_guidance(report.d5.decision)
    typer.echo(
        f"保留：当前及最近三旧={len(report.retained_install_ids)}，已有验收保护={len(report.acceptance_install_ids)}，现场树数={report.present_count}，上限=4"
    )
    for item in report.instances:
        typer.echo(
            f"历史现场 install_id={item.install_id} reason={item.reason} "
            f"present={item.present} protection={','.join(item.protection) or '无'} "
            f"protection_state={item.protection_state} "
            f"protection_reason={item.protection_reason or '无'}"
        )
    typer.echo(
        "RPC、真实模型/凭据、参数映射、生产隔离、校准与自动精读未验证："
        + ", ".join(report.not_assessed)
    )
    typer.echo("0仅表示所选供给scope通过；不代表全项目就绪，不刷新预算或启用门禁。")
    if not report.passed:
        raise typer.Exit(2)


GC_HELP = (
    """生成可审阅的不可变安装清理计划，或显式执行保存的计划。

参数与选项：--database 必填；--dry-run 必须给实际
--data-root/--config-root/--material-root；--execute <plan-id> 仅接受保存的完整计划ID。
两种模式互斥，执行时不得传根路径；不接受 force。
安装位置只来自本库登记的根和实例，不接受目标路径、glob 或 force。
副作用：dry-run 只追加计划事实，不删除；执行重新核验所有安全依据，
非阻塞排他锁后短事务退役，再不覆盖移入受控 trash 后删除并记录逐项结果。
退役不会撤销；失败或强杀后须用新 dry-run 计划显式回收，不能刷新旧预期。
共用原安装根的恢复活动副本，在旧副本退役前不得清理。
保留窗口跨供给按 install_id 去重，当前和最近三个旧实例
叠加在途、未知保护及各范围最近通过。
未知 staging/未登记树人工处理；已退役残留单列；超过四棵仅报告，不绕过保护。
分配占用来自真实 inode 遍历并去重，可回收量是估算，不保证实际释放字节数。
"""
    + COMMON
    + """
常见失败：根归属或路径不安全会标注无法核验；生成期间事实变化须重试。
示例：paper-radar pi supply gc --dry-run --database data/paperradar.sqlite3
  --data-root data --config-root config --material-root tools/pi
"""
)


def _show_plan(plan: CleanupPlan) -> None:
    typer.echo(f"plan_id={plan.plan_id} facts_version={plan.facts_version}")
    typer.echo("保存计划但不删除；现场探测不是删除授权。")
    typer.echo(
        f"候选={len(plan.candidates)} 已退役待删={len(plan.retired_pending)} "
        f"需人工处理={len(plan.manual)} 现场树数={plan.present_count} "
        f"上限=4 超限={plan.over_limit}"
    )
    typer.echo(
        f"遍历分配占用={plan.allocated_bytes} "
        f"预计可回收={plan.reclaimable_bytes} 占用存在未知={plan.occupancy_unknown}"
    )
    for item in plan.items:
        typer.echo(
            f"install_id={item.install_id} supply_id={item.supply_id} "
            f"state={item.state} ever_activated={item.ever_activated} "
            f"disposition={item.disposition} reason={item.reason} "
            f"protection={','.join(item.protection) or '无'} "
            f"actual_tree_hash={item.actual_tree_hash or '未知'}"
        )
    for manual in plan.manual:
        typer.echo(
            f"人工处理 root_id={manual.root_id} reason={manual.reason} "
            f"allocated_bytes={manual.allocated_bytes} "
            f"logical_bytes={manual.logical_bytes} "
            f"occupancy_reason={manual.occupancy_reason}"
        )


@supply_app.command("gc", cls=SupplyCommand, help=GC_HELP)
def gc_command(
    database: Annotated[Path, typer.Option("--database", help="已升级数据库。")],
    data_root: Annotated[
        Path | None, typer.Option("--data-root", help="dry-run实际数据根。")
    ] = None,
    config_root: Annotated[
        Path | None, typer.Option("--config-root", help="dry-run实际配置根。")
    ] = None,
    material_root: Annotated[
        Path | None, typer.Option("--material-root", help="dry-run固定材料根。")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="保存计划但不删除。")
    ] = False,
    execute: Annotated[
        str | None, typer.Option("--execute", help="仅执行保存的完整计划ID。")
    ] = None,
) -> None:
    from paper_radar.pi_supply import (
        SupplyError,
        create_cleanup_plan,
        execute_cleanup_plan,
    )

    if (dry_run and execute is not None) or (not dry_run and execute is None):
        typer.echo(
            "必须显式使用 --dry-run 或 --execute <plan-id>，两种模式互斥。", err=True
        )
        raise typer.Exit(2)
    if execute is not None and any(
        root is not None for root in (data_root, config_root, material_root)
    ):
        typer.echo(
            "执行仅接受保存的计划ID，不接受根路径；请先核对 show-plan。", err=True
        )
        raise typer.Exit(2)
    if dry_run and any(
        root is None for root in (data_root, config_root, material_root)
    ):
        typer.echo(
            "--dry-run 必须给实际 --data-root、--config-root、--material-root。",
            err=True,
        )
        raise typer.Exit(2)
    try:
        if execute is not None:
            result = execute_cleanup_plan(database, execute)
            _show_execution(result)
            if not result.passed:
                raise typer.Exit(2)
        else:
            assert (
                data_root is not None
                and config_root is not None
                and material_root is not None
            )
            _show_plan(
                create_cleanup_plan(
                    database,
                    data_root=data_root,
                    config_root=config_root,
                    material_root=material_root,
                )
            )
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "清理操作中断；退役不会撤销，请重新生成计划并显式回收残留。", err=True
        )
        raise typer.Exit(130) from None


def _show_execution(execution: CleanupExecution) -> None:
    typer.echo(
        f"run_id={execution.run_id} plan_id={execution.plan_id} "
        f"result={'passed' if execution.passed else 'incomplete'}"
    )
    for item in execution.items:
        if item.phase == "not_run" and item.reason != "not_run":
            typer.echo("库级前置阻断：该候选未运行，未归因为候选自身失败。")
        typer.echo(
            f"install_id={item.install_id} phase={item.phase} reason={item.reason}"
        )
    if not execution.passed:
        typer.echo("清理未完成；退役不会撤销，请重新生成计划并显式回收残留。")


@supply_app.command(
    "show-plan",
    cls=SupplyCommand,
    help="""只读回查不可变清理计划的原有依据。

参数与选项：<plan-id> 为完整64位计划ID；--database 为既有数据库；
--canonical 输出保存的规范 JSON 原字节，终端附一个换行。
副作用：只读历史回放，不检查现场，不写库、不联网、不运行程序。
输出去向：终端显示计划汇总和理由，或规范 JSON。
"""
    + COMMON
    + """
常见失败：未知ID请先 gc --dry-run；损坏计划请保留数据库检查完整性。
示例：paper-radar pi supply show-plan <plan-id> --database data/paperradar.sqlite3
""",
)
def show_plan_command(
    plan_id: str,
    database: Annotated[
        Path, typer.Option("--database", help="既有数据库，只读打开。")
    ],
    canonical: Annotated[
        bool, typer.Option("--canonical", help="输出不可变规范JSON原字节。")
    ] = False,
) -> None:
    from paper_radar.pi_supply import (
        SupplyError,
        list_cleanup_executions,
        show_cleanup_plan,
    )

    try:
        plan = show_cleanup_plan(database, plan_id)
        executions = () if canonical else list_cleanup_executions(database)
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    if canonical:
        typer.echo(plan.canonical_bytes.decode())
    else:
        _show_plan(plan)
        for execution in executions:
            if execution.plan_id == plan.plan_id:
                _show_execution(execution)


@supply_app.command(
    "export",
    cls=SupplyCommand,
    help="""从已核验数据库导出可提交版本控制的固定小型材料。

参数与选项：<supply-id> 为完整 ID；--database 为既有库；--target 为材料根。
材料根须与库内全部已登记安装根及数据库位置分离，不从 cwd 猜配置或数据根。
输出去向：target/<supply-id>/ 下六个顶层材料及 d5-evidence/<摘要前16位>.bin。
不导出内部派生锁、安装树、Node/npm 归档、凭据、日志或 RPC。
副作用：整组预检后不覆盖发布；同字节跳过，冲突拒绝，额外用户文件保留。
list/show/export 无平台、网络、Node/Pi 或安装现场前置。
材料 tools/pi/ 可提交 Git；安装 .tools/pi/ 被忽略，二者须分开。
"""
    + COMMON
    + """
常见失败：历史损坏、异字节、链接、特殊文件或证据短名冲突返回 2。
请保留原文件并选择空目标；I/O 失败可重试，同字节文件不重复写入。
示例：paper-radar pi supply export <supply-id> --database data/paperradar.sqlite3
  --target tools/pi
""",
)
def export_command(
    supply_id: str,
    database: Annotated[Path, typer.Option("--database", help="既有数据库。")],
    target: Annotated[
        Path, typer.Option("--target", help="可提交版本控制的固定材料根。")
    ],
) -> None:
    from paper_radar.pi_supply import SupplyError, export_supply

    try:
        result = export_supply(database, supply_id, target)
    except SupplyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("材料导出中断；请保留完整文件并重试，同字节文件会跳过。", err=True)
        raise typer.Exit(130) from None
    typer.echo(
        f"supply_id={result.supply_id} files={len(result.files)} "
        f"created={len(result.created)} result=passed"
    )
