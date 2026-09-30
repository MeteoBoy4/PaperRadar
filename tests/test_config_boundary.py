"""A2-02 研究边界配置服务回归。"""

from __future__ import annotations

import os
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
)
from paper_radar.config.compile import MissingReason, StageName
from tests.config_test_support import boundary_inputs


def test_ready_snapshot_keeps_all_materials_after_files_removed(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    checked = check_config(settings, db)
    assert checked.stages[StageName.BOUNDARY].status == "ready"
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)
    saved = compile_config(settings, db)
    assert saved == checked
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (5,)
    for path in (tmp_path / "config").rglob("*.yaml"):
        path.unlink()
    for path in (tmp_path / "prompts").rglob("*.md"):
        path.unlink()
    for path in (tmp_path / "contracts").rglob("*.json"):
        path.unlink()
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_placeholder_model_is_not_ready_with_specific_reason(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path, model="REQUIRED")
    result = compile_config(settings, db)
    assert result.model_slots["screening"] == "placeholder"
    assert result.stages[StageName.BOUNDARY].missing == (
        MissingReason.SCREENING_MODEL_PLACEHOLDER,
    )


def test_contract_damage_rolls_back_all_new_materials(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    manifest = tmp_path / "contracts/screening/boundary/v1/manifest.json"
    manifest.write_bytes(b"{}")
    with pytest.raises(ConfigError, match=r"contracts\.boundary"):
        compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    ("damage", "category"),
    [("missing", "missing_snapshot"), ("damaged", "damaged_snapshot")],
)
def test_contract_check_reports_specific_failure_without_writing(
    tmp_path: Path, damage: str, category: str
) -> None:
    settings, db = boundary_inputs(tmp_path)
    folder = tmp_path / "contracts/screening/boundary/v1"
    if damage == "missing":
        (folder / "schema.json").unlink()
    else:
        (folder / "manifest.json").write_bytes(b"{}")
    with pytest.raises(ConfigError, match=category) as error:
        check_config(settings, db)
    assert "contracts.boundary" in str(error.value)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


