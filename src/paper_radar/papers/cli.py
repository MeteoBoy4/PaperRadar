"""论文事实只读命令;不提供生产写入口。"""

import json
from pathlib import Path
from typing import Annotated

import typer

from paper_radar.backup.cli_support import BatchCommand, BatchGroup
from paper_radar.papers.errors import PaperError
from paper_radar.storage.errors import StorageError

HELP = """\
当前用途：只读查看 DOI 论文当前事实与来源历史；不写入、不调用模型。

参数与选项：show/trace 接受 PAPER_ID、必填 --database；可选 --data-root、
--json、--show-abstract。trace 可用 --verify-source-bytes 只读核验来源字节。

副作用：只读既有数据库；字节核验才访问既有制品根。帮助不连接数据库、不创建目录、不联网。

自动配额：消耗 0 次模型配额。

输出去向：事实写入标准输出；默认隐藏所有摘要，
显式 --show-abstract 才展开；不转储原响应。

常见失败：请先显式 db upgrade 迁移既有库；缺失 ID 请核对，损坏请检查备份。
受控失败退出 1，参数错误退出 2。

示例：paper-radar paper show PAPER_ID --database data/paper-radar.sqlite3
示例：paper-radar paper trace PAPER_ID --database data/paper-radar.sqlite3 --json
"""


class PaperGroup(BatchGroup):
    parameter_error = "论文查询参数不正确；请运行 paper-radar paper --help"
    unknown_command_error = "论文查询子命令不受支持；请使用 show 或 trace"


class PaperCommand(BatchCommand):
    parameter_error = "论文查询参数不正确；请查看该命令 --help"


paper_app = typer.Typer(
    cls=PaperGroup, help=HELP, no_args_is_help=True, rich_markup_mode=None
)
Database = Annotated[Path, typer.Option("--database", help="既有 SQLite 数据库路径")]
DataRoot = Annotated[
    Path | None, typer.Option("--data-root", help="既有制品根（字节核验必填）")
]


def _redact_abstracts(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _redact_abstracts(item) if key != "abstract" else _hide_abstract(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_abstracts(item) for item in value]
    return value


def _hide_abstract(value: object) -> object:
    if isinstance(value, dict):
        field = dict(value)
        abstract = field.get("value")
        if isinstance(abstract, dict):
            field["value"] = {
                key: item for key, item in abstract.items() if key != "text"
            }
        return field
    return value


def _query(
    paper_id: str,
    database: Path,
    data_root: Path | None,
    trace: bool,
    as_json: bool,
    show_abstract: bool,
    verify_source_bytes: bool = False,
) -> None:
    from paper_radar.papers.service import PaperFacts

    try:
        service = PaperFacts(database, data_root)
        result = (
            service.trace(paper_id, verify_source_bytes=verify_source_bytes)
            if trace
            else service.show(paper_id)
        )
        payload: object = result.model_dump(mode="json")
        if not show_abstract:
            payload = _redact_abstracts(payload)
        if not as_json:
            typer.echo("论文来源历史（只读）" if trace else "论文当前事实（只读）")
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    except (PaperError, StorageError) as error:
        typer.echo(f"论文查询失败 [{error.reason.value}]：{error}", err=True)
        raise typer.Exit(1) from None


@paper_app.command("show", cls=PaperCommand, help=HELP)
def show_command(
    paper_id: Annotated[str, typer.Argument(help="论文 UUID")],
    database: Database,
    data_root: DataRoot = None,
    as_json: Annotated[bool, typer.Option("--json", help="受控 JSON 输出")] = False,
    show_abstract: Annotated[
        bool, typer.Option("--show-abstract", help="显式展开摘要")
    ] = False,
) -> None:
    _query(paper_id, database, data_root, False, as_json, show_abstract)


@paper_app.command("trace", cls=PaperCommand, help=HELP)
def trace_command(
    paper_id: Annotated[str, typer.Argument(help="论文 UUID")],
    database: Database,
    data_root: DataRoot = None,
    as_json: Annotated[bool, typer.Option("--json", help="受控 JSON 输出")] = False,
    show_abstract: Annotated[
        bool, typer.Option("--show-abstract", help="显式展开包括未获选候选的摘要")
    ] = False,
    verify_source_bytes: Annotated[
        bool, typer.Option("--verify-source-bytes", help="只读核验来源字节，不转储正文")
    ] = False,
) -> None:
    _query(
        paper_id, database, data_root, True, as_json, show_abstract, verify_source_bytes
    )
