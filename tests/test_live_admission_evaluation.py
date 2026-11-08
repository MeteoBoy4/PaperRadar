"""公开纯判定边界:三态、资格、期限及材料分层各自成立。"""

from dataclasses import replace

import pytest

from paper_radar.live_evidence.evaluator import evaluate_admission
from paper_radar.live_evidence.evidence import Applicability, ExecutionBinding
from paper_radar.live_evidence.registry import INITIAL_REGISTRY
from paper_radar.live_evidence.types import BindingComponent, Capability, EvidenceStatus
from tests.live_admission_support import BINDING, NOW, USE, item, records


def test_required_gap_refuses_without_promoting_disclosures_or_not_applicable() -> None:
    evidence = records()
    current = item(evidence, Capability.CWD_ANCESTORS)
    gap = replace(
        current,
        claim=replace(current.claim, status=EvidenceStatus.UNKNOWN, verified_at=None),
    )
    evidence = tuple(gap if record is current else record for record in evidence)
    result = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assert result.executable is False
    assert [reason.token for reason in result.reasons] == [
        "capability_required:cwd_ancestors"
    ]
    assert result.for_capability(Capability.CWD_ANCESTORS).claim == gap.claim
    disclosed = result.for_capability(Capability.AUTH_CACHE_HISTORY)
    assert disclosed.disclosure_unknown is True
    assert disclosed.claim == item(evidence, Capability.AUTH_CACHE_HISTORY).claim
    not_applicable = result.for_capability(Capability.EXTERNAL_INTERRUPT)
    assert not_applicable.reasons == ()
    assert not_applicable.claim == item(evidence, Capability.EXTERNAL_INTERRUPT).claim
    assert not_applicable.claim is not None
    assert not_applicable.claim.status is EvidenceStatus.NOT_ASSESSED
    assert not_applicable.claim.verified_at is None
    assert all(record.claim.basis == "synthetic basis" for record in evidence)


def test_provider_expiry_uses_original_time_even_when_activated_on_day_29() -> None:
    from datetime import timedelta

    from tests.live_admission_support import VERIFIED_AT

    evidence = records()
    deadline = VERIFIED_AT + timedelta(days=30)
    before = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=deadline - timedelta(microseconds=1),
        checked_components=frozenset(BindingComponent),
    )
    after = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=deadline,
        checked_components=frozenset(BindingComponent),
    )
    assert before.executable is True
    assert before.for_capability(Capability.MODEL_IDENTITY).expires_at == deadline
    assert after.executable is False
    expired = after.for_capability(Capability.MODEL_IDENTITY)
    assert expired.expired is True
    assert [reason.token for reason in expired.reasons] == ["evidence_expired"]
    assert expired.claim == item(evidence, Capability.MODEL_IDENTITY).claim
    day_29 = VERIFIED_AT + timedelta(days=29)
    activated = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=day_29,
        checked_components=frozenset(BindingComponent),
    ).for_capability(Capability.MODEL_IDENTITY)
    assert activated.expires_at is not None
    assert activated.expires_at - day_29 == timedelta(days=1)


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("naive_now", "evidence_time_invalid"),
        ("naive_verified", "evidence_time_invalid"),
        ("future_verified", "evidence_time_future"),
        ("future_observation", "evidence_time_future"),
        ("missing_verified", "evidence_time_invalid"),
        ("unknown_verified", "evidence_time_invalid"),
        ("naive_watermark", "evidence_time_invalid"),
        ("rollback", "clock_rollback"),
    ],
)
def test_invalid_times_and_ledger_watermark_fail_closed(
    case: str, expected: str
) -> None:
    from datetime import timedelta

    evidence = records()
    current = item(evidence, Capability.MODEL_IDENTITY)
    now = NOW.replace(tzinfo=None) if case == "naive_now" else NOW
    watermark = NOW + timedelta(microseconds=1) if case == "rollback" else NOW
    if case == "naive_watermark":
        watermark = NOW.replace(tzinfo=None)
    claim = current.claim
    if case == "naive_verified":
        claim = replace(claim, verified_at=NOW.replace(tzinfo=None))
    if case == "future_verified":
        claim = replace(claim, verified_at=NOW + timedelta(microseconds=1))
    if case == "future_observation":
        claim = replace(claim, evidence_at=NOW + timedelta(microseconds=1))
    if case == "missing_verified":
        claim = replace(claim, verified_at=None)
    if case == "unknown_verified":
        claim = replace(claim, status=EvidenceStatus.UNKNOWN)
    evidence = tuple(
        replace(record, claim=claim) if record is current else record
        for record in evidence
    )
    result = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=now,
        ledger_watermark=watermark,
        checked_components=frozenset(BindingComponent),
    )
    assert result.executable is False
    assert expected in {reason.token for reason in result.reasons}


