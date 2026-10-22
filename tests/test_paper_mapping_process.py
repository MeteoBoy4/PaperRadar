"""真实映射进程:一致读屏障、跨 cwd/hashseed 与只读证明边界。"""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from tests.a3_process_support import paused_subprocess
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

READ = """
import json, os, sys
from pathlib import Path
from paper_radar.papers import PaperFacts
os.chdir(sys.argv[4])
selector = ({"version_id": sys.argv[5], "revision_no": 1}
            if len(sys.argv) > 5 else {"paper_id": sys.argv[2]})
r = PaperFacts(Path(sys.argv[1])).map_screening_inputs(
    snapshot_id=sys.argv[3], **selector
)
assert r.evidence and r.boundary.value and r.value.value
print(json.dumps({
    "revision": r.evidence.revision_no,
    "fields": sorted(r.evidence.fields),
    "boundary": r.boundary.value.fingerprint,
    "value": r.value.value.fingerprint,
    "selection": (r.evidence.selection.selection_id
                  if r.evidence.selection else None)
}, sort_keys=True))
"""


def test_mapping_has_one_read_view_across_concurrent_commit(tmp_path: Path) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    before = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert before.boundary.value and before.value.value and before.evidence
    assert saved.paper_id
    with paused_subprocess(
        [
            sys.executable,
            "-c",
            READ,
            str(database),
            saved.paper_id,
            snapshot.snapshot_id,
            str(tmp_path),
        ],
        Path(__file__).parent / "paper_mapping_process",
        {"MAPPING_PAUSE": "1", "MAPPING_FORBIDDEN": str(tmp_path / "data")},
        "映射进程未到达一致读屏障",
        "映射进程提前退出",
    ) as (reader, release):
        updated = service.submit(
            observation(
                payload=b"concurrent update",
                observed_at=datetime(2026, 2, 1, tzinfo=UTC),
                fields=screening_fields("New title", "New abstract"),
            )
        )
        assert updated.status == "retained" and updated.revision_no == 2
        os.write(release, b"G")
        stdout, stderr = reader.communicate(timeout=15)
        assert reader.returncode == 0, stderr
        result = json.loads(stdout)
    assert result["revision"] == 1
    assert result["boundary"] == before.boundary.value.fingerprint
    assert result["value"] == before.value.value.fingerprint
    assert result["selection"] == before.evidence.selection.selection_id  # type: ignore[union-attr]
    after = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert after.evidence and after.evidence.revision_no == 2
    assert after.value.value and after.value.value.fingerprint != result["value"]


def test_cross_process_cwd_hashseed_and_source_io_guard(tmp_path: Path) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(
        observation(
            fields=screening_fields(
                "private-title-sentinel", "private-abstract-sentinel"
            )
        )
    )
    assert saved.paper_id
    before = service.trace(saved.paper_id)
    with closing(sqlite3.connect(database)) as connection:
        dump = tuple(connection.iterdump())
    files = {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if not path.name.endswith(("-wal", "-shm"))
    }
    assert saved.version_id
    outputs = []
    for seed, cwd in (("1", tmp_path), ("27", tmp_path / "config")):
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                READ,
                str(database),
                saved.paper_id,
                snapshot.snapshot_id,
                str(cwd),
                saved.version_id,
            ],
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": os.pathsep.join(
                    (
                        str(Path(__file__).parent / "paper_mapping_process"),
                        str(Path(__file__).parents[1]),
                    )
                ),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": seed,
                "MAPPING_FORBIDDEN": str(tmp_path / "data"),
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        assert child.returncode == 0, child.stderr
        assert "private" not in child.stdout + child.stderr
        outputs.append(json.loads(child.stdout))
    assert outputs[0] == outputs[1]
    with closing(sqlite3.connect(database)) as connection:
        assert tuple(connection.iterdump()) == dump
    assert service.trace(saved.paper_id) == before
    assert {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if not path.name.endswith(("-wal", "-shm"))
    } == files
    # data_root is not required and never created by mapping.
    nonexistent = tmp_path / "never-created"
    mapped = PaperFacts(database, nonexistent).map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert mapped.value.value and mapped.evidence
    assert mapped.evidence.source_bytes_verified is False
    assert not nonexistent.exists()
    assert "private" not in repr(mapped) + repr(mapped.evidence)
