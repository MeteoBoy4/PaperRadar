"""固定模型采集的 root 账本/回执边界;不 receive 或激活。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from paper_radar.live_evidence.collection import (
    CollectionRound,
    ProtectedCollection,
    Reservation,
)
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.model_ipc import WorkerMessage
from paper_radar.live_evidence.model_manifest import ModelCell, ModelManifest
from paper_radar.live_evidence.model_worker import ModelObservation
from paper_radar.live_evidence.receipt import (
    CaseResult,
    EvidenceReceipt,
    ReceiptClaim,
    UseId,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.receipt_v2 import (
    ApprovedPlanV2,
    EvidenceReceiptV2,
    FailureRecordV2,
)
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration, _publish
from paper_radar.live_evidence.types import Capability as C
from paper_radar.live_evidence.types import EvidenceStatus as S
from paper_radar.pi_execution.placement import PlacementTarget

MODEL_CAPABILITIES = (
    C.RPC_COMPLETION,
    C.RPC_EOF,
    C.RPC_TERMINATE,
    C.MODEL_IDENTITY,
    C.SINGLE_DISPATCH,
    C.NO_EXTRA_TURNS,
)


def _complete_and_publish(
    collection: ProtectedCollection,
    receipt: EvidenceReceiptV2,
    prefix: str,
    *,
    now: datetime,
) -> Path:
    digest = content_sha256(receipt)
    pending = collection.ledger.root / f"publish-{digest}.pending"
    _publish(pending, (prefix + "\n").encode())
    collection.complete_round(receipt, now=now)
    source = collection.ledger.root / "inbox" / f"{prefix}-{digest}.json"
    _publish(source, canonical_bytes(receipt))
    _clear_publication(pending)
    return source


def _clear_publication(path: Path) -> None:
    import os

    path.unlink()
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reconcile_publications(
    collection: ProtectedCollection, manifest: ModelManifest
) -> None:
    from paper_radar.live_evidence.ledger import LedgerError

    plans = {cell.plan.plan_id for cell in manifest.cells} | {
        manifest.negative_plan.plan_id
    }
    for receipt in collection.completed_receipts():
        if receipt.plan_id not in plans:
            continue
        digest = content_sha256(receipt)
        prefix = (
            "negative" if receipt.plan_id == manifest.negative_plan.plan_id else "model"
        )
        source = collection.ledger.root / "inbox" / f"{prefix}-{digest}.json"
        pending = collection.ledger.root / f"publish-{digest}.pending"
        if pending.exists():
            collection.ledger._protected(pending)
            if pending.read_bytes() != (prefix + "\n").encode():
                raise LedgerError("source_untrusted")
            if not source.exists():
                _publish(source, canonical_bytes(receipt))
            elif collection.ledger._read_source(source) != canonical_bytes(receipt):
                raise LedgerError("source_untrusted")
            _clear_publication(pending)
        elif collection.ledger._read_source(source) != canonical_bytes(receipt):
            raise LedgerError("source_untrusted")


def complete_model_case(
    collection: ProtectedCollection,
    plan: ApprovedPlanV2,
    run: CollectionRound,
    use_id: UseId,
    observed: ModelObservation,
    reservations: tuple[Reservation, ...],
    *,
    ipv4_verified: bool,
    now: datetime,
) -> Path:
    case_id = run.case_ids[0]
    counts = Counter(item.operation for item in reservations)
    if len(run.case_ids) != 1 or any(
        item.case_id != case_id or item.round_id != run.round_id
        for item in reservations
    ):
        raise ValueError("collector_result_invalid")
    if observed.passed and (
        counts != {"auth": 1, "model": 1}
        or observed.authority != use_id.rsplit("-", 1)[0]
    ):
        raise ValueError("collector_result_invalid")
    claims = tuple(
        ReceiptClaim(
            capability=capability,
            use_id=use_id,
            case_id=case_id,
            status=S.VERIFIED
            if observed.passed and (capability != C.IPV4_EGRESS or ipv4_verified)
            else S.UNKNOWN,
            basis=("site_probe" if capability == C.IPV4_EGRESS else "rpc_probe")
            if observed.passed and (capability != C.IPV4_EGRESS or ipv4_verified)
            else "not_observed",
            scope=("current_site" if capability == C.IPV4_EGRESS else "single_case")
            if observed.passed and (capability != C.IPV4_EGRESS or ipv4_verified)
            else "not_observed",
            verified_at=now
            if observed.passed and (capability != C.IPV4_EGRESS or ipv4_verified)
            else None,
            evidence_at=now,
        )
        for capability in (*MODEL_CAPABILITIES, C.IPV4_EGRESS)
    )
    receipt = EvidenceReceiptV2(
        format_version="v2",
        domain_id="live-177",
        registry_version="live-admission-v1",
        plan_id=plan.plan_id,
        plan_sha256=content_sha256(plan),
        collector_sha256=plan.collector_sha256,
        round_id=run.round_id,
        round_number=run.round_number,
        history_sha256=run.history_sha256,
        prior_receipts=run.prior_receipts,
        reservation_ids=tuple(item.reservation_id for item in reservations),
        started_at=run.started_at,
        completed_at=now,
        binding=run.binding,
        cases=(
            CaseResult(
                case_id=case_id,
                outcome="passed" if observed.passed else "failed",
                auth_calls=counts["auth"],
                model_calls=counts["model"],
                network_requests=counts["network"],
            ),
        ),
        failure_history=()
        if observed.passed
        else (
            FailureRecordV2(
                case_id=case_id, reason=observed.failure or "collector_failed"
            ),
        ),
        claims=claims,
    )
    source = _complete_and_publish(collection, receipt, "model", now=now)
    digest = content_sha256(receipt)
    # 摘要观测是披露,不扩展已冻结 v2 receipt wire;不保存原文/自由错误。
    _publish(
        collection.ledger.root / "inbox" / f"model-{digest}-observation.json",
        canonical_bytes(observed),
    )
    import json

    _publish(
        collection.ledger.root / "inbox" / f"model-{digest}-accounting.json",
        (
            json.dumps(
                {
                    "auth_cli_lower_bound": counts["auth"],
                    "prompt_lower_bound": counts["model"],
                    "observation_layer": "product_rpc_and_protected_reservations",
                    "exact_provider_requests": "unknown",
                    "hidden_calls": "unknown",
                    "session_full_history": "not_assessed",
                },
                sort_keys=True,
            )
            + "\n"
        ).encode(),
    )
    return source


def read_manifest(root: Path, ledger: EvidenceLedger) -> ModelManifest:
    """仅受保护固定入口调用,检查完整材料库存与所有者来源声明。"""
    import hashlib

    from paper_radar.live_evidence.model_manifest import ModelManifest
    from paper_radar.live_evidence.protected_observer import _protected_bytes
    from paper_radar.pi_execution.site_binding import component_digest

    raw = _protected_bytes(ledger, root / "model-manifest.json")
    manifest = ModelManifest.model_validate_json(raw)
    if canonical_bytes(manifest) != raw:
        raise ValueError("collector_manifest_invalid")
    actual = {
        str(path.relative_to(root))
        for path in (root / "materials").rglob("*")
        if not path.is_dir() or path.is_symlink()
    }
    if actual != set(manifest.members):
        raise ValueError("collector_members_invalid")
    for name, digest in manifest.members.items():
        if hashlib.sha256(_protected_bytes(ledger, root / name)).hexdigest() != digest:
            raise ValueError("collector_material_invalid")
    for cell in manifest.cells:
        selected = {
            name: digest
            for name, digest in manifest.members.items()
            if name.startswith(f"materials/{cell.use_id}/")
        }
        if not selected or component_digest(selected) != cell.material_sha256:
            raise ValueError("collector_material_invalid")
    confirmation = _protected_bytes(ledger, root / "network-owner-confirmation.json")
    if (
        hashlib.sha256(confirmation).hexdigest()
        != manifest.network.owner_confirmation_sha256
    ):
        raise ValueError("collector_network_invalid")
    return manifest


def site_prerequisite(
    root: Path,
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    cell: ModelCell,
    *,
    now: datetime,
) -> EvidenceReceipt:
    """已批准受保护站点完成源;不要求owner预先receive/activate。"""
    from paper_radar.live_evidence.collector import _SITE_DEPENDENCIES, SITE_CASES
    from paper_radar.live_evidence.receipt import (
        ApprovedPlan,
        EvidenceReceipt,
        validate_against_plan,
    )

    plan = ledger.show_plan(manifest.site_plan_id)
    if (
        content_sha256(plan) != manifest.site_plan_sha256
        or plan.kind != "site_beta"
        or plan.cases != SITE_CASES
    ):
        raise ValueError("collector_site_missing")
    raw = ledger._read_source(ledger.root / "inbox" / f"{plan.plan_id}-round-1.json")
    receipt = EvidenceReceipt.model_validate_json(raw)
    if not isinstance(plan, ApprovedPlan):
        raise ValueError("collector_site_missing")
    validate_against_plan(receipt, plan, now=now)
    if (
        canonical_bytes(receipt) != raw
        or receipt.failure_history
        or tuple(case.case_id for case in receipt.cases if case.outcome == "passed")
        != SITE_CASES
    ):
        raise ValueError("collector_site_missing")
    for capability, dependencies in _SITE_DEPENDENCIES.items():
        matching = [
            claim
            for claim in receipt.claims
            if claim.use_id == cell.use_id
            and claim.capability == capability
            and claim.status == S.VERIFIED
            and claim.basis == "site_probe"
            and claim.scope == "current_site"
        ]
        if len(matching) != 1 or any(
            receipt.binding[part] != cell.binding[part] for part in dependencies
        ):
            raise ValueError("collector_site_missing")
    if (
        now < receipt.completed_at
        or (now - receipt.completed_at).total_seconds() > 30 * 86400
    ):
        raise ValueError("collector_site_missing")
    return receipt


def _current(
    root: Path,
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    cell: ModelCell,
    site: SiteConfiguration,
    lock_fd: int,
    *,
    now: datetime,
) -> None:
    from paper_radar.live_evidence.observation import (
        load_current_observation,
        load_refresh_status,
    )
    from paper_radar.live_evidence.protected_observer import refresh_under_lock
    from paper_radar.live_evidence.sealed_runtime import product_observation
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.llm.dispatch import DispatchDenied

    try:
        refresh = refresh_under_lock(root, ledger, lock_fd=lock_fd, now=now)
        if refresh != "available":
            raise DispatchDenied(
                "identity_mismatch"
                if refresh == "observation_drift"
                else "source_untrusted"
                if refresh == "source_untrusted"
                else "resource_unavailable"
            )
        observation = load_current_observation(ledger, now=now)
        observation.validate_current(load_refresh_status(ledger), now=now)
        observed = product_observation(
            site.model_copy(update={"binding": cell.model, "use_id": cell.use_id}),
            metadata_only=True,
            require_snapshot=True,
        )
        components = observation.binding | observed.components
        if (
            observed.failure is not None
            or not observed.checks
            or observed.checks[0] != ("metadata", True)
        ):
            raise DispatchDenied(
                "identity_mismatch"
                if observed.failure == "binding_observation_unavailable"
                else "resource_unavailable"
            )
        if components != cell.binding or not {B.IPV4_EGRESS, B.OBSERVER} <= set(
            observation.checked_components
        ):
            raise DispatchDenied("identity_mismatch")
        if not manifest.network.starts_at <= now <= manifest.network.ends_at:
            raise DispatchDenied("resource_unavailable")
        site_prerequisite(root, ledger, manifest, cell, now=now)
    except DispatchDenied:
        raise
    except Exception:
        raise DispatchDenied("source_untrusted") from None


def _target(ledger: EvidenceLedger) -> PlacementTarget:
    from paper_radar.pi_execution.placement import TARGET_FILENAME, PlacementTarget

    return PlacementTarget.model_validate_json(
        ledger._read_source(ledger.root / "inbox" / TARGET_FILENAME)
    )


def _stop_placed(targets: list[tuple[int, int, int]]) -> None:
    """只回收曾经由root核验的固定放置进程组,PID复用则不碰。"""
    import os
    import signal

    from paper_radar.pi_execution.placement import _proc

    for pid, start, group in targets:
        try:
            if _proc(pid)[0] == start and os.getpgid(pid) == group and group > 1:
                os.killpg(group, signal.SIGKILL)
        except (OSError, ValueError):
            pass


def _run_model(
    root: Path,
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    cell: ModelCell,
    site: SiteConfiguration,
    collection: ProtectedCollection,
    lock_fd: int,
    clock: Callable[[], datetime],
) -> bool:
    import os

    from paper_radar.live_evidence.model_ipc import product_worker
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.llm.dispatch import DispatchDenied
    from paper_radar.pi_execution.placement import verify_placement
    from paper_radar.pi_execution.site_binding import component_digest

    now = clock()
    _current(root, ledger, manifest, cell, site, lock_fd, now=now)
    if collection.completed_case(cell.plan.cases[0], binding=cell.binding) is not None:
        return True
    run = collection.start_round(cell.plan.plan_id, binding=cell.binding, now=now)
    reservations = []
    stages: list[str] = []
    targets: list[tuple[int, int, int]] = []

    def gate(message: WorkerMessage) -> None:
        expected = ("auth", "prepared", "model")
        if len(stages) >= 3 or message.stage != expected[len(stages)]:
            raise DispatchDenied("source_untrusted")
        target = _target(ledger)
        verify_placement(target, message.pid, message.start, message.unit)
        targets.append((message.pid, message.start, os.getpgid(message.pid)))
        _current(root, ledger, manifest, cell, site, lock_fd, now=clock())
        if message.stage != "prepared":
            try:
                reservations.append(
                    collection.reserve(
                        run.round_id,
                        run.case_ids[0],
                        "auth" if message.stage == "auth" else "model",
                        now=clock(),
                    )
                )
            except Exception:
                raise DispatchDenied("resource_unavailable") from None
        stages.append(message.stage)

    try:
        observed = product_worker(
            site,
            root,
            cell,
            run.case_ids[0],
            component_digest(cell.binding),
            cell.material_sha256,
            gate,
        )
        if not isinstance(observed, ModelObservation):
            raise DispatchDenied("source_untrusted")
        if observed.passed and stages != ["auth", "prepared", "model"]:
            raise DispatchDenied("source_untrusted")
        if observed.passed:
            try:
                _current(root, ledger, manifest, cell, site, lock_fd, now=clock())
            except DispatchDenied as error:
                observed = observed.model_copy(
                    update={"passed": False, "failure": error.reason}
                )
        if not reservations:
            collection.cancel_round(run.round_id, now=clock())
            return False
        source = complete_model_case(
            collection,
            cell.plan,
            run,
            cell.use_id,
            observed,
            tuple(reservations),
            ipv4_verified=True,
            now=clock(),
        )
        # 复合出网来源:四个root完成源+所有者确认+本次权威成功;不是仅RPC成功。
        import json

        from paper_radar.live_evidence.model_manifest import NEGATIVES

        negatives = [
            collection.completed_case(case, binding=manifest.cells[0].binding)
            for case in NEGATIVES
        ]
        if any(receipt is None for receipt in negatives):
            raise DispatchDenied("source_untrusted")
        provenance = {
            "negative_receipts": [
                content_sha256(receipt) for receipt in negatives if receipt is not None
            ],
            "owner_confirmation_sha256": manifest.network.owner_confirmation_sha256,
            "egress_digest": run.binding[B.IPV4_EGRESS],
            "model_source": source.name,
            "site_receipt_sha256": content_sha256(
                site_prerequisite(root, ledger, manifest, cell, now=clock())
            ),
        }
        _publish(
            source.with_name(source.stem + "-sources.json"),
            (json.dumps(provenance, sort_keys=True) + "\n").encode(),
        )
        return observed.passed
    except BaseException:
        _stop_placed(targets)
        # 消费后的未知不能退款或伪装空轮;中断恢复安全首停。
        if reservations:
            collection.recover_interrupted(now=clock())
        else:
            collection.cancel_round(run.round_id, now=clock())
        raise


def _run_negatives(
    root: Path,
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    site: SiteConfiguration,
    collection: ProtectedCollection,
    lock_fd: int,
    clock: Callable[[], datetime],
) -> bool:
    import os

    from paper_radar.live_evidence.model_ipc import product_worker
    from paper_radar.live_evidence.model_manifest import NEGATIVES
    from paper_radar.live_evidence.network_collection import (
        NetworkOutcome,
        exclusive_probe,
        verify_counter_change,
    )
    from paper_radar.live_evidence.protected_observer import (
        egress_identity,
        read_nft_snapshot,
    )
    from paper_radar.llm.dispatch import DispatchDenied
    from paper_radar.pi_execution.site_binding import component_digest

    cell = manifest.cells[0]
    _current(root, ledger, manifest, cell, site, lock_fd, now=clock())
    if all(
        collection.completed_case(case, binding=cell.binding) is not None
        for case in NEGATIVES
    ):
        return True
    plan = manifest.negative_plan
    run = collection.start_round(plan.plan_id, binding=cell.binding, now=clock())
    reservations = []
    cases = []
    targets: list[tuple[int, int, int]] = []
    failure = None
    try:
        for case_id in run.case_ids:
            before = None
            rule_handle = None
            attributable = False
            target = _target(ledger)

            def gate(
                message: WorkerMessage,
                target: PlacementTarget = target,
                case_id: str = case_id,
            ) -> None:
                nonlocal before, attributable, rule_handle
                if message.stage != "network" or before is not None:
                    raise DispatchDenied("source_untrusted")
                _current(root, ledger, manifest, cell, site, lock_fd, now=clock())
                attributable = exclusive_probe(
                    target, message.pid, message.start, message.unit
                )
                if not attributable:
                    raise DispatchDenied("resource_unavailable")
                targets.append((message.pid, message.start, os.getpgid(message.pid)))
                before = read_nft_snapshot()
                if egress_identity(before, target) != target.egress_digest:
                    raise DispatchDenied("identity_mismatch")
                from paper_radar.live_evidence.network_collection import (
                    negative_rule_handle,
                )

                rule_handle = negative_rule_handle(
                    before, manifest.network.rule_comments[NEGATIVES.index(case_id)]
                )
                if rule_handle is None:
                    raise DispatchDenied("resource_unavailable")
                try:
                    reservations.append(
                        collection.reserve(
                            run.round_id, case_id, "network", now=clock()
                        )
                    )
                except Exception:
                    raise DispatchDenied("resource_unavailable") from None

            outcome = product_worker(
                site,
                root,
                None,
                case_id,
                component_digest(cell.binding),
                manifest.network.owner_confirmation_sha256,
                gate,
            )
            if not isinstance(outcome, NetworkOutcome):
                raise DispatchDenied("source_untrusted")
            after = read_nft_snapshot()
            from paper_radar.live_evidence.network_collection import idle_probe_scope

            attributable &= idle_probe_scope(target)
            passed = bool(
                outcome.attempted
                and not outcome.response
                and before is not None
                and rule_handle is not None
                and verify_counter_change(
                    before,
                    after,
                    handle=rule_handle,
                    attributable=attributable,
                )
                and egress_identity(after, target) == target.egress_digest
            )
            if not passed:
                failure = FailureRecordV2(
                    case_id=case_id,
                    reason="isolation_failed"
                    if outcome.response
                    else "resource_unavailable",
                )
            cases.append(
                CaseResult(
                    case_id=case_id,
                    outcome="passed" if passed else "failed",
                    auth_calls=0,
                    model_calls=0,
                    network_requests=sum(
                        item.case_id == case_id for item in reservations
                    ),
                )
            )
            if failure is not None:
                break
        now = clock()
        if not reservations:
            collection.cancel_round(run.round_id, now=now)
            return False
        receipt = EvidenceReceiptV2(
            format_version="v2",
            domain_id="live-177",
            registry_version="live-admission-v1",
            plan_id=plan.plan_id,
            plan_sha256=content_sha256(plan),
            collector_sha256=plan.collector_sha256,
            round_id=run.round_id,
            round_number=run.round_number,
            history_sha256=run.history_sha256,
            prior_receipts=run.prior_receipts,
            reservation_ids=tuple(item.reservation_id for item in reservations),
            started_at=run.started_at,
            completed_at=now,
            binding=run.binding,
            cases=tuple(cases),
            failure_history=() if failure is None else (failure,),
            claims=(
                ReceiptClaim(
                    capability=C.IPV4_EGRESS,
                    use_id=cell.use_id,
                    case_id=cases[-1].case_id,
                    status=S.UNKNOWN,
                    basis="not_observed",
                    scope="not_observed",
                    verified_at=None,
                    evidence_at=now,
                ),
            ),
        )
        _complete_and_publish(collection, receipt, "negative", now=now)
        return failure is None
    except BaseException:
        _stop_placed(targets)
        if reservations:
            collection.recover_interrupted(now=clock())
        else:
            collection.cancel_round(run.round_id, now=clock())
        raise


def bind_collection_site(
    root: Path,
    ledger: EvidenceLedger,
    manifest: ModelManifest,
    collection: ProtectedCollection,
    lock_fd: int,
    *,
    now: datetime,
) -> ModelManifest:
    """严格站点完成源与当前root观察决定运行绑定,不把部署后事实静态封入包。"""
    import hashlib
    import json

    from paper_radar.live_evidence.observation import load_current_observation
    from paper_radar.live_evidence.protected_observer import refresh_under_lock
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.llm.dispatch import DispatchDenied
    from paper_radar.pi_execution.current_binding import model_tuple_component

    result = refresh_under_lock(root, ledger, lock_fd=lock_fd, now=now)
    if result != "available":
        raise DispatchDenied(
            "identity_mismatch"
            if result == "observation_drift"
            else "source_untrusted"
            if result == "source_untrusted"
            else "resource_unavailable"
        )
    observation = load_current_observation(ledger, now=now)
    if not {B.OBSERVER, B.IPV4_EGRESS} <= set(observation.checked_components):
        raise DispatchDenied("source_untrusted")
    target = _target(ledger)
    if target.egress_digest != observation.binding[B.IPV4_EGRESS]:
        raise DispatchDenied("identity_mismatch")
    cells = []
    site_source = None
    for cell in manifest.cells:
        binding = observation.binding | {
            B.MODEL_TUPLE: model_tuple_component(cell.model)
        }
        if any(binding[part] != value for part, value in cell.binding.items()):
            raise DispatchDenied("identity_mismatch")
        bound = cell.model_copy(update={"binding": binding})
        try:
            site_source = site_prerequisite(root, ledger, manifest, bound, now=now)
        except (ValueError, LedgerError):
            raise DispatchDenied("source_untrusted") from None
        cells.append(bound)
    assert site_source is not None
    manifest_sha = content_sha256(manifest)
    enrollment = {
        "format_version": 1,
        "manifest_sha256": manifest_sha,
        "site_receipt_sha256": content_sha256(site_source),
        "target_sha256": hashlib.sha256(canonical_bytes(target)).hexdigest(),
        "owner_confirmation_sha256": manifest.network.owner_confirmation_sha256,
        "bindings": {cell.use_id: cell.binding for cell in cells},
    }
    raw = (
        json.dumps(enrollment, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    source = ledger.root / "inbox" / f"collection-bindings-{manifest_sha}.json"
    if source.exists():
        if ledger._read_source(source) != raw:
            raise DispatchDenied("identity_mismatch")
    else:
        plans = {cell.plan.plan_id for cell in cells} | {manifest.negative_plan.plan_id}
        if any(receipt.plan_id in plans for receipt in collection.completed_receipts()):
            raise DispatchDenied("source_untrusted")
        _publish(source, raw)
    return manifest.model_copy(update={"cells": tuple(cells)})


def collect_models_once(
    root: Path, ledger: EvidenceLedger, *, clock: Callable[[], datetime] | None = None
) -> tuple[str, ...]:
    """固定零参数入口的实现;整组独占同一181锁,不部署、不批准。"""
    from datetime import UTC

    from paper_radar.live_evidence.protected_observer import protected_collection_lock
    from paper_radar.live_evidence.sealed_runtime import _read_configuration

    if clock is None:

        def clock() -> datetime:
            return datetime.now(UTC)

    ledger._writer()
    ledger._protected(root)
    with protected_collection_lock(ledger) as lock_fd:
        manifest = read_manifest(root, ledger)
        site = _read_configuration(root)
        if site.snapshot_id != manifest.actual_snapshot_id or any(
            (
                cell.model.supply_id,
                cell.model.install_id,
                cell.model.launch_policy_version,
                cell.model.isolation_policy_version,
                cell.model.auth_mode,
                cell.model.proxy,
            )
            != (
                site.binding.supply_id,
                site.binding.install_id,
                site.binding.launch_policy_version,
                site.binding.isolation_policy_version,
                site.binding.auth_mode,
                site.binding.proxy,
            )
            for cell in manifest.cells
        ):
            raise ValueError("collector_manifest_invalid")
        collection = ProtectedCollection(ledger)
        # 初始化/approve均属于所有者;缺谱系或批准就拒绝。
        for plan in (
            *tuple(cell.plan for cell in manifest.cells),
            manifest.negative_plan,
        ):
            if not plan.starts_at <= clock() <= plan.ends_at:
                raise ValueError("plan_window_invalid")
            if canonical_bytes(ledger.show_plan(plan.plan_id)) != canonical_bytes(plan):
                raise ValueError("collector_plan_invalid")
        collection.recover_interrupted(now=clock())
        _reconcile_publications(collection, manifest)
        if collection.status(manifest.cells[0].plan.plan_id, now=clock()).stopped:
            from paper_radar.live_evidence.ledger import LedgerError

            raise LedgerError("plan_stopped")
        manifest = bind_collection_site(
            root, ledger, manifest, collection, lock_fd, now=clock()
        )
        if not _run_negatives(root, ledger, manifest, site, collection, lock_fd, clock):
            return ()
        passed = []
        for cell in manifest.cells:
            if not _run_model(
                root, ledger, manifest, cell, site, collection, lock_fd, clock
            ):
                break
            passed.append(cell.use_id)
        return tuple(passed)


def model_collector_main(arguments: list[str] | None = None) -> int:
    import sys

    from paper_radar.live_evidence.ledger import EvidenceLedger
    from paper_radar.live_evidence.sealed_runtime import RUNTIME_ROOT

    args = sys.argv[1:] if arguments is None else arguments
    if args:
        return 2
    try:
        passed = collect_models_once(RUNTIME_ROOT, EvidenceLedger())
        print(
            f"模型采集已完成格数={len(passed)};未接收、未激活;请所有者审阅受保护历史。"
        )
        return 0 if len(passed) == 6 else 2
    except Exception:
        print(
            "模型采集拒绝 [collector_unavailable];"
            "请核对封印计划、站点前置与受保护历史。",
            file=sys.stderr,
        )
        return 2
