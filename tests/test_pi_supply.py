"""固定供给公共服务;仅网络和外部进程使用 fake。"""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from paper_radar.pi_supply import SupplyError, prepare_supply
from tests.pi_supply_support import encoded, inputs, prepare


def test_prepare_rejects_unknown_request_without_creating_root(tmp_path: Path) -> None:
    request = tmp_path / "request.yaml"
    request.write_text("command: SECRET-arbitrary-command\n")
    root = tmp_path / "install"
    with pytest.raises(SupplyError, match="request_invalid") as caught:
        prepare_supply(
            tmp_path / "missing.db",
            "f" * 64,
            "screening",
            request,
            root,
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
        )
    assert "SECRET" not in str(caught.value)
    assert not root.exists()


def test_prepare_freezes_materials_and_queries_without_network(tmp_path: Path) -> None:
    from paper_radar.pi_supply import list_supplies, show_supply

    database, snapshot, request, download, run = inputs(tmp_path)
    result = prepare_supply(
        database,
        snapshot[:8],
        "screening",
        request,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=download,
        runner=run,
    )
    assert list_supplies(database)[0].supply_id == result.supply_id
    record = show_supply(database, result.supply_id)
    assert record.manifest.pi_version == "1.3.0"
    assert (
        record.materials["package.json"]
        == download.content["https://pi.dev/api/installer/releases/1.3.0/package.json"]
    )
    evidence_hash = record.manifest.d5.evidence[0].sha256
    assert evidence_hash is not None
    assert record.materials[f"d5-evidence/{evidence_hash}.bin"] == (
        b"First supply; upstream reviewed.\n"
    )
    assert record.installs[0].install_id == result.install_id
    assert record.installs[0].checks[0].scope == "install_check"
    assert record.installs[0].checks[0].passed
    assert record.installs[0].path.is_dir()
    assert not record.installs[0].path.stat().st_mode & 0o222
    assert any("ci" in argv for argv, _, _ in run.calls)
    assert all("NODE_OPTIONS" not in env for _, _, env in run.calls)


def test_backup_rejects_broken_supply_material(tmp_path: Path) -> None:
    from paper_radar.backup import BackupError, create_backup

    database, snapshot, request, download, run = inputs(tmp_path)
    prepare_supply(
        database,
        snapshot,
        "screening",
        request,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=download,
        runner=run,
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE pi_supply_materials SET raw = ? WHERE role = ?",
            (
                b"SECRET corrupt material",
                "package.json",
            ),
        )
    with pytest.raises(BackupError) as caught:
        create_backup(database, tmp_path / "data", tmp_path / "backups")
    assert caught.value.reason.value == "supply_invalid"
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("format_version", True),
        ("node_version", "latest"),
        ("npm_version", "^10.9.3"),
        ("command", "SECRET command"),
    ],
)
def test_strict_request_rejected_before_io(
    tmp_path: Path, field: str, value: object
) -> None:
    source = inputs(tmp_path)
    request = source[2]
    payload = json.loads(request.read_bytes())
    payload[field] = value
    request.write_bytes(encoded(payload))
    with pytest.raises(SupplyError, match="request_invalid"):
        prepare(tmp_path, source)
    assert not source[3].calls
    assert not (tmp_path / "install").exists()


def test_concurrent_prepare_has_one_supply_and_one_instance(tmp_path: Path) -> None:
    from paper_radar.pi_supply import list_supplies
    from tests.pi_supply_support import Download

    source = inputs(tmp_path)
    barrier = Barrier(2)

    class ConcurrentDownload(Download):
        def fetch(self, url: str, *, limit: int, proxy: str | None) -> bytes:
            if url.endswith("/package.json"):
                barrier.wait(timeout=10)
            return super().fetch(url, limit=limit, proxy=proxy)

    source = (*source[:3], ConcurrentDownload(), source[4])
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = tuple(pool.map(lambda _: prepare(tmp_path, source), range(2)))
    assert first.supply_id == second.supply_id
    assert first.install_id == second.install_id
    assert first.reused_concurrent != second.reused_concurrent
    records = list_supplies(source[0])
    assert len(records) == len(records[0].installs) == 1
    assert not tuple((tmp_path / "install").glob(".staging-*"))


