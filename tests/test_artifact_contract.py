"""独立冻结的完整清单字面量与标准 SHA-256 向量。"""

import json

import pytest
from pydantic import ValidationError

from paper_radar.storage.artifact_contract import (
    ArtifactError,
    ArtifactManifest,
    ArtifactMember,
    artifact_manifest,
    media_type,
)

EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
SINGLE_JSON = (
    '{"domain":"paper-radar.artifact","format_version":1,"kind":"'
    'source_snapshot","members":[{"role":"payload","sha256":"e3b0'
    "c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    '","size_bytes":0}]}'
)
EXTRACTION_JSON = (
    '{"domain":"paper-radar.artifact","format_version":1,"kind":"'
    'extraction","members":[{"role":"document","sha256":"ba7816bf'
    '8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","s'
    'ize_bytes":3},{"role":"evidence_map","sha256":"e3b0c44298fc1'
    'c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","size_b'
    'ytes":0},{"role":"manifest","sha256":"e3b0c44298fc1c149afbf4'
    'c8996fb92427ae41e4649b934ca495991b7852b855","size_bytes":0},'
    '{"role":"reading","sha256":"ba7816bf8f01cfea414140de5dae2223'
    'b00361a396177a9cb410ff61f20015ad","size_bytes":3}]}'
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            SINGLE_JSON,
            "accf50f8375b85b3f2105c3904cf05db0d56922a0bffe9cafb0f1e8bf6e57afa",
        ),
        (
            EXTRACTION_JSON,
            "b461c859afffb63c837b556746fd0ab9cfe892bcd1a58a912da46799b1738d87",
        ),
    ],
)
def test_fixed_complete_manifest_vectors(raw: str, expected: str) -> None:
    manifest = ArtifactManifest.model_validate_json(raw)
    assert manifest.canonical_json == raw
    assert manifest.artifact_id == expected
    reversed_manifest = artifact_manifest(
        manifest.kind, tuple(reversed(manifest.members))
    )
    assert reversed_manifest.artifact_id == expected


@pytest.mark.parametrize(
    "damage",
    [
        "unknown",
        "missing",
        "domain",
        "format",
        "bool_version",
        "kind",
        "role",
        "duplicate",
        "negative",
        "bool_size",
        "extra_member",
        "hash",
    ],
)
def test_strict_manifest_rejects_noncontract_material(damage: str) -> None:
    payload = json.loads(SINGLE_JSON)
    member = payload["members"][0]
    match damage:
        case "unknown":
            payload["path"] = "private"
        case "missing":
            del payload["domain"]
        case "domain":
            payload["domain"] = "other"
        case "format":
            payload["format_version"] = 2
        case "bool_version":
            payload["format_version"] = True
        case "kind":
            payload["kind"] = "other"
        case "role":
            member["role"] = "unknown"
        case "duplicate":
            payload["members"].append(member)
        case "negative":
            member["size_bytes"] = -1
        case "bool_size":
            member["size_bytes"] = False
        case "extra_member":
            member["media_type"] = "text/plain"
        case "hash":
            member["sha256"] = "../escape"
    with pytest.raises((ValidationError, ArtifactError)):
        ArtifactManifest.model_validate_json(json.dumps(payload))


def test_content_kind_and_role_affect_identity_but_media_is_derived() -> None:
    payload = ArtifactMember(role="payload", sha256=ABC, size_bytes=3)
    ids = {
        artifact_manifest(kind, (payload,)).artifact_id
        for kind in (
            "source_snapshot",
            "original_pdf",
            "model_success_response",
            "reference_tei",
        )
    }
    assert len(ids) == 4
    assert media_type("extraction", "document") == "application/json"
    assert media_type("extraction", "reading") == "text/markdown"
