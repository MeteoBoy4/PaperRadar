"""独立owner恢复工具;仅临时受保护来源/OS边界,不执行sudo或真实root。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_scoped_samefs_tempdir_survives_child_environment_clear_and_is_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import issue176_resume_after_backup_workflow as resume

    base = tmp_path / "tmp-base"
    base.mkdir(mode=0o1777)
    base.chmod(0o1777)
    log = tmp_path / "pending-model"
    log.write_bytes(b"synthetic-log")
    monkeypatch.setattr(resume, "TEMP_BASE", base)
    monkeypatch.setattr(resume, "ROOT_UID", os.getuid())
    monkeypatch.setattr(resume, "ROOT_GID", os.getgid())
    original = tempfile.tempdir

    def probe(config: dict[str, object]) -> dict[str, object]:
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            os.environ.clear()
            with tempfile.TemporaryDirectory() as child:
                path = Path(child)
                os.write(
                    write_fd,
                    json.dumps(
                        {"parent": str(path.parent), "device": path.stat().st_dev}
                    ).encode(),
                )
            os._exit(0)
        os.close(write_fd)
        with os.fdopen(read_fd, "rb") as stream:
            result = json.loads(stream.read())
        assert os.waitpid(pid, 0)[1] == 0
        return dict(result)

    owner = SimpleNamespace(
        open_intents=lambda: SimpleNamespace(path=log), product_log_probe=probe
    )
    result = resume.same_device_probe(owner, {})
    assert result == {"parent": str(base), "device": log.stat().st_dev}
    assert tempfile.tempdir == original
    assert log.read_bytes() == b"synthetic-log"


@pytest.fixture
def after_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    import hashlib

    from typer.testing import CliRunner

    from paper_radar.live_evidence import cli, service, tightening
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import (
        EvidenceLifecycle,
        use_for_id,
        use_id_for,
    )
    from paper_radar.live_evidence.types import BindingComponent
    from scripts import issue176_closure_workflow as owner
    from scripts import issue176_resume_after_backup_workflow as resume
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    # 此 fixture 模拟专用续行器实际导入的冻结 v4 runtime,不把目标改为当前开发版。
    monkeypatch.setattr(
        "paper_radar.pi_execution.current_binding.ADMISSION_POLICY_VERSION",
        "pi-admission-v4",
    )
    ledger, receipt, components = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        capabilities=("cwd_ancestors",),
        uses=("boundary-low", "value-low", "read-low"),
        activate=False,
    )
    monkeypatch.setattr(owner, "open_ledger", lambda: ledger)
    monkeypatch.setattr(owner, "open_intents", service._intents)
    monkeypatch.setattr(owner, "now", lambda: NOW)
    budgets = {"screening_budgets": {"count": 1, "identity_sha256": "original"}}
    monkeypatch.setattr(owner, "budget_inventory", lambda: budgets)
    runtime = ledger.root / "runtime"
    runtime.mkdir(mode=0o755)
    config = {
        "plan_id": receipt.plan_id,
        "run_name": "closure-fixture",
        "admission_policy": "pi-admission-v4",
        "drill_use": "value-low",
        "final_use": "boundary-low",
        "initial_activation": "required",
        "protected_log_probe": "required",
    }
    cfg = runtime / "owner-closure.json"
    cfg.write_text(json.dumps(config))
    cfg.chmod(0o644)
    script = runtime / "owner-closure.py"
    script.write_bytes(b"synthetic verified original")
    script.chmod(0o644)
    monkeypatch.setattr(resume, "RUNTIME", runtime)
    output = ledger.root / config["run_name"]
    output.mkdir(mode=0o755)
    lifecycle = EvidenceLifecycle(ledger)
    binding = ExecutionBinding(tuple(components.items()))

    def grant(use: str) -> None:
        review = lifecycle.review(
            receipt.receipt_id,
            use_id_for(use_for_id(use)),
            binding=binding,
            checked_components=frozenset(BindingComponent),
            now=NOW,
        )
        lifecycle.activate(review, confirmation=receipt.receipt_id, now=NOW)

    resolved = owner.resolve_receipt(config)
    grant("boundary-low")
    owner.write_report(output / "initial.json", owner.selected_state(resolved))
    owner.write_report(output / "business-before.json", {"budget_inventory": budgets})
    grant("value-low")
    owner.write_report(output / "drill-active.json", owner.selected_state(resolved))
    lifecycle.backup(output / "before-revoke.sqlite3")
    inputs = {
        "constraints_only_not_grant_authority": True,
        "receipt_id": receipt.receipt_id,
        "plan_id": receipt.plan_id,
        "run_name": config["run_name"],
        "admission_policy": "pi-admission-v4",
        "final_use": "boundary-low",
        "drill_use": "value-low",
        "payload_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "owner_script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "owner_config_sha256": hashlib.sha256(cfg.read_bytes()).hexdigest(),
        "checkpoint_sha256": {
            name: hashlib.sha256((output / name).read_bytes()).hexdigest()
            for name in resume.CHECKPOINTS
        },
        "expected_final_capabilities": ["cwd_ancestors"],
        "expected_drill_capabilities": ["cwd_ancestors"],
        "same_device_tempdir": "/var/tmp",
    }
    prompts = []
    actions = []

    def os_entry(arguments: list[str], *, interactive: bool = False) -> None:
        actions.append(Path(arguments[0]).name)
        if arguments[0] == str(owner.COLLECT):
            assert not interactive
        elif arguments[0] == str(owner.OWNER):
            assert interactive
            prompts.append(arguments[-1])
            monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
            monkeypatch.setattr(cli, "_now", lambda: NOW)
            monkeypatch.setattr(cli, "_refresh_current_observation", lambda: None)
            result = CliRunner().invoke(
                cli.live_evidence_app, arguments[1:], input=receipt.receipt_id + "\n"
            )
            assert result.exit_code == 0, result.output
        elif arguments[0] == str(owner.TIGHTEN):
            monkeypatch.setattr(tightening, "EvidenceLedger", lambda: ledger)
            monkeypatch.setattr(
                tightening,
                "datetime",
                type("Clock", (), {"now": staticmethod(lambda tz: NOW)}),
            )
            assert tightening.tightening_main(arguments[1:]) == 0
        else:
            assert arguments[-2] == "checkpoint"
            owner.write_report(Path(arguments[-1]), owner.selected_state(resolved))

    base = tmp_path / "tmp-base"
    base.mkdir(mode=0o1777)
    base.chmod(0o1777)
    monkeypatch.setattr(resume, "TEMP_BASE", base)
    monkeypatch.setattr(resume, "ROOT_UID", os.getuid())
    monkeypatch.setattr(resume, "ROOT_GID", os.getgid())

    def probe(selected: dict[str, str]) -> dict[str, bool]:
        assert tempfile.tempdir == str(base)
        monkeypatch.setattr(service, "_run_helper", lambda args: False)
        assert (
            service.request_revocation(receipt.receipt_id, "value-low", now=NOW)
            is False
        )
        return {
            name: True
            for name in (
                "delete",
                "truncate",
                "overwrite",
                "replace",
                "hardlink",
                "clear_flag",
                "helper_failed_intent_persisted",
            )
        }

    monkeypatch.setattr(owner, "run_entry", os_entry)
    monkeypatch.setattr(owner, "product_log_probe", probe)
    return SimpleNamespace(
        ledger=ledger,
        receipt=receipt,
        owner=owner,
        resume=resume,
        inputs=inputs,
        output=output,
        budgets=budgets,
        prompts=prompts,
        actions=actions,
        base=base,
    )


def test_resume_preserves_four_old_files_and_only_final_owner_confirmation(
    after_backup: SimpleNamespace,
) -> None:
    case = after_backup
    before = {
        name: (case.output / name).read_bytes() for name in case.resume.CHECKPOINTS
    }
    stages: list[str] = []
    case.resume.resume_after_backup(case.inputs, case.owner, stages.append)
    assert case.prompts == ["boundary-low"]
    assert {
        name: (case.output / name).read_bytes() for name in case.resume.CHECKPOINTS
    } == before
    receipt = json.loads((case.output / "safety-receipt.json").read_bytes())
    assert receipt["status"] == "completed" and receipt["resumed_after_backup"] is True
    assert receipt["business_budget_inventory_unchanged"] is True
    assert receipt["product_protection"]["helper_failed_intent_persisted"] is True
    final = json.loads((case.output / "final.json").read_bytes())
    assert case.owner.active_for(final, "boundary-low") == {"cwd_ancestors"}
    assert not case.owner.active_for(final, "value-low")
    assert stages[-1] == "completed"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("extra_phase", "resume_phase_changed"),
        ("checkpoint", "resume_source_integrity"),
        ("budget", "resume_business_budget_changed"),
        ("pending", "resume_pending_revocation"),
        ("revoked", "resume_revocation_changed"),
        ("not_active", "resume_active_scope_changed"),
        ("config", "resume_original_config_changed"),
        ("stopped", "resume_plan_invalid"),
        ("audit_stopped", "resume_plan_invalid"),
        ("expired", "resume_plan_invalid"),
        ("other_active", "resume_active_scope_changed"),
    ],
)
def test_resume_rejects_any_changed_starting_state_before_probe(
    after_backup: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    import hashlib

    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from tests.live_evidence_ledger_support import NOW

    case = after_backup
    if change == "extra_phase":
        (case.output / "helper-failed.json").write_bytes(b"prior phase")
    elif change == "checkpoint":
        (case.output / "initial.json").write_bytes(b"altered")
    elif change == "budget":
        monkeypatch.setattr(
            case.owner, "budget_inventory", lambda: {"changed": {"count": 9}}
        )
    elif change == "pending":
        monkeypatch.setattr(service, "_run_helper", lambda args: False)
        service.request_revocation(case.receipt.receipt_id, "value-low", now=NOW)
    elif change == "revoked":
        EvidenceLifecycle(case.ledger).tighten(
            case.receipt.receipt_id, "value-low", now=NOW
        )
    elif change == "not_active":
        EvidenceLifecycle(case.ledger).record_restore(now=NOW)
    elif change == "config":
        path = case.resume.RUNTIME / "owner-closure.json"
        data = json.loads(path.read_bytes())
        data["plan_id"] = "other"
        path.write_text(json.dumps(data))
        case.inputs["owner_config_sha256"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    elif change == "audit_stopped":
        with case.ledger.connection(writable=True) as connection:
            case.ledger._event(connection, "plan_stopped", case.receipt.plan_id, NOW)
    elif change == "expired":
        from datetime import timedelta

        monkeypatch.setattr(case.owner, "now", lambda: NOW + timedelta(days=2))
    elif change == "other_active":
        from paper_radar.live_evidence.evidence import ExecutionBinding
        from paper_radar.live_evidence.types import BindingComponent

        lifecycle = EvidenceLifecycle(case.ledger)
        binding = ExecutionBinding(tuple(case.receipt.binding.items()))
        review = lifecycle.review(
            case.receipt.receipt_id,
            "read-low",
            binding=binding,
            checked_components=frozenset(BindingComponent),
            now=NOW,
        )
        lifecycle.activate(review, confirmation=case.receipt.receipt_id, now=NOW)
    else:
        (case.ledger.root / (case.receipt.plan_id + ".stopped")).write_bytes(b"stopped")
    with pytest.raises(ValueError, match=reason):
        case.resume.resume_after_backup(case.inputs, case.owner)
    assert case.prompts == [] and case.actions == []
    assert not (case.output / "safety-receipt.json").exists()


@pytest.mark.parametrize("outcome", ["exdev", "false_result"])
def test_probe_failure_never_reaches_revoke_restore_or_activation(
    after_backup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    case = after_backup

    def failed(config: dict[str, str]) -> dict[str, bool]:
        if outcome == "exdev":
            raise ValueError("closure_product_probe_failed")
        return {"replace": False}

    monkeypatch.setattr(case.owner, "product_log_probe", failed)
    before = tempfile.tempdir
    reason = (
        "closure_product_probe_failed"
        if outcome == "exdev"
        else "resume_product_probe_incomplete"
    )
    with pytest.raises(ValueError, match=reason):
        case.resume.resume_after_backup(case.inputs, case.owner)
    assert tempfile.tempdir == before
    assert case.prompts == [] and case.actions == ["live-evidence-collect"]
    assert {path.name for path in case.output.iterdir()} == set(case.resume.CHECKPOINTS)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("mode", "resume_temp_untrusted"),
        ("symlink", "resume_temp_untrusted"),
        ("mount", "resume_temp_mount_mismatch"),
        ("unknown_mount", "resume_temp_mount_unknown"),
    ],
)
def test_samefs_adapter_rejects_untrusted_base_before_probe(
    after_backup: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    case = after_backup
    called = []

    def probe(config: dict[str, str]) -> dict[str, bool]:
        called.append(True)
        return {}

    monkeypatch.setattr(case.owner, "product_log_probe", probe)
    if change == "mode":
        case.base.chmod(0o777)
    elif change == "symlink":
        saved = case.base.with_suffix(".saved")
        case.base.rename(saved)
        case.base.symlink_to(saved, target_is_directory=True)
    elif change == "mount":
        identifiers = iter([1, 2])
        monkeypatch.setattr(case.resume, "mount_id", lambda fd: next(identifiers))
    else:

        def unknown(fd: int) -> int:
            raise ValueError("resume_temp_mount_unknown")

        monkeypatch.setattr(case.resume, "mount_id", unknown)
    previous = tempfile.tempdir
    with pytest.raises(ValueError, match=reason):
        case.resume.same_device_probe(case.owner, {})
    assert called == [] and tempfile.tempdir == previous


def test_lock_busy_is_controlled_and_original_lock_file_is_preserved(
    after_backup: SimpleNamespace,
) -> None:
    import fcntl

    case = after_backup
    path = case.ledger.root / "closure.lock"
    path.write_bytes(b"")
    path.chmod(0o644)
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="resume_lock_busy"):
            case.resume.acquire_lock(case.ledger)
    finally:
        os.close(fd)
    assert path.read_bytes() == b""


def test_failure_records_precise_stage_without_rewriting_old_phase(
    after_backup: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import sys

    case = after_backup
    stage = case.ledger.root / "new-resume-tool"
    stage.mkdir(mode=0o755)
    (stage / "workflow.py").write_bytes(b"synthetic")
    (stage / "workflow.py").chmod(0o644)
    (stage / "config.json").write_text(json.dumps(case.inputs))
    (stage / "config.json").chmod(0o644)
    lock = case.ledger.root / "closure.lock"
    lock.write_bytes(b"")
    lock.chmod(0o644)
    monkeypatch.setattr(case.resume, "__file__", str(stage / "workflow.py"))
    monkeypatch.setattr(sys, "argv", [str(stage / "workflow.py")])
    monkeypatch.setattr(case.resume, "load_owner", lambda inputs: case.owner)

    def failed(config: dict[str, str]) -> dict[str, bool]:
        raise ValueError("closure_product_probe_failed")

    monkeypatch.setattr(case.owner, "product_log_probe", failed)
    before = {
        name: (case.output / name).read_bytes() for name in case.resume.CHECKPOINTS
    }
    assert case.resume.main() == 2
    result = json.loads((stage / "failure.json").read_bytes())
    assert (
        result["stage"] == "same_device_product_probe"
        and result["reason"] == "closure_product_probe_failed"
    )
    assert (
        "stage=same_device_product_probe reason=closure_product_probe_failed"
        in capsys.readouterr().err
    )
    assert {
        name: (case.output / name).read_bytes() for name in case.resume.CHECKPOINTS
    } == before
    assert case.prompts == []


def test_restore_failure_stops_before_final_grant(
    after_backup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

    case = after_backup

    def failed(*args: object, **kwargs: object) -> None:
        raise ValueError("synthetic_restore_failed")

    monkeypatch.setattr(EvidenceLifecycle, "restore", failed)
    with pytest.raises(ValueError, match="synthetic_restore_failed"):
        case.resume.resume_after_backup(case.inputs, case.owner)
    assert case.prompts == [] and not (case.output / "safety-receipt.json").exists()
    assert (case.output / "drill-revoked.json").exists()


@pytest.mark.parametrize("swap", [False, True])
def test_resume_bundle_embeds_new_bytes_and_keeps_runtime_unchanged(
    after_backup: SimpleNamespace, tmp_path: Path, swap: bool
) -> None:
    import hashlib
    import subprocess

    from scripts.issue176_resume_after_backup import build_bundle
    from tests.live_admission_closure_support import bundle_model

    runtime, _, events, _ = bundle_model(tmp_path / "model")
    host = runtime.parents[3]
    inputs = after_backup.inputs | {
        "payload_sha256": "a" * 64,
        "manifest_sha256": hashlib.sha256(
            (runtime / "manifest.sha256").read_bytes()
        ).hexdigest(),
    }
    output = tmp_path / "new-package"
    build_bundle(output, inputs)
    original = (output / "workflow.py").read_bytes()
    protected_before = {
        path.relative_to(runtime): path.read_bytes()
        for path in runtime.rglob("*")
        if path.is_file()
    }
    sudo = tmp_path / "sudo-model"
    sudo.write_text(
        '#!/bin/sh\n[ "$1" = -k ] || exit 99\nshift\n'
        '[ "$1" = -- ] || exit 99\nshift\nexec "$@"\n'
    )
    sudo.chmod(0o755)
    if swap:
        secret = tmp_path / "synthetic-private"
        secret.write_bytes(b"private-marker-not-to-copy")
        secret.chmod(0o600)
        sudo.write_text(
            sudo.read_text().replace(
                'exec "$@"',
                f'/usr/bin/rm "{output / "workflow.py"}"\n'
                f'/usr/bin/ln -s "{secret}" "{output / "workflow.py"}"\nexec "$@"',
            )
        )
    source = (output / "run-resume.sh").read_text()
    for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d"):
        source = source.replace(prefix, str(host) + prefix)
    source = source.replace(
        "[ -t 0 ] || refuse interactive_tty_required", ": # TTY OS boundary"
    )
    source = source.replace('$(/usr/bin/id -u)" -eq 0', '0" -eq 0')
    source = (
        source.replace('$(/usr/bin/stat -c %u "$current")', "0")
        .replace('[ "$current" != / ]', f'[ "$current" != "{host}" ]')
        .replace(" -o root -g root", "")
    )
    source = source.replace("$(/usr/bin/stat -c %u /usr/bin/sudo.ws)", "0").replace(
        "$(/usr/bin/stat -c %a /usr/bin/sudo.ws)", "4755"
    )
    source = source.replace("/usr/bin/sudo.ws", str(sudo))
    runner = output / "model-run.sh"
    runner.write_text(source)
    result = subprocess.run(["/bin/sh", str(runner)], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode()
    staged = list(
        (host / "var/lib/paperradar").glob("live-evidence-resume-*/workflow.py")
    )
    assert len(staged) == 1 and staged[0].read_bytes() == original
    assert {
        path.relative_to(runtime): path.read_bytes()
        for path in runtime.rglob("*")
        if path.is_file()
    } == protected_before
    assert events.read_text() == "executed"
    archive = staged[0].with_name("uninstall.sh")
    text = archive.read_text()
    for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d"):
        text = text.replace(prefix, str(host) + prefix)
    text = (
        text.replace("$(/usr/bin/id -u)", "0")
        .replace('$(/usr/bin/stat -c %u "$current")', "0")
        .replace('[ "$current" != / ]', f'[ "$current" != "{host}" ]')
    )
    archive.write_text(text)
    result = subprocess.run(["/bin/sh", str(archive)], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode()
    assert (
        not staged[0].parent.exists()
        and staged[0].parent.with_suffix(".archive").is_dir()
    )
    assert {
        path.relative_to(runtime): path.read_bytes()
        for path in runtime.rglob("*")
        if path.is_file()
    } == protected_before


def test_device_mismatch_refuses_instead_of_counting_exdev_as_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import issue176_resume_after_backup_workflow as resume

    base = tmp_path / "temp-base"
    base.mkdir(mode=0o1777)
    base.chmod(0o1777)
    log = tmp_path / "log"
    log.write_bytes(b"synthetic")
    monkeypatch.setattr(resume, "TEMP_BASE", base)
    monkeypatch.setattr(resume, "ROOT_UID", os.getuid())
    monkeypatch.setattr(resume, "ROOT_GID", os.getgid())
    original = Path.stat

    def metadata(
        path: Path, *, follow_symlinks: bool = True
    ) -> os.stat_result | SimpleNamespace:
        result = original(path, follow_symlinks=follow_symlinks)
        if path == log:
            return SimpleNamespace(st_dev=result.st_dev + 1)
        return result

    monkeypatch.setattr(Path, "stat", metadata)

    def forbidden(config: dict[str, str]) -> dict[str, bool]:
        raise AssertionError("mismatch必须在实际probe前拒绝")

    owner = SimpleNamespace(
        open_intents=lambda: SimpleNamespace(path=log), product_log_probe=forbidden
    )
    with pytest.raises(ValueError, match="resume_temp_device_mismatch"):
        resume.same_device_probe(owner, {})


def test_builder_cli_is_nonprivileged_and_uses_explicit_classic_sudo(
    after_backup: SimpleNamespace, tmp_path: Path
) -> None:
    import subprocess
    import sys

    inputs = tmp_path / "constraints.json"
    inputs.write_text(json.dumps(after_backup.inputs))
    output = tmp_path / "review"
    script = (
        Path(__file__).resolve().parents[1] / "scripts/issue176_resume_after_backup.py"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--inputs",
            str(inputs),
            "--output",
            str(output),
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    runner = (output / "run-resume.sh").read_text()
    assert runner.count("exec /usr/bin/sudo.ws ") == 1
    assert "/usr/bin/sudo -" not in runner and 'source="$1/' not in runner
    assert "uninstall.sh" in (output / "SHA256SUMS").read_text()
    for name in ("run-resume.sh", "uninstall.sh"):
        assert (
            subprocess.run(
                ["/bin/sh", "-n", str(output / name)], capture_output=True, check=False
            ).returncode
            == 0
        )


def test_budget_change_on_refresh_refuses_before_probe(
    after_backup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = after_backup
    original = case.owner.run_entry

    def changed(arguments: list[str], *, interactive: bool = False) -> None:
        original(arguments, interactive=interactive)
        if arguments[0] == str(case.owner.COLLECT):
            monkeypatch.setattr(
                case.owner, "budget_inventory", lambda: {"changed": {"count": 4}}
            )

    monkeypatch.setattr(case.owner, "run_entry", changed)
    with pytest.raises(ValueError, match="resume_business_budget_changed"):
        case.resume.resume_after_backup(case.inputs, case.owner)
    assert case.actions == ["live-evidence-collect"] and case.prompts == []
    assert {path.name for path in case.output.iterdir()} == set(case.resume.CHECKPOINTS)
