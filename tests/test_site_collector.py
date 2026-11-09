from pathlib import Path

import pytest

from paper_radar.live_evidence.receipt import UseId, validate_against_plan
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.live_evidence.types import Capability as C
from paper_radar.live_evidence.types import EvidenceStatus as S
from tests.live_evidence_ledger_support import NOW, plan


def test_beta_receipt_is_receivable_without_model_or_privileged_claims() -> None:
    from paper_radar.live_evidence.collector import SiteObservation, build_site_receipt

    approved = plan().model_copy(update={"cases": ("metadata", "isolation")})
    observed = SiteObservation(
        {
            component: "b" * 64
            for component in B
            if component not in {B.IPV4_EGRESS, B.OBSERVER}
        },
        (("metadata", True), ("isolation", True)),
    )
    receipt, current = build_site_receipt(
        approved,
        observed,
        use_id="boundary-low",
        started_at=NOW,
        completed_at=NOW,
    )
    validate_against_plan(receipt, approved, now=NOW)
    claims = {claim.capability: claim for claim in receipt.claims}
    assert claims[C.CWD_ANCESTORS].status is S.VERIFIED
    assert claims[C.FILE_ISOLATION].status is S.VERIFIED
    assert claims[C.IPV4_EGRESS].status is S.UNKNOWN
    assert claims[C.MODEL_IDENTITY].status is S.UNKNOWN
    assert claims[C.IPV4_EGRESS].verified_at is None
    assert set(current.checked_components) == set(B) - {B.IPV4_EGRESS, B.OBSERVER}
    assert all(
        case.auth_calls == case.model_calls == case.network_requests == 0
        for case in receipt.cases
    )


def test_first_failure_stops_and_keeps_unknown_capabilities() -> None:
    from paper_radar.live_evidence.collector import SiteObservation, build_site_receipt

    approved = plan().model_copy(update={"cases": ("metadata", "isolation")})
    observed = SiteObservation({}, (("metadata", False),))
    receipt, current = build_site_receipt(
        approved,
        observed,
        use_id="boundary-low",
        started_at=NOW,
        completed_at=NOW,
    )
    validate_against_plan(receipt, approved, now=NOW)
    assert [(case.case_id, case.outcome) for case in receipt.cases] == [
        ("metadata", "failed")
    ]
    assert [
        (failure.case_id, failure.reason) for failure in receipt.failure_history
    ] == [("metadata", "resource_unavailable")]
    assert not current.checked_components
    assert all(claim.status is S.UNKNOWN for claim in receipt.claims)
    assert all(claim.verified_at is None for claim in receipt.claims)


def test_collector_rejects_arguments_before_touching_any_source() -> None:
    from paper_radar.live_evidence.sealed_runtime import collector_main

    assert collector_main(["--config", "/tmp/untrusted"]) == 2
    assert collector_main(["activate"]) == 2


