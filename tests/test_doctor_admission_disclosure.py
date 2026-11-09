"""独立未绑定;准入权威投影的结构化行与中文片段。"""

from datetime import UTC, datetime

from paper_radar.live_evidence.evaluator import evaluate_admission
from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.lifecycle import use_for_id
from paper_radar.live_evidence.registry import INITIAL_REGISTRY
from paper_radar.live_evidence.service import AdmissionProjection
from paper_radar.live_evidence.types import BindingComponent

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def test_empty_report_still_discloses_required_and_unknown_capabilities() -> None:
    from paper_radar.doctor.admission import admission_rows, render_admission_fragment

    decision = evaluate_admission(
        INITIAL_REGISTRY,
        use_for_id("boundary-low"),
        (),
        binding=ExecutionBinding(
            tuple((part, "synthetic") for part in BindingComponent)
        ),
        now=NOW,
    )
    projection = AdmissionProjection(decision, NOW, False)
    rows = admission_rows(projection)
    assert len(rows) == 35
    required = next(row for row in rows if row.capability.value == "cwd_ancestors")
    assert required.result.value == "missing"
    assert required.evidence.value == "unknown"
    disclosed = next(
        row for row in rows if row.capability.value == "pi_public_300_seconds"
    )
    assert disclosed.result.value == "passed"
    assert disclosed.evidence.value == "unknown"
    assert disclosed.original_state is None
    fragment = render_admission_fragment(projection)
    assert "executable=false" in fragment
    assert "capability=pi_public_300_seconds result=passed evidence=unknown" in fragment
    assert "每日五项/全文三项" in fragment


def synthetic_projection(
    *,
    mixed: bool = False,
    pending: bool = False,
    expired: bool = False,
    rollback: bool = False,
) -> AdmissionProjection:
    from datetime import timedelta

    from paper_radar.live_evidence.evidence import CapabilityClaim, CapabilityEvidence
    from paper_radar.live_evidence.types import EvidenceStatus, Requirement

    use = use_for_id("boundary-low")
    binding = ExecutionBinding(tuple((part, "synthetic") for part in BindingComponent))
    records = tuple(
        CapabilityEvidence(
            rule.capability,
            use,
            "live-admission-v1",
            binding,
            CapabilityClaim(
                EvidenceStatus.NOT_ASSESSED
                if rule.requirement is Requirement.DISCLOSURE
                else EvidenceStatus.VERIFIED,
                "自然条件未触发\n原始说明",
                "synthetic boundary-low only",
                None
                if rule.requirement is Requirement.DISCLOSURE
                else NOW - timedelta(days=30 if expired else 1),
                NOW - timedelta(days=1),
            ),
            True,
            True,
            pending and rule.capability.value == "cwd_ancestors",
        )
        for rule in INITIAL_REGISTRY.requirements_for(use)
        if not (mixed and rule.capability.value == "rpc_eof")
    )
    decision = evaluate_admission(
        INITIAL_REGISTRY,
        use,
        records,
        binding=binding,
        now=NOW,
        checked_components=frozenset(BindingComponent),
        ledger_watermark=NOW + timedelta(seconds=1) if rollback else NOW,
    )
    return AdmissionProjection(decision, NOW, pending, ())


def test_healthy_keeps_disclosure_unknown_and_original_not_assessed() -> None:
    from paper_radar.doctor.admission import (
        UsageDisclosure,
        admission_rows,
        render_admission_fragment,
    )

    projection = synthetic_projection()
    assert projection.decision.executable
    rows = admission_rows(projection)
    unknown = next(
        row for row in rows if row.capability.value == "pi_public_300_seconds"
    )
    assert unknown.result.value == "passed"
    assert unknown.evidence.value == "unknown"
    assert unknown.original_state is not None
    assert unknown.original_state.value == "not_assessed"
    assert unknown.basis == "自然条件未触发\n原始说明"
    assert unknown.scope == "synthetic boundary-low only"
    assert unknown.evidence_at == datetime(2026, 11, 8, tzinfo=UTC)
    text = render_admission_fragment(projection, usage=UsageDisclosure(2, 125))
    assert "executable=true" in text
    assert "original_state=not_assessed" in text
    assert "自然条件未触发\\n原始说明" in text
    assert "请求可证下界=2 精确请求数=unknown" in text
    assert "Pi token 用量=125" in text
    assert "缺失或 totalTokens=0 不代表零成本" in text
    assert "capability=ipv6 result=passed" in text


