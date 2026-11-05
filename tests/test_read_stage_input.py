"""Body D1:Read 纯输入身份,独立于 A9/A8 固定向量。"""

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from paper_radar.config import (
    RuntimeConfigSnapshot,
    StageName,
    compile_config,
    load_config_snapshot,
    project_config,
)
from paper_radar.contracts import export_frozen_contract
from paper_radar.stage_inputs import (
    BuildReason,
    ExtractionFacts,
    ReadFacts,
    ReplayReason,
    ScreeningFacts,
    StageInput,
    StageInputError,
    build_stage_input,
    replay_stage_input,
)
from tests.config_projection_support import full_inputs, new_yaml_version


def read_configuration(root: Path) -> tuple[Path, Path]:
    settings, database = full_inputs(root)
    export_frozen_contract("read", "v1", root / "contracts")
    settings.write_text(
        settings.read_text().replace("contracts:\n", "contracts:\n  read: v1\n")
    )
    adapter = settings.parent / "adapters/pi-v1.yaml"
    adapter.write_text(adapter.read_text().replace("1.1.0", "1.4.0"))
    return settings, database


def test_read_round_trip_binds_only_body_identity_and_output_language(
    tmp_path: Path,
) -> None:
    settings, database = read_configuration(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    facts = ReadFacts(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        output_language="zh",
    )
    result = build_stage_input(snapshot, StageName.READ, facts)
    historical = load_config_snapshot(database, snapshot.snapshot_id)
    assert (
        replay_stage_input(
            result.payload_bytes, result.fingerprint, snapshot=historical
        )
        == result
    )
    assert json.loads(result.payload_bytes)["facts"] == {
        "extraction_fingerprint": extraction.fingerprint,
        "reading_sha256": "2" * 64,
        "evidence_map_sha256": "3" * 64,
        "output_language": "zh",
    }


def inputs(
    root: Path, language: str = "zh"
) -> tuple[Path, Path, RuntimeConfigSnapshot, StageInput, ReadFacts]:
    settings, database = read_configuration(root)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    facts = ReadFacts(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        output_language=language,
    )
    return settings, database, snapshot, extraction, facts


@pytest.mark.parametrize(
    "field,value",
    [
        ("reading_sha256", "A" * 64),
        ("evidence_map_sha256", 1),
        ("output_language", "fr"),
        ("output_language", True),
        ("paper_id", "private"),
        ("purpose", "production"),
        ("artifact_id", "private"),
        ("extraction_fingerprint", "1" * 64),
    ],
)
def test_read_facts_reject_nonsemantic_extra_and_invalid_identity(
    tmp_path: Path, field: str, value: object
) -> None:
    _, _, _, extraction, _ = inputs(tmp_path)
    kwargs = dict(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        output_language="zh",
    )
    kwargs[field] = value
    with pytest.raises(StageInputError) as caught:
        ReadFacts(**kwargs)
    assert caught.value.reason in (BuildReason.INVALID_FACTS, BuildReason.INVALID_HASH)
    assert "private" not in str(caught.value)
    assert not {"paper_id", "purpose", "database", "query"} & set(
        inspect.signature(build_stage_input).parameters
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("extraction_fingerprint", "4" * 64),
        ("reading_sha256", "4" * 64),
        ("evidence_map_sha256", "4" * 64),
        ("output_language", "en"),
    ],
)
def test_read_identity_components_are_independent(
    tmp_path: Path, field: str, value: str
) -> None:
    _, _, snapshot, _, facts = inputs(tmp_path)
    before = build_stage_input(snapshot, StageName.READ, facts)
    payload = json.loads(before.payload_bytes)
    payload["facts"][field] = value
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    after = replay_stage_input(raw, hashlib.sha256(raw).hexdigest(), snapshot=snapshot)
    assert after.fingerprint != before.fingerprint


@pytest.mark.parametrize(
    "mutate", ["extra", "missing", "screening", "format", "newline", "duplicate"]
)
def test_read_replay_is_strict_and_does_not_keep_raw_input(
    tmp_path: Path, mutate: str
) -> None:
    _, _, snapshot, _, facts = inputs(tmp_path)
    before = build_stage_input(snapshot, StageName.READ, facts)
    payload = json.loads(before.payload_bytes)
    if mutate == "extra":
        payload["facts"]["private"] = "secret"
    if mutate == "missing":
        del payload["facts"]["output_language"]
    if mutate == "screening":
        payload["facts"] = {
            "title": "secret",
            "abstract": "secret",
            "abstract_truncated": False,
        }
    if mutate == "format":
        payload["format_version"] = True
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if mutate == "newline":
        raw += b"\n"
    if mutate == "duplicate":
        raw = raw.replace(
            b'"output_language":"zh"', b'"output_language":"en","output_language":"zh"'
        )
    with pytest.raises(StageInputError) as failure:
        replay_stage_input(raw, hashlib.sha256(raw).hexdigest())
    assert failure.value.reason in (
        ReplayReason.INVALID_PAYLOAD,
        ReplayReason.UNSUPPORTED_FORMAT,
        ReplayReason.NON_CANONICAL,
    )
    assert "secret" not in str(failure.value)


