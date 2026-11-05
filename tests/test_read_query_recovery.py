"""D1 两轴、语言、降级和未结算预算的异地冷恢复。"""

import json
import os
import subprocess
from pathlib import Path

from paper_radar.backup import create_backup
from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadAnalysis, ReadTasks
from tests.no_extra_runtime import no_extra_python as no_extra_python
from tests.pi_rpc_source_support import NOW
from tests.read_queries_support import changed_profile, query_projection, successful
from tests.read_tasks_support import ready, valid_candidate


def test_two_axes_languages_and_discards_restore_without_sdk_or_writes(
    tmp_path: Path, no_extra_python: Path
) -> None:
    original = tmp_path / "source"
    data, _, extraction = ready(original)
    tasks = ReadTasks(data.database, data.data_root, clock=lambda: NOW)
    first = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    bad = valid_candidate(
        main_findings=[
            {
                "statement": "丢弃内容。",
                "evidence": [{"evidence_id": "bad-private-id"}],
            },
            {"statement": "有效内容。", "evidence": [{"evidence_id": "e000002"}]},
        ]
    )
    tasks.submit_test(tasks.claim(first.task_id), bad)
    result = tasks.submit_test(tasks.claim(first.task_id), bad)
    assert isinstance(result, ReadAnalysis)
    successful(tasks, data, extraction.fingerprint, "en", language="en")
    reference = changed_profile(data)
    pending = tasks.register(
        data.paper_id,
        snapshot_id=reference,
        extraction_fingerprint=extraction.fingerprint,
        request_id="pending",
    )
    tasks.claim(pending.task_id)
    expected = {
        "paper": data.paper_id,
        "snapshot": reference,
        "analysis": result.analysis_id,
        "projection": query_projection(
            ReadQueries(data.database, data.data_root), data.paper_id, reference
        ),
        "tasks": [
            [t.task_id, t.remaining_attempts, t.status]
            for t in tasks.history(data.paper_id)
        ],
    }
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(expected))
    backup = create_backup(data.database, data.data_root, tmp_path / "backups")
    unavailable = tmp_path / "unavailable"
    original.rename(unavailable)
    root = Path(__file__).parents[1]
    completed = subprocess.run(
        [
            str(no_extra_python),
            "-B",
            "-m",
            "tests.read_queries_recovery_worker",
            str(backup.batch_dir),
            str(tmp_path / "restore"),
            str(tmp_path / "moved"),
            str(path),
            str(original),
            str(unavailable),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(root) + os.pathsep + str(root / "src")},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "read query recovered without SDK" in completed.stdout
