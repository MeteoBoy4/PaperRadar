"""恢复独立事实视图与真实子进程支撑,不重写配置或制品身份算法。"""

import os
import select
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from paper_radar.config import (
    list_config_snapshots,
    load_config_snapshot,
    project_config,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.config_transaction_support import config_facts


def history_view(database: Path, data_root: Path) -> dict[str, Any]:
    summaries = list_config_snapshots(database)
    snapshots = []
    for summary in summaries:
        assert summary.created_at is not None
        snapshot = load_config_snapshot(database, summary.snapshot_id)
        semantics = project_config(snapshot)
        snapshots.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "created_at": summary.created_at.isoformat(),
                "payload": snapshot.payload_json,
                "projections": {
                    stage.value: {
                        "id": projection.projection_id,
                        "payload": projection.payload_json,
                    }
                    for stage, projection in semantics.projections.items()
                },
                "baseline": {
                    "id": semantics.baseline.baseline_id,
                    "payload": semantics.baseline.payload_json,
                },
            }
        )
    store = ArtifactStore(database, data_root)
    artifacts = [
        {
            "artifact_id": record.artifact_id,
            "kind": record.kind,
            "format_version": record.format_version,
            "created_at": record.created_at,
            "members": [member.model_dump() for member in record.members],
            "bytes_hex": {
                role: raw.hex()
                for role, raw in store.read_artifact(record.artifact_id).items()
            },
        }
        for record in store.list_artifacts()
    ]
    return {
        "snapshots": snapshots,
        "config_facts": [
            [
                [value.hex() if isinstance(value, bytes) else value for value in row]
                for row in table
            ]
            for table in config_facts(database)
        ],
        "artifacts": artifacts,
    }


@contextmanager
def paused_restore(
    batch: Path, target: Path, phase: str
) -> Iterator[tuple[subprocess.Popen[str], int]]:
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()
    process = subprocess.Popen(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(target),
        ],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "restore_process"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "A3_RESTORE_PHASE": phase,
            "A3_READY_FD": str(ready_write),
            "A3_RELEASE_FD": str(release_read),
        },
        pass_fds=(ready_write, release_read),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    os.close(ready_write)
    os.close(release_read)
    try:
        readable, _, _ = select.select([ready_read], [], [], 15)
        assert readable, "恢复子进程未到达文件系统屏障"
        assert os.read(ready_read, 1) == b"R", "恢复子进程提前退出"
        yield process, release_write
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=15)
        os.close(ready_read)
        os.close(release_write)
