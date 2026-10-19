"""四阶段通过同一公共 Interface 执行共同身份契约。"""

import builtins
import hashlib
import io
import json
import os
import socket
import sqlite3
import sqlite3.dbapi2
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from paper_radar.config import RuntimeConfigSnapshot, compile_config, project_config
from paper_radar.stage_inputs import (
    BuildReason,
    ExtractionFacts,
    ExtractionRef,
    ReplayReason,
    ReuseFacts,
    ScreeningFacts,
    SelectedExcerpt,
    SourceSnapshotRef,
    StageInputError,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)
from tests.config_projection_support import empty_inputs, full_inputs
from tests.stage_input_recovery_support import (
    rebuild_inputs,
    synthetic_members,
    synthetic_submission,
)

CASES = ("boundary", "value", "extraction", "structured", "body")


@pytest.fixture(scope="module")
def configured(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[RuntimeConfigSnapshot, Path]:
    settings, database = full_inputs(tmp_path_factory.mktemp("stage-common"))
    topics = settings.parent / "topics/topics-v1.yaml"
    topics.write_text(topics.read_text().replace("enabled: false", "enabled: true"))
    return compile_config(settings, database), database


@pytest.fixture(scope="module")
def vectors() -> dict[str, Any]:
    result = json.loads(
        (Path(__file__).parent / "fixtures/stage_inputs/recovery-v1.json").read_bytes()
    )
    assert isinstance(result, dict)
    return result


@pytest.mark.parametrize("case", CASES)
def test_all_stages_share_canonical_heads_round_trip_and_their_own_projection(
    configured: tuple[RuntimeConfigSnapshot, Path], vectors: dict[str, Any], case: str
) -> None:
    snapshot, database = configured
    before = database.read_bytes()
    value = rebuild_inputs(snapshot, synthetic_members(), synthetic_submission())[case]
    expected = vectors[case]
    assert value.payload_bytes == expected["payload"].encode("utf-8")
    assert value.fingerprint == expected["fingerprint"]
    payload = json.loads(value.payload_bytes)
    assert set(payload) == {
        "kind",
        "stage",
        "format_version",
        "config_projection",
        "facts",
    }
    assert payload["kind"] == "stage_input"
    assert payload["stage"] == value.stage.value
    assert type(payload["format_version"]) is int and value.format_version == 1
    assert (
        value.projection_id
        == project_config(snapshot).projections[value.stage].projection_id
    )
    replayed = replay_stage_input(
        value.payload_bytes, expected["fingerprint"], snapshot=snapshot
    )
    assert compare_stage_inputs(value, replayed).status == "same"
    assert database.read_bytes() == before


@pytest.mark.parametrize("case", CASES)
def test_all_stages_construct_replay_and_compare_without_io_or_private_output(
    configured: tuple[RuntimeConfigSnapshot, Path],
    case: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    snapshot, database = configured
    before = database.read_bytes()
    members = synthetic_members()
    submission = synthetic_submission()
    submission["screening"]["title"] = "PRIVATE_A5_TITLE"
    submission["excerpts"][0]["text"] = "PRIVATE_A5_EXCERPT"
    submission["excerpts"][0]["locator"][0] = "PRIVATE_A5_LOCATOR"

    def deny_io(*args: object, **kwargs: object) -> None:
        raise AssertionError("纯阶段输入操作不应执行 I/O")

    with monkeypatch.context() as sentinel:
        for owner, attribute in (
            (builtins, "open"),
            (io, "open"),
            (Path, "open"),
            (os, "open"),
            (sqlite3, "connect"),
            (sqlite3.dbapi2, "connect"),
            (socket, "socket"),
            (socket, "create_connection"),
        ):
            sentinel.setattr(owner, attribute, deny_io)
        value = rebuild_inputs(snapshot, members, submission)[case]
        replayed = replay_stage_input(
            value.payload_bytes, value.fingerprint, snapshot=snapshot
        )
        difference = compare_stage_inputs(value, replayed)
        assert difference.status == "same"
        with pytest.raises(StageInputError) as caught:
            replay_stage_input(b"PRIVATE_A5_INVALID_PAYLOAD", "0" * 64)
        assert caught.value.reason is ReplayReason.INVALID_PAYLOAD
        assert caught.value.__context__ is None
        assert "PRIVATE_A5" not in (
            repr(value)
            + repr(value.facts)
            + repr(difference)
            + repr(caught.value)
            + str(caught.value)
        )
        with pytest.raises(FrozenInstanceError):
            value.format_version = 2  # type: ignore[misc]
        assert value.format_version == 1
        attribute = (
            "title"
            if isinstance(value.facts, ScreeningFacts)
            else "pdf_sha256"
            if isinstance(value.facts, ExtractionFacts)
            else "excerpts"
        )
        with pytest.raises(FrozenInstanceError):
            setattr(value.facts, attribute, "PRIVATE_A5_CHANGE")
        submission["screening"]["title"] = "CHANGED"
        submission["excerpts"].reverse()
        submission["excerpts"][1]["locator"].append("CHANGED")
        assert compare_stage_inputs(value, replayed).status == "same"
        assert value.fingerprint == replayed.fingerprint
    assert database.read_bytes() == before
    assert capsys.readouterr() == ("", "")
    assert not caplog.records


@pytest.fixture(scope="module")
def unconfigured(tmp_path_factory: pytest.TempPathFactory) -> RuntimeConfigSnapshot:
    settings, database = empty_inputs(tmp_path_factory.mktemp("stage-missing"))
    return compile_config(settings, database)


@pytest.mark.parametrize("case", CASES)
def test_all_stages_preserve_their_own_missing_configuration_reason(
    configured: tuple[RuntimeConfigSnapshot, Path],
    unconfigured: RuntimeConfigSnapshot,
    case: str,
) -> None:
    value = rebuild_inputs(configured[0], synthetic_members(), synthetic_submission())[
        case
    ]
    with pytest.raises(StageInputError) as caught:
        build_stage_input(unconfigured, value.stage, value.facts)
    assert caught.value.reason is BuildReason.NOT_READY
    assert caught.value.readiness is unconfigured.stages[value.stage]


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("kind", ReplayReason.INVALID_PAYLOAD),
        ("extra", ReplayReason.INVALID_PAYLOAD),
        ("stage", ReplayReason.UNSUPPORTED_STAGE),
        ("stage_format", ReplayReason.UNSUPPORTED_FORMAT),
        ("bool_format", ReplayReason.UNSUPPORTED_FORMAT),
        ("projection_format", ReplayReason.PROJECTION_FORMAT_UNVERIFIABLE),
        ("projection_hash", ReplayReason.INVALID_PAYLOAD),
        ("fingerprint", ReplayReason.FINGERPRINT_MISMATCH),
        ("hash_encoding", ReplayReason.INVALID_FINGERPRINT),
        ("whitespace", ReplayReason.NON_CANONICAL),
    ],
)
def test_all_stages_share_strict_head_format_hash_and_encoding_checks(
    vectors: dict[str, Any], case: str, damage: str, reason: ReplayReason
) -> None:
    original = vectors[case]["payload"].encode("utf-8")
    payload = json.loads(original)
    if damage == "kind":
        payload["kind"] = "PRIVATE_A5_KIND"
    elif damage == "extra":
        payload["PRIVATE_A5_FIELD"] = "PRIVATE_A5_VALUE"
    elif damage == "stage":
        payload["stage"] = "PRIVATE_A5_STAGE"
    elif damage in {"stage_format", "bool_format"}:
        payload["format_version"] = True if damage == "bool_format" else 2
    elif damage == "projection_format":
        payload["config_projection"]["format_version"] = 2
    elif damage == "projection_hash":
        payload["config_projection"]["projection_id"] = "PRIVATE_A5_HASH"
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if damage == "whitespace":
        raw += b"\n"
    fingerprint = hashlib.sha256(raw).hexdigest()
    if damage == "fingerprint":
        fingerprint = "0" * 64
    elif damage == "hash_encoding":
        fingerprint = fingerprint.upper()
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(raw, fingerprint)
    assert caught.value.reason is reason
    assert caught.value.__context__ is None
    assert "PRIVATE_A5" not in repr(caught.value) + str(caught.value)


