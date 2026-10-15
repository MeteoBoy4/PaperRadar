"""#27 公共只读查询边界。真实迁移与固定 SQLite 材料。"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    compile_config,
    list_config_snapshots,
    resolve_config_snapshot_reference,
)
from tests.config_projection_support import empty_inputs, full_inputs
from tests.config_snapshot_support import (
    checkpoint,
    database_damage,
    insert_index_records,
)


def test_initialized_database_without_snapshots_has_empty_listing(
    tmp_path: Path,
) -> None:
    _, database = empty_inputs(tmp_path)
    assert list_config_snapshots(database) == ()


def test_listing_exposes_only_ids_audit_time_and_controlled_versions(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE runtime_config_snapshots SET created_at = ?",
            ("2026-10-15T01:00:00+00:00",),
        )
    (summary,) = list_config_snapshots(database)
    assert summary.snapshot_id == snapshot.snapshot_id
    assert summary.short_reference == snapshot.snapshot_id[:8]
    assert summary.created_at == datetime(2026, 10, 15, 1, tzinfo=UTC)
    assert ("profile", "profile", "profile-v1") in {
        (version.kind.value, version.name, version.version)
        for version in summary.versions
    }
    assert ("adapter", "pi-rpc", "pi-v1") in {
        (version.kind.value, version.name, version.version)
        for version in summary.versions
    }
    assert "Boundary prompt" not in repr(summary)
    assert "climate" not in repr(summary)


def test_all_snapshots_define_prefixes_and_stable_audit_order(tmp_path: Path) -> None:
    _, database = empty_inputs(tmp_path)
    first = "12345678" + "a" * 56
    second = "12345678" + "b" * 56
    extreme_a = "c" * 63 + "0"
    extreme_b = "c" * 63 + "1"
    insert_index_records(
        database,
        [
            (second, "2026-10-14T22:00:00+00:00"),
            (first, "2026-10-15T06:00:00+08:00"),
            (extreme_b, ""),
            (extreme_a, ""),
            ("d" * 64, "2026-10-15T00:00:00Z"),
        ],
    )
    summaries = list_config_snapshots(database)
    assert tuple(s.snapshot_id for s in summaries) == (
        "d" * 64,
        first,
        second,
        extreme_a,
        extreme_b,
    )
    assert tuple(s.short_reference for s in summaries) == (
        "d" * 8,
        "12345678a",
        "12345678b",
        extreme_a,
        extreme_b,
    )
    assert summaries[-1].created_at is None
    for summary in summaries:
        assert (
            resolve_config_snapshot_reference(database, summary.short_reference)
            == summary.snapshot_id
        )


def test_references_resolve_against_all_records_and_recheck_uniqueness(
    tmp_path: Path,
) -> None:
    _, database = empty_inputs(tmp_path)
    snapshot_id = "12345678" + "a" * 56
    insert_index_records(database, [(snapshot_id, "")])
    for reference in (snapshot_id, snapshot_id[:8], snapshot_id[:20], snapshot_id[:63]):
        assert resolve_config_snapshot_reference(database, reference) == snapshot_id
    insert_index_records(database, [("12345678" + "b" * 56, "")])
    with pytest.raises(ConfigError, match="补充字符"):
        resolve_config_snapshot_reference(database, "12345678")
    with pytest.raises(ConfigError, match="未找到快照"):
        resolve_config_snapshot_reference(database, "0" * 8)
    with pytest.raises(ConfigError, match="未找到快照"):
        resolve_config_snapshot_reference(database, "0" * 64)


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "a" * 7,
        "a" * 65,
        "A" * 8,
        "A" * 64,
        "x" * 8,
        " aaaaaaaa",
        "aaaaaaaa\n",
        "latest",
        "PRIVATE_INPUT_MARKER",
    ],
)
def test_reference_format_is_strict_without_echoing_inputs(
    tmp_path: Path, reference: str
) -> None:
    _, database = empty_inputs(tmp_path)
    with pytest.raises(ConfigError, match="8–63") as error:
        resolve_config_snapshot_reference(database, reference)
    if reference:
        assert reference not in str(error.value)


@pytest.mark.parametrize(
    "damage",
    [
        "missing_database",
        "uninitialized",
        "missing_revision",
        "old_revision",
        "future_revision",
        "missing_table",
    ],
)
def test_queries_reject_unavailable_archives_without_writes(
    tmp_path: Path, damage: str
) -> None:
    _, database = empty_inputs(tmp_path)
    if damage == "missing_database":
        database = tmp_path / "missing.sqlite3"
    else:
        database_damage(database, damage)
    original = database.read_bytes() if database.exists() else None
    for query in (
        lambda: list_config_snapshots(database),
        lambda: resolve_config_snapshot_reference(database, "a" * 8),
    ):
        with pytest.raises(ConfigError) as error:
            query()
        assert "PRIVATE_REVISION_MARKER" not in str(error.value)
        assert "SELECT" not in str(error.value)
        assert (database.read_bytes() if database.exists() else None) == original


def test_listing_and_resolution_are_discovery_not_payload_validation(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE runtime_config_snapshots SET payload_json = ?",
            ("PRIVATE_DAMAGE_MARKER",),
        )
    checkpoint(database)
    original = database.read_bytes()
    assert list_config_snapshots(database)[0].snapshot_id == snapshot.snapshot_id
    assert (
        resolve_config_snapshot_reference(database, snapshot.snapshot_id[:8])
        == snapshot.snapshot_id
    )
    assert database.read_bytes() == original


@pytest.mark.parametrize(
    "column,value",
    [
        ("kind", "PRIVATE_KIND_MARKER"),
        ("name", "PRIVATE_NAME_MARKER"),
        ("declared_version", "PRIVATE_VERSION_MARKER"),
    ],
)
def test_listing_rejects_uncontrolled_summary_fields_without_echoing_them(
    tmp_path: Path,
    column: str,
    value: str,
) -> None:
    settings, database = full_inputs(tmp_path)
    compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"UPDATE snapshot_version_refs SET {column} = ? WHERE kind = 'profile'",
            (value,),
        )
    with pytest.raises(ConfigError, match="版本摘要损坏") as error:
        list_config_snapshots(database)
    assert value not in str(error.value)
