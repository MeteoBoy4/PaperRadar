"""D1:持久成员 -> 隔离恢复 -> 冷进程无 SDK 逐字证据。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, restore_backup
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.canonical import (
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalProvenance,
)
from paper_radar.fulltext.models import FulltextError
from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database


def save(
    store: ArtifactStore, orig: str = "Exact persisted 原文."
) -> tuple[str, str, str, str]:
    doc = CanonicalDocument(
        pages=(
            CanonicalPage(page_no=7, width=600.0, height=800.0, origin="bottom_left"),
        ),
        blocks=(
            CanonicalBlock(
                ref="#/texts/0",
                order=(0,),
                label="text",
                orig=orig,
                text=orig,
                provenance=(
                    CanonicalProvenance(
                        page_no=7,
                        bbox=(10.0, 20.0, 400.0, 50.0),
                        charspan=(0, len(orig)),
                        origin="bottom_left",
                    ),
                ),
            ),
        ),
    )
    result = FulltextArtifacts(store).publish(
        doc,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=4096,
        document_json=b'{"audit_only":"not a canonical reader input"}',
    )
    return (
        result.artifact_id,
        result.identity.extraction_fingerprint,
        result.identity.reading_sha256,
        result.identity.evidence_map_sha256,
    )


def test_moved_backup_rebuilds_source_in_cold_process_without_sdk_or_original_root(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    database = source / "db"
    upgrade_database(database)
    store = ArtifactStore(database, source / "data")
    reference = save(store)
    backup = create_backup(database, source / "data", tmp_path / "batches")
    source.rename(tmp_path / "source-unavailable")
    restored = restore_backup(backup.batch_dir, tmp_path / "restored").target_dir
    script = r"""
import sys, importlib.abc, json
class DenySDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        denied = {'docling','docling_core','torch','transformers','docling_parse'}
        if fullname.split('.')[0] in denied:
            raise RuntimeError('SDK import forbidden')
sys.meta_path.insert(0,DenySDK())
from pathlib import Path
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.reading.context import ExtractionIdentity
root = Path(sys.argv[1])
artifact, fingerprint, reading_hash, evidence_hash = json.loads(sys.argv[2])
service = FulltextArtifacts(ArtifactStore(root/'database.sqlite3',root))
identity = ExtractionIdentity(fingerprint,reading_hash,evidence_hash)
loaded = service.load(artifact,expected_identity=identity)
parts = loaded.context.replay()
assert len(parts) == 1
assert parts[0].text == 'Exact persisted 原文.'
assert parts[0].provenance.page_no == 7
assert loaded.context.pages[0].origin == 'bottom_left'
assert service.lookup(artifact,loaded.identity,'e000001') == parts
print('replayed without SDK')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(restored), json.dumps(reference)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "replayed without SDK"


@pytest.mark.parametrize("damage", ["missing", "orig_tampered"])
def test_missing_or_modified_persistent_orig_is_refused(
    tmp_path: Path, damage: str
) -> None:
    database = tmp_path / "db"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    artifact, fingerprint, reading_hash, evidence_hash = save(store)
    from paper_radar.reading.context import ExtractionIdentity

    record, blobs = store.artifact_blobs(artifact)
    index = [m.role for m in record.members].index("evidence_map")
    path = store.verified_blob_path(blobs[index])
    if damage == "missing":
        path.unlink()
    else:
        path.chmod(0o600)
        path.write_bytes(
            path.read_bytes().replace(b"Exact persisted", b"Wrong persisted")
        )
        path.chmod(0o400)
    with pytest.raises(ArtifactError) as failure:
        FulltextArtifacts(store).load(
            artifact,
            expected_identity=ExtractionIdentity(
                fingerprint, reading_hash, evidence_hash
            ),
        )
    assert failure.value.reason == (
        ArtifactReason.BLOB_MISSING
        if damage == "missing"
        else ArtifactReason.BLOB_CORRUPT
    )


def test_same_fingerprint_and_block_id_cannot_cross_content(tmp_path: Path) -> None:
    from paper_radar.reading.context import ExtractionIdentity

    database = tmp_path / "db"
    upgrade_database(database)
    store = ArtifactStore(database, tmp_path / "root")
    first = save(store)
    second = save(store, "Different source 原文.")
    assert first[1] == second[1]
    with pytest.raises(FulltextError) as failure:
        FulltextArtifacts(store).lookup(
            second[0], ExtractionIdentity(*first[1:]), "e000001"
        )
    assert failure.value.reason == "identity_mismatch"