@pytest.mark.parametrize(
    ("case", "capability", "expected"),
    [
        ("uncovered", Capability.CWD_ANCESTORS, "coverage_incomplete"),
        ("uncovered", Capability.LAUNCH_POLICY, "coverage_incomplete"),
        ("bounded", Capability.CWD_ANCESTORS, None),
        ("bounded_expired", Capability.CWD_ANCESTORS, "evidence_expired"),
        ("privileged", Capability.IPV4_EGRESS, None),
        ("full", Capability.LAUNCH_POLICY, None),
    ],
)
def test_site_and_engineering_lifetime_requires_coverage_bound_or_privileged_proof(
    case: str,
    capability: Capability,
    expected: str | None,
) -> None:
    from datetime import timedelta

    from tests.live_admission_support import VERIFIED_AT

    entry = INITIAL_REGISTRY.uses[0]
    rule = next(rule for rule in entry.requirements if rule.capability is capability)
    registry = INITIAL_REGISTRY
    if case.startswith("bounded"):
        from paper_radar.live_evidence.registry import AdmissionRegistry

        bounded = replace(rule, maximum_age_days=2)
        registry = AdmissionRegistry(
            INITIAL_REGISTRY.version,
            (
                replace(
                    entry,
                    requirements=tuple(
                        bounded if r is rule else r for r in entry.requirements
                    ),
                ),
            ),
        )
    checked = frozenset(BindingComponent) - rule.dependencies
    if case == "full":
        checked = frozenset(BindingComponent)
    proof = rule.dependencies if case == "privileged" else frozenset()
    now = VERIFIED_AT + timedelta(days=2) if case == "bounded_expired" else NOW
    result = evaluate_admission(
        registry,
        USE,
        records(),
        binding=BINDING,
        now=now,
        checked_components=checked,
        privileged_components=proof,
    ).for_capability(capability)
    assert [reason.token for reason in result.reasons] == (
        [] if expected is None else [expected]
    )
    if case.startswith("bounded"):
        assert result.expires_at == VERIFIED_AT + timedelta(days=2)
    elif case in {"full", "privileged"}:
        assert result.expires_at is None


