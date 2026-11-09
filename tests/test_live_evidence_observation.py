"""固定受保护现场观察的新鲜度与完整性边界。"""

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.observation import (
    CurrentObservation,
    load_current_observation,
)
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.types import BindingComponent
from tests.live_evidence_ledger_support import NOW, receipt
from tests.live_evidence_lifecycle_support import installed


@pytest.mark.parametrize(
    "seconds,reason",
    [(-60, None), (-61, "observation_stale"), (1, "evidence_time_future")],
)
def test_observation_freshness_is_separate_from_capability_expiry(
    seconds: int, reason: str | None
) -> None:
    observation = CurrentObservation(
        observed_at=NOW + timedelta(seconds=seconds),
        binding=receipt().binding,
        checked_components=tuple(BindingComponent),
    )
    if reason:
        with pytest.raises(LedgerError, match=reason):
            observation.validate_time(now=NOW)
    else:
        observation.validate_time(now=NOW)


@pytest.mark.parametrize(
    "damage,reason",
    [
        ("naive", "evidence_time_invalid"),
        ("incomplete", "binding_incomplete"),
        ("duplicate", "observation_component_duplicate"),
    ],
)
def test_observation_rejects_naive_time_or_incomplete_component_claims(
    damage: str, reason: str
) -> None:
    data = {
        "observed_at": NOW,
        "binding": receipt().binding,
        "checked_components": tuple(BindingComponent),
    }
    if damage == "naive":
        data["observed_at"] = NOW.replace(tzinfo=None)
    elif damage == "incomplete":
        data["binding"] = {BindingComponent.HOST: "b" * 64}
    else:
        data["checked_components"] = (BindingComponent.HOST, BindingComponent.HOST)
    with pytest.raises(ValidationError, match=reason):
        CurrentObservation.model_validate(data)


def test_current_observation_load_is_read_only_and_uses_fixed_protected_source(
    tmp_path: Path,
) -> None:
    ledger, original, _ = installed(tmp_path)
    observation = CurrentObservation(
        observed_at=NOW,
        binding=original.binding,
        checked_components=(BindingComponent.CWD_ANCESTORS,),
    )
    target = ledger.root / "inbox" / "current-observation.json"
    target.write_bytes(canonical_bytes(observation))
    target.chmod(0o644)
    before = {
        path: path.read_bytes() for path in ledger.root.rglob("*") if path.is_file()
    }
    loaded = load_current_observation(ledger, now=NOW)
    assert loaded.checked_components == (BindingComponent.CWD_ANCESTORS,)
    assert before == {
        path: path.read_bytes() for path in ledger.root.rglob("*") if path.is_file()
    }
