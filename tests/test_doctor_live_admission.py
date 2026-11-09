"""#175 独立公共 CLI;真实临时账本与当前绑定,不授予产品工程能力。"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from paper_radar.live_evidence.ledger import EvidenceLedger
from paper_radar.live_evidence.receipt import EvidenceReceipt
from paper_radar.live_evidence.types import BindingComponent
from paper_radar.pi_execution.admission import bind_description
from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
from paper_radar.pi_execution.resources import (
    LAUNCH_POLICY_VERSION,
    expected_cwd_section,
)
from paper_radar.pi_execution.service import prepare_call
from paper_radar.pi_execution.site_binding import site_binding_components
from paper_radar.pi_supply import activation_history
from tests.live_evidence_ledger_support import NOW
from tests.screening_live_admission_support import (
    REQUIRED,
    product_inputs,
    protected_admission,
)
from tests.test_doctor_process import inventory, logical


def selected_site(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    capabilities: tuple[str, ...] = REQUIRED,
    activate: bool = True,
) -> tuple[Path, str, Path, EvidenceLedger, EvidenceReceipt]:
    from paper_radar.doctor import pi_exec
    from paper_radar.pi_execution import current_binding

    service, request, credentials = product_inputs(root / "product", monkeypatch)
    selected = activation_history(service.database)[-1]
    binding = bind_description(
        prepare_call(service.tasks, request.receipt_id),
        supply_id=selected.supply_id,
        install_id=selected.install_id,
        launch_policy_version=LAUNCH_POLICY_VERSION,
        isolation_policy_version=ISOLATION_POLICY_VERSION,
        cwd_section=expected_cwd_section(),
        auth_mode="chatgpt_subscription",
    )
    (root / "evidence").mkdir()
    # 固定OS站点观察,避免并行pytest创建共享/tmp祖先导致测试自身漂移。
    # 安装树与认证/cache stat仍由真实local_binding_components读取。
    site = site_binding_components()
    monkeypatch.setattr(current_binding, "site_binding_components", lambda: site.copy())
    original = current_binding.local_binding_components
    components = {component: "b" * 64 for component in BindingComponent}
    components.update(original(service.database, binding, credentials_dir=credentials))
    ledger, receipt, _ = protected_admission(
        root / "evidence/material",
        monkeypatch,
        components=components,
        uses=("boundary-low", "value-low"),
        capabilities=capabilities,
        activate=activate,
    )
    monkeypatch.setattr(current_binding, "local_binding_components", original)
    monkeypatch.setattr(pi_exec, "_utc_now", lambda: NOW, raising=False)
    monkeypatch.setattr(pi_exec, "EXECUTION_CWD", root / "product/cwd")
    return service.database, request.snapshot_id, credentials, ledger, receipt


def diagnose(database: Path, snapshot: str, credentials: Path) -> Result:
    return CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "pi-exec",
            "--database",
            str(database),
            "--snapshot",
            snapshot,
            "--credentials-dir",
            str(credentials),
        ],
    )


def test_healthy_required_checks_exit_zero_and_keep_unknown_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, snapshot, credentials, _, _ = selected_site(tmp_path, monkeypatch)
    before, before_db = inventory(tmp_path), logical(database)
    result = diagnose(database, snapshot, credentials)
    assert result.exit_code == 0, result.output
    assert "scope=pi-exec result=passed executable=true" in result.output
    assert "use=boundary-low" in result.output
    assert "use=value-low" in result.output
    assert (
        "capability=pi_public_300_seconds result=passed evidence=unknown"
        in result.output
    )
    assert "Read 此命令未选择、未诊断" in result.output
    assert "Pi token 用量=unknown" in result.output
    assert "oauth-test-only-sensitive-sentinel" not in result.output
    assert "Frozen effective Pi system prompt" not in result.output
    assert inventory(tmp_path) == before
    assert logical(database) == before_db
    (credentials / "new-cache").write_bytes(b"synthetic-cache-metadata-only")
    drifted_tree = inventory(tmp_path)
    drifted = diagnose(database, snapshot, credentials)
    assert drifted.exit_code == 2, drifted.output
    assert "binding_drift:auth_cache_baseline" in drifted.output
    assert (
        "capability=auth_cache_baseline result=invalid evidence=unknown "
        "original_state=verified" in drifted.output
    )
    assert inventory(tmp_path) == drifted_tree
    assert logical(database) == before_db


@pytest.mark.parametrize(
    "scenario,reason",
    [
        ("missing_required", "evidence_missing"),
        ("not_activated", "evidence_not_activated"),
        ("pending_required", "evidence_revoked"),
        ("clock_rollback", "clock_rollback"),
        ("exact_expiry", "evidence_expired"),
        ("ledger_corrupt", "ledger_untrusted"),
    ],
)
def test_required_gap_or_untrusted_facts_exit_two_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, reason: str
) -> None:
    from paper_radar.doctor import pi_exec
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.live_evidence.types import BindingComponent

    database, snapshot, credentials, ledger, receipt = selected_site(
        tmp_path,
        monkeypatch,
        capabilities=tuple(cap for cap in REQUIRED if cap != "rpc_eof")
        if scenario == "missing_required"
        else REQUIRED,
        activate=scenario != "not_activated",
    )
    if scenario == "pending_required":
        service.request_revocation(
            receipt.receipt_id,
            "boundary-low",
            now=NOW,
            components=frozenset({BindingComponent.CWD_ANCESTORS}),
        )
    if scenario in {"clock_rollback", "exact_expiry"}:
        current = NOW + (
            timedelta(days=30) if scenario == "exact_expiry" else -timedelta(seconds=1)
        )
        monkeypatch.setattr(pi_exec, "_utc_now", lambda: current)
        source = ledger.root / "inbox/current-observation.json"
        observation = CurrentObservation.model_validate_json(source.read_bytes())
        source.write_bytes(
            canonical_bytes(observation.model_copy(update={"observed_at": current}))
        )
    if scenario == "ledger_corrupt":
        ledger.database.write_bytes(b"corrupt-synthetic-ledger")
    before, before_db = inventory(tmp_path), logical(database)
    result = diagnose(database, snapshot, credentials)
    assert result.exit_code == 2, result.output
    assert "scope=pi-exec result=failed executable=false" in result.output
    assert reason in result.output
    if scenario == "ledger_corrupt":
        assert "check=admission result=invalid reason=ledger_untrusted" in result.output
    if scenario == "exact_expiry":
        assert "original_state=verified" in result.output
        assert "expires_at=2026-12-09T12:00:00+00:00 expired=true" in result.output
    if scenario == "pending_required":
        assert "pending_revocation=true" in result.output
        assert "evidence_active=true revoked=true" in result.output
    assert inventory(tmp_path) == before
    assert logical(database) == before_db


def test_pending_disclosure_stays_visible_without_becoming_independent_blocker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.types import Capability

    database, snapshot, credentials, _, receipt = selected_site(
        tmp_path, monkeypatch, capabilities=(*REQUIRED, "pi_public_300_seconds")
    )
    service.request_revocation(
        receipt.receipt_id,
        "boundary-low",
        now=NOW,
        components=frozenset(),
        failed_capabilities=frozenset({Capability.PI_PUBLIC_300_SECONDS}),
    )
    before = inventory(tmp_path)
    result = diagnose(database, snapshot, credentials)
    assert result.exit_code == 0, result.output
    assert "scope=pi-exec result=passed executable=true" in result.output
    assert "pending_revocation=true" in result.output
    row = next(
        line
        for line in result.output.splitlines()
        if line.startswith("capability=pi_public_300_seconds")
    )
    assert "result=passed evidence=unknown original_state=verified" in row
    assert "evidence_revoked" in row
    assert inventory(tmp_path) == before


def test_healthy_diagnosis_never_reads_credentials_or_calls_network_or_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.live_evidence import service

    database, snapshot, credentials, _, _ = selected_site(tmp_path, monkeypatch)
    before = inventory(tmp_path)
    original_open = Path.open
    original_os_open = os.open

    def reject_external(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("doctor_external_io_forbidden")

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        assert path != credentials / "auth.json", "credential_content_forbidden"
        return original_open(path, *args, **kwargs)

    def guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        assert Path(path).name != "auth.json", "credential_content_forbidden"
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC), (
            "doctor_write_forbidden"
        )
        return original_os_open(path, flags, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr("subprocess.Popen", reject_external)
        guard.setattr("socket.socket", reject_external)
        guard.setattr(service, "_run_helper", reject_external)
        guard.setattr(Path, "open", guarded_open)
        guard.setattr(os, "open", guarded_os_open)
        result = diagnose(database, snapshot, credentials)
    assert result.exit_code == 0, result.output
    assert inventory(tmp_path) == before
