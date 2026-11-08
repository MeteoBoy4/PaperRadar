"""Independent D1: resolver worker seams, synthetic Python only, no network."""

import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from scripts import issue167_resolver_worker as worker

if TYPE_CHECKING:
    from scripts.issue167_resolver_case import Case


def test_reservation_is_single_use_and_publication_is_private(tmp_path: Path) -> None:
    marker = tmp_path / "worker-started.json"
    worker.reserve(marker, "123456abcdef")
    original = marker.read_bytes()
    with pytest.raises(FileExistsError):
        worker.reserve(marker, "123456abcdef")
    assert marker.read_bytes() == original
    assert marker.stat().st_mode & 0o777 == 0o600
    result = tmp_path / "result.json"
    worker.publish(result, {"result": "unknown"})
    assert json.loads(result.read_text()) == {"result": "unknown"}
    assert result.stat().st_mode & 0o777 == 0o600
    assert result.stat().st_nlink == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "result.json",
        "worker-started.json",
    ]


@pytest.mark.parametrize("sequence", [True, 0, 2])
def test_wrong_gate_fails_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sequence: object
) -> None:
    calls = []

    def read(*_args: object, **_kwargs: object) -> object:
        calls.append("read")
        return {"run_id": "123456abcdef", "sequence": sequence}

    monkeypatch.setattr(worker, "read_json", read)
    with pytest.raises(worker.WorkerRejected, match=r"^gate_unknown$"):
        worker.wait_gate(
            tmp_path / "gate.json", "123456abcdef", 1, time.monotonic() + 1
        )
    assert calls == ["read"]


def test_metadata_reader_rejects_symlink_without_reading_target(tmp_path: Path) -> None:
    target = tmp_path / "synthetic-target"
    target.write_bytes(b"not-a-metadata-document")
    link = tmp_path / "linked-result"
    link.symlink_to(target)
    with pytest.raises(OSError):
        worker.read_json(link, owner=os.getuid())


@pytest.mark.parametrize("field", ["no_new_privs", "core_zero", "fd_inherited"])
def test_unexpected_child_metadata_cannot_pass(field: str) -> None:
    value = {
        "fd_inherited": True,
        "core_zero": True,
        "cgroup_matches": True,
        "resolver_matches": True,
        "no_new_privs": True,
        "separate_session": True,
    }
    value[field] = False
    with pytest.raises(worker.WorkerRejected, match=r"^child_metadata_unknown$"):
        worker._child_meta(value)


def test_child_argv_never_contains_marker_or_environment(tmp_path: Path) -> None:
    args = worker.child_argv(
        tmp_path, "model", 17, "/synthetic", "a" * 64, tmp_path / "tree"
    )
    assert "OPENAI_API_KEY" not in " ".join(args)
    assert "issue167-public-nonsecret-resolver-fixture" not in " ".join(args)
    with pytest.raises(worker.WorkerRejected, match=r"^child_role_unknown$"):
        worker.child_argv(tmp_path, "arbitrary", 17, "/synthetic", "a" * 64, tmp_path)


def test_model_boundary_adds_only_versioned_python_standard_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    native = Path("/lib/x86_64-linux-gnu")

    class Boundary:
        def __init__(self, *_args: object) -> None:
            self._runtime = (native,)

    module = ModuleType("synthetic_isolation")
    module.__dict__.update(
        {"IsolationBoundary": Boundary, "disable_core_dumps": lambda: None}
    )
    monkeypatch.setattr(worker, "load_isolation", lambda _root: module)
    captured: list[tuple[Path, ...]] = []
    calls: list[dict[str, object]] = []

    def popen(*_args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        calls.append(kwargs)
        if len(calls) == 1:
            return cast(
                "subprocess.Popen[bytes]", SimpleNamespace(wait=lambda **_kw: 0)
            )
        boundary = kwargs["preexec_fn"]
        assert isinstance(boundary, Boundary)
        captured.append(boundary._runtime)
        raise worker.WorkerRejected("captured_before_model_exec")

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(worker, "_stop", lambda _child: None)
    monkeypatch.setattr(
        worker,
        "_line",
        lambda *_a: {
            "marker": "issue167-public-nonsecret-resolver-fixture",
            "metadata": {
                "fd_inherited": True,
                "core_zero": True,
                "cgroup_matches": True,
                "resolver_matches": True,
                "no_new_privs": True,
                "separate_session": True,
            },
        },
    )
    with pytest.raises(worker.WorkerRejected, match=r"^captured_before_model_exec$"):
        worker.run_chain(
            tmp_path,
            tmp_path / "tree",
            tmp_path / "lock",
            "/synthetic",
            "a" * 64,
            deadline=time.monotonic() + 5,
        )
    expected = (
        Path(sys.base_prefix)
        / "lib"
        / (f"python{sys.version_info.major}.{sys.version_info.minor}")
    )
    assert captured == [(native, expected)]
    assert Path(sys.base_prefix) / "lib" not in captured[0]
    assert len(calls) == 2


def test_real_synthetic_chain_preserves_ofd_and_memory_marker_only(
    tmp_path: Path,
) -> None:
    """A separate coordinator simulates NNP; no real service/cgroup is claimed."""
    root = tmp_path / "installation"
    root.mkdir()
    tree = tmp_path / "model"
    (tree / "agent").mkdir(parents=True)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    project = Path(__file__).resolve().parents[1]
    for target, source in (
        (
            "production_isolation.py",
            project / "src/paper_radar/pi_execution/isolation.py",
        ),
        ("production_errors.py", project / "src/paper_radar/pi_execution/errors.py"),
        ("issue167_resolver_child.py", project / "scripts/issue167_resolver_child.py"),
        ("synthetic-python", Path(sys.executable).resolve()),
    ):
        shutil.copyfile(source, root / target)
    (root / "synthetic-python").chmod(0o500)
    resolver_sha = hashlib.sha256(Path("/etc/resolv.conf").read_bytes()).hexdigest()
    code = """
import ctypes,json,resource,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from scripts.issue167_resolver_worker import run_chain
if ctypes.CDLL(None).prctl(38,1,0,0,0)!=0: raise SystemExit(2)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
group=Path('/proc/self/cgroup').read_text().split('::',1)[1].strip()
value=run_chain(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),group,sys.argv[5],deadline=time.monotonic()+15,cwd=Path(sys.argv[6]))
print(json.dumps(value,sort_keys=True))
"""
    before = resource.getrlimit(resource.RLIMIT_CORE)
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            code,
            str(project),
            str(root),
            str(tree),
            str(tmp_path / "lock"),
            resolver_sha,
            str(cwd),
        ],
        env={},
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert child.returncode == 0, child.stderr.decode()
    value = json.loads(child.stdout)
    assert len(value) == 12
    assert all(item is True for item in value.values())
    assert list((tree / "agent").iterdir()) == []
    assert resource.getrlimit(resource.RLIMIT_CORE) == before
    assert (
        b"issue167-public-nonsecret-resolver-fixture" not in child.stdout + child.stderr
    )


