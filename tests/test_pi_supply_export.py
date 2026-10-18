"""固定材料导出的公共服务行为。"""

import os
import sqlite3
from pathlib import Path

import pytest

from paper_radar.pi_supply import SupplyError, export_supply, show_supply
from tests.pi_supply_support import inputs, prepare


def test_export_only_fixed_verified_original_materials(tmp_path: Path) -> None:
    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    record = show_supply(source[0], prepared.supply_id)
    target = tmp_path / "tools/pi"
    result = export_supply(source[0], prepared.supply_id, target)
    expected = {
        "package.json": record.materials["package.json"],
        "package-lock.json": record.materials["package-lock.json"],
        "release.json": record.materials["release.json"],
        "supply-manifest.json": record.manifest.canonical_bytes,
        "integrity-supplements.json": record.materials["integrity-supplements.json"],
        "SHASUMS256.txt": record.materials["SHASUMS256.txt"],
    }
    evidence = record.manifest.d5.evidence[0].sha256
    assert evidence is not None
    expected[f"d5-evidence/{evidence[:16]}.bin"] = b"First supply; upstream reviewed.\n"
    directory = target / prepared.supply_id
    assert {
        str(p.relative_to(directory)): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    } == expected
    assert set(result.files) == set(expected)
    assert set(result.created) == set(expected)


def test_export_is_noop_and_preflights_the_entire_group(tmp_path: Path) -> None:
    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    target = tmp_path / "tools/pi"
    export_supply(source[0], prepared.supply_id, target)
    directory = target / prepared.supply_id

    def metadata() -> dict[Path, tuple[int, int, int]]:
        return {
            path: (value.st_ino, value.st_mtime_ns, value.st_mode)
            for path in (directory, *directory.rglob("*"))
            for value in (path.stat(),)
        }

    before = metadata()
    second = export_supply(source[0], prepared.supply_id, target)
    assert second.created == ()
    assert metadata() == before
    (directory / "extra.txt").write_bytes(b"user file")
    (directory / "package.json").unlink()
    (directory / "release.json").write_bytes(b"do not overwrite")
    with pytest.raises(SupplyError, match="export_conflict"):
        export_supply(source[0], prepared.supply_id, target)
    assert not (directory / "package.json").exists()
    assert (directory / "release.json").read_bytes() == b"do not overwrite"
    assert (directory / "extra.txt").read_bytes() == b"user file"


def test_public_evidence_layout_deduplicates_and_rejects_short_name_collision() -> None:
    from paper_radar.pi_supply.export import export_evidence_layout

    digest = "a" * 16 + "0" * 48
    assert export_evidence_layout([digest, digest]) == (
        (digest, "d5-evidence/aaaaaaaaaaaaaaaa.bin"),
    )
    with pytest.raises(SupplyError, match="export_evidence_collision"):
        export_evidence_layout([digest, "a" * 16 + "1" * 48])
    with pytest.raises(SupplyError, match="supply_corrupt"):
        export_evidence_layout(["A" * 64])


def test_cli_export_has_pure_help_and_safe_arguments(tmp_path: Path) -> None:
    from tests.config_test_support import run_cli

    result = run_cli(tmp_path, "pi", "supply", "export", "--help", help_only=True)
    assert result.returncode == 0
    assert all(
        word in result.stdout
        for word in ("副作用", "配额", "输出", "示例", "--target", "不覆盖")
    )
    for args in (("SECRET-id",), ("--SECRET-bad", "SECRET-value")):
        result = run_cli(tmp_path, "pi", "supply", "export", *args)
        assert result.returncode == 2
        assert "SECRET" not in result.stderr + result.stdout
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("entry", ["target", "supply", "evidence", "file", "fifo"])
def test_unsafe_export_paths_never_touch_sentinel_or_create_missing_files(
    tmp_path: Path, entry: str
) -> None:
    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    target = tmp_path / "materials"
    directory = target / prepared.supply_id
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    (sentinel / "package.json").write_bytes(b"private sentinel")
    if entry == "target":
        target.symlink_to(sentinel, target_is_directory=True)
    else:
        target.mkdir()
        if entry == "supply":
            directory.symlink_to(sentinel, target_is_directory=True)
        else:
            directory.mkdir()
            if entry == "evidence":
                (directory / "d5-evidence").symlink_to(
                    sentinel, target_is_directory=True
                )
            elif entry == "file":
                (directory / "release.json").symlink_to(sentinel / "package.json")
            else:
                os.mkfifo(directory / "release.json")
    with pytest.raises(SupplyError):
        export_supply(source[0], prepared.supply_id, target)
    assert sorted(p.name for p in sentinel.iterdir()) == ["package.json"]
    assert (sentinel / "package.json").read_bytes() == b"private sentinel"
    assert not (directory / "SHASUMS256.txt").exists()


