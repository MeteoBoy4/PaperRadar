"""实际 SQLite 事务故障不能追认上次取得成功或留下半条解释。"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.fixture_audit import FixtureError
from paper_radar.storage.artifacts import ArtifactStore
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


@pytest.mark.parametrize("table", ["audit_route_settlements", "audit_abstract_rows"])
def test_resume_recovers_publication_or_interpretation_transaction_failure(
    tmp_path: Path, table: str
) -> None:
    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    with closing(sqlite3.connect(service.database)) as connection:
        predicate = (
            'NEW.execution_id IN (SELECT execution_id FROM audit_route_starts WHERE request_json LIKE \'%"journal":"jgr"%\' AND request_json LIKE \'%"route":"publisher"%\')'
            if table == "audit_route_settlements"
            else "NEW.route='publisher' AND NEW.channel='http' AND NEW.content_json LIKE '%\"journal\":\"jgr\"%'"
        )
        connection.execute(
            f"CREATE TRIGGER injected_failure BEFORE INSERT ON {table} WHEN {predicate} BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
        connection.commit()
    with pytest.raises(FixtureError) as caught:
        service.run_audit(contact_email="first@example.org", code_identity=CODE)
    assert caught.value.reason == "corrupt_reference"
    before = service.list_audits()[0]
    publisher = next(
        value
        for value in before.executions
        if value.request.journal == "jgr" and value.request.route == "publisher"
    )
    assert service.data_root
    store = ArtifactStore(service.database, service.data_root)
    unused = {value.artifact_id for value in store.list_artifacts()} - {
        value.settlement.artifact_id
        for value in before.executions
        if value.settlement and value.settlement.artifact_id
    }
    if table == "audit_route_settlements":
        assert publisher.settlement is None and len(unused) == 1
    else:
        assert publisher.reason == "acquired" and not unused
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute("DROP TRIGGER injected_failure")
        connection.commit()
    resumed = service.resume_audit(
        before.plan.plan_id, contact_email="second@example.org", code_identity=CODE
    )
    assert resumed.status == "complete"
    current = next(
        row
        for row in resumed.matrix
        if row.request.journal == "jgr"
        and row.request.route == "publisher"
        and row.request.channel == "http"
    )
    result = next(
        value
        for value in resumed.executions
        if value.execution_id == current.acquisition_id
    )
    assert result.settlement
    if table == "audit_route_settlements":
        assert result.settlement.artifact_id in unused
        old = next(
            value
            for value in resumed.executions
            if value.execution_id == publisher.execution_id
        )
        assert old.reason == "outcome_unknown" and old.physical_requests is None
    else:
        assert result.execution_id == publisher.execution_id
    service.replay_audit(before.plan.plan_id)
