"""D1: 安装入口完整报告先于任何 kernel、归档和业务写入。"""

import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from paper_radar.live_evidence.live_install import LiveDeployment
from tests.preparation_void_support import assert_void_preserved, void_case


@pytest.mark.parametrize(
    "status,name,reason",
    [
        ("fail", "manager_linger", "systemd_boot_marker_missing"),
        ("blocked", "native_scope_trace", "dependency_failed"),
        ("pending", "nft", "unknown_dependency"),
        ("pending", "native_scope_trace", "unknown_dependency"),
    ],
)
def test_install_aggregates_failure_blocked_and_unsupported_pending_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    name: str,
    reason: str,
) -> None:
    model = void_case(tmp_path, monkeypatch)
    host = model.original.original.host
    report = (
        SimpleNamespace(name=name, status=status, reason=reason),
        SimpleNamespace(name="sudoers", status="fail", reason="syntax_refused"),
    )
    monkeypatch.setattr(
        host, "prerequisite_report", lambda *args, **kwargs: report, raising=False
    )
    deployment = LiveDeployment(
        model.gate.staged, paths=model.gate.paths, host=host, owner_uid=os.getuid()
    )
    with pytest.raises(ValueError, match=r"^installation_prerequisites_failed$"):
        deployment.install()
    output = capsys.readouterr().out
    assert f"{name}={status}" in output and "sudoers=fail" in output
    assert model.original.original.io.writes == []
    assert not model.gate.journal.exists()
    assert not any(path.exists() for path in model.gate.archives())
    assert_void_preserved(model)


def test_successful_void_install_reenters_normally_and_business_failure_is_not_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import live_install
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.model_manifest import parse_manifest
    from paper_radar.live_evidence.normal_auth_refresh import read_epoch

    model = void_case(tmp_path, monkeypatch)
    host = model.original.original.host
    original_check, original_prepare = host.preflight_placement, host.prepare_placement
    monkeypatch.setattr(
        host,
        "prerequisite_report",
        lambda *args, **kwargs: (
            SimpleNamespace(
                name="native_scope_trace",
                status="pending",
                reason="placement_transaction_required",
            ),
        ),
        raising=False,
    )

    def check(root: Path, *, recover: bool = False) -> None:
        if not model.gate.check(recover=recover):
            original_check(root, recover=recover)

    def prepare(root: Path, site: object, *, recover: bool = False) -> None:
        if not model.gate.prepare(lambda: None, lambda: None, recover=recover):
            original_prepare(root, site, recover=recover)

    monkeypatch.setattr(host, "preflight_placement", check)
    monkeypatch.setattr(host, "prepare_placement", prepare)
    host.policy_os = model.original.original.io
    deployment = LiveDeployment(
        model.gate.staged, paths=model.gate.paths, host=host, owner_uid=os.getuid()
    )
    old_main = model.gate.paths.journal.read_bytes()
    original_publish = live_install.publish

    def fail_history(
        path: Path, raw: bytes, *, replace: bool = False, mode: int = 0o644
    ) -> None:
        if path.name.startswith("deployment-v2-history-"):
            raise ValueError("synthetic_business_publication_failure")
        original_publish(path, raw, replace=replace, mode=mode)

    with monkeypatch.context() as failure:
        failure.setattr(live_install, "publish", fail_history)
        with pytest.raises(
            ValueError, match=r"^synthetic_business_publication_failure$"
        ):
            deployment.install()
    assert model.gate.paths.journal.read_bytes() == old_main
    assert model.original.original.io.profiles
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert deployment.install(recover=True) == "installed"
    writes = list(model.original.original.io.writes)
    assert deployment.install() == "already_installed"
    assert model.original.original.io.writes == writes
    assert all(path.read_bytes() == raw for path, raw in model.gate.archives().items())
    manifest = parse_manifest(
        (model.gate.paths.runtime / "model-manifest.json").read_bytes()
    )
    ledger = EvidenceLedger(
        model.gate.paths.ledger,
        trust=LedgerTrust(owner_uid=os.getuid(), anchor=model.gate.paths.anchor),
    )
    assert read_epoch(ledger, manifest).deployed_at == datetime.fromisoformat(
        json.loads((model.gate.staged / "deployment.json").read_bytes())[
            "epoch_upgrade"
        ]["deployed_at"]
    )
