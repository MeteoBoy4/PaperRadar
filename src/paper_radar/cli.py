"""PaperRadar 命令行入口。"""

from __future__ import annotations

import typer

ROOT_HELP = """\
PaperRadar 工程入口。

当前用途：确认 PaperRadar 已正确安装，并查看当前已经交付的命令能力。
本 ticket 尚未提供论文处理命令；后续能力会在各自验收完成后注册。

参数与选项：当前没有位置参数；使用 `--help` 显示本说明。

副作用：查看帮助不会读取配置或凭据，不访问网络，不连接或写入数据库，
也不会创建 data、reports、logs 等业务目录或文件。

自动配额：查看帮助消耗 0 次 Screening、复用升级和全文精读配额。

输出去向：帮助文本只写入标准输出，不生成报告或业务制品。

常见失败：若 shell 提示找不到命令，请先在仓库中执行 `uv sync --locked`；
若依赖尚未准备好，离线检查会明确失败，不会联网补装。

示例：`paper-radar --help`
"""

app = typer.Typer(
    name="paper-radar",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


@app.command(help=ROOT_HELP)
def root() -> None:
    """显示当前已经交付的 PaperRadar 命令能力。"""


def main() -> None:
    """运行 PaperRadar 命令行入口。"""
    app(prog_name="paper-radar")


if __name__ == "__main__":
    main()