def test_new_prompt_version_can_reuse_same_bytes(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    first = compile_config(settings, db)
    prompt = tmp_path / "prompts/screening/boundary-v1.md"
    (prompt.parent / "boundary-v2.md").write_bytes(prompt.read_bytes())
    settings.write_text(
        settings.read_text().replace(
            "boundary: v1\ncontracts", "boundary: v2\ncontracts"
        ),
        encoding="utf-8",
    )
    second = compile_config(settings, db)
    assert second.snapshot_id != first.snapshot_id
    assert load_config_snapshot(db, first.snapshot_id) == first
    prompt.write_bytes(b"Changed\n")
    settings.write_text(
        settings.read_text().replace(
            "boundary: v2\ncontracts", "boundary: v1\ncontracts"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
        check_config(settings, db)


def test_active_contract_damage_is_rejected_after_registration(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    saved = compile_config(settings, db)
    schema = tmp_path / "contracts/screening/boundary/v1/schema.json"
    schema.write_bytes(schema.read_bytes() + b" ")
    with pytest.raises(ConfigError, match=r"contracts\.boundary"):
        check_config(settings, db)
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_new_model_version_keeps_old_bytes_and_new_selection(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    first = compile_config(settings, db)
    old = tmp_path / "config/models/models-v1.yaml"
    newer = old.parent / "models-v2.yaml"
    newer.write_text(
        old.read_text().replace("models-v1", "models-v2"), encoding="utf-8"
    )
    settings.write_text(
        settings.read_text().replace("models: models-v1", "models: models-v2"),
        encoding="utf-8",
    )
    second = compile_config(settings, db)
    assert second.snapshot_id != first.snapshot_id
    assert load_config_snapshot(db, first.snapshot_id) == first
    old.write_bytes(old.read_bytes() + b"# drift\n")
    settings.write_text(
        settings.read_text().replace("models: models-v2", "models: models-v1"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
        compile_config(settings, db)


def test_selected_unsupported_contract_is_rejected(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    settings.write_text(
        settings.read_text().replace("boundary: v1\n", "boundary: v2\n"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match=r"prompts\.boundary"):
        check_config(settings, db)
    settings.write_text(
        "profile: profile-v1\nmodels: models-v1\ncontracts:\n  boundary: v2\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match=r"contracts\.boundary"):
        check_config(settings, db)


def test_multi_material_transaction_rollback(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TRIGGER fail_snapshot BEFORE INSERT ON runtime_config_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
    with pytest.raises(ConfigError, match="已回滚"):
        compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


def test_model_slots_are_independent_even_with_same_provider_model(
    tmp_path: Path,
) -> None:
    settings, db = boundary_inputs(tmp_path)
    models = tmp_path / "config/models/models-v1.yaml"
    models.write_text(
        models.read_text()
        .replace(
            "reuse_assessment: null",
            "reuse_assessment:\n  provider: provider-a\n"
            "  model: real-model\n  protocol: json_schema",
        )
        .replace(
            "reading: null",
            "reading:\n  provider: provider-a\n"
            "  model: real-model\n  protocol: json_schema",
        ),
        encoding="utf-8",
    )
    result = compile_config(settings, db)
    assert result.model_slots == {
        "screening": "configured",
        "reuse_assessment": "configured",
        "reading": "configured",
    }
    assert result.stages[StageName.REUSE].status == "not_ready"
    assert result.stages[StageName.READ].status == "not_ready"
    assert result.stages[StageName.BOUNDARY].status == "ready"


@pytest.mark.parametrize(
    ("replacement", "field"),
    [
        ("protocol: unknown", "models.screening.protocol"),
        ("temperature: 3.0", "models.screening.temperature"),
        ("api_key: secret-marker", "models.screening.api_key"),
    ],
)
def test_invalid_model_contract_is_rejected_without_leak(
    tmp_path: Path, replacement: str, field: str
) -> None:
    settings, db = boundary_inputs(tmp_path)
    path = tmp_path / "config/models/models-v1.yaml"
    if replacement.startswith("protocol"):
        path.write_text(
            path.read_text().replace("protocol: json_schema", replacement),
            encoding="utf-8",
        )
    else:
        path.write_text(
            path.read_text().replace(
                "  protocol: json_schema", "  protocol: json_schema\n  " + replacement
            ),
            encoding="utf-8",
        )
    with pytest.raises(ConfigError) as error:
        compile_config(settings, db)
    assert field in str(error.value)
    assert "secret-marker" not in str(error.value)


def test_missing_and_placeholder_inputs_are_reported_together(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path, model="REQUIRED")
    settings.write_text(
        "models: models-v1\nprompts:\n  boundary: v1\n", encoding="utf-8"
    )
    result = check_config(settings, db)
    assert result.stages[StageName.BOUNDARY].missing == (
        MissingReason.PROFILE,
        MissingReason.SCREENING_MODEL_PLACEHOLDER,
        MissingReason.BOUNDARY_CONTRACT,
    )


def test_installed_cli_ready_and_help_has_no_io(tmp_path: Path) -> None:
    settings, db = boundary_inputs(tmp_path)
    executable = str(Path(sys.executable).with_name("paper-radar"))
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    checked = subprocess.run(
        [
            executable,
            "config",
            "check",
            "--settings",
            str(settings),
            "--database",
            str(db),
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr
    assert "boundary：ready" in checked.stdout
    assert "models.screening：configured" in checked.stdout

    def cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                executable,
                "config",
                *args,
                "--settings",
                str(settings),
                "--database",
                str(db),
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    assert cli("compile").returncode == 0
    manifest = tmp_path / "contracts/screening/boundary/v1/manifest.json"
    original = manifest.read_bytes()
    manifest.write_bytes(b"{}")
    damaged = cli("compile")
    assert damaged.returncode == 2
    assert "contracts.boundary" in damaged.stderr
    assert "damaged_snapshot" in damaged.stderr
    manifest.write_bytes(original)

    prompt = tmp_path / "prompts/screening/boundary-v1.md"
    (prompt.parent / "boundary-v2.md").write_bytes(prompt.read_bytes())
    settings.write_text(
        settings.read_text().replace(
            "boundary: v1\ncontracts", "boundary: v2\ncontracts"
        ),
        encoding="utf-8",
    )
    assert cli("compile").returncode == 0

    models = tmp_path / "config/models/models-v1.yaml"
    (models.parent / "models-v2.yaml").write_text(
        models.read_text()
        .replace("models-v1", "models-v2")
        .replace("real-model", "REQUIRED"),
        encoding="utf-8",
    )
    settings.write_text(
        settings.read_text().replace("models: models-v1", "models: models-v2"),
        encoding="utf-8",
    )
    placeholder = cli("check")
    assert placeholder.returncode == 0
    assert "models.screening：placeholder" in placeholder.stdout
    assert "boundary：not_ready" in placeholder.stdout
    help_env = dict(env, PYTHONPATH=str(Path(__file__).parent / "deny_external_io"))
    help_result = subprocess.run(
        [executable, "config", "check", "--help"],
        cwd=tmp_path,
        env=help_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "示例" in help_result.stdout
