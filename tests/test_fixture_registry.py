"""通过公共登记接口验证不可变样本声明与独立读取。"""

import json
from pathlib import Path

import pytest

from paper_radar.fixture_audit import FixtureAudit, FixtureError, FixtureReason
from paper_radar.storage.database import upgrade_database
from tests.fixture_registry_support import declaration_bytes


def test_register_retains_exact_bytes_after_source_is_deleted(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database, tmp_path / "data")
    source = tmp_path / "history.json"
    raw = declaration_bytes()
    source.write_bytes(raw)
    registered = registry.register(source)
    assert len(registered.entries) == 1
    assert registered.entries[0].entry.key == "aies-reference-one"
    assert registered.entries[0].entry.expectations.publisher_count == 77
    assert registry.register(source) == registered
    source.unlink()
    assert registry.read_declaration(registered.declaration_id) == raw
    assert registry.show(registered.entries[0].record_id) == registered.entries[0]
    assert registry.list() == registered.entries


def test_historical_seed_has_six_reference_counts_and_four_pdf_requirements(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database)
    seed = Path(__file__).parents[1] / "fixtures/a10/historical-v1.json"
    result = registry.register(seed)
    references = [
        record.entry
        for record in result.entries
        if record.entry.purpose == "references"
    ]
    assert [
        (item.doi, item.expectations.publisher_count, item.expectations.registry_count)
        for item in references
    ] == [
        ("10.1175/AIES-D-25-0111.1", 77, 0),
        ("10.1175/AIES-D-25-0103.1", 20, 20),
        ("10.1002/qj.70299", 57, 57),
        ("10.1002/qj.70303", 66, 66),
        ("10.3878/j.issn.1006-9895.2604.26034", 78, None),
        ("10.3878/j.issn.1006-9895.2512.24134", 32, None),
    ]
    pdfs = [record.entry for record in result.entries if record.entry.purpose == "pdf"]
    assert {item.journal for item in pdfs} == {"aies", "jgr", "qjrms", "dqkx"}
    jgr = next(item for item in pdfs if item.journal == "jgr")
    assert jgr.doi == "10.1029/2025JD043927"
    assert jgr.handle == "11094/103589"
    assert (
        "2–3 min 被合并为 23 min 的精确字符降级回归" in jgr.expectations.known_failures
    )
    assert all(
        item.basis == "historical_declaration"
        for item in (record.entry for record in result.entries)
    )


@pytest.mark.parametrize(
    ("original", "replacement", "reason"),
    [
        (
            b'"format_version": 1',
            b'"format_version": true',
            FixtureReason.INVALID_DECLARATION,
        ),
        (
            b'"format_version": 1',
            b'"format_version": 2',
            FixtureReason.UNSUPPORTED_FORMAT,
        ),
        (
            b'"format_version": 1',
            b'"format_version": 1, "format_version": 1',
            FixtureReason.INVALID_DECLARATION,
        ),
        (
            b'"declared_date": "2026-09-13"',
            b'"declared_date": "2026-02-30"',
            FixtureReason.INVALID_DECLARATION,
        ),
        (
            b'"publisher_count": 77',
            b'"publisher_count": true',
            FixtureReason.INVALID_DECLARATION,
        ),
        (
            b'"publisher_count": 77',
            b'"publisher_count": -1',
            FixtureReason.INVALID_DECLARATION,
        ),
        (
            b'"basis": "historical_declaration"',
            b'"basis": "acquired"',
            FixtureReason.EVIDENCE_REQUIRED,
        ),
        (
            b'"expectations": {',
            b'"SECRET_FIELD": "SENSITIVE_VALUE", "expectations": {',
            FixtureReason.INVALID_DECLARATION,
        ),
    ],
)
def test_invalid_declarations_are_safe_and_leave_no_records(
    tmp_path: Path,
    original: bytes,
    replacement: bytes,
    reason: FixtureReason,
) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database)
    source = tmp_path / "invalid.json"
    source.write_bytes(declaration_bytes().replace(original, replacement))
    with pytest.raises(FixtureError) as caught:
        registry.register(source)
    assert caught.value.reason == reason
    assert caught.value.path
    assert "SECRET_FIELD" not in str(caught.value)
    assert "SENSITIVE_VALUE" not in str(caught.value)
    assert registry.list(history=True) == ()


