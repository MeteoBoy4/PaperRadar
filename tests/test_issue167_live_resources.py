"""Independent D1: experimental resource hook, synthetic processes and metadata."""

import json
import os
import shutil
import struct
import threading
from pathlib import Path
from typing import cast

import pytest

from paper_radar.llm.rpc_types import RpcProblem, RpcReason
from paper_radar.pi_execution import ExecutionRoots, placement, prepare_launch
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.resources import AttemptResources
from scripts import issue167_live_resources as adapter
from scripts.issue167_fork_observation import (
    CgroupReader,
    ForkObservation,
    WindowRejected,
)
from scripts.issue167_h1_phase import Plan
from scripts.issue167_session_observation import ClassifiedSessionObservation
from tests.pi_execution_support import TOKEN, launch_inputs, observed
from tests.pi_placement_support import instrument_wrapper
from tests.test_issue167_fork_observation import ReplayObserver
from tests.test_issue167_observed_launch_fixture import PEER

CLASSIFIED_PEER = f"""
import json,os,sys
from pathlib import Path
agent=Path(os.environ['PI_CODING_AGENT_DIR'])
if not sys.argv[1:]:
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    os.write(int(os.environ['PAPERRADAR_AUTH_METADATA_FD']), json.dumps({{
        'format_version': 1, 'source_id': 'pi-auth-refresh-1.4.0-v1',
        'pid': os.getpid(), 'started_at': now, 'completed_at': now,
        'refresh_called': False,
    }}).encode())
    print(json.loads((agent/'auth.json').read_text())['token'])
else:
    for name in ('auth.json','models-store.json'):
        (agent/name).write_bytes(b'{{}}')
    for name in ('auth.json','models-store.json','settings.json'):
        lock=agent/(name+'.lock');lock.mkdir();lock.rmdir()
    cache=Path(os.environ['TMPDIR'])/'node-compile-cache/version-fixture/deep'
    cache.mkdir(parents=True);(cache/'bytecode').write_bytes(b'public-fixed-code')
    inherited=0
    for descriptor in range(3,256):
        try:os.fstat(descriptor);inherited+=1
        except OSError:pass
    print(json.dumps({{'ready':True,'marker_received':os.environ.get('OPENAI_API_KEY')=={TOKEN!r},'inherited_descriptor_count':inherited}}),flush=True)
    sys.stdin.buffer.read()
"""


@pytest.fixture
def reader(tmp_path: Path) -> CgroupReader:
    plan = Plan("df567890abcd", os.getuid(), os.getgid(), network_mode="ipv4_only")
    root = tmp_path / "fixture-cgroup"
    group = root / "system.slice" / plan.unit
    group.mkdir(parents=True)
    (group / "cgroup.procs").write_text(f"{os.getpid()}\n")
    own = tmp_path / "fixture-self-cgroup"
    own.write_text(f"0::{plan.cgroup}\n")
    return CgroupReader(plan, cgroup_root=root, self_cgroup=own)


def factory() -> type[AttemptResources]:
    return adapter._LAUNCHER.AttemptResources


def group(reader: CgroupReader) -> Path:
    return reader.cgroup_root / "system.slice" / reader.plan.unit


def roots(tmp_path: Path) -> ExecutionRoots:
    return ExecutionRoots(
        tmp_path / "data",
        tmp_path / "config",
        tmp_path / "materials",
        tmp_path / "install",
    )


@pytest.fixture
def replay(monkeypatch: pytest.MonkeyPatch) -> list[ForkObservation]:
    windows: list[ForkObservation] = []

    class ReplayWindow(ForkObservation):
        def __init__(self, root: Path, reader: CgroupReader) -> None:
            super().__init__(root, reader, observer_factory=ReplayObserver)
            windows.append(self)

    monkeypatch.setattr(adapter, "ForkObservation", ReplayWindow)
    return windows


