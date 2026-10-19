"""正文来源的消费闭包、审计隔离与混合摘录身份。"""

from pathlib import Path

import pytest

from paper_radar.config import StageName, compile_config
from paper_radar.screening import validate_output
from paper_radar.stage_inputs import (
    ExtractionFacts,
    ExtractionRef,
    ReuseFacts,
    SelectedExcerpt,
    SourceSnapshotRef,
    StageInput,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)
from tests.config_projection_support import full_inputs


def test_body_and_structured_excerpts_share_reuse_round_trip_and_context(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    extraction = replay_stage_input(extraction.payload_bytes, extraction.fingerprint)
    source = ExtractionRef(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        locator=["section", "block-1"],
    )
    facts = ReuseFacts(
        excerpts=[
            SelectedExcerpt(
                excerpt_id="body-1",
                kind="methods",
                text="Synthetic body text",
                source=source,
            ),
            SelectedExcerpt(
                excerpt_id="source-1",
                kind="availability",
                text="Synthetic source text",
                source=SourceSnapshotRef(
                    content_sha256="4" * 64, locator=["availability"]
                ),
            ),
        ]
    )
    original = build_stage_input(snapshot, StageName.REUSE, facts)
    restored = replay_stage_input(
        original.payload_bytes, original.fingerprint, snapshot=snapshot
    )
    assert restored == original
    assert compare_stage_inputs(original, restored).status == "same"
    assert (
        validate_output(
            "reuse_assessment",
            {
                "reuse_feasibility": 4,
                "reuse_feasibility_reason_zh": "所引摘录表明方法和数据可以复用。",
                "required_adaptations": [],
                "excerpt_kind": "both",
                "excerpt_ids": ["body-1", "source-1"],
            },
            restored.reuse_assessment_context(),
        ).reuse_feasibility
        == 4
    )


@pytest.mark.parametrize("changed", ["reading", "evidence_map", "fingerprint"])
def test_one_reuse_call_rejects_conflicting_body_content_or_multiple_extractions(
    tmp_path: Path, changed: str
) -> None:
    from paper_radar.stage_inputs import BuildReason, StageInputError

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    other = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="9" * 64)
    )
    first = ExtractionRef(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        locator=["block-1"],
    )
    second = ExtractionRef(
        extraction_input=other if changed == "fingerprint" else extraction,
        reading_sha256=("8" if changed == "reading" else "2") * 64,
        evidence_map_sha256=("7" if changed == "evidence_map" else "3") * 64,
        locator=["block-2"],
    )
    with pytest.raises(StageInputError) as caught:
        ReuseFacts(
            excerpts=[
                SelectedExcerpt(
                    excerpt_id="body-1",
                    kind="methods",
                    text="SECRET_FIRST",
                    source=first,
                ),
                SelectedExcerpt(
                    excerpt_id="body-2",
                    kind="availability",
                    text="SECRET_SECOND",
                    source=second,
                ),
            ]
        )
    assert caught.value.reason is BuildReason.INCONSISTENT_EXTRACTION_SOURCE
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize("changed_role", ["reading", "evidence_map"])
def test_real_extraction_artifacts_ignore_manifest_and_bind_consumed_members(
    tmp_path: Path, changed_role: str
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    store = ArtifactStore(database, tmp_path / "artifacts")
    content = {
        "reading": b"Synthetic reading text",
        "evidence_map": b'{"blocks":["block-1"]}',
        "document": b'{"backend":"synthetic"}',
        "manifest": b'{"started_at":"first","elapsed":1}',
    }
    first = store.publish_artifact(
        "extraction", {role: [raw] for role, raw in content.items()}
    )
    content["manifest"] = b'{"started_at":"second","elapsed":2}'
    second = store.publish_artifact(
        "extraction", {role: [raw] for role, raw in content.items()}
    )
    assert first.artifact_id != second.artifact_id

    def body_reuse(artifact_id: str) -> StageInput:
        # 始终从制品库回放的真实成员取得哈希。artifact_id 仅用于定位。
        members = {
            member.role: member.sha256
            for member in store.get_artifact(artifact_id).members
        }
        reference = ExtractionRef(
            extraction_input=extraction,
            reading_sha256=members["reading"],
            evidence_map_sha256=members["evidence_map"],
            locator=["block-1"],
        )
        return build_stage_input(
            snapshot,
            StageName.REUSE,
            ReuseFacts(
                excerpts=[
                    SelectedExcerpt(
                        excerpt_id="body-1",
                        kind="methods",
                        text="Synthetic selected text",
                        source=reference,
                    )
                ]
            ),
        )

    original = body_reuse(first.artifact_id)
    audited = body_reuse(second.artifact_id)
    assert original == audited
    assert first.artifact_id.encode() not in original.payload_bytes
    assert second.artifact_id.encode() not in audited.payload_bytes
    content[changed_role] += b" changed"
    third = store.publish_artifact(
        "extraction", {role: [raw] for role, raw in content.items()}
    )
    changed = body_reuse(third.artifact_id)
    # 同一 extraction 指纹在两次独立调用中可绑定不同实际输出。
    assert changed.fingerprint != original.fingerprint
    assert compare_stage_inputs(original, changed).changed_components == (
        "excerpt_sources",
    )


def test_body_reference_requires_extraction_input_domain(tmp_path: Path) -> None:
    from paper_radar.stage_inputs import (
        BuildReason,
        InputField,
        ScreeningFacts,
        StageInputError,
    )

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    text = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    wrong_inputs = [
        "1" * 64,
        {"extraction_fingerprint": "1" * 64},
        SourceSnapshotRef(content_sha256="1" * 64, locator=["block"]),
        build_stage_input(snapshot, StageName.BOUNDARY, text),
        build_stage_input(snapshot, StageName.VALUE, text),
        build_stage_input(
            snapshot,
            StageName.REUSE,
            ReuseFacts(
                excerpts=[
                    SelectedExcerpt(
                        excerpt_id="source-1",
                        kind="methods",
                        text="T",
                        source=SourceSnapshotRef(
                            content_sha256="1" * 64, locator=["block"]
                        ),
                    )
                ]
            ),
        ),
    ]
    for invalid in wrong_inputs:
        with pytest.raises(StageInputError) as caught:
            ExtractionRef(
                extraction_input=invalid,
                reading_sha256="2" * 64,
                evidence_map_sha256="3" * 64,
                locator=["SECRET_LOCATOR"],
            )
        assert caught.value.reason is BuildReason.INVALID_FACTS
        assert caught.value.field is InputField.EXTRACTION_INPUT
        assert "SECRET" not in str(caught.value) + repr(caught.value)
        assert caught.value.__context__ is None


@pytest.mark.parametrize("field", ["reading_sha256", "evidence_map_sha256"])
@pytest.mark.parametrize(
    "invalid", [None, 1, True, "A" * 64, "0x" + "1" * 64, "1" * 63, "SECRET\ud800"]
)
def test_body_member_hashes_are_strict_and_safe(
    tmp_path: Path, field: str, invalid: object
) -> None:
    from paper_radar.stage_inputs import BuildReason, StageInputError

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    values: dict[str, object] = {
        "extraction_input": extraction,
        "reading_sha256": "2" * 64,
        "evidence_map_sha256": "3" * 64,
        "locator": ["SECRET_LOCATOR"],
        field: invalid,
    }
    with pytest.raises(StageInputError) as caught:
        ExtractionRef(**values)
    assert caught.value.reason is BuildReason.INVALID_HASH
    assert caught.value.field.value.endswith(field)
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize(
    "override",
    [
        {"locator": []},
        {"locator": "SECRET_LOCATOR"},
        {"locator": {"SECRET": "VALUE"}},
        {"locator": [""]},
        {"locator": [" \n"]},
        {"locator": [1]},
        {"locator": ["SECRET\ud800"]},
        {"content_sha256": "4" * 64},
        {"artifact_id": "4" * 64},
        {"manifest": "SECRET_MANIFEST"},
        {"document": "SECRET_DOCUMENT"},
        {"path": "SECRET_PATH"},
        {"observed_at": "SECRET_TIME"},
        {"extraction_fingerprint": "4" * 64},
    ],
)
def test_body_reference_rejects_locator_errors_and_extra_source_fields(
    tmp_path: Path, override: dict[str, object]
) -> None:
    from paper_radar.stage_inputs import StageInputError

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    values = {
        "extraction_input": extraction,
        "reading_sha256": "2" * 64,
        "evidence_map_sha256": "3" * 64,
        "locator": ["block-1"],
        **override,
    }
    with pytest.raises(StageInputError) as caught:
        ExtractionRef(**values)
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value) + repr(caught.value)


