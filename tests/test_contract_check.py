"""冻结契约只读检查的公共接口测试。"""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

import pytest

from paper_radar.contracts import (
    ContractBatchCheckResult,
    ContractCheckError,
    ContractCheckErrorCategory,
    ContractCheckOutcome,
    ContractName,
    ContractVersion,
    build_frozen_contract,
    check_frozen_contract,
    check_frozen_contracts,
    export_frozen_contract,
    export_frozen_contracts,
)
from tests.contract_snapshot_support import (
    canonical_json_bytes,
    filesystem_fingerprint,
    install_self_consistent_schema,
    self_consistent_huge_integer_schema,
)

_SNAPSHOT_PARTS = ("screening", "boundary", "v1")

_MALFORMED_SCHEMA_PAYLOADS = {
    "unpaired-surrogate": b'{"x": "\\ud800"}',
    "huge-integer": b'{"x": ' + b"1" * 5000 + b"}",
    "nan-constant": b'{"x": NaN}',
    "infinity-constant": b'{"x": -Infinity}',
    "deep-nesting": b"[" * 200_000 + b"]" * 200_000,
}


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


def test_batch_check_reports_every_selected_contract_in_declaration_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    requested = (
        "decision-reasons",
        "boundary",
        "reuse-assessment",
        "value-prediction",
    )
    export_frozen_contracts(requested, "v1", root)
    boundary = root / "screening" / "boundary" / "v1"
    (boundary / "schema.json").write_text(
        '{"synthetic-secret-batch-check": true}\n',
        encoding="utf-8",
    )
    value = root / "screening" / "value-prediction" / "v1"
    (value / "manifest.json").unlink()
    before = filesystem_fingerprint(root)

    result = check_frozen_contracts(requested, "v1", root)

    assert isinstance(result, ContractBatchCheckResult)
    assert result.passed is False
    assert [item.name.value for item in result.items] == [
        "boundary",
        "value-prediction",
        "reuse-assessment",
        "decision-reasons",
    ]
    assert [item.outcome for item in result.items] == [
        ContractCheckOutcome.FAILED,
        ContractCheckOutcome.FAILED,
        ContractCheckOutcome.PASSED,
        ContractCheckOutcome.PASSED,
    ]
    assert [item.error_category for item in result.items] == [
        ContractCheckErrorCategory.DAMAGED_SNAPSHOT,
        ContractCheckErrorCategory.MISSING_SNAPSHOT,
        None,
        None,
    ]
    assert [item.message_zh for item in result.items[2:]] == [
        "冻结契约一致：",
        "冻结契约一致：",
    ]
    assert "synthetic-secret-batch-check" not in "".join(
        item.message_zh for item in result.items
    )
    assert filesystem_fingerprint(root) == before


def test_batch_check_rejects_all_selections_before_checking_any_contract(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contracts(("boundary", "unknown"), "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_SELECTION
    assert filesystem_fingerprint(root) == before


def test_batch_check_rejects_duplicate_selection_before_reading_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contracts(("boundary", "boundary"), "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_SELECTION
    assert "重复选择" in str(captured.value)
    assert not root.exists()


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


@pytest.mark.parametrize(
    "payload",
    _MALFORMED_SCHEMA_PAYLOADS.values(),
    ids=_MALFORMED_SCHEMA_PAYLOADS.keys(),
)
def test_malformed_snapshot_content_is_damaged_and_not_rewritten(
    tmp_path: Path,
    payload: bytes,
) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    (snapshot_dir / "schema.json").write_bytes(payload)
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.DAMAGED_SNAPSHOT
    assert filesystem_fingerprint(root) == before


def test_nonstandard_json_constants_are_damaged_even_when_consistent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    install_self_consistent_schema(snapshot_dir, b'{\n  "x": NaN\n}\n')
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.DAMAGED_SNAPSHOT
    assert filesystem_fingerprint(root) == before


def test_huge_integer_is_damaged_when_interpreter_limit_disabled(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    install_self_consistent_schema(
        snapshot_dir,
        self_consistent_huge_integer_schema(),
    )
    before = filesystem_fingerprint(root)
    previous_limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(0)
    try:
        with pytest.raises(ContractCheckError) as captured:
            check_frozen_contract("boundary", "v1", root)
    finally:
        sys.set_int_max_str_digits(previous_limit)

    assert captured.value.category is ContractCheckErrorCategory.DAMAGED_SNAPSHOT
    assert filesystem_fingerprint(root) == before


@pytest.mark.parametrize(
    ("digits", "expected_category"),
    [
        (100, ContractCheckErrorCategory.CONTENT_DRIFT),
        (101, ContractCheckErrorCategory.DAMAGED_SNAPSHOT),
    ],
)
def test_integer_digit_cap_is_fixed_and_documented(
    tmp_path: Path,
    digits: int,
    expected_category: ContractCheckErrorCategory,
) -> None:
    root = tmp_path / "contracts"
    snapshot_dir = _create_snapshot(root)
    install_self_consistent_schema(
        snapshot_dir,
        canonical_json_bytes(
            {
                "x": int("1" * digits),
                "x-paper-radar-contract": {"name": "boundary", "version": "v1"},
            }
        ),
    )

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is expected_category


@pytest.mark.parametrize("restricted", ["root", "screening"])
def test_directory_permission_denied_is_reported_as_unreadable(
    tmp_path: Path,
    restricted: str,
) -> None:
    root = tmp_path / "contracts"
    _create_snapshot(root)
    restricted_dir = root if restricted == "root" else root / "screening"
    before = filesystem_fingerprint(root)
    original_mode = stat.S_IMODE(restricted_dir.stat().st_mode)
    restricted_dir.chmod(0o000)
    try:
        with pytest.raises(ContractCheckError) as captured:
            check_frozen_contract("boundary", "v1", root)

        assert captured.value.category is ContractCheckErrorCategory.UNREADABLE_SNAPSHOT
        assert "权限" in str(captured.value)
    finally:
        restricted_dir.chmod(original_mode)
    assert filesystem_fingerprint(root) == before


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


def test_intermediate_symlink_loop_is_invalid_target_not_missing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    (root / "screening").symlink_to(root / "screening", target_is_directory=True)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_TARGET
    assert "无法解析" in str(captured.value)
    assert (root / "screening").is_symlink()


def test_intermediate_non_directory_component_is_invalid_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    (root / "screening").write_text("occupied", encoding="utf-8")
    before = filesystem_fingerprint(root)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_TARGET
    assert "无法解析" in str(captured.value)
    assert filesystem_fingerprint(root) == before


def test_unresolvable_target_symlink_loop_is_invalid_target(tmp_path: Path) -> None:
    root = tmp_path / "loop"
    root.symlink_to(root, target_is_directory=True)

    with pytest.raises(ContractCheckError) as captured:
        check_frozen_contract("boundary", "v1", root)

    assert captured.value.category is ContractCheckErrorCategory.INVALID_TARGET
    assert root.is_symlink()
