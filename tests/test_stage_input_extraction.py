"""原始 PDF 内容身份与正文提取配方。不读取 PDF 或解析器。"""

from pathlib import Path

import pytest

from paper_radar.config import StageName, compile_config, load_config_snapshot
from paper_radar.stage_inputs import (
    ExtractionFacts,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)
from tests.config_projection_support import full_inputs


def test_extraction_round_trip_and_pdf_change(tmp_path: Path) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    original = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    restored = replay_stage_input(
        original.payload_bytes,
        original.fingerprint,
        snapshot=load_config_snapshot(database, snapshot.snapshot_id),
    )
    assert restored == original
    assert restored.stage is StageName.EXTRACTION
    assert isinstance(restored.facts, ExtractionFacts)
    assert restored.facts.pdf_sha256 == "1" * 64
    assert compare_stage_inputs(original, restored).status == "same"
    changed = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="2" * 64)
    )
    assert changed.fingerprint != original.fingerprint
    assert compare_stage_inputs(original, changed).changed_components == ("pdf",)


def test_extraction_matches_independent_literal_vector(tmp_path: Path) -> None:
    import hashlib

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    fixture = Path(__file__).parent / "fixtures/stage_inputs"
    payload = (fixture / "extraction-v1.json").read_bytes()
    expected = (fixture / "extraction-v1.sha256").read_text().strip()
    assert hashlib.sha256(payload).hexdigest() == expected
    result = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    assert result.payload_bytes == payload
    assert result.fingerprint == expected
    assert replay_stage_input(payload, expected, snapshot=snapshot) == result


def test_extraction_tracks_its_projection_and_ignores_profile_and_screening(
    tmp_path: Path,
) -> None:
    from paper_radar.config import project_config
    from tests.config_projection_support import new_yaml_version

    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    facts = ExtractionFacts(pdf_sha256="1" * 64)
    original = build_stage_input(before, StageName.EXTRACTION, facts)
    new_yaml_version(settings, "profile", lambda c: c.update(background="changed"))
    new_yaml_version(
        settings, "adapters.screening", lambda c: c.update(thinking_level="high")
    )
    unrelated = compile_config(settings, database)
    assert build_stage_input(unrelated, StageName.EXTRACTION, facts) == original
    new_yaml_version(
        settings,
        "extraction",
        lambda c: c.update(pdf_backend="threaded_docling_parse"),
    )
    changed = compile_config(settings, database)
    after = build_stage_input(changed, StageName.EXTRACTION, facts)
    assert after.fingerprint != original.fingerprint
    assert (after.fingerprint != original.fingerprint) == (
        project_config(before).projections[StageName.EXTRACTION].projection_id
        != project_config(changed).projections[StageName.EXTRACTION].projection_id
    )
    assert compare_stage_inputs(original, after).changed_components == (
        "config_projection",
    )
    assert (
        replay_stage_input(
            original.payload_bytes, original.fingerprint, snapshot=before
        )
        == original
    )