def test_corrupt_unselected_supply_prevents_any_export(tmp_path: Path) -> None:
    import json

    from tests.pi_supply_support import encoded

    source = inputs(tmp_path / "source")
    first = prepare(tmp_path / "source", source)
    source[3].content["https://pi.dev/api/installer/releases/1.3.0/package.json"] += (
        b"\n"
    )
    request = json.loads(source[2].read_bytes())
    request["d5"]["baseline_supply_id"] = first.supply_id
    source[2].write_bytes(encoded(request))
    second = prepare(tmp_path / "source", source)
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "UPDATE pi_supply_materials SET raw=? "
            "WHERE supply_id=? AND role='release.json'",
            (b"SECRET damaged", first.supply_id),
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    target = tmp_path / "materials"
    with pytest.raises(SupplyError, match="supply_corrupt") as error:
        export_supply(source[0], second.supply_id, target)
    assert "SECRET" not in str(error.value)
    assert not target.exists()


def test_cli_export_success_and_idempotence(tmp_path: Path) -> None:
    from tests.config_test_support import run_cli

    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    args = (
        "pi",
        "supply",
        "export",
        prepared.supply_id,
        "--database",
        str(source[0]),
        "--target",
        str(tmp_path / "materials"),
    )
    first = run_cli(tmp_path, *args)
    assert first.returncode == 0, first.stderr
    assert "files=7 created=7 result=passed" in first.stdout
    second = run_cli(tmp_path, *args)
    assert second.returncode == 0, second.stderr
    assert "files=7 created=0 result=passed" in second.stdout