def test_reuse_keeps_explicit_body_reference_across_current_extraction_changes(
    tmp_path: Path,
) -> None:
    from paper_radar.stage_inputs import ScreeningFacts
    from tests.config_projection_support import new_yaml_version

    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    extraction = build_stage_input(
        before, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )

    def facts_for(body_input: StageInput) -> ReuseFacts:
        return ReuseFacts(
            excerpts=[
                SelectedExcerpt(
                    excerpt_id="body-1",
                    kind="methods",
                    text="Synthetic text",
                    source=ExtractionRef(
                        extraction_input=body_input,
                        reading_sha256="2" * 64,
                        evidence_map_sha256="3" * 64,
                        locator=["block-1"],
                    ),
                )
            ]
        )

    frozen_facts = facts_for(extraction)
    original = build_stage_input(before, StageName.REUSE, frozen_facts)
    new_yaml_version(
        settings, "extraction", lambda c: c.update(pdf_backend="threaded_docling_parse")
    )
    after = compile_config(settings, database)
    assert build_stage_input(after, StageName.REUSE, frozen_facts) == original
    new_extraction = build_stage_input(
        after, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    rebound = build_stage_input(after, StageName.REUSE, facts_for(new_extraction))
    assert rebound.fingerprint != original.fingerprint
    assert compare_stage_inputs(original, rebound).changed_components == (
        "excerpt_sources",
    )
    text = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    for stage in (StageName.BOUNDARY, StageName.VALUE):
        assert build_stage_input(before, stage, text) == build_stage_input(
            after, stage, text
        )
    settings.write_text(settings.read_text().replace("extraction: extraction-v2\n", ""))
    missing = compile_config(settings, database)
    assert missing.stages[StageName.EXTRACTION].status == "not_ready"
    assert build_stage_input(missing, StageName.REUSE, frozen_facts) == original


@pytest.mark.parametrize(
    "changed", ["fingerprint", "locator", "text", "kind", "order", "structured_source"]
)
def test_body_and_mixed_input_changes_have_fixed_safe_comparison_components(
    tmp_path: Path, changed: str
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    other = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="9" * 64)
    )

    def facts_for(modified: bool) -> ReuseFacts:
        body = ExtractionRef(
            extraction_input=other
            if modified and changed == "fingerprint"
            else extraction,
            reading_sha256="2" * 64,
            evidence_map_sha256="3" * 64,
            locator=["block-2" if modified and changed == "locator" else "block-1"],
        )
        excerpts = [
            SelectedExcerpt(
                excerpt_id="body-1",
                kind="availability" if modified and changed == "kind" else "methods",
                text="SECRET_NEW" if modified and changed == "text" else "SECRET_TEXT",
                source=body,
            ),
            SelectedExcerpt(
                excerpt_id="source-1",
                kind="availability",
                text="SECRET_SOURCE",
                source=SourceSnapshotRef(
                    content_sha256=(
                        "8" if modified and changed == "structured_source" else "4"
                    )
                    * 64,
                    locator=["source-block"],
                ),
            ),
        ]
        return ReuseFacts(
            excerpts=list(reversed(excerpts))
            if modified and changed == "order"
            else excerpts
        )

    original = build_stage_input(snapshot, StageName.REUSE, facts_for(False))
    after = build_stage_input(snapshot, StageName.REUSE, facts_for(True))
    assert original.fingerprint != after.fingerprint
    expected = (
        ("excerpts", "excerpt_sources")
        if changed == "order"
        else (("excerpts",) if changed in ("text", "kind") else ("excerpt_sources",))
    )
    comparison = compare_stage_inputs(original, after)
    assert comparison.changed_components == expected
    assert "SECRET" not in repr(comparison)


