"""Live-04 独立例行观察覆盖;合成 root fixture 不授予现场资格。"""

import subprocess
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from sqlite3 import Connection
from typing import BinaryIO

import pytest

from paper_radar.live_evidence.collector import SiteObservation
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.observation import (
    CurrentObservation,
    load_current_observation,
)
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.live_evidence.types import BindingComponent
from paper_radar.pi_execution.admission import EvidenceBinding
from tests.live_evidence_ledger_support import NOW
from tests.live_evidence_lifecycle_support import activated


def test_failed_routine_refresh_keeps_fresh_snapshot_and_rejects_across_reopen(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.refresh import record_refresh

    ledger, original, _ = activated(tmp_path)
    observation = CurrentObservation(
        observed_at=NOW, binding=original.binding, checked_components=()
    )
    target = ledger.root / "inbox/current-observation.json"
    target.write_bytes(canonical_bytes(observation))
    target.chmod(0o644)
    prior_events = ledger.audit()
    record_refresh(
        ledger,
        candidate=None,
        failure="observation_unavailable",
        now=NOW + timedelta(seconds=1),
    )
    assert target.read_bytes() == canonical_bytes(observation)
    assert ledger.audit() == prior_events
    with pytest.raises(LedgerError, match="observation_unavailable"):
        load_current_observation(ledger, now=NOW + timedelta(seconds=2))


def test_new_snapshot_restores_freshness_without_reviving_revoked_evidence(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.refresh import record_refresh
    from paper_radar.live_evidence.types import BindingComponent as B

    ledger, original, _ = activated(tmp_path)
    original_snapshot = CurrentObservation(
        observed_at=NOW - timedelta(seconds=61),
        binding=original.binding,
        checked_components=(B.CWD_ANCESTORS,),
    )
    source = ledger.root / "inbox/current-observation.json"
    source.write_bytes(canonical_bytes(original_snapshot))
    source.chmod(0o644)
    candidate = original_snapshot.model_copy(
        update={
            "observed_at": NOW,
            "binding": original.binding | {B.CWD_ANCESTORS: "d" * 64},
        }
    )
    status = record_refresh(ledger, candidate=candidate, now=NOW)
    assert status.result == "observation_drift"
    with pytest.raises(LedgerError, match="observation_drift"):
        load_current_observation(ledger, now=NOW)
    assert EvidenceLifecycle(ledger).snapshot(now=NOW).evidence[0].revoked
    record_refresh(
        ledger,
        candidate=candidate.model_copy(
            update={"observed_at": NOW + timedelta(seconds=1)}
        ),
        now=NOW + timedelta(seconds=1),
    )
    assert load_current_observation(
        ledger, now=NOW + timedelta(seconds=1)
    ).observed_at == NOW + timedelta(seconds=1)
    assert (
        EvidenceLifecycle(ledger)
        .snapshot(now=NOW + timedelta(seconds=1))
        .evidence[0]
        .revoked
    )
    assert ledger.show(original.receipt_id).receipt == original


def test_unavailable_projection_keeps_original_evidence_and_shared_chinese_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.doctor.admission import render_admission_fragment
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.service import (
        AdmissionRequest,
        load_admission_evidence,
        unavailable_projection,
    )
    from tests.screening_live_admission_support import protected_admission

    ledger, original, components = protected_admission(
        tmp_path / "evidence", monkeypatch
    )
    projection = load_admission_evidence(
        AdmissionRequest(
            use_for_id("boundary-low"),
            ExecutionBinding(tuple(components.items())),
            frozenset(components),
        ),
        now=NOW,
    )
    failed = unavailable_projection(
        projection.decision.use,
        LedgerError("observation_unavailable"),
        previous=projection,
    )
    fragment = render_admission_fragment(failed)
    assert "观察不可用（临时）" in fragment
    assert "reason=observation_unavailable" in fragment
    assert "original_state=verified" in fragment
    assert f"verified_at={NOW.isoformat()}" in fragment
    assert not failed.decision.executable
    assert not any(item.qualified for item in failed.decision.capabilities)
    assert ledger.show(original.receipt_id).receipt == original


def refresh_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[EvidenceLedger, Path, dict[str, object], CurrentObservation]:
    import json

    from paper_radar.live_evidence import protected_observer as observer
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.live_evidence.types import Capability as C
    from paper_radar.pi_execution import placement

    ledger, original, _ = activated(
        tmp_path,
        capabilities=(C.CWD_ANCESTORS, C.IPV4_EGRESS, C.SINGLE_DISPATCH),
        provider=True,
    )
    runtime = ledger.root / "sealed-runtime"
    for relative in observer.OBSERVER_MEMBERS:
        member = runtime / relative
        member.parent.mkdir(parents=True, exist_ok=True)
        member.write_bytes(b"sealed observer synthetic fixture\n")
        member.chmod(0o644)
    for directory in (runtime, *(path for path in runtime.rglob("*") if path.is_dir())):
        directory.chmod(0o755)
    from tests.site_collector_support import site_configuration

    (runtime / "site.json").write_bytes(canonical_bytes(site_configuration(tmp_path)))
    local_components = {
        component: value
        for component, value in original.binding.items()
        if component not in {B.IPV4_EGRESS, B.OBSERVER}
    }

    def metadata(
        site: SiteConfiguration, *, metadata_only: bool = False
    ) -> SiteObservation:
        assert metadata_only
        return SiteObservation(local_components.copy(), (("metadata", True),))

    monkeypatch.setattr(
        "paper_radar.live_evidence.sealed_runtime.product_observation", metadata
    )
    cg = tmp_path / "cgroup"
    (cg / "paperradar.slice").mkdir(parents=True)
    proc = tmp_path / "proc/4242"
    proc.mkdir(parents=True)
    (proc / "stat").write_text("4242 (anchor) S " + "0 " * 18 + "100\n")
    (proc / "cgroup").write_text("0::/paperradar.slice/paperradar-anchor.service\n")
    monkeypatch.setattr(placement, "_CGROUP_ROOT", cg)
    monkeypatch.setattr(placement, "_PROC_ROOT", tmp_path / "proc")
    target = placement.PlacementTarget(
        format_version=1,
        slice="paperradar.slice",
        ancestors=tuple(
            placement.CgroupIdentity(
                path, directory.stat().st_dev, directory.stat().st_ino
            )
            for path, directory in (
                ("/paperradar.slice", cg / "paperradar.slice"),
                ("/", cg),
            )
        ),
        anchor_pid=4242,
        anchor_start=100,
        anchor_cgroup="/paperradar.slice/paperradar-anchor.service",
        egress_digest="0" * 64,
        resolver_view="/run/paper-radar/resolv.conf",
        resolver_digest="a" * 64,
    )
    nft: dict[str, object] = {
        "nftables": [
            {"table": {"family": "inet", "name": "paperradar", "handle": 7}},
            {
                "rule": {
                    "expr": [{"counter": {"packets": 0, "bytes": 0}}, {"drop": None}]
                }
            },
        ]
    }
    target = target.model_copy(
        update={"egress_digest": observer.egress_identity(nft, target)}
    )
    (ledger.root / "inbox" / placement.TARGET_FILENAME).write_bytes(
        canonical_bytes(target)
    )
    (ledger.root / "inbox" / placement.TARGET_FILENAME).chmod(0o644)
    previous = CurrentObservation(
        observed_at=NOW,
        binding=original.binding
        | {
            B.IPV4_EGRESS: target.egress_digest,
            B.OBSERVER: observer.observer_identity(runtime, ledger),
        },
        checked_components=tuple(B),
    )
    (ledger.root / "inbox/current-observation.json").write_bytes(
        canonical_bytes(previous)
    )
    (ledger.root / "inbox/current-observation.json").chmod(0o644)

    def run(
        argv: tuple[str, ...], *, stdout: BinaryIO, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        from subprocess import CompletedProcess

        assert argv == ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar")
        stdout.write(json.dumps(nft).encode())
        return CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    return ledger, runtime, nft, previous


def test_routine_root_refresh_uses_actual_sources_and_survives_observer_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.ledger import EvidenceLedger
    from paper_radar.live_evidence.protected_observer import refresh_once

    ledger, runtime, _nft, previous = refresh_site(tmp_path, monkeypatch)
    prior = ledger.audit()
    assert refresh_once(runtime, ledger, now=NOW + timedelta(seconds=1)) == "available"
    reopened = EvidenceLedger(ledger.root, trust=ledger.trust)
    current = load_current_observation(reopened, now=NOW + timedelta(seconds=61))
    assert current.observed_at == NOW + timedelta(seconds=1)
    assert current.binding == previous.binding
    with pytest.raises(LedgerError, match="observation_stale"):
        load_current_observation(
            reopened, now=NOW + timedelta(seconds=61, microseconds=1)
        )
    assert ledger.audit() == prior
    assert not tuple(ledger.root.glob("*.stopped"))


@pytest.mark.parametrize(
    "damage",
    [
        "nft_unavailable",
        "nft_drift",
        "cgroup_drift_and_nft_failure",
        "observer_drift",
        "observer_lost",
        "observer_untrusted",
    ],
)
def test_routine_refresh_classifies_failures_without_stale_hiding_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from paper_radar.live_evidence import protected_observer as observer
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.types import Capability as C

    ledger, runtime, nft, _previous = refresh_site(tmp_path, monkeypatch)
    before = (ledger.root / "inbox/current-observation.json").read_bytes()
    if damage in {"nft_unavailable", "cgroup_drift_and_nft_failure"}:

        def unavailable(*args: object, **kwargs: object) -> None:
            raise OSError("transient synthetic failure")

        monkeypatch.setattr(subprocess, "run", unavailable)
    if damage == "cgroup_drift_and_nft_failure":
        (tmp_path / "proc/4242/cgroup").write_text("0::/different-anchor\n")
    elif damage == "nft_drift":
        rows = nft["nftables"]
        assert isinstance(rows, list)
        rows.append({"rule": {"accept": None}})
    elif damage == "observer_drift":
        (runtime / "entry.py").write_bytes(b"changed sealed observer\n")
    elif damage == "observer_lost":
        (runtime / "entry.py").unlink()
    elif damage == "observer_untrusted":
        (runtime / "entry.py").chmod(0o666)
    result = observer.refresh_once(runtime, ledger, now=NOW + timedelta(seconds=61))
    expected = (
        "observation_unavailable"
        if damage == "nft_unavailable"
        else "source_untrusted"
        if damage in {"observer_lost", "observer_untrusted"}
        else "observation_drift"
    )
    assert result == expected
    with pytest.raises(LedgerError, match=expected):
        load_current_observation(ledger, now=NOW + timedelta(seconds=61))
    if damage in {"nft_unavailable", "observer_lost"}:
        assert (ledger.root / "inbox/current-observation.json").read_bytes() == before
    evidence = {
        item.capability: item
        for item in EvidenceLifecycle(ledger)
        .snapshot(now=NOW + timedelta(seconds=61))
        .evidence
    }
    assert evidence[C.CWD_ANCESTORS].revoked == (
        damage in {"observer_lost", "observer_untrusted"}
    )
    assert evidence[C.IPV4_EGRESS].revoked == (
        damage
        in {
            "nft_drift",
            "cgroup_drift_and_nft_failure",
            "observer_lost",
            "observer_untrusted",
        }
    )
    assert evidence[C.SINGLE_DISPATCH].revoked == (
        damage in {"observer_drift", "observer_lost", "observer_untrusted"}
    )


def test_site_snapshot_supports_low_and_high_without_borrowing_model_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id
    from paper_radar.live_evidence.receipt import content_sha256
    from paper_radar.live_evidence.service import load_admission_evidence
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.pi_execution import current_binding
    from tests.screening_live_admission_support import protected_admission
    from tests.test_pi_execution_admission import binding

    ledger, original, components = protected_admission(
        tmp_path / "evidence", monkeypatch
    )

    def local(
        _database: Path, selected: EvidenceBinding, **kwargs: object
    ) -> dict[BindingComponent, str]:
        return {
            key: value
            for key, value in components.items()
            if key not in {B.IPV4_EGRESS, B.OBSERVER}
        } | {
            B.MODEL_TUPLE: "d" * 64
            if selected.thinking_level == "high"
            else components[B.MODEL_TUPLE]
        }

    monkeypatch.setattr(current_binding, "local_binding_components", local)
    low = current_binding.build_admission_request(
        tmp_path / "unused",
        binding(),
        use=use_for_id("boundary-low"),
        credentials_dir=tmp_path,
        now=NOW,
    )
    high = current_binding.build_admission_request(
        tmp_path / "unused",
        replace(binding(), thinking_level="high"),
        use=use_for_id("boundary-high"),
        credentials_dir=tmp_path,
        now=NOW,
    )
    assert {B.IPV4_EGRESS, B.OBSERVER} <= high.checked_components
    current_binding.recheck_admission_request(high, now=NOW)
    assert load_admission_evidence(low, now=NOW).decision.executable
    assert not load_admission_evidence(high, now=NOW).decision.executable
    from tests.live_evidence_ledger_support import plan

    approved = plan().model_copy(
        update={"plan_id": "high-cell", "kind": "model_six_cell"}
    )
    ledger.approve_plan(approved, now=NOW)
    high_receipt = original.model_copy(
        update={
            "plan_id": approved.plan_id,
            "plan_sha256": content_sha256(approved),
            "binding": dict(high.binding.components),
            "claims": tuple(
                claim.model_copy(update={"use_id": "boundary-high"})
                for claim in original.claims
            ),
        }
    )
    source = ledger.root / "inbox/high.json"
    source.write_bytes(canonical_bytes(high_receipt))
    source.chmod(0o644)
    ledger.receive(source, now=NOW)
    lifecycle = EvidenceLifecycle(ledger)
    review = lifecycle.review(
        high_receipt.receipt_id,
        "boundary-high",
        binding=high.binding,
        checked_components=high.checked_components,
        now=NOW,
    )
    lifecycle.activate(review, confirmation=high_receipt.receipt_id, now=NOW)
    assert load_admission_evidence(high, now=NOW).decision.executable
    components[B.KERNEL] = "e" * 64
    drifted = current_binding.build_admission_request(
        tmp_path / "unused",
        replace(binding(), thinking_level="high"),
        use=use_for_id("boundary-high"),
        credentials_dir=tmp_path,
        now=NOW,
    )
    assert not {B.IPV4_EGRESS, B.OBSERVER} <= drifted.checked_components
    assert not load_admission_evidence(drifted, now=NOW).decision.executable


@pytest.mark.parametrize("consumer", ["screening", "read"])
def test_formal_refresh_failure_before_auth_has_no_business_or_evidence_side_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    from paper_radar.live_evidence import service as evidence
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.pi_execution.errors import ExecutionError
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    if consumer == "screening":
        product, task, credentials = product_inputs(tmp_path / "product", monkeypatch)
        identifier = task.receipt_id
        before = product.tasks.status(identifier)
    else:
        from tests.read_execution_support import setup

        read_product, read_task, credentials = setup(tmp_path / "product", monkeypatch)
        identifier = read_task.task_id
        read_before = read_product.tasks.task(identifier)
    ledger, original, _ = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("boundary-low", "read-low")
    )
    active_product = product if consumer == "screening" else read_product
    active_product._now = lambda: NOW
    events = ledger.audit()

    def unavailable() -> None:
        raise LedgerError("observation_unavailable")

    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_observation_refresh",
        unavailable,
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        active_product.run_attempt(identifier)
    after = (
        product.tasks.status(identifier)
        if consumer == "screening"
        else read_product.tasks.task(identifier)
    )
    assert after == (before if consumer == "screening" else read_before)
    assert ledger.audit() == events
    assert not (credentials / "auth-observed.json").exists()
    assert evidence._read_pending() == ()
    assert ledger.show(original.receipt_id).receipt == original


def test_doctor_reads_failed_refresh_and_preserves_snapshot_time_without_refreshing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.refresh import record_refresh
    from tests.test_doctor_live_admission import diagnose, selected_site

    database, snapshot, credentials, ledger, original = selected_site(
        tmp_path, monkeypatch
    )
    record_refresh(ledger, candidate=None, failure="observation_unavailable", now=NOW)
    before = ledger.audit()

    def forbidden() -> None:
        raise AssertionError("doctor must remain read only")

    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_observation_refresh",
        forbidden,
    )
    result = diagnose(database, snapshot, credentials)
    assert result.exit_code == 2
    assert "观察不可用（临时）" in result.output
    assert "original_state=verified" in result.output
    assert f"observed_at={NOW.isoformat()}" in result.output
    assert "refresh_result=observation_unavailable" in result.output
    assert ledger.audit() == before
    assert ledger.show(original.receipt_id).receipt == original


def test_collector_can_refresh_under_same_kernel_lock_without_relocking_other_fd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.protected_observer import (
        protected_collection_lock,
        refresh_under_lock,
    )

    ledger, runtime, _nft, _previous = refresh_site(tmp_path, monkeypatch)
    with protected_collection_lock(ledger) as lock_fd:
        assert (
            refresh_under_lock(runtime, ledger, lock_fd=lock_fd, now=NOW) == "available"
        )
        assert (
            refresh_under_lock(runtime, ledger, lock_fd=lock_fd, now=NOW) == "available"
        )


@pytest.mark.parametrize("returncode", [0, 2])
def test_helper_cannot_reuse_old_fresh_observation_when_refresh_did_not_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int
) -> None:
    from subprocess import CompletedProcess

    from paper_radar.live_evidence import protected_observer as observer

    ledger, _runtime, _nft, _previous = refresh_site(tmp_path, monkeypatch)
    monkeypatch.setattr(observer, "EvidenceLedger", lambda: ledger)

    def run(
        argv: tuple[str, ...], *, stdout: BinaryIO, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        assert argv == (
            "/usr/bin/sudo",
            "-n",
            "--",
            "/usr/libexec/paperradar/live-evidence-refresh",
        )
        assert kwargs["stdin"] == -3
        return CompletedProcess(argv, returncode)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(LedgerError, match="observation_unavailable"):
        observer.request_observation_refresh()


def test_refresh_entry_rejects_free_arguments_before_reading_any_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import protected_observer as observer

    def forbidden() -> None:
        raise AssertionError("must not open ledger")

    monkeypatch.setattr(observer, "EvidenceLedger", forbidden)
    assert observer.refresh_main(["/tmp/free-path"]) == 2


def test_database_failure_keeps_drift_marker_and_pending_disclosure_across_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    from paper_radar.live_evidence.ledger import EvidenceLedger
    from paper_radar.live_evidence.observation import load_refresh_status
    from paper_radar.live_evidence.protected_observer import refresh_once

    ledger, runtime, nft, previous = refresh_site(tmp_path, monkeypatch)
    rows = nft["nftables"]
    assert isinstance(rows, list)
    rows.append({"rule": {"accept": None}})
    original = ledger.connection

    @contextmanager
    def unavailable(*, writable: bool = False) -> Iterator[Connection]:
        if writable:
            raise OSError("synthetic database unavailable")
        with original() as connection:
            yield connection

    monkeypatch.setattr(ledger, "connection", unavailable)
    with pytest.raises(OSError, match="synthetic database unavailable"):
        refresh_once(runtime, ledger, now=NOW + timedelta(seconds=61))
    reopened = EvidenceLedger(ledger.root, trust=ledger.trust)
    status = load_refresh_status(reopened)
    assert status is not None and status.result == "observation_drift"
    assert status.pending_revocation
    assert (
        ledger.root / "inbox/current-observation.json"
    ).read_bytes() == canonical_bytes(previous)
    assert (
        b'"result":"observation_drift"'
        in (ledger.root / "observation-refresh-history.jsonl").read_bytes()
    )
    with pytest.raises(LedgerError, match="observation_drift"):
        load_current_observation(reopened, now=NOW + timedelta(seconds=61))


def test_confirmed_nft_table_loss_is_drift_instead_of_temporary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from subprocess import CompletedProcess

    from paper_radar.live_evidence import protected_observer as observer

    ledger, runtime, _nft, _previous = refresh_site(tmp_path, monkeypatch)

    def run(
        argv: tuple[str, ...], *, stdout: BinaryIO, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        if argv == ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar"):
            return CompletedProcess(argv, 2)
        assert argv == ("/usr/sbin/nft", "-j", "list", "tables")
        stdout.write(b'{"nftables":[]}')
        return CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert observer.refresh_once(runtime, ledger, now=NOW) == "observation_drift"
    assert observer.refresh_once(runtime, ledger, now=NOW) == "observation_drift"


def test_missing_refresh_source_cannot_be_treated_as_observer_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import protected_observer as observer

    ledger, runtime, _nft, _previous = refresh_site(tmp_path, monkeypatch)
    assert observer.refresh_once(runtime, ledger, now=NOW) == "available"
    (ledger.root / "inbox/observation-refresh.json").unlink()
    with pytest.raises(LedgerError, match="source_untrusted"):
        load_current_observation(ledger, now=NOW)
    assert observer.refresh_once(runtime, ledger, now=NOW) == "source_untrusted"


def test_preclaim_finds_actual_binding_drift_before_stale_and_preserves_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.observation import ObservationChanged
    from paper_radar.live_evidence.service import AdmissionRequest
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.pi_execution import current_binding

    ledger, _runtime, _nft, previous = refresh_site(tmp_path, monkeypatch)
    monkeypatch.setattr(current_binding, "EvidenceLedger", lambda: ledger)
    request = AdmissionRequest(
        use_for_id("boundary-low"),
        ExecutionBinding(tuple(previous.binding.items())),
        frozenset(B),
    )
    changed = previous.model_copy(
        update={"binding": previous.binding | {B.IPV4_EGRESS: "e" * 64}}
    )
    (ledger.root / "inbox/current-observation.json").write_bytes(
        canonical_bytes(changed)
    )
    with pytest.raises(ObservationChanged, match="observation_changed") as raised:
        current_binding.recheck_admission_request(
            request, now=NOW + timedelta(seconds=61)
        )
    assert raised.value.components == frozenset({B.IPV4_EGRESS})


def test_only_counter_values_evolve_while_rule_byte_constraints_still_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import protected_observer as observer

    ledger, runtime, nft, _previous = refresh_site(tmp_path, monkeypatch)
    rows = nft["nftables"]
    assert isinstance(rows, list)
    rows[1]["rule"]["expr"][0]["counter"] = {"packets": 3, "bytes": 800}
    assert observer.refresh_once(runtime, ledger, now=NOW) == "available"
    rows[1]["rule"]["expr"].append({"quota": {"bytes": 5}})
    assert observer.refresh_once(runtime, ledger, now=NOW) == "observation_drift"


@pytest.mark.parametrize(
    "version,expected",
    [
        (6, "df039edfb53f85b526c7828984dda44d51c3300a65a07e833b4a4dffc3916223"),
        (7, "7d5f59efbc2addb76848bbd6cccdbfa6bb6a9a1172a659ba8667bf08d189075e"),
    ],
)
def test_archived_policies_keep_original_bytes(version: int, expected: str) -> None:
    import hashlib

    source = (
        Path(__file__).parent / f"fixtures/live-admission-source-guard-v{version}.json"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("consumer", ["screening", "read"])
def test_helper_unavailable_does_not_hide_confirmed_missing_observation_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    from paper_radar.live_evidence import service as evidence
    from paper_radar.pi_execution.errors import ExecutionError
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    if consumer == "screening":
        product, task, _credentials = product_inputs(tmp_path / "product", monkeypatch)
        identifier = task.receipt_id
    else:
        from tests.read_execution_support import setup

        read_product, read_task, _credentials = setup(tmp_path / "product", monkeypatch)
        identifier = read_task.task_id
    ledger, _original, _components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("boundary-low", "read-low")
    )
    active_product = product if consumer == "screening" else read_product
    active_product._now = lambda: NOW
    (ledger.root / "inbox/current-observation.json").unlink()

    def unavailable() -> None:
        raise LedgerError("observation_unavailable")

    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_observation_refresh",
        unavailable,
    )
    monkeypatch.setattr(evidence, "_run_helper", lambda arguments: False)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        active_product.run_attempt(identifier)
    assert evidence._read_pending()


def test_metadata_only_observation_rechecks_context_without_full_beta_or_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.live_evidence import sealed_runtime as runtime
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.pi_execution.admission import bind_description
    from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
    from paper_radar.pi_execution.resources import (
        LAUNCH_POLICY_VERSION,
        expected_cwd_section,
    )
    from paper_radar.pi_execution.service import prepare_call
    from paper_radar.pi_supply import activation_history
    from tests.screening_live_admission_support import product_inputs

    product, task, credentials = product_inputs(tmp_path, monkeypatch)
    selected = activation_history(product.database)[-1]
    binding = bind_description(
        prepare_call(product.tasks, task.receipt_id),
        supply_id=selected.supply_id,
        install_id=selected.install_id,
        launch_policy_version=LAUNCH_POLICY_VERSION,
        isolation_policy_version=ISOLATION_POLICY_VERSION,
        cwd_section=expected_cwd_section(),
        auth_mode="chatgpt_subscription",
    )
    site = runtime.SiteConfiguration(
        product_uid=os.getuid(),
        product_gid=os.getgid(),
        database=product.database,
        snapshot_id=selected.snapshot_id,
        install_path=product.roots.install_root
        / selected.supply_id
        / selected.install_id,
        credentials_dir=credentials,
        roots=product.roots,
        binding=binding,
        use_id="boundary-low",
    )

    def forbidden_probe(*args: object, **kwargs: object) -> None:
        raise AssertionError("routine metadata must not run full beta")

    import platform

    platform.processor()  # 先完成公开平台查询;例行观察不得再启动 Node 或 beta。
    monkeypatch.setattr(runtime, "isolation_probe", forbidden_probe)
    monkeypatch.setattr(subprocess, "run", forbidden_probe)
    observed = runtime.observe_site(site, metadata_only=True)
    assert observed.checks == (("metadata", True),)
    assert set(observed.components) == set(B) - {B.IPV4_EGRESS, B.OBSERVER}
    assert not (credentials / "auth-observed.json").exists()


def test_fresh_snapshot_failed_refresh_is_refused_by_new_python_process(
    tmp_path: Path,
) -> None:
    import subprocess
    import sys

    from paper_radar.live_evidence.refresh import record_refresh

    ledger, original, _binding = activated(tmp_path)
    snapshot = CurrentObservation(
        observed_at=NOW, binding=original.binding, checked_components=()
    )
    source = ledger.root / "inbox/current-observation.json"
    source.write_bytes(canonical_bytes(snapshot))
    source.chmod(0o644)
    record_refresh(ledger, candidate=None, failure="observation_unavailable", now=NOW)
    program = """
import sys
from datetime import datetime
from pathlib import Path
import subprocess
from typing import BinaryIO
from collections.abc import Iterator
from sqlite3 import Connection
from paper_radar.live_evidence.ledger import EvidenceLedger
from paper_radar.live_evidence.collector import SiteObservation
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.live_evidence.types import BindingComponent
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust, LedgerError
from paper_radar.live_evidence.observation import load_current_observation
root = Path(sys.argv[1])
trust = LedgerTrust(int(sys.argv[2]), int(sys.argv[2])+1, root)
ledger = EvidenceLedger(root, trust=trust)
try:
    load_current_observation(ledger, now=datetime.fromisoformat(sys.argv[3]))
except LedgerError as error:
    print(error.category)
else:
    raise AssertionError('old fresh snapshot must not admit after failed refresh')
"""
    child = subprocess.run(
        (
            sys.executable,
            "-I",
            "-c",
            program,
            str(ledger.root),
            str(ledger.trust.owner_uid),
            NOW.isoformat(),
        ),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env={},
        timeout=10,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout == "observation_unavailable\n"


def test_preclaim_rejects_atomic_publication_between_snapshot_and_status_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.observation import RefreshStatus
    from paper_radar.live_evidence.service import AdmissionRequest
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.pi_execution import current_binding

    ledger, _runtime, _nft, previous = refresh_site(tmp_path, monkeypatch)
    request = AdmissionRequest(
        use_for_id("boundary-low"),
        ExecutionBinding(tuple(previous.binding.items())),
        frozenset(B),
    )
    reader = ledger._read_source
    published = False

    def read(source: Path) -> bytes:
        nonlocal published
        data = reader(source)
        if source.name == "current-observation.json" and not published:
            published = True
            changed = previous.model_copy(
                update={"binding": previous.binding | {B.IPV4_EGRESS: "e" * 64}}
            )
            source.write_bytes(canonical_bytes(changed))
            status = RefreshStatus(
                recorded_at=NOW,
                result="available",
                snapshot_sha256=hashlib.sha256(canonical_bytes(changed)).hexdigest(),
            )
            marker = ledger.root / "inbox/observation-refresh.json"
            marker.write_bytes(canonical_bytes(status))
            marker.chmod(0o644)
        return data

    monkeypatch.setattr(ledger, "_read_source", read)
    monkeypatch.setattr(current_binding, "EvidenceLedger", lambda: ledger)
    with pytest.raises(LedgerError, match="observation_unavailable"):
        current_binding.recheck_admission_request(request, now=NOW)


def test_healthy_doctor_discloses_same_successful_snapshot_and_refresh_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.observation import load_current_observation
    from paper_radar.live_evidence.refresh import record_refresh
    from tests.test_doctor_live_admission import diagnose, selected_site

    database, snapshot, credentials, ledger, _original = selected_site(
        tmp_path, monkeypatch
    )
    current = load_current_observation(ledger, now=NOW)
    record_refresh(ledger, candidate=current, now=NOW)
    result = diagnose(database, snapshot, credentials)
    assert result.exit_code == 0, result.output
    assert f"observed_at={NOW.isoformat()}" in result.output
    assert "refresh_result=available" in result.output
    assert "executable=true" in result.output
