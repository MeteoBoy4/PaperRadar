"""Independent D1: instrumented public launcher, Python peer and fixture cgroup.

This test-only resource subclass is an experimental collector adapter. It is
neither an unchanged production path nor actual service/cgroup evidence. Popen,
pre-exec isolation and pipe termination remain real; no Node/Pi/network is used.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from paper_radar.llm.rpc_types import RpcProblem, RpcReason
from paper_radar.pi_execution import ExecutionRoots, launcher, prepare_launch
from paper_radar.pi_execution.resources import AttemptResources
from scripts.issue167_fork_observation import (
    CgroupReader,
    ForkObservation,
    WindowRejected,
)
from scripts.issue167_h1_phase import Plan
from tests.pi_execution_support import TOKEN, launch_inputs, observed

PEER = f"""
import json,os,sys
from pathlib import Path
def inherited_count():
    count = 0
    for descriptor in range(3, 256):
        try:
            os.fstat(descriptor)
            count += 1
        except OSError:
            pass
    return count
agent = Path(os.environ['PI_CODING_AGENT_DIR'])
if sys.argv[1:3] == ['auth', 'print-bearer-token']:
    config = json.loads((agent / 'auth.json').read_text())
    (agent / 'auth-chain-metadata.json').write_text(json.dumps({{
        'inherited_descriptor_count': inherited_count()
    }}))
    print(config['token'])
else:
    transient = agent / 'temporary-synthetic-write'
    transient.write_bytes(b'fixed-nonsecret-file')
    transient.unlink()
    print(json.dumps({{
        'ready': True,
        'marker_received': os.environ.get('OPENAI_API_KEY') == {TOKEN!r},
        'inherited_descriptor_count': inherited_count()
    }}), flush=True)
    sys.stdin.buffer.read()
"""


def instrument_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, list[Path], list[dict[str, object]], list[ForkObservation]]:
    plan = Plan("bc567890abcd", os.getuid(), os.getgid(), network_mode="ipv4_only")
    cgroup_root = tmp_path / "cgroup-fixture"
    group = cgroup_root / "system.slice" / plan.unit
    group.mkdir(parents=True)
    members = group / "cgroup.procs"
    members.write_text(f"{os.getpid()}\n")
    own = tmp_path / "synthetic-self-cgroup"
    own.write_text(f"0::{plan.cgroup}\n")
    reader = CgroupReader(plan, cgroup_root=cgroup_root, self_cgroup=own)
    roots: list[Path] = []
    receipts: list[dict[str, object]] = []
    windows: list[ForkObservation] = []

    class ObservedResources(AttemptResources):
        def __init__(self, execution_roots: ExecutionRoots, proxy: str | None) -> None:
            # The original constructor can virtually call close on failure.
            self.window: ForkObservation | None = None
            self.finished = False
            super().__init__(execution_roots, proxy)
            roots.append(self.root)
            try:
                window = ForkObservation(self.root, reader)
                self.window = window
                windows.append(window)
                window.start()
            except BaseException:
                if self.window is not None:
                    self.window.close()
                # No model Popen has occurred before constructor completion.
                AttemptResources.close(self)
                raise

        def close(self) -> None:
            if self.finished:
                return
            if self.window is None:
                AttemptResources.close(self)
                return
            try:
                self.window.seal_terminal()
                AttemptResources.close(self)
                self.window.check_deleted()
                receipt = self.window.receipt()
                receipts.append(receipt)
                if receipt["result"] != "window_complete":
                    raise WindowRejected("observed_window_unknown")
                self.finished = True
            except WindowRejected:
                receipts.append(self.window.receipt())
                raise
            finally:
                self.window.close()

    monkeypatch.setattr(launcher, "AttemptResources", ObservedResources)
    return members, roots, receipts, windows


def test_public_prepare_launch_can_arm_before_real_model_exec_and_seal_before_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database, description, execution_roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=PEER
    )
    _members, roots, receipts, windows = instrument_resources(tmp_path, monkeypatch)
    try:
        with prepare_launch(
            database,
            description,
            roots=execution_roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ) as prepared:
            auth = json.loads((credentials / "auth-chain-metadata.json").read_text())
            assert auth["inherited_descriptor_count"] >= 1
            session = prepared(description)
            metadata = observed(session)
            assert metadata["ready"] is True
            assert metadata["marker_received"] is True
            inherited = metadata["inherited_descriptor_count"]
            assert type(inherited) is int and inherited >= 1
            session.terminate(5)
        assert len(roots) == len(receipts) == 1
        receipt = receipts[0]
        assert receipt["source"] == "synthetic_cgroup_fixture"
        assert receipt["event_source"] == "inotify"
        assert receipt["result"] == "window_complete"
        assert receipt["history"] == "observed_mutation"
        assert receipt["terminal_regular_files"] == 1  # Existing settings only.
        assert receipt["directory_deleted"] is True
        assert not roots[0].exists()
        assert TOKEN not in json.dumps(receipts)
        assert "temporary-synthetic-write" not in json.dumps(receipts)
    finally:
        for window in windows:
            window.close()
        for root in roots:
            shutil.rmtree(root, ignore_errors=True)
    captured = capsys.readouterr()
    assert TOKEN not in captured.out + captured.err


def test_group_termination_alone_cannot_delete_with_fixture_descendant_remaining(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database, description, execution_roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=PEER
    )
    members, roots, receipts, windows = instrument_resources(tmp_path, monkeypatch)
    try:
        with (
            pytest.raises(WindowRejected, match=r"^writers_not_quiescent$"),
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
            # Only fixture metadata: no process is created/signaled by this PID.
            members.write_text(f"{os.getpid()}\n{os.getpid() + 100000}\n")
            session.terminate(5)
        assert len(roots) == 1 and roots[0].is_dir()
        assert receipts and all(r["result"] == "unknown" for r in receipts)
        assert all(r["terminal_regular_files"] is None for r in receipts)
        assert all(r["directory_deleted"] is False for r in receipts)
        assert TOKEN not in json.dumps(receipts)
    finally:
        # The actual synthetic model was already terminated by the public pipe
        # layer. Retained trees are cleaned by the test, after clearing its fixture.
        members.write_text(f"{os.getpid()}\n")
        for window in windows:
            window.close()
        for root in roots:
            shutil.rmtree(root, ignore_errors=True)
    captured = capsys.readouterr()
    assert TOKEN not in captured.out + captured.err


def test_original_resource_init_failure_can_virtually_close_before_window_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, description, execution_roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=PEER
    )
    _members, roots, receipts, windows = instrument_resources(tmp_path, monkeypatch)
    allocated: list[Path] = []
    original_outside = ExecutionRoots.outside

    def reject_attempt(self: ExecutionRoots, path: Path) -> bool:
        if path.name.startswith("paper-radar-pi-"):
            allocated.append(path)
            return False
        return original_outside(self, path)

    monkeypatch.setattr(ExecutionRoots, "outside", reject_attempt)
    with prepare_launch(
        database,
        description,
        roots=execution_roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        with pytest.raises(RpcProblem) as problem:
            prepared(description)
        assert problem.value.reason == RpcReason.STARTUP_ERROR
    assert len(allocated) == 1
    assert not allocated[0].exists()
    assert not roots
    assert not receipts
    assert not windows
