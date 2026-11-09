"""所有者完整审阅后的真实新鲜观察,独立未绑定回归。"""

from datetime import timedelta
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.live_evidence.observation import CurrentObservation
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.types import BindingComponent
from tests.live_evidence_ledger_support import NOW
from tests.live_evidence_lifecycle_support import installed


def test_owner_can_finish_review_after_sixty_seconds_with_fresh_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import cli

    ledger, original, _ = installed(tmp_path)
    target = ledger.root / "inbox" / "current-observation.json"
    clock = [NOW]
    refreshes = []

    def observe() -> None:
        target.write_bytes(
            canonical_bytes(
                CurrentObservation(
                    observed_at=clock[0],
                    binding=original.binding,
                    checked_components=tuple(BindingComponent),
                )
            )
        )
        target.chmod(0o644)

    def confirm(*args: object, **kwargs: object) -> str:
        clock[0] += timedelta(seconds=61)
        return original.receipt_id

    def refresh() -> None:
        refreshes.append(clock[0])
        observe()

    observe()
    monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
    monkeypatch.setattr(cli, "_now", lambda: clock[0])
    monkeypatch.setattr(typer, "prompt", confirm)
    monkeypatch.setattr(cli, "_refresh_current_observation", refresh, raising=False)
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
    )
    assert result.exit_code == 0, result.output
    assert refreshes == [NOW + timedelta(seconds=61)]
    assert '"binding"' in result.output
    assert "capabilities=cwd_ancestors" in result.output
    assert "verified_at=2026-11-09 12:00:00+00:00 expires_at=None" in result.output
    assert ledger.show(original.receipt_id).receipt == original


@pytest.mark.parametrize(
    "change,reason",
    [
        ("binding", "observation_changed"),
        ("coverage", "observation_changed"),
        ("old_observation", "observation_stale"),
        ("not_refreshed", "observation_changed"),
        ("future_observation", "evidence_time_future"),
        ("revoked", "observation_changed"),
        ("restore", "observation_changed"),
        ("source_missing", "source_untrusted"),
        ("clock_rollback", "clock_rollback"),
        ("expired", "evidence_activation_empty"),
        ("collector_failed", "binding_observation_unavailable"),
        ("wrong_confirmation", "evidence_activation_confirmation_mismatch"),
    ],
)
def test_owner_refuses_changed_or_unavailable_review_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str, reason: str
) -> None:
    from paper_radar.live_evidence import cli
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.types import Capability

    capabilities: tuple[Capability, ...] = (
        Capability.CWD_ANCESTORS,
        Capability.HOST_RUNTIME,
    )
    provider = False
    verified_at = NOW
    if change == "expired":
        capabilities = (Capability.MODEL_IDENTITY,)
        provider = True
        verified_at = NOW - timedelta(days=30) + timedelta(seconds=30)
    ledger, original, _ = installed(
        tmp_path, capabilities=capabilities, provider=provider, verified_at=verified_at
    )
    target = ledger.root / "inbox" / "current-observation.json"
    clock = [NOW]
    observation = CurrentObservation(
        observed_at=NOW,
        binding=original.binding,
        checked_components=tuple(BindingComponent),
    )
    target.write_bytes(canonical_bytes(observation))
    target.chmod(0o644)
    refreshes = []

    def confirm(*args: object, **kwargs: object) -> str:
        clock[0] += timedelta(seconds=61 if change != "not_refreshed" else 1)
        if change == "clock_rollback":
            EvidenceLifecycle(ledger).tick(now=clock[0] + timedelta(seconds=1))
        if change == "revoked":
            EvidenceLifecycle(ledger).tighten(
                original.receipt_id,
                "boundary-low",
                now=clock[0],
                failed_capabilities=frozenset({Capability.HOST_RUNTIME}),
                components=frozenset(),
            )
        if change == "restore":
            EvidenceLifecycle(ledger).record_restore(now=clock[0])
        if change == "source_missing":
            (ledger.root / "inbox/site.json").unlink()
        return "wrong" if change == "wrong_confirmation" else original.receipt_id

    def refresh() -> None:
        refreshes.append(clock[0])
        if change == "collector_failed":
            raise LedgerError("binding_observation_unavailable")
        if change in {"old_observation", "not_refreshed"}:
            return
        data = observation.model_dump()
        data["observed_at"] = clock[0] + (
            timedelta(seconds=1) if change == "future_observation" else timedelta()
        )
        if change == "binding":
            data["binding"] = original.binding | {BindingComponent.HOST: "c" * 64}
        if change == "coverage":
            data["checked_components"] = tuple(
                c for c in BindingComponent if c != BindingComponent.HOST
            )
        target.write_bytes(canonical_bytes(CurrentObservation.model_validate(data)))

    monkeypatch.setattr(cli, "_owner_ledger", lambda: ledger)
    monkeypatch.setattr(cli, "_now", lambda: clock[0])
    monkeypatch.setattr(typer, "prompt", confirm)
    monkeypatch.setattr(cli, "_refresh_current_observation", refresh)
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
    )
    assert result.exit_code == 2, result.output
    assert f"[{reason}]" in result.output
    assert not any(event.action == "evidence_activated" for event in ledger.audit())
    assert len(refreshes) == (0 if change == "wrong_confirmation" else 1)


@pytest.mark.parametrize("outcome", ["ok", "denied", "timeout", "missing"])
def test_confirmation_refresh_uses_only_the_fixed_frozen_collector(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    import subprocess

    from paper_radar.live_evidence.cli import _refresh_current_observation
    from paper_radar.live_evidence.ledger import LedgerError

    calls = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append((args, kwargs))
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args, 120)
        if outcome == "missing":
            raise OSError("synthetic-only")
        return subprocess.CompletedProcess(args, 0 if outcome == "ok" else 2)

    monkeypatch.setattr(subprocess, "run", run)
    if outcome == "ok":
        _refresh_current_observation()
    else:
        with pytest.raises(LedgerError, match="binding_observation_unavailable"):
            _refresh_current_observation()
    assert calls == [
        (
            ["/usr/libexec/paperradar/live-evidence-collect"],
            {
                "env": {},
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "timeout": 120,
                "check": False,
            },
        )
    ]
