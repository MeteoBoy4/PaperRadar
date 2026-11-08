"""独立D1:仅mock transport/子进程与临时元数据,不联网或执行服务。"""

import errno
import json
import os
import resource
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import pytest

from scripts import issue167_h1_network_worker as worker
from scripts.issue167_h1_phase import Plan
from scripts.issue167_observation import FileObserver


def plan() -> Plan:
    return Plan("a1b2c3d4e5f6", os.getuid(), os.getgid())


def row(probe: worker.Probe, outcome: worker.Outcome) -> worker.ProbeRow:
    return {
        "case": probe.case,
        "kind": probe.kind,
        "family": probe.family,
        "port": probe.port,
        "expected": probe.expected,
        "outcome": outcome,
        "errno_category": "none",
    }


def test_fixed_two_phase_inventory_is_loopback_only_and_bounded() -> None:
    current = plan()
    expected_names = [
        "v4-current-tcp",
        "v6-current-tcp",
        "v4-other-tcp",
        "v6-other-tcp",
        "v4-blocked-tcp",
        "v6-blocked-tcp",
        "v4-blocked-udp",
        "v6-blocked-udp",
        "v4-dns-udp",
        "v6-dns-udp",
    ]
    phases: tuple[tuple[worker.Phase, int, int], ...] = (
        ("a", 38167, 38169),
        ("b", 38169, 38167),
    )
    for phase, allowed, other in phases:
        probes = worker.probes(current, phase)
        assert [probe.case for probe in probes] == expected_names
        assert len(probes) == 10
        assert [probe.port for probe in probes] == [
            allowed,
            allowed,
            other,
            other,
            38168,
            38168,
            38168,
            38168,
            53,
            53,
        ]
        assert [probe.expected for probe in probes] == ["allow"] * 2 + ["deny"] * 8


def test_phase_stops_on_first_unknown_without_fallback_or_extra_attempts() -> None:
    calls = []

    def perform(probe: worker.Probe) -> worker.ProbeRow:
        calls.append(probe.case)
        return row(probe, "unknown")

    rows, complete = worker.run_phase(plan(), "a", perform=perform)
    assert calls == ["v4-current-tcp"]
    assert len(rows) == 1 and not complete


def test_phase_executes_exact_once_per_case_when_expectations_match() -> None:
    calls = []

    def perform(probe: worker.Probe) -> worker.ProbeRow:
        calls.append(probe.case)
        return row(probe, "allowed" if probe.expected == "allow" else "denied")

    rows, complete = worker.run_phase(plan(), "b", perform=perform)
    assert len(calls) == len(set(calls)) == len(rows) == 10
    assert complete


@pytest.mark.parametrize(
    "number,outcome,category",
    [
        (errno.ECONNREFUSED, "unknown", "connection_refused"),
        (errno.EPERM, "denied", "permission_denied"),
        (errno.EHOSTUNREACH, "denied", "admin_unreachable"),
        (errno.ETIMEDOUT, "unknown", "timed_out"),
        (errno.EINVAL, "unknown", "other"),
    ],
)
def test_error_classification_never_uses_external_text(
    number: int,
    outcome: str,
    category: str,
) -> None:
    assert worker.classify_error(OSError(number, "external text")) == (
        outcome,
        category,
    )


def test_transport_only_uses_literal_endpoint_and_fixed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class FakeSocket:
        def __init__(self, family: int, kind: int) -> None:
            calls.append(("socket", family, kind))

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            calls.append(("closed",))

        def settimeout(self, timeout: float) -> None:
            assert timeout == 0.5

        def connect(self, address: tuple[str, int]) -> None:
            calls.append(("address", address))

        def send(self, payload: bytes) -> int:
            assert payload == b"P"
            return 1

        def recv(self, size: int) -> bytes:
            assert size == 2
            return b"OK"

    monkeypatch.setattr(socket, "socket", FakeSocket)
    result = worker.run_probe(worker.Probe("v6-dns-udp", "udp", "v6", 53, "deny"))
    assert ("address", ("::1", 53)) in calls
    assert result["outcome"] == "allowed"  # 这是负例失败,不能把收到响应记为拒绝。
    assert set(result) == {
        "case",
        "kind",
        "family",
        "port",
        "expected",
        "outcome",
        "errno_category",
    }


