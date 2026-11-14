"""B-E10 恢复冷进程:只读 CLI 与 PDF 闭包,网络/执行不参与。"""

import hashlib
import json
import socket
import ssl  # noqa: F401
import sys
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.experiment.pdf import PdfSamples
from paper_radar.experiment.validation import validate_all


def forbidden(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("external I/O forbidden")


def inventory(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def main() -> None:
    root = Path(sys.argv[1])
    before = inventory(root)
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
        validate_all(root / "database.sqlite3", root)
        samples = PdfSamples(root / "database.sqlite3", root)
        assert len(samples.history()) == 1 and len(samples.samples()) == 1
        first = CliRunner().invoke(app, args)
        assert first.exit_code == 0, (first.output, repr(first.exception))
        second = CliRunner().invoke(app, args)
        assert second.exit_code == 0 and second.stdout == first.stdout
    assert inventory(root) == before
    print(json.dumps(json.loads(first.stdout), ensure_ascii=False))


if __name__ == "__main__":
    main()