def test_kernel_public_launch_arms_before_model_and_keeps_original_fd_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
) -> None:
    database, description, execution_roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=PEER
    )
    order: list[str] = []
    allocated: list[Path] = []
    real_start = ForkObservation.start
    platform = placement.PLACEMENT_PLATFORM
    real_verify = platform.verify

    def arm(window: ForkObservation) -> None:
        real_start(window)
        assert not os.get_inheritable(window._observer.fd)
        allocated.append(window._observer.root)
        order.append("armed")

    def verify(
        target: placement.PlacementTarget, pid: int, start: int, unit: str
    ) -> None:
        real_verify(target, pid, start, unit)
        # 实际内核 exec-stop 后读目标 argv;阻塞 wrapper 的 Popen 不算模型启动。
        if b"--mode\x00rpc\x00" in Path(f"/proc/{pid}/cmdline").read_bytes():
            order.append("model")
            assert order[-2:] == ["armed", "model"]

    monkeypatch.setattr(ForkObservation, "start", arm)
    monkeypatch.setattr(platform, "verify", verify)
    with adapter.observe_launch_resources(reader, synthetic=True) as observations:
        with prepare_launch(
            database,
            description,
            roots=execution_roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ) as prepared:
            session = prepared(description)
            child = observed(session)
            assert child["ready"] is True and child["marker_received"] is True
            assert child["inherited_descriptor_count"] == 1
            session.terminate(5)
        observations.assert_complete()
    (receipt,) = observations.receipts
    assert order == ["armed", "model"]
    assert receipt["result"] == "window_complete"
    assert receipt["history"] == "observed_mutation"
    assert receipt["terminal_regular_files"] == 1
    assert receipt["directory_deleted"] is True
    assert receipt["source"] == "synthetic_cgroup_fixture"
    assert receipt["event_source"] == "inotify"
    assert receipt["sequence"] == 1
    assert not allocated[0].exists()
    assert TOKEN not in json.dumps(observations.receipts)
    assert "temporary-synthetic-write" not in json.dumps(observations.receipts)
    assert factory() is AttemptResources


def test_fixture_cannot_masquerade_as_kernel_authority(reader: CgroupReader) -> None:
    with (
        pytest.raises(
            adapter.ResourceObservationRejected, match=r"^resource_authority_unknown$"
        ),
        adapter.observe_launch_resources(reader),
    ):
        pytest.fail("fixture_must_not_enter_live_context")
    assert factory() is AttemptResources


def test_classified_public_python_launch_keeps_cache_and_session_claims_separate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
) -> None:
    database, description, execution_roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=CLASSIFIED_PEER
    )
    with adapter.observe_launch_resources(
        reader, synthetic=True, classified=True
    ) as observations:
        with prepare_launch(
            database,
            description,
            roots=execution_roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ) as prepared:
            session = prepared(description)
            metadata = observed(session)
            assert metadata["ready"] is True and metadata["marker_received"] is True
            assert metadata["inherited_descriptor_count"] == 1
            session.terminate(5)
        observations.assert_complete()
    (row,) = observations.receipts
    assert row["result"] == "session_window_complete"
    assert row["scope"] == "classified_session_observation"
    assert row["known_non_session_history"] == "not_assessed"
    assert row["session_history"] == "zero_observed"
    inventory = cast(dict[str, dict[str, int]], row["terminal_inventory"])
    assert inventory["compile_cache"]["regular"] == 1
    assert row["directory_deleted"] is True
    assert TOKEN not in json.dumps(row)
    assert factory() is AttemptResources


