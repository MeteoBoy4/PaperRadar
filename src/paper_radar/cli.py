"""PaperRadar 命令行入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from paper_radar.contracts import (
    ContractExportError,
    ExportOutcome,
    export_frozen_contract,
)

ROOT_HELP = """\
PaperRadar 工程入口。

当前用途：查看已交付能力；当前可安全导出一份 BoundaryOutput 冻结契约。

参数与选项：使用 `--help` 查看命令组；业务操作的参数由子命令明确提供。

副作用：查看帮助不读取配置或凭据，不访问网络，不连接或写入数据库，
也不会创建 data、reports、logs 等业务目录或文件。

自动配额：查看帮助和契约操作消耗 0 次 Screening、复用升级和全文精读配额。

输出去向：帮助写入标准输出；冻结契约只写入 export 的显式目标目录。

常见失败：若 shell 提示找不到命令，请先在仓库中执行 `uv sync --locked`；
若依赖尚未准备好，离线检查会明确失败，不会联网补装。

示例：`paper-radar --help`
"""

CONTRACTS_HELP = """\
管理由权威 Pydantic 模型生成的版本化冻结契约。

当前用途：导出已实现的 `boundary` 契约；本 ticket 不提供只读 check 或批处理。

参数与选项：export 必须明确提供契约名、声明版本和目标目录。

副作用：查看帮助只输出文本；export 仅在目标目录创建不可覆盖的快照。

自动配额：契约命令不访问模型，消耗 0 次自动处理配额。

输出去向：`<目标>/screening/boundary/v1/`，包含 Schema 与哈希清单。

常见失败：未知契约、无效版本、既有快照损坏或冲突、目标不可写均返回非零。

示例：`paper-radar contracts --help`
"""

EXPORT_HELP = """\
从权威 BoundaryOutput 生成并安全发布一份冻结 JSON Schema。

当前用途：只支持 `boundary` 的声明版本 `v1`，一次只导出一份契约。

参数与选项：`--contract` 选择契约，`--version` 选择声明版本，`--target`
选择输出根目录；三项都必须显式提供。

副作用：首次成功会创建版本目录；同版本同内容不改写；任何冲突都拒绝覆盖。

自动配额：不访问网络、数据库或模型，消耗 0 次自动处理配额。

输出去向：目标目录下的 `screening/boundary/v1/schema.json` 和
`manifest.json`。

常见失败：未知选择、版本非法、快照损坏、版本不一致、内容冲突或写入失败。

示例：`paper-radar contracts export --contract boundary --version v1 --target contracts`
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
        typer.Option("--contract", help="受控契约名；当前仅支持 boundary。"),
    ],
    version: Annotated[
        str,
        typer.Option("--version", help="声明版本；当前仅支持 v1。"),
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


def main() -> None:
    """运行 PaperRadar 命令行入口。"""
    app(prog_name="paper-radar")


if __name__ == "__main__":
    main()
