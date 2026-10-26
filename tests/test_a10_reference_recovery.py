"""外层重哈希不能为错误引用、汇总边界或原声明字节洗白。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.backup.restore_contract import RestoreError
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service
from tests.paper_recovery_support import tree_hash
from tests.test_fixture_audit_references import audit_declaration


def rehash_batch(batch: Path) -> None:
    manifest_path = batch / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = (batch / "database.sqlite3").read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )


@pytest.mark.parametrize(
    "damage",
    [
        "snapshot",
        "summary",
        "journal",
        "member",
        "raw",
        "boundary",
        "settlement",
        "replacement",
        "parser",
    ],
)
def test_rehashed_reference_damage_rejects_verify_and_never_publishes_restore(
    tmp_path: Path, damage: str
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    audit = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    source = tmp_path / "references.json"
    source.write_bytes(audit_declaration(service, audit.plan.plan_id))
    first = service.register(source)
    declaration = json.loads(source.read_bytes())
    declaration["declared_version"] = "v2"
    for entry, previous in zip(declaration["entries"], first.entries, strict=True):
        entry.update(replaces=previous.record_id, replacement_reason="追加引用历史")
    source.write_text(json.dumps(declaration, ensure_ascii=False))
    latest = service.register(source)
    if damage == "parser":
        from tests.test_audit_reinterpret import SyntheticV2

        service.reinterpret_audit(
            audit.plan.plan_id, parser=SyntheticV2(), request_key="v2"
        )
    assert service.data_root
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    with closing(sqlite3.connect(batch.batch_dir / "database.sqlite3")) as connection:
        if damage in {"boundary", "settlement"}:
            digest, text = connection.execute(
                "SELECT summary_sha256,content_json FROM audit_summaries"
            ).fetchone()
            boundary = json.loads(text)
            if damage == "boundary":
                boundary["matrix_rows"].pop()
            else:
                boundary["executions"][0][1] = "0" * 64
            connection.execute(
                "UPDATE audit_summaries SET content_json=? WHERE summary_sha256=?",
                (
                    json.dumps(boundary, ensure_ascii=False, separators=(",", ":")),
                    digest,
                ),
            )
        elif damage == "parser":
            identity, text = connection.execute(
                "SELECT interpretation_id,content_json FROM audit_interpretations"
            ).fetchone()
            value = json.loads(text)
            value["parser_version"] = "forged-version"
            value["interpretation_id"] = ""
            value["interpretation_id"] = hashlib.sha256(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest()
            connection.execute(
                "UPDATE audit_interpretations SET interpretation_id=?,content_json=? "
                "WHERE interpretation_id=?",
                (
                    value["interpretation_id"],
                    json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                    identity,
                ),
            )
        elif damage == "raw":
            connection.execute(
                "UPDATE fixture_declarations SET raw_content=raw_content || X'20' "
                "WHERE declaration_id=?",
                (latest.declaration_id,),
            )
        else:
            value = json.loads(source.read_bytes())
            feed, whole = value["entries"]
            if damage == "snapshot":
                whole["audit_reference"]["feed_snapshots"]["dqkx"] = feed[
                    "audit_reference"
                ]["feed_sha256"]
            elif damage == "summary":
                feed["audit_reference"]["summary_sha256"] = "0" * 64
            elif damage == "journal":
                feed["journal"] = "dqkx"
            elif damage == "member":
                feed["doi"] = "10.1175/aies.synthetic"
            else:
                feed["replaces"] = first.entries[1].record_id
                whole["replaces"] = first.entries[0].record_id
                connection.execute(
                    "UPDATE fixture_records SET replaces=NULL WHERE declaration_id=?",
                    (latest.declaration_id,),
                )
            raw = json.dumps(value, ensure_ascii=False).encode()
            new_id = hashlib.sha256(raw).hexdigest()
            connection.execute(
                "UPDATE fixture_declarations SET declaration_id=?,raw_sha256=?,"
                "raw_content=? WHERE declaration_id=?",
                (new_id, new_id, raw, latest.declaration_id),
            )
            for original, entry in zip(latest.entries, value["entries"], strict=True):
                # Public parser provides the canonical entry encoding; independent
                # SHA identities are rehashed too, leaving semantic refusal to backup.
                from paper_radar.fixture_audit.models import parse_declaration

                parsed = next(
                    item
                    for item in parse_declaration(raw).entries
                    if item.key == entry["key"]
                )
                identity = hashlib.sha256(
                    "\0".join(
                        (
                            new_id,
                            entry["purpose"],
                            entry["journal"] or "plan",
                            entry["key"],
                        )
                    ).encode()
                ).hexdigest()
                connection.execute(
                    "UPDATE fixture_records SET record_id=?,declaration_id=?,journal=?,"
                    "entry_json=?,replaces=? WHERE record_id=?",
                    (
                        identity,
                        new_id,
                        entry["journal"],
                        parsed.model_dump_json(),
                        entry["replaces"],
                        original.record_id,
                    ),
                )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    rehash_batch(batch.batch_dir)
    before = tree_hash(batch.batch_dir)
    with pytest.raises(BackupError) as verified:
        verify_backup(batch.batch_dir)
    assert verified.value.reason == "registration_invalid"
    assert tree_hash(batch.batch_dir) == before
    target = tmp_path / "rejected-target"
    with pytest.raises(RestoreError) as restored:
        restore_backup(batch.batch_dir, target)
    assert restored.value.reason == "registration_invalid"
    assert not target.exists()
    assert tree_hash(batch.batch_dir) == before
