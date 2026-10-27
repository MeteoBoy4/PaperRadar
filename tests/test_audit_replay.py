"""历史规则的只读回放区分保留材料与执行事实。"""

from pathlib import Path

import pytest

from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def test_replay_reconstructs_frozen_v1_and_discloses_proof_levels_without_http_or_locks(
    tmp_path: Path,
) -> None:
    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    before_calls = tuple(sources.calls)
    replay = service.replay_audit(original.plan.plan_id)
    assert replay.status == "verified"
    assert replay.view == original
    assert len(replay.semantic_sha256) == 64
    assert {proof.level for proof in replay.proofs} == {
        "material_reparsed",
        "execution_facts_only",
    }
    assert sum(proof.level == "material_reparsed" for proof in replay.proofs) == 11
    assert tuple(sources.calls) == before_calls
    assert service.replay_audit(original.plan.plan_id) == replay


def test_missing_historical_version_is_distinct_from_unrehashed_plan_corruption(
    tmp_path: Path,
) -> None:
    import hashlib
    import json
    import sqlite3
    from contextlib import closing

    import pytest

    from paper_radar.fixture_audit import FixtureError

    service = sampling_service(tmp_path, MatrixSources())
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    with closing(sqlite3.connect(service.database)) as connection:
        raw = connection.execute("SELECT plan_json FROM audit_plans").fetchone()[0]
        value = json.loads(raw)
        value["abstract_rules_version"] = "audit-abstract-unavailable"
        connection.execute(
            "UPDATE audit_plans SET plan_json=?",
            (json.dumps(value, ensure_ascii=False, separators=(",", ":")),),
        )
        connection.commit()
    with pytest.raises(FixtureError) as corrupt:
        service.replay_audit(plan.plan_id)
    assert corrupt.value.reason == "corrupt_reference"
    value["plan_id"] = ""
    value["plan_id"] = hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            "UPDATE audit_plans SET plan_id=?,plan_json=?",
            (
                value["plan_id"],
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        connection.commit()
    with pytest.raises(FixtureError) as unsupported:
        service.replay_audit(value["plan_id"])
    assert unsupported.value.reason == "unsupported_history"
    with pytest.raises(FixtureError) as incompatible:
        service.resume_audit(
            value["plan_id"], contact_email="audit@example.org", code_identity=CODE
        )
    assert incompatible.value.reason == "plan_identity_mismatch"


def test_frozen_v1_replay_does_not_consume_current_default_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.fixture_audit import FixtureError, abstract_models

    service = sampling_service(tmp_path, MatrixSources())
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    before = service.replay_audit(original.plan.plan_id)
    monkeypatch.setattr(
        abstract_models, "ABSTRACT_RULES_VERSION", "audit-abstract-v999"
    )
    assert service.replay_audit(original.plan.plan_id) == before
    with pytest.raises(FixtureError) as mismatch:
        service.resume_audit(
            original.plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
    assert mismatch.value.reason == "plan_identity_mismatch"
    assert mismatch.value.path == "code_identity"
    assert service.replay_audit(original.plan.plan_id) == before
