"""Issue #146:显式新计划与 v1 回放/恢复共存;全合成来源。"""

from pathlib import Path

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.fixture_audit import FixtureAudit
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service
from tests.test_wiley_abstract_v2 import MAIN, NOTE, feed


def test_new_plan_selects_v2_while_frozen_v1_replays_after_restore(
    tmp_path: Path,
) -> None:
    original_root = tmp_path / "original"
    original_root.mkdir()
    sources = MatrixSources()
    for url in sources.feeds:
        if "wiley.com" in url:
            sources.feeds[url] = feed(
                "<dc:identifier>10.1029/synthetic</dc:identifier>"
                f"<description>{NOTE}</description>"
                "<content:encoded><![CDATA[<h2>Abstract</h2>"
                f"<p>{MAIN}</p>]]></content:encoded>"
            )
    service = sampling_service(original_root, sources)
    old = service.run_audit(
        contact_email="audit@example.org", code_identity=CODE, plan_key="old"
    )
    before = service.replay_audit(old.plan.plan_id)
    new = service.run_audit(
        contact_email="audit@example.org",
        code_identity=CODE,
        plan_key="new",
        abstract_rules_version="audit-abstract-v2",
    )
    assert new.plan.abstract_rules_version == "audit-abstract-v2"
    rows = [
        row
        for row in new.matrix
        if row.request.journal in {"jgr", "qjrms"} and row.request.route == "feed"
    ]
    assert rows
    for row in rows:
        candidate = next(value for value in row.candidates if value.field == "abstract")
        assert row.abstract_rules_version == "audit-abstract-v2"
        assert service.read_audit_text(new.plan.plan_id, candidate.candidate_id) == MAIN
    assert service.replay_audit(old.plan.plan_id) == before
    assert service.data_root
    current = service.replay_audit(new.plan.plan_id)
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    original_root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.replay_audit(old.plan.plan_id) == before
    assert recovered.replay_audit(new.plan.plan_id) == current


def test_partial_plan_cannot_append_interpretation_or_claim_builtin_version(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.fixture_audit import FixtureError
    from tests.test_audit_reinterpret import SyntheticV2

    service = sampling_service(tmp_path, MatrixSources())
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    before = service.replay_audit(plan.plan_id)
    with pytest.raises(FixtureError) as incomplete:
        service.reinterpret_audit(
            plan.plan_id, parser=SyntheticV2(), request_key="blocked"
        )
    assert incomplete.value.reason == "execution_incomplete"
    assert incomplete.value.path == "audit.interpretation"

    class Impostor(SyntheticV2):
        version = "audit-abstract-v2"

    with pytest.raises(FixtureError) as reserved:
        service.reinterpret_audit(
            plan.plan_id, parser=Impostor(), request_key="reserved"
        )
    assert reserved.value.reason == "invalid_request"
    assert reserved.value.path == "audit.parser"
    assert service.replay_audit(plan.plan_id) == before
    assert service.list_audit_interpretations(plan.plan_id) == ()