def test_collected_receipt_can_be_received_queried_and_refresh_keeps_original_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    from datetime import timedelta

    from paper_radar.live_evidence.collector import SITE_CASES, SiteObservation
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.live_evidence.sealed_runtime import collect_once
    from tests.site_collector_support import site_configuration

    sealed = tmp_path / "runtime"
    sealed.mkdir(mode=0o755)
    (sealed / "site.json").write_bytes(canonical_bytes(site_configuration(tmp_path)))
    approved = plan().model_copy(
        update={
            "plan_id": "site-beta",
            "cases": SITE_CASES,
            "starts_at": NOW - timedelta(days=100),
            "ends_at": NOW + timedelta(days=100),
        }
    )
    (sealed / "plan.json").write_bytes(canonical_bytes(approved))
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir(mode=0o755)
    (ledger_root / "inbox").mkdir(mode=0o755)
    ledger = EvidenceLedger(
        ledger_root,
        trust=LedgerTrust(owner_uid=os.getuid(), product_uid=999999, anchor=tmp_path),
    )
    observation = SiteObservation(
        {
            component: "b" * 64
            for component in B
            if component not in {B.IPV4_EGRESS, B.OBSERVER}
        },
        tuple((case, True) for case in SITE_CASES),
    )
    monkeypatch.setattr(
        "paper_radar.live_evidence.sealed_runtime.product_observation",
        lambda site: observation,
    )
    monkeypatch.setattr(
        "paper_radar.live_evidence.site_tree.observe_tree",
        lambda root, *, product_uid: "b" * 64,
    )
    source = ledger_root / "inbox" / collect_once(sealed, ledger)
    original = source.read_bytes()
    assert (ledger_root / "inbox/site-beta-plan.json").read_bytes() == canonical_bytes(
        approved
    )
    from datetime import UTC, datetime

    ledger.approve_plan_source(
        ledger_root / "inbox/site-beta-plan.json", now=datetime.now(UTC)
    )
    from datetime import UTC, datetime

    received = ledger.receive(source, now=datetime.now(UTC))
    assert ledger.show(received.receipt_id).receipt.failure_history == ()
    collect_once(sealed, ledger)
    assert source.read_bytes() == original
    assert len((ledger_root / "collector-history.jsonl").read_bytes().splitlines()) == 2