@pytest.mark.parametrize(
    "field",
    [
        "authors",
        "volume",
        "pages",
        "url",
        "observed_at",
        "paper_id",
        "supply_id",
        "install_id",
        "tree_sha256",
        "session_id",
    ],
)
@pytest.mark.parametrize(
    "entity", ["screening", "extraction", "reuse", "structured", "body", "excerpt"]
)
def test_bibliographic_and_execution_audit_fields_are_outside_closed_input_types(
    configured: tuple[RuntimeConfigSnapshot, Path], field: str, entity: str
) -> None:
    members = synthetic_members()
    inputs = rebuild_inputs(configured[0], members, synthetic_submission())
    facts = inputs["structured"].facts
    assert isinstance(facts, ReuseFacts)
    factories: dict[str, tuple[Callable[..., object], dict[str, Any]]] = {
        "screening": (ScreeningFacts, synthetic_submission()["screening"]),
        "extraction": (ExtractionFacts, {"pdf_sha256": members["pdf"]["payload"]}),
        "reuse": (ReuseFacts, {"excerpts": facts.excerpts}),
        "structured": (
            SourceSnapshotRef,
            {"content_sha256": members["structured"]["payload"], "locator": ["block"]},
        ),
        "body": (
            ExtractionRef,
            {
                "extraction_input": inputs["extraction"],
                "reading_sha256": members["body"]["reading"],
                "evidence_map_sha256": members["body"]["evidence_map"],
                "locator": ["block"],
            },
        ),
        "excerpt": (
            SelectedExcerpt,
            {
                "excerpt_id": "id",
                "kind": "methods",
                "text": "PRIVATE_A5_TEXT",
                "source": facts.excerpts[0].source,
            },
        ),
    }
    construct, kwargs = factories[entity]
    with pytest.raises(StageInputError) as caught:
        construct(**kwargs, **{field: "PRIVATE_A5_AUDIT"})
    assert caught.value.reason is BuildReason.INVALID_FACTS
    assert caught.value.__context__ is None
    assert "PRIVATE_A5" not in repr(caught.value) + str(caught.value)