def test_future_normalization_is_a_pure_fixture_and_cannot_be_compiled(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    import pytest

    from paper_radar.config import ConfigError
    from paper_radar.stage_inputs import ScreeningFacts
    from tests.config_projection_support import new_yaml_version

    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    assert before.extraction is not None
    future = replace(
        before,
        extraction=replace(
            before.extraction,
            normalization_version="fixture-v2",  # type: ignore[arg-type]
        ),
    )
    facts = ExtractionFacts(pdf_sha256="1" * 64)
    original = build_stage_input(before, StageName.EXTRACTION, facts)
    after = build_stage_input(future, StageName.EXTRACTION, facts)
    assert after.fingerprint != original.fingerprint
    assert compare_stage_inputs(original, after).changed_components == (
        "config_projection",
    )
    texts = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    for stage in (StageName.BOUNDARY, StageName.VALUE):
        assert build_stage_input(before, stage, texts) == build_stage_input(
            future, stage, texts
        )
    new_yaml_version(
        settings, "extraction", lambda c: c.update(normalization_version="fixture-v2")
    )
    with pytest.raises(ConfigError):
        compile_config(settings, database)


@pytest.mark.parametrize(
    "invalid",
    [None, 123, True, b"1" * 64, "A" * 64, "0x" + "1" * 64, "1" * 63, "secret\ud800"],
)
def test_pdf_hash_encoding_is_strict_and_errors_are_safe(invalid: object) -> None:
    from paper_radar.stage_inputs import BuildReason, InputField, StageInputError

    with pytest.raises(StageInputError) as caught:
        ExtractionFacts(pdf_sha256=invalid)
    assert caught.value.reason is BuildReason.INVALID_HASH
    assert caught.value.field is InputField.PDF_SHA256
    assert caught.value.__context__ is None
    assert "secret" not in repr(caught.value) + str(caught.value)


@pytest.mark.parametrize(
    "extra",
    [
        "title",
        "doi",
        "abstract",
        "path",
        "downloaded_at",
        "elapsed",
        "backend",
        "normalization_version",
        "supply_id",
        "install_id",
    ],
)
def test_extraction_facts_reject_metadata_and_audit_fields(extra: str) -> None:
    from paper_radar.stage_inputs import BuildReason, InputField, StageInputError

    with pytest.raises(StageInputError) as caught:
        ExtractionFacts(pdf_sha256="1" * 64, **{extra: "SECRET_VALUE"})
    assert caught.value.reason is BuildReason.INVALID_FACTS
    assert caught.value.field is InputField.FACTS
    assert "SECRET" not in repr(caught.value)


def test_missing_pdf_hash_is_not_defaulted() -> None:
    from paper_radar.stage_inputs import BuildReason, StageInputError

    with pytest.raises(StageInputError) as caught:
        ExtractionFacts()
    assert caught.value.reason is BuildReason.INVALID_HASH


def test_extraction_only_requires_its_own_configuration(tmp_path: Path) -> None:
    from paper_radar.stage_inputs import BuildReason, StageInputError
    from tests.config_projection_support import empty_inputs

    settings, database = full_inputs(tmp_path / "full")
    settings.write_text("extraction: extraction-v1\n")
    snapshot = compile_config(settings, database)
    assert snapshot.stages[StageName.VALUE].status == "not_ready"
    assert (
        build_stage_input(
            snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
        ).stage
        is StageName.EXTRACTION
    )
    settings, database = empty_inputs(tmp_path / "empty")
    missing = compile_config(settings, database)
    with pytest.raises(StageInputError) as caught:
        build_stage_input(
            missing, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
        )
    assert caught.value.reason is BuildReason.NOT_READY
    assert caught.value.readiness is missing.stages[StageName.EXTRACTION]


def test_stage_and_fact_types_cannot_impersonate_each_other(tmp_path: Path) -> None:
    from paper_radar.stage_inputs import BuildReason, ScreeningFacts, StageInputError

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ExtractionFacts(pdf_sha256="1" * 64)
    extraction = build_stage_input(snapshot, StageName.EXTRACTION, facts)
    text = ScreeningFacts(title="T", abstract="A", abstract_truncated=False)
    boundary = build_stage_input(snapshot, StageName.BOUNDARY, text)
    for invalid in ("1" * 64, {"pdf_sha256": "1" * 64}, text, boundary, extraction):
        with pytest.raises(StageInputError) as caught:
            build_stage_input(snapshot, StageName.EXTRACTION, invalid)  # type: ignore[arg-type]
        assert caught.value.reason is BuildReason.INVALID_FACTS
    for stage in (StageName.BOUNDARY, StageName.VALUE):
        with pytest.raises(StageInputError) as caught:
            build_stage_input(snapshot, stage, facts)
        assert caught.value.reason is BuildReason.INVALID_FACTS
    for unsupported_stage in (StageName.READ, StageName.SUGGESTION, "extraction"):
        with pytest.raises(StageInputError) as caught:
            build_stage_input(snapshot, unsupported_stage, facts)  # type: ignore[arg-type]
        assert caught.value.reason is BuildReason.UNSUPPORTED_STAGE
    assert compare_stage_inputs(boundary, extraction).reason == "different_stage"
    assert compare_stage_inputs("1" * 64, extraction).reason == "invalid_input"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"facts": {}}, "invalid_payload"),
        ({"facts": {"pdf_sha256": "A" * 64}}, "invalid_payload"),
        ({"facts": {"pdf_sha256": 1}}, "invalid_payload"),
        (
            {"facts": {"pdf_sha256": "1" * 64, "title": "SECRET_TITLE"}},
            "invalid_payload",
        ),
        (
            {
                "facts": {
                    "title": "SECRET_TITLE",
                    "abstract": "SECRET_ABSTRACT",
                    "abstract_truncated": False,
                }
            },
            "invalid_payload",
        ),
        ({"format_version": True}, "unsupported_format"),
        ({"format_version": 2}, "unsupported_format"),
        (
            {"config_projection": {"format_version": 2, "projection_id": "1" * 64}},
            "projection_format_unverifiable",
        ),
        (
            {"config_projection": {"format_version": 1, "projection_id": "A" * 64}},
            "invalid_payload",
        ),
        ({"stage": "read"}, "unsupported_stage"),
        ({"stage": "suggestion"}, "unsupported_stage"),
    ],
)
def test_extraction_replay_strictly_rejects_invalid_payloads(
    change: dict[str, object], reason: str
) -> None:
    import hashlib
    import json

    from paper_radar.stage_inputs import StageInputError

    fixture = Path(__file__).parent / "fixtures/stage_inputs/extraction-v1.json"
    value = json.loads(fixture.read_bytes())
    value.update(change)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(payload, hashlib.sha256(payload).hexdigest())
    assert caught.value.reason == reason
    assert caught.value.__context__ is None
    assert "SECRET" not in str(caught.value) + repr(caught.value)


