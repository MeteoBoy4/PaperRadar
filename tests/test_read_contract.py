from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from paper_radar.contracts import (
    ContractCheckError,
    ContractCheckErrorCategory,
    ContractExportError,
    ContractExportErrorCategory,
    ContractName,
    ContractVersion,
    ExportOutcome,
    build_frozen_contract,
    check_frozen_contract,
    check_frozen_contracts,
    export_frozen_contract,
    export_frozen_contracts,
)
from paper_radar.reading import (
    VALUE_TYPE_DESCRIPTIONS_ZH,
    ReadAnalysisOutput,
    ValueType,
)
from scripts.offline_evidence import Check, run_offline_verification
from tests.contract_snapshot_support import canonical_json_bytes


def test_read_contract_has_complete_authoritative_shape_and_identity() -> None:
    contract = build_frozen_contract(ContractName.READ, ContractVersion.V1)
    schema = json.loads(contract.schema_bytes)

    assert contract.snapshot_parts == ("read", "read", "v1")
    assert schema["$id"] == "urn:paper-radar:contracts:read:read:v1"
    fields = {
        "output_language",
        "one_sentence_conclusion",
        "research_question",
        "methods_summary",
        "data_summary",
        "main_findings",
        "research_value",
        "research_value_reason",
        "reuse_feasibility",
        "reuse_feasibility_reason",
        "required_adaptations",
        "reusable_points",
        "key_limitations",
        "open_questions",
        "value_types",
        "why_it_matters",
        "next_action",
        "degraded_content_warnings",
    }
    assert set(schema["properties"]) == fields
    assert set(schema["required"]) == fields
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["EvidenceRef"]["properties"] == {
        "evidence_id": {"minLength": 1, "title": "Evidence Id", "type": "string"},
    }
    assert set(schema["$defs"]["SupportedStatement"]["required"]) == {
        "statement",
        "evidence",
    }
    assert set(schema["$defs"]["ReusablePoint"]["required"]) == {
        "item",
        "how_to_reuse",
        "evidence",
    }
    assert schema["properties"]["research_value"]["minimum"] == 1
    assert schema["properties"]["research_value"]["maximum"] == 5


def test_read_value_vocabulary_and_model_descriptions_are_frozen_independently() -> (
    None
):
    # Read 冻结时与 Screening v1 相等, 此历史向量不跟随将来的 Screening 枚举。
    assert {
        item.value: label for item, label in VALUE_TYPE_DESCRIPTIONS_ZH.items()
    } == {
        "method": "方法",
        "data": "数据",
        "code_tool": "代码/工具",
        "theory_mechanism": "理论/机制",
        "evidence_conclusion": "证据/结论",
        "question_hypothesis": "问题/假设",
        "review_knowledge_map": "综述/知识地图",
    }
    assert len(ValueType) == 7
    contract = build_frozen_contract(ContractName.READ, ContractVersion.V1)
    schema = json.loads(contract.schema_bytes)
    assert schema["description"] == "Read 阶段的全文精读分析。"
    assert (
        schema["$defs"]["ValueType"]["description"]
        == "精读分析允许返回的七类受控价值。"
    )
    assert (
        schema["properties"]["value_types"]["description"]
        == "精读分析允许返回的七类受控价值。"
    )
    assert schema["$defs"]["EvidenceRef"]["description"] == "精读分析对单条证据的引用。"
    assert (
        schema["$defs"]["SupportedStatement"]["description"]
        == "具有证据引用的精读陈述。"
    )
    assert (
        schema["$defs"]["ReusablePoint"]["description"]
        == "共用自身证据引用的可复用内容及其使用方式。"
    )
    for forbidden in (
        b"provenance",
        b"extraction_fingerprint",
        b"verified",
        b"diagnostic",
        b"rank",
        b"priority",
        b"urgency",
        b"topic",
        b"mode",
        b"allowed_evidence",
    ):
        assert forbidden not in contract.schema_bytes


def _read_data() -> dict[str, object]:
    reason = {"statement": "提供了适用的方法。", "evidence": [{"evidence_id": "e-1"}]}
    return {
        "output_language": "zh",
        "one_sentence_conclusion": "提出了新的方法。",
        "research_question": "如何估计预测误差？",
        "methods_summary": "比较独立预测。",
        "data_summary": "未使用观测数据。",
        "main_findings": [],
        "research_value": 2,
        "research_value_reason": reason,
        "reuse_feasibility": 2,
        "reuse_feasibility_reason": reason,
        "required_adaptations": [],
        "reusable_points": [],
        "key_limitations": [],
        "open_questions": [],
        "value_types": [],
        "why_it_matters": "提供了方法比较。",
        "next_action": "检查研究假设。",
        "degraded_content_warnings": [],
    }


def test_read_model_accepts_all_required_fields_with_optional_empty_lists() -> None:
    candidate = _read_data()
    result = ReadAnalysisOutput.model_validate(candidate)

    assert result.model_dump(mode="json") == candidate


