"""#169 的公开能力登记边界;不依赖账本或真实主机。"""

from dataclasses import replace

import pytest

from paper_radar.live_evidence.registry import INITIAL_REGISTRY, AdmissionRegistry
from paper_radar.live_evidence.types import (
    AdmissionUse,
    CallSite,
    Capability,
    CapabilityRequirement,
    Consumer,
    EvidenceStatus,
    ExpiryClass,
    RegistryError,
    Requirement,
    ThinkingLevel,
)


def test_registry_explicitly_maps_the_six_product_consumer_cells() -> None:
    expected = {
        AdmissionUse(CallSite.SCREENING, Consumer.BOUNDARY, ThinkingLevel.LOW),
        AdmissionUse(CallSite.SCREENING, Consumer.BOUNDARY, ThinkingLevel.HIGH),
        AdmissionUse(CallSite.SCREENING, Consumer.VALUE, ThinkingLevel.LOW),
        AdmissionUse(CallSite.SCREENING, Consumer.VALUE, ThinkingLevel.HIGH),
        AdmissionUse(CallSite.READ, Consumer.READ, ThinkingLevel.LOW),
        AdmissionUse(CallSite.READ, Consumer.READ, ThinkingLevel.HIGH),
    }
    assert {entry.use for entry in INITIAL_REGISTRY.uses} == expected
    for use in expected:
        assert INITIAL_REGISTRY.requirements_for(use)


def test_undefined_use_and_empty_required_set_are_controlled_rejections() -> None:
    undefined = AdmissionUse(CallSite.READ, Consumer.BOUNDARY, ThinkingLevel.LOW)
    with pytest.raises(RegistryError, match="admission_use_undefined"):
        INITIAL_REGISTRY.requirements_for(undefined)
    entry = INITIAL_REGISTRY.uses[0]
    disclosed_only = replace(
        entry,
        requirements=tuple(
            replace(rule, requirement=Requirement.DISCLOSURE)
            for rule in entry.requirements
        ),
    )
    with pytest.raises(RegistryError, match="required_set_empty"):
        AdmissionRegistry("test-empty-v1", (disclosed_only,))


def test_owner_classification_keeps_current_cache_required_and_history_disclosed() -> (
    None
):
    rules = {rule.capability: rule for rule in INITIAL_REGISTRY.uses[0].requirements}
    assert rules[Capability.AUTH_CACHE_CURRENT].requirement is Requirement.REQUIRED
    assert rules[Capability.AUTH_CACHE_BASELINE].requirement is Requirement.REQUIRED
    assert rules[Capability.AUTH_CACHE_HISTORY].requirement is Requirement.DISCLOSURE
    assert rules[Capability.AUTH_CACHE_WRITER].requirement is Requirement.DISCLOSURE
    assert rules[Capability.SUPERVISOR_EXIT].requirement is Requirement.NOT_APPLICABLE
    assert (
        rules[Capability.EXTERNAL_INTERRUPT].requirement is Requirement.NOT_APPLICABLE
    )
    assert rules[Capability.EXTERNAL_INTERRUPT].expiry_class is ExpiryClass.ENGINEERING
    assert {rule.capability for rule in rules.values()} == set(Capability)
    assert set(EvidenceStatus) == {
        EvidenceStatus.VERIFIED,
        EvidenceStatus.NOT_ASSESSED,
        EvidenceStatus.UNKNOWN,
    }


def test_registry_rejects_duplicate_use_capability_and_unbounded_incomplete_rules() -> (
    None
):
    entry = INITIAL_REGISTRY.uses[0]
    with pytest.raises(RegistryError, match="duplicate_use"):
        AdmissionRegistry("duplicate-v1", (entry, entry))
    with pytest.raises(RegistryError, match="duplicate_capability"):
        AdmissionRegistry(
            "duplicate-rule-v1",
            (replace(entry, requirements=entry.requirements + entry.requirements[:1]),),
        )
    with pytest.raises(RegistryError, match="expiry_limit_invalid"):
        CapabilityRequirement(
            Capability.CWD_ANCESTORS,
            Requirement.REQUIRED,
            ExpiryClass.SITE,
            frozenset(),
            maximum_age_days=0,
        )


def test_required_rule_cannot_claim_drift_validity_with_no_dependencies() -> None:
    with pytest.raises(RegistryError, match="required_dependencies_empty"):
        CapabilityRequirement(
            Capability.CWD_ANCESTORS,
            Requirement.REQUIRED,
            ExpiryClass.SITE,
            frozenset(),
        )
