"""#176 收口公共边界;仅临时账本与OS模型,不操作真实站点。"""

from pathlib import Path

import pytest


def test_closure_bundle_is_bound_to_runtime_and_never_confirms_activation(
    tmp_path: Path,
) -> None:
    from scripts.issue176_closure import build_bundle

    output = tmp_path / "review"
    build_bundle(
        output,
        payload_sha256="a" * 64,
        manifest_sha256="b" * 64,
        receipt_id="0123456789abcdef",
    )
    runner = (output / "run-owner.sh").read_text()
    workflow = (output / "workflow.py").read_text()
    assert runner.count("/usr/bin/sudo ") == 1
    assert "-I -S -B" in runner
    assert "old_runtime_members" in runner
    assert "old_runtime_integrity" in runner
    assert "b" * 64 in runner
    assert "a" * 64 in (output / "config.json").read_text()
    assert "confirmation=" not in workflow
    assert "typer.prompt" not in workflow
    assert "--use-id" in workflow
    assert "value-low" in (output / "config.json").read_text()
    assert "boundary-low" in (output / "config.json").read_text()
    assert "sudoers" not in (output / "SHA256SUMS").read_text()


@pytest.mark.parametrize(
    "failure", [None, "drill_activation", "revoke", "restore", "final_activation"]
)
def test_owner_workflow_restores_history_without_reviving_revoked_cell_or_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    import json

    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.ledger import EvidenceLedger
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.types import BindingComponent
    from scripts import issue176_closure_workflow as workflow
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    ledger, receipt, components = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        uses=("boundary-low", "value-low"),
        activate=False,
    )
    lifecycle = EvidenceLifecycle(ledger)
    review = lifecycle.review(
        receipt.receipt_id,
        "boundary-low",
        binding=ExecutionBinding(tuple(components.items())),
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    lifecycle.activate(review, confirmation=receipt.receipt_id, now=NOW)
    monkeypatch.setattr(workflow, "now", lambda: NOW)
    monkeypatch.setattr(
        workflow, "open_ledger", lambda: EvidenceLedger(ledger.root, trust=ledger.trust)
    )
    budgets: dict[str, dict[str, int | str]] = {
        "screening_budgets": {"count": 1, "identity_sha256": "unchanged"}
    }
    monkeypatch.setattr(workflow, "budget_inventory", lambda: budgets.copy())
    config = {
        "receipt_id": receipt.receipt_id,
        "drill_use": "value-low",
        "final_use": "boundary-low",
        "run_name": "closure-model",
    }
    prompts: list[str] = []
    children: list[str] = []

    def subprocess_boundary(arguments: list[str], *, interactive: bool = False) -> None:
        from typer.testing import CliRunner

        from paper_radar.live_evidence import cli
        from paper_radar.live_evidence.tightening import tightening_main

        if arguments[0] == str(workflow.COLLECT):
            assert not interactive
        elif arguments[0] == str(workflow.OWNER):
            assert interactive
            monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
            monkeypatch.setattr(cli, "_now", lambda: NOW)
            monkeypatch.setattr(cli, "_refresh_current_observation", lambda: None)
            prompts.append(arguments[-1])
            if failure == (
                "drill_activation"
                if arguments[-1] == "value-low"
                else "final_activation"
            ):
                raise ValueError("closure_entry_failed")
            result = CliRunner().invoke(
                cli.live_evidence_app, arguments[1:], input=receipt.receipt_id + "\n"
            )
            assert result.exit_code == 0, result.output
            assert "输入回执短 ID" in result.output
        elif arguments[0] == str(workflow.TIGHTEN):
            if failure == "revoke":
                raise ValueError("closure_entry_failed")
            monkeypatch.setattr(
                "paper_radar.live_evidence.tightening.EvidenceLedger", lambda: ledger
            )
            monkeypatch.setattr(
                "paper_radar.live_evidence.tightening.datetime",
                type("Clock", (), {"now": staticmethod(lambda tz: NOW)}),
            )
            assert tightening_main(arguments[1:]) == 0
        else:
            assert arguments[1:4] == ["-I", "-S", "-B"]
            assert arguments[-2] == "checkpoint"
            children.append(Path(arguments[-1]).name)
            workflow.write_report(Path(arguments[-1]), workflow.selected_state(config))

    monkeypatch.setattr(workflow, "run_entry", subprocess_boundary)
    output = ledger.root / "closure-model"
    if failure is not None:
        if failure == "restore":

            def restore_failure(*args: object, **kwargs: object) -> None:
                raise ValueError("closure_entry_failed")

            monkeypatch.setattr(EvidenceLifecycle, "restore", restore_failure)
        with pytest.raises(ValueError, match="closure_entry_failed"):
            workflow.exercise(config, output)
        assert not (output / "safety-receipt.json").exists()
        current = workflow.selected_state(config)
        assert bool(workflow.active_for(current, "boundary-low")) is (
            failure != "final_activation"
        )
        if failure in {"restore", "final_activation"}:
            assert not workflow.active_for(current, "value-low")
            assert any(
                item["revoked"]
                for item in current["selected"]
                if item["use_id"] == "value-low"
            )
        assert ledger.show(receipt.receipt_id).receipt == receipt
        assert workflow.budget_inventory() == budgets
        return
    workflow.exercise(config, output)
    assert prompts == ["value-low", "boundary-low"]
    assert children == [
        "drill-active.json",
        "drill-revoked.json",
        "restored.json",
        "final.json",
    ]
    restored = json.loads((output / "restored.json").read_bytes())
    assert restored["active_groups"] == []
    final = json.loads((output / "final.json").read_bytes())
    assert final["active_groups"] == [[receipt.receipt_id, "boundary-low"]]
    assert all(
        item["revoked"] and not item["active"]
        for item in final["selected"]
        if item["use_id"] == "value-low"
    )
    safety = json.loads((output / "safety-receipt.json").read_bytes())
    assert safety["status"] == "completed"
    assert safety["business_budget_inventory_unchanged"] is True
    assert safety["requests"] == {"authentication": 0, "model": 0, "network": 0}
    assert safety["capabilities"]
    assert all(
        claim["verified_at"] == NOW.isoformat().replace("+00:00", "Z")
        for claim in safety["original_claims"]
    )
    before = ledger.database.read_bytes()
    with pytest.raises(ValueError, match="closure_not_eligible"):
        workflow.exercise(config, output)
    assert ledger.database.read_bytes() == before


@pytest.mark.parametrize("state", ["partial_active", "revoked", "restored"])
def test_partial_site_evidence_keeps_formal_consumers_and_doctor_consistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    from paper_radar.doctor.admission import admission_rows, render_admission_fragment
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id
    from paper_radar.live_evidence.service import (
        AdmissionRequest,
        load_admission_evidence,
    )
    from paper_radar.live_evidence.types import BindingComponent, Capability
    from paper_radar.pi_execution.errors import ExecutionError
    from tests.live_evidence_ledger_support import NOW
    from tests.read_execution_support import setup
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    screening, request, screening_credentials = product_inputs(
        tmp_path / "screening", monkeypatch
    )
    reading, task, reading_credentials = setup(tmp_path / "reading", monkeypatch)
    # ADR0052及β站点范围的独立人工预期;绝不从collector或登记反推。
    site_capabilities = (
        "auth_cache_current",
        "auth_cache_baseline",
        "cwd_ancestors",
        "file_isolation",
        "zero_core",
        "apport_identity",
        "supply_tree",
        "instance_tree",
        "pi_version",
        "launch_policy",
        "isolation_policy",
        "host_runtime",
    )
    ledger, receipt, components = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        capabilities=site_capabilities,
        uses=("boundary-low", "read-low"),
    )
    lifecycle = EvidenceLifecycle(ledger)
    if state == "revoked":
        for use in ("boundary-low", "read-low"):
            lifecycle.tighten(receipt.receipt_id, use, now=NOW)
    elif state == "restored":
        backup = ledger.root / "before-restore.sqlite3"
        lifecycle.backup(backup)
        lifecycle.restore(backup, now=NOW)
    projections = [
        load_admission_evidence(
            AdmissionRequest(
                use_for_id(use),
                ExecutionBinding(tuple(components.items())),
                frozenset(BindingComponent),
            ),
            now=NOW,
        )
        for use in ("boundary-low", "read-low")
    ]
    for projection in projections:
        assert not projection.decision.executable
        rows = admission_rows(projection)
        cwd = next(item for item in rows if item.capability is Capability.CWD_ANCESTORS)
        assert cwd.original_state is not None and cwd.original_state.value == "verified"
        assert cwd.verified_at == NOW
        assert cwd.qualified is (state == "partial_active")
        rpc = next(
            item for item in rows if item.capability is Capability.RPC_COMPLETION
        )
        assert rpc.original_state is None and not rpc.qualified
        fragment = render_admission_fragment(projection)
        assert "executable=false" in fragment
        assert "精确请求数=unknown" in fragment
    assert projections[0].decision.capabilities == projections[1].decision.capabilities
    assert projections[0].decision.reasons == projections[1].decision.reasons
    screening._now = reading._now = lambda: NOW
    with pytest.raises(ExecutionError, match="evidence_missing"):
        screening.run_attempt(request.receipt_id)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        reading.run_attempt(task.task_id)
    assert screening.tasks.status(request.receipt_id).used_attempts == 0
    assert reading.tasks.task(task.task_id).remaining_attempts == 2
    assert not (screening_credentials / "auth-observed.json").exists()
    assert not (reading_credentials / "auth-observed.json").exists()


