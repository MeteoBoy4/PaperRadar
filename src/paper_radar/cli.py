"""PaperRadar 命令行入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from paper_radar.config.cli import config_app, db_app
from paper_radar.contracts import (
    ContractBatchCheckResult,
    ContractBatchExportResult,
    ContractCheckError,
    ContractCheckItemResult,
    ContractCheckOutcome,
    ContractExportError,
    ContractExportItemResult,
    ContractName,
    ContractVersion,
    ExportOutcome,
    check_frozen_contracts,
    export_frozen_contracts,
)
from paper_radar.contracts.schema import _SUPPORTED_CONTRACT_VERSIONS

_EXAMPLE_CONTRACT_NAME = ContractName.BOUNDARY.value
_EXAMPLE_CONTRACT_VERSION = ContractVersion.V1.value
_EXPORT_EXAMPLE = (
    f"paper-radar contracts export --contract {_EXAMPLE_CONTRACT_NAME} "
    f"--version {_EXAMPLE_CONTRACT_VERSION} --target contracts"
)
_CHECK_EXAMPLE = (
    f"paper-radar contracts check --contract {_EXAMPLE_CONTRACT_NAME} "
    f"--version {_EXAMPLE_CONTRACT_VERSION} --target contracts"
)
_CHECK_ALL_EXAMPLE = (
    "paper-radar contracts check --contract boundary "
    "--contract value-prediction --contract reuse-assessment "
    "--contract decision-reasons --version v1 --target contracts"
)
_CONTRACT_CHOICES_HELP = "\n".join(
    f"- `{name.value}`（`{ContractVersion.V1.value}`）" for name in ContractName
)

ROOT_HELP = """\
PaperRadar 工程入口。

当前用途：管理冻结契约；显式迁移配置数据库，检查或编译 Profile 配置快照。
未实现的模型与流程配置会明确显示未就绪。

参数与选项：使用 `--help` 查看命令组；业务操作的参数由子命令明确提供。

副作用：查看帮助不读取配置或凭据，不访问网络，不连接或写入数据库，
也不会创建 data、reports、logs 等业务目录或文件。

自动配额：帮助、契约和配置命令消耗 0 次 Screening、复用升级和全文精读配额。

输出去向：帮助写入标准输出；冻结契约写入 export 目标目录，配置快照写入
--database 指定的既有数据库。

常见失败：若 shell 提示找不到命令，请先在仓库中执行 `uv sync --locked`；
若依赖尚未准备好，离线检查会明确失败，不会联网补装。

示例：`paper-radar --help`

A1 验收：在仓库根目录运行 `./scripts/check-offline`；本次离线证据和独立结论
写入 `verification-runs/`。A1 通过不表示阶段 A 或自动精读已验收。
"""

CONTRACTS_HELP = f"""\
管理由权威 Pydantic 模型生成的版本化冻结契约。

当前用途：导出或只读检查一份或多份已实现契约。多份 check 会逐项报告，
单份失败不会隐藏其他已选契约的结果。

当前支持：
{_CONTRACT_CHOICES_HELP}

参数与选项：export 和 check 都可重复提供 `--contract`，并按上方声明顺序处理。
完整集合须显式列出当前四份契约；两者都必须明确提供声明版本和目标目录。

副作用：查看帮助只输出文本；export 先预检全部已选目标，再逐份创建不可覆盖的
快照；check 只读取既有文件，成功或失败都不写入。批量 export 不承诺跨快照事务。

自动配额：契约命令不访问模型，消耗 0 次自动处理配额。

输出去向：export 写入目标目录内对应版本的子目录；check 按固定字段逐项把结果
写入标准输出或标准错误。

常见失败：未知契约、无效版本、既有快照损坏或冲突、目标不可写均返回非零。
预检失败不会写入；运行中断时完整项保留并逐份报告，修复后原命令重跑即可补齐。

示例：`paper-radar contracts --help`
"""

EXPORT_HELP = f"""\
从权威 Pydantic 定义生成并安全发布一份或多份冻结 JSON Schema。

当前用途：重复提供 `--contract` 可在一次命令中导出多份契约；无论参数顺序如何，
都按下方声明顺序预检和发布。

当前支持的契约与声明版本：
{_CONTRACT_CHOICES_HELP}
当前支持的声明版本：{_SUPPORTED_CONTRACT_VERSIONS}。

参数与选项：`--contract` 可重复选择契约，每份至多一次；`--version` 选择声明
版本，`--target` 选择输出根目录；三项都必须显式提供。

副作用：写入前预检全部选择的损坏、版本不一致和内容冲突；预检失败不写入。
开始发布后逐份安全落盘，不承诺跨快照事务；中断前的完整项保留，半快照不算成功。

自动配额：不访问网络、数据库或模型，消耗 0 次自动处理配额。

输出去向：目标目录内各对应版本子目录的 `schema.json` 和 `manifest.json`；
每份输出“已创建”“未改写”或“未完成”。

常见失败：未知/重复选择、版本非法、快照损坏、版本不一致、内容冲突或写入失败；
失败返回 2，修复后使用原命令重跑会保留完整项并补齐缺失项。

示例：`{_EXPORT_EXAMPLE}`

批量示例：`paper-radar contracts export --contract boundary --contract value-prediction
--contract reuse-assessment --contract decision-reasons --version v1 --target contracts`
"""

CHECK_HELP = f"""\
只读比较一份或多份既有冻结契约与当前权威定义，逐项报告一致或失败原因。

