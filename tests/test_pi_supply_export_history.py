"""非空 WAL、多供给/D5/多实例激活的完全隔离历史恢复。"""

import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from paper_radar.backup import create_backup, restore_backup, verify_backup
from paper_radar.pi_supply import (
    SupplyError,
    activate_supply,
    activation_history,
    doctor_supply,
    export_supply,
    list_supplies,
    rebuild_supply,
    show_supply,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.pi_supply_support import Download, Run, encoded, inputs, prepare
from tests.restore_support import history_view


def test_full_wal_history_exports_without_original_roots_then_explicit_rebuild(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = inputs(root)
    database, snapshot, request, download, runner = source
    first = prepare(root, source)
    previous = show_supply(database, first.supply_id)
    activate_supply(database, first.supply_id, snapshot)
    (root / "second-evidence.txt").write_bytes(b"Second independent audit evidence.\n")
    payload = json.loads(request.read_bytes())
    payload["d5"] = {
        "decision": "no_change",
        "basis": "Only official material formatting changed",
        "baseline_supply_id": first.supply_id,
        "evidence": [
            {"kind": "evidence_file", "path": "evidence.txt"},
            {"kind": "evidence_file", "path": "second-evidence.txt"},
            {"kind": "evidence_file", "path": "evidence.txt"},
            {
                "kind": "supply_material",
                "supply_id": first.supply_id,
                "material": "release.json",
            },
            {
                "kind": "supply_record",
                "supply_id": first.supply_id,
                "check_id": previous.installs[0].checks[0].check_id,
            },
        ],
    }
    request.write_bytes(encoded(payload))
    download.content["https://pi.dev/api/installer/releases/1.3.0/package.json"] += (
        b"\n"
    )
    second = prepare(root, source)
    activate_supply(database, second.supply_id, snapshot)
    rebuilt = rebuild_supply(
        database,
        second.supply_id,
        root / "install",
        data_root=root / "data",
        config_root=root / "config",
        material_root=root / "materials",
        downloader=download,
        runner=runner,
    )
    activate_supply(database, second.supply_id, snapshot)
    assert activation_history(database)[-1].install_id == rebuilt.install_id
    broken_download = Download()
    archive_url = next(
        url for url in broken_download.content if url.endswith(".tar.xz")
    )
    broken_download.content[archive_url] = b"corrupt archive"
    try:
        rebuild_supply(
            database,
            second.supply_id,
            root / "install",
            data_root=root / "data",
            config_root=root / "config",
            material_root=root / "materials",
            downloader=broken_download,
            runner=Run(),
        )
    except SupplyError as error:
        assert error.reason == "node_checksum_mismatch"
    else:
        raise AssertionError("corrupt archive unexpectedly rebuilt")
    store = ArtifactStore(database, root / "data")
    store.publish_single("original_pdf", [b"old original PDF"])
    store.publish_single("source_snapshot", [b"old source observation"])
    export_supply(database, second.supply_id, root / "materials")
    records = list_supplies(database)
    history = activation_history(database)
    old_facts = history_view(database, root / "data")
    # Hold a real reader while a new committed event remains in the nonempty WAL.
    with sqlite3.connect(database) as held:
        held.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        held.execute("BEGIN")
        held.execute("SELECT count(*) FROM pi_activation_events").fetchone()
        activate_supply(database, second.supply_id, snapshot)
        history = activation_history(database)
        assert Path(str(database) + "-wal").stat().st_size > 32
        batch = create_backup(database, root / "data", tmp_path / "backups")
        held.rollback()
    manifest = verify_backup(batch.batch_dir).manifest
    assert manifest.format_version == 1
    assert not any(
        name in str(manifest.model_dump())
        for name in ("install_root", "supply_id", "materials/", ".tar.xz")
    )
    # Even the source SQLite, configuration, request, exports and runtime roots vanish.
    root.rename(tmp_path / "unavailable-source")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    restored_db = restored.target_dir / "database.sqlite3"
    assert list_supplies(restored_db) == records
    assert activation_history(restored_db) == history
    assert history_view(restored_db, restored.target_dir) == old_facts
    export_root = tmp_path / "restored-materials"
    # Fresh process: fail at every external program/network/platform probe boundary.
    program = r"""
import json, platform, socket, subprocess, sys
from pathlib import Path
from dataclasses import asdict
from paper_radar.pi_supply import (
    list_supplies, show_supply, export_supply, activation_history,
)

def forbidden(*args, **kwargs):
    raise AssertionError("external capability used during isolated query")
platform.machine = lambda: "unsupported-architecture"
platform.system = lambda: "UnsupportedOS"
platform.libc_ver = lambda: ("unsupported-libc", "0")
class NoSocket(socket.socket):
    def __new__(cls, *args, **kwargs):
        return forbidden()
socket.socket = NoSocket
subprocess.Popen = forbidden
records = list_supplies(Path(sys.argv[1]))
for record in records:
    assert show_supply(Path(sys.argv[1]), record.supply_id) == record
    result = export_supply(Path(sys.argv[1]), record.supply_id, Path(sys.argv[2]))
    digests = {e.sha256 for e in record.manifest.d5.evidence
               if e.kind == "evidence_file"}
    assert len(result.files) == 6 + len(digests)
print(json.dumps({
    "ids": [r.supply_id for r in records],
    "history": [asdict(a) for a in activation_history(Path(sys.argv[1]))],
}, default=str, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(restored_db), str(export_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == json.loads(
        json.dumps(
            {
                "ids": [r.supply_id for r in records],
                "history": [asdict(a) for a in history],
            },
            default=str,
        )
    )
    for record in records:
        exported = export_root / record.supply_id
        assert (
            exported / "supply-manifest.json"
        ).read_bytes() == record.manifest.canonical_bytes
        for name, raw in record.materials.items():
            if name == "derived-lock.json":
                assert not (exported / name).exists()
            else:
                output_name = (
                    f"d5-evidence/{name.split('/')[1][:16]}.bin"
                    if name.startswith("d5-evidence/")
                    else name
                )
                assert (exported / output_name).read_bytes() == raw
    report = doctor_supply(restored_db, snapshot)
    assert not report.passed and "install_unavailable" in report.blockers
    assert activation_history(restored_db) == history
    new = rebuild_supply(
        restored_db,
        second.supply_id,
        tmp_path / "new-install",
        data_root=restored.target_dir,
        config_root=tmp_path / "new-config",
        material_root=export_root,
        downloader=download,
        runner=Run(),
    )
    assert not doctor_supply(restored_db, snapshot).passed
    assert activation_history(restored_db) == history
    after = show_supply(restored_db, second.supply_id)
    original = next(
        record for record in records if record.supply_id == second.supply_id
    )
    assert after.manifest == original.manifest and after.materials == original.materials
    assert after.installs[:-1] == original.installs
    assert after.rebuild_failures == original.rebuild_failures
    selected = activate_supply(restored_db, second.supply_id, snapshot)
    assert selected.install_id == new.install_id
    report = doctor_supply(restored_db, snapshot)
    assert report.passed
    assert all(
        item.present is False
        for item in report.instances
        if item.install_id != new.install_id
    )
    assert activation_history(restored_db)[:-1] == history
    assert history_view(restored_db, restored.target_dir) == old_facts
