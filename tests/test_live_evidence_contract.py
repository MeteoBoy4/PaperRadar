from __future__ import annotations

import json
from pathlib import Path

from paper_radar.contracts import ContractName, ContractVersion, build_frozen_contract
from paper_radar.live_evidence.receipt import EvidenceReceipt


def test_receipt_frozen_contract_matches_authority_and_committed_snapshot() -> None:
    contract = build_frozen_contract(ContractName("live-evidence"), ContractVersion.V1)
    schema = json.loads(contract.schema_bytes)
    assert set(schema["properties"]) == set(EvidenceReceipt.model_fields)
    assert schema["$id"] == "urn:paper-radar:contracts:live-evidence:live-evidence:v1"
    assert schema["additionalProperties"] is False
    snapshot = Path(__file__).parents[1] / "contracts/live-evidence/live-evidence/v1"
    assert (snapshot / "schema.json").read_bytes() == contract.schema_bytes
    assert (snapshot / "manifest.json").read_bytes() == contract.manifest_bytes


def test_receipt_contract_is_explicitly_selectable_without_expanding_history(
    tmp_path: Path,
) -> None:
    from paper_radar.contracts import check_frozen_contract, export_frozen_contract

    export_frozen_contract(name="live-evidence", version="v1", target=tmp_path)
    check_frozen_contract(name="live-evidence", version="v1", target=tmp_path)
    assert {
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("schema.json")
    } == {
        "live-evidence/live-evidence/v1/schema.json",
    }