def test_exact_bytes_freeze_even_semantically_equivalent_whitespace(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database)
    source = tmp_path / "history.json"
    source.write_bytes(declaration_bytes())
    assert registry.check(source).status == "unregistered"
    original = registry.register(source)
    source.write_bytes(declaration_bytes() + b"\n")
    assert registry.check(source).status == "drift"
    with pytest.raises(FixtureError) as caught:
        registry.register(source)
    assert caught.value.reason == FixtureReason.DECLARATION_CONFLICT
    assert registry.read_declaration(original.declaration_id) == declaration_bytes()
    assert registry.list(history=True) == original.entries


def test_explicit_replacement_preserves_history_and_ignores_version_sorting(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database)
    source = tmp_path / "first.json"
    source.write_bytes(declaration_bytes(version="z9"))
    first = registry.register(source).entries[0]
    raw = json.loads(declaration_bytes(version="a1"))
    raw["entries"][0]["replaces"] = first.record_id
    raw["entries"][0]["replacement_reason"] = "修正历史注记"
    raw["entries"][0]["notes"] = ["更正材料，旧字节保留"]
    second_source = tmp_path / "renamed.json"
    second_source.write_text(json.dumps(raw, ensure_ascii=False))
    second = registry.register(second_source).entries[0]
    assert registry.list() == (second,)
    assert len(registry.list(history=True)) == 2
    assert registry.show(first.record_id).entry == first.entry
    assert registry.show(first.record_id).current is False
    assert registry.read_declaration(first.declaration_id) == declaration_bytes(
        version="z9"
    )
    assert registry.check(source).status == "byte_verified"
    assert registry.list() == (second,)


def test_dangling_and_cross_object_replacement_is_atomic(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database)
    source = tmp_path / "first.json"
    source.write_bytes(declaration_bytes())
    original = registry.register(source)
    raw = json.loads(declaration_bytes(version="v2"))
    raw["entries"][0]["key"] = "different-sample"
    raw["entries"][0]["replaces"] = original.entries[0].record_id
    raw["entries"][0]["replacement_reason"] = "不得跨样本替换"
    source.write_text(json.dumps(raw))
    with pytest.raises(FixtureError) as caught:
        registry.register(source)
    assert caught.value.reason == FixtureReason.INVALID_REFERENCE
    assert registry.list(history=True) == original.entries
    raw["entries"][0]["replaces"] = "0" * 64
    source.write_text(json.dumps(raw))
    with pytest.raises(FixtureError) as caught:
        registry.register(source)
    assert caught.value.reason == FixtureReason.INVALID_REFERENCE
    assert registry.list(history=True) == original.entries


def test_four_purposes_are_separate_and_file_location_does_not_change_identity(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database)
    entries = []
    for purpose in ("feed", "abstract_audit", "references", "pdf"):
        entries.append(
            {
                "key": "one-logical-key",
                "purpose": purpose,
                "journal": "jgr",
                "basis": "synthetic",
                "source_basis": "手写合成向量，不是真实来源",
            }
        )
    raw = json.dumps(
        {
            "format_version": 1,
            "declaration_key": "synthetic-four-purposes",
            "declared_version": "v1",
            "entries": entries,
        }
    ).encode()
    first = tmp_path / "one.json"
    first.write_bytes(raw)
    registered = registry.register(first)
    moved = tmp_path / "different-name.json"
    first.rename(moved)
    assert registry.register(moved) == registered
    assert {record.entry.purpose for record in registered.entries} == {
        "feed",
        "abstract_audit",
        "references",
        "pdf",
    }
    assert len({record.record_id for record in registered.entries}) == 4
