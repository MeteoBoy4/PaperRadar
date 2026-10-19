"""结构化来源的冻结复用摘录与公共输入身份。"""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    StageName,
    compile_config,
    load_config_snapshot,
    project_config,
)
from paper_radar.screening import ExcerptKind, OutputValidationError, validate_output
from paper_radar.stage_inputs import (
    BuildReason,
    InputField,
    ReuseFacts,
    ScreeningFacts,
    SelectedExcerpt,
    SourceSnapshotRef,
    StageInputError,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.config_projection_support import full_inputs, new_yaml_version


def test_structured_reuse_binds_actual_payload_member_and_validates_same_excerpts(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    settings.write_text(settings.read_text().replace("extraction: extraction-v1\n", ""))
    snapshot = compile_config(settings, database)
    assert snapshot.stages[StageName.EXTRACTION].status == "not_ready"
    store = ArtifactStore(database, tmp_path / "artifacts")
    published = store.publish_single("source_snapshot", [b"Synthetic source snapshot"])
    loaded_record = store.get_artifact(published.artifact_id)
    member = next(
        member for member in loaded_record.members if member.role == "payload"
    )
    assert member.sha256 != published.artifact_id
    source = SourceSnapshotRef(
        content_sha256=member.sha256, locator=("data-availability", "paragraph-1")
    )
    facts = ReuseFacts(
        excerpts=[
            SelectedExcerpt(
                excerpt_id="availability-1",
                kind="availability",
                text="Synthetic availability text",
                source=source,
            )
        ]
    )
    before_database = database.read_bytes()
    value = build_stage_input(
        load_config_snapshot(database, snapshot.snapshot_id), StageName.REUSE, facts
    )
    replayed = replay_stage_input(
        value.payload_bytes, value.fingerprint, snapshot=snapshot
    )
    context = replayed.reuse_assessment_context()
    payload = {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "所引摘录表明数据可以复用。",
        "required_adaptations": [],
        "excerpt_kind": "availability",
        "excerpt_ids": ["availability-1"],
    }
    assert validate_output("reuse_assessment", payload, context).reuse_feasibility == 4
    payload["excerpt_ids"] = ["unknown"]
    with pytest.raises(OutputValidationError):
        validate_output("reuse_assessment", payload, context)
    assert compare_stage_inputs(value, replayed).status == "same"
    assert member.sha256.encode() in value.payload_bytes
    assert published.artifact_id.encode() not in value.payload_bytes
    assert database.read_bytes() == before_database


def _source(**overrides: object) -> SourceSnapshotRef:
    return SourceSnapshotRef(
        **{"content_sha256": "1" * 64, "locator": ["section", "paragraph"], **overrides}
    )


def _excerpt(**overrides: object) -> SelectedExcerpt:
    return SelectedExcerpt(
        **{
            "excerpt_id": "id-1",
            "kind": "availability",
            "text": "SENSITIVE_EXCERPT",
            "source": _source(),
            **overrides,
        }
    )


@pytest.mark.parametrize(
    "override",
    [
        {"content_sha256": "A" * 64},
        {"content_sha256": "0x" + "1" * 64},
        {"content_sha256": 123},
        {"content_sha256": "1" * 63},
        {"locator": []},
        {"locator": "SENSITIVE_LOCATOR"},
        {"locator": {}},
        {"locator": [""]},
        {"locator": [" \t\n"]},
        {"locator": [1]},
        {"locator": ["SENSITIVE\ud800"]},
        {"url": "SENSITIVE_URL"},
        {"observed_at": "SENSITIVE_TIME"},
        {"artifact_id": "2" * 64},
        {"extraction_fingerprint": "3" * 64},
        {"SENSITIVE_KEY": "SENSITIVE_VALUE"},
    ],
)
def test_structured_source_strictly_rejects_invalid_fields_without_leaks(
    override: dict[str, object],
) -> None:
    with pytest.raises(StageInputError) as caught:
        _source(**override)
    assert caught.value.__context__ is None
    assert "SENSITIVE" not in repr(caught.value) + str(caught.value)


@pytest.mark.parametrize(
    "override",
    [
        {"excerpt_id": ""},
        {"excerpt_id": " \t"},
        {"excerpt_id": 1},
        {"excerpt_id": []},
        {"excerpt_id": "SENSITIVE\ud800"},
        {"kind": "both"},
        {"kind": "data"},
        {"kind": "SENSITIVE_KIND"},
        {"kind": True},
        {"text": ""},
        {"text": " \t\n"},
        {"text": None},
        {"text": "SENSITIVE\ud800"},
        {"source": {"SENSITIVE": "SENSITIVE"}},
        {"artifact_id": "SENSITIVE_ARTIFACT"},
    ],
)
def test_excerpt_id_and_kind_use_authoritative_context_rejections(
    override: dict[str, object],
) -> None:
    with pytest.raises(StageInputError) as caught:
        _excerpt(**override)
    assert caught.value.__context__ is None
    assert "SENSITIVE" not in repr(caught.value) + str(caught.value)


@pytest.mark.parametrize(
    "excerpts", [[], (), {}, "SENSITIVE_INPUT", ["SENSITIVE_INPUT"]]
)
def test_reuse_requires_a_nonempty_ordered_typed_collection(excerpts: object) -> None:
    with pytest.raises(StageInputError) as caught:
        ReuseFacts(excerpts=excerpts)
    assert caught.value.reason is BuildReason.INVALID_FACTS
    assert "SENSITIVE" not in repr(caught.value)


def test_duplicate_ids_from_different_sources_are_rejected_before_context_mapping() -> (
    None
):
    first = _excerpt()
    second = _excerpt(source=_source(content_sha256="2" * 64), kind="methods")
    with pytest.raises(StageInputError) as caught:
        ReuseFacts(excerpts=[first, second])
    assert caught.value.reason is BuildReason.DUPLICATE_EXCERPT_ID
    assert caught.value.field is InputField.EXCERPTS
    assert "id-1" not in str(caught.value)


def test_collection_locator_and_context_freeze_the_same_input_without_text_logging(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    locator = ["SENSITIVE_LOCATOR", "paragraph"]
    source = _source(locator=locator)
    excerpt = _excerpt(excerpt_id=" id-1 ", source=source)
    collection = [excerpt]
    facts = ReuseFacts(excerpts=collection)
    result = build_stage_input(snapshot, StageName.REUSE, facts)
    fingerprint = result.fingerprint
    context = result.reuse_assessment_context()
    locator.append("new")
    collection.clear()
    assert source.locator == ("SENSITIVE_LOCATOR", "paragraph")
    assert facts.excerpts == (excerpt,)
    assert context.excerpt_kinds == {" id-1 ": ExcerptKind.AVAILABILITY}
    assert result.fingerprint == fingerprint
    with pytest.raises(TypeError):
        context.excerpt_kinds["changed"] = ExcerptKind.METHODS
    for item, name in (
        (source, "locator"),
        (excerpt, "text"),
        (facts, "excerpts"),
        (result, "payload_bytes"),
    ):
        with pytest.raises(FrozenInstanceError) as caught:
            setattr(item, name, "SENSITIVE_NEW_VALUE")
        assert "SENSITIVE" not in repr(caught.value)
    assert "SENSITIVE" not in repr(source) + repr(excerpt) + repr(facts) + repr(result)
    assert capsys.readouterr() == ("", "")
    assert not caplog.records
    with pytest.raises(StageInputError) as context_error:
        result.reuse_assessment_context(excerpt_kinds={"changed": "methods"})
    assert context_error.value.reason is BuildReason.INVALID_CONTEXT


@pytest.mark.parametrize(
    ("change", "components"),
    [
        ({"excerpt_id": "id-2"}, ("excerpts",)),
        ({"kind": "methods"}, ("excerpts",)),
        ({"text": "SENSITIVE_NEW_EXCERPT"}, ("excerpts",)),
        ({"source_hash": "2" * 64}, ("excerpt_sources",)),
        ({"locator": ("section", "new-paragraph")}, ("excerpt_sources",)),
    ],
)
def test_reuse_comparison_explains_only_fixed_components(
    tmp_path: Path, change: dict[str, object], components: tuple[str, ...]
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    before = build_stage_input(
        snapshot, StageName.REUSE, ReuseFacts(excerpts=[_excerpt()])
    )
    if "source_hash" in change:
        changed = _excerpt(source=_source(content_sha256=change["source_hash"]))
    elif "locator" in change:
        changed = _excerpt(source=_source(locator=change["locator"]))
    else:
        changed = _excerpt(**change)
    after = build_stage_input(snapshot, StageName.REUSE, ReuseFacts(excerpts=[changed]))
    diff = compare_stage_inputs(before, after)
    assert before.fingerprint != after.fingerprint
    assert diff.status == "changed"
    assert diff.changed_components == components
    assert "SENSITIVE" not in repr(diff)
    assert "id-1" not in repr(diff)


def test_reordering_excerpts_preserves_input_order_and_reports_ordered_sources(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    first = _excerpt()
    second = _excerpt(
        excerpt_id="id-2", kind="methods", source=_source(content_sha256="2" * 64)
    )
    before = build_stage_input(
        snapshot, StageName.REUSE, ReuseFacts(excerpts=[first, second])
    )
    after = build_stage_input(
        snapshot, StageName.REUSE, ReuseFacts(excerpts=[second, first])
    )
    assert compare_stage_inputs(before, after).changed_components == (
        "excerpts",
        "excerpt_sources",
    )
    replayed = replay_stage_input(after.payload_bytes, after.fingerprint)
    assert isinstance(replayed.facts, ReuseFacts)
    assert replayed.facts.excerpts == (second, first)


def test_structured_reuse_ignores_unrelated_extraction_and_has_selector_semantics(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ReuseFacts(excerpts=[_excerpt()])
    before = build_stage_input(snapshot, StageName.REUSE, facts)
    store = ArtifactStore(database, tmp_path / "artifacts")
    store.publish_single("original_pdf", [b"Synthetic old PDF"])
    assert build_stage_input(snapshot, StageName.REUSE, facts) == before
    store.publish_single("original_pdf", [b"Synthetic new PDF"])
    assert build_stage_input(snapshot, StageName.REUSE, facts) == before
    new_yaml_version(
        settings, "extraction", lambda c: c.update(pdf_backend="threaded_docling_parse")
    )
    after_snapshot = compile_config(settings, database)
    assert build_stage_input(after_snapshot, StageName.REUSE, facts) == before
    assert snapshot.escalation is not None
    future_escalation = replace(
        snapshot.escalation,
        excerpt_selector_version="fixture-v2",  # type: ignore[arg-type]
    )
    future = replace(snapshot, escalation=future_escalation)
    after = build_stage_input(future, StageName.REUSE, facts)
    assert compare_stage_inputs(before, after).changed_components == (
        "config_projection",
    )
    assert (
        project_config(future).projections[StageName.REUSE].projection_id
        != before.projection_id
    )
    text_facts = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    assert build_stage_input(
        future, StageName.BOUNDARY, text_facts
    ) == build_stage_input(snapshot, StageName.BOUNDARY, text_facts)
    assert build_stage_input(future, StageName.VALUE, text_facts) == build_stage_input(
        snapshot, StageName.VALUE, text_facts
    )
    new_yaml_version(
        settings,
        "escalation",
        lambda c: c.update(excerpt_selector_version="fixture-v2"),
    )
    with pytest.raises(ConfigError):
        compile_config(settings, database)


def test_missing_reuse_materials_keep_the_existing_stage_readiness(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    settings.write_text(settings.read_text().replace("escalation: escalation-v1\n", ""))
    snapshot = compile_config(settings, database)
    with pytest.raises(StageInputError) as caught:
        build_stage_input(snapshot, StageName.REUSE, ReuseFacts(excerpts=[_excerpt()]))
    assert caught.value.reason is BuildReason.NOT_READY
    assert caught.value.readiness == snapshot.stages[StageName.REUSE]


def test_reuse_matches_independent_literal_vector_from_actual_source_member(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    store = ArtifactStore(database, tmp_path / "artifacts")
    saved = store.publish_single("source_snapshot", [b"Synthetic source snapshot"])
    member = store.get_artifact(saved.artifact_id).members[0]
    assert member.role == "payload"
    assert (
        member.sha256
        == "abdec00bc1f149e9b543ff79d5f4712097309c61136f95a2fbb52f0802139881"
    )
    assert (
        project_config(snapshot).projections[StageName.REUSE].projection_id
        == "f2c879f0ea03e7292c028e6f7470fb0b1c78c4569ebbbb55d6e0a269520ea791"
    )
    fixture = Path(__file__).parent / "fixtures/stage_inputs"
    payload = (fixture / "reuse-structured-v1.json").read_bytes()
    expected = (fixture / "reuse-structured-v1.sha256").read_text().strip()
    assert (
        expected == "3c9deffa8929d61e6cb2e96582b0c7af6e3c78ec958630b8be83986684e370b4"
    )
    assert hashlib.sha256(payload).hexdigest() == expected
    for _ in range(2):
        source = SourceSnapshotRef(
            content_sha256=member.sha256, locator=("data-availability", "paragraph-1")
        )
        facts = ReuseFacts(
            excerpts=[
                SelectedExcerpt(
                    excerpt_id="availability-1",
                    kind="availability",
                    text="Synthetic availability text",
                    source=source,
                )
            ]
        )
        result = build_stage_input(snapshot, StageName.REUSE, facts)
        assert result.payload_bytes == payload
        assert result.fingerprint == expected
        assert replay_stage_input(payload, expected, snapshot=snapshot) == result


@pytest.mark.parametrize(
    "damage",
    [
        "extra_source",
        "wrong_source",
        "bad_hash",
        "bad_locator",
        "duplicate_ids",
        "extra_fact",
    ],
)
def test_replay_strictly_checks_reuse_facts_without_raw_error_chains(
    damage: str,
) -> None:
    fixture = Path(__file__).parent / "fixtures/stage_inputs/reuse-structured-v1.json"
    value = json.loads(fixture.read_bytes())
    excerpt = value["facts"]["excerpts"][0]
    if damage == "extra_source":
        excerpt["source"]["SENSITIVE_UNKNOWN"] = "SENSITIVE_VALUE"
    elif damage == "wrong_source":
        excerpt["source"]["kind"] = "extraction"
    elif damage == "bad_hash":
        excerpt["source"]["content_sha256"] = "SENSITIVE_HASH"
    elif damage == "bad_locator":
        excerpt["source"]["locator"] = {"SENSITIVE": "SENSITIVE"}
    elif damage == "duplicate_ids":
        value["facts"]["excerpts"].append(excerpt)
    else:
        value["facts"]["SENSITIVE"] = "SENSITIVE"
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(payload, hashlib.sha256(payload).hexdigest())
    assert caught.value.reason == "invalid_payload"
    assert caught.value.__context__ is None
    assert "SENSITIVE" not in repr(caught.value) + str(caught.value)


@pytest.mark.parametrize("field", ["text", "locator"])
def test_reuse_keeps_unicode_whitespace_and_locator_order_exact(
    tmp_path: Path, field: str
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    if field == "text":
        first = _excerpt(text=" café\r\n")
        second = _excerpt(text=" cafe\u0301\n")
    else:
        first = _excerpt(source=_source(locator=[" section ", "paragraph"]))
        second = _excerpt(source=_source(locator=["paragraph", " section "]))
    before = build_stage_input(snapshot, StageName.REUSE, ReuseFacts(excerpts=[first]))
    after = build_stage_input(snapshot, StageName.REUSE, ReuseFacts(excerpts=[second]))
    assert before.fingerprint != after.fingerprint
    replayed = replay_stage_input(before.payload_bytes, before.fingerprint)
    assert isinstance(replayed.facts, ReuseFacts)
    assert replayed.facts.excerpts == (first,)


def test_reuse_and_screening_fact_types_and_contexts_cannot_be_mixed(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ReuseFacts(excerpts=[_excerpt()])
    screening = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    for stage, supplied in ((StageName.BOUNDARY, facts), (StageName.REUSE, screening)):
        with pytest.raises(StageInputError) as caught:
            build_stage_input(snapshot, stage, supplied)
        assert caught.value.reason is BuildReason.INVALID_FACTS
    boundary = build_stage_input(snapshot, StageName.BOUNDARY, screening)
    with pytest.raises(StageInputError) as caught:
        boundary.reuse_assessment_context()
    assert caught.value.reason is BuildReason.INVALID_CONTEXT
    reuse = build_stage_input(snapshot, StageName.REUSE, facts)
    assert compare_stage_inputs(boundary, reuse).reason == "different_stage"
