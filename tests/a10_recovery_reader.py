"""独立进程只消费自包含批次,拒绝原目录/网络后重建全部公共投影。"""

import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from typer.testing import CliRunner

from paper_radar.backup.restore import restore_backup
from paper_radar.cli import app
from paper_radar.fixture_audit import FixtureAudit, FixtureError
from paper_radar.storage.artifacts import ArtifactStore
from tests.a10_recovery_support import audit_projection, old_projection
from tests.audit_matrix_support import MAIN
from tests.paper_recovery_reader import guard
from tests.paper_recovery_support import tree_hash
from tests.test_audit_reinterpret import SyntheticV2


def run() -> None:
    request = json.load(sys.stdin)
    root = Path(request["root"])
    guard([*request["forbidden"], str(root.parent / ".paper-radar-audit-locks")])
    if len(sys.argv) == 2:
        restore_backup(Path(sys.argv[1]), root)
    database = root / "database.sqlite3"
    before = tree_hash(root, ignore_sqlite_sidecars=True)
    with closing(sqlite3.connect(database)) as connection:
        dump = tuple(connection.iterdump())
    service = FixtureAudit(database, root)
    service.validate_all()
    assert old_projection(database, root, request["ids"]) == request["expected"]["old"]
    assert audit_projection(service) == request["expected"]["audit"]
    assert service.check(root / "absent-declaration.json").status == "source_missing"
    plan_id, summary = request["ids"]["summary"]
    assert (
        service.replay_audit(plan_id, summary_sha256=summary).semantic_sha256 == summary
    )
    plan_id, interpretation_id = request["ids"]["interpretation"]
    try:
        service.replay_audit_interpretation(plan_id, interpretation_id)
    except FixtureError as error:
        assert error.reason == "unsupported_history"
        assert all(marker not in str(error) for marker in request["markers"])
    else:
        raise AssertionError("missing v2 runtime was falsely accepted")
    v2 = service.replay_audit_interpretation(
        plan_id, interpretation_id, parser=SyntheticV2()
    )
    assert v2.proof_level == "available_material_reparsed"
    store = ArtifactStore(database, root)
    for artifact in request["ids"]["unbound"]:
        assert store.read_artifact(artifact)
    runner = CliRunner()
    for args in (
        ["fixture", "list", "--history"],
        ["audit", "show", plan_id],
        ["audit", "replay", plan_id],
    ):
        extra = [] if args[:2] == ["audit", "show"] else ["--data-root", str(root)]
        result = runner.invoke(
            app, [*args, "--database", str(database), *extra, "--json"]
        )
        assert result.exit_code == 0, "restored public CLI failed"
        assert all(marker not in result.stdout for marker in request["markers"])
        assert MAIN not in result.stdout
        assert "New v2 primary interpretation." not in result.stdout
    assert all(
        marker not in repr(service.list(history=True)) for marker in request["markers"]
    )
    for path in root.rglob("*"):
        if path.is_file():
            assert all(
                marker.encode() not in path.read_bytes()
                for marker in request["markers"]
            ), "private transport marker recovered"
    assert not list(root.rglob("*.lock"))
    assert not (root / ".paper-radar-audit-locks").exists()
    assert not (root / ".tools").exists()
    with closing(sqlite3.connect(database)) as connection:
        assert tuple(connection.iterdump()) == dump
    assert tree_hash(root, ignore_sqlite_sidecars=True) == before
    print(json.dumps({"read_only": True, "v2": v2.proof_level}))


if __name__ == "__main__":
    run()
