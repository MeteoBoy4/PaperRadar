"""D1:显式 Docling 公共执行与持久服务组合。"""

from pathlib import Path

import pytest

from paper_radar.docling_executor import (
    DoclingParser,
    DoclingPreflightError,
    DoclingRun,
)
from tests.body_support import prepared
from tests.docling_runtime_support import environment


def test_runtime_probe_refusal_never_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved, service, _ = prepared(tmp_path)
    # 固定外部包/模块事实,由真实probe计算旧工具链对新core的拒绝。
    environment(monkeypatch)
    parser = DoclingParser(
        DoclingRun(
            model_root=tmp_path / "missing",
            timeout_seconds=30.0,
            memory_limit_bytes=2**34,
        )
    )
    with pytest.raises(DoclingPreflightError) as error:
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert error.value.reason == "dependency_version_mismatch"
    assert service.facts(saved.paper_id).extraction is None


def test_supervisor_timeout_reaps_descendants_and_measures_worker_peak(
    tmp_path: Path,
) -> None:
    import os
    import sys
    import time

    from paper_radar.docling_execution.models import WorkerRequest
    from paper_radar.docling_execution.process import DoclingProcess

    pid_file = tmp_path / "grandchild.pid"
    script = """import os,sys,time
from pathlib import Path
child=os.fork()
if child==0:
 time.sleep(60)
else:
 Path(sys.argv[1]).with_name('grandchild.pid').write_text(str(child))
 time.sleep(60)
"""
    request = WorkerRequest(
        model_root=str(tmp_path),
        pdf_path=str(tmp_path / "input.pdf"),
        response_path=str(tmp_path / "result.json"),
        timeout_seconds=0.3,
        memory_limit_bytes=2**34,
        threads=1,
        backend_config_json="{}",
        model_commits={},
    )
    result = DoclingProcess(command=(sys.executable, "-c", script)).execute(request)
    assert result.failure == "timeout" and result.peak_memory_bytes > 0
    pid = int(pid_file.read_text())
    for _ in range(100):
        status = Path(f"/proc/{pid}/stat")
        if not status.exists() or status.read_text().split()[2] == "Z":
            break
        time.sleep(0.01)
    else:
        os.kill(pid, 9)
        pytest.fail("后代仍在执行")