def test_registry_upgrade_and_material_binding_do_not_expand_activation() -> None:
    from paper_radar.live_evidence.registry import AdmissionRegistry

    evidence = records()
    upgraded = replace(INITIAL_REGISTRY, version="live-admission-v2")
    denied = evaluate_admission(
        upgraded,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assert denied.executable is False
    assert {reason.token for reason in denied.reasons} == {"registry_version_mismatch"}
    assert all(
        assessment.applicability is Applicability.APPLICABLE
        for assessment in denied.capabilities
    )
    ordinary = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        material_identity="real-material-v2",
        checked_components=frozenset(BindingComponent),
    )
    assert ordinary.executable is True
    entry = INITIAL_REGISTRY.uses[0]
    dependent = AdmissionRegistry(
        INITIAL_REGISTRY.version,
        (
            replace(
                entry,
                requirements=tuple(
                    replace(rule, material_dependent=True)
                    if rule.capability is Capability.MODEL_IDENTITY
                    else rule
                    for rule in entry.requirements
                ),
            ),
        ),
    )
    denied = evaluate_admission(
        dependent,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        material_identity="real-material-v2",
        checked_components=frozenset(BindingComponent),
    )
    assert [
        reason.token
        for reason in denied.for_capability(Capability.MODEL_IDENTITY).reasons
    ] == ["material_mismatch"]
    bound = tuple(
        replace(record, material_identity="real-material-v2") for record in evidence
    )
    assert (
        evaluate_admission(
            dependent,
            USE,
            bound,
            binding=BINDING,
            now=NOW,
            material_identity="real-material-v2",
            checked_components=frozenset(BindingComponent),
        ).executable
        is True
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_duplicate_claims_are_rejected_independent_of_order(
    reverse: bool,
) -> None:
    evidence = records()
    conflict = replace(item(evidence, Capability.MODEL_IDENTITY), revoked=True)
    combined = (conflict, *evidence) if reverse else (*evidence, conflict)
    result = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        combined,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assert result.executable is False
    assert [reason.token for reason in result.reasons] == ["evidence_conflict"]


def test_other_consumer_cells_are_not_borrowed_and_do_not_hide_the_matching_cell() -> (
    None
):
    other_use = INITIAL_REGISTRY.uses[-1].use
    other = records(other_use)
    denied = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        other,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assert denied.executable is False
    assert {reason.token for reason in denied.reasons} == {"evidence_missing"}
    assert all(item.claim is None for item in denied.capabilities)
    assert (
        evaluate_admission(
            INITIAL_REGISTRY,
            USE,
            other + records(),
            binding=BINDING,
            now=NOW,
            checked_components=frozenset(BindingComponent),
        ).executable
        is True
    )


@pytest.mark.parametrize("component", list(BindingComponent))
def test_each_execution_component_drift_is_controlled_and_keeps_original_claims(
    component: BindingComponent,
) -> None:
    evidence = records()
    changed = ExecutionBinding(
        tuple(
            (name, "changed" if name is component else value)
            for name, value in BINDING.components
        )
    )
    result = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=changed,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assert result.executable is False
    assert f"binding_drift:{component.value}" in {
        reason.token for reason in result.reasons
    }
    for record in evidence:
        assert result.for_capability(record.capability).claim == record.claim
    unaffected = next(
        rule
        for rule in INITIAL_REGISTRY.uses[0].requirements
        if component not in rule.dependencies and rule.requirement.value == "required"
    )
    assert result.for_capability(unaffected.capability).qualified is True
    for rule in INITIAL_REGISTRY.requirements_for(USE):
        assessment = result.for_capability(rule.capability)
        if component in rule.dependencies:
            assert assessment.applicability is Applicability.NOT_APPLICABLE
        else:
            assert (
                assessment.applicability
                is item(evidence, rule.capability).applicability
            )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("received", False, "evidence_not_received"),
        ("evidence_active", False, "evidence_not_activated"),
        ("revoked", True, "evidence_revoked"),
    ],
)
def test_qualification_dimensions_do_not_rewrite_verified_history(
    field: str,
    value: bool,
    reason: str,
) -> None:
    current = item(records(), Capability.CWD_ANCESTORS)
    if field == "received":
        changed = replace(current, received=value)
    elif field == "evidence_active":
        changed = replace(current, evidence_active=value)
    else:
        changed = replace(current, revoked=value)
    evidence = tuple(
        changed if record.capability is current.capability else record
        for record in records()
    )
    result = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    ).for_capability(current.capability)
    assert [r.token for r in result.reasons] == [reason]
    assert result.claim == current.claim
    assert result.claim is not None
    assert result.claim.status is EvidenceStatus.VERIFIED
    assert result.applicability is Applicability.APPLICABLE


def test_unknown_applicability_and_missing_required_fact_refuse_without_inference() -> (
    None
):
    current = item(records(), Capability.IPV4_EGRESS)
    evidence = tuple(
        replace(record, applicability=Applicability.UNKNOWN)
        if record.capability is current.capability
        else record
        for record in records()
    )
    assessment = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    ).for_capability(current.capability)
    assert [reason.token for reason in assessment.reasons] == [
        "evidence_applicability_unknown"
    ]
    assert assessment.claim == current.claim
    missing = tuple(
        record for record in records() if record.capability is not current.capability
    )
    assessment = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        missing,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    ).for_capability(current.capability)
    assert [reason.token for reason in assessment.reasons] == ["evidence_missing"]
    assert assessment.claim is None


def test_disclosed_verified_fact_keeps_its_binding_without_blocking() -> None:
    from tests.live_admission_support import VERIFIED_AT

    evidence = records()
    record = item(evidence, Capability.DATE_ALIAS)
    altered = replace(
        record,
        claim=replace(
            record.claim,
            status=EvidenceStatus.VERIFIED,
            verified_at=VERIFIED_AT,
        ),
    )
    changed_binding = ExecutionBinding(
        tuple(
            (
                component,
                "other-model" if component is BindingComponent.MODEL_TUPLE else value,
            )
            for component, value in BINDING.components
        )
    )
    altered = replace(altered, binding=changed_binding)
    evidence = tuple(altered if entry is record else entry for entry in evidence)
    decision = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assert decision.executable is True
    assessment = decision.for_capability(Capability.DATE_ALIAS)
    assert assessment.disclosure_unknown is True
    assert [reason.token for reason in assessment.reasons] == [
        "binding_drift:model_tuple"
    ]
    assert assessment.claim == altered.claim


