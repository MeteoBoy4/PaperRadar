from __future__ import annotations

import os
from pathlib import Path

import pytest

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError, LedgerTrust
from paper_radar.live_evidence.receipt import canonical_bytes
from tests.live_evidence_ledger_support import (
    NOW,
    owner_uid,
    plan,
    protected_root,
    receipt,
)


def test_protected_receive_is_idempotent_auditable_and_query_is_read_only(
    tmp_path: Path,
) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    ledger.approve_plan(plan(), now=NOW)
    source = root / "inbox" / "site.json"
    source.write_bytes(canonical_bytes(receipt()))
    source.chmod(0o644)
    result = ledger.receive(source, now=NOW)
    assert result.receipt_id == receipt().receipt_id
    assert result.duplicate is False
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    shown = ledger.show(result.receipt_id)
    assert shown.receipt == receipt()
    assert shown.evidence_active is False
    assert before == {
        path: path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    assert ledger.receive(source, now=NOW).duplicate is True
    assert [event.action for event in ledger.audit()] == [
        "plan_approved",
        "received",
        "receive_duplicate",
    ]
    assert os.stat(root / "ledger.sqlite3").st_mode & 0o022 == 0


@pytest.mark.parametrize(
    "damage",
    [
        "writable",
        "symlink",
        "journal",
        "corrupt",
        "missing",
        "owner",
        "writable_parent",
        "source_missing",
    ],
)
def test_query_fails_closed_on_untrusted_storage(tmp_path: Path, damage: str) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    ledger.approve_plan(plan(), now=NOW)
    source = root / "inbox" / "site.json"
    source.write_bytes(canonical_bytes(receipt()))
    source.chmod(0o644)
    identifier = ledger.receive(source, now=NOW).receipt_id
    database = root / "ledger.sqlite3"
    if damage == "writable":
        database.chmod(0o666)
    elif damage == "symlink":
        database.rename(root / "moved")
        database.symlink_to(root / "moved")
    elif damage == "journal":
        Path(str(database) + "-journal").write_bytes(b"hot")
    elif damage == "corrupt":
        database.write_bytes(b"not sqlite")
    elif damage == "missing":
        database.unlink()
    elif damage == "owner":
        ledger = EvidenceLedger(
            root, trust=LedgerTrust(owner_uid() + 10, owner_uid(), root)
        )
    elif damage == "writable_parent":
        root.chmod(0o777)
    else:
        source.unlink()
    with pytest.raises(LedgerError) as error:
        ledger.show(identifier)
    assert error.value.reason == "ledger_untrusted"


def test_unprotected_json_is_rejected_and_rejection_audited(tmp_path: Path) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    ordinary = tmp_path / "ordinary.json"
    ordinary.write_bytes(canonical_bytes(receipt()))
    with pytest.raises(LedgerError) as error:
        ledger.receive(ordinary, now=NOW)
    assert error.value.category == "source_untrusted"
    assert [(event.action, event.reason) for event in ledger.audit()] == [
        ("receive_rejected", "source_untrusted"),
    ]
    assert ledger.list_received() == ()


def test_product_has_no_ledger_write_channel(tmp_path: Path) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid(), root))
    with pytest.raises(LedgerError) as error:
        ledger.initialize()
    assert error.value.category == "protected_entry_required"
    assert not (root / "ledger.sqlite3").exists()


def test_unapproved_receipt_is_atomic_and_has_controlled_failure_history(
    tmp_path: Path,
) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    source = root / "inbox" / "site.json"
    source.write_bytes(canonical_bytes(receipt()))
    source.chmod(0o644)
    with pytest.raises(LedgerError) as error:
        ledger.receive(source, now=NOW)
    assert error.value.category == "plan_missing"
    assert ledger.list_received() == ()
    assert [(item.action, item.reason) for item in ledger.audit()] == [
        ("receive_rejected", "plan_missing"),
    ]


def test_failed_round_is_preserved_and_stops_plan(tmp_path: Path) -> None:
    from paper_radar.live_evidence.receipt import (
        ApprovedPlan,
        EvidenceReceipt,
        content_sha256,
    )

    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    approved = ApprovedPlan.model_validate(plan().model_dump() | {"max_rounds": 2})
    ledger.approve_plan(approved, now=NOW)
    data = receipt().model_dump(mode="json")
    data["plan_sha256"] = content_sha256(approved)
    data["cases"][0]["outcome"] = "failed"
    data["failure_history"] = [{"case_id": "cwd", "reason": "isolation_failed"}]
    data["claims"][0].update({"status": "unknown", "verified_at": None})
    failed = EvidenceReceipt.model_validate(data)
    source = root / "inbox" / "failed.json"
    source.write_bytes(canonical_bytes(failed))
    source.chmod(0o644)
    result = ledger.receive(source, now=NOW)
    assert (
        ledger.show(result.receipt_id).receipt.failure_history[0].reason
        == "isolation_failed"
    )
    data["round_number"] = 2
    second = root / "inbox" / "next.json"
    second.write_bytes(canonical_bytes(EvidenceReceipt.model_validate(data)))
    second.chmod(0o644)
    with pytest.raises(LedgerError) as error:
        ledger.receive(second, now=NOW)
    assert error.value.category == "plan_stopped"
    assert len(ledger.list_received()) == 1


def test_ledger_schema_is_separate_and_newer_version_is_never_written(
    tmp_path: Path,
) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    with ledger.connection(writable=True) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert {
            row[1] for row in connection.execute("PRAGMA table_info(receipts)")
        } == {
            "receipt_id",
            "digest",
            "payload",
            "source_name",
            "source_digest",
            "plan_id",
            "round_number",
            "received_at",
        }
        connection.execute("PRAGMA user_version=2")
    before = (root / "ledger.sqlite3").read_bytes()
    with pytest.raises(LedgerError) as error:
        ledger.approve_plan(plan(), now=NOW)
    assert error.value.category == "ledger_schema_unsupported"
    with pytest.raises(LedgerError) as error:
        ledger.list_received()
    assert error.value.category == "ledger_schema_unsupported"
    assert before == (root / "ledger.sqlite3").read_bytes()


def test_approved_plan_can_be_queried_before_any_receipt(tmp_path: Path) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    ledger.approve_plan(plan(), now=NOW)
    assert ledger.show_plan("beta-1") == plan()
    assert ledger.list_received() == ()
