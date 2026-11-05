"""D1 完整Pi成功业务闭包在无extra新进程中恢复/搬迁/回查。"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from paper_radar.backup import create_backup
from paper_radar.body.extraction import LOCK_FILENAME
from paper_radar.config import compile_config
from paper_radar.read_tasks import ReadAnalysis, ReadTask
from tests.a8_call_support import Archive
from tests.body_read_closure_support import closure, projection
from tests.config_projection_support import new_yaml_version
from tests.no_extra_runtime import no_extra_python as no_extra_python
from tests.read_queries_support import successful


@pytest.mark.parametrize("mode", ["normal", "degrade"])
def test_full_business_bytes_and_queries_survive_two_no_extra_cold_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_extra_python: Path, mode: str
) -> None:
    source = tmp_path / "source"
    service, task, body = closure(source, monkeypatch, mode=mode)
    result = service.run_attempt(task.task_id)
    if mode == "degrade":
        assert isinstance(result, ReadTask)
        assert result.attempts[0].failure == "output_invalid"
        result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis)
    settings = source / "config/settings.yaml"
    pdf = body.current_pdf(task.paper_id)
    assert pdf is not None
    data = Archive(
        settings,
        service.database,
        service.data_root,
        task.snapshot_id,
        task.paper_id,
        pdf.version_id,
    )
    english = successful(
        service.tasks,
        data,
        task.identity.extraction_fingerprint,
        "english",
        language="en",
    )
    assert english.executor_kind == "test"
    new_yaml_version(
        settings,
        "profile",
        lambda c: c.update(background="Changed synthetic background"),
    )
    reference = compile_config(settings, service.database).snapshot_id
    pending = service.tasks.register(
        task.paper_id,
        snapshot_id=reference,
        extraction_fingerprint=task.identity.extraction_fingerprint,
        request_id="pending",
    )
    service.tasks.claim(pending.task_id)
    # 待结算lease会过期,但恢复/查询必须原样保留,不隐式reclaim。
    before = projection(service.database, service.data_root, task.paper_id, reference)
    assert before["queries"]["old"] and len(before["queries"]["analyses"]) == 2
    expected = tmp_path / "expected.json"
    expected.write_text(
        json.dumps(
            {"paper": task.paper_id, "snapshot": reference, "projection": before}
        )
    )
    backup = create_backup(service.database, service.data_root, tmp_path / "backups")
    assert not (backup.batch_dir / LOCK_FILENAME).exists()
    assert not (backup.batch_dir / ".body-read.lock").exists()
    assert all(LOCK_FILENAME not in b.path for b in backup.manifest.blobs)
    unavailable = tmp_path / "source-unavailable"
    source.rename(unavailable)
    root = Path(__file__).resolve().parents[1]
    for phase, probes in (("restore", 2), ("query", 4)):
        completed = subprocess.run(
            [
                str(no_extra_python),
                "-B",
                "-m",
                "tests.body_read_closure_worker",
                phase,
                str(backup.batch_dir),
                str(tmp_path / "restored"),
                str(tmp_path / "moved"),
                str(expected),
                str(source),
                str(unavailable),
            ],
            cwd=tmp_path,
            env={
                **os.environ,
                "PYTHONPATH": str(root) + os.pathsep + str(root / "src"),
            },
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {
            "phase": phase,
            "guard_probes": probes,
            "sdk_imported": False,
            "passed": True,
        }
