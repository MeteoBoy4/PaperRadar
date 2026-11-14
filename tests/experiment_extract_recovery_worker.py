"""B-E11 恢复冷进程;禁网络/模型,重建 trace 与逐字 evidence。"""

import json
import socket
import ssl  # noqa: F401
import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from paper_radar.body import BodyService
from paper_radar.cli import app
from paper_radar.experiment.extraction import Extractions
from paper_radar.experiment.validation import validate_all
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.storage.artifacts import ArtifactStore
from tests.experiment_pdf_recovery_worker import forbidden, inventory


def main() -> None:
    root = Path(sys.argv[1])
    before = inventory(root)
    database = root / "database.sqlite3"
    with patch.object(socket, "socket", forbidden):
        validate_all(database, root)
        records = Extractions(database, root).history(sys.argv[2])
        assert len(records) == 1
        body = BodyService(database, root).extractions(sys.argv[2])[0]
        assert body.artifact_id is not None and body.identity is not None
        sources = FulltextArtifacts(ArtifactStore(database, root)).lookup(
            body.artifact_id, body.identity, "e000002"
        )
        assert sources[0].text == "Exact source α = 2."
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
