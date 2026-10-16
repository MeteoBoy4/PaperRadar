"""以重构前的固定字节结果验证公共入口, 不从新实现生成期望。"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    check_config,
    compile_config,
    load_config_snapshot,
)
from tests.config_projection_support import full_inputs

KINDS = ("profile", "models", "topics", "journals", "escalation", "extraction", "read")
SELECTIONS = (
    "all",
    "none",
    *(f"only-{k}" for k in KINDS),
    *(f"omit-{k}" for k in KINDS),
)
FAULTS = (
    "utf8",
    "syntax",
    "duplicate",
    "version",
    "type",
    "unknown",
    "null",
    "missing",
)
HISTORY_FAULTS = (*FAULTS, "compiled", "unselected")
GOLDEN = Path(__file__).parent / "fixtures/config_material_compatibility.json"


def prepare(root: Path, selection: str = "all") -> tuple[Path, Path]:
    settings, database = full_inputs(root)
    text = settings.read_text(encoding="utf-8")
    for kind in KINDS:
        if (
            selection == "none"
            or selection == f"omit-{kind}"
            or (selection.startswith("only-") and selection != f"only-{kind}")
        ):
            text = text.replace(f"{kind}: {kind}-v1\n", "")
    settings.write_text(text, encoding="utf-8")
    return settings, database


def source_path(settings: Path, kind: str) -> Path:
    folder = {"profile": "profiles", "escalation": "screening"}.get(kind, kind)
    return settings.parent / folder / f"{kind}-v1.yaml"


def damaged_bytes(raw: bytes, kind: str, fault: str) -> bytes:
    return {
        "utf8": b"\xff",
        "syntax": b"version: [\n",
        "duplicate": raw + f"version: {kind}-v1\n".encode(),
        "version": raw.replace(f"{kind}-v1".encode(), f"{kind}-v2".encode()),
        "type": raw.replace(f"version: {kind}-v1".encode(), b"version: 3"),
        "unknown": raw + b"private_extra: PRIVATE_MARKER\n",
        "null": b"null\n",
    }[fault]


def damage_history(database: Path, snapshot_id: str, kind: str, fault: str) -> str:
    """保持外层哈希自洽, 使测试真正走到历史材料验证。源文件保持合法。"""
    with sqlite3.connect(database) as connection:
        payload = json.loads(
            connection.execute(
                "SELECT payload_json FROM runtime_config_snapshots "
                "WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()[0]
        )
        entry = next(item for item in payload["materials"] if item["kind"] == kind)
        if fault == "missing":
            payload["materials"].remove(entry)
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind = ?", (kind,)
            )
        elif fault == "compiled":
            entry["config"] = {"private_extra": "PRIVATE_MARKER"}
        elif fault == "missing_config":
            del entry["config"]
        elif fault == "unselected":
            payload["selectors"].pop(kind)
        else:
            raw = connection.execute(
                "SELECT raw_content FROM config_versions WHERE kind = ?", (kind,)
            ).fetchone()[0]
            changed = damaged_bytes(raw, kind, fault)
            digest = hashlib.sha256(changed).hexdigest()
            entry["raw_sha256"] = digest
            connection.execute(
                "UPDATE config_versions SET raw_content = ?, raw_sha256 = ? "
                "WHERE kind = ?",
                (changed, digest, kind),
            )
            connection.execute(
                "UPDATE snapshot_version_refs SET raw_sha256 = ? WHERE kind = ?",
                (digest, kind),
            )
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        changed_id = hashlib.sha256(canonical.encode()).hexdigest()
        connection.execute(
            "UPDATE runtime_config_snapshots SET snapshot_id = ?, payload_json = ?",
            (changed_id, canonical),
        )
        connection.execute(
            "UPDATE snapshot_version_refs SET snapshot_id = ?", (changed_id,)
        )
    return changed_id


def error_message(root: Path, origin: str, kind: str, fault: str) -> str:
    settings, database = prepare(root)
    if origin == "history":
        snapshot = compile_config(settings, database)
        changed_id = damage_history(database, snapshot.snapshot_id, kind, fault)
        with pytest.raises(ConfigError) as error:
            load_config_snapshot(database, changed_id)
    else:
        path = source_path(settings, kind)
        if fault == "missing":
            path.unlink()
        else:
            path.write_bytes(damaged_bytes(path.read_bytes(), kind, fault))
        messages = []
        for operation in (check_config, compile_config):
            with pytest.raises(ConfigError) as error:
                operation(settings, database)
            messages.append(str(error.value))
        assert messages[0] == messages[1]
    message = str(error.value)
    assert "PRIVATE_MARKER" not in message
    return message


@pytest.mark.parametrize("selection", SELECTIONS)
def test_selected_materials_keep_pre_refactor_snapshot_bytes(
    tmp_path: Path, selection: str
) -> None:
    expected = json.loads(GOLDEN.read_bytes())["snapshots"][selection]
    settings, database = prepare(tmp_path, selection)
    checked = check_config(settings, database)
    saved = compile_config(settings, database)
    assert saved == checked
    assert saved.snapshot_id.encode() == expected.encode()
    assert hashlib.sha256(saved.payload_json.encode()).hexdigest() == expected
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    loaded = load_config_snapshot(database, saved.snapshot_id)
    assert loaded == saved
    assert loaded.payload_json.encode() == saved.payload_json.encode()


@pytest.mark.parametrize(
    ("origin", "kind", "fault"),
    [
        (origin, kind, fault)
        for origin, faults in (("current", FAULTS), ("history", HISTORY_FAULTS))
        for kind in KINDS
        for fault in faults
    ],
)
def test_material_errors_keep_pre_refactor_chinese_bytes(
    tmp_path: Path, origin: str, kind: str, fault: str
) -> None:
    expected = json.loads(GOLDEN.read_bytes())["errors"][f"{origin}/{kind}/{fault}"]
    assert error_message(tmp_path, origin, kind, fault).encode() == expected.encode()


@pytest.mark.parametrize("origin", ["current", "history"])
def test_multiple_errors_keep_existing_first_failure(
    tmp_path: Path, origin: str
) -> None:
    settings, database = prepare(tmp_path)
    if origin == "current":
        # 当前装载先验证 journals, 随后才读取 escalation。
        source_path(settings, "journals").write_bytes(b"\xff")
        source_path(settings, "escalation").unlink()
        with pytest.raises(ConfigError) as error:
            check_config(settings, database)
        expected = "journals：必须是 UTF-8 文本"
    else:
        # 历史按已保存条目顺序验证, escalation 在 journals 之前。
        saved = compile_config(settings, database)
        changed_id = damage_history(database, saved.snapshot_id, "journals", "utf8")
        changed_id = damage_history(database, changed_id, "escalation", "utf8")
        with pytest.raises(ConfigError) as error:
            load_config_snapshot(database, changed_id)
        expected = "escalation：必须是 UTF-8 文本"
    assert str(error.value).encode() == expected.encode()


@pytest.mark.parametrize("kind", (*KINDS, "adapter"))
def test_historical_decode_error_precedes_missing_compiled_field(
    tmp_path: Path, kind: str
) -> None:
    settings, database = prepare(tmp_path)
    saved = compile_config(settings, database)
    changed_id = damage_history(database, saved.snapshot_id, kind, "missing_config")
    changed_id = damage_history(database, changed_id, kind, "utf8")
    with pytest.raises(ConfigError) as error:
        load_config_snapshot(database, changed_id)
    assert str(error.value).encode() == f"{kind}：必须是 UTF-8 文本".encode()
