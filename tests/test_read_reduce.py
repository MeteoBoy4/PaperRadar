"""reduce 只使用调用方明确给定、同正文的 map 证据。"""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

from paper_radar.reading import (
    AllowedEvidence,
    ExtractionIdentity,
    ReadContextError,
    ReadOutputError,
    validate_read_output,
)
from tests.read_support import candidate, context_for


def test_same_candidate_is_accepted_in_single_and_allowed_reduce() -> None:
    single = context_for()
    reduce = context_for(
        mode="reduce",
        allowed_evidence=AllowedEvidence(single.identity, ("e1",)),
    )
    raw = candidate()
    single_result = validate_read_output(raw, single)
    reduce_result = validate_read_output(raw, reduce)

    assert reduce_result.analysis == single_result.analysis
    assert reduce_result.mode == "reduce"
    assert reduce_result.identity == single.identity
    assert reduce_result.evidence_rule_version == "read-evidence-v1"
    assert reduce_result.numeric_rule_version == "read-numeric-v1"


def test_reduce_requires_explicit_allowance_instead_of_full_text_fallback() -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(mode="reduce")
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence", "missing_allowed_evidence")
    ]


def test_single_rejects_a_reduce_allowance() -> None:
    identity = context_for().identity
    with pytest.raises(ReadContextError) as error:
        context_for(allowed_evidence=AllowedEvidence(identity, ("e1",)))
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence", "unexpected_allowed_evidence")
    ]


@pytest.mark.parametrize(
    "identity",
    [
        ExtractionIdentity("other-extraction", "reading-1", "map-1"),
        ExtractionIdentity("extraction-1", "other-reading", "map-1"),
        ExtractionIdentity("extraction-1", "reading-1", "other-map"),
    ],
)
def test_reduce_allowance_cannot_cross_any_consumption_identity(
    identity: ExtractionIdentity,
) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(mode="reduce", allowed_evidence=AllowedEvidence(identity, ("e1",)))
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence.identity", "identity_mismatch")
    ]


@pytest.mark.parametrize("members", [("e1", "e1"), ["e1", "e1"]])
def test_allowance_rejects_duplicate_ids_before_building_a_lookup(
    members: list[str] | tuple[str, ...],
) -> None:
    with pytest.raises(ReadContextError) as error:
        AllowedEvidence(context_for().identity, members)
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence.evidence_ids[1]", "duplicate_id")
    ]


def test_unknown_allowance_member_is_a_context_error() -> None:
    identity = context_for().identity
    with pytest.raises(ReadContextError) as error:
        context_for(
            mode="reduce",
            allowed_evidence=AllowedEvidence(identity, ("unknown-secret-id",)),
        )
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence.evidence_ids[0]", "unknown_allowed_evidence")
    ]
    assert "unknown-secret-id" not in str(error.value)


@pytest.mark.parametrize("members", ["e1", {"e1"}, {"e1": True}, 1, None])
def test_allowance_requires_an_ordered_sequence_with_detectable_duplicates(
    members: Any,
) -> None:
    with pytest.raises(ReadContextError) as error:
        AllowedEvidence(context_for().identity, members)
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence.evidence_ids", "invalid_allowed_evidence")
    ]


@pytest.mark.parametrize("member", [True, 1, None, "", " e1", "e1\n"])
def test_allowance_members_use_strict_unchanged_evidence_ids(member: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        AllowedEvidence(context_for().identity, (member,))
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence.evidence_ids[0]", "invalid_evidence_id")
    ]


def test_existing_full_text_evidence_outside_allowance_is_output_rejection() -> None:
    single = context_for()
    reduce = context_for(
        mode="reduce",
        evidence=[single.evidence[0], replace(single.evidence[0], evidence_id="e2")],
        allowed_evidence=AllowedEvidence(single.identity, ("e2",)),
    )
    raw = candidate()
    validate_read_output(raw, single)
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, reduce)
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.research_value_reason.evidence", "evidence_required"),
        ("$.research_value_reason.evidence[0].evidence_id", "evidence_not_allowed"),
        ("$.reuse_feasibility_reason.evidence", "evidence_required"),
        ("$.reuse_feasibility_reason.evidence[0].evidence_id", "evidence_not_allowed"),
    ]


def test_unknown_output_id_and_existing_disallowed_id_are_distinct() -> None:
    single = context_for()
    reduce = context_for(
        mode="reduce",
        evidence=[single.evidence[0], replace(single.evidence[0], evidence_id="e2")],
        allowed_evidence=AllowedEvidence(single.identity, ("e1",)),
    )
    raw = candidate(
        main_findings=[
            {"statement": "新发现。", "evidence": [{"evidence_id": "missing-secret"}]},
            {"statement": "另一发现。", "evidence": [{"evidence_id": "e2"}]},
        ]
    )
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, reduce)
    categories = {(i.location, i.category.value) for i in error.value.issues}
    assert (
        "$.main_findings[0].evidence[0].evidence_id",
        "unknown_evidence",
    ) in categories
    assert (
        "$.main_findings[1].evidence[0].evidence_id",
        "evidence_not_allowed",
    ) in categories
    assert "missing-secret" not in repr(error.value)


