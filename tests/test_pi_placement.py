"""Live-03 独立公共放置覆盖,不继承历史现场结论。"""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from paper_radar.live_evidence.receipt import UseId
from paper_radar.live_evidence.service import AdmissionRequest
from paper_radar.pi_execution import ExecutionError, prepare_launch
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.placement import PlacementTarget
from tests.pi_execution_support import launch_inputs
from tests.pi_placement_support import LocalPlacementPlatform, local_placement


def test_scope_is_blocked_until_verified_exec_and_no_target_action_precedes_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.pi_execution.placement import PlacedProcess

    platform = local_placement(monkeypatch)
    marker = tmp_path / "target-started"
    checks: list[str] = []

    def verify(_target: PlacementTarget, pid: int, _start: int, _unit: str) -> None:
        executable = os.readlink(f"/proc/{pid}/exe")
        checks.append(executable)
        assert not marker.exists()

    monkeypatch.setattr(platform, "verify", verify)
    process = PlacedProcess()
    try:
        assert not marker.exists()
        child = process.execute(
            ("/usr/bin/touch", str(marker)),
            env={},
            cwd=tmp_path,
            install=tmp_path,
            attempt=None,
            proxy_port=None,
            pass_fds=(),
        )
        child.wait(timeout=3)
        assert marker.exists()
        assert os.path.samefile(checks[-1], "/usr/bin/touch")
    finally:
        process.close()


def test_exec_identity_drift_never_releases_target_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.pi_execution.placement import PlacedProcess

    platform = local_placement(monkeypatch)
    marker = tmp_path / "target-started"

    def verify(_target: PlacementTarget, pid: int, _start: int, _unit: str) -> None:
        if os.path.samefile(f"/proc/{pid}/exe", "/usr/bin/touch"):
            raise ExecutionError("placement_mismatch")

    monkeypatch.setattr(platform, "verify", verify)
    process = PlacedProcess()
    with pytest.raises(ExecutionError, match="placement_mismatch"):
        process.execute(
            ("/usr/bin/touch", str(marker)),
            env={},
            cwd=tmp_path,
            install=tmp_path,
            attempt=None,
            proxy_port=None,
            pass_fds=(),
        )
    assert not marker.exists()
    process.close()


def test_missing_protected_placement_refuses_before_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    monkeypatch.undo()
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", _cwd)
    from paper_radar.live_evidence.ledger import EvidenceLedger

    monkeypatch.setattr(
        "paper_radar.pi_execution.placement.EvidenceLedger",
        lambda: EvidenceLedger(tmp_path / "absent-protected-ledger"),
    )
    with (
        pytest.raises(ExecutionError, match="placement_unavailable"),
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ),
    ):
        pytest.fail("must reject without protected placement")
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("consumer", ["screening", "read"])
def test_placement_drift_at_preclaim_spends_no_business_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    from paper_radar.pi_execution.admission_checkpoints import AdmissionCheckpoints

    if consumer == "screening":
        from tests.pi_execution_service_support import allow_synthetic, service_inputs

        service, task, _credentials = service_inputs(tmp_path, monkeypatch)
        allow_synthetic(monkeypatch)
        task_id = task.receipt_id
        before = service.tasks.status(task_id)
    else:
        from tests.read_execution_support import allow_engineering_path, setup

        read_service, read_task, _credentials = setup(tmp_path, monkeypatch)
        allow_engineering_path(monkeypatch)
        task_id = read_task.task_id
        read_before = read_service.tasks.task(task_id)
    from paper_radar.pi_execution import placement

    platform = placement.PLACEMENT_PLATFORM
    assert isinstance(platform, LocalPlacementPlatform)
    original = AdmissionCheckpoints.after_prepare

    def after_prepare(
        self: AdmissionCheckpoints, request: AdmissionRequest, binding: EvidenceBinding
    ) -> AdmissionRequest:
        result = original(self, request, binding)
        platform.refuse = True
        return result

    monkeypatch.setattr(AdmissionCheckpoints, "after_prepare", after_prepare)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        (service if consumer == "screening" else read_service).run_attempt(task_id)
    after = (
        service.tasks.status(task_id)
        if consumer == "screening"
        else read_service.tasks.task(task_id)
    )
    assert after == (before if consumer == "screening" else read_before)


