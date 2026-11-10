"""外部审阅回归:真实共享权威经两正式消费者保持分项收紧边界。"""

from datetime import timedelta
from pathlib import Path

import pytest

from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
from paper_radar.live_evidence.observation import CurrentObservation
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    EvidenceReceipt,
    UseId,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.types import BindingComponent, Capability
from paper_radar.pi_execution.errors import ExecutionError
from tests.live_evidence_ledger_support import NOW, plan
from tests.read_execution_support import setup
from tests.screening_live_admission_support import product_inputs, protected_admission
from tests.test_owner_resume_after_backup import after_backup as after_backup


def test_v4_resume_refuses_current_v5_runtime_without_retargeting(
    after_backup: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    assert isinstance(after_backup, SimpleNamespace)
    case = after_backup
    before = {
        name: (case.output / name).read_bytes() for name in case.resume.CHECKPOINTS
    }
    monkeypatch.setattr(
        "paper_radar.pi_execution.current_binding.ADMISSION_POLICY_VERSION",
        "pi-admission-v5",
    )
    with pytest.raises(ValueError, match="resume_policy_changed"):
        case.resume.preflight(case.inputs, case.owner)
    assert case.inputs["admission_policy"] == "pi-admission-v4"
    assert before == {
        name: (case.output / name).read_bytes() for name in case.resume.CHECKPOINTS
    }
    assert case.prompts == []


@pytest.mark.parametrize("rebind_manifest", [False, True])
def test_disk_source_change_is_rejected_by_a_cold_guard_process(
    tmp_path: Path, rebind_manifest: bool
) -> None:
    import hashlib
    import json
    import shutil
    import subprocess
    import sys

    from tests import test_live_admission_source_guard as guard

    for relative in guard.SOURCE_FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(guard.ROOT / relative, target)
    copied_test = tmp_path / "tests/test_live_admission_source_guard.py"
    copied_test.parent.mkdir(parents=True)
    shutil.copyfile(Path(guard.__file__), copied_test)
    manifest_path = tmp_path / "tests/fixtures" / guard.MANIFEST.name
    manifest_path.parent.mkdir(parents=True)
    shutil.copyfile(guard.MANIFEST, manifest_path)
    changed_relative = "scripts/issue176_resume_after_backup_workflow.py"
    changed = tmp_path / changed_relative
    changed.write_bytes(changed.read_bytes() + b"\n# unreviewed source change\n")
    if rebind_manifest:
        manifest = json.loads(manifest_path.read_bytes())
        manifest["files"][changed_relative] = hashlib.sha256(
            changed.read_bytes()
        ).hexdigest()
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    # 冷进程从磁盘重读源码/清单,不复用父进程中的dict或授予结论。
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import runpy,sys; module=runpy.run_path(sys.argv[1]); "
            "module['test_admission_sources_match_reviewed_policy_manifest']()",
            str(copied_test),
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    expected = "policy_version_must_change" if rebind_manifest else changed_relative
    assert expected in result.stderr.decode()


def test_source_guard_explicitly_covers_resume_and_grant_authority() -> None:
    from tests.test_live_admission_source_guard import SOURCE_FILES

    assert {
        "scripts/issue176_resume_after_backup.py",
        "scripts/issue176_resume_after_backup_workflow.py",
        "src/paper_radar/pi_execution/admission_checkpoints.py",
        "src/paper_radar/live_evidence/collector.py",
        "src/paper_radar/live_evidence/site_tree.py",
        "src/paper_radar/live_evidence/cli.py",
        "src/paper_radar/pi_supply/filesystem.py",
    } <= set(SOURCE_FILES)


def test_owner_closure_argument_rejection_gives_chinese_next_step(
    tmp_path: Path,
) -> None:
    import subprocess

    from scripts.issue176_closure import build_bundle

    output = tmp_path / "review"
    build_bundle(
        output,
        payload_sha256="a" * 64,
        manifest_sha256="b" * 64,
        receipt_id="0123456789abcdef",
    )
    result = subprocess.run(
        ["/bin/sh", str(output / "run-owner.sh"), "sensitive-argument"],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    message = result.stderr.decode()
    assert "封印操作拒绝" in message
    assert "stage=user_preflight" in message
    assert "reason=arguments_invalid" in message
    assert "请" in message
    assert "sensitive-argument" not in message


def test_owner_resume_rejection_gives_chinese_next_step(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    from scripts import issue176_resume_after_backup_workflow as resume

    monkeypatch.setattr(sys, "argv", ["workflow.py", "sensitive-argument"])
    assert resume.main() == 2
    message = capsys.readouterr().err
    assert "封印操作拒绝" in message
    assert "stage=inputs" in message
    assert "reason=resume_protected_entry_required" in message
    assert "请" in message
    assert "sensitive-argument" not in message


def test_owner_resume_never_echoes_an_unknown_exception_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import os
    import sys

    from scripts import issue176_resume_after_backup_workflow as resume

    source = tmp_path / "workflow.py"
    (tmp_path / "config.json").write_text("{}")
    monkeypatch.setattr(resume, "__file__", str(source))
    monkeypatch.setattr(resume, "ROOT_UID", os.geteuid())
    monkeypatch.setattr(sys, "argv", [str(source)])

    def invalid(inputs: object) -> None:
        raise ValueError("sensitive_token_in_exception")

    monkeypatch.setattr(resume, "validate_inputs", invalid)
    assert resume.main() == 2
    message = capsys.readouterr().err
    assert "reason=resume_operation_failed" in message
    assert "sensitive_token_in_exception" not in message


def test_owner_cli_uses_qualified_evidence_activation_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from paper_radar.cli import app
    from paper_radar.live_evidence import cli

    ledger, receipt, _ = protected_admission(
        tmp_path / "evidence", monkeypatch, activate=False
    )
    monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
    monkeypatch.setattr(cli, "_refresh_current_observation", lambda: None)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    result = CliRunner().invoke(
        app,
        [
            "live-evidence",
            "activate",
            "--receipt-id",
            receipt.receipt_id,
            "--use-id",
            "boundary-low",
        ],
        input="wrong\n",
    )
    assert result.exit_code == 2
    assert "[evidence_activation_confirmation_mismatch]" in result.output


def test_registry_rejects_an_empty_use_registry() -> None:
    from paper_radar.live_evidence.registry import AdmissionRegistry
    from paper_radar.live_evidence.types import RegistryError

    with pytest.raises(RegistryError, match="admission_use_undefined"):
        AdmissionRegistry("empty-v1", ())


@pytest.mark.parametrize(
    "expression",
    [
        "_evidence_for(binding)",
        "service._evidence_for(binding)",
        'getattr(service, "_evidence_for")(binding)',
    ],
)
def test_unreachable_guard_catches_reads_in_any_product_module(
    tmp_path: Path, expression: str
) -> None:
    from tests.live_admission_source_support import legacy_alias_reads

    source = tmp_path / "other/module.py"
    source.parent.mkdir()
    source.write_text(expression + "\n")
    assert legacy_alias_reads(tmp_path) == ("other/module.py:1",)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("isolation", "outside-read-denied"),
        ("outside-read-denied", "outside-read-denied"),
        ("cwd-write-denied", "cwd-write-denied"),
        ("install-write-denied", "install-write-denied"),
        ("attempt-write-allowed", "attempt-write-allowed"),
        ("core-zero", "core-zero"),
    ],
)
def test_isolation_probe_reports_controlled_case_for_each_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected: str,
) -> None:
    import errno
    import os
    import resource

    from paper_radar.live_evidence import sealed_runtime as runtime

    cwd, install = tmp_path / "cwd", tmp_path / "install"
    cwd.mkdir()
    install.mkdir()
    monkeypatch.setattr(runtime, "check_cwd", lambda: cwd)

    def boundary(*args: object) -> object:
        def apply() -> None:
            if failure == "isolation":
                raise RuntimeError("secret-probe-exception")

        return apply

    monkeypatch.setattr(runtime, "IsolationBoundary", boundary)
    parent_pid = os.getpid()
    original_read = Path.read_bytes
    original_write = Path.write_bytes
    original_open = os.open

    def read(path: Path) -> bytes:
        if os.getpid() != parent_pid and path.name == "synthetic-outside":
            if failure == "outside-read-denied":
                raise RuntimeError("secret-probe-exception")
            raise PermissionError(errno.EACCES, "synthetic denied")
        return original_read(path)

    def write(path: Path, data: bytes) -> int:
        if path.name == "allowed" and failure == "attempt-write-allowed":
            raise RuntimeError("secret-probe-exception")
        return original_write(path, data)

    def open_file(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if flags & os.O_TMPFILE == os.O_TMPFILE:
            case = "cwd-write-denied" if path == cwd else "install-write-denied"
            if failure == case:
                raise RuntimeError("secret-probe-exception")
            raise PermissionError(errno.EPERM, "synthetic denied")
        return original_open(path, flags, mode, dir_fd=dir_fd)

    def core_limit(resource: int) -> tuple[int, int]:
        raise RuntimeError("secret-probe-exception")

    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(Path, "write_bytes", write)
    monkeypatch.setattr(os, "open", open_file)
    monkeypatch.setattr(resource, "getrlimit", core_limit)
    results = runtime.isolation_probe(install, proxy=None)
    assert results[-1] == (expected, False)
    assert all(passed for _, passed in results[:-1])
    assert "secret-probe-exception" not in repr(results)


@pytest.mark.parametrize("use_id", ["boundary-low", "read-low"])
@pytest.mark.parametrize("gap", ["expired", "not_activated", "unknown"])
def test_mixed_drift_only_revokes_affected_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    use_id: UseId,
    gap: str,
) -> None:
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.service import (
        AdmissionRequest,
        load_admission_evidence,
    )
    from paper_radar.pi_execution.service import PiExecution
    from paper_radar.read_execution.service import ReadExecution

    ledger, receipt, components = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        uses=(use_id,),
        activate=False,
        claim_overrides=(
            {"rpc_eof": {"status": "unknown", "verified_at": None}}
            if gap == "unknown"
            else None
        ),
    )
    lifecycle = EvidenceLifecycle(ledger)
    review = lifecycle.review(
        receipt.receipt_id,
        use_id,
        binding=ExecutionBinding(tuple(components.items())),
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    lifecycle.activate(review, confirmation=receipt.receipt_id, now=NOW)
    if gap == "not_activated":
        # 新接收的独立分项没有继承旧回执的证据激活。
        approved = ApprovedPlan.model_validate(
            plan().model_dump() | {"plan_id": "new-eof", "kind": "model_six_cell"}
        )
        ledger.approve_plan(approved, now=NOW)
        refreshed = EvidenceReceipt.model_validate(
            receipt.model_dump()
            | {
                "plan_id": approved.plan_id,
                "plan_sha256": content_sha256(approved),
                "claims": [
                    claim for claim in receipt.claims if claim.capability == "rpc_eof"
                ],
            }
        )
        source = ledger.root / "inbox/refreshed.json"
        source.write_bytes(canonical_bytes(refreshed))
        source.chmod(0o644)
        ledger.receive(source, now=NOW)
    now = NOW + timedelta(days=30) if gap == "expired" else NOW
    before = lifecycle.snapshot(now=now)
    components[BindingComponent.CWD_ANCESTORS] = "c" * 64
    observation = CurrentObservation(
        observed_at=now,
        binding=components,
        checked_components=tuple(BindingComponent),
    )
    (ledger.root / "inbox/current-observation.json").write_bytes(
        canonical_bytes(observation)
    )
    consumer: PiExecution | ReadExecution
    if use_id == "boundary-low":
        consumer, task, _ = product_inputs(tmp_path / "consumer", monkeypatch)
        identifier = task.receipt_id
    else:
        consumer, read_task, _ = setup(tmp_path / "consumer", monkeypatch)
        identifier = read_task.task_id
    consumer._now = lambda: now
    with pytest.raises(ExecutionError, match="evidence_missing"):
        consumer.run_attempt(identifier)
    projection = load_admission_evidence(
        AdmissionRequest(
            use_for_id(use_id),
            ExecutionBinding(tuple(components.items())),
            frozenset(BindingComponent),
        ),
        now=now,
    )
    assert not projection.decision.executable
    assert projection.pending_revocation
    affected = projection.decision.for_capability(Capability.CWD_ANCESTORS)
    assert affected.revoked
    unrelated = projection.decision.for_capability(Capability.RPC_EOF)
    assert not unrelated.revoked
    assert not unrelated.qualified
    assert {reason.token for reason in unrelated.reasons} == {
        "expired": {"evidence_expired"},
        "not_activated": {"evidence_not_activated"},
        "unknown": {"capability_required:rpc_eof", "evidence_not_activated"},
    }[gap]
    assert all(
        not item.revoked
        for item in projection.decision.capabilities
        if item.capability is not Capability.CWD_ANCESTORS
    )
    after = lifecycle.snapshot(now=now)
    assert tuple(item.claim for item in after.evidence) == tuple(
        item.claim for item in before.evidence
    )
    assert ledger.show(receipt.receipt_id).receipt == receipt