def test_sandbox_denies_network_and_process_group_escape_in_descendants(
    tmp_path: Path,
) -> None:
    import subprocess
    import sys

    script = """import os,socket,threading
from paper_radar.docling_execution.sandbox import restrict_worker
restrict_worker(2**34)
seen=[]
thread=threading.Thread(target=lambda:seen.append(1))
thread.start();thread.join()
assert seen==[1]
for operation in (lambda:socket.socket(),os.setsid,lambda:os.setpgid(0,0)):
 try: operation()
 except PermissionError: pass
 else: raise AssertionError('隔离未生效')
pid=os.fork()
if pid==0:
 try: socket.socket()
 except PermissionError: os._exit(0)
 os._exit(1)
assert os.waitpid(pid,0)[1]==0
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "executor_error",
        "timeout",
        "resource_exhausted",
        "extraction_failed_quality_gate",
        "extraction_failed_no_text_layer",
    ],
)
def test_public_service_records_worker_outcomes_and_preserves_budget(
    tmp_path: Path, failure: str | None
) -> None:
    from paper_radar.body import BodyService
    from tests.docling_executor_support import prepared_docling

    saved, service, parser = prepared_docling(tmp_path, failure=failure)
    first = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert first.attempts[0].failure == failure
    assert first.attempts[0].executor_audit is not None
    assert first.attempts[0].executor_audit.memory_limit_bytes == 2**34
    assert (
        first.attempts[0].peak_memory_bytes and first.attempts[0].peak_memory_bytes > 0
    )
    if failure is None:
        assert first.artifact_id and first.identity
        from paper_radar.fulltext.artifacts import FulltextArtifacts

        loaded = FulltextArtifacts(service.store).load(
            first.artifact_id, expected_identity=first.identity
        )
        assert loaded.context.replay()[1].text == "Exact source α = 2."
    second = BodyService(saved.database, saved.data_root).extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    if failure in {"executor_error", "timeout", "resource_exhausted"}:
        assert len(second.attempts) == 2 and second.remaining_attempts == 0
    else:
        assert second == first
        assert first.permanent_failure == (failure is not None)
    service.validate_all()


def test_model_hash_refusal_precedes_lock_without_claim(tmp_path: Path) -> None:
    import fcntl

    from paper_radar.body.extraction import LOCK_FILENAME
    from tests.docling_executor_support import prepared_docling

    saved, service, parser = prepared_docling(tmp_path)
    source = (
        parser.run.model_root
        / "docling-project--docling-layout-egret-medium/config.json"
    )
    source.write_bytes(b"changed")
    lock = saved.data_root / LOCK_FILENAME
    with lock.open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(DoclingPreflightError) as error:
            service.extract(
                saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
            )
    assert error.value.reason == "model_deployment_invalid"
    assert service.facts(saved.paper_id).extraction is None


def test_concurrent_requests_release_each_preparation_even_when_success_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    from tests.docling_executor_support import prepared_docling

    saved, service, parser = prepared_docling(tmp_path / "archive")
    work = tmp_path / "temporary"
    work.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(work))

    def extract() -> object:
        return service.extract(
            saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: extract(), range(2)))
    assert first == second
    assert list(work.iterdir()) == []
    assert extract() == first
    assert list(work.iterdir()) == []


def test_prepared_models_survive_later_deployment_changes(tmp_path: Path) -> None:
    import hashlib
    import json
    from dataclasses import replace

    from paper_radar.config import load_config_snapshot
    from paper_radar.config.extraction_models import ModelFile
    from tests.body_support import PDF
    from tests.docling_executor_support import prepared_docling

    saved, _, parser = prepared_docling(tmp_path)
    semantics = load_config_snapshot(saved.database, saved.snapshot_id).extraction
    assert semantics
    first = parser.preflight(semantics)
    try:
        models = list(semantics.model_artifacts)
        layout = models[0]
        changed = (
            parser.run.model_root
            / layout.repo_id.replace("/", "--")
            / layout.files[0].path
        )
        changed.write_bytes(b"new frozen file")
        files = (
            ModelFile(
                path=layout.files[0].path,
                sha256=hashlib.sha256(changed.read_bytes()).hexdigest(),
            ),
            *layout.files[1:],
        )
        models[0] = replace(layout, files=files)
        replacement = replace(semantics, model_artifacts=tuple(models))
        deployment_path = parser.run.model_root / "deployment.json"
        deployment = json.loads(deployment_path.read_text())
        deployment["models"][0]["files"] = [f.model_dump() for f in files]
        deployment_path.write_text(json.dumps(deployment))
        second = parser.preflight(replacement)
        try:
            assert first.audit.model_artifacts_hash != second.audit.model_artifacts_hash
            assert (
                first.convert(PDF, semantics).document.blocks[1].orig
                == "Exact source α = 2."
            )
            assert (
                second.convert(PDF, replacement).document.blocks[1].orig
                == "Exact source α = 2."
            )
        finally:
            second.close()
    finally:
        first.close()


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        '{"failure":"unknown"}',
        "{}",
        '{"failure":"executor_error","failure":"timeout"}',
    ],
)
def test_malformed_external_response_is_executor_error(
    tmp_path: Path, body: str
) -> None:
    import sys

    from paper_radar.docling_execution.models import WorkerRequest
    from paper_radar.docling_execution.process import DoclingProcess

    script = (
        "import json,sys;from pathlib import Path;"
        "r=json.loads(Path(sys.argv[1]).read_text());"
        "Path(r['response_path']).write_text(" + repr(body) + ")"
    )
    request = WorkerRequest(
        model_root=str(tmp_path),
        pdf_path=str(tmp_path / "input.pdf"),
        response_path=str(tmp_path / "response.json"),
        timeout_seconds=2.0,
        memory_limit_bytes=2**34,
        threads=1,
        backend_config_json="{}",
        model_commits={},
    )
    response = DoclingProcess(command=(sys.executable, "-c", script)).execute(request)
    # 空成功必须在协议边界拒绝,不能让调用者误认为完整 canonical。
    assert response.failure == "executor_error"


@pytest.mark.parametrize("damage", ["commit", "missing", "symlink"])
def test_deployment_refusal_never_claims(tmp_path: Path, damage: str) -> None:
    import json

    from tests.docling_executor_support import prepared_docling

    saved, service, parser = prepared_docling(tmp_path)
    deployment = parser.run.model_root / "deployment.json"
    source = (
        parser.run.model_root
        / "docling-project--docling-layout-egret-medium/config.json"
    )
    if damage == "commit":
        value = json.loads(deployment.read_text())
        value["models"][0]["commit_sha"] = "0" * 40
        deployment.write_text(json.dumps(value))
    elif damage == "missing":
        source.unlink()
    else:
        replacement = tmp_path / "replacement"
        replacement.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(replacement)
    with pytest.raises(DoclingPreflightError) as error:
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert error.value.reason == "model_deployment_invalid"
    assert service.facts(saved.paper_id).extraction is None


def test_disabled_formula_does_not_require_or_hash_its_deployment(
    tmp_path: Path,
) -> None:
    import shutil

    import yaml

    from paper_radar.config.extraction import Extraction
    from tests.docling_executor_support import prepared_docling

    _, _, parser = prepared_docling(tmp_path)
    config = yaml.safe_load(
        (tmp_path / "config/extraction/extraction-v1.yaml").read_text()
    )
    config["policy"] = {"do_formula_enrichment": False}
    del config["models"]["formula"]
    shutil.rmtree(parser.run.model_root / "docling-project--CodeFormulaV2")
    semantics = Extraction.model_validate(config).semantics
    prepared = parser.preflight(semantics)
    try:
        assert prepared.audit.model_artifacts_hash == semantics.model_artifacts_hash
    finally:
        prepared.close()


@pytest.mark.parametrize(
    "exception,expected",
    [("ImportError", "executor_error"), ("MemoryError", "resource_exhausted")],
)
def test_real_worker_settles_import_and_allocation_failures_safely(
    tmp_path: Path, exception: str, expected: str
) -> None:
    import sys

    from paper_radar.docling_execution.process import DoclingProcess
    from tests.docling_executor_support import prepared_docling

    saved, service, configured = prepared_docling(tmp_path)
    script = """import importlib.abc,runpy,sys
class FailExternalSDK(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0]=='docling': raise EXCEPTION('private loader text')
sys.meta_path.insert(0,FailExternalSDK())
runpy.run_module('paper_radar.docling_execution.worker',run_name='__main__')
""".replace("EXCEPTION", exception)
    parser = DoclingParser(
        configured.run, executor=DoclingProcess(command=(sys.executable, "-c", script))
    )
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert result.attempts[-1].failure == expected
    assert result.remaining_attempts == 1 and result.quality.basis == "absent"
    assert result.attempts[-1].executor_audit is not None
    assert "private loader text" not in repr(result)


def test_virtual_address_limit_is_enforced_without_loading_sdk() -> None:
    import subprocess
    import sys

    script = """import resource
from paper_radar.docling_execution.sandbox import restrict_worker
restrict_worker(2**26)
assert resource.getrlimit(resource.RLIMIT_AS)==(2**26,2**26)
try: bytearray(2**28)
except MemoryError: pass
else: raise AssertionError('虚拟地址空间上限未生效')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