def test_mixed_gap_keeps_original_verified_and_precise_expiry() -> None:
    from paper_radar.doctor.admission import admission_rows, render_admission_fragment

    projection = synthetic_projection(mixed=True, expired=True)
    rows = admission_rows(projection)
    eof = next(row for row in rows if row.capability.value == "rpc_eof")
    assert eof.result.value == "missing"
    identity = next(row for row in rows if row.capability.value == "model_identity")
    assert identity.original_state is not None
    assert identity.original_state.value == "verified"
    assert identity.result.value == "invalid"
    assert identity.expires_at == NOW
    assert identity.expired is True
    assert "evidence_expired" in identity.reasons
    assert "executable=false" in render_admission_fragment(projection)


def test_pending_revocation_retains_activation_and_original_state() -> None:
    from paper_radar.doctor.admission import admission_rows, render_admission_fragment

    projection = synthetic_projection(pending=True)
    row = next(
        row
        for row in admission_rows(projection)
        if row.capability.value == "cwd_ancestors"
    )
    assert row.evidence_active and row.revoked and row.received
    assert row.original_state is not None and row.original_state.value == "verified"
    assert row.result.value == "invalid"
    assert "evidence_revoked" in row.reasons
    assert "pending_revocation=true" in render_admission_fragment(projection)


def test_clock_rollback_global_reason_survives_empty_capability_list() -> None:
    from paper_radar.doctor.admission import render_admission_fragment

    projection = synthetic_projection(rollback=True)
    assert projection.decision.capabilities == ()
    text = render_admission_fragment(projection)
    assert "executable=false reason=clock_rollback" in text
    assert "Pi token 用量=unknown" in text


def test_zero_tokens_stay_unknown_and_request_bounds_keep_provenance() -> None:
    from paper_radar.doctor.admission import UsageDisclosure, render_admission_fragment

    usage = UsageDisclosure(
        2,
        0,
        request_layer="explicit dispatch",
        request_source="synthetic observer",
        request_window="run-1",
    )
    text = render_admission_fragment(synthetic_projection(), usage=usage)
    assert "Pi token 用量=unknown" in text
    assert 'request_layer="explicit dispatch"' in text
    assert 'request_source="synthetic observer"' in text
    assert 'request_window="run-1"' in text
    assert "隐藏重试/预热/刷新" in text


def test_global_ledger_failure_is_invalid_instead_of_not_assessed() -> None:
    from paper_radar.doctor.admission import projection_checks
    from paper_radar.live_evidence.evaluator import AdmissionDecision
    from paper_radar.live_evidence.reasons import AdmissionReason, ReasonCode

    projection = AdmissionProjection(
        AdmissionDecision(
            use_for_id("boundary-low"),
            "live-admission-v1",
            (),
            (AdmissionReason(ReasonCode.LEDGER_UNTRUSTED),),
        ),
        None,
        False,
    )
    checks = projection_checks(projection)
    assert checks[0].result.value == "invalid"
    assert checks[0].reason == "ledger_untrusted"
    assert checks[0].required
    assert checks[1].detail is not None
    assert "executable=false reason=ledger_untrusted" in checks[1].detail


def test_read_fragment_keeps_its_own_scope_and_does_not_borrow_screening() -> None:
    from paper_radar.doctor.admission import admission_rows, render_admission_fragment
    from paper_radar.live_evidence.evidence import CapabilityClaim, CapabilityEvidence
    from paper_radar.live_evidence.types import Capability, EvidenceStatus

    binding = ExecutionBinding(tuple((part, "synthetic") for part in BindingComponent))
    screening_evidence = CapabilityEvidence(
        Capability.CWD_ANCESTORS,
        use_for_id("boundary-low"),
        "live-admission-v1",
        binding,
        CapabilityClaim(EvidenceStatus.VERIFIED, "合成站点观察", "boundary-low", NOW),
        True,
        True,
        False,
    )
    decision = evaluate_admission(
        INITIAL_REGISTRY,
        use_for_id("read-low"),
        (screening_evidence,),
        binding=binding,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    projection = AdmissionProjection(decision, NOW, False)
    row = next(
        row
        for row in admission_rows(projection)
        if row.capability is Capability.CWD_ANCESTORS
    )
    assert row.original_state is None
    assert row.result.value == "missing"
    assert row.reasons == ("evidence_missing",)
    assert "use=read-low call_site=read_execution" in render_admission_fragment(
        projection
    )
