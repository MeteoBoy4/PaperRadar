from __future__ import annotations

import json
from pathlib import Path

from paper_radar.contracts import ContractName, ContractVersion, build_frozen_contract

EXPECTED_BOUNDARY_SCHEMA = """{
  "$id": "urn:paper-radar:contracts:screening:boundary:v1",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "description": "Screening 第一阶段的研究边界判断。",
  "properties": {
    "boundary": {
      "enum": [
        "in_scope",
        "out_of_scope",
        "uncertain"
      ],
      "title": "Boundary",
      "type": "string"
    },
    "reason_zh": {
      "title": "Reason Zh",
      "type": "string"
    }
  },
  "required": [
    "boundary",
    "reason_zh"
  ],
  "title": "BoundaryOutput",
  "type": "object",
  "x-paper-radar-contract": {
    "name": "boundary",
    "version": "v1"
  }
}
""".encode()


def test_boundary_contract_is_generated_deterministically_from_model() -> None:
    contract = build_frozen_contract(ContractName.BOUNDARY, ContractVersion.V1)

    assert contract.schema_bytes == EXPECTED_BOUNDARY_SCHEMA
    assert (
        contract.schema_sha256
        == "9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7"
    )
    assert contract.snapshot_parts == ("screening", "boundary", "v1")
    assert contract.schema_filename == "schema.json"
    assert contract.manifest_filename == "manifest.json"

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
