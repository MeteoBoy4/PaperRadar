"""备份的参数与中文输出薄层;完整性由公共服务统一负责。"""

from pathlib import Path
from typing import Annotated

import typer

from paper_radar.backup.cli_support import (
    BatchCommand,
    BatchGroup,
    show_failure,
    show_result,
)
from paper_radar.backup.manifest import BackupError, BackupReason

BACKUP_HELP = """管理自包含备份批次。

当前用途：create 创建数据库与全部已登记制品的备份；verify 只读核对已发布批次。
参数与选项：create 必须显式提供 --database、--data-root、--output；verify 接受批次目录。
副作用：create 在 output 内创建私有 staging，全部验证后发布；
verify 成功和失败都不写批次。
自动配额：不联网、不调用模型，消耗 0 次自动处理配额；帮助不读配置或凭据、不连接数据库。
输出去向：完成批次写入 output；终端仅显示批次 ID、清单 SHA-256、
按 kind 的数量与字节汇总。
常见失败：缺失、损坏、版本不支持、目标冲突或空间不足返回 2；不会覆盖已有批次。
示例：paper-radar backup create --database data/paperradar.sqlite3
        --data-root data --output backups
"""

CREATE_HELP = """创建包含已登记配置材料与制品的自包含备份批次。

当前用途：用 SQLite 在线 backup 固定活动库，复制固定副本的完整登记闭包并全量验证。
参数与选项：必须提供 --database、--data-root、--output；数据根与数据库无包含关系要求。
副作用：只读源库，要求当前 head；output 不存在时按属主权限创建，
在其内部创建唯一 staging。
验证通过后同文件系统原子发布，旧批次包括空目录绝不覆盖；只清理本次自己的失败 staging。
自动配额：不联网、不访问模型，不消耗 Screening、复用升级或精读配额；帮助无外部 I/O。
输出去向：output 下的完成批次；数据库为 journal_mode=DELETE 的独立单文件，
不依赖源 WAL/SHM。
已登记配置材料随数据库保留；不包含 config/ 树、settings.yaml、未登记草稿、
contracts/ 导出目录、
reports/logs。配置文件本身请用 git 保管。
常见失败：旧库须先 db upgrade；内容缺失、损坏、格式不支持、空间或发布失败返回 2。
拒绝 output 位于本 data-root 的 blobs 或 tmp 子树中，不扫描源目录来猜测事实。
示例：paper-radar backup create --database data/paperradar.sqlite3
        --data-root data --output backups
"""

VERIFY_HELP = """只读校验已发布备份批次的全部文件与登记。

当前用途：核对完整 SHA-256、数据库 integrity/foreign key、制品闭包和历史配置回放。
参数与选项：<backup-batch> 是已发布批次目录，不是运行配置快照 ID；不接受 staging。
副作用：不写库、不迁移、不补文件；成功和失败都不改批次字节或目录条目，不访问原数据或配置根。
自动配额：不联网、不调用模型，消耗 0 次自动处理配额；帮助不读配置、凭据或数据库。
输出去向：只写终端，包含批次 ID、清单 SHA-256 以及按 kind 的数量与字节汇总。
常见失败：不支持格式、缺文件、登记损坏、SHA-256 不符或任何清单外条目返回 2，
请保留原批次检查。
示例：paper-radar backup verify backups/20261017T000000Z-1234abcd
"""


class _BackupGroup(BatchGroup):
    parameter_error = "备份参数错误：请查看 paper-radar backup --help。"
    unknown_command_error = "备份命令无效：请查看 paper-radar backup --help。"


class _BackupCommand(BatchCommand):
    parameter_error = (
        "备份参数错误：请显式提供帮助中要求的路径；参见 paper-radar backup --help。"
    )


backup_app = typer.Typer(
    cls=_BackupGroup,
    help=BACKUP_HELP,
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="markdown",
)


@backup_app.command("create", cls=_BackupCommand, help=CREATE_HELP)
def backup_create(
    database: Annotated[
        Path, typer.Option("--database", help="既有且为当前 head 的 SQLite 路径。")
    ],
    data_root: Annotated[
        Path, typer.Option("--data-root", help="已登记不可变制品的数据根。")
    ],
    output: Annotated[
        Path, typer.Option("--output", help="完成批次和 staging 所在输出根。")
    ],
) -> None:
    from paper_radar.backup.service import create_backup

    try:
        show_result(create_backup(database, data_root, output))
    except BackupError as error:
        show_failure("备份", error)
    except KeyboardInterrupt:
        show_failure("备份", BackupError(BackupReason.INTERRUPTED))


@backup_app.command("verify", cls=_BackupCommand, help=VERIFY_HELP)
def backup_verify(
    backup_batch: Annotated[
        Path,
        typer.Argument(
            metavar="<backup-batch>", help="已发布备份批次目录，不是配置快照 ID。"
        ),
    ],
) -> None:
    from paper_radar.backup.service import verify_backup

    try:
        show_result(verify_backup(backup_batch))
    except BackupError as error:
        show_failure("备份", error)
    except KeyboardInterrupt:
        show_failure("备份", BackupError(BackupReason.INTERRUPTED))
