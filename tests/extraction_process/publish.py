"""经真实公共服务发布正文成员的子进程。"""

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

from paper_radar.storage.artifacts import ArtifactStore
from tests.extraction_support import PAYLOADS, chunked

values = dict(PAYLOADS)
if sys.argv[3] == "variant":
    values["reading"] = b"PRIVATE_OTHER_READING"
members = chunked(values)
if os.environ["A3_EXTRACTION_PHASE"] == "temporary":

    def temporary_chunks() -> Iterator[bytes]:
        yield b"PRI"
        os.write(int(os.environ["A3_READY_FD"]), b"R")
        os.read(int(os.environ["A3_RELEASE_FD"]), 1)
        yield values["document"][3:]

    members["document"] = temporary_chunks()
record = ArtifactStore(Path(sys.argv[1]), Path(sys.argv[2])).publish_artifact(
    "extraction", members
)
print(json.dumps({"artifact_id": record.artifact_id, "created_at": record.created_at}))