def test_pdf_changes_read_while_bibliographic_completion_cannot_enter_facts(
    tmp_path: Path,
) -> None:
    _, _, snapshot, extraction, facts = inputs(tmp_path)
    other = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="9" * 64)
    )
    assert other.fingerprint != extraction.fingerprint
    first = build_stage_input(snapshot, StageName.READ, facts)
    changed = ReadFacts(
        extraction_input=other,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        output_language="zh",
    )
    assert (
        build_stage_input(snapshot, StageName.READ, changed).fingerprint
        != first.fingerprint
    )
    with pytest.raises(StageInputError) as caught:
        ReadFacts(
            extraction_input=extraction,
            reading_sha256="2" * 64,
            evidence_map_sha256="3" * 64,
            output_language="zh",
            volume="12",
            pages="1-4",
        )
    assert caught.value.reason is BuildReason.INVALID_FACTS


def test_read_model_change_preserves_screening_calibration_and_historical_replay(
    tmp_path: Path,
) -> None:
    settings, database, snapshot, _, facts = inputs(tmp_path)
    old = build_stage_input(snapshot, StageName.READ, facts)
    new_yaml_version(
        settings,
        "models",
        lambda value: value["reading"].update(model="new-read-model"),
    )
    newer = compile_config(settings, database)
    assert (
        build_stage_input(newer, StageName.READ, facts).fingerprint != old.fingerprint
    )
    assert (
        project_config(newer).projections[StageName.VALUE]
        == project_config(snapshot).projections[StageName.VALUE]
    )
    assert project_config(newer).baseline == project_config(snapshot).baseline
    historical = load_config_snapshot(database, snapshot.snapshot_id)
    assert (
        replay_stage_input(old.payload_bytes, old.fingerprint, snapshot=historical)
        == old
    )
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(old.payload_bytes, old.fingerprint, snapshot=newer)
    assert caught.value.reason is ReplayReason.PROJECTION_MISMATCH


def test_read_facts_cannot_impersonate_other_stages(tmp_path: Path) -> None:
    _, _, snapshot, _, facts = inputs(tmp_path)
    cases: list[tuple[StageName, ScreeningFacts | ExtractionFacts | ReadFacts]] = [
        (StageName.BOUNDARY, facts),
        (StageName.EXTRACTION, facts),
        (StageName.READ, ExtractionFacts(pdf_sha256="1" * 64)),
        (
            StageName.READ,
            ScreeningFacts(title="t", abstract="a", abstract_truncated=False),
        ),
    ]
    for stage, wrong in cases:
        with pytest.raises(StageInputError) as caught:
            build_stage_input(snapshot, stage, wrong)
        assert caught.value.reason is BuildReason.INVALID_FACTS


@pytest.mark.parametrize("component", ["profile", "prompt", "adapter"])
def test_read_consumed_semantics_change_fingerprint(
    tmp_path: Path, component: str
) -> None:
    settings, database, snapshot, _, facts = inputs(tmp_path)
    before = build_stage_input(snapshot, StageName.READ, facts)
    if component == "profile":
        new_yaml_version(
            settings,
            "profile",
            lambda value: value.update(background="Changed background"),
        )
    elif component == "adapter":
        new_yaml_version(
            settings,
            "adapters.reading",
            lambda value: value.update(thinking_level="high"),
        )
    else:
        source = tmp_path / "prompts/reading/v1.md"
        source.with_name("v2.md").write_text("Changed Read prompt\n")
        settings.write_text(settings.read_text().replace("reading: v1", "reading: v2"))
    after = compile_config(settings, database)
    assert (
        build_stage_input(after, StageName.READ, facts).fingerprint
        != before.fingerprint
    )
    assert (
        replay_stage_input(
            before.payload_bytes,
            before.fingerprint,
            snapshot=load_config_snapshot(database, snapshot.snapshot_id),
        )
        == before
    )


@pytest.mark.parametrize("component", ["policy", "chunking"])
def test_unknown_read_render_semantics_are_rejected(
    tmp_path: Path, component: str
) -> None:
    from paper_radar.config import ConfigError

    settings, database = read_configuration(tmp_path)
    if component == "chunking":
        path = settings.parent / "read/read-v1.yaml"
        path.write_text("version: read-v1\nchunking_version: future\n")
        expected = "chunking_version"
    else:
        path = settings.parent / "adapters/pi-v1.yaml"
        path.write_text(path.read_text() + "policy:\n  version: future\n")
        expected = "policy.version"
    with pytest.raises(ConfigError, match=expected):
        compile_config(settings, database)
