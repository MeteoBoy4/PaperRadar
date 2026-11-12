"""D1: 显式双准备作废描述的封闭 Schema 与规范往返。"""

import pytest
from pydantic import ValidationError

from paper_radar.live_evidence.preparation_void import FailedPreparationVoidDescriptor
from paper_radar.live_evidence.receipt import canonical_bytes


def test_void_descriptor_refuses_unknown_and_non_integer_version() -> None:
    with pytest.raises(ValidationError, match="format_version"):
        FailedPreparationVoidDescriptor.model_validate({"format_version": True})


def test_void_descriptor_schema_and_canonical_restore_preserve_exact_selection() -> (
    None
):
    raw = {
        "format_version": 1,
        "authorization": "owner-authorized-zero-operation-preparations-v1",
        "sources": [
            {
                "failure_stage": "no_secret_preflight",
                "payload_sha256": "1" * 64,
                "runtime_manifest_sha256": "2" * 64,
                "journal_sha256": "3" * 64,
            },
            {
                "failure_stage": "no_secret_preflight",
                "payload_sha256": "4" * 64,
                "runtime_manifest_sha256": "5" * 64,
                "journal_sha256": "6" * 64,
            },
        ],
        "failed_placement_identity": "7" * 64,
        "failed_marker_sha256": "8" * 64,
        "new_placement_identity": "9" * 64,
        "upgrade_from": ["a" * 64, "b" * 64],
        "epoch_upgrade_sha256": "c" * 64,
        "continuity_sha256": "d" * 64,
        "baseline": "auth=0;network=0;model=0;remaining=40/40;idle;unstopped",
    }
    descriptor = FailedPreparationVoidDescriptor.model_validate(raw)
    restored = FailedPreparationVoidDescriptor.model_validate_json(
        canonical_bytes(descriptor)
    )
    assert restored.model_dump(mode="json") == raw
    schema = FailedPreparationVoidDescriptor.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["sources"]["minItems"] == 2
    assert schema["properties"]["sources"]["maxItems"] == 2
    with pytest.raises(ValidationError, match="arbitrary_source"):
        FailedPreparationVoidDescriptor.model_validate(
            {**raw, "arbitrary_source": "forbidden"}
        )