@pytest.mark.parametrize("damage", ["child", "anchor", "recreated_slice", "ancestor"])
def test_actual_proc_and_kernel_identity_reject_same_path_or_ancestor_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from paper_radar.pi_execution import placement

    proc = tmp_path / "proc"
    cgroups = tmp_path / "cgroups"
    slice_path = cgroups / "paperradar.slice"
    slice_path.mkdir(parents=True)
    for pid, group in (
        (123, "/paperradar.slice/call.scope"),
        (456, "/paperradar.slice/paperradar-anchor.service"),
    ):
        directory = proc / str(pid)
        directory.mkdir(parents=True)
        # Literal stat fields through starttime (22), including a comm space.
        (directory / "stat").write_text(
            f"{pid} (controlled peer) S 1 123 123 0 -1 4194304 "
            "1 0 0 0 0 0 0 0 20 0 1 0 777 0\n"
        )
        (directory / "cgroup").write_text("0::" + group + "\n")
    target = placement.PlacementTarget.model_validate(
        {
            "format_version": 1,
            "slice": "paperradar.slice",
            "ancestors": [
                {
                    "path": path,
                    "device": node.stat().st_dev,
                    "inode": node.stat().st_ino,
                }
                for path, node in (("/paperradar.slice", slice_path), ("/", cgroups))
            ],
            "anchor_pid": 456,
            "anchor_start": 777,
            "anchor_cgroup": "/paperradar.slice/paperradar-anchor.service",
            "egress_digest": "1" * 64,
            "resolver_view": "/run/paper-radar/resolver/resolv.conf",
            "resolver_digest": "2" * 64,
        }
    )
    monkeypatch.setattr(placement, "_PROC_ROOT", proc)
    monkeypatch.setattr(placement, "_CGROUP_ROOT", cgroups)
    placement.verify_placement(target, 123, 777, "call.scope")
    reason = "placement_mismatch"
    if damage == "child":
        (proc / "123/cgroup").write_text("0::/outside/call.scope\n")
    elif damage == "anchor":
        (proc / "456/stat").write_text(
            (proc / "456/stat").read_text().replace("777", "778")
        )
        reason = "placement_anchor_invalid"
    elif damage == "recreated_slice":
        slice_path.rename(cgroups / "old.slice")
        slice_path.mkdir()
    else:
        cgroups.rename(tmp_path / "old-cgroups")
        cgroups.mkdir()
        (cgroups / "paperradar.slice").mkdir()
    with pytest.raises(ExecutionError, match=reason):
        placement.verify_placement(target, 123, 777, "call.scope")


@pytest.mark.parametrize(
    "failure", ["degraded", "no_linger", "no_anchor", "unavailable"]
)
def test_manager_linger_and_anchor_are_required(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import subprocess

    from paper_radar.pi_execution import placement

    local_placement(monkeypatch)
    monkeypatch.setattr(
        placement, "PLACEMENT_PLATFORM", placement.LinuxPlacementPlatform()
    )
    manager_query = (
        "/usr/bin/systemctl",
        "--user",
        "show",
        "--property=SystemState",
        "--value",
    )

    def run(
        argv: tuple[str, ...], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        if failure == "unavailable":
            raise OSError("private manager error")
        output = {
            manager_query: b"running\n",
            (
                "/usr/bin/loginctl",
                "show-user",
                str(os.getuid()),
                "--property=Linger",
                "--value",
            ): b"yes\n",
            (
                "/usr/bin/systemctl",
                "--user",
                "is-active",
                "paperradar-anchor.service",
            ): b"active\n",
        }[argv]
        if (
            (failure == "degraded" and argv == manager_query)
            or (failure == "no_linger" and "show-user" in argv)
            or (failure == "no_anchor" and "is-active" in argv)
        ):
            output = b"no\n"
        return subprocess.CompletedProcess(argv, 0, output, b"")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ExecutionError, match="placement_unavailable"):
        placement.check_placement_readiness()


@pytest.mark.parametrize("failure", ["exit", "timeout", "invalid"])
def test_bounded_preparation_distinguishes_peer_exit_timeout_and_protocol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import sys

    from paper_radar.pi_execution import placement

    platform = local_placement(monkeypatch)
    original = placement.LinuxPlacementPlatform.spawn

    def spawn(argv: tuple[str, ...], env: dict[str, str]) -> subprocess.Popen[bytes]:
        command: tuple[str, ...]
        if failure == "exit":
            command = ("/usr/bin/true",)
        elif failure == "timeout":
            command = ("/usr/bin/sleep", "30")
        else:
            command = (
                sys.executable,
                "-I",
                "-c",
                "import socket,sys,time; s=socket.socket(socket.AF_UNIX); "
                "s.connect(sys.argv[1]); s.sendall(b'X'); time.sleep(30)",
                argv[-2],
            )
        return original(platform, command, env)

    monkeypatch.setattr(platform, "spawn", spawn)
    reason = {
        "exit": "placement_peer_exited",
        "timeout": "placement_handshake_timeout",
        "invalid": "placement_handshake_invalid",
    }[failure]
    with pytest.raises(ExecutionError, match=reason):
        placement.PlacedProcess(timeout=0.2)


def test_scope_id_change_and_cleanup_failure_are_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    from paper_radar.pi_execution import placement

    platform = local_placement(monkeypatch)
    process = placement.PlacedProcess()
    monkeypatch.setattr(platform, "scope_identity", lambda *_args: (1, 3))
    with pytest.raises(ExecutionError, match="placement_mismatch"):
        process.recheck()
    original = shutil.rmtree

    def fail_cleanup(
        path: str | os.PathLike[str],
        *,
        onexc: Callable[[Callable[..., object], str, BaseException], object]
        | None = None,
    ) -> None:
        if str(path).startswith("/tmp/paperradar-placement-"):
            raise PermissionError("private cleanup detail")
        return original(path, onexc=onexc)

    monkeypatch.setattr(shutil, "rmtree", fail_cleanup)
    with pytest.raises(ExecutionError, match="cleanup_failed"):
        process.close()
    monkeypatch.setattr(shutil, "rmtree", original)
    process.close()


def test_resolver_digest_failure_does_not_modify_host_view() -> None:
    from paper_radar.pi_execution.resolver import apply_resolver_view

    before = Path("/etc/resolv.conf").read_bytes()
    with pytest.raises(ExecutionError, match="resolver_unavailable"):
        apply_resolver_view(Path("/etc/resolv.conf"), "0" * 64)
    assert Path("/etc/resolv.conf").read_bytes() == before


@pytest.mark.parametrize("consumer", ["screening", "read"])
@pytest.mark.parametrize("failure", ["manager", "stale", "drift", "untrusted"])
def test_placement_denial_preserves_temporary_and_durable_admission_distinction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, failure: str
) -> None:
    from paper_radar.pi_execution import placement
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        projected_admission,
        protected_admission,
    )

    use_id: UseId
    if consumer == "screening":
        service, task, credentials = product_inputs(tmp_path / "product", monkeypatch)
        task_id = task.receipt_id
        use_id = "boundary-low"
    else:
        from tests.read_execution_support import setup

        read_service, read_task, credentials = setup(tmp_path / "product", monkeypatch)
        task_id = read_task.task_id
        use_id = "read-low"
    _ledger, _receipt, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=(use_id,)
    )
    active_service = service if consumer == "screening" else read_service
    active_service._now = lambda: NOW
    assert projected_admission(components, use_id).decision.executable

    def reject(*_args: object, **_kwargs: object) -> None:
        if failure in {"stale", "untrusted"}:
            raise placement.PlacementError(
                "placement_unavailable",
                source_reason="observation_stale"
                if failure == "stale"
                else "source_untrusted",
            )
        raise ExecutionError(
            "placement_unavailable" if failure == "manager" else "placement_mismatch"
        )

    if failure in {"stale", "untrusted"}:
        monkeypatch.setattr(placement, "load_placement_target", reject)
    elif failure == "manager":
        monkeypatch.setattr(placement.PLACEMENT_PLATFORM, "manager_environment", reject)
    else:
        monkeypatch.setattr(placement.PLACEMENT_PLATFORM, "verify", reject)
    with pytest.raises(
        ExecutionError, match=r"placement_unavailable|placement_mismatch"
    ):
        active_service.run_attempt(task_id)
    assert not (credentials / "auth-observed.json").exists()
    result = projected_admission(components, use_id)
    assert result.pending_revocation == (failure in {"drift", "untrusted"})
    assert result.decision.executable == (failure in {"manager", "stale"})
    if consumer == "screening":
        assert service.tasks.status(task_id).used_attempts == 0
    else:
        assert read_service.tasks.task(task_id).attempts == ()