当前用途：重复 `--contract` 可检查多份契约；完整集合必须显式列出下方四份，
不会因未来新增契约而静默扩大。单份失败不会中断其余检查。

当前支持的契约与声明版本：
{_CONTRACT_CHOICES_HELP}
当前支持的声明版本：{_SUPPORTED_CONTRACT_VERSIONS}。

参数与选项：`--contract` 可重复选择契约，每份至多一次；`--version` 选择声明
版本，`--target` 选择既有快照的根目录；三项都必须显式提供。

副作用：只读取目标目录内的既有文件；成功或失败都不写入，也不创建目录。

自动配额：不访问网络、数据库或模型，消耗 0 次自动处理配额。

输出去向：每项固定输出 `contract`、`version`、`result`、`error_category` 和中文
说明；结果只写入标准输出或标准错误，不产生文件。全部已选契约一致才返回 0。

常见失败：未知或重复选择会在执行前整体拒绝；快照缺失、不可读取、损坏、版本
不一致或内容漂移会逐项报告，全部检查完成后返回 2。

示例：`{_CHECK_EXAMPLE}`

整组示例：`{_CHECK_ALL_EXAMPLE}`
"""

app = typer.Typer(
    name="paper-radar",
    help=ROOT_HELP,
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="markdown",
)
contracts_app = typer.Typer(
    name="contracts",
    help=CONTRACTS_HELP,
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="markdown",
)
app.add_typer(contracts_app, name="contracts")
app.add_typer(db_app, name="db")
app.add_typer(config_app, name="config")


def _write_export_item(item: ContractExportItemResult) -> None:
    identity = f"{item.name.value} {item.version.value}"
    if item.outcome in (ExportOutcome.CREATED, ExportOutcome.UNCHANGED):
        typer.echo(
            f"{identity}：{item.message_zh}："
            f"{item.snapshot_dir}（SHA-256: {item.schema_sha256}）"
        )
    elif item.outcome is ExportOutcome.FAILED:
        category = (
            item.error_category.value if item.error_category is not None else "none"
        )
        typer.echo(f"{identity}：未完成 [{category}]：{item.message_zh}", err=True)
    else:
        typer.echo(f"{identity}：未完成：{item.message_zh}", err=True)


def _write_batch_export_result(result: ContractBatchExportResult) -> None:
    for item in result.items:
        _write_export_item(item)


def _write_check_item(result: ContractCheckItemResult, *, err: bool) -> None:
    error_category = (
        result.error_category.value if result.error_category is not None else "none"
    )
    if result.outcome is ContractCheckOutcome.PASSED:
        message = (
            f"{result.message_zh}{result.name.value} {result.version.value} "
            f"{result.snapshot_dir}（SHA-256: {result.schema_sha256}）"
        )
    else:
        message = result.message_zh
    typer.echo(
        f"contract={result.name.value} version={result.version.value} "
        f"result={result.outcome.value} error_category={error_category} "
        f"message_zh={message}",
        err=err,
    )


def _write_batch_check_result(result: ContractBatchCheckResult) -> None:
    for item in result.items:
        _write_check_item(item, err=not result.passed)


@contracts_app.command("export", help=EXPORT_HELP)
def export_contract_command(
    contract: Annotated[
        list[str],
        typer.Option(
            "--contract",
            help="可重复的受控契约名；完整选择见上方当前支持清单。",
        ),
    ],
    version: Annotated[
        str,
        typer.Option(
            "--version",
            help=f"声明版本；当前支持：{_SUPPORTED_CONTRACT_VERSIONS}。",
        ),
    ],
    target: Annotated[
        Path,
        typer.Option("--target", help="冻结契约输出根目录。"),
    ],
) -> None:
    """预检后导出一份或多份不可覆盖的冻结契约。"""
    try:
        result = export_frozen_contracts(contract, version, target)
    except ContractExportError as error:
        typer.echo(f"导出失败 [{error.category.value}]：{error}", err=True)
        raise typer.Exit(code=2) from None

    _write_batch_export_result(result)
    if not result.passed:
        raise typer.Exit(code=2)


@contracts_app.command("check", help=CHECK_HELP)
def check_contract_command(
    contract: Annotated[
        list[str],
        typer.Option(
            "--contract",
            help="可重复的受控契约名；完整选择见上方当前支持清单。",
        ),
    ],
    version: Annotated[
        str,
        typer.Option(
            "--version",
            help=f"声明版本；当前支持：{_SUPPORTED_CONTRACT_VERSIONS}。",
        ),
    ],
    target: Annotated[
        Path,
        typer.Option("--target", help="冻结契约检查的既有快照根目录（只读）。"),
    ],
) -> None:
    """只读检查一份或多份冻结契约是否漂移。"""
    try:
        result = check_frozen_contracts(contract, version, target)
    except ContractCheckError as error:
        typer.echo(f"检查失败 [{error.category.value}]：{error}", err=True)
        raise typer.Exit(code=2) from None

    _write_batch_check_result(result)
    if not result.passed:
        raise typer.Exit(code=2)


def main() -> None:
    """运行 PaperRadar 命令行入口。"""
    app(prog_name="paper-radar")


if __name__ == "__main__":
    main()