@pytest.mark.parametrize("mixed", [False, True])
def test_body_and_mixed_reuse_match_independent_literal_vectors(
    tmp_path: Path, mixed: bool
) -> None:
    import hashlib

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    source = ExtractionRef(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        locator=["section", "block-1"],
    )
    excerpts = [
        SelectedExcerpt(
            excerpt_id="body-1",
            kind="methods",
            text="Synthetic body text",
            source=source,
        )
    ]
    if mixed:
        excerpts.append(
            SelectedExcerpt(
                excerpt_id="source-1",
                kind="availability",
                text="Synthetic source text",
                source=SourceSnapshotRef(
                    content_sha256="4" * 64, locator=["availability"]
                ),
            )
        )
    result = build_stage_input(snapshot, StageName.REUSE, ReuseFacts(excerpts=excerpts))
    fixture = Path(__file__).parent / "fixtures/stage_inputs"
    name = "reuse-mixed-v1" if mixed else "reuse-body-v1"
    payload = (fixture / f"{name}.json").read_bytes()
    expected = (fixture / f"{name}.sha256").read_text().strip()
    assert hashlib.sha256(payload).hexdigest() == expected
    assert result.payload_bytes == payload
    assert result.fingerprint == expected
    assert replay_stage_input(payload, expected, snapshot=snapshot) == result


