"""D1:可选执行审计不改写旧四角色manifest字节。"""

import json
from pathlib import Path

from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.normalization import canonical_json, sha256
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from tests.test_fulltext_artifacts import document


def test_old_manifest_bytes_still_load_through_public_service(tmp_path: Path) -> None:
    database = tmp_path / "db"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "data")
    service = FulltextArtifacts(store)
    saved = service.publish(
        document(),
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=4096,
    )
    members = store.read_artifact(saved.artifact_id)
    # 旧格式的独立字面字段集合,不从新增Pydantic缺省字段推导。
    old_manifest = canonical_json(
        {
            "format_version": 1,
            "normalization_version": "v1",
            "extraction_fingerprint": "a" * 64,
            "reading_sha256": sha256(members["reading"]),
            "evidence_map_sha256": sha256(members["evidence_map"]),
            "document_sha256": sha256(members["document"]),
            "backend_config_hash": "b" * 64,
            "model_artifacts_hash": "c" * 64,
            "elapsed_seconds": 1.0,
            "peak_memory_bytes": 4096,
            "warnings": [],
        }
    )
    assert members["manifest"] == old_manifest
    assert "execution_audit" not in json.loads(old_manifest)
    restored = store.publish_artifact(
        "extraction",
        {
            role: [old_manifest if role == "manifest" else raw]
            for role, raw in members.items()
        },
    )
    loaded = service.load(restored.artifact_id, expected_identity=saved.identity)
    assert loaded.context.replay()[1].text == "Exact source α = 2."


def test_optional_audit_preserves_body_identity_and_rejects_internal_mismatch(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.docling_toolchain import backend_identity
    from paper_radar.fulltext.execution_audit import ExtractionExecutionAudit
    from paper_radar.fulltext.models import FulltextError

    database = tmp_path / "db"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "data")
    service = FulltextArtifacts(store)
    old = service.publish(
        document(),
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=4096,
    )
    audit = ExtractionExecutionAudit(
        toolchain="docling-2.135.0-cpu-v2",
        pdf_backend="pypdfium2",
        component_versions=backend_identity(
            "docling-2.135.0-cpu-v2", "pypdfium2"
        ).component_versions,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        timeout_seconds=30.0,
        memory_limit_bytes=2**34,
        threads=4,
    )
    new = service.publish(
        document(),
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=4096,
        execution_audit=audit,
    )
    assert new.identity == old.identity and new.artifact_id != old.artifact_id
    assert (
        service.load(new.artifact_id, expected_identity=new.identity)
        .context.replay()[1]
        .text
        == "Exact source α = 2."
    )
    members = store.read_artifact(new.artifact_id)
    manifest = json.loads(members["manifest"])
    assert manifest["execution_audit"]["hf_hub_offline"] == "1"
    manifest["execution_audit"]["model_artifacts_hash"] = "d" * 64
    members["manifest"] = canonical_json(manifest)
    tampered = store.publish_artifact(
        "extraction", {role: [raw] for role, raw in members.items()}
    )
    with pytest.raises(FulltextError) as error:
        service.load(tampered.artifact_id, expected_identity=new.identity)
    assert error.value.reason == "invalid_members"