def test_failed_commit_leaves_no_fact_and_retry_recovers_published_tree(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import list_supplies

    source = inputs(tmp_path)
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "CREATE TRIGGER abort_supply BEFORE INSERT ON pi_supply_materials "
            "BEGIN SELECT RAISE(ABORT, 'SECRET interrupted'); END"
        )
    with pytest.raises(SupplyError, match="database_unavailable"):
        prepare(tmp_path, source)
    assert list_supplies(source[0]) == ()
    published = tuple((tmp_path / "install").glob("[0-9a-f]*/[0-9a-f]*"))
    assert len(published) == 1
    with sqlite3.connect(source[0]) as connection:
        connection.execute("DROP TRIGGER abort_supply")
    result = prepare(tmp_path, source)
    record = list_supplies(source[0])[0]
    assert record.installs[0].path == published[0]
    assert record.installs[0].install_id == result.install_id
    assert len(tuple((tmp_path / "install").glob("[0-9a-f]*/[0-9a-f]*"))) == 1


def test_repeat_prepare_with_changed_d5_requires_rebuild(tmp_path: Path) -> None:
    source = inputs(tmp_path)
    prepare(tmp_path, source)
    payload = json.loads(source[2].read_bytes())
    payload["d5"]["basis"] = "Changed nonsecret review basis"
    source[2].write_bytes(encoded(payload))
    source[4].calls.clear()
    with pytest.raises(SupplyError, match="already_prepared_use_rebuild"):
        prepare(tmp_path, source)
    assert not source[4].calls


def test_official_override_cannot_conflict_with_locked_version(tmp_path: Path) -> None:
    source = inputs(tmp_path)
    url = "https://pi.dev/api/installer/releases/1.3.0/package-lock.json"
    lock = json.loads(source[3].content[url])
    lock["packages"]["node_modules/protobufjs"] = {
        "version": "7.6.5",
        "resolved": "https://registry.npmjs.org/protobufjs/-/protobufjs-7.6.5.tgz",
        "integrity": "sha512-" + "A" * 86 + "==",
    }
    source[3].content[url] = encoded(lock)
    with pytest.raises(SupplyError, match="material_conflict"):
        prepare(tmp_path, source)


@pytest.mark.parametrize(
    "part", ["root_name", "root_version", "schema_bool", "lock_bool"]
)
def test_material_pair_rejects_inconsistent_identity(tmp_path: Path, part: str) -> None:
    source = inputs(tmp_path)
    suffix = "" if part == "schema_bool" else "/package-lock.json"
    url = "https://pi.dev/api/installer/releases/1.3.0" + suffix
    payload = json.loads(source[3].content[url])
    if part == "root_name":
        payload["packages"][""]["name"] = "another-package"
    elif part == "root_version":
        payload["packages"][""]["version"] = "1.2.0"
    elif part == "schema_bool":
        payload["schemaVersion"] = True
    else:
        payload["lockfileVersion"] = True
    source[3].content[url] = encoded(payload)
    with pytest.raises(SupplyError):
        prepare(tmp_path, source)


def test_concurrent_different_entry_cannot_freeze_second_supply(tmp_path: Path) -> None:
    from paper_radar.pi_supply import list_supplies
    from tests.pi_supply_support import PACKAGE_NAME, Download, Run

    source = inputs(tmp_path)
    barrier = Barrier(2)

    class ConcurrentDownload(Download):
        def fetch(self, url: str, *, limit: int, proxy: str | None) -> bytes:
            if url.endswith("/package.json"):
                barrier.wait(timeout=10)
            return super().fetch(url, limit=limit, proxy=proxy)

    class DifferentEntry(Run):
        def run(
            self,
            argv: tuple[str, ...],
            *,
            cwd: Path,
            env: dict[str, str],
            timeout: int,
            limit: int,
            pass_fds: tuple[int, ...] = (),
        ) -> bytes:
            output = super().run(argv, cwd=cwd, env=env, timeout=timeout, limit=limit)
            if "ci" in argv:
                package = cwd / "node_modules" / PACKAGE_NAME
                data = json.loads((package / "package.json").read_bytes())
                data["bin"]["pi"] = "dist/changed.js"
                (package / "package.json").write_bytes(encoded(data))
                (package / "dist/cli.js").rename(package / "dist/changed.js")
            return output

    sources = [
        (*source[:3], ConcurrentDownload(), Run()),
        (*source[:3], ConcurrentDownload(), DifferentEntry()),
    ]

    def attempt(index: int) -> object:
        try:
            return prepare(tmp_path, sources[index])
        except SupplyError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(attempt, range(2)))
    assert sum(isinstance(result, SupplyError) for result in outcomes) == 1
    assert len(list_supplies(source[0])) == 1