def test_synthetic_probe_records_individual_denials_and_zero_core(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.sealed_runtime import isolation_probe
    from paper_radar.pi_execution import resources
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.pi_execution.isolation import isolation_capability

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    install = tmp_path / "install"
    install.mkdir()
    monkeypatch.setattr(resources, "EXECUTION_CWD", cwd)
    try:
        isolation_capability()
    except ExecutionError:
        assert isolation_probe(install, proxy=None) == (("outside-read-denied", False),)
    else:
        assert isolation_probe(install, proxy=None) == (
            ("outside-read-denied", True),
            ("cwd-write-denied", True),
            ("install-write-denied", True),
            ("attempt-write-allowed", True),
            ("core-zero", True),
        )
    assert not list(cwd.iterdir())
    assert not list(install.iterdir())


def test_failed_round_stays_stopped_instead_of_retrying_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    from datetime import timedelta

    from paper_radar.live_evidence.collector import SITE_CASES, SiteObservation
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.receipt import EvidenceReceipt, canonical_bytes
    from paper_radar.live_evidence.sealed_runtime import collect_once
    from tests.site_collector_support import site_configuration

    sealed = tmp_path / "runtime"
    sealed.mkdir(mode=0o755)
    (sealed / "site.json").write_bytes(canonical_bytes(site_configuration(tmp_path)))
    approved = plan().model_copy(
        update={
            "cases": SITE_CASES,
            "starts_at": NOW - timedelta(days=100),
            "ends_at": NOW + timedelta(days=100),
        }
    )
    (sealed / "plan.json").write_bytes(canonical_bytes(approved))
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir(mode=0o755)
    (ledger_root / "inbox").mkdir(mode=0o755)
    ledger = EvidenceLedger(
        ledger_root,
        trust=LedgerTrust(owner_uid=os.getuid(), product_uid=999999, anchor=tmp_path),
    )
    monkeypatch.setattr(
        "paper_radar.live_evidence.sealed_runtime.product_observation",
        lambda site: SiteObservation({}, (("metadata", False),)),
    )
    source = ledger_root / "inbox" / collect_once(sealed, ledger)
    receipt = EvidenceReceipt.model_validate_json(source.read_bytes())
    assert receipt.failure_history[0].reason == "resource_unavailable"
    with pytest.raises(ValueError, match="plan_stopped"):
        collect_once(sealed, ledger)
    assert len((ledger_root / "collector-history.jsonl").read_bytes().splitlines()) == 1


@pytest.mark.parametrize(
    "change,reason",
    [
        ("path", "collector_path_invalid"),
        ("use", "collector_use_mismatch"),
        ("uid", "product_uid"),
    ],
)
def test_sealed_site_rejects_invalid_identity_and_paths(
    tmp_path: Path, change: str, reason: str
) -> None:
    from pydantic import ValidationError

    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
    from tests.site_collector_support import site_configuration

    data = site_configuration(tmp_path).model_dump()
    if change == "path":
        data["credentials_dir"] = Path("relative")
    elif change == "use":
        data["use_id"] = "value-high"
    else:
        data["product_uid"] = 0
    with pytest.raises(ValidationError, match=reason):
        SiteConfiguration.model_validate(data)


def test_observer_requires_product_identity_before_reading_sources(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.sealed_runtime import observe_site
    from tests.site_collector_support import site_configuration

    site = site_configuration(tmp_path)
    site = site.model_copy(update={"product_uid": site.product_uid + 1})
    with pytest.raises(ValueError, match="collector_product_identity"):
        observe_site(site)


def test_six_cells_share_only_content_independent_site_measurements() -> None:
    from paper_radar.live_evidence.collector import (
        SITE_CASES,
        SiteObservation,
        build_site_receipt,
    )

    approved = plan().model_copy(update={"cases": SITE_CASES})
    observed = SiteObservation(
        {
            component: "b" * 64
            for component in B
            if component not in {B.IPV4_EGRESS, B.OBSERVER}
        },
        tuple((case, True) for case in SITE_CASES),
    )
    uses: tuple[UseId, ...] = (
        "boundary-low",
        "boundary-high",
        "value-low",
        "value-high",
        "read-low",
        "read-high",
    )
    receipt, current = build_site_receipt(
        approved,
        observed,
        use_id="boundary-low",
        use_ids=uses,
        started_at=NOW,
        completed_at=NOW,
    )
    assert len(receipt.claims) == 210
    assert len(receipt.cases) == 7
    assert [
        claim.use_id
        for claim in receipt.claims
        if claim.capability is C.CWD_ANCESTORS and claim.status is S.VERIFIED
    ] == list(uses)
    assert all(
        claim.status is S.UNKNOWN
        for claim in receipt.claims
        if claim.capability in {C.MODEL_IDENTITY, C.RPC_COMPLETION, C.IPV4_EGRESS}
    )
    assert B.IPV4_EGRESS not in current.checked_components


def test_root_tree_recomputation_refuses_fabricated_product_expected_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    from datetime import timedelta

    from paper_radar.live_evidence.collector import SITE_CASES, SiteObservation
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.receipt import EvidenceReceipt, canonical_bytes
    from paper_radar.live_evidence.sealed_runtime import collect_once
    from tests.site_collector_support import site_configuration

    site = site_configuration(tmp_path)
    site.install_path.mkdir(parents=True)
    (site.install_path / "program").write_bytes(b"actual current tree")
    sealed = tmp_path / "runtime"
    sealed.mkdir(mode=0o755)
    (sealed / "site.json").write_bytes(canonical_bytes(site))
    approved = plan().model_copy(
        update={
            "cases": SITE_CASES,
            "starts_at": NOW - timedelta(days=100),
            "ends_at": NOW + timedelta(days=100),
        }
    )
    (sealed / "plan.json").write_bytes(canonical_bytes(approved))
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir(mode=0o755)
    (ledger_root / "inbox").mkdir(mode=0o755)
    ledger = EvidenceLedger(
        ledger_root,
        trust=LedgerTrust(owner_uid=os.getuid(), product_uid=999999, anchor=tmp_path),
    )
    fabricated = SiteObservation(
        {component: "b" * 64 for component in B},
        tuple((case, True) for case in SITE_CASES),
    )
    monkeypatch.setattr(
        "paper_radar.live_evidence.sealed_runtime.product_observation",
        lambda site: fabricated,
    )
    source = ledger_root / "inbox" / collect_once(sealed, ledger)
    receipt = EvidenceReceipt.model_validate_json(source.read_bytes())
    assert receipt.failure_history[0].reason == "resource_unavailable"
    assert all(claim.status is S.UNKNOWN for claim in receipt.claims)
