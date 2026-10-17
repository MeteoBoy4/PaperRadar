"""验证性恢复的薄 CLI;帮助仅加载纯类型与静态中文文本。"""

from pathlib import Path
from typing import Annotated

import typer

from paper_radar.backup.cli_support import BatchCommand, BatchGroup, show_result
from paper_radar.backup.restore_contract import RestoreError, RestoreReason

RESTORE_HELP = """向空隔离位置验证性恢复备份批次。

当前用途：restore verify 会写入完整副本，并验证历史配置和全部制品；不激活配置或任务。
参数与选项：<backup-batch> 是已发布批次目录，不是运行配置快照 ID；必须提供 --target。
副作用：在目标父目录临时创建唯一隐藏 staging，全量校验后原子发布；
父目录须已存在，目标可以不存在或为非符号链接的空目录。
自动配额：不联网、不调用模型，消耗 0 次自动处理配额；帮助不读配置、凭据或数据库。
输出去向：完整副本写入 target；终端仅显示批次 ID、清单 SHA-256 和按 kind 汇总。
常见失败：批次损坏、目标非空/为链接/位于批次内、复制或发布失败返回 2；中断非零。
示例：paper-radar restore verify backups/20261017T000000Z-1234abcd --target restored
"""

RESTORE_VERIFY_HELP = """向 --target 写入完整副本并验证，不是只读校验。

当前用途：从已发布备份批次复制并核验数据库、历史配置与全部已登记制品，脱离原目录查询。
参数与选项：<backup-batch> 是备份批次目录，不是运行配置快照 ID；--target 必须显式提供。
副作用：会写入完整副本，并在目标父目录临时创建唯一隐藏 staging；
父目录须已存在，目标只能不存在或为非符号链接的空目录，不覆盖非空目标。
副本保留 DELETE 单文件模式，不自动升级、激活快照或启动任务；
要作为工作库需另行 db upgrade。
自动配额：不联网、不调用模型、不安装 Pi，不消耗自动处理配额；帮助无外部 I/O。
输出去向：恢复副本写入 target；终端只显示批次 ID、清单 SHA-256
和按 kind 的数量/字节汇总。
常见失败：不接受 staging、损坏或清单外条目；拒绝批次内目标、符号链接和非空目录。
错误返回 2，中断非零；仅清理本次 staging，强杀残留由人工处理。
示例：paper-radar restore verify backups/20261017T000000Z-1234abcd --target restored
"""


class _RestoreGroup(BatchGroup):
    parameter_error = "恢复参数错误：请查看 paper-radar restore --help。"
    unknown_command_error = "恢复命令无效：请查看 paper-radar restore --help。"


class _RestoreCommand(BatchCommand):
    parameter_error = (
        "恢复参数错误：请提供备份批次目录与 --target；"
        "参见 paper-radar restore verify --help。"
    )


restore_app = typer.Typer(
    cls=_RestoreGroup,
    help=RESTORE_HELP,
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="markdown",
)


@restore_app.command("verify", cls=_RestoreCommand, help=RESTORE_VERIFY_HELP)
def restore_verify(
    backup_batch: Annotated[
        Path,
        typer.Argument(
            metavar="<backup-batch>", help="已发布备份批次目录，不是配置快照 ID。"
        ),
    ],
    target: Annotated[
        Path,
        typer.Option(
            "--target", help="完整副本目标；父目录须存在，目标须为空或不存在。"
        ),
    ],
) -> None:
    from paper_radar.backup import restore_backup

    try:
        show_result(restore_backup(backup_batch, target))
    except RestoreError as error:
        typer.echo(f"恢复失败 [{error.reason.value}]：{error}", err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        interrupted = RestoreError(RestoreReason.INTERRUPTED)
        typer.echo(f"恢复失败 [{interrupted.reason.value}]：{interrupted}", err=True)
        raise typer.Exit(2) from None