def test_body_reference_freezes_nested_inputs_and_replays_without_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    import builtins
    import sqlite3
    from dataclasses import FrozenInstanceError

    from paper_radar.storage.artifacts import ArtifactStore

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    locator = [" SECRET_LOCATOR ", "cafe\u0301\r\n"]
    source = ExtractionRef(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        locator=locator,
    )
    excerpt = SelectedExcerpt(
        excerpt_id="SECRET_ID", kind="methods", text="SECRET_TEXT", source=source
    )
    excerpts = [excerpt]
    facts = ReuseFacts(excerpts=excerpts)
    original = build_stage_input(snapshot, StageName.REUSE, facts)
    payload, fingerprint = original.payload_bytes, original.fingerprint
    context = original.reuse_assessment_context()
    locator.clear()
    excerpts.clear()
    assert source.locator == (" SECRET_LOCATOR ", "cafe\u0301\r\n")
    assert original.payload_bytes == payload
    assert original.fingerprint == fingerprint
    assert original.reuse_assessment_context() == context
    for item, name in (
        (source, "reading_sha256"),
        (source, "locator"),
        (excerpt, "source"),
        (facts, "excerpts"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(item, name, "SECRET_MUTATION")
    database_before = database.read_bytes()

    def forbid_io(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected I/O")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbid_io)
        patch.setattr(Path, "open", forbid_io)
        patch.setattr(sqlite3, "connect", forbid_io)
        patch.setattr(ArtifactStore, "get_artifact", forbid_io)
        rebuilt = build_stage_input(snapshot, StageName.REUSE, facts)
        for explicit in (None, snapshot):
            restored = replay_stage_input(payload, fingerprint, snapshot=explicit)
            assert compare_stage_inputs(rebuilt, restored).status == "same"
            assert restored.reuse_assessment_context() == context
    assert database.read_bytes() == database_before
    assert "SECRET" not in repr(source) + repr(excerpt) + repr(facts) + repr(original)
    assert capsys.readouterr() == ("", "")
    assert not caplog.records


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "fingerprint_upper",
        "fingerprint_int",
        "reading",
        "evidence_map",
        "kind",
        "manifest",
        "document",
        "artifact_id",
        "locator",
        "unicode",
        "conflicting_reading",
        "conflicting_evidence_map",
        "multiple_extractions",
        "duplicate_cross_type",
    ],
)
def test_body_replay_rejects_invalid_and_inconsistent_source_descriptions(
    damage: str,
) -> None:
    import copy
    import hashlib
    import json

    from paper_radar.stage_inputs import ReplayReason, StageInputError

    value = json.loads(
        (
            Path(__file__).parent / "fixtures/stage_inputs/reuse-mixed-v1.json"
        ).read_bytes()
    )
    body = value["facts"]["excerpts"][0]
    source = body["source"]
    if damage == "missing":
        source.pop("reading_sha256")
    elif damage == "fingerprint_upper":
        source["extraction_fingerprint"] = "A" * 64
    elif damage == "fingerprint_int":
        source["extraction_fingerprint"] = 123
    elif damage == "reading":
        source["reading_sha256"] = "SECRET_HASH"
    elif damage == "evidence_map":
        source["evidence_map_sha256"] = "0x" + "1" * 64
    elif damage == "kind":
        source["kind"] = "source_snapshot"
    elif damage in ("manifest", "document", "artifact_id"):
        source[damage] = "SECRET_VALUE"
    elif damage == "locator":
        source["locator"] = {"SECRET": "VALUE"}
    elif damage == "unicode":
        source["locator"] = ["SECRET\ud800"]
    elif damage == "duplicate_cross_type":
        value["facts"]["excerpts"][1]["excerpt_id"] = body["excerpt_id"]
    else:
        conflict = copy.deepcopy(body)
        conflict["excerpt_id"] = "body-2"
        field = {
            "conflicting_reading": "reading_sha256",
            "conflicting_evidence_map": "evidence_map_sha256",
            "multiple_extractions": "extraction_fingerprint",
        }[damage]
        conflict["source"][field] = "9" * 64
        value["facts"]["excerpts"].append(conflict)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(payload, hashlib.sha256(payload).hexdigest())
    assert caught.value.reason is ReplayReason.INVALID_PAYLOAD
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value) + repr(caught.value)