@pytest.mark.parametrize("damage", ["egress", "stale", "permission", "noncanonical"])
def test_protected_target_requires_current_observation_and_unchanged_trusted_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from datetime import timedelta

    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.pi_execution import placement
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    ledger, _receipt, _components = protected_admission(
        tmp_path / "evidence", monkeypatch
    )
    target = placement.PlacementTarget.model_validate(
        {
            "format_version": 1,
            "slice": "paperradar.slice",
            "ancestors": [
                {"path": "/paperradar.slice", "device": 1, "inode": 2},
                {"path": "/", "device": 1, "inode": 1},
            ],
            "anchor_pid": 123,
            "anchor_start": 777,
            "anchor_cgroup": "/paperradar.slice/paperradar-anchor.service",
            "egress_digest": "b" * 64,
            "resolver_view": "/run/paper-radar/resolver/resolv.conf",
            "resolver_digest": "2" * 64,
        }
    )
    source = ledger.root / "inbox" / placement.TARGET_FILENAME
    source.write_bytes(canonical_bytes(target))
    source.chmod(0o644)
    monkeypatch.setattr(placement, "EvidenceLedger", lambda: ledger)
    assert placement.load_placement_target(now=NOW) == target
    now = NOW
    reason = "placement_unavailable"
    if damage == "egress":
        source.write_bytes(
            canonical_bytes(target.model_copy(update={"egress_digest": "c" * 64}))
        )
        reason = "placement_mismatch"
    elif damage == "stale":
        now += timedelta(seconds=61)
    elif damage == "permission":
        source.chmod(0o666)
    else:
        source.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(ExecutionError, match=reason) as caught:
        placement.load_placement_target(now=now)
    if damage == "stale":
        assert isinstance(caught.value, placement.PlacementError)
        assert caught.value.source_reason == "observation_stale"
    elif damage == "noncanonical":
        assert isinstance(caught.value, placement.PlacementError)
        assert caught.value.source_reason == "source_integrity"


def test_previous_auth_policy_manifest_keeps_exact_frozen_bytes() -> None:
    import hashlib

    source = Path(__file__).parent / "fixtures/live-admission-source-guard-v6.json"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "df039edfb53f85b526c7828984dda44d51c3300a65a07e833b4a4dffc3916223"
    )
