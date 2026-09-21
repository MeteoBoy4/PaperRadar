"""PaperRadar 命令行入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from paper_radar.contracts import (
    ContractCheckError,
    ContractExportError,
    ContractName,
    ContractVersion,
    ExportOutcome,
    check_frozen_contract,
    export_frozen_contract,
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
_CONTRACT_CHOICES_HELP = "\n".join(
    f"- `{name.value}`（`{ContractVersion.V1.value}`）" for name in ContractName
)

ROOT_HELP = """\
PaperRadar 工程入口。

当前用途：查看已交付能力；当前可安全地逐份导出或只读检查四种 Screening
冻结契约。

参数与选项：使用 `--help` 查看命令组；业务操作的参数由子命令明确提供。

副作用：查看帮助不读取配置或凭据，不访问网络，不连接或写入数据库，
也不会创建 data、reports、logs 等业务目录或文件。

自动配额：查看帮助和契约操作消耗 0 次 Screening、复用升级和全文精读配额。

输出去向：帮助写入标准输出；冻结契约只写入 export 的显式目标目录。

常见失败：若 shell 提示找不到命令，请先在仓库中执行 `uv sync --locked`；
若依赖尚未准备好，离线检查会明确失败，不会联网补装。

示例：`paper-radar --help`
"""

CONTRACTS_HELP = f"""\
管理由权威 Pydantic 模型生成的版本化冻结契约。

当前用途：导出已实现的契约，以及只读检查单份既有快照是否漂移；每次只选择
一份，不提供批量导出或汇总。

当前支持：
{_CONTRACT_CHOICES_HELP}

参数与选项：export 与 check 都必须明确提供契约名、声明版本和目标目录。

副作用：查看帮助只输出文本；export 仅在目标目录创建不可覆盖的快照；
check 只读取既有文件，成功或失败都不写入。

自动配额：契约命令不访问模型，消耗 0 次自动处理配额。

输出去向：export 写入目标目录内对应版本的子目录；check 只把结果写入标准
输出和标准错误。

常见失败：未知契约、无效版本、既有快照损坏或冲突、目标不可写均返回非零。

示例：`paper-radar contracts --help`
"""

EXPORT_HELP = f"""\
从权威 Pydantic 定义生成并安全发布一份冻结 JSON Schema。

当前用途：一次只导出一份已经实现的契约。

当前支持的契约与声明版本：
{_CONTRACT_CHOICES_HELP}
当前支持的声明版本：{_SUPPORTED_CONTRACT_VERSIONS}。

参数与选项：`--contract` 选择契约，`--version` 选择声明版本，`--target`
选择输出根目录；三项都必须显式提供。

副作用：首次成功会创建版本目录；同版本同内容不改写；任何冲突都拒绝覆盖。

自动配额：不访问网络、数据库或模型，消耗 0 次自动处理配额。

输出去向：目标目录内对应版本子目录的 `schema.json` 和 `manifest.json`。

常见失败：未知选择、版本非法、快照损坏、版本不一致、内容冲突或写入失败。

示例：`{_EXPORT_EXAMPLE}`
"""

CHECK_HELP = f"""\
只读比较一份既有冻结契约与当前权威定义，报告缺失、损坏、版本或内容漂移。

当前用途：检查单份已经实现的契约；不修复、不刷新、不创建任何文件。

当前支持的契约与声明版本：
{_CONTRACT_CHOICES_HELP}
当前支持的声明版本：{_SUPPORTED_CONTRACT_VERSIONS}。

参数与选项：`--contract` 选择契约，`--version` 选择声明版本，`--target`
选择既有快照的根目录；三项都必须显式提供。

副作用：只读取目标目录内的既有文件；成功或失败都不写入，也不创建目录。

自动配额：不访问网络、数据库或模型，消耗 0 次自动处理配额。

输出去向：结果只写入标准输出和标准错误，不产生文件。

常见失败：快照缺失、不可读取、损坏、版本不一致或内容漂移；均返回非零。

示例：`{_CHECK_EXAMPLE}`
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


@contracts_app.command("export", help=EXPORT_HELP)
def export_contract_command(
    contract: Annotated[
        str,
        typer.Option(
            "--contract",
            help="受控契约名；完整选择见当前用途。",
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
    """导出一份不可覆盖的冻结契约。"""
    try:
        result = export_frozen_contract(contract, version, target)
    except ContractExportError as error:
        typer.echo(f"导出失败 [{error.category.value}]：{error}", err=True)
        raise typer.Exit(code=2) from None

    if result.outcome is ExportOutcome.CREATED:
        status = "已创建冻结契约"
    else:
        status = "冻结契约内容一致，未改写"
    typer.echo(f"{status}：{result.snapshot_dir}（SHA-256: {result.schema_sha256}）")


@contracts_app.command("check", help=CHECK_HELP)
def check_contract_command(
    contract: Annotated[
        str,
        typer.Option(
            "--contract",
            help="受控契约名；完整选择见当前用途。",
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
    """只读检查一份冻结契约是否漂移。"""
    try:
        result = check_frozen_contract(contract, version, target)
    except ContractCheckError as error:
        typer.echo(f"检查失败 [{error.category.value}]：{error}", err=True)
        raise typer.Exit(code=2) from None

    typer.echo(
        f"冻结契约一致：{result.name.value} {result.version.value} "
        f"{result.snapshot_dir}（SHA-256: {result.schema_sha256}）"
    )


def main() -> None:
    """运行 PaperRadar 命令行入口。"""
    app(prog_name="paper-radar")


if __name__ == "__main__":
    main()
