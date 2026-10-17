"""备份与隔离恢复共用的参数脱敏和批次摘要;不加载 I/O 服务。"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal, NoReturn

import typer
from typer.core import TyperCommand, TyperGroup

from paper_radar.backup.manifest import BackupError, BackupResult
from paper_radar.backup.restore_contract import RestoreError, RestoreResult


@contextmanager
def _redact_argument_errors(message: str) -> Iterator[None]:
    try:
        yield
    except (typer.Exit, typer.Abort):
        raise
    except Exception:
        typer.echo(message, err=True)
        raise typer.Exit(2) from None


class BatchGroup(TyperGroup):
    parameter_error: str
    unknown_command_error: str

    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        with _redact_argument_errors(self.parameter_error):
            return super().parse_args(ctx, args)

    def get_command(self, ctx: Any, cmd_name: str) -> Any:
        command = super().get_command(ctx, cmd_name)
        if command is None:
            typer.echo(self.unknown_command_error, err=True)
            raise typer.Exit(2)
        return command


class BatchCommand(TyperCommand):
    parameter_error: str

    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        with _redact_argument_errors(self.parameter_error):
            return super().parse_args(ctx, args)


def show_failure(
    operation: Literal["备份", "恢复"], error: BackupError | RestoreError
) -> NoReturn:
    typer.echo(f"{operation}失败 [{error.reason.value}]：{error}", err=True)
    raise typer.Exit(2) from None


def show_result(result: BackupResult | RestoreResult) -> None:
    typer.echo(f"备份批次：{result.manifest.batch_id}")
    typer.echo(f"清单 SHA-256：{result.manifest_sha256}")
    for kind, count in result.manifest.counts.by_kind.items():
        typer.echo(
            f"{kind}：制品 {count.artifacts}；"
            f"成员 {count.members}；字节 {count.size_bytes}"
        )