def test_classified_session_write_cannot_pass_as_non_session_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
) -> None:
    peer = CLASSIFIED_PEER.replace(
        "inherited=0",
        "(agent/'sessions').mkdir();"
        "(agent/'sessions/session.jsonl').write_text('synthetic-session')"
        "\n    inherited=0",
    )
    database, description, execution_roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=peer
    )
    owned: list[Path] = []

    class RecordedWindow(ClassifiedSessionObservation):
        def __init__(
            self,
            root: Path,
            authority: CgroupReader,
            *,
            expected_settings: bytes | None = None,
        ) -> None:
            owned.append(root)
            super().__init__(root, authority, expected_settings=expected_settings)

    monkeypatch.setattr(adapter, "ClassifiedSessionObservation", RecordedWindow)
    try:
        with (
            pytest.raises(
                adapter.ResourceObservationRejected, match="resource_window_unknown"
            ),
            adapter.observe_launch_resources(
                reader, synthetic=True, classified=True
            ) as observations,
            prepare_launch(
                database,
                description,
                roots=execution_roots,
                credentials_dir=credentials,
                auth_mode="chatgpt_subscription",
            ) as prepared,
        ):
            session = prepared(description)
            assert observed(session)["ready"] is True
            session.terminate(5)
        assert observations.receipts[0]["result"] == "unknown"
        assert owned[0].exists()
    finally:
        for root in owned:
            shutil.rmtree(root, ignore_errors=True)


def test_nested_and_concurrent_takeover_are_rejected_and_original_restored(
    reader: CgroupReader,
) -> None:
    errors: list[str] = []
    with (
        pytest.raises(
            adapter.ResourceObservationRejected, match=r"^resource_observation_missing$"
        ),
        adapter.observe_launch_resources(reader, synthetic=True),
    ):
        active = factory()
        with (
            pytest.raises(
                adapter.ResourceObservationRejected, match=r"^resource_adapter_busy$"
            ),
            adapter.observe_launch_resources(reader, synthetic=True),
        ):
            pytest.fail("nested_context_entered")

        def another_thread() -> None:
            try:
                with adapter.observe_launch_resources(reader, synthetic=True):
                    errors.append("unexpected")
            except adapter.ResourceObservationRejected as error:
                errors.append(str(error))

        thread = threading.Thread(target=another_thread)
        thread.start()
        thread.join(5)
        assert not thread.is_alive()
        assert errors == ["resource_adapter_busy"]
        assert factory() is active
    assert factory() is AttemptResources


