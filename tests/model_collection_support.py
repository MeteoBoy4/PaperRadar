"""独立合成root库存与替代OS/RPC边界;没有现场资格。"""

import hashlib
import os
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.collection import ProtectedCollection
from paper_radar.live_evidence.collector import (
    SITE_CASES,
    SiteObservation,
    build_site_receipt,
)
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.model_ipc import Stage, WorkerMessage
from paper_radar.live_evidence.model_manifest import (
    NEGATIVES,
    USES,
    ModelCell,
    ModelManifest,
    NetworkConfiguration,
)
from paper_radar.live_evidence.model_worker import ModelObservation
from paper_radar.live_evidence.network_collection import NetworkOutcome
from paper_radar.live_evidence.observation import CurrentObservation
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.refresh import record_refresh
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution.current_binding import model_tuple_component
from paper_radar.pi_execution.placement import CgroupIdentity, PlacementTarget
from paper_radar.pi_execution.site_binding import component_digest
from tests.live_evidence_ledger_support import NOW, owner_uid, protected_root
from tests.site_collector_support import site_configuration
from tests.test_live_collection_v2 import approved


def nft(packets: list[int]) -> dict[str, Any]:
    return {
        "nftables": [
            {
                "rule": {
                    "family": "inet",
                    "table": "paperradar",
                    "chain": "output",
                    "handle": 11 + i,
                    "comment": "paperradar-negative-" + NEGATIVES[i],
                    "expr": [
                        {"counter": {"packets": value, "bytes": value * 80}},
                        {"drop": None},
                    ],
                }
            }
            for i, value in enumerate(packets)
        ]
    }


