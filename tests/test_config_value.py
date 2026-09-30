"""A2-03 主题与价值预测的公共配置服务回归。"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    check_config,
    compile_config,
    load_config_snapshot,
    upgrade_database,
)
from paper_radar.config.compile import MissingReason, StageName
from tests.test_config_boundary import _inputs


def _value_inputs(root: Path, topics: str = "[]") -> tuple[Path, Path]:
    settings, db = _inputs(root)
    (root / "config/topics").mkdir()
    (root / "config/topics/topics-v1.yaml").write_text(
        f"version: topics-v1\ntopics: {topics}\n", encoding="utf-8"
    )
    (root / "prompts/screening/value-v1.md").write_bytes(b"Value prompt\n")
    source = (
        Path(__file__).resolve().parents[1] / "contracts/screening/value-prediction"
    )
    shutil.copytree(source, root / "contracts/screening/value-prediction")
    settings.write_text(
        "profile: profile-v1\nmodels: models-v1\ntopics: topics-v1\n"
        "prompts:\n  boundary: v1\n  value: v1\n"
        "contracts:\n  boundary: v1\n  value_prediction: v1\n",
        encoding="utf-8",
    )
    return settings, db


@pytest.mark.parametrize(
    "topics",
    [
        "[]",
        "[{id: monsoon, name: 季风, description: 季风机制, enabled: false}]",
        "[{id: monsoon, name: 季风, description: 季风机制, enabled: true}]",
    ],
)
def test_configured_topics_make_value_ready_and_replay_without_source_files(
    tmp_path: Path, topics: str
) -> None:
    settings, db = _value_inputs(tmp_path, topics)
    checked = check_config(settings, db)
    assert checked.stages[StageName.VALUE].status == "ready"
    assert checked.stages[StageName.BOUNDARY].status == "ready"
    assert checked.topics_status == "configured"
    expected = [("monsoon", "季风", "季风机制")] if "true" in topics else []
    assert [(t.id, t.name, t.description) for t in checked.enabled_topics] == expected
    saved = compile_config(settings, db)
    assert saved == checked
    assert compile_config(settings, db) == saved
    payload = json.loads(saved.payload_json)
    material = next(m for m in payload["materials"] if m["kind"] == "topics")
    assert material["version"] == "topics-v1"
    expected_full = (
        []
        if topics == "[]"
        else [
            {
                "id": "monsoon",
                "name": "季风",
                "description": "季风机制",
                "enabled": "true" in topics,
            }
        ]
    )
    assert material["config"]["topics"] == expected_full
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_empty_and_disabled_sets_keep_distinct_history_and_same_enabled_semantics(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    empty = compile_config(settings, db)
    (tmp_path / "config/topics/topics-v2.yaml").write_text(
        "version: topics-v2\ntopics:\n"
        "  - {id: monsoon, name: 季风, description: 季风机制, enabled: false}\n",
        encoding="utf-8",
    )
    settings.write_text(settings.read_text().replace("topics-v1", "topics-v2"))
    disabled = compile_config(settings, db)
    assert empty.snapshot_id != disabled.snapshot_id
    assert empty.enabled_topics == disabled.enabled_topics == ()
    assert empty.topics_status == disabled.topics_status == "configured"
    assert empty.stages[StageName.VALUE] == disabled.stages[StageName.VALUE]
    assert load_config_snapshot(db, empty.snapshot_id) == empty


@pytest.mark.parametrize("selector", ["", "topics: null\n"])
def test_unselected_topics_are_missing_even_when_file_exists(
    tmp_path: Path, selector: str
) -> None:
    settings, db = _value_inputs(tmp_path)
    settings.write_text(settings.read_text().replace("topics: topics-v1\n", selector))
    saved = compile_config(settings, db)
    assert saved.topics_status == "unconfigured"
    assert saved.enabled_topics == ()
    assert saved.stages[StageName.VALUE].missing == (MissingReason.TOPICS,)
    assert saved.stages[StageName.BOUNDARY].status == "ready"
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_value_does_not_require_boundary_materials(tmp_path: Path) -> None:
    settings, db = _value_inputs(tmp_path)
    settings.write_text(settings.read_text().replace("  boundary: v1\n", ""))
    result = check_config(settings, db)
    assert result.stages[StageName.VALUE].status == "ready"
    assert result.stages[StageName.BOUNDARY].missing == (
        MissingReason.BOUNDARY_PROMPT,
        MissingReason.BOUNDARY_CONTRACT,
    )


@pytest.mark.parametrize(
    ("replacement", "expected"),
    [
        ("profile: null", MissingReason.PROFILE),
        ("models: null", MissingReason.SCREENING_MODEL),
        ("  value: null", MissingReason.VALUE_PROMPT),
        ("  value_prediction: null", MissingReason.VALUE_CONTRACT),
    ],
)
def test_value_reports_each_required_configuration_slot(
    tmp_path: Path, replacement: str, expected: MissingReason
) -> None:
    settings, db = _value_inputs(tmp_path)
    original = replacement.replace(
        "null",
        {
            MissingReason.PROFILE: "profile-v1",
            MissingReason.SCREENING_MODEL: "models-v1",
            MissingReason.VALUE_PROMPT: "v1",
            MissingReason.VALUE_CONTRACT: "v1",
        }[expected],
    )
    settings.write_text(settings.read_text().replace(original, replacement))
    saved = compile_config(settings, db)
    assert saved.stages[StageName.VALUE].missing == (expected,)
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize("text", [b"", b" \n", b" ... \n"])
def test_value_prompt_placeholder_has_specific_reason(
    tmp_path: Path, text: bytes
) -> None:
    settings, db = _value_inputs(tmp_path)
    (tmp_path / "prompts/screening/value-v1.md").write_bytes(text)
    saved = compile_config(settings, db)
    assert saved.stages[StageName.VALUE].missing == (
        MissingReason.VALUE_PROMPT_PLACEHOLDER,
    )
    assert saved.stages[StageName.BOUNDARY].status == "ready"
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize(
    "topic",
    [
        "{id: Monsoon, name: N, description: D, enabled: true}",
        "{id: ' monsoon ', name: N, description: D, enabled: true}",
        "{id: a_b, name: N, description: D, enabled: true}",
        "{id: 1topic, name: N, description: D, enabled: true}",
        "{id: '../outside', name: N, description: D, enabled: true}",
        "{id: '', name: N, description: D, enabled: true}",
        "{id: '" + "a" * 65 + "', name: N, description: D, enabled: true}",
        "{id: 123, name: N, description: D, enabled: true}",
        "{id: monsoon, description: D, enabled: true}",
        "{id: monsoon, name: '  ', description: D, enabled: true}",
        "{id: monsoon, name: N, description: '', enabled: true}",
        "{id: monsoon, name: N, description: null, enabled: true}",
        "{id: monsoon, name: N, description: D}",
        "{id: monsoon, name: N, description: D, enabled: yes}",
        "{id: monsoon, name: N, description: D, enabled: on}",
        "{id: monsoon, name: N, description: D, enabled: True}",
        "{id: monsoon, name: N, description: D, enabled: !!bool yes}",
        "{id: monsoon, name: N, description: D, enabled: !!bool on}",
        "{id: monsoon, name: N, description: D, enabled: !!bool True}",
        "{id: monsoon, name: N, description: D, enabled: 'false'}",
        "{id: monsoon, name: N, description: D, enabled: 1}",
        "{id: monsoon, name: N, description: D, enabled: null}",
        "{id: monsoon, name: N, description: D, enabled: true, weight: 1}",
        "{id: monsoon, name: N, description: D, enabled: true, api_key: secret-marker}",
    ],
)
def test_invalid_topic_fields_fail_without_registry_writes_or_value_leak(
    tmp_path: Path, topic: str
) -> None:
    settings, db = _value_inputs(tmp_path, f"[{topic}]")
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError) as error:
            operation(settings, db)
        if "!!bool" in topic:
            assert "布尔值仅允许小写 true/false" in str(error.value)
        else:
            assert "topics.topics.0." in str(error.value)
        assert "secret-marker" not in str(error.value)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    "content",
    [
        "version: topics-v1\ntopics: null\n",
        "version: topics-v1\n",
        "topics: []\n",
        "version: topics-v2\ntopics: []\n",
        "version: topics-v1\ntopics: []\nunknown: secret-marker\n",
        "version: topics-v1\ntopics:\n"
        "  - {id: a, name: N, description: D, enabled: true}\n"
        "  - {id: a, name: N2, description: D2, enabled: false}\n",
        "version: topics-v1\ntopics: []\ntopics: []\n",
    ],
)
def test_invalid_topic_collection_is_rejected(tmp_path: Path, content: str) -> None:
    settings, db = _value_inputs(tmp_path)
    (tmp_path / "config/topics/topics-v1.yaml").write_text(content)
    with pytest.raises(ConfigError) as error:
        compile_config(settings, db)
    assert "secret-marker" not in str(error.value)


def test_topics_are_sorted_and_text_has_no_placeholder_detection(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(
        tmp_path,
        "[{id: z, name: ' ... ', description: ' D ', enabled: true},"
        "{id: a, name: A, description: …, enabled: true}]",
    )
    saved = compile_config(settings, db)
    assert [(t.id, t.name, t.description) for t in saved.enabled_topics] == [
        ("a", "A", "…"),
        ("z", " ... ", " D "),
    ]
    payload = json.loads(saved.payload_json)
    topics = next(m for m in payload["materials"] if m["kind"] == "topics")
    assert [t["id"] for t in topics["config"]["topics"]] == ["a", "z"]


@pytest.mark.parametrize("version", ["Topics-v1", " topics-v1", "../outside"])
def test_topic_selector_is_a_controlled_version(tmp_path: Path, version: str) -> None:
    settings, db = _value_inputs(tmp_path)
    settings.write_text(
        settings.read_text().replace("topics: topics-v1", f"topics: '{version}'")
    )
    with pytest.raises(ConfigError, match=r"settings\.topics"):
        compile_config(settings, db)


@pytest.mark.parametrize("material", ["topics", "prompt"])
def test_registered_topics_and_value_prompt_require_new_versions(
    tmp_path: Path, material: str
) -> None:
    settings, db = _value_inputs(tmp_path)
    saved = compile_config(settings, db)
    path = tmp_path / (
        "config/topics/topics-v1.yaml"
        if material == "topics"
        else "prompts/screening/value-v1.md"
    )
    original = path.read_bytes()
    path.write_bytes(original + b"\n")
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
            operation(settings, db)
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    if material == "topics":
        (path.parent / "topics-v2.yaml").write_bytes(
            path.read_bytes().replace(b"topics-v1", b"topics-v2")
        )
        settings.write_text(
            settings.read_text().replace("topics: topics-v1", "topics: topics-v2")
        )
    else:
        (path.parent / "value-v2.md").write_bytes(path.read_bytes())
        settings.write_text(settings.read_text().replace("  value: v1", "  value: v2"))
    newer = compile_config(settings, db)
    assert newer.snapshot_id != saved.snapshot_id
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    assert load_config_snapshot(db, newer.snapshot_id) == newer


def test_value_material_registration_rolls_back_after_snapshot_write_failure(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TRIGGER fail_snapshot BEFORE INSERT ON runtime_config_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'secret-marker'); END"
        )
    with pytest.raises(ConfigError, match="已回滚") as error:
        compile_config(settings, db)
    assert "secret-marker" not in str(error.value)
    with sqlite3.connect(db) as connection:
        for table in (
            "config_versions",
            "runtime_config_snapshots",
            "snapshot_version_refs",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                0,
            )
        connection.execute("DROP TRIGGER fail_snapshot")
    saved = compile_config(settings, db)
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize("damage", ["missing", "manifest", "schema", "unsupported"])
def test_value_contract_failure_writes_no_partial_materials(
    tmp_path: Path, damage: str
) -> None:
    settings, db = _value_inputs(tmp_path)
    before = {
        p: p.read_bytes()
        for folder in ("config", "prompts", "contracts")
        for p in (tmp_path / folder).rglob("*")
        if p.is_file()
    }
    folder = tmp_path / "contracts/screening/value-prediction/v1"
    if damage == "missing":
        (folder / "schema.json").unlink()
    elif damage == "unsupported":
        settings.write_text(
            settings.read_text().replace("value_prediction: v1", "value_prediction: v2")
        )
    else:
        (folder / f"{damage}.json").write_bytes(b"{}")
    active = {p: p.read_bytes() for p in before if p.exists()}
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=r"contracts\.value_prediction"):
            operation(settings, db)
    assert {p: p.read_bytes() for p in active} == active
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


def test_new_process_load_keeps_value_materials_without_original_files(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    saved = compile_config(settings, db)
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; "
            "from paper_radar.config import load_config_snapshot; "
            "import sys; s=load_config_snapshot(Path(sys.argv[1]),sys.argv[2]); "
            "print(s.snapshot_id,s.stages['value'].status,s.topics_status)",
            str(db),
            saved.snapshot_id,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{saved.snapshot_id} ready configured"


def test_changed_disabled_topic_keeps_enabled_semantics_and_boundary_readiness(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(
        tmp_path,
        "[{id: active, name: A, description: D, enabled: true},"
        "{id: disabled, name: X, description: Old, enabled: false}]",
    )
    first = compile_config(settings, db)
    old = tmp_path / "config/topics/topics-v1.yaml"
    (old.parent / "topics-v2.yaml").write_text(
        old.read_text().replace("topics-v1", "topics-v2").replace("Old", "New")
    )
    settings.write_text(settings.read_text().replace("topics-v1", "topics-v2"))
    second = compile_config(settings, db)
    assert second.snapshot_id != first.snapshot_id
    assert second.enabled_topics == first.enabled_topics
    assert second.stages[StageName.BOUNDARY] == first.stages[StageName.BOUNDARY]
    assert load_config_snapshot(db, first.snapshot_id) == first


def test_other_material_conflict_rolls_back_new_value_registration(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    full = settings.read_text()
    settings.write_text(
        full.replace("topics: topics-v1\n", "")
        .replace("  value: v1\n", "")
        .replace("  value_prediction: v1\n", "")
    )
    first = compile_config(settings, db)
    settings.write_text(full)
    prompt = tmp_path / "prompts/screening/boundary-v1.md"
    original = prompt.read_bytes()
    prompt.write_bytes(original + b"\n")
    with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
        compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (5,)
        assert connection.execute(
            "SELECT count(*) FROM runtime_config_snapshots"
        ).fetchone() == (1,)
    prompt.write_bytes(original)
    saved = compile_config(settings, db)
    assert saved.stages[StageName.VALUE].status == "ready"
    assert load_config_snapshot(db, first.snapshot_id) == first


def test_value_snapshot_is_independent_of_material_directory_and_does_not_write_inputs(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    before = {
        p: p.read_bytes()
        for folder in ("config", "prompts", "contracts")
        for p in (tmp_path / folder).rglob("*")
        if p.is_file()
    }
    first = compile_config(settings, db)
    assert {p: p.read_bytes() for p in before} == before
    moved = tmp_path / "moved"
    for folder in ("config", "prompts", "contracts"):
        shutil.copytree(tmp_path / folder, moved / folder)
    other_db = moved / "other.sqlite3"
    upgrade_database(other_db)
    second = compile_config(moved / "config/settings.yaml", other_db)
    assert second == first


def test_load_rejects_corrupt_registered_topics_without_using_source_file(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    saved = compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE config_versions SET raw_content = ? WHERE kind = 'topics'",
            (b"secret-marker",),
        )
    with pytest.raises(ConfigError, match="损坏") as error:
        load_config_snapshot(db, saved.snapshot_id)
    assert "secret-marker" not in str(error.value)


def test_topics_schema_remains_in_the_pure_config_layer() -> None:
    from tests.test_config_architecture import _imports

    module = Path(__file__).resolve().parents[1] / "src/paper_radar/config/topics.py"
    imports = _imports(module)
    assert not imports & {"yaml", "sqlite3", "sqlalchemy", "alembic", "typer"}
    assert not any(name.startswith("paper_radar.storage") for name in imports)


def test_synthetic_examples_show_ready_stages_and_missing_value_materials(
    tmp_path: Path,
) -> None:
    examples = Path(__file__).resolve().parents[1] / "examples/config"
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    value = compile_config(examples / "settings-value.yaml", db)
    assert value.stages[StageName.BOUNDARY].status == "ready"
    assert value.stages[StageName.VALUE].status == "ready"
    assert value.topics_status == "configured"
    boundary = compile_config(examples / "settings-boundary.yaml", db)
    assert boundary.stages[StageName.BOUNDARY].status == "ready"
    assert boundary.stages[StageName.VALUE].missing == (
        MissingReason.VALUE_PROMPT,
        MissingReason.VALUE_CONTRACT,
        MissingReason.TOPICS,
    )
    assert load_config_snapshot(db, value.snapshot_id) == value