def test_remaining_descendant_keeps_tree_and_unknown(
    tmp_path: Path,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    resource = None
    try:
        with (
            pytest.raises(WindowRejected, match=r"^writers_not_quiescent$"),
            adapter.observe_launch_resources(reader, synthetic=True) as observations,
        ):
            resource = factory()(roots(tmp_path), None)
            (group(reader) / "cgroup.procs").write_text(
                f"{os.getpid()}\n{os.getpid() + 100000}\n"
            )
            resource.close()
        assert resource is not None and resource.root.is_dir()
        (receipt,) = observations.receipts
        assert receipt["result"] == "unknown"
        assert receipt["terminal_regular_files"] is None
        assert receipt["directory_deleted"] is False
        assert replay[0]._observer.closed
    finally:
        (group(reader) / "cgroup.procs").write_text(f"{os.getpid()}\n")
        if resource is not None:
            shutil.rmtree(resource.root, ignore_errors=True)


def test_overflow_blocks_deletion_before_history_is_hidden(
    tmp_path: Path,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    resource = None
    try:
        with (
            pytest.raises(
                adapter.ResourceObservationRejected, match=r"^resource_window_unknown$"
            ),
            adapter.observe_launch_resources(reader, synthetic=True) as observations,
        ):
            resource = factory()(roots(tmp_path), None)
            replay[0]._observer.ingest(struct.pack("iIII", -1, 0x4000, 0, 0))
            resource.close()
        assert resource is not None and resource.root.is_dir()
        (receipt,) = observations.receipts
        assert receipt["result"] == "unknown" and receipt["history"] == "unknown"
        assert receipt["directory_deleted"] is False
    finally:
        if resource is not None:
            shutil.rmtree(resource.root, ignore_errors=True)


def test_post_terminal_mutation_cannot_be_accepted_as_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    original_close = AttemptResources.close

    def mutate_then_delete(resource: AttemptResources) -> None:
        replay[0]._observer.ingest(struct.pack("iIII", 1, 0x2, 0, 0))
        original_close(resource)

    monkeypatch.setattr(AttemptResources, "close", mutate_then_delete)
    with (
        pytest.raises(
            adapter.ResourceObservationRejected, match=r"^resource_window_unknown$"
        ),
        adapter.observe_launch_resources(reader, synthetic=True) as observations,
    ):
        resource = factory()(roots(tmp_path), None)
        resource.close()
    (receipt,) = observations.receipts
    assert receipt["result"] == "unknown"
    assert receipt["post_terminal_mutation_events"] == 1
    assert receipt["directory_deleted"] is True
    assert "cleanup_mutation_unknown" in cast(list[str], receipt["reasons"])


def test_missing_delete_is_independently_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    monkeypatch.setattr(AttemptResources, "close", lambda _self: None)
    resource = None
    try:
        with (
            pytest.raises(WindowRejected, match=r"^deletion_unknown$"),
            adapter.observe_launch_resources(reader, synthetic=True) as observations,
        ):
            resource = factory()(roots(tmp_path), None)
            resource.close()
        assert resource is not None and resource.root.is_dir()
        assert observations.receipts[0]["result"] == "unknown"
    finally:
        if resource is not None:
            shutil.rmtree(resource.root, ignore_errors=True)


def test_context_does_not_delete_unclosed_attempts(
    tmp_path: Path,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    resource = None
    try:
        with (
            pytest.raises(
                adapter.ResourceObservationRejected,
                match=r"^resource_observation_incomplete$",
            ),
            adapter.observe_launch_resources(reader, synthetic=True) as observations,
        ):
            resource = factory()(roots(tmp_path), None)
        assert resource is not None and resource.root.is_dir()
        assert observations.receipts[0]["result"] == "unknown"
        assert replay[0]._observer.closed
        assert factory() is AttemptResources
    finally:
        if resource is not None:
            shutil.rmtree(resource.root, ignore_errors=True)


def test_original_init_virtual_close_does_not_leak_owned_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
) -> None:
    allocated: list[Path] = []
    real_outside = ExecutionRoots.outside

    def reject_attempt(self: ExecutionRoots, path: Path) -> bool:
        if path.name.startswith("paper-radar-pi-"):
            allocated.append(path)
            return False
        return real_outside(self, path)

    monkeypatch.setattr(ExecutionRoots, "outside", reject_attempt)
    with (
        pytest.raises(ExecutionError, match=r"^resources_invalid$"),
        adapter.observe_launch_resources(reader, synthetic=True) as observations,
    ):
        factory()(roots(tmp_path), None)
    assert len(allocated) == 1 and not allocated[0].exists()
    assert observations.receipts[0]["result"] == "unknown"
    assert observations.receipts[0]["directory_deleted"] is True
    assert factory() is AttemptResources


def test_model_popen_failure_closes_armed_resources_without_new_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
) -> None:
    database, description, execution_roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=PEER
    )
    fault = tmp_path / "model-exec-fault"
    instrument_wrapper(
        monkeypatch,
        f"""
execve = os.execve
fault_fd = os.open({str(fault)!r}, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
def fail_model(path, argv, env):
    if argv[2:4] == ['--mode', 'rpc']:
        os.write(fault_fd, b'model_execve')
        raise OSError('synthetic_model_launch_failure')
    return execve(path, argv, env)
os.execve = fail_model
""",
    )
    with (
        adapter.observe_launch_resources(reader, synthetic=True) as observations,
        prepare_launch(
            database,
            description,
            roots=execution_roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ) as prepared,
    ):
        with pytest.raises(RpcProblem) as error:
            prepared(description)
        assert error.value.reason is RpcReason.STARTUP_ERROR
    assert fault.read_bytes() == b"model_execve"
    assert observations.receipts[0]["result"] == "window_complete"
    assert observations.receipts[0]["directory_deleted"] is True