def test_replay_checks_hash_shape_without_claiming_its_real_identity_domain() -> None:
    import hashlib
    import json

    value = json.loads(
        (
            Path(__file__).parent / "fixtures/stage_inputs/reuse-body-v1.json"
        ).read_bytes()
    )
    value["facts"]["excerpts"][0]["source"]["extraction_fingerprint"] = "9" * 64
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    restored = replay_stage_input(payload, hashlib.sha256(payload).hexdigest())
    assert isinstance(restored.facts, ReuseFacts)
    source = restored.facts.excerpts[0].source
    assert isinstance(source, ExtractionRef)
    assert source.extraction_fingerprint == "9" * 64


def test_two_body_excerpts_can_share_one_content_identity_in_producer_order(
    tmp_path: Path,
) -> None:
    from paper_radar.stage_inputs import BuildReason, StageInputError

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    excerpts = [
        SelectedExcerpt(
            excerpt_id=f"body-{index}",
            kind=kind,
            text="Synthetic text",
            source=ExtractionRef(
                extraction_input=extraction,
                reading_sha256="2" * 64,
                evidence_map_sha256="3" * 64,
                locator=[f"block-{index}"],
            ),
        )
        for index, kind in enumerate(("methods", "availability"), start=1)
    ]
    result = build_stage_input(snapshot, StageName.REUSE, ReuseFacts(excerpts=excerpts))
    assert isinstance(result.facts, ReuseFacts)
    assert result.facts.excerpts == tuple(excerpts)
    assert set(result.reuse_assessment_context().excerpt_kinds) == {"body-1", "body-2"}
    with pytest.raises(StageInputError) as caught:
        ReuseFacts(
            excerpts=[
                excerpts[0],
                SelectedExcerpt(
                    excerpt_id="body-1",
                    kind="availability",
                    text="Synthetic text",
                    source=SourceSnapshotRef(
                        content_sha256="4" * 64, locator=["section"]
                    ),
                ),
            ]
        )
    assert caught.value.reason is BuildReason.DUPLICATE_EXCERPT_ID