def test_reviewed_bundle_freezes_new_code_before_using_existing_runtime(
    tmp_path: Path,
) -> None:
    import subprocess

    from tests.live_admission_closure_support import bundle_model

    runtime, runner, events, _ = bundle_model(tmp_path)
    before = (runtime / "manifest.sha256").read_bytes()
    result = subprocess.run(["/bin/sh", str(runner)], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert events.read_bytes() == b"executed"
    assert (runtime / "manifest.sha256").read_bytes() == before
    frozen = list(
        (tmp_path / "host/var/lib/paperradar").glob(
            "live-evidence-closure-*/workflow.py"
        )
    )
    assert len(frozen) == 1
    assert frozen[0].read_bytes() == runner.with_name("workflow.py").read_bytes()
    repeated = subprocess.run(
        ["/bin/sh", str(runner)], capture_output=True, check=False
    )
    assert repeated.returncode == 2
    assert b"closure_already_staged" in repeated.stderr


@pytest.mark.parametrize(
    "change,reason",
    [
        ("extra", "old_runtime_members"),
        ("source", "old_runtime_integrity"),
        ("mode", "protected_mode"),
        ("symlink", "old_runtime_node"),
        ("entry", "entry_conflict"),
        ("policy", "policy_conflict"),
        ("package_before_sudo", "sha"),
    ],
)
def test_owner_bundle_rejects_tampering_before_ledger_or_runtime_execution(
    tmp_path: Path, change: str, reason: str
) -> None:
    import subprocess

    from tests.live_admission_closure_support import bundle_model

    runtime, runner, events, _ = bundle_model(tmp_path)
    if change == "extra":
        (runtime / "unexpected").write_bytes(b"unknown")
    elif change == "source":
        (runtime / "python/bin/python3").write_bytes(b"tampered")
    elif change == "mode":
        (runtime / "python/bin/python3").chmod(0o777)
    elif change == "symlink":
        (runtime / "unexpected").symlink_to(tmp_path)
    elif change == "entry":
        (runtime.parent / "live-evidence-owner").write_bytes(b"changed")
    elif change == "policy":
        policy = tmp_path / "host/etc/sudoers.d/paperradar-live-evidence"
        policy.chmod(0o644)
        policy.write_bytes(b"changed")
        policy.chmod(0o440)
    elif change == "package_before_sudo":
        runner.with_name("workflow.py").write_bytes(b"changed")
    result = subprocess.run(["/bin/sh", str(runner)], capture_output=True, check=False)
    assert result.returncode != 0
    assert not events.exists()
    assert reason.encode() in result.stderr
    assert list((tmp_path / "host/var/lib/paperradar/live-evidence").iterdir()) == []


def test_readonly_sampling_reads_only_selected_execution_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config import load_config_snapshot
    from paper_radar.doctor.pi_exec import _binding
    from paper_radar.pi_supply import activation_history
    from scripts.issue176_admission_snapshot import metadata_bindings
    from tests.read_execution_support import setup

    product, _, _ = setup(tmp_path, monkeypatch)
    selected = activation_history(product.database)[-1]
    snapshot_id, bindings = metadata_bindings(product.database)
    assert snapshot_id == selected.snapshot_id
    snapshot = load_config_snapshot(product.database, snapshot_id)
    assert bindings["screening"] == _binding(
        snapshot, selected.supply_id, selected.install_id
    )
    assert bindings["reading"].model == bindings["screening"].model
    assert bindings["reading"].thinking_level == "low"


@pytest.mark.parametrize("expired", [False, True])
def test_formal_readonly_sample_preserves_partial_active_and_rejects_stale_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, expired: bool
) -> None:
    from datetime import timedelta

    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.types import BindingComponent
    from scripts import issue176_admission_snapshot as sampling
    from tests.live_evidence_ledger_support import NOW
    from tests.read_execution_support import setup
    from tests.screening_live_admission_support import protected_admission
    from tests.test_doctor_process import inventory, logical

    product, _, credentials = setup(tmp_path / "product", monkeypatch)
    ledger, receipt, components = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        capabilities=("cwd_ancestors",),
        uses=("boundary-low", "value-low", "read-low"),
        activate=False,
    )
    lifecycle = EvidenceLifecycle(ledger)
    review = lifecycle.review(
        receipt.receipt_id,
        "boundary-low",
        binding=ExecutionBinding(tuple(components.items())),
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    lifecycle.activate(review, confirmation=receipt.receipt_id, now=NOW)
    monkeypatch.setattr(
        sampling,
        "datetime",
        type(
            "Clock",
            (),
            {
                "now": staticmethod(
                    lambda tz: NOW + timedelta(seconds=61 if expired else 0)
                )
            },
        ),
    )

    def forbidden(*args: object, **kwargs: object) -> bool:
        raise AssertionError("只读采样触及特权helper/子进程")

    monkeypatch.setattr("paper_radar.live_evidence.service._run_helper", forbidden)
    before, before_db = inventory(tmp_path), logical(product.database)
    result = sampling.sample(product.database, credentials)
    assert result["read_only"] is True
    assert [row["use_id"] for row in result["reports"]] == [
        "boundary-low",
        "value-low",
        "read-low",
    ]
    assert all(not row["executable"] for row in result["reports"])
    if expired:
        assert all(row["reason"] == ["ledger_untrusted"] for row in result["reports"])
        assert all(not row["active"] for row in result["reports"])
    else:
        assert [row["active"] for row in result["reports"]] == [
            ["cwd_ancestors"],
            [],
            [],
        ]
        assert all(
            "精确请求数=unknown" in row["doctor_fragment"] for row in result["reports"]
        )
    assert inventory(tmp_path) == before
    assert logical(product.database) == before_db


@pytest.mark.parametrize("sidecar", [None, "-wal", "-shm", "-journal"])
def test_owner_budget_check_selects_only_ids_generations_and_attempt_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sidecar: str | None
) -> None:
    import sqlite3

    from scripts import issue176_closure_workflow as workflow
    from tests.site_collector_support import site_configuration

    site = site_configuration(tmp_path)
    site.database.parent.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "site.json").write_text(site.model_dump_json())
    monkeypatch.setattr(workflow, "RUNTIME", runtime)
    tables = {
        "screening_budgets": "budget_id TEXT,fingerprint TEXT",
        "screening_tasks": "task_id TEXT,budget_id TEXT,generation INTEGER",
        "screening_attempts": "task_id TEXT,attempt_no INTEGER",
        "screening_requests": (
            "receipt_id TEXT,task_id TEXT,source TEXT,scheduled_day TEXT"
        ),
        "read_budgets": "budget_id TEXT,fingerprint TEXT",
        "read_tasks": "task_id TEXT,budget_id TEXT,generation INTEGER",
        "read_attempts": "attempt_id TEXT,task_id TEXT,ordinal INTEGER",
    }
    with sqlite3.connect(site.database) as connection:
        for table, columns in tables.items():
            connection.execute(f"CREATE TABLE {table} ({columns},payload TEXT)")
    before = site.database.read_bytes()
    if sidecar is not None:
        marker = Path(str(site.database) + sidecar)
        marker.write_bytes(b"do-not-read-or-delete")
        with pytest.raises(ValueError, match="closure_business_sidecars_present"):
            workflow.budget_inventory()
        assert marker.read_bytes() == b"do-not-read-or-delete"
        assert site.database.read_bytes() == before
        return
    original_connect = sqlite3.connect
    observed_columns: list[str] = []

    def readonly_connection(database: str, *, uri: bool = False) -> sqlite3.Connection:
        connection = original_connect(database, uri=uri)

        def authorize(
            action: int,
            table: str | None,
            column: str | None,
            database: str | None,
            trigger: str | None,
        ) -> int:
            if action == sqlite3.SQLITE_READ and column is not None:
                observed_columns.append(column)
                if column == "payload":
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        return connection

    monkeypatch.setattr(sqlite3, "connect", readonly_connection)
    result = workflow.budget_inventory()
    assert "payload" not in observed_columns and "generation" in observed_columns
    assert set(result) == set(tables)
    assert all(item["count"] == 0 for item in result.values())
    assert site.database.read_bytes() == before
    assert not Path(str(site.database) + "-wal").exists()


def test_root_freezing_never_reads_user_paths_after_password_boundary(
    tmp_path: Path,
) -> None:
    import subprocess

    from tests.live_admission_closure_support import bundle_model

    _, runner, events, sudo = bundle_model(tmp_path)
    original = runner.with_name("workflow.py").read_bytes()
    secret = tmp_path / "root-only-model"
    secret.write_bytes(b"must-not-be-copied")
    source = sudo.read_text().replace(
        'exec "$@"',
        f'/usr/bin/rm "{runner.with_name("workflow.py")}"\n'
        f'/usr/bin/ln -s "{secret}" "{runner.with_name("workflow.py")}"\nexec "$@"',
    )
    sudo.write_text(source)
    result = subprocess.run(["/bin/sh", str(runner)], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert events.is_file()
    frozen = list(
        (tmp_path / "host/var/lib/paperradar").glob(
            "live-evidence-closure-*/workflow.py"
        )
    )
    assert len(frozen) == 1
    assert frozen[0].read_bytes() == original
    assert secret.read_bytes() == b"must-not-be-copied"
