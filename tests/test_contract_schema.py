from __future__ import annotations

import json
from pathlib import Path

from paper_radar.contracts import ContractName, ContractVersion, build_frozen_contract
from paper_radar.screening import BoundaryOutput


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
