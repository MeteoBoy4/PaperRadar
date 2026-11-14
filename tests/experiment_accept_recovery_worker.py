"""B-E9 恢复查询冷进程:只读真实 CLI,禁止任何 socket。"""

import json
import socket
import ssl  # noqa: F401
import sys
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

from typer.testing import CliRunner

from paper_radar.cli import app


def forbidden(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("external I/O forbidden")


def main() -> None:
    root = Path(sys.argv[1])
    args = [
        "paper",
        "trace",
        sys.argv[2],
        "--database",
        str(root / "database.sqlite3"),
        "--data-root",
        str(root),
        "--snapshot",
        sys.argv[3],
        "--json",
    ]
    with patch.object(socket, "socket", forbidden):
        first = CliRunner().invoke(app, args)
        assert first.exit_code == 0, (first.output, repr(first.exception))
        second = CliRunner().invoke(app, args)
        assert second.exit_code == 0 and second.stdout == first.stdout
    print(json.dumps(json.loads(first.stdout), ensure_ascii=False))


if __name__ == "__main__":
    main()
