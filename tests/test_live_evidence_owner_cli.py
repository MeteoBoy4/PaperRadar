from datetime import timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.receipt import canonical_bytes
from tests.live_evidence_ledger_support import (
    NOW,
    owner_uid,
    plan,
    protected_root,
    receipt,
)


def test_owner_cli_reviews_before_confirmation_and_refuses_expired_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import cli

    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    ledger.approve_plan(plan(), now=NOW)
    source = root / "inbox" / "site.json"
    source.write_bytes(canonical_bytes(receipt()))
    source.chmod(0o644)
    ledger.receive(source, now=NOW)
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.types import BindingComponent

    observation = CurrentObservation(
        observed_at=NOW - timedelta(seconds=61),
        binding=receipt().binding,
        checked_components=tuple(BindingComponent),
    )
    (root / "inbox" / "current-observation.json").write_bytes(
        canonical_bytes(observation)
    )
    (root / "inbox" / "current-observation.json").chmod(0o644)
    monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
    monkeypatch.setattr(cli, "_refresh_current_observation", lambda: None)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    result = CliRunner().invoke(
        app,
        [
            "live-evidence",
            "activate",
            "--receipt-id",
            receipt().receipt_id,
            "--use-id",
            "boundary-low",
        ],
        input=receipt().receipt_id + "\n",
    )
    assert result.exit_code == 2
    assert "observation_stale" in result.output
    assert not any(item.action == "evidence_activated" for item in ledger.audit())


@pytest.mark.parametrize("confirmation,expected", [("correct", 0), ("wrong", 2)])
def test_owner_reviews_complete_receipt_and_confirms_exact_short_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    confirmation: str,
    expected: int,
) -> None:
    from paper_radar.live_evidence import cli
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.types import BindingComponent
    from tests.live_evidence_lifecycle_support import installed

    ledger, original, _ = installed(tmp_path)
    observation = CurrentObservation(
        observed_at=NOW,
        binding=original.binding,
        checked_components=tuple(BindingComponent),
    )
    target = ledger.root / "inbox" / "current-observation.json"
    target.write_bytes(canonical_bytes(observation))
    target.chmod(0o644)
    monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
    monkeypatch.setattr(cli, "_refresh_current_observation", lambda: None)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    result = CliRunner().invoke(
        app,
        [
            "live-evidence",
            "activate",
            "--receipt-id",
            original.receipt_id,
            "--use-id",
            "boundary-low",
        ],
        input=(original.receipt_id if confirmation == "correct" else "wrong") + "\n",
    )
    assert result.exit_code == expected, result.output
    assert result.output.index('"binding"') < result.output.index("输入回执短 ID")
    assert "verified_at=" in result.output and "expires_at=" in result.output
    if expected:
        assert "evidence_activation_confirmation_mismatch" in result.output
    else:
        assert "capabilities=cwd_ancestors" in result.output


def test_confirmation_wait_cannot_outlive_current_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import cli
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.types import BindingComponent
    from tests.live_evidence_lifecycle_support import installed

    ledger, original, _ = installed(tmp_path)
    target = ledger.root / "inbox" / "current-observation.json"
    target.write_bytes(
        canonical_bytes(
            CurrentObservation(
                observed_at=NOW,
                binding=original.binding,
                checked_components=tuple(BindingComponent),
            )
        )
    )
    target.chmod(0o644)
    times = iter([NOW, NOW, NOW + timedelta(seconds=61), NOW + timedelta(seconds=61)])
    monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
    monkeypatch.setattr(cli, "_refresh_current_observation", lambda: None)
    monkeypatch.setattr(cli, "_now", lambda: next(times))
    result = CliRunner().invoke(
        app,
        [
            "live-evidence",
            "activate",
            "--receipt-id",
            original.receipt_id,
            "--use-id",
            "boundary-low",
        ],
        input=original.receipt_id + "\n",
    )
    assert result.exit_code == 2
    assert "observation_stale" in result.output
    assert not any(event.action == "evidence_activated" for event in ledger.audit())


def test_show_displays_actual_activation_without_changing_historical_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import cli
    from paper_radar.live_evidence import ledger as ledger_module
    from tests.live_evidence_lifecycle_support import activated

    ledger, original, _ = activated(tmp_path)
    monkeypatch.setattr(ledger_module, "EvidenceLedger", lambda: ledger)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    result = CliRunner().invoke(
        app, ["live-evidence", "show", "--receipt-id", original.receipt_id]
    )
    assert result.exit_code == 0, result.output
    assert "evidence_active=true" in result.output
    assert "evidence=verified" in result.output


@pytest.mark.parametrize("command", ["activate", "revoke"])
def test_new_owner_command_help_has_no_external_io(
    tmp_path: Path, command: str
) -> None:
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "live-evidence",
            command,
            "--help",
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "当前用途" in result.stdout and "副作用" in result.stdout
    assert list(tmp_path.iterdir()) == []
