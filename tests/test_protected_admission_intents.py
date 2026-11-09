"""ADR0056 公开拒绝边界;仅临时来源及内核文件操作模型。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paper_radar.live_evidence.intents import ProtectedIntentLog
    from paper_radar.live_evidence.ledger import EvidenceLedger
    from tests.protected_intents_support import AppendOnlyKernel

import pytest


@pytest.mark.parametrize("attack", ["delete", "truncate", "rollback"])
def test_failed_helper_intent_cannot_be_cleared_by_product_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.types import BindingComponent
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    _, receipt, components = protected_admission(tmp_path / "evidence", monkeypatch)
    path = tmp_path / "evidence/pending.jsonl"
    before = path.read_bytes() if path.exists() else b""
    request = service.AdmissionRequest(
        use_for_id("boundary-low"),
        ExecutionBinding(tuple(components.items())),
        frozenset(BindingComponent),
    )
    assert service.load_admission_evidence(request, now=NOW).decision.executable is True
    monkeypatch.setattr(service, "_run_helper", lambda args: False)
    assert (
        service.request_revocation(receipt.receipt_id, "boundary-low", now=NOW) is False
    )
    # 此处故意越过内核模型破坏文件,核对缺失/截断/替换后仍拒绝。
    # 真正同uid syscall拒绝另由OS边界模型及owner现场负例证明。
    if attack == "delete":
        path.unlink()
    elif attack == "truncate":
        path.write_bytes(b"")
    else:
        replacement = tmp_path / "old-copy"
        replacement.write_bytes(before)
        replacement.chmod(0o660)
        replacement.replace(path)
    projected = service.load_admission_evidence(
        service.AdmissionRequest(
            use_for_id("boundary-low"),
            ExecutionBinding(tuple(components.items())),
            frozenset(BindingComponent),
        ),
        now=NOW,
    )
    assert projected.decision.executable is False
    assert projected.pending_revocation is True
    assert [reason.token for reason in projected.decision.reasons] == [
        "ledger_untrusted"
    ]


def empty_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[EvidenceLedger, ProtectedIntentLog, AppendOnlyKernel]:
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from tests.live_evidence_ledger_support import owner_uid, protected_root
    from tests.protected_intents_support import intent_log

    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    log, kernel = intent_log(ledger, monkeypatch)
    return ledger, log, kernel


@pytest.mark.parametrize(
    "operation", ["delete", "truncate", "overwrite", "rollback", "replace", "hardlink"]
)
def test_product_syscalls_cannot_remove_append_only_records_in_os_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    _, log, kernel = empty_log(tmp_path, monkeypatch)
    before = log.path.read_bytes()
    log.append(b'{"refusal":"synthetic"}')
    with pytest.raises(PermissionError, match="append_only_kernel_denied"):
        kernel.mutate(log.path, operation, before)
    assert log.path.read_bytes() == before + b'{"refusal":"synthetic"}\n'


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "flag_lost",
        "unsupported",
        "mode",
        "parent",
        "hardlink",
        "symlink",
        "full",
        "partial",
        "header",
    ],
)
def test_missing_or_untrusted_protected_log_never_means_no_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import os

    from paper_radar.live_evidence import intents
    from paper_radar.live_evidence.ledger import LedgerError

    ledger, log, kernel = empty_log(tmp_path, monkeypatch)
    if failure == "missing":
        log.path.unlink()
    elif failure == "flag_lost":
        kernel.flags.clear()
    elif failure == "unsupported":

        def unavailable(fd: int) -> int:
            raise OSError("synthetic_ioctl_not_supported")

        monkeypatch.setattr(intents, "_get_flags", unavailable)
    elif failure == "mode":
        log.path.chmod(0o666)
    elif failure == "parent":
        log.path.parent.chmod(0o777)
    elif failure == "hardlink":
        os.link(log.path, tmp_path / "linked")
    elif failure == "symlink":
        saved = tmp_path / "saved"
        log.path.rename(saved)
        log.path.symlink_to(saved)
    elif failure == "full":
        monkeypatch.setattr(intents, "MAX_INTENT_BYTES", log.path.stat().st_size)
    elif failure == "partial":
        with log.path.open("ab") as stream:
            stream.write(b"partial")
    else:
        log.path.write_bytes(b'{"format_version":99}\n')
    with pytest.raises(LedgerError, match="pending_revocation_unavailable"):
        log.read(ledger)


def test_cutover_permanently_revokes_old_receipts_and_requires_fresh_owner_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import timedelta

    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id
    from paper_radar.live_evidence.receipt import (
        ApprovedPlan,
        EvidenceReceipt,
        canonical_bytes,
        content_sha256,
    )
    from paper_radar.live_evidence.types import BindingComponent, Capability
    from tests.live_evidence_ledger_support import NOW
    from tests.live_evidence_lifecycle_support import activated
    from tests.protected_intents_support import intent_log
    from tests.screening_live_admission_support import REQUIRED

    ledger, old, binding = activated(
        tmp_path, capabilities=tuple(Capability(cap) for cap in REQUIRED), provider=True
    )
    assert all(
        item.evidence_active
        for item in EvidenceLifecycle(ledger).snapshot(now=NOW).evidence
    )
    log, _ = intent_log(ledger, monkeypatch)
    monkeypatch.setattr(service, "_ledger", lambda: ledger)
    lifecycle = EvidenceLifecycle(ledger)
    assert all(
        item.revoked and not item.evidence_active
        for item in lifecycle.snapshot(now=NOW).evidence
    )
    with pytest.raises(LedgerError, match="evidence_activation_empty"):
        lifecycle.activate(
            lifecycle.review(
                old.receipt_id,
                "boundary-low",
                binding=binding,
                checked_components=frozenset(BindingComponent),
                now=NOW,
            ),
            confirmation=old.receipt_id,
            now=NOW,
        )
    before_db, before_log = ledger.database.read_bytes(), log.path.read_bytes()
    assert log.provision(ledger, now=NOW) is False
    assert (ledger.database.read_bytes(), log.path.read_bytes()) == (
        before_db,
        before_log,
    )
    new_time = NOW + timedelta(seconds=1)
    with ledger.connection() as connection:
        old_plan = ApprovedPlan.model_validate_json(
            connection.execute("SELECT payload FROM plans").fetchone()[0]
        )
    new_plan = old_plan.model_copy(update={"plan_id": "new-current-evidence"})
    ledger.approve_plan(new_plan, now=new_time)
    data = old.model_dump()
    data.update(
        plan_id=new_plan.plan_id,
        plan_sha256=content_sha256(new_plan),
        started_at=new_time,
        completed_at=new_time,
    )
    data["claims"] = [
        claim | {"verified_at": new_time, "evidence_at": new_time}
        for claim in data["claims"]
    ]
    fresh = EvidenceReceipt.model_validate(data)
    source = ledger.root / "inbox/fresh.json"
    source.write_bytes(canonical_bytes(fresh))
    source.chmod(0o644)
    ledger.receive(source, now=new_time)
    request = service.AdmissionRequest(
        use_for_id("boundary-low"),
        ExecutionBinding(tuple(fresh.binding.items())),
        frozenset(BindingComponent),
    )
    assert (
        service.load_admission_evidence(request, now=new_time).decision.executable
        is False
    )
    review = lifecycle.review(
        fresh.receipt_id,
        "boundary-low",
        binding=binding,
        checked_components=frozenset(BindingComponent),
        now=new_time,
    )
    lifecycle.activate(review, confirmation=fresh.receipt_id, now=new_time)
    assert (
        service.load_admission_evidence(request, now=new_time).decision.executable
        is True
    )
    assert ledger.show(old.receipt_id).receipt == old
    log.path.unlink()
    with pytest.raises(LedgerError, match="pending_revocation_unavailable"):
        log.provision(ledger, now=new_time)


@pytest.mark.parametrize("root_success", [False, True])
def test_fsync_failure_never_reports_a_persistent_intent_without_root_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root_success: bool
) -> None:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    ledger, receipt, _ = protected_admission(tmp_path / "evidence", monkeypatch)
    calls = []

    def helper(arguments: tuple[str, ...]) -> bool:
        calls.append(arguments[0])
        if root_success:
            EvidenceLifecycle(ledger).tighten(
                receipt.receipt_id, "boundary-low", now=NOW
            )
        return root_success

    def failed(fd: int) -> None:
        raise OSError("synthetic_fsync_failure")

    monkeypatch.setattr(service, "_run_helper", helper)
    monkeypatch.setattr("os.fsync", failed)
    if root_success:
        assert (
            service.request_revocation(receipt.receipt_id, "boundary-low", now=NOW)
            is True
        )
        assert any(event.action == "evidence_revoked" for event in ledger.audit())
    else:
        with pytest.raises(LedgerError, match="pending_revocation_unavailable"):
            service.request_revocation(receipt.receipt_id, "boundary-low", now=NOW)
    assert calls == ["revoke"]


def test_helper_has_no_log_provisioning_or_reset_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import tightening

    def forbidden() -> None:
        raise AssertionError("helper不能打开授予/日志provision入口")

    monkeypatch.setattr(tightening, "EvidenceLedger", forbidden)
    assert tightening.tightening_main(["provision-intents"]) == 2


def test_owner_safety_projection_includes_protected_failed_helper_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import service
    from scripts import issue176_closure_workflow as workflow
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    ledger, receipt, _ = protected_admission(
        tmp_path / "evidence", monkeypatch, capabilities=("cwd_ancestors",)
    )
    monkeypatch.setattr(service, "_run_helper", lambda args: False)
    monkeypatch.setattr(workflow, "open_ledger", lambda: ledger)
    monkeypatch.setattr(workflow, "open_intents", service._intents, raising=False)
    monkeypatch.setattr(workflow, "now", lambda: NOW)
    assert (
        service.request_revocation(receipt.receipt_id, "boundary-low", now=NOW) is False
    )
    state = workflow.selected_state({"receipt_id": receipt.receipt_id})
    assert all(not row["qualified"] for row in state["selected"])
    assert all(row["raw_active"] and row["revoked"] for row in state["selected"])
    assert state["active_groups"] == []
    assert state["pending_revocation"] is True


def test_integrated_owner_bundle_freezes_cutover_and_new_plan_drill(
    tmp_path: Path,
) -> None:
    import json
    import tarfile
    from datetime import timedelta

    from paper_radar.live_evidence.deployment import build_deployment
    from tests.live_evidence_ledger_support import NOW
    from tests.site_collector_support import site_configuration

    output = tmp_path / "review"
    build_deployment(
        output,
        site_configuration(tmp_path).model_copy(
            update={
                "claim_uses": (
                    "boundary-low",
                    "boundary-high",
                    "value-low",
                    "value-high",
                    "read-low",
                    "read-high",
                )
            }
        ),
        starts_at=NOW,
        ends_at=NOW + timedelta(days=7),
        source_root=Path(__file__).resolve().parents[1],
        owner_closure=True,
    )
    with tarfile.open(output / "payload.tar") as archive:
        configuration = archive.extractfile("owner-closure.json")
        assert configuration is not None
        config = json.loads(configuration.read())
        workflow = archive.extractfile("owner-closure.py")
        assert workflow is not None
        source = workflow.read().decode()
    assert (
        config["plan_id"]
        == json.loads((output / "approved-plan.json").read_bytes())["plan_id"]
    )
    assert config["initial_evidence_activation"] == "required"
    assert config["protected_log_probe"] == "required"
    assert "receipt_id" not in config
    assert "PR_SET_NO_NEW_PRIVS" in source
    assert "</dev/tty" in (output / "run-g2.sh").read_text()
    assert "interactive=True" in source
    deploy = (output / "deploy.sh").read_text()
    assert deploy.index("provision-intents") < deploy.index("stage=collect")
    assert deploy.index("stage=receive") < deploy.index("owner-closure.py")


def test_initialization_never_exposes_a_product_writable_inode_before_append_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import stat

    from paper_radar.live_evidence import intents
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from tests.live_evidence_ledger_support import NOW, owner_uid, protected_root
    from tests.protected_intents_support import AppendOnlyKernel

    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    path = tmp_path / "intents/pending.jsonl"
    log = intents.ProtectedIntentLog(
        path,
        product_gid=os.getgid(),
        trust=LedgerTrust(owner_uid(), owner_uid() + 1, tmp_path),
    )
    kernel = AppendOnlyKernel()
    observed = []

    def seal(fd: int) -> None:
        exposed = stat.S_IMODE(path.parent.stat().st_mode) != 0o700 and bool(
            os.fstat(fd).st_mode & 0o020
        )
        assert not exposed, "product_write_exposed_before_append_flag"
        observed.append(True)
        kernel.set_append_only(fd)

    monkeypatch.setattr(intents, "_get_flags", kernel.get_flags)
    monkeypatch.setattr(intents, "_set_append_only", seal)
    assert log.provision(ledger, now=NOW) is True
    assert observed == [True]
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o755
    assert log.read(ledger) == ()


@pytest.mark.parametrize("probe_failure", [False, True])
def test_integrated_owner_drill_uses_new_receipt_manual_confirmations_and_durable_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe_failure: bool
) -> None:
    import json

    from typer.testing import CliRunner

    from paper_radar.live_evidence import cli, service, tightening
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from scripts import issue176_closure_workflow as workflow
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    ledger, receipt, _ = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        capabilities=("cwd_ancestors",),
        uses=("boundary-low", "value-low"),
        activate=False,
    )
    monkeypatch.setattr(workflow, "open_ledger", lambda: ledger)
    monkeypatch.setattr(workflow, "open_intents", service._intents)
    monkeypatch.setattr(workflow, "now", lambda: NOW)
    budgets = {"screening_budgets": {"count": 1, "identity_sha256": "original"}}
    monkeypatch.setattr(workflow, "budget_inventory", lambda: budgets)
    monkeypatch.setattr(service, "_run_helper", lambda args: False)
    prompts = []
    config = {
        "plan_id": receipt.plan_id,
        "drill_use": "value-low",
        "final_use": "boundary-low",
        "initial_activation": "required",
        "protected_log_probe": "required",
        "run_name": "new-current-plan",
    }

    def os_entry(arguments: list[str], *, interactive: bool = False) -> None:
        if arguments[0] == str(workflow.COLLECT):
            assert not interactive
        elif arguments[0] == str(workflow.OWNER):
            assert interactive
            prompts.append(arguments[-1])
            monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
            monkeypatch.setattr(cli, "_now", lambda: NOW)
            monkeypatch.setattr(cli, "_refresh_current_observation", lambda: None)
            result = CliRunner().invoke(
                cli.live_evidence_app, arguments[1:], input=receipt.receipt_id + "\n"
            )
            assert result.exit_code == 0, result.output
            assert "输入回执短 ID" in result.output
        elif arguments[0] == str(workflow.TIGHTEN):
            monkeypatch.setattr(tightening, "EvidenceLedger", lambda: ledger)
            monkeypatch.setattr(
                tightening,
                "datetime",
                type("Clock", (), {"now": staticmethod(lambda tz: NOW)}),
            )
            assert tightening.tightening_main(arguments[1:]) == 0
        else:
            assert arguments[-2] == "checkpoint"
            workflow.write_report(
                Path(arguments[-1]),
                workflow.selected_state(workflow.resolve_receipt(config)),
            )

    def product_os_boundary(selected: dict[str, str]) -> dict[str, bool]:
        if probe_failure:
            raise ValueError("closure_product_probe_failed")
        assert selected["receipt_id"] == receipt.receipt_id
        assert (
            service.request_revocation(receipt.receipt_id, "value-low", now=NOW)
            is False
        )
        return {
            "delete": True,
            "truncate": True,
            "overwrite": True,
            "replace": True,
            "hardlink": True,
            "clear_flag": True,
            "helper_failed_intent_persisted": True,
        }

    monkeypatch.setattr(workflow, "run_entry", os_entry)
    monkeypatch.setattr(workflow, "product_log_probe", product_os_boundary)
    destination = ledger.root / "new-current-plan"
    if probe_failure:
        with pytest.raises(ValueError, match="closure_product_probe_failed"):
            workflow.exercise(config, destination)
        assert prompts == ["boundary-low", "value-low"]
        assert not (destination / "safety-receipt.json").exists()
    else:
        workflow.exercise(config, destination)
        assert prompts == ["boundary-low", "value-low", "boundary-low"]
        failed = json.loads((destination / "helper-failed.json").read_bytes())
        assert failed["pending_revocation"] is True
        assert all(
            not item["qualified"] and item["raw_active"]
            for item in failed["selected"]
            if item["use_id"] == "value-low"
        )
        final = json.loads((destination / "safety-receipt.json").read_bytes())
        assert final["status"] == "completed"
        assert final["product_protection"]["helper_failed_intent_persisted"] is True
        assert final["requests"] == {"authentication": 0, "model": 0, "network": 0}
        assert final["business_budget_inventory_unchanged"] is True
        assert all(
            item.revoked
            for item in EvidenceLifecycle(ledger).snapshot(now=NOW).evidence
            if item.use.consumer.value == "value"
        )
    assert ledger.show(receipt.receipt_id).receipt == receipt


def test_failed_initial_sealing_keeps_private_directory_and_old_revocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import stat

    from paper_radar.live_evidence import intents
    from paper_radar.live_evidence.ledger import LedgerError, LedgerTrust
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from tests.live_evidence_ledger_support import NOW, owner_uid
    from tests.live_evidence_lifecycle_support import activated
    from tests.protected_intents_support import AppendOnlyKernel

    ledger, receipt, _ = activated(tmp_path)
    path = tmp_path / "intents/pending.jsonl"
    log = intents.ProtectedIntentLog(
        path,
        product_gid=os.getgid(),
        trust=LedgerTrust(owner_uid(), owner_uid() + 1, tmp_path),
    )
    kernel = AppendOnlyKernel()
    monkeypatch.setattr(intents, "_get_flags", kernel.get_flags)
    calls = []

    def unsupported(fd: int) -> None:
        calls.append(fd)
        raise OSError("synthetic_append_flag_unsupported")

    monkeypatch.setattr(intents, "_set_append_only", unsupported)
    with pytest.raises(LedgerError, match="pending_revocation_unavailable"):
        log.provision(ledger, now=NOW)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert all(
        item.revoked for item in EvidenceLifecycle(ledger).snapshot(now=NOW).evidence
    )
    before = path.read_bytes(), ledger.database.read_bytes()
    with pytest.raises(LedgerError, match="pending_revocation_unavailable"):
        log.provision(ledger, now=NOW)
    assert (path.read_bytes(), ledger.database.read_bytes()) == before
    assert len(calls) == 1
    assert ledger.show(receipt.receipt_id).receipt == receipt


def test_unknown_ioctl_platform_is_rejected_without_guessing_a_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import intents
    from paper_radar.live_evidence.ledger import LedgerError

    get_flags = intents._get_flags
    ledger, log, _ = empty_log(tmp_path, monkeypatch)
    monkeypatch.setattr(intents, "_get_flags", get_flags)
    monkeypatch.setattr("platform.machine", lambda: "unreviewed-abi")
    with pytest.raises(LedgerError, match="pending_revocation_unavailable"):
        log.read(ledger)


@pytest.mark.parametrize(
    "reason",
    [
        "intent_platform_unknown",
        "intent_capability_missing",
        "intent_filesystem_unavailable",
    ],
)
def test_readonly_preflight_refuses_before_archiving_old_runtime(
    tmp_path: Path, reason: str
) -> None:
    import hashlib

    from paper_radar.live_evidence.deployment import render_upgrade
    from tests.site_deployment_support import (
        deployment_sandbox,
        model_intent_preflight,
        run_script,
    )

    root, deploy, _ = deployment_sandbox(tmp_path)
    assert run_script(deploy).returncode == 0
    runtime = root / "usr/libexec/paperradar/live-evidence-runtime"
    payload = (runtime / "payload.sha256").read_text().strip()
    manifest = hashlib.sha256((runtime / "manifest.sha256").read_bytes()).hexdigest()
    script = model_intent_preflight(render_upgrade(payload, manifest), failure=reason)
    for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d", "/srv"):
        script = script.replace(prefix, str(root) + prefix)
    script = (
        script.replace("$(/usr/bin/id -u)", "0")
        .replace('$(/usr/bin/stat -c %u "$current")', "0")
        .replace('[ "$current" != / ]', f'[ "$current" != "{root}" ]')
    )
    upgrade = deploy.with_name("upgrade.sh")
    upgrade.write_text(script)
    upgrade.chmod(0o644)
    result = run_script(upgrade)
    assert result.returncode == 2
    assert f"[{reason}]".encode() in result.stderr
    assert runtime.is_dir()
    assert not runtime.with_name(runtime.name + ".archive-" + payload).exists()
    assert not (root / "var/lib/paperradar/live-evidence-intents").exists()


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ("supported", None),
        ("abi", "intent_platform_unknown"),
        ("capability", "intent_capability_missing"),
        ("readonly", "intent_filesystem_readonly"),
        ("ioctl", "intent_filesystem_unavailable"),
        ("partial", "intent_partial"),
    ],
)
def test_rendered_readonly_preflight_checks_actual_predicates_at_os_boundary(
    tmp_path: Path, state: str, reason: str | None
) -> None:
    import subprocess

    from paper_radar.live_evidence.deployment import render_intent_preflight

    root = tmp_path / "system"
    root.mkdir()
    (root / "caps").write_text(
        "CapEff:\t"
        + ("0000000000000000" if state == "capability" else "0000000000000200")
        + "\n"
    )
    if state == "partial":
        (root / "live-evidence-intents").mkdir(mode=0o700)
    uname, findmnt, lsattr = (
        tmp_path / name for name in ("uname", "findmnt", "lsattr")
    )
    uname.write_text(
        '#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo '
        + ("unreviewed" if state == "abi" else "x86_64")
        + ";; esac\n"
    )
    findmnt.write_text(
        "#!/bin/sh\necho "
        + ("ro,nosuid" if state == "readonly" else "rw,nosuid")
        + "\n"
    )
    lsattr.write_text("#!/bin/sh\nexit " + ("1" if state == "ioctl" else "0") + "\n")
    for path in (uname, findmnt, lsattr):
        path.chmod(0o755)
    source = (
        render_intent_preflight()
        .replace("/var/lib/paperradar", str(root))
        .replace("/proc/self/status", str(root / "caps"))
    )
    for original, replacement in (
        ("/usr/bin/uname", uname),
        ("/usr/bin/findmnt", findmnt),
        ("/usr/bin/lsattr", lsattr),
    ):
        source = source.replace(original, str(replacement))
    source = (
        'set -eu\nrefuse() { printf "refused [%s]\\n" "$1" >&2; exit 2; }\n'
        "protected() { :; }\n" + source
    )
    result = subprocess.run(["/bin/sh", "-c", source], capture_output=True, check=False)
    assert result.returncode == (0 if reason is None else 2)
    assert result.stderr == (
        b"" if reason is None else f"refused [{reason}]\n".encode()
    )
