"""冻结契约只读检查的公共接口测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from paper_radar.contracts import (
    ContractCheckError,
    ContractCheckErrorCategory,
    ContractName,
    ContractVersion,
    build_frozen_contract,
    check_frozen_contract,
    export_frozen_contract,
)
from tests.contract_snapshot_support import (
    canonical_json_bytes,
    filesystem_fingerprint,
)

_SNAPSHOT_PARTS = ("screening", "boundary", "v1")


def _create_snapshot(root: Path) -> Path:
    export_frozen_contract("boundary", "v1", root)
    return root.joinpath(*_SNAPSHOT_PARTS)


def _rewrite_schema(
    snapshot_dir: Path,
    schema: object,
    *,
    version: str = "v1",
) -> None:
    schema_bytes = canonical_json_bytes(schema)
    (snapshot_dir / "schema.json").write_bytes(schema_bytes)
    manifest = json.loads((snapshot_dir / "manifest.json").read_bytes())
    manifest["version"] = version
    manifest["schema_sha256"] = hashlib.sha256(schema_bytes).hexdigest()
    (snapshot_dir / "manifest.json").write_bytes(canonical_json_bytes(manifest))


def test_consistent_snapshot_passes_and_reports_identity_and_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    expected = build_frozen_contract(ContractName.BOUNDARY, ContractVersion.V1)
    before = filesystem_fingerprint(root)

    result = check_frozen_contract("boundary", "v1", root)

    assert result.name is ContractName.BOUNDARY
    assert result.version is ContractVersion.V1
    assert result.snapshot_dir == snapshot_dir
    assert result.schema_sha256 == expected.schema_sha256
    assert filesystem_fingerprint(root) == before


def test_missing_snapshot_is_reported_without_creating_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.MISSING_SNAPSHOT
    assert "boundary" in str(captured.value)
    assert "v1" in str(captured.value)
    assert not root.exists()


@pytest.mark.parametrize("missing", ["version-dir", "manifest", "schema"])
def test_absent_or_incomplete_snapshot_is_missing_and_not_repaired(
    tmp_path: Path,
    missing: str,
) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    if missing != "version-dir":
        snapshot_dir = _create_snapshot(root)
        (snapshot_dir / f"{missing}.json").unlink()
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.MISSING_SNAPSHOT
    assert filesystem_fingerprint(root) == before


def test_tampered_snapshot_is_damaged_and_not_rewritten(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    (snapshot_dir / "schema.json").write_text('{"tampered": true}\n', encoding="utf-8")
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.DAMAGED_SNAPSHOT
    assert filesystem_fingerprint(root) == before


def test_check_errors_do_not_leak_snapshot_content(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    (snapshot_dir / "schema.json").write_text(
        '{"synthetic-secret-contract-check": "sk-test-123"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    message = str(captured.value)
    assert captured.value.category is ContractCheckErrorCategory.DAMAGED_SNAPSHOT
    assert "synthetic-secret-contract-check" not in message
    assert "sk-test-123" not in message


def test_unreadable_snapshot_is_reported_separately_from_damage(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    schema_path = snapshot_dir / "schema.json"
    schema_path.chmod(0o000)
    try:
        before = filesystem_fingerprint(root)

        with pytest.raises(ContractCheckError) as captured:
            check_frozen_contract("boundary", "v1", root)

        assert captured.value.category is ContractCheckErrorCategory.UNREADABLE_SNAPSHOT
        assert "权限" in str(captured.value)
        assert filesystem_fingerprint(root) == before
    finally:
        schema_path.chmod(0o600)


def test_version_mismatch_is_reported_separately_from_drift(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    schema = json.loads((snapshot_dir / "schema.json").read_bytes())
    schema["x-paper-radar-contract"]["version"] = "v2"
    _rewrite_schema(snapshot_dir, schema, version="v2")
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.VERSION_MISMATCH
    assert "boundary v1" in str(captured.value)
    assert filesystem_fingerprint(root) == before


def test_content_drift_is_reported_without_refreshing_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    schema = json.loads((snapshot_dir / "schema.json").read_bytes())
    schema["description"] = "同版本的另一份有效内容"
    _rewrite_schema(snapshot_dir, schema)
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.CONTENT_DRIFT
    assert "新建版本" in str(captured.value)
    assert filesystem_fingerprint(root) == before


@pytest.mark.parametrize(
    ("name", "version"),
    [("unknown", "v1"), ("boundary", "../v1"), ("boundary", "v2")],
)
def test_invalid_selection_is_rejected_before_touching_target(
    tmp_path: Path,
    name: str,
    version: str,
) -> None:
    root = tmp_path / "contracts"

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract(name, version, root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_SELECTION
    assert not root.exists()


def test_target_that_is_not_a_directory_is_invalid_target(tmp_path: Path) -> None:
    root = tmp_path / "occupied"
    root.write_text("occupied", encoding="utf-8")

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_TARGET
    assert root.read_text(encoding="utf-8") == "occupied"


def test_symlink_path_escape_is_rejected_without_touching_outside(
    tmp_path: Path,
) -> None:
    root = tmp_path / "target"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "screening").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.PATH_ESCAPE
    assert list(outside.iterdir()) == []
    assert (root / "screening").is_symlink()


def test_unresolvable_target_symlink_loop_is_invalid_target(tmp_path: Path) -> None:
    root = tmp_path / "loop"
    root.symlink_to(root, target_is_directory=True)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_TARGET
    assert root.is_symlink()