def setup_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, EvidenceLedger, ProtectedCollection, ModelManifest, list[str]]:
    from paper_radar.live_evidence import protected_observer as observer

    root = protected_root(tmp_path)
    ledger = EvidenceLedger(
        root, trust=LedgerTrust(owner_uid=owner_uid(), anchor=tmp_path)
    )
    ledger.initialize()
    collection = ProtectedCollection(ledger)
    collection.initialize(now=NOW)
    runtime = root / "runtime"
    runtime.mkdir()
    site = site_configuration(tmp_path)
    (runtime / "site.json").write_bytes(canonical_bytes(site))
    cg = tmp_path / "cgroup"
    (cg / "paperradar.slice").mkdir(parents=True)
    (cg / "paperradar.slice/cgroup.procs").write_text("4242\n")
    target = PlacementTarget(
        format_version=1,
        slice="paperradar.slice",
        ancestors=(
            CgroupIdentity("/paperradar.slice", 1, 2),
            CgroupIdentity("/", 1, 3),
        ),
        anchor_pid=4242,
        anchor_start=100,
        anchor_cgroup="/paperradar.slice/paperradar-anchor.service",
        egress_digest="a" * 64,
        resolver_view="/run/paper-radar/resolv.conf",
        resolver_digest="a" * 64,
    )
    digest = observer.egress_identity(nft([0, 0, 0, 0]), target)
    target = target.model_copy(update={"egress_digest": digest})
    (root / "inbox/placement-target-v1.json").write_bytes(canonical_bytes(target))
    monkeypatch.setattr("paper_radar.pi_execution.placement._CGROUP_ROOT", cg)
    monkeypatch.setattr(
        "paper_radar.pi_execution.placement.verify_placement", lambda *args: None
    )
    monkeypatch.setattr(
        "paper_radar.live_evidence.network_collection.exclusive_probe",
        lambda *args: True,
    )
    monkeypatch.setattr("os.getpgid", lambda pid: 999999)
    binding = {part: "b" * 64 for part in B} | {
        B.IPV4_EGRESS: digest,
        B.MODEL_TUPLE: model_tuple_component(site.binding),
    }
    site_plan = ApprovedPlan(
        format_version="v1",
        plan_id="site-fixed",
        kind="site_beta",
        collector_sha256="a" * 64,
        cases=SITE_CASES,
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(days=1),
        max_auth_calls=0,
        max_model_calls=0,
        max_network_requests=0,
        max_rounds=1,
        stop_on_first_failure=True,
    )
    ledger.approve_plan(site_plan, now=NOW)
    receipt, _ = build_site_receipt(
        site_plan,
        SiteObservation(binding, tuple((name, True) for name in SITE_CASES)),
        use_id="boundary-low",
        use_ids=USES,
        started_at=NOW,
        completed_at=NOW,
    )
    (root / "inbox/site-fixed-round-1.json").write_bytes(canonical_bytes(receipt))
    members = {}
    cells = []
    for use in USES:
        path = runtime / "materials" / use / "fixed.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"fixed synthetic material\n")
        relative = str(path.relative_to(runtime))
        members[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        plan = approved("plan-" + use).model_copy(
            update={"cases": ("model-" + use,), "max_network_requests": 0}
        )
        collection.approve_plan(plan, now=NOW)
        cells.append(
            ModelCell(
                use_id=use,
                plan=plan,
                model=replace(site.binding, thinking_level=use.rsplit("-", 1)[1]),
                binding={
                    B.MODEL_TUPLE: model_tuple_component(
                        replace(site.binding, thinking_level=use.rsplit("-", 1)[1])
                    )
                },
                material_sha256=component_digest({relative: members[relative]}),
                snapshot_id="d" * 64,
                request_sha256="e" * 64,
            )
        )
    negative = approved("negative-fixed").model_copy(
        update={
            "kind": "site_beta",
            "cases": NEGATIVES,
            "max_auth_calls": 0,
            "max_model_calls": 0,
            "max_network_requests": 20,
        }
    )
    collection.approve_plan(negative, now=NOW)
    confirmation = b"Owner reviewed fixed synthetic network applicability.\n"
    (runtime / "network-owner-confirmation.json").write_bytes(confirmation)
    manifest = ModelManifest(
        format_version=1,
        collector_sha256="a" * 64,
        site_plan_id=site_plan.plan_id,
        site_plan_sha256=content_sha256(site_plan),
        actual_snapshot_id=site.snapshot_id,
        cells=tuple(cells),
        negative_plan=negative,
        network=NetworkConfiguration.model_validate(
            dict(
                pool="192.0.2.0/24",
                router="192.0.2.1",
                outside="198.51.100.10",
                nonrouter="192.0.2.2",
                udp443="198.51.100.10",
                owner_confirmation_sha256=hashlib.sha256(confirmation).hexdigest(),
                plan_ids=(*(cell.plan.plan_id for cell in cells), negative.plan_id),
                starts_at=NOW - timedelta(hours=1),
                ends_at=NOW + timedelta(days=1),
            )
        ),
        members=members,
    )
    (runtime / "model-manifest.json").write_bytes(canonical_bytes(manifest))
    (root / "inbox/current-observation.json").write_bytes(
        canonical_bytes(
            CurrentObservation(
                observed_at=NOW, binding=binding, checked_components=tuple(B)
            )
        )
    )
    (root / "inbox/current-observation.json").chmod(0o644)

    def refresh(_root: Path, _ledger: EvidenceLedger, *, lock_fd: int, now: Any) -> str:
        assert os.fstat(lock_fd).st_ino
        record_refresh(
            ledger,
            candidate=CurrentObservation(
                observed_at=now, binding=binding, checked_components=tuple(B)
            ),
            now=now,
        )
        return "available"

    monkeypatch.setattr(observer, "refresh_under_lock", refresh)

    def metadata(
        current_site: SiteConfiguration,
        *,
        metadata_only: bool,
        require_snapshot: bool = False,
    ) -> SiteObservation:
        components = binding | {
            B.MODEL_TUPLE: model_tuple_component(current_site.binding)
        }
        return SiteObservation(
            {
                key: value
                for key, value in components.items()
                if key not in {B.IPV4_EGRESS, B.OBSERVER}
            },
            (("metadata", True),),
        )

    monkeypatch.setattr(
        "paper_radar.live_evidence.sealed_runtime.product_observation", metadata
    )
    packets = [0, 0, 0, 0]
    active = []

    def snapshot() -> dict[str, Any]:
        return nft(packets.copy())

    monkeypatch.setattr(observer, "read_nft_snapshot", snapshot)

    def worker(
        current_site: SiteConfiguration,
        root: Path,
        cell: ModelCell | None,
        case_id: str,
        binding_sha: str,
        material_sha: str,
        handler: Callable[[WorkerMessage], None],
    ) -> ModelObservation | NetworkOutcome:
        active.append(case_id)
        if cell is None:
            handler(
                WorkerMessage(
                    case_id=case_id,
                    sequence=1,
                    stage="network",
                    binding_sha256=binding_sha,
                    material_sha256=material_sha,
                    pid=999999,
                    start=100,
                    unit="paperradar-" + "a" * 32 + ".scope",
                )
            )
            packets[NEGATIVES.index(case_id)] += 1
            return NetworkOutcome(attempted=True, response=False)
        stages: tuple[Stage, ...] = ("auth", "prepared", "model")
        for sequence, stage in enumerate(stages, 1):
            handler(
                WorkerMessage(
                    case_id=case_id,
                    sequence=sequence,
                    stage=stage,
                    binding_sha256=binding_sha,
                    material_sha256=material_sha,
                    pid=999999,
                    start=100,
                    unit="paperradar-" + "a" * 32 + ".scope",
                )
            )
        return ModelObservation(
            passed=True,
            authority="read"
            if cell.use_id.startswith("read")
            else "value"
            if cell.use_id.startswith("value")
            else "boundary",
            initialized=True,
            settled=True,
            eof=True,
            terminated=True,
            terminal_clean=True,
            deleted=True,
            input_tokens=5,
            output_tokens=2,
        )

    monkeypatch.setattr("paper_radar.live_evidence.model_ipc.product_worker", worker)
    for path in (
        runtime,
        *runtime.rglob("*"),
        root / "inbox/placement-target-v1.json",
        root / "inbox/site-fixed-round-1.json",
    ):
        path.chmod(0o755 if path.is_dir() else 0o644)
    manifest = manifest.model_copy(
        update={
            "cells": tuple(
                cell.model_copy(
                    update={
                        "binding": binding
                        | {B.MODEL_TUPLE: model_tuple_component(cell.model)}
                    }
                )
                for cell in manifest.cells
            )
        }
    )
    return runtime, ledger, collection, manifest, active