def test_observer_start_failure_before_model_cleans_tree_and_watch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
) -> None:
    windows: list[ForkObservation] = []
    allocated: list[Path] = []

    class StartFails(ForkObservation):
        def __init__(self, root: Path, authority: CgroupReader) -> None:
            super().__init__(root, authority, observer_factory=ReplayObserver)
            windows.append(self)
            allocated.append(root)

        def start(self) -> None:
            raise WindowRejected("cgroup_read_unknown")

    monkeypatch.setattr(adapter, "ForkObservation", StartFails)
    with (
        pytest.raises(WindowRejected, match=r"^cgroup_read_unknown$"),
        adapter.observe_launch_resources(reader, synthetic=True) as observations,
    ):
        factory()(roots(tmp_path), None)
    assert len(allocated) == 1 and not allocated[0].exists()
    assert windows[0]._observer.closed
    assert observations.receipts[0]["result"] == "unknown"
    assert factory() is AttemptResources


def test_reading_pending_status_does_not_poison_window_or_allow_receipt_mutation(
    tmp_path: Path,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    with adapter.observe_launch_resources(reader, synthetic=True) as observations:
        resource = factory()(roots(tmp_path), None)
        pending = observations.receipts
        assert pending[0]["result"] == "unknown"
        resource.close()
        snapshot = observations.receipts[0]
        cast(list[str], snapshot["reasons"]).append("synthetic-caller-mutation")
        observations.assert_complete()
    assert observations.receipts[0]["result"] == "window_complete"
    assert observations.receipts[0]["reasons"] == []


def test_cleanup_interruption_still_releases_context_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    real_close = ReplayObserver.close
    interrupted = False

    def interrupt_once(observer: ReplayObserver) -> None:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        real_close(observer)

    monkeypatch.setattr(ReplayObserver, "close", interrupt_once)
    resource = None
    try:
        with (
            pytest.raises(KeyboardInterrupt),
            adapter.observe_launch_resources(reader, synthetic=True) as observations,
        ):
            resource = factory()(roots(tmp_path), None)
        assert factory() is AttemptResources
        assert observations.receipts[0]["result"] == "unknown"
        with pytest.raises(
            adapter.ResourceObservationRejected, match=r"^resource_cleanup_interrupted$"
        ):
            observations.assert_complete()
        with (
            pytest.raises(
                adapter.ResourceObservationRejected,
                match=r"^resource_observation_missing$",
            ),
            adapter.observe_launch_resources(reader, synthetic=True),
        ):
            pass
    finally:
        for window in replay:
            window.close()
        if resource is not None:
            shutil.rmtree(resource.root, ignore_errors=True)


def test_watch_close_failure_cannot_leave_a_complete_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: CgroupReader,
    replay: list[ForkObservation],
) -> None:
    real_close = ReplayObserver.close
    failed = False

    def close_then_fail_once(observer: ReplayObserver) -> None:
        nonlocal failed
        real_close(observer)
        if not failed:
            failed = True
            raise OSError("synthetic_close_error")

    monkeypatch.setattr(ReplayObserver, "close", close_then_fail_once)
    with (
        pytest.raises(
            adapter.ResourceObservationRejected,
            match=r"^resource_observer_close_unknown$",
        ),
        adapter.observe_launch_resources(reader, synthetic=True) as observations,
    ):
        resource = factory()(roots(tmp_path), None)
        resource.close()
    assert replay[0]._observer.closed
    assert observations.receipts[0]["result"] == "unknown"
    assert "resource_observer_close_unknown" in cast(
        list[str], observations.receipts[0]["reasons"]
    )
    assert factory() is AttemptResources