@pytest.mark.parametrize("field", ["research_value", "reuse_feasibility"])
@pytest.mark.parametrize("invalid", [True, False, 0, 6, 2.0, "2"])
def test_read_scores_reject_coercion_and_values_outside_one_to_five(
    field: str,
    invalid: object,
) -> None:
    candidate = _read_data()
    candidate[field] = invalid
    with pytest.raises(ValidationError) as captured:
        ReadAnalysisOutput.model_validate(candidate)
    assert captured.value.errors()[0]["loc"] == (field,)
    assert captured.value.errors()[0]["type"] in {
        "int_type",
        "greater_than_equal",
        "less_than_equal",
    }


@pytest.mark.parametrize("field", tuple(_read_data()))
def test_read_model_requires_each_field_without_defaults(field: str) -> None:
    candidate = _read_data()
    del candidate[field]
    with pytest.raises(ValidationError) as captured:
        ReadAnalysisOutput.model_validate(candidate)
    assert captured.value.errors()[0]["loc"] == (field,)
    assert captured.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize("field", ["verified", "rank", "topic_ids", "decision"])
def test_read_model_rejects_fields_outside_its_closed_shape(field: str) -> None:
    candidate = _read_data()
    candidate[field] = "synthetic-secret"
    with pytest.raises(ValidationError) as captured:
        ReadAnalysisOutput.model_validate(candidate)
    assert captured.value.errors()[0]["loc"] == (field,)
    assert captured.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("field", "invalid", "reason"),
    [
        ("one_sentence_conclusion", 2, "string_type"),
        ("research_question", True, "string_type"),
        ("main_findings", (), "list_type"),
        ("required_adaptations", [2], "string_type"),
        ("open_questions", "a question", "list_type"),
        ("value_types", [1], "value_error"),
        ("value_types", ["other"], "value_error"),
        ("degraded_content_warnings", [False], "string_type"),
    ],
)
def test_read_model_rejects_coercion_outside_scores(
    field: str,
    invalid: object,
    reason: str,
) -> None:
    candidate = _read_data()
    candidate[field] = invalid
    with pytest.raises(ValidationError) as captured:
        ReadAnalysisOutput.model_validate(candidate)
    assert captured.value.errors()[0]["loc"][0] == field
    assert captured.value.errors()[0]["type"] == reason


@pytest.mark.parametrize("score", [1, 5])
def test_read_scores_accept_exact_boundaries(score: int) -> None:
    candidate = _read_data()
    candidate["research_value"] = score
    candidate["reuse_feasibility"] = score
    candidate["value_types"] = ["method"]
    model = ReadAnalysisOutput.model_validate(candidate)
    assert model.research_value == score
    assert model.reuse_feasibility == score


def test_read_nested_models_reject_omitted_and_extra_fields() -> None:
    candidate = _read_data()
    candidate["reusable_points"] = [{"item": "可复用方法", "evidence": []}]
    candidate["research_value_reason"] = {
        "statement": "方法适用于本研究。",
        "evidence": [{"evidence_id": "e-1", "verified": True}],
    }
    with pytest.raises(ValidationError) as captured:
        ReadAnalysisOutput.model_validate(candidate)
    assert {(error["loc"], error["type"]) for error in captured.value.errors()} == {
        (("research_value_reason", "evidence", 0, "verified"), "extra_forbidden"),
        (("reusable_points", 0, "how_to_reuse"), "missing"),
        (("reusable_points", 0, "evidence"), "too_short"),
    }


def test_read_freeze_is_identical_in_repository_and_example_roots() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = build_frozen_contract(ContractName.READ, ContractVersion.V1)
    for directory in (root / "contracts", root / "examples" / "contracts"):
        snapshot = directory.joinpath(*contract.snapshot_parts)
        assert (snapshot / "schema.json").read_bytes() == contract.schema_bytes
        assert (snapshot / "manifest.json").read_bytes() == contract.manifest_bytes


def test_read_models_keep_content_out_of_default_representations() -> None:
    candidate = _read_data()
    candidate["one_sentence_conclusion"] = "synthetic-secret-model-content"
    model = ReadAnalysisOutput.model_validate(candidate)
    assert "synthetic-secret" not in repr(model)
    assert "synthetic-secret" not in str(model)
    assert "e-1" not in repr(model.research_value_reason)
    assert "e-1" not in str(model.research_value_reason.evidence[0])


@pytest.mark.parametrize("language", ["zh", "en"])
def test_read_contract_exports_and_checks_without_rewriting(
    tmp_path: Path,
    language: str,
) -> None:
    candidate = _read_data()
    candidate["output_language"] = language
    candidate["value_types"] = ["method"]
    assert ReadAnalysisOutput.model_validate(candidate).output_language == language
    first = export_frozen_contract("read", "v1", tmp_path)
    paths = [first.snapshot_dir / name for name in ("schema.json", "manifest.json")]
    mtimes = [path.stat().st_mtime_ns for path in paths]
    assert first.outcome is ExportOutcome.CREATED
    assert (
        export_frozen_contract("read", "v1", tmp_path).outcome
        is ExportOutcome.UNCHANGED
    )
    assert (
        check_frozen_contract("read", "v1", tmp_path).schema_sha256
        == first.schema_sha256
    )
    assert [path.stat().st_mtime_ns for path in paths] == mtimes


