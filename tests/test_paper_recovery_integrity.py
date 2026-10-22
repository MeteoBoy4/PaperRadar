"""组合论文恢复的校验时点、语义损坏与来源字节边界。"""

from pathlib import Path

import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.storage.artifacts import ArtifactStore
from tests.paper_recovery_support import tree_hash
from tests.test_source_backup import populated


def test_create_checks_source_bytes_before_copy_only_semantic_validation(
    tmp_path: Path,
) -> None:
    service, paper_id, _ = populated(tmp_path / "source")
    assert service.data_root
    manual = next(
        source
        for source in service.trace(paper_id).observations
        if source.source_kind == "manual"
    )
    store = ArtifactStore(service.database, service.data_root)
    _, blobs = store.artifact_blobs(manual.artifact_id)
    blob = service.data_root / blobs[0].relative_path
    blob.chmod(0o600)
    blob.write_bytes(b"damaged source bytes")
    before = tree_hash(tmp_path / "source", ignore_sqlite_sidecars=True)
    with pytest.raises(BackupError) as failure:
        create_backup(service.database, service.data_root, tmp_path / "batches")
    assert failure.value.reason == "file_corrupt"
    assert tree_hash(tmp_path / "source", ignore_sqlite_sidecars=True) == before
    assert not tuple((tmp_path / "batches").iterdir())


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_relation_only_bytes_are_optional_explicit_and_never_dumped(
    tmp_path: Path,
    damage: str,
) -> None:
    from typer.testing import CliRunner

    from paper_radar.cli import app
    from paper_radar.papers import PaperError
    from tests.paper_recovery_support import populated as combined

    facts = combined(tmp_path / "source")
    service = facts.service
    assert service.data_root and facts.pre.paper_id
    trace = service.trace(facts.pre.paper_id)
    # This retained relation material has no corresponding field observation.
    assert facts.unbound_artifact not in {
        source.artifact_id for source in trace.observations
    }
    retained = {
        assertion.artifact_id
        for relation in trace.relations
        for assertion in relation.assertions
        if assertion.artifact_id
    }
    assert retained <= {source.artifact_id for source in trace.observations} | {
        relation.artifact_id for relation in trace.relations
    }
    _, blobs = ArtifactStore(service.database, service.data_root).artifact_blobs(
        facts.unbound_artifact
    )
    blob = service.data_root / blobs[0].relative_path
    if damage == "missing":
        blob.unlink()
    else:
        blob.chmod(0o600)
        blob.write_bytes(b"PRIVATE-RECOVERY broken relation material")
    before = tree_hash(tmp_path / "source", ignore_sqlite_sidecars=True)
    assert service.trace(facts.pre.paper_id) == trace
    with pytest.raises(PaperError) as failure:
        service.trace(facts.pre.paper_id, verify_source_bytes=True)
    assert failure.value.reason == "corrupt_reference"
    query = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            facts.pre.paper_id,
            "--database",
            str(service.database),
            "--data-root",
            str(service.data_root),
            "--verify-source-bytes",
        ],
    )
    assert query.exit_code == 1
    assert "corrupt_reference" in query.output
    assert "PRIVATE-RECOVERY" not in query.output
    assert tree_hash(tmp_path / "source", ignore_sqlite_sidecars=True) == before