@pytest.mark.parametrize(
    "capability", [Capability.DATE_ALIAS, Capability.EXTERNAL_INTERRUPT]
)
def test_future_times_are_invalid_input_even_for_nonrequired_capabilities(
    capability: Capability,
) -> None:
    from datetime import timedelta

    record = item(records(), capability)
    evidence = tuple(
        replace(
            entry,
            claim=replace(
                entry.claim,
                evidence_at=NOW + timedelta(microseconds=1),
            ),
        )
        if entry.capability is record.capability
        else entry
        for entry in records()
    )
    result = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assert result.executable is False
    assert [reason.token for reason in result.reasons] == ["evidence_time_future"]


@pytest.mark.parametrize(
    ("capability", "component"),
    [
        (Capability.CWD_ANCESTORS, BindingComponent.CWD_ANCESTORS),
        (Capability.DATE_ALIAS, BindingComponent.MODEL_TUPLE),
    ],
)
@pytest.mark.parametrize(
    ("original", "drifted", "expected"),
    [
        (Applicability.APPLICABLE, False, Applicability.APPLICABLE),
        (Applicability.APPLICABLE, True, Applicability.NOT_APPLICABLE),
        (Applicability.UNKNOWN, False, Applicability.UNKNOWN),
        (Applicability.UNKNOWN, True, Applicability.NOT_APPLICABLE),
        (Applicability.NOT_APPLICABLE, False, Applicability.NOT_APPLICABLE),
        (Applicability.NOT_APPLICABLE, True, Applicability.NOT_APPLICABLE),
    ],
)
def test_current_applicability_accounts_for_drift_without_changing_source_facts(
    capability: Capability,
    component: BindingComponent,
    original: Applicability,
    drifted: bool,
    expected: Applicability,
) -> None:
    changed = ExecutionBinding(
        tuple(
            (name, "changed" if drifted and name is component else value)
            for name, value in BINDING.components
        )
    )
    evidence = tuple(
        replace(record, applicability=original, binding=changed)
        if record.capability is capability
        else record
        for record in records()
    )
    decision = evaluate_admission(
        INITIAL_REGISTRY,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    assessment = decision.for_capability(capability)
    source = item(evidence, capability)
    assert assessment.applicability is expected
    assert source.applicability is original
    assert assessment.claim == source.claim
    assert assessment.received is True
    assert assessment.evidence_active is True
    assert assessment.revoked is False
    if drifted:
        assert f"binding_drift:{component.value}" in {
            reason.token for reason in assessment.reasons
        }
        assert assessment.qualified is False
        if capability is Capability.CWD_ANCESTORS:
            assert decision.executable is False
        else:
            assert decision.executable is True
            assert assessment.disclosure_unknown is True
    unaffected = decision.for_capability(Capability.AUTH_CACHE_CURRENT)
    assert unaffected.applicability is Applicability.APPLICABLE
    assert unaffected.claim == item(evidence, Capability.AUTH_CACHE_CURRENT).claim
    assert unaffected.qualified is True


@pytest.mark.parametrize(
    ("material_identity", "expected", "reason"),
    [
        (None, Applicability.NOT_APPLICABLE, "material_mismatch"),
        ("other-material", Applicability.NOT_APPLICABLE, "material_mismatch"),
        ("bound-material", Applicability.APPLICABLE, None),
    ],
)
def test_material_dependent_current_applicability_uses_material_identity(
    material_identity: str | None,
    expected: Applicability,
    reason: str | None,
) -> None:
    entry = INITIAL_REGISTRY.uses[0]
    registry = replace(
        INITIAL_REGISTRY,
        uses=(
            replace(
                entry,
                requirements=tuple(
                    replace(rule, material_dependent=True)
                    if rule.capability is Capability.MODEL_IDENTITY
                    else rule
                    for rule in entry.requirements
                ),
            ),
        ),
    )
    evidence = tuple(
        replace(record, material_identity="bound-material") for record in records()
    )
    decision = evaluate_admission(
        registry,
        USE,
        evidence,
        binding=BINDING,
        now=NOW,
        material_identity=material_identity,
        checked_components=frozenset(BindingComponent),
    )
    assessment = decision.for_capability(Capability.MODEL_IDENTITY)
    assert assessment.applicability is expected
    assert [r.token for r in assessment.reasons] == ([] if reason is None else [reason])
    assert assessment.claim == item(evidence, Capability.MODEL_IDENTITY).claim
    assert (
        item(evidence, Capability.MODEL_IDENTITY).applicability
        is Applicability.APPLICABLE
    )
    unaffected = decision.for_capability(Capability.CWD_ANCESTORS)
    assert unaffected.applicability is Applicability.APPLICABLE
    assert unaffected.qualified is True