def test_read_contract_can_be_exported_and_checked_with_historical_contracts(
    tmp_path: Path,
) -> None:
    names = (
        "read",
        "decision-reasons",
        "reuse-assessment",
        "value-prediction",
        "boundary",
    )
    result = export_frozen_contracts(names, "v1", tmp_path)
    assert result.passed
    assert [item.name.value for item in result.items] == [
        "boundary",
        "value-prediction",
        "reuse-assessment",
        "decision-reasons",
        "read",
    ]
    assert check_frozen_contracts(names, "v1", tmp_path).passed


@pytest.mark.parametrize("member", ["schema.json", "manifest.json"])
def test_read_contract_missing_member_is_rejected_without_repair(
    tmp_path: Path,
    member: str,
) -> None:
    exported = export_frozen_contract("read", "v1", tmp_path)
    missing = exported.snapshot_dir / member
    missing.unlink()
    with pytest.raises(ContractCheckError) as checked:
        check_frozen_contract("read", "v1", tmp_path)
    assert checked.value.category is ContractCheckErrorCategory.MISSING_SNAPSHOT
    with pytest.raises(ContractExportError) as published:
        export_frozen_contract("read", "v1", tmp_path)
    assert published.value.category is ContractExportErrorCategory.DAMAGED_SNAPSHOT
    assert not missing.exists()


@pytest.mark.parametrize("damage", ["manifest", "same-version-content"])
def test_read_contract_rejects_bad_manifest_and_same_version_replacement(
    tmp_path: Path,
    damage: str,
) -> None:
    exported = export_frozen_contract("read", "v1", tmp_path)
    schema_path = exported.snapshot_dir / "schema.json"
    manifest_path = exported.snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if damage == "manifest":
        manifest["schema_sha256"] = "0" * 64
        expected_check = ContractCheckErrorCategory.DAMAGED_SNAPSHOT
        expected_export = ContractExportErrorCategory.DAMAGED_SNAPSHOT
    else:
        schema = json.loads(schema_path.read_bytes())
        schema["description"] = "另一份内容"
        changed = canonical_json_bytes(schema)
        schema_path.write_bytes(changed)
        manifest["schema_sha256"] = hashlib.sha256(changed).hexdigest()
        expected_check = ContractCheckErrorCategory.CONTENT_DRIFT
        expected_export = ContractExportErrorCategory.CONTENT_CONFLICT
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    before = (schema_path.read_bytes(), manifest_path.read_bytes())
    with pytest.raises(ContractCheckError) as checked:
        check_frozen_contract("read", "v1", tmp_path)
    assert checked.value.category is expected_check
    with pytest.raises(ContractExportError) as published:
        export_frozen_contract("read", "v1", tmp_path)
    assert published.value.category is expected_export
    assert (schema_path.read_bytes(), manifest_path.read_bytes()) == before


def test_read_contract_publication_failure_can_be_retried_without_partial_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt_publish(source: Path, destination: Path) -> None:
        raise OSError("synthetic-secret-interruption")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", interrupt_publish)
        with pytest.raises(ContractExportError) as captured:
            export_frozen_contract("read", "v1", tmp_path)
        assert captured.value.category is ContractExportErrorCategory.WRITE_FAILED
        assert "synthetic-secret" not in str(captured.value)
    assert not (tmp_path / "read" / "read" / "v1").exists()
    assert (
        export_frozen_contract("read", "v1", tmp_path).outcome is ExportOutcome.CREATED
    )
    assert check_frozen_contract("read", "v1", tmp_path).name is ContractName.READ


def test_read_contract_is_deterministic_in_an_independent_process(
    tmp_path: Path,
) -> None:
    entrypoint = Path(sys.executable).with_name("paper-radar")
    result = subprocess.run(
        [
            str(entrypoint),
            "contracts",
            "export",
            "--contract",
            "read",
            "--version",
            "v1",
            "--target",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    contract = build_frozen_contract(ContractName.READ, ContractVersion.V1)
    assert (
        tmp_path / "read" / "read" / "v1" / "schema.json"
    ).read_bytes() == contract.schema_bytes


def test_read_metadata_uses_registered_area_without_expanding_historical_plan(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    _path, evidence = run_offline_verification(
        root,
        (Check("fixture_pass", (sys.executable, "-c", "pass")),),
        tmp_path,
        contract_names=("read",),
    )
    assert evidence["contracts"] == [
        {
            "name": "read",
            "version": "v1",
            "schema_sha256": (
                "1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111"
            ),
        }
    ]