def test_extraction_projection_mismatch_and_incompatible_format_are_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from paper_radar.config import projections
    from paper_radar.stage_inputs import ReplayReason, StageInputError

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    facts = ExtractionFacts(pdf_sha256="1" * 64)
    original = build_stage_input(snapshot, StageName.EXTRACTION, facts)
    assert snapshot.extraction is not None
    changed = replace(
        snapshot,
        extraction=replace(
            snapshot.extraction,
            normalization_version="fixture-v2",  # type: ignore[arg-type]
        ),
    )
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(
            original.payload_bytes, original.fingerprint, snapshot=changed
        )
    assert caught.value.reason is ReplayReason.PROJECTION_MISMATCH
    versions = dict(projections.PROJECTION_FORMAT_VERSIONS)
    versions[StageName.EXTRACTION] = 2
    monkeypatch.setattr(projections, "PROJECTION_FORMAT_VERSIONS", versions)
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(
            original.payload_bytes, original.fingerprint, snapshot=snapshot
        )
    assert caught.value.reason is ReplayReason.PROJECTION_FORMAT_UNVERIFIABLE
    future = build_stage_input(snapshot, StageName.EXTRACTION, facts)
    assert future.format_version == 1
    assert future.projection_format_version == 2
    assert compare_stage_inputs(original, future).reason == "incompatible_format"


def test_extraction_is_immutable_safe_and_needs_no_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    import builtins
    from dataclasses import FrozenInstanceError

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    database_before = database.read_bytes()
    facts = ExtractionFacts(pdf_sha256="a" * 64)

    def forbid_io(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected I/O")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbid_io)
        patch.setattr(Path, "open", forbid_io)
        original = build_stage_input(snapshot, StageName.EXTRACTION, facts)
        replayed = replay_stage_input(
            original.payload_bytes, original.fingerprint, snapshot=snapshot
        )
        assert compare_stage_inputs(original, replayed).status == "same"
    for item, name in (
        (facts, "pdf_sha256"),
        (original, "stage"),
        (replayed, "payload_bytes"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(item, name, "SECRET_MUTATION")
    assert "a" * 64 not in repr(facts) + repr(original)
    assert database.read_bytes() == database_before
    assert capsys.readouterr() == ("", "")
    assert not caplog.records
