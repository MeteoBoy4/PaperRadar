"""Body D1:持久正文的单次 Read 准备,不调用执行器。"""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest

from paper_radar.config import RuntimeConfigSnapshot, StageName, compile_config
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.models import FulltextError, PublishedExtraction
from paper_radar.llm import CallDescriptionError, DescriptionReason, render_request
from paper_radar.llm.rpc import validate_request
from paper_radar.llm.rpc_frames import command_frame
from paper_radar.read_inputs import (
    PreparedReadInput,
    build_read_correction,
    prepare_read_input,
    read_input_budget,
)
from paper_radar.reading.acceptance_v2 import ReadV2Category, ReadV2Issue
from paper_radar.stage_inputs import ExtractionFacts, StageInput, build_stage_input
from paper_radar.storage.artifacts import ArtifactStore
from tests.test_fulltext_artifacts import document
from tests.test_read_stage_input import read_configuration


def test_prepare_reads_registered_members_and_preflights_context(
    tmp_path: Path,
) -> None:
    settings, database = read_configuration(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    artifacts = FulltextArtifacts(ArtifactStore(database, tmp_path / "data"))
    saved = artifacts.publish(
        document(),
        extraction_fingerprint=extraction.fingerprint,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=0,
        peak_memory_bytes=0,
    )
    prepared = prepare_read_input(
        artifacts,
        saved.artifact_id,
        extraction,
        snapshot,
        snapshot,
        expected_identity=saved.identity,
    )
    assert prepared.budget.accepted
    assert prepared.context.identity == saved.identity
    assert prepared.description.stage == "read"
    request = json.loads(prepared.description.user_payload_json)
    assert (
        request["body"]["reading"]
        == "[evidence:e000001]\n# Results\n\n[evidence:e000002]\nExact source α = 2.\n"
    )
    assert request["body"]["evidence"][1]["pages"] == [1]
    assert request["output_language"] == "zh"
    assert "paper" not in request


def test_budget_reserves_worst_second_frame_before_first_claim(tmp_path: Path) -> None:
    settings, database = read_configuration(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    artifacts = FulltextArtifacts(ArtifactStore(database, tmp_path / "data"))
    saved = artifacts.publish(
        document(),
        extraction_fingerprint=extraction.fingerprint,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=0,
        peak_memory_bytes=0,
    )
    prepared = prepare_read_input(
        artifacts,
        saved.artifact_id,
        extraction,
        snapshot,
        snapshot,
        expected_identity=saved.identity,
    )
    # 独立的小型完整外层帧:四字节 emoji + 中文,有两层引号/换行转义。
    literal = replace(
        prepared.description, user_payload_json='{"correction":null,"text":"中😀"}'
    )
    assert read_input_budget(literal).first_frame_bytes == 113
    # 边界按实际 UTF-8 字节计,一字节超限不得留待第二次领取。
    base = replace(
        prepared.description, user_payload_json='{"correction":null,"text":""}'
    )
    size = read_input_budget(base).correction_frame_bytes
    padding = 262144 - size
    accepted = replace(
        base,
        user_payload_json=json.dumps(
            {"correction": None, "text": "中😀" * (padding // 7) + "x" * (padding % 7)},
            separators=(",", ":"),
        ),
    )
    assert read_input_budget(accepted).correction_frame_bytes == 262144
    assert read_input_budget(accepted).accepted
    assert read_input_budget(accepted).first_frame_bytes == 178176
    assert read_input_budget(accepted).cumulative_frame_bytes == 440320
    rejected = replace(
        accepted,
        user_payload_json=accepted.user_payload_json.replace('"text":"', '"text":"x'),
    )
    result = read_input_budget(rejected)
    assert not result.accepted
    assert result.reason == "read_input_over_budget"
    assert read_input_budget(rejected) == result
    assert (
        validate_request(render_request(rejected)) is None
    )  # 第一次仍可发,因此必须预留。
    worst = '"' * 83968
    with pytest.raises(CallDescriptionError) as failure:
        render_request(accepted, worst)
    assert failure.value.reason is DescriptionReason.INVALID_CONTEXT


def prepared_input(
    root: Path, *, text: str | None = None, language: Literal["zh", "en"] = "zh"
) -> tuple[
    FulltextArtifacts,
    PublishedExtraction,
    StageInput,
    RuntimeConfigSnapshot,
    PreparedReadInput,
]:
    settings, database = read_configuration(root)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    artifacts = FulltextArtifacts(ArtifactStore(database, root / "data"))
    doc = document()
    if text is not None:
        block = doc.blocks[1]
        provenance = block.provenance[0].model_copy(update={"charspan": (0, len(text))})
        block = block.model_copy(
            update={"orig": text, "text": text, "provenance": (provenance,)}
        )
        doc = doc.model_copy(update={"blocks": (doc.blocks[0], block)})
    saved = artifacts.publish(
        doc,
        extraction_fingerprint=extraction.fingerprint,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=0,
        peak_memory_bytes=0,
    )
    return (
        artifacts,
        saved,
        extraction,
        snapshot,
        prepare_read_input(
            artifacts,
            saved.artifact_id,
            extraction,
            snapshot,
            snapshot,
            expected_identity=saved.identity,
            output_language=language,
        ),
    )


def test_worst_controlled_correction_is_bounded_and_sensitive_paths_are_folded(
    tmp_path: Path,
) -> None:
    _, _, _, _, prepared = prepared_input(tmp_path)
    long_path = (
        "$.main_findings[1234567890123456789].evidence[1234567890123456789].evidence_id"
    )
    issues = tuple(ReadV2Issue(long_path, category) for category in ReadV2Category)
    correction = build_read_correction(issues)
    assert len(ReadV2Category) == 36
    message = render_request(prepared.description, correction)
    assert validate_request(message) is None
    frame = command_frame("rpc-9", "prompt", message=message.decode())
    assert len(frame) <= prepared.budget.correction_frame_bytes
    assert len(correction.splitlines()) == 37
    folded = build_read_correction(
        (
            ReadV2Issue("$.secret_payload", ReadV2Category.EXTRA_FIELD),
            ReadV2Issue("$." + "x" * 193, ReadV2Category.INVALID_TEXT),
        )
    )
    assert "secret" not in folded
    assert "extra_field: $" in folded
    assert "invalid_text: $" in folded
    assert build_read_correction(reversed(issues)) == correction


def test_over_budget_preparation_is_recomputable_without_database_writes(
    tmp_path: Path,
) -> None:
    artifacts, saved, extraction, snapshot, prepared = prepared_input(
        tmp_path, text="正文😀" * 25000
    )
    assert prepared.budget.reason == "read_input_over_budget"
    database = tmp_path / "db.sqlite3"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    repeated = prepare_read_input(
        artifacts,
        saved.artifact_id,
        extraction,
        snapshot,
        snapshot,
        expected_identity=saved.identity,
    )
    assert repeated.budget == prepared.budget
    assert repeated.description == prepared.description
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert (
        len(json.loads(prepared.description.user_payload_json)["body"]["reading"])
        > 75000
    )


def test_prepare_rejects_swapped_body_identity_before_call(tmp_path: Path) -> None:
    artifacts, saved, extraction, snapshot, _ = prepared_input(tmp_path)
    wrong = replace(saved.identity, evidence_map_sha256="f" * 64)
    with pytest.raises(FulltextError) as caught:
        prepare_read_input(
            artifacts,
            saved.artifact_id,
            extraction,
            snapshot,
            snapshot,
            expected_identity=wrong,
        )
    assert caught.value.reason == "identity_mismatch"


def test_no_extra_import_when_preparing_persisted_read(tmp_path: Path) -> None:
    # 冷进程执行真实公共准备服务,阻止 SDK 导入,不是只检查 import 语句。
    code = """
import importlib.abc, sys
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'docling', 'docling_core', 'torch', 'transformers'}:
   raise AssertionError('forbidden SDK import')
sys.meta_path.insert(0, Deny())
from pathlib import Path
from tests.test_read_inputs import prepared_input
prepared = prepared_input(Path(sys.argv[1]))[-1]
assert prepared.budget.accepted
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_generated_formula_and_placeholder_have_no_evidence_anchor(
    tmp_path: Path,
) -> None:
    from paper_radar.fulltext.canonical import CanonicalBlock, CanonicalProvenance

    settings, database = read_configuration(tmp_path)
    snapshot = compile_config(settings, database)
    extraction = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    artifacts = FulltextArtifacts(ArtifactStore(database, tmp_path / "data"))
    doc = document()
    candidate = CanonicalBlock(
        ref="#/texts/2",
        order=(2,),
        label="formula",
        orig="",
        text="",
        generated_text="[evidence:spoof] x^2",
        provenance=(
            CanonicalProvenance(
                page_no=1, bbox=(20.0, 100.0, 500.0, 130.0), charspan=(0, 0)
            ),
        ),
    )
    doc = doc.model_copy(update={"blocks": (*doc.blocks, candidate)})
    saved = artifacts.publish(
        doc,
        extraction_fingerprint=extraction.fingerprint,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=0,
        peak_memory_bytes=0,
    )
    result = prepare_read_input(
        artifacts,
        saved.artifact_id,
        extraction,
        snapshot,
        snapshot,
        expected_identity=saved.identity,
    )
    body = json.loads(result.description.user_payload_json)["body"]
    assert len(body["evidence"]) == 2
    assert "公式不可用" in body["reading"]
    assert "[生成候选，非证据]" in body["reading"]
    assert "[evidence:spoof]" not in body["reading"]
    assert "[evidence:e000003]" not in body["reading"]


def test_read_language_is_independent_and_historical_configuration_replays(
    tmp_path: Path,
) -> None:
    from paper_radar.config import load_config_snapshot
    from tests.config_projection_support import new_yaml_version

    artifacts, saved, extraction, snapshot, zh = prepared_input(tmp_path)
    en = prepare_read_input(
        artifacts,
        saved.artifact_id,
        extraction,
        snapshot,
        snapshot,
        expected_identity=saved.identity,
        output_language="en",
    )
    assert en.stage_input.fingerprint != zh.stage_input.fingerprint
    assert en.context.expected_language == "en"
    settings = tmp_path / "config/settings.yaml"
    new_yaml_version(
        settings, "models", lambda value: value["reading"].update(model="new-read")
    )
    compile_config(settings, tmp_path / "db.sqlite3")
    old = load_config_snapshot(tmp_path / "db.sqlite3", snapshot.snapshot_id)
    repeated = prepare_read_input(
        artifacts,
        saved.artifact_id,
        extraction,
        old,
        old,
        expected_identity=saved.identity,
    )
    assert repeated == zh


def test_read_request_has_independent_frozen_utf8_vector(tmp_path: Path) -> None:
    _, _, _, _, prepared = prepared_input(tmp_path)
    fixture = Path(__file__).parent / "fixtures/read_inputs"
    request = (fixture / "read-request-v1.txt").read_bytes()
    frame = (fixture / "rpc9-read-v1.jsonl").read_bytes()
    assert render_request(prepared.description) == request
    assert command_frame("rpc-9", "prompt", message=request.decode()) == frame
    assert prepared.budget.first_frame_bytes == len(frame)


def test_receiving_rule_version_changes_do_not_change_model_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.reading import acceptance_v2

    artifacts, saved, extraction, snapshot, original = prepared_input(tmp_path)
    monkeypatch.setattr(acceptance_v2, "EVIDENCE_RULE_VERSION", "future-evidence")
    monkeypatch.setattr(acceptance_v2, "NUMERIC_RULE_VERSION", "future-numeric")
    monkeypatch.setattr(
        acceptance_v2, "CONTENT_LIMITATION_RULE_VERSION", "future-warning"
    )
    repeated = prepare_read_input(
        artifacts,
        saved.artifact_id,
        extraction,
        snapshot,
        snapshot,
        expected_identity=saved.identity,
    )
    assert repeated.stage_input == original.stage_input
    assert repeated.description == original.description
    assert repeated.budget == original.budget
