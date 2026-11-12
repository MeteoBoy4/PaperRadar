"""D1: 候选纯站点/负对照零调用事实也拒绝作废,历史回执保留。"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.live_evidence.collection import ProtectedCollection
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.live_install import json_bytes
from paper_radar.live_evidence.model_manifest import parse_manifest
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    canonical_bytes,
    content_sha256,
)
from tests.live_evidence_ledger_support import plan, receipt
from tests.preparation_void_support import assert_void_preserved, void_case
from tests.test_live_epoch_upgrade import BINDING


@pytest.mark.parametrize(
    "fact", ["strict-approved", "negative-approved", "negative-cancelled", "inbox-site"]
)
def test_zero_call_candidate_facts_are_not_treated_as_an_unexecuted_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fact: str
) -> None:
    model = void_case(tmp_path, monkeypatch)
    ledger = EvidenceLedger(
        model.gate.paths.ledger,
        trust=LedgerTrust(owner_uid=os.getuid(), anchor=model.gate.paths.anchor),
    )
    collection = ProtectedCollection(ledger)
    source = model.original.source.staged
    manifest = parse_manifest((source / "model-manifest.json").read_bytes())
    now = datetime.now(UTC)
    if fact == "strict-approved":
        ledger.approve_plan(
            ApprovedPlan.model_validate_json((source / "plan.json").read_bytes()),
            now=now,
        )
    elif fact == "inbox-site":
        (ledger.root / "inbox" / f"site-{manifest.site_plan_id}.json").write_bytes(
            json_bytes({"plan_id": manifest.site_plan_id})
        )
    else:
        collection.approve_plan(manifest.negative_plan, now=now)
        if fact == "negative-cancelled":
            run = collection.start_round(
                manifest.negative_plan.plan_id, binding=BINDING, now=now
            )
            collection.cancel_round(run.round_id, now=now)
    assert collection.zero_operation_baseline() is True
    before = ledger.database.read_bytes()
    reason = (
        "source_untrusted"
        if fact == "negative-cancelled"
        else "preparation_void_candidate_evidence"
    )
    with pytest.raises(ValueError, match="^" + reason + "$"):
        model.gate.prepare(lambda: pytest.fail("no native"), lambda: None)
    assert ledger.database.read_bytes() == before
    assert model.original.original.io.writes == []


def test_four_non_candidate_historical_receipts_survive_void_and_failure_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = void_case(tmp_path, monkeypatch)
    ledger = EvidenceLedger(
        model.gate.paths.ledger,
        trust=LedgerTrust(owner_uid=os.getuid(), anchor=model.gate.paths.anchor),
    )
    now = datetime.now(UTC)
    for index in range(4):
        approved = plan().model_copy(update={"plan_id": f"historical-{index}"})
        ledger.approve_plan(approved, now=now)
        record = receipt().model_copy(
            update={
                "plan_id": approved.plan_id,
                "plan_sha256": content_sha256(approved),
            }
        )
        source = ledger.root / "inbox" / f"historical-{index}.json"
        source.write_bytes(canonical_bytes(record))
        source.chmod(0o644)
        ledger.receive(source, now=now)
    before = ledger.database.read_bytes()

    def refused() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.gate.prepare(refused, lambda: None)
    assert ledger.database.read_bytes() == before
    # 原数据快照在新增历史前取得;其余原来源仍逐字保持。
    model.preserved.pop(ledger.database)
    assert_void_preserved(model)
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "clean"