def test_metadata_publish_is_atomic_exclusive_and_retains_old_status(
    tmp_path: Path,
) -> None:
    target = tmp_path / "a-done.json"
    worker.publish(target, {"phase": "a", "cases": []})
    assert json.loads(target.read_text()) == {"phase": "a", "cases": []}
    assert target.stat().st_nlink == 1
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        worker.publish(target, {"phase": "b"})
    assert json.loads(target.read_text())["phase"] == "a"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize(
    "data",
    [
        {"run_id": "a1b2c3d4e5f6", "phase": "a", "sequence": True},
        {"run_id": "a1b2c3d4e5f6", "phase": "b", "sequence": 2},
        {"run_id": "wrong", "phase": "a", "sequence": 1},
        {"run_id": "a1b2c3d4e5f6", "phase": "a", "sequence": 1, "extra": True},
        [],
    ],
)
def test_gate_requires_exact_run_phase_and_nonboolean_sequence(data: object) -> None:
    with pytest.raises(worker.WorkerRejected, match=r"^gate_invalid$"):
        worker.decode_gate(json.dumps(data).encode(), "a1b2c3d4e5f6", "a")


def test_gate_accepts_exact_closed_metadata() -> None:
    worker.decode_gate(
        b'{"run_id":"a1b2c3d4e5f6","phase":"a","sequence":1}', "a1b2c3d4e5f6", "a"
    )


def test_two_link_gate_publication_window_is_not_read(tmp_path: Path) -> None:
    temporary = tmp_path / "temp"
    temporary.write_text("incomplete")
    target = tmp_path / "go-a.json"
    os.link(temporary, target)
    with pytest.raises(FileNotFoundError):
        worker.read_gate(target, "a1b2c3d4e5f6", "a")


def test_gate_rejects_user_owned_or_symlink_metadata(tmp_path: Path) -> None:
    target = tmp_path / "go-a.json"
    target.write_text("{}")
    with pytest.raises(worker.WorkerRejected, match=r"^gate_metadata_invalid$"):
        worker.read_gate(target, "a1b2c3d4e5f6", "a")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(worker.WorkerRejected, match=r"^gate_metadata_invalid$"):
        worker.read_gate(link, "a1b2c3d4e5f6", "a")


def test_runtime_initialization_wait_is_bounded_without_creating_root_dirs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 2)
    with pytest.raises(worker.WorkerRejected, match=r"^runtime_timeout$"):
        worker.wait_directories(plan(), deadline=1)


def test_existing_started_blocks_before_file_or_network_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker.reserve_started(tmp_path / "started.json", plan().run_id)
    monkeypatch.setattr(worker, "wait_directories", lambda *_args, **_kwargs: tmp_path)

    def forbidden(_plan: Plan) -> dict[str, object]:
        pytest.fail("must not reach file/network action after old reservation")

    monkeypatch.setattr(worker, "run_file_probe", forbidden)
    with pytest.raises(FileExistsError):
        worker.execute_worker(plan())


def test_file_failure_retains_start_and_never_reaches_network_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "wait_directories", lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(resource, "getrlimit", lambda _key: (0, 0))
    monkeypatch.setattr(
        worker,
        "process_metadata",
        lambda _plan: {
            "core_limits": [0, 0],
            "no_new_privs": True,
            "cap_eff_zero": True,
            "cgroup_matches": True,
        },
    )
    monkeypatch.setattr(worker, "run_file_probe", lambda _plan: {"result": "unknown"})

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("file unknown must not wait for network gate")

    monkeypatch.setattr(worker, "wait_gate", forbidden)
    with pytest.raises(worker.WorkerRejected, match=r"^file_probe_unknown$"):
        worker.execute_worker(plan())
    assert (
        json.loads((tmp_path / "started.json").read_text())["result"]
        == "reserved_unknown"
    )
    assert not (tmp_path / "ready.json").exists()


