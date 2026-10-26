"""恢复执行链和新解释链的基本闭包,不声明缺失运行时已被重解析。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.fixture_audit import FixtureAudit, FixtureError
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service
from tests.test_audit_reinterpret import SyntheticV2


def test_restored_interpretation_needs_runtime_only_for_explicit_v2_reparse(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    service = sampling_service(root, MatrixSources())
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    value = service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV2(), request_key="v2"
    )
    assert service.data_root
    before = service.replay_audit(original.plan.plan_id)
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.replay_audit(original.plan.plan_id) == before
    assert recovered.list_audit_interpretations(original.plan.plan_id) == (value,)
    assert value.proof_level == "declaration_and_reference_verified"
    with pytest.raises(FixtureError) as missing:
        recovered.replay_audit_interpretation(
            original.plan.plan_id, value.interpretation_id
        )
    assert missing.value.reason == "unsupported_history"
    assert (
        recovered.replay_audit_interpretation(
            original.plan.plan_id, value.interpretation_id, parser=SyntheticV2()
        ).interpretation
        == value
    )
    assert not list(restored.target_dir.rglob("*.lock"))
    for path in batch.batch_dir.rglob("*"):
        if path.is_file():
            assert b"audit@example.org" not in path.read_bytes()
            assert b"New v2 primary interpretation." not in path.read_bytes()


@pytest.mark.parametrize("damage", ["version", "source", "difference", "chain"])
def test_rehashed_interpretation_closure_rejects_source_version_diff_or_chain(
    tmp_path: Path, damage: str
) -> None:
    class SyntheticV3(SyntheticV2):
        version = "synthetic-abstract-v3"
        implementation_sha256 = "3" * 64

    service = sampling_service(tmp_path, MatrixSources())
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV2(), request_key="first"
    )
    latest = service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV3(), request_key="second"
    )
    value = json.loads(latest.model_dump_json())
    if damage == "version":
        value["parser_version"] = "synthetic-abstract-forged"
    elif damage == "source":
        value["rows"][0]["acquisition_id"] = value["rows"][1]["acquisition_id"]
    elif damage == "difference":
        value["rows"][0]["added"] = ["title"]
    else:
        value["previous_interpretation_id"] = None
    value["interpretation_id"] = ""
    value["interpretation_id"] = hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            "UPDATE audit_interpretations SET interpretation_id=?,"
            "previous_interpretation_id=?,content_json=? WHERE interpretation_id=?",
            (
                value["interpretation_id"],
                value["previous_interpretation_id"],
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                latest.interpretation_id,
            ),
        )
        connection.commit()
    with pytest.raises(FixtureError) as caught:
        service.validate_all()
    assert caught.value.reason == "corrupt_reference"
    assert caught.value.path in {
        "audit.interpretation",
        "audit.interpretation_source",
        "audit.interpretation_difference",
        "audit.interpretation_chain",
    }
