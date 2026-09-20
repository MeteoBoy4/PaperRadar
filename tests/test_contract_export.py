from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from paper_radar.contracts import (
    ContractExportError,
    ContractExportErrorCategory,
    ContractName,
    ContractVersion,
    ExportOutcome,
    build_frozen_contract,
    export_frozen_contract,
)
from tests.contract_snapshot_support import canonical_json_bytes


def _snapshot_files(root: Path) -> tuple[Path, Path]:
    snapshot_dir = root / "screening" / "boundary" / "v1"
    return snapshot_dir / "schema.json", snapshot_dir / "manifest.json"


def test_first_export_creates_complete_snapshot_and_repeat_does_not_rewrite(
    tmp_path: Path,
) -> None:
    expected = build_frozen_contract(ContractName.BOUNDARY, ContractVersion.V1)

    first = export_frozen_contract("boundary", "v1", tmp_path)
    schema_path, manifest_path = _snapshot_files(tmp_path)

    assert first.outcome is ExportOutcome.CREATED
    assert first.snapshot_dir == schema_path.parent
    assert first.schema_sha256 == expected.schema_sha256
    assert schema_path.read_bytes() == expected.schema_bytes
    assert manifest_path.read_bytes() == expected.manifest_bytes

    mtimes = (schema_path.stat().st_mtime_ns, manifest_path.stat().st_mtime_ns)
    second = export_frozen_contract("boundary", "v1", tmp_path)

    assert second.outcome is ExportOutcome.UNCHANGED
    assert (schema_path.stat().st_mtime_ns, manifest_path.stat().st_mtime_ns) == mtimes


