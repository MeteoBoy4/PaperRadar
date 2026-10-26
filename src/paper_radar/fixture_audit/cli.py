"""显式登记与只读查询;帮助不访问业务资源。"""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from paper_radar.backup.cli_support import BatchCommand, BatchGroup
from paper_radar.fixture_audit.errors import FixtureError
from paper_radar.fixture_audit.models import DeclarationCheck
from paper_radar.fixture_audit.service import FixtureAudit
from paper_radar.storage.errors import StorageError

HELP = """\
当前用途：登记版本化 fixture 声明、只读核对原字节并查询完整历史。
参数：register/check 接受声明文件，show 接受记录 ID；均显式提供 --database。
register 需 --data-root；list 可用 --history，所有命令支持 --json。
副作用：register 追加 SQLite 登记；check/list/show 只读，不迁移、不创建业务目录。
帮助不访问网络、数据库、凭据或源文件。历史与合成材料不代表真实来源已核实。
自动配额：0 次模型调用，不运行真实来源、浏览器或 Docling。
输出去向：查询结果写标准输出，受控错误写标准错误；错误退出 1，参数错误退出 2。
常见失败：数据库缺失时先显式 db upgrade；原字节漂移须新声明版本，不能覆盖。
示例：paper-radar fixture register fixtures/a10/historical-v1.json
  --database data/paper-radar.sqlite3 --data-root data
示例：paper-radar fixture list --database data/paper-radar.sqlite3 --history --json
"""


class FixtureGroup(BatchGroup):
    parameter_error = "样本命令参数不正确；请查看 paper-radar fixture --help"
    unknown_command_error = "样本子命令不支持；请使用 register/check/list/show"


class FixtureCommand(BatchCommand):
    parameter_error = "样本命令参数不正确；请查看该命令 --help"


fixture_app = typer.Typer(
    cls=FixtureGroup, help=HELP, no_args_is_help=True, rich_markup_mode=None
)
Database = Annotated[
    Path, typer.Option("--database", help="既有 SQLite 数据库，不隐式迁移")
]
JsonOutput = Annotated[bool, typer.Option("--json", help="输出结构化 JSON")]


def _run(operation: Callable[[], object], json_output: bool) -> object:
    import json

    try:
        result = operation()
    except (FixtureError, StorageError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    if isinstance(result, BaseModel):
        value: object = result.model_dump(mode="json")
    elif isinstance(result, tuple):
        value = [item.model_dump(mode="json") for item in result]
    else:
        value = result
    if json_output:
        typer.echo(json.dumps(value, ensure_ascii=False))
    elif isinstance(result, DeclarationCheck):
        typer.echo(f"声明核对：{result.status}；源文件可用：{result.source_available}")
    else:
        typer.echo("样本登记历史（byte_verified 仅指声明字节，不证明来源实测）")
        typer.echo(json.dumps(value, ensure_ascii=False, indent=2))
    return result


@fixture_app.command(
    "register", cls=FixtureCommand, help="显式追加声明原字节。\n\n" + HELP
)
def register_command(
    source: Annotated[Path, typer.Argument(help="版本化 JSON 声明文件")],
    database: Database,
    data_root: Annotated[
        Path, typer.Option("--data-root", help="制品根；本命令不创建目录")
    ],
    json_output: JsonOutput = False,
) -> None:
    _run(lambda: FixtureAudit(database, data_root).register(source), json_output)


@fixture_app.command(
    "check", cls=FixtureCommand, help="只读比对声明与已登记字节。\n\n" + HELP
)
def check_command(
    source: Annotated[Path, typer.Argument(help="待核对声明文件")],
    database: Database,
    json_output: JsonOutput = False,
) -> None:
    result = _run(lambda: FixtureAudit(database).check(source), json_output)
    if isinstance(result, DeclarationCheck) and result.status != "byte_verified":
        raise typer.Exit(1)


@fixture_app.command(
    "list", cls=FixtureCommand, help="只读列出当前样本或历史。\n\n" + HELP
)
def list_command(
    database: Database,
    history: Annotated[
        bool, typer.Option("--history", help="包含已被替换的完整历史")
    ] = False,
    json_output: JsonOutput = False,
) -> None:
    _run(lambda: FixtureAudit(database).list(history=history), json_output)


@fixture_app.command(
    "show", cls=FixtureCommand, help="只读查看指定样本记录。\n\n" + HELP
)
def show_command(
    record_id: Annotated[str, typer.Argument(help="显式样本记录 ID")],
    database: Database,
    json_output: JsonOutput = False,
) -> None:
    _run(lambda: FixtureAudit(database).show(record_id), json_output)