def test_file_probe_uses_only_synthetic_fixtures_and_freezes_before_deletion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    (runtime / "worker").mkdir(parents=True)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(Plan, "runtime_root", property(lambda _self: runtime))
    monkeypatch.setattr(worker, "_probe_cwd", lambda: cwd)

    class Boundary:
        def __init__(self, *_args: object) -> None:
            self._runtime: tuple[Path, ...] = ()

    isolation = SimpleNamespace(IsolationBoundary=Boundary)
    observation = SimpleNamespace(FileObserver=FileObserver)
    monkeypatch.setattr(
        worker,
        "_load_local",
        lambda name, filename: (
            isolation if filename == "production_isolation.py" else observation
        ),
    )

    def child(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        assert kwargs["env"] == {}
        paths = json.loads(argv[-1])
        transient = Path(paths["transient"])
        transient.write_bytes(b"synthetic")
        transient.unlink()
        Path(paths["retained"]).write_bytes(b"synthetic")
        result = {
            "install_read": True,
            "attempt_write": True,
            "install_write": False,
            "cwd_write": False,
            "business_read": False,
            "publisher_read": False,
            "credentials_read": False,
            "cwd_created": None,
        }
        return subprocess.CompletedProcess(argv, 0, json.dumps(result).encode(), b"")

    monkeypatch.setattr(subprocess, "run", child)
    result = worker.run_file_probe(plan())
    assert result["result"] == "observed_expected"
    assert result["history"] == "observed_mutation"
    assert result["terminal_regular_files"] == 1
    assert result["directory_deleted"] is True
    assert not (runtime / "worker/files/attempt").exists()
    assert not list(cwd.iterdir())


def test_standalone_fixture_module_imports_without_site_or_product_package(
    tmp_path: Path,
) -> None:
    # 仅导入stdlib/既有源码,不调用Boundary、不运行worker/网络/服务。
    project = Path(__file__).resolve().parents[1]
    shutil.copyfile(
        project / "scripts/issue167_h1_network_worker.py", tmp_path / "worker.py"
    )
    shutil.copyfile(
        project / "src/paper_radar/pi_execution/errors.py",
        tmp_path / "production_errors.py",
    )
    shutil.copyfile(
        project / "src/paper_radar/pi_execution/isolation.py",
        tmp_path / "production_isolation.py",
    )
    script = """
import importlib.util,sys
from pathlib import Path
root=Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('synthetic_worker',root/'worker.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
m._load_local('paper_radar.pi_execution.errors','production_errors.py')
iso=m._load_local('fixture_iso','production_isolation.py')
assert callable(iso.IsolationBoundary)
print('imported')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", script, str(tmp_path)],
        env={},
        capture_output=True,
        timeout=5,
        check=True,
    )
    assert result.stdout == b"imported\n"


def test_process_metadata_uses_only_selected_current_process_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = plan()

    def read(path: Path) -> str:
        if path.name == "status":
            return "Name:\tsynthetic\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\n"
        assert str(path) == "/proc/self/cgroup"
        return f"0::{current.cgroup}\n"

    monkeypatch.setattr(worker, "_read_process_metadata", read)
    monkeypatch.setattr(resource, "getrlimit", lambda _key: (0, 0))
    assert worker.process_metadata(current) == {
        "core_limits": [0, 0],
        "no_new_privs": True,
        "cap_eff_zero": True,
        "cgroup_matches": True,
    }


@pytest.mark.parametrize("field", ["no_new_privs", "cap_eff_zero", "cgroup_matches"])
def test_bad_process_metadata_stops_before_file_or_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    monkeypatch.setattr(worker, "wait_directories", lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(resource, "getrlimit", lambda _key: (0, 0))
    metadata: dict[str, object] = {
        "core_limits": [0, 0],
        "no_new_privs": True,
        "cap_eff_zero": True,
        "cgroup_matches": True,
    }
    metadata[field] = False
    monkeypatch.setattr(worker, "process_metadata", lambda _plan: metadata)

    def forbidden(_plan: Plan) -> dict[str, object]:
        pytest.fail("bad process metadata must not reach file or network probe")

    monkeypatch.setattr(worker, "run_file_probe", forbidden)
    with pytest.raises(worker.WorkerRejected, match=r"^process_metadata_invalid$"):
        worker.execute_worker(plan())
    assert (
        json.loads((tmp_path / "started.json").read_text())["result"]
        == "reserved_unknown"
    )
