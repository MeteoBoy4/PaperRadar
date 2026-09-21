from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_radar.contracts import ContractName, ContractVersion, build_frozen_contract
from paper_radar.screening import (
    BoundaryOutput,
    ReuseAssessmentOutput,
    ValuePredictionOutput,
    screening_reason_json_schema,
)

_CONTRACT_CASES = (
    (ContractName.BOUNDARY, "boundary", BoundaryOutput),
    (ContractName.VALUE_PREDICTION, "value-prediction", ValuePredictionOutput),
    (ContractName.REUSE_ASSESSMENT, "reuse-assessment", ReuseAssessmentOutput),
)


def test_boundary_contract_is_generated_deterministically_from_model() -> None:
    contract = build_frozen_contract(ContractName.BOUNDARY, ContractVersion.V1)

    assert (
        contract.schema_sha256
        == "9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7"
    )
    assert contract.snapshot_parts == ("screening", "boundary", "v1")
    assert contract.schema_filename == "schema.json"
    assert contract.manifest_filename == "manifest.json"

    schema = json.loads(contract.schema_bytes)
    assert set(schema["properties"]) == set(BoundaryOutput.model_fields)
    assert schema["x-paper-radar-contract"] == {
        "name": "boundary",
        "version": "v1",
    }
    manifest = json.loads(contract.manifest_bytes)
    assert manifest == {
        "contract": "boundary",
        "format_version": 1,
        "schema_file": "schema.json",
        "schema_sha256": contract.schema_sha256,
        "version": "v1",
    }
    assert contract.manifest_bytes.endswith(b"\n")


def test_committed_boundary_snapshot_matches_authoritative_contract() -> None:
    contract = build_frozen_contract(ContractName.BOUNDARY, ContractVersion.V1)
    snapshot_dir = (
        Path(__file__).parents[1] / "contracts" / "screening" / "boundary" / "v1"
    )

    assert (snapshot_dir / "schema.json").read_bytes() == contract.schema_bytes
    assert (snapshot_dir / "manifest.json").read_bytes() == contract.manifest_bytes


@pytest.mark.parametrize(("name", "directory", "model"), _CONTRACT_CASES)
def test_output_contracts_are_generated_from_authoritative_models(
    name: ContractName,
    directory: str,
    model: type[BoundaryOutput | ValuePredictionOutput | ReuseAssessmentOutput],
) -> None:
    contract = build_frozen_contract(name, ContractVersion.V1)
    schema = json.loads(contract.schema_bytes)

    assert contract.snapshot_parts == ("screening", directory, "v1")
    assert set(schema["properties"]) == set(model.model_fields)
    assert schema["x-paper-radar-contract"] == {
        "name": directory,
        "version": "v1",
    }


def test_decision_reason_contract_preserves_authoritative_legal_combinations() -> None:
    contract = build_frozen_contract(
        ContractName.DECISION_REASONS,
        ContractVersion.V1,
    )
    schema = json.loads(contract.schema_bytes)
    identity_fields = {"$schema", "$id", "x-paper-radar-contract"}
    authoritative_schema = screening_reason_json_schema()

    assert contract.snapshot_parts == ("screening", "decision-reasons", "v1")
    assert {
        key: value for key, value in schema.items() if key not in identity_fields
    } == (authoritative_schema)
    assert schema["x-paper-radar-contract"] == {
        "name": "decision-reasons",
        "version": "v1",
    }


@pytest.mark.parametrize("name", tuple(ContractName))
def test_committed_snapshots_match_every_authoritative_contract(
    name: ContractName,
) -> None:
    contract = build_frozen_contract(name, ContractVersion.V1)
    snapshot_dir = (
        Path(__file__).parents[1] / "contracts" / Path(*contract.snapshot_parts)
    )

    assert (snapshot_dir / "schema.json").read_bytes() == contract.schema_bytes
    assert (snapshot_dir / "manifest.json").read_bytes() == contract.manifest_bytes


def test_frozen_schemas_exclude_forbidden_outputs_and_runtime_context() -> None:
    serialized_schemas = b"\n".join(
        build_frozen_contract(name, ContractVersion.V1).schema_bytes
        for name in ContractName
    )

    for forbidden_name in (
        b"journal_reputation",
        b"rank",
        b"priority",
        b"urgency",
        b"free_tags",
        b"topic_weights",
        b"confidence",
        b"enabled_topic_ids",
        b"original_title_is_zh",
        b"excerpt_kinds",
    ):
        assert forbidden_name not in serialized_schemas
