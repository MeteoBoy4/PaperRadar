"""响应保留标志涵盖字段及关系材料;不代表物理新增 blob。"""

from datetime import UTC, datetime
from pathlib import Path

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.test_paper_service import observation
from tests.test_version_relations import relation


def test_relation_material_retention_is_true_for_relation_only_and_reused_fields(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    only_request = observation(
        doi="10.1/pre", version_kind="preprint", fields={}, relations=relation()
    )
    only = service.submit(only_request)
    assert only.status == "retained" and only.version_id is None
    pre = service.submit(
        observation(doi="10.1/pre", version_kind="preprint", payload=b"version arrived")
    )
    assert pre.paper_id
    only_assertion = service.trace(pre.paper_id).relations[0].assertions[0]
    assert only_assertion.response_bytes_retained is True
    assert only_assertion.artifact_id is not None
    assert service.submit(only_request) == only

    second_relation = (
        {
            "kind": "is-preprint-of",
            "source_doi": "10.1/pre",
            "target_doi": "10.1/journal2",
            "locator": "second",
        },
    )
    request = observation(
        doi="10.1/pre",
        version_kind="preprint",
        payload=b"same fields, new relation",
        observed_at=datetime(2026, 1, 2, tzinfo=UTC),
        relations=second_relation,
    )
    linked = service.submit(request)
    trace = service.trace(pre.paper_id, verify_source_bytes=True)
    assert len(trace.observations) == 1
    acquired = next(
        event
        for event in trace.acquisitions
        if event.acquisition_id == linked.acquisition_id
    )
    assert acquired.response_bytes_retained is True
    assertion = next(
        item
        for edge in trace.relations
        for item in edge.assertions
        if item.acquisition_id == linked.acquisition_id
    )
    assert (
        assertion.response_bytes_retained is True and assertion.artifact_id is not None
    )
    assert service.submit(request) == linked
    service.validate_all()

    repeat_request = observation(
        doi="10.1/pre",
        version_kind="preprint",
        fields={},
        payload=b"same relationship only",
        observed_at=datetime(2026, 1, 3, tzinfo=UTC),
        relations=second_relation,
    )
    repeated = service.submit(repeat_request)
    assert repeated.status == "not_retained"
    trace = service.trace(pre.paper_id)
    repeat_acquired = next(
        event
        for event in trace.acquisitions
        if event.acquisition_id == repeated.acquisition_id
    )
    assert repeat_acquired.response_bytes_retained is False
    repeat_assertion = next(
        item
        for edge in trace.relations
        for item in edge.assertions
        if item.acquisition_id == repeated.acquisition_id
    )
    assert (
        repeat_assertion.response_bytes_retained is False
        and repeat_assertion.artifact_id is None
    )
    assert service.submit(repeat_request) == repeated
    service.validate_all()

    batch = create_backup(db, tmp_path / "data", tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = PaperFacts(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.trace(pre.paper_id, verify_source_bytes=True) == trace
    assert recovered.submit(only_request) == only
    assert recovered.submit(request) == linked
    assert recovered.submit(repeat_request) == repeated
    recovered.validate_all()


def test_field_material_with_repeated_relation_is_retained_when_blob_is_deduplicated(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore

    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    source = service.submit(
        observation(
            doi="10.1/pre", version_kind="preprint", fields={}, relations=relation()
        )
    )
    observed = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            query_key="field-interpretation",
            relations=relation(),
        )
    )
    assert source.status == observed.status == "retained" and observed.paper_id
    trace = service.trace(observed.paper_id, verify_source_bytes=True)
    assertions = trace.relations[0].assertions
    assert len(assertions) == 2
    assert all(item.response_bytes_retained for item in assertions)
    assert len({item.artifact_id for item in assertions}) == 1
    assert all(item.artifact_id is not None for item in assertions)
    assert len(ArtifactStore(db, tmp_path / "data").list_artifacts()) == 1
    service.validate_all()