def test_empty_reduce_allowance_is_expressible_but_rejects_required_support() -> None:
    context = context_for(
        mode="reduce", allowed_evidence=AllowedEvidence(context_for().identity, ())
    )
    assert context.allowed_evidence is not None
    assert context.allowed_evidence.evidence_ids == ()
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(candidate(), context)
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.research_value_reason.evidence", "evidence_required"),
        ("$.research_value_reason.evidence[0].evidence_id", "evidence_not_allowed"),
        ("$.reuse_feasibility_reason.evidence", "evidence_required"),
        ("$.reuse_feasibility_reason.evidence[0].evidence_id", "evidence_not_allowed"),
    ]


def test_allowance_is_frozen_and_does_not_require_using_every_permitted_id() -> None:
    single = context_for()
    members = ["e2", "e1"]
    allowed = AllowedEvidence(single.identity, members)
    evidence = [single.evidence[0], replace(single.evidence[0], evidence_id="e2")]
    context = context_for(mode="reduce", evidence=evidence, allowed_evidence=allowed)
    members[:] = ["unknown"]
    evidence.clear()

    assert allowed.evidence_ids == ("e2", "e1")
    result = validate_read_output(candidate(), context)
    assert result.mode == "reduce"
    assert result.analysis.research_value_reason.evidence[0].evidence_id == "e1"
    with pytest.raises(FrozenInstanceError):
        allowed.evidence_ids = ()  # type: ignore[misc]


@pytest.mark.parametrize("allowance", [("e1",), {"e1"}, {"identity": "secret"}, True])
def test_reduce_requires_the_authoritative_allowance_type(allowance: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(mode="reduce", allowed_evidence=allowance)
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence", "invalid_allowed_evidence")
    ]


@pytest.mark.parametrize("identity", [None, "identity-secret", ("e", "r", "m")])
def test_allowance_itself_requires_a_valid_identity(identity: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        AllowedEvidence(identity, ("e1",))
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.allowed_evidence.identity", "invalid_identity")
    ]
    assert "identity-secret" not in repr(error.value)


@pytest.mark.parametrize(
    "field", ["main_findings", "reusable_points", "key_limitations"]
)
def test_reduce_scope_applies_to_every_protected_content(field: str) -> None:
    single = context_for()
    context = context_for(
        mode="reduce",
        evidence=[single.evidence[0], replace(single.evidence[0], evidence_id="e2")],
        allowed_evidence=AllowedEvidence(single.identity, ("e1",)),
    )
    entry = (
        {"item": "可复用的方法。", "how_to_reuse": "比较研究条件。"}
        if field == "reusable_points"
        else {"statement": "需要进一步核对。"}
    )
    raw = candidate(**{field: [{**entry, "evidence": [{"evidence_id": "e2"}]}]})
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, context)
    assert (
        f"$.{field}[0].evidence[0].evidence_id",
        "evidence_not_allowed",
    ) in [(i.location, i.category.value) for i in error.value.issues]


def test_reduce_retains_numeric_diagnostics_and_model_warnings() -> None:
    single = context_for("The increase was 20%.")
    context = context_for(
        "The increase was 20%.",
        mode="reduce",
        allowed_evidence=AllowedEvidence(single.identity, ("e1",)),
    )
    raw = candidate(
        main_findings=[
            {"statement": "增加了30%。", "evidence": [{"evidence_id": "e1"}]}
        ],
        degraded_content_warnings=["模型要求核对来源。"],
    )
    result = validate_read_output(raw, context)
    assert [(d.location, d.reason.value, d.ordinal) for d in result.diagnostics] == [
        ("$.main_findings[0].statement", "number_not_supported", 0)
    ]
    assert [w.origin for w in result.warnings] == ["model", "program"]
    assert result.model_warnings == ("模型要求核对来源。",)
    assert result == validate_read_output(raw, context)


@pytest.mark.parametrize(
    ("changes", "location", "category"),
    [
        ({"mode": "single"}, "$.<额外字段>", "extra_field"),
        ({"output_language": "en"}, "$.output_language", "language_mismatch"),
        ({"research_value": True}, "$.research_value", "invalid_type"),
        ({"value_types": []}, "$.value_types", "value_types_required"),
    ],
)
def test_reduce_uses_the_same_strict_output_rules(
    changes: dict[str, object], location: str, category: str
) -> None:
    context = context_for(
        mode="reduce", allowed_evidence=AllowedEvidence(context_for().identity, ("e1",))
    )
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(candidate(**changes), context)
    assert (location, category) in [
        (i.location, i.category.value) for i in error.value.issues
    ]


def test_reduce_program_fields_do_not_change_the_frozen_model_contract(
    tmp_path: Path,
) -> None:
    from paper_radar.contracts import check_frozen_contract, export_frozen_contract

    exported = export_frozen_contract("read", "v1", tmp_path)
    checked = check_frozen_contract("read", "v1", tmp_path)
    assert checked.schema_sha256 == (
        "1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111"
    )
    schema = (exported.snapshot_dir / "schema.json").read_bytes()
    assert b"allowed_evidence" not in schema
    assert b"mode" not in schema


def test_allowance_default_representations_hide_evidence_ids() -> None:
    allowance = AllowedEvidence(context_for().identity, ("evidence-id-secret",))
    assert "evidence-id-secret" not in repr(allowance)
    assert "evidence-id-secret" not in str(allowance)


def test_unknown_mode_remains_a_controlled_context_failure() -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(mode="map")
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$.mode", "unsupported_mode")
    ]