def test_export_is_identical_across_directories_and_preserves_older_versions(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    old_snapshot = second_root / "screening" / "boundary" / "v0" / "schema.json"
    old_snapshot.parent.mkdir(parents=True)
    old_snapshot.write_text("historical snapshot", encoding="utf-8")

    export_frozen_contract("boundary", "v1", first_root)
    export_frozen_contract("boundary", "v1", second_root)

    first_schema, first_manifest = _snapshot_files(first_root)
    second_schema, second_manifest = _snapshot_files(second_root)
    assert first_schema.read_bytes() == second_schema.read_bytes()
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    assert old_snapshot.read_text(encoding="utf-8") == "historical snapshot"


@pytest.mark.parametrize("missing_filename", ["schema.json", "manifest.json"])
def test_incomplete_snapshot_is_reported_as_damaged(
    tmp_path: Path,
    missing_filename: str,
) -> None:
    export_frozen_contract("boundary", "v1", tmp_path)
    schema_path, manifest_path = _snapshot_files(tmp_path)
    {"schema.json": schema_path, "manifest.json": manifest_path}[
        missing_filename
    ].unlink()

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", tmp_path)

    assert captured.value.category is ContractExportErrorCategory.DAMAGED_SNAPSHOT
    assert "损坏或不完整" in str(captured.value)


def test_hash_mismatch_is_damaged_and_does_not_overwrite_snapshot(
    tmp_path: Path,
) -> None:
    export_frozen_contract("boundary", "v1", tmp_path)
    schema_path, manifest_path = _snapshot_files(tmp_path)
    manifest_before = manifest_path.read_bytes()
    schema_path.write_text('{"tampered": true}\n', encoding="utf-8")
    schema_before = schema_path.read_bytes()

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", tmp_path)

    assert captured.value.category is ContractExportErrorCategory.DAMAGED_SNAPSHOT
    assert schema_path.read_bytes() == schema_before
    assert manifest_path.read_bytes() == manifest_before


def test_consistent_but_wrong_version_metadata_is_reported_separately(
    tmp_path: Path,
) -> None:
    export_frozen_contract("boundary", "v1", tmp_path)
    schema_path, manifest_path = _snapshot_files(tmp_path)
    schema = json.loads(schema_path.read_bytes())
    schema["x-paper-radar-contract"]["version"] = "v2"
    changed_schema = canonical_json_bytes(schema)
    schema_path.write_bytes(changed_schema)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["version"] = "v2"
    manifest["schema_sha256"] = hashlib.sha256(changed_schema).hexdigest()
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", tmp_path)

    assert captured.value.category is ContractExportErrorCategory.VERSION_MISMATCH
    assert "版本信息不一致" in str(captured.value)


def test_consistent_same_version_different_schema_is_content_conflict(
    tmp_path: Path,
) -> None:
    export_frozen_contract("boundary", "v1", tmp_path)
    schema_path, manifest_path = _snapshot_files(tmp_path)
    schema = json.loads(schema_path.read_bytes())
    schema["description"] = "同版本的另一份有效内容"
    changed_schema = canonical_json_bytes(schema)
    schema_path.write_bytes(changed_schema)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["schema_sha256"] = hashlib.sha256(changed_schema).hexdigest()
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", tmp_path)

    assert captured.value.category is ContractExportErrorCategory.CONTENT_CONFLICT
    assert "新建版本" in str(captured.value)


@pytest.mark.parametrize(
    ("name", "version"),
    [("unknown", "v1"), ("boundary", "../v1"), ("boundary", "v2")],
)
def test_unknown_contract_and_invalid_version_are_rejected_before_path_creation(
    tmp_path: Path,
    name: str,
    version: str,
) -> None:
    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract(name, version, tmp_path)

    assert captured.value.category is ContractExportErrorCategory.INVALID_SELECTION
    assert list(tmp_path.iterdir()) == []


def test_generated_path_cannot_escape_target_through_a_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    outside = tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    (target / "screening").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", target)

    assert captured.value.category is ContractExportErrorCategory.PATH_ESCAPE
    assert list(outside.iterdir()) == []


def test_unresolvable_target_has_a_controlled_actionable_error(tmp_path: Path) -> None:
    target = tmp_path / "loop"
    target.symlink_to(target, target_is_directory=True)

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", target)

    assert captured.value.category is ContractExportErrorCategory.INVALID_TARGET
    assert "符号链接循环" in str(captured.value)


def test_broken_snapshot_symlink_is_not_treated_as_an_empty_version(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "screening" / "boundary" / "v1"
    snapshot_dir.parent.mkdir(parents=True)
    snapshot_dir.symlink_to(tmp_path / "missing-snapshot", target_is_directory=True)

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", tmp_path)

    assert captured.value.category is ContractExportErrorCategory.DAMAGED_SNAPSHOT
    assert snapshot_dir.is_symlink()


def test_interrupted_publish_keeps_history_and_leaves_no_partial_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical = tmp_path / "screening" / "boundary" / "v0" / "schema.json"
    historical.parent.mkdir(parents=True)
    historical.write_text("historical snapshot", encoding="utf-8")

    def interrupt_publish(source: object, destination: object) -> None:
        del source, destination
        raise InterruptedError("synthetic-secret-interruption")

    monkeypatch.setattr(os, "replace", interrupt_publish)

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", tmp_path)

    version_parent = tmp_path / "screening" / "boundary"
    assert captured.value.category is ContractExportErrorCategory.WRITE_FAILED
    assert "synthetic-secret-interruption" not in str(captured.value)
    assert historical.read_text(encoding="utf-8") == "historical snapshot"
    assert not (version_parent / "v1").exists()
    assert {path.name for path in version_parent.iterdir()} == {"v0"}


def test_uncontrolled_json_in_snapshot_is_damaged_not_a_traceback(
    tmp_path: Path,
) -> None:
    export_frozen_contract("boundary", "v1", tmp_path)
    schema_path, _manifest_path = _snapshot_files(tmp_path)
    schema_path.write_bytes(b'{"x": "\\ud800"}')
    tampered = schema_path.read_bytes()

    with pytest.raises(ContractExportError) as captured:
        export_frozen_contract("boundary", "v1", tmp_path)

    assert captured.value.category is ContractExportErrorCategory.DAMAGED_SNAPSHOT
    assert schema_path.read_bytes() == tampered


def test_inaccessible_target_is_reported_as_write_failure(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    original_mode = stat.S_IMODE(target.stat().st_mode)
    target.chmod(0o000)
    try:
        with pytest.raises(ContractExportError) as captured:
            export_frozen_contract("boundary", "v1", target)
    finally:
        target.chmod(original_mode)

    assert captured.value.category is ContractExportErrorCategory.WRITE_FAILED
    assert "不可访问" in str(captured.value)
    assert list(target.iterdir()) == []


def test_unwritable_target_fails_without_publishing_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir(mode=0o500)
    try:
        with pytest.raises(ContractExportError) as captured:
            export_frozen_contract("boundary", "v1", target)
    finally:
        target.chmod(0o700)

    assert captured.value.category is ContractExportErrorCategory.WRITE_FAILED
    assert "目录权限" in str(captured.value)
    assert not (target / "screening" / "boundary" / "v1").exists()
