"""B-E15 独立 D1: 登记/文件故障、并发范围变化及冻结源损坏。"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from paper_radar.experiment.exposure import ExposureError, Exposures
from paper_radar.storage.artifacts import ArtifactStore
from tests.artifact_support import fail_sql
from tests.exposure_support import backup, decision, exposed, initialized, payload
from tests.test_experiment_candidates_cli import invoke
from tests.test_experiment_exposure_cli import export


@pytest.mark.parametrize("stop", ["INSERT INTO exposure_exports", "fsync", "link"])
def test_interrupted_publication_is_retriable_and_does_not_leak_private_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    root = initialized(tmp_path / "experiment")
    exposed(root)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("PRIVATE_PUBLICATION_FAILURE")

    if stop.startswith("INSERT"):
        with fail_sql(stop):
            interrupted = invoke("export-exposure", "--root", str(root.root))
    else:
        with monkeypatch.context() as crash:
            crash.setattr(os, stop, fail)
            interrupted = invoke("export-exposure", "--root", str(root.root))
    assert interrupted.exit_code == 2
    assert (
        "execution_failed" if stop.startswith("INSERT") else "publication_failed"
    ) in interrupted.output
    assert "PRIVATE_PUBLICATION_FAILURE" not in interrupted.output
    receipt = export(root.root)
    original = (root.views / receipt["relative_path"]).read_bytes()
    assert export(root.root) == receipt
    assert (root.views / receipt["relative_path"]).read_bytes() == original
    assert list(root.views.glob("exposure/.exposure-*")) == []


def test_final_short_transaction_rejects_facts_added_after_capture(
    tmp_path: Path,
) -> None:
    root = initialized(tmp_path / "experiment")
    paper_id, _ = exposed(root)
    service = Exposures(root.database, root.data_root)
    transactions = 0
    injected = False

    def append_before_lock(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        nonlocal transactions, injected
        if statement == "BEGIN IMMEDIATE" and not injected:
            transactions += 1
            if transactions == 2:
                injected = True
                decision(root, paper_id, "late-decision")

    event.listen(Engine, "before_cursor_execute", append_before_lock)
    try:
        with pytest.raises(ExposureError, match="facts_changed"):
            service.export()
    finally:
        event.remove(Engine, "before_cursor_execute", append_before_lock)
    assert injected
    receipt = export(root.root)
    assert service.receipt(receipt["export_id"]) == receipt


@pytest.mark.parametrize(
    "damage",
    ["payload", "audit-omission", "source-omission", "source-reference", "root"],
)
def test_backup_refuses_tampered_export_or_frozen_source_closure(
    tmp_path: Path, damage: str
) -> None:
    root = initialized(tmp_path / "experiment")
    paper_id, _ = exposed(root)
    receipt, _, raw = payload(root)
    store = ArtifactStore(root.database, root.data_root)
    (artifact,) = [a for a in store.list_artifacts() if a.kind == "exposure_manifest"]
    members = store.read_artifact(artifact.artifact_id)
    if damage in {"payload", "audit-omission", "root"}:
        audit = json.loads(members["audit"])
        document = json.loads(raw)
        if damage == "payload":
            document["papers"] = []
        elif damage == "root":
            document["root_id"] = audit["root_id"] = "forged-root"
        else:
            page = next(p for p in audit["pages"] if p["table"] == "body_decisions")
            page["rows"] = []
            page["identities"] = []
            document["papers"] = []

        def encode(value: object) -> bytes:
            return json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()

        new_payload, new_audit = encode(document), encode(audit)
        replacement = store.publish_artifact(
            "exposure_manifest", {"payload": [new_payload], "audit": [new_audit]}
        )
        with sqlite3.connect(root.database) as connection:
            connection.execute("DROP TRIGGER exposure_exports_no_update")
            connection.execute(
                "UPDATE exposure_exports SET export_id=?,root_id=?,"
                "artifact_id=?,audit_sha256=?",
                (
                    hashlib.sha256(new_payload).hexdigest(),
                    audit["root_id"],
                    replacement.artifact_id,
                    hashlib.sha256(new_audit).hexdigest(),
                ),
            )
    else:
        with sqlite3.connect(root.database) as connection:
            action = "delete" if damage == "source-omission" else "update"
            connection.execute(f"DROP TRIGGER IF EXISTS body_decisions_no_{action}")
            if damage == "source-omission":
                connection.execute(
                    "DELETE FROM body_decisions WHERE paper_id=?", (paper_id,)
                )
            else:
                connection.execute(
                    "UPDATE body_decisions SET sequence=99 WHERE paper_id=?",
                    (paper_id,),
                )
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 2 and "registration_invalid" in saved.output
    assert "PRIVATE_" not in saved.output
    assert receipt["export_id"]


def test_export_view_refuses_symlinks_and_changed_bytes(tmp_path: Path) -> None:
    root = initialized(tmp_path / "experiment")
    exposed(root)
    receipt, _, original = payload(root)
    path = root.views / receipt["relative_path"]
    path.write_bytes(original + b"PRIVATE_TAMPER")
    changed = invoke("export-exposure", "--root", str(root.root))
    assert changed.exit_code == 2 and "content_corrupt" in changed.output
    assert "PRIVATE_TAMPER" not in changed.output
    path.unlink()
    outside = tmp_path / "private-outside"
    outside.write_bytes(b"PRIVATE_OUTSIDE")
    path.symlink_to(outside)
    linked = invoke("export-exposure", "--root", str(root.root))
    assert linked.exit_code == 2 and "unsafe_path" in linked.output
    assert outside.read_bytes() == b"PRIVATE_OUTSIDE"


@pytest.mark.parametrize("boundary", ["view_fsync", "view_link", "interrupt"])
def test_registered_export_survives_view_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    root = initialized(tmp_path / "experiment")
    exposed(root)
    original_fsync = os.fsync
    original_link = os.link

    def fsync(descriptor: int) -> None:
        if "/.exposure-" in os.readlink(f"/proc/self/fd/{descriptor}"):
            raise OSError("PRIVATE_VIEW_FAILURE")
        original_fsync(descriptor)

    def link(source: str | Path, target: str | Path, **kwargs: Any) -> None:
        if str(target).endswith(".json"):
            if boundary == "interrupt":
                raise KeyboardInterrupt
            raise OSError("PRIVATE_VIEW_FAILURE")
        original_link(source, target, **kwargs)

    with monkeypatch.context() as crash:
        crash.setattr(
            os,
            "fsync" if boundary == "view_fsync" else "link",
            fsync if boundary == "view_fsync" else link,
        )
        result = invoke("export-exposure", "--root", str(root.root))
    assert result.exit_code == (130 if boundary == "interrupt" else 2)
    assert (
        "interrupted" if boundary == "interrupt" else "execution_failed"
    ) in result.output
    assert "PRIVATE_VIEW_FAILURE" not in result.output
    receipt = export(root.root)
    assert (
        Exposures(root.database, root.data_root).receipt(receipt["export_id"])
        == receipt
    )
    assert list(root.views.glob("exposure/.exposure-*")) == []


def test_concurrent_identical_export_converges_to_one_registration(
    tmp_path: Path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    root = initialized(tmp_path / "experiment")
    exposed(root)

    def create() -> dict[str, object]:
        return Exposures(root.database, root.data_root).export()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create), pool.submit(create)]
        receipts = [future.result() for future in futures]
    assert receipts[0] == receipts[1]
    artifacts = ArtifactStore(root.database, root.data_root).list_artifacts()
    assert (
        len(
            [artifact for artifact in artifacts if artifact.kind == "exposure_manifest"]
        )
        == 1
    )
    assert export(root.root) == receipts[0]
