"""D1:失败准备描述只承载闭合身份,不承载root路径或命令。"""

import pytest
from pydantic import ValidationError

from paper_radar.live_evidence.preparation_retirement import FailedPreparation


def descriptor() -> dict[str, object]:
    return {
        "format_version": 1,
        "payload_sha256": "1" * 64,
        "runtime_manifest_sha256": "2" * 64,
        "placement_identity": "3" * 64,
        "binary_sha256": "4" * 64,
        "source_sha256": "5" * 64,
        "marker_sha256": "6" * 64,
        "new_placement_identity": "7" * 64,
        "upgrade_from": ["8" * 64, "9" * 64],
        "epoch_upgrade_sha256": "a" * 64,
        "continuity_sha256": "b" * 64,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runtime", "/arbitrary/runtime"),
        ("command", "/usr/bin/false"),
        ("payload_sha256", "../runtime"),
        ("format_version", True),
        ("upgrade_from", ["8" * 64]),
    ],
)
def test_descriptor_rejects_unknown_paths_commands_and_forged_identity(
    field: str, value: object
) -> None:
    raw = descriptor()
    raw[field] = value
    with pytest.raises(
        ValidationError,
        match=field if field != "format_version" else "failed_preparation_descriptor",
    ):
        FailedPreparation.model_validate(raw)


def test_descriptor_accepts_only_closed_identity_fields() -> None:
    parsed = FailedPreparation.model_validate(descriptor())
    assert parsed.payload_sha256 == "1" * 64
    assert parsed.upgrade_from == ("8" * 64, "9" * 64)
