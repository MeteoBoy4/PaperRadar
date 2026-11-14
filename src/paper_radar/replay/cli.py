"""脱网回放入口:冷帮助不加载恢复或隔离服务。"""

from pathlib import Path
from typing import Annotated

import typer

from paper_radar.backup.cli_support import BatchCommand

REPLAY_HELP = """在实际 OS 隔离与禁网条件下核验恢复内容闭包。

参数：--restored 仅接受 restore verify --replay-container 的产物；
--original-database、--original-data-root、--original-config-root 必填，
--original-material-root 可重复，须列全原材料、安装与模型目录（不提供认证目录）。
副作用：数据库与 contents 只读，不迁移、激活配置、回收租约或执行任务；
仅在恢复封装内独立 views 重渲染全部固定日报、单篇报告及暴露清单，不建日志。
自动配额：0；不联网、不调用或安装 Pi、OAuth、Docling，不依赖模型缓存；帮助无外部 I/O。
输出去向：私有视图写 restored/views；终端仅显示受控计数与隔离结果。
常见失败：来源不符、缺件/篡改、路径重叠或隔离能力不足返回 2，成功 0，中断 130；
保留副本，用匹配程序检查 restore verify 与 Linux x86_64 Landlock/seccomp 支持后重试。
示例：paper-radar replay --restored demo/restore/session
 --original-database demo/paper-radar.sqlite3 --original-data-root demo/data
 --original-config-root demo/config --original-material-root demo/pi-materials
 --original-material-root demo/pi-install --original-material-root demo/models
"""


class ReplayCommand(BatchCommand):
    parameter_error = (
        "invalid_arguments：回放参数不完整；请查看 paper-radar replay --help。"
    )


def replay_command(
    restored: Annotated[Path, typer.Option(help="restore verify 生成的回放封装。")],
    original_database: Annotated[
        Path, typer.Option(help="原业务数据库文件；仅探测打开权限，不读取内容。")
    ],
    original_data_root: Annotated[Path, typer.Option(help="原制品数据树。")],
    original_config_root: Annotated[Path, typer.Option(help="原配置树。")],
    original_material_root: Annotated[
        list[Path], typer.Option(help="原材料/安装/模型树；重复列全，勿指定认证树。")
    ],
) -> None:
    import json

    from paper_radar.replay.contract import ReplayError
    from paper_radar.replay.service import replay

    try:
        result = replay(
            restored,
            (
                original_database,
                original_data_root,
                original_config_root,
                *original_material_root,
            ),
        )
        typer.echo(json.dumps(result, sort_keys=True, ensure_ascii=False))
    except ReplayError as error:
        typer.echo(
            f"{error.reason}：回放未完成；请保留副本，检查来源、完整性与隔离部署后重试。",
            err=True,
        )
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("interrupted：回放中断；请保留副本并显式重试。", err=True)
        raise typer.Exit(130) from None
