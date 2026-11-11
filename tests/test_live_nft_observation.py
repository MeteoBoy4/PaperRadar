"""D1: gen/双视图未知保持临时拒绝,已确认 level/selector/结构丢失持久收紧。"""

import json
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any, BinaryIO

import pytest

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
from paper_radar.live_evidence.nft_rules import merge_nft_views
from paper_radar.live_evidence.observation import (
    CurrentObservation,
    load_current_observation,
)
from paper_radar.live_evidence.protected_observer import egress_identity, refresh_once
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.live_evidence.types import Capability as C
from paper_radar.pi_execution.placement import PlacementTarget
from tests.live_evidence_ledger_support import NOW
from tests.test_observation_refresh import refresh_site


@pytest.mark.parametrize(
    "damage",
    [
        "level",
        "selector_deleted",
        "extra_expression",
        "generation_unavailable",
        "views_mismatch",
        "table_lost",
        "selector_comment",
        "extra_chain",
    ],
)
def test_actual_nft_drift_and_unavailable_have_distinct_durable_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    ledger, runtime, _, previous = refresh_site(tmp_path, monkeypatch)
    fixture = Path(__file__).parent / "fixtures/live-nft-1.1.6-source-derived.json"
    snapshot = json.loads(fixture.read_bytes())
    native = fixture.with_suffix(".nft").read_text()
    target_path = ledger.root / "inbox/placement-target-v1.json"
    target = PlacementTarget.model_validate_json(target_path.read_bytes())
    identity = egress_identity(merge_nft_views(snapshot, native), target)
    target_path.write_bytes(
        canonical_bytes(target.model_copy(update={"egress_digest": identity}))
    )
    source = ledger.root / "inbox/current-observation.json"
    source.write_bytes(
        canonical_bytes(
            previous.model_copy(
                update={"binding": previous.binding | {B.IPV4_EGRESS: identity}}
            )
        )
    )
    lost = False

    def run(
        argv: tuple[str, ...], *, stdout: BinaryIO, **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        if lost:
            if argv == ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar"):
                return subprocess.CompletedProcess(argv, 2)
            assert argv == ("/usr/sbin/nft", "-j", "list", "tables")
            stdout.write(b'{"nftables":[]}')
        elif argv == (
            "/usr/sbin/nft",
            "-a",
            "-n",
            "list",
            "table",
            "inet",
            "paperradar",
        ):
            stdout.write(native.encode())
        else:
            assert argv == (
                "/usr/sbin/nft",
                "-j",
                "list",
                "table",
                "inet",
                "paperradar",
            )
            stdout.write(json.dumps(snapshot).encode())
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert refresh_once(runtime, ledger, now=NOW) == "available"
    before = source.read_bytes()
    if damage == "level":
        native = native.replace("level 4", "level 3")
    elif damage == "selector_deleted":
        snapshot["nftables"].pop(3)
        native = (
            "\n".join(
                line for line in native.splitlines() if "socket cgroupv2" not in line
            )
            + "\n"
        )
    elif damage == "selector_comment":
        del snapshot["nftables"][3]["rule"]["comment"]
        native = native.replace(' comment "paperradar-placement-v1"', "")
    elif damage == "extra_chain":
        snapshot["nftables"].append(
            {
                "chain": {
                    "family": "inet",
                    "table": "paperradar",
                    "name": "other",
                    "handle": 13,
                }
            }
        )
        native = native.rstrip()[:-1] + "chain other { # handle 13\n}\n}\n"
    elif damage == "extra_expression":
        snapshot["nftables"][4]["rule"]["expr"].insert(
            2, {"match": {"op": "==", "left": {"meta": {"key": "mark"}}, "right": 0}}
        )
        native = native.replace(
            "tcp dport 443 counter", "tcp dport 443 meta mark 0 counter", 1
        )
    elif damage == "views_mismatch":
        native = native.replace("# handle 4", "# handle 99")
    elif damage == "generation_unavailable":

        def unavailable() -> int:
            raise ValueError("nft_generation_unavailable")

        monkeypatch.setattr(
            "paper_radar.live_evidence.nft_rules.nft_generation", unavailable
        )
    else:
        lost = True
    drift = damage not in {"generation_unavailable", "views_mismatch"}
    reason = "observation_drift" if drift else "observation_unavailable"
    assert refresh_once(runtime, ledger, now=NOW + timedelta(seconds=1)) == reason
    if drift:
        actual = CurrentObservation.model_validate_json(source.read_bytes())
        assert actual.observed_at == NOW + timedelta(seconds=1)
        assert actual.binding[B.IPV4_EGRESS] != identity
    else:
        assert source.read_bytes() == before
    reopened = EvidenceLedger(ledger.root, trust=ledger.trust)
    with pytest.raises(LedgerError, match="^" + reason + "$"):
        load_current_observation(reopened, now=NOW + timedelta(seconds=1))
    evidence = {
        item.capability: item
        for item in EvidenceLifecycle(reopened)
        .snapshot(now=NOW + timedelta(seconds=1))
        .evidence
    }
    assert evidence[C.IPV4_EGRESS].revoked is drift
    assert not evidence[C.CWD_ANCESTORS].revoked
    assert not evidence[C.SINGLE_DISPATCH].revoked
