"""恢复冷进程:仅持久成员/人工审阅,拒绝 SDK 与网络,不创建日志。"""

import json
import socket
import ssl  # noqa: F401
import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from paper_radar.body import BodyService
from paper_radar.cli import app
from paper_radar.experiment.layout import LayoutReviews
from paper_radar.experiment.validation import validate_all
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.storage.artifacts import ArtifactStore
from tests.experiment_pdf_recovery_worker import forbidden, inventory


def main() -> None:
    root = Path(sys.argv[1])
    before = inventory(root)
    database = root / "database.sqlite3"

    def audit(event: str, args: tuple[object, ...]) -> None:
        if (
            event == "import"
            and args
            and str(args[0]).split(".")[0] in {"docling", "torch", "pypdfium2", "PIL"}
        ):
            raise AssertionError("SDK import forbidden")

    sys.addaudithook(audit)
    with patch.object(socket, "socket", forbidden):
        validate_all(database, root)
        records = LayoutReviews(database, root).history(sys.argv[2])
        assert len(records) == 1 and records[0]["reviewer"] == "owner"
        body = BodyService(database, root).extractions(sys.argv[2])[0]
        assert body.identity is not None and body.artifact_id is not None
        replayed = FulltextArtifacts(ArtifactStore(database, root)).lookup(
            body.artifact_id, body.identity, "e000002"
        )
        assert replayed[0].text == "Exact source α = 2."
        result = CliRunner().invoke(
            app,
            [
                "paper",
                "trace",
                sys.argv[2],
                "--database",
                str(database),
                "--data-root",
                str(root),
                "--snapshot",
                sys.argv[3],
                "--json",
            ],
        )
        assert result.exit_code == 0, (result.output, repr(result.exception))
    assert inventory(root) == before
    print(json.dumps(json.loads(result.stdout), ensure_ascii=False))


if __name__ == "__main__":
    main()
