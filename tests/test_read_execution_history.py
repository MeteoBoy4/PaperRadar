"""D1执行审计/首次语义两轴和恢复来源闭包。"""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.read_tasks import ReadAnalysis, ReadTaskError
from tests.read_execution_support import allow_engineering_path, setup


def test_current_registered_audit_snapshot_does_not_rewrite_first_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, task, _ = setup(tmp_path, monkeypatch)
    config = service.roots.config_root
    source = config / "adapters/pi-rpc-source-v1.yaml"
    (config / "adapters/pi-read-audit-v2.yaml").write_text(
        source.read_text()
        .replace("version: pi-rpc-source-v1", "version: pi-read-audit-v2")
        .replace("transport-v1", "transport-v2")
    )
    settings = config / "settings.yaml"
    settings.write_text(
        settings.read_text().replace(
            "reading: pi-rpc-source-v1", "reading: pi-read-audit-v2"
        )
    )
    snapshot = compile_config(settings, service.database)
    with pytest.raises(ReadTaskError, match="corrupt_reference"):
        service.tasks.prepare_execution(
            task.task_id, audit_snapshot_id=snapshot.snapshot_id
        )
    registered = service.tasks.register(
        task.paper_id,
        snapshot_id=snapshot.snapshot_id,
        extraction_fingerprint=task.identity.extraction_fingerprint,
        request_id="audit-v2",
    )
    assert (
        registered.task_id == task.task_id
        and registered.snapshot_id == task.snapshot_id
    )
    prepared = service.tasks.prepare_execution(
        task.task_id, audit_snapshot_id=snapshot.snapshot_id
    )
    assert prepared.description.semantic_snapshot_id == task.snapshot_id
    assert prepared.description.audit_snapshot_id == snapshot.snapshot_id
    assert prepared.description.adapter_version == "transport-v2"
    # 当前settings文件彻底失去可用性,执行仍从明确持久引用重建。
    settings.write_text("not: a usable current configuration")
    allow_engineering_path(monkeypatch)
    result = service.run_attempt(task.task_id, audit_snapshot_id=snapshot.snapshot_id)
    assert isinstance(result, ReadAnalysis)
    assert result.fingerprint == task.fingerprint
    assert result.audit["adapter_version"] == "transport-v2"
    assert result.audit["audit_snapshot_id"] == snapshot.snapshot_id
    service.tasks.validate_all()


def test_pi_engineering_success_restores_without_original_root_install_or_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.backup import create_backup

    source = tmp_path / "source"
    source.mkdir()
    service, task, _ = setup(source, monkeypatch, mode="degrade")
    allow_engineering_path(monkeypatch)
    service.run_attempt(task.task_id)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis)
    backup = create_backup(service.database, service.data_root, tmp_path / "backups")
    source.rename(tmp_path / "unavailable")
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            """
import hashlib, importlib.abc, json, sys
from pathlib import Path
class NoRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        prefixes = ("paper_radar.read_execution", "paper_radar.pi_execution", "docling")
        if fullname.startswith(prefixes):
            raise RuntimeError("execution import forbidden")
def deny(event, args):
    process = {"os.fork", "os.exec", "os.system"}
    if event.startswith(("socket.", "subprocess.")) or event in process:
        raise RuntimeError("runtime forbidden")
    if event == "open" and str(args[0]).startswith(sys.argv[4]):
        raise RuntimeError("original root forbidden")
sys.meta_path.insert(0, NoRuntime())
sys.addaudithook(deny)
from paper_radar.backup import restore_backup
from paper_radar.read_tasks import ReadTasks, ReadTaskError
batch, target, key, unavailable = sys.argv[1:]
restored = restore_backup(Path(batch), Path(target))
tasks = ReadTasks(Path(target) / "database.sqlite3", Path(target))
def hashes():
    return {str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(target).rglob("*") if p.is_file()}
before = hashes()
analysis = tasks.analysis(key)
assert analysis.executor_kind == "pi_rpc" and analysis.attempt_ordinal == 2
assert analysis.discards and analysis.audit["audit_snapshot_id"]
assert tasks.task(analysis.task_id).remaining_attempts == 0
try:
    tasks.analysis(key, ordinary=True)
except ReadTaskError as error:
    assert error.reason == "ordinary_consumption_denied"
else:
    raise AssertionError("ordinary experiment consumption allowed")
tasks.validate_all()
assert hashes() == before
print(json.dumps({"kind": analysis.executor_kind, "audit": analysis.audit}))
""",
            str(backup.batch_dir),
            str(tmp_path / "restored"),
            result.analysis_id,
            str(tmp_path / "unavailable"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == {"kind": "pi_rpc", "audit": result.audit}


@pytest.mark.parametrize("damage", ["install", "adapter", "channel"])
def test_pi_port_rejects_forged_execution_audit_without_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from tests.read_tasks_support import valid_candidate
    from tests.test_read_tasks_execution import pi_candidate

    service, task, _ = setup(tmp_path, monkeypatch)
    candidate = pi_candidate(service.tasks, valid_candidate())
    value = candidate.execution_audit.model_dump()
    value.update(
        {"install_id": "0" * 32}
        if damage == "install"
        else {"adapter_version": "other"}
        if damage == "adapter"
        else {"channel": "other"}
    )
    # model_construct刻意绕开形状校验,接收权威仍须重建strict Schema。
    bad = candidate.execution_audit.model_construct(**value)
    with pytest.raises(
        ReadTaskError,
        match="invalid_request" if damage == "channel" else "corrupt_reference",
    ):
        service.tasks.run_pi_once(
            task.task_id, lambda _: replace(candidate, execution_audit=bad)
        )
    assert service.tasks.analyses(task.paper_id) == ()
    assert service.tasks.task(task.task_id).remaining_attempts == 1


def test_test_executor_cannot_submit_pi_candidate_and_cannot_claim_pi_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import Any

    from tests.read_tasks_support import valid_candidate
    from tests.test_read_tasks_execution import pi_candidate

    service, task, _ = setup(tmp_path, monkeypatch)
    forged: Any = pi_candidate(service.tasks, valid_candidate())
    with pytest.raises(ReadTaskError, match="invalid_request"):
        service.tasks.run_once(task.task_id, lambda _: forged)
    assert service.tasks.analyses(task.paper_id) == ()
    assert service.tasks.task(task.task_id).status == "running"


def test_read_history_import_does_not_acquire_execution_capability(
    tmp_path: Path,
) -> None:
    script = """
import importlib.abc, json, sys
class HistoryOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        denied = ("paper_radar.llm", "paper_radar.read_execution",
                  "paper_radar.pi_execution", "docling")
        if fullname.startswith(denied):
            raise RuntimeError("execution import forbidden: " + fullname)
def deny(event, args):
    if event.startswith(("socket.", "subprocess.")) or event == "sqlite3.connect":
        raise RuntimeError("runtime IO forbidden")
sys.meta_path.insert(0, HistoryOnly())
sys.addaudithook(deny)
from paper_radar.read_tasks import ReadTasks
from paper_radar.read_tasks.execution import execution_resource
assert callable(ReadTasks) and callable(execution_resource)
print(json.dumps({"history_only": True}))
"""
    child = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == {"history_only": True}