def test_concurrent_exports_publish_complete_files_without_overwrite(
    tmp_path: Path,
) -> None:
    import subprocess
    import sys

    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    target = tmp_path / "materials"
    script = """
from pathlib import Path
from paper_radar.pi_supply import export_supply
import sys
export_supply(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                script,
                str(source[0]),
                prepared.supply_id,
                str(target),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(3)
    ]
    for process in processes:
        _, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
    result = export_supply(source[0], prepared.supply_id, target)
    assert result.created == ()
    assert len(tuple((target / prepared.supply_id).rglob("*.bin"))) == 1
    assert not tuple(target.rglob(".pi-export-*"))


def test_publication_io_failure_keeps_complete_items_and_allows_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import Any

    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    target = tmp_path / "materials"
    linked = os.link
    count = 0

    def fail_second(*args: Any, **kwargs: Any) -> None:
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("SECRET publication error")
        linked(*args, **kwargs)

    monkeypatch.setattr(os, "link", fail_second)
    with pytest.raises(SupplyError, match="export_failed") as caught:
        export_supply(source[0], prepared.supply_id, target)
    assert "SECRET" not in str(caught.value)
    directory = target / prepared.supply_id
    record = show_supply(source[0], prepared.supply_id)
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == {
        "package.json": record.materials["package.json"],
    }
    monkeypatch.undo()
    result = export_supply(source[0], prepared.supply_id, target)
    assert len(result.created) == 6
    assert "package.json" not in result.created


def test_publication_race_rechecks_external_file_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import Any

    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    target = tmp_path / "materials"
    linked = os.link
    directory = target / prepared.supply_id

    def insert_competing_file(source: Any, destination: Any, **kwargs: Any) -> None:
        if destination == "package.json":
            (directory / "package.json").write_bytes(b"external sentinel")
        linked(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", insert_competing_file)
    with pytest.raises(SupplyError, match="export_conflict"):
        export_supply(source[0], prepared.supply_id, target)
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == {
        "package.json": b"external sentinel",
    }


def test_missing_posix_filesystem_capability_is_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    target = tmp_path / "materials"
    monkeypatch.delattr(os, "O_DIRECTORY")
    from paper_radar.pi_supply import list_supplies

    assert show_supply(source[0], prepared.supply_id).supply_id == prepared.supply_id
    assert len(list_supplies(source[0])) == 1
    with pytest.raises(SupplyError, match="export_failed"):
        export_supply(source[0], prepared.supply_id, target)
    assert not target.exists()


def test_unsupported_directory_handles_are_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import Any

    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    target = tmp_path / "materials"
    opened = os.open

    def without_dir_fd(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if "dir_fd" in kwargs:
            raise NotImplementedError("SECRET unsupported directory handle")
        return opened(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", without_dir_fd)
    with pytest.raises(SupplyError, match="export_failed") as error:
        export_supply(source[0], prepared.supply_id, target)
    assert "SECRET" not in str(error.value)
    assert not target.exists()


@pytest.mark.parametrize(
    "destination",
    [
        "install",
        "inside_install",
        "parent_install",
        "database",
        "database_parent",
        "unavailable_install",
        "empty_registered_root",
        "other_supply",
    ],
)
def test_export_root_stays_separate_from_all_registered_installs_and_database(
    tmp_path: Path,
    destination: str,
) -> None:
    from paper_radar.pi_supply import prepare_supply, rebuild_supply
    from tests.pi_supply_support import Download, Run

    root = tmp_path / "source"
    source = inputs(root)
    prepared = prepare(root, source)
    other_root = tmp_path / "other-supply-install"
    if destination == "other_supply":
        source[3].content[
            "https://pi.dev/api/installer/releases/1.3.0/package.json"
        ] += b"\n"
        prepare_supply(
            source[0],
            source[1],
            "screening",
            source[2],
            other_root,
            data_root=root / "data",
            config_root=root / "config",
            material_root=root / "materials",
            downloader=source[3],
            runner=source[4],
        )
    reserved = tmp_path / "reserved-install"
    broken = Download()
    archive = next(url for url in broken.content if url.endswith(".tar.xz"))
    broken.content[archive] = b"invalid archive"
    with pytest.raises(SupplyError, match="node_checksum_mismatch"):
        rebuild_supply(
            source[0],
            prepared.supply_id,
            reserved,
            data_root=root / "data",
            config_root=root / "config",
            material_root=root / "materials",
            downloader=broken,
            runner=Run(),
        )
    targets = {
        "install": root / "install",
        "inside_install": root / "install/extra",
        "parent_install": root,
        "database": source[0],
        "database_parent": source[0].parent,
        "unavailable_install": root / "install",
        "empty_registered_root": reserved,
        "other_supply": other_root,
    }
    if destination == "unavailable_install":
        (root / "install").rename(tmp_path / "unavailable-install")
    target = targets[destination]

    def files() -> dict[Path, bytes]:
        # Read-only SQLite may create its own WAL shared-memory sidecars.
        auxiliary = {source[0].name + suffix for suffix in ("-wal", "-shm")}
        return {
            p: p.read_bytes()
            for p in target.rglob("*")
            if p.is_file() and p.name not in auxiliary
        }

    before = files()
    with pytest.raises(SupplyError, match="unsafe_root"):
        export_supply(source[0], prepared.supply_id, target)
    assert files() == before