def test_entry_rejects_unprotected_root_before_sibling_import(tmp_path: Path) -> None:
    with pytest.raises(worker.WorkerRejected, match=r"^installed_root_unknown$"):
        worker.installed_case_module(tmp_path)


def test_unknown_before_ready_is_published_once_without_exception_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    own = tmp_path / "worker"
    own.mkdir(mode=0o700)
    case = cast(
        "Case",
        SimpleNamespace(
            uid=os.getuid(),
            gid=os.getgid(),
            worker_root=own,
            runtime_root=tmp_path,
            run_id="123456abcdef",
            worker_timeout_s=40,
        ),
    )
    calls = []

    def fail(_case: object) -> dict[str, object]:
        calls.append("metadata")
        raise RuntimeError("external-private-error-sentinel")

    monkeypatch.setattr(worker, "own_metadata", fail)
    result = worker.run_worker(case)
    assert result["result"] == "unknown"
    assert result["failure_reason"] == "worker_observation_unknown"
    stored = json.loads((own / "worker-result.json").read_text())
    assert stored == result
    assert "external-private-error-sentinel" not in str(stored)
    assert not (own / "ready.json").exists()
    with pytest.raises(FileExistsError):
        worker.run_worker(case)
    assert calls == ["metadata"]


def test_wrong_worker_identity_is_rejected_before_reservation(tmp_path: Path) -> None:
    case = cast(
        "Case",
        SimpleNamespace(uid=os.getuid() + 1, gid=os.getgid(), worker_root=tmp_path),
    )
    with pytest.raises(worker.WorkerRejected, match=r"^worker_identity_unknown$"):
        worker.run_worker(case)
    assert list(tmp_path.iterdir()) == []


def test_duplicate_publication_preserves_original_target(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    worker.publish(path, {"result": "unknown"})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        worker.publish(path, {"result": "observed_expected"})
    assert path.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.json"]


def test_transient_atomic_link_is_waited_for_not_parsed(tmp_path: Path) -> None:
    pending = tmp_path / "pending.json"
    pending.write_text('{"partial":')
    pending.chmod(0o600)
    os.link(pending, tmp_path / "second-link")
    with pytest.raises(FileNotFoundError, match=r"^metadata_publishing$"):
        worker.read_json(pending, owner=os.getuid())


def test_expired_chain_cannot_load_or_spawn(tmp_path: Path) -> None:
    with pytest.raises(worker.WorkerRejected, match=r"^worker_timeout$"):
        worker.run_chain(
            tmp_path,
            tmp_path / "tree",
            tmp_path / "lock",
            "/synthetic",
            "a" * 64,
            deadline=time.monotonic() - 1,
        )
    assert list(tmp_path.iterdir()) == []


def test_gate_read_returning_after_deadline_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter([0.0, 2.0])
    monkeypatch.setattr(worker, "time", SimpleNamespace(monotonic=lambda: next(times)))
    monkeypatch.setattr(
        worker, "read_json", lambda *_a, **_k: {"run_id": "123456abcdef", "sequence": 1}
    )
    with pytest.raises(worker.WorkerRejected, match=r"^worker_timeout$"):
        worker.wait_gate(tmp_path / "gate", "123456abcdef", 1, 1.0)
