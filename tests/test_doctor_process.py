"""doctor 冷进程只读、四态、选择与旧供给输出证据。"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.storage.database import upgrade_database
from tests.config_test_support import boundary_inputs


def invoke(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(Path(sys.executable).with_name("paper-radar")), "doctor", *args],
        cwd=root,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "doctor_guard"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "DOCTOR_HELP_ONLY": "1" if "--help" in args else "0",
            "DOCTOR_FORBIDDEN_INSTALL": str(root / "install"),
            "DOCTOR_FORBIDDEN_CREDENTIAL": str(root / "credential-sentinel"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def inventory(root: Path) -> tuple[tuple[str, bytes | None], ...]:
    return tuple(
        sorted(
            (str(path.relative_to(root)), path.read_bytes() if path.is_file() else None)
            for path in root.rglob("*")
            if not path.name.endswith(("-wal", "-shm", "-journal"))
        )
    )


def logical(database: Path) -> tuple[str, ...]:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        return tuple(connection.iterdump())


@pytest.mark.parametrize("selection", ["settings", "snapshot"])
def test_selected_config_is_readonly_and_discloses_only_selected_models(
    tmp_path: Path,
    selection: str,
) -> None:
    settings, database = boundary_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    (tmp_path / "install").mkdir()
    (tmp_path / "install/forbidden").write_text("INSTALL_SECRET")
    (tmp_path / "credential-sentinel").write_text("CREDENTIAL_SECRET")
    if selection == "snapshot":
        settings.unlink()  # 历史回放不依赖当前材料。
    before_tree, before_db = inventory(tmp_path), logical(database)
    chosen = str(settings) if selection == "settings" else snapshot.snapshot_id[:12]
    result = invoke(
        tmp_path,
        "--scope",
        "config",
        "--database",
        str(database),
        f"--{selection}",
        chosen,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "stage=boundary result=passed reason=configured" in result.stdout
    assert "stage=value result=missing reason=" in result.stdout
    assert 'provider="provider-a" model="real-model"' in result.stdout
    assert "category=feed Feed readiness result=not_assessed" in result.stdout
    assert "owner=Audit/Source" in result.stdout
    assert "doctor --scope pi-supply" in result.stdout
    assert "0 不代表任何阶段可运行。" in result.stdout
    assert inventory(tmp_path) == before_tree
    assert logical(database) == before_db


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--help",),
        ("--scope", "SECRET", "--database", "SECRET.db"),
        ("--scope", "all", "--database", "SECRET.db"),
        ("--scope", "basic", "--database", "SECRET.db", "--json"),
        ("--scope", "config", "--database", "SECRET.db"),
        (
            "--scope",
            "config",
            "--database",
            "SECRET.db",
            "--settings",
            "SECRET",
            "--snapshot",
            "SECRET",
        ),
        ("--scope", "pi-supply", "--database", "SECRET.db"),
        (
            "--scope",
            "pi-supply",
            "--database",
            "SECRET.db",
            "--settings",
            "SECRET",
            "--snapshot",
            "SECRET",
        ),
        ("--scope", "basic", "--database", "SECRET.db", "--settings", "SECRET"),
        ("--scope", "basic"),
        ("--SECRET", "SECRET"),
    ],
)
def test_help_and_usage_errors_have_no_io_or_sensitive_echo(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = invoke(tmp_path, *args)
    assert result.returncode == (0 if args == ("--help",) else 2)
    assert "SECRET" not in result.stdout + result.stderr
    if args in {(), ("--help",)}:
        assert "basic/config/pi-supply" in result.stdout + result.stderr
    assert inventory(tmp_path) == ()


@pytest.mark.parametrize(
    ("kind", "state", "reason"),
    [
        ("absent", "missing", "database_missing"),
        ("empty", "missing", "database_uninitialized"),
        ("old", "missing", "upgrade_required"),
        ("future", "invalid", "unknown_revision"),
        ("corrupt", "invalid", "database_unreadable"),
        ("revision_corrupt", "invalid", "database_revision_corrupt"),
    ],
)
def test_database_failures_are_controlled_and_readonly(
    tmp_path: Path, kind: str, state: str, reason: str
) -> None:
    database = tmp_path / "test.sqlite3"
    if kind == "empty":
        database.touch()
    elif kind == "corrupt":
        database.write_bytes(b"not a SQLite database SECRET")
    elif kind in {"old", "future", "revision_corrupt"}:
        upgrade_database(database)
        with sqlite3.connect(database) as connection:
            if kind == "revision_corrupt":
                connection.execute("DELETE FROM alembic_version")
            else:
                connection.execute(
                    "UPDATE alembic_version SET version_num=?",
                    ("a401_pi_supply" if kind == "old" else "future-SECRET",),
                )
    before = inventory(tmp_path)
    result = invoke(tmp_path, "--scope", "basic", "--database", str(database))
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"check=database result={state} reason={reason}" in result.stdout
    assert "SECRET" not in result.stdout + result.stderr
    assert inventory(tmp_path) == before


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("missing", "selected_file_unreadable"),
        ("directory", "selected_file_unreadable"),
        ("yaml", "content_invalid"),
        ("field", "content_invalid"),
        ("material_missing", "selected_file_unreadable"),
        ("conflict", "content_invalid"),
        ("contract_drift", "content_invalid"),
        ("snapshot_missing", "content_invalid"),
    ],
)
def test_invalid_selection_never_writes_or_falls_back(
    tmp_path: Path, kind: str, reason: str
) -> None:
    settings, database = boundary_inputs(tmp_path)
    compile_config(settings, database)
    if kind == "missing":
        settings.unlink()
    elif kind == "directory":
        settings.unlink()
        settings.mkdir()
    elif kind == "yaml":
        settings.write_text("profile: [SECRET")
    elif kind == "field":
        settings.write_text("profile: [SECRET]\n")
    elif kind == "material_missing":
        (settings.parent / "models/models-v1.yaml").unlink()
    elif kind == "conflict":
        profile = settings.parent / "profiles/profile-v1.yaml"
        profile.write_text(profile.read_text().replace("climate", "SECRET"))
    elif kind == "contract_drift":
        (tmp_path / "contracts/screening/boundary/v1/schema.json").write_text("{}")
    before_tree, before_db = inventory(tmp_path), logical(database)
    selection = (
        ("--snapshot", "f" * 64)
        if kind == "snapshot_missing"
        else ("--settings", str(settings))
    )
    result = invoke(
        tmp_path, "--scope", "config", "--database", str(database), *selection
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"check=selection result=invalid reason={reason}" in result.stdout
    assert "outbound_stage=" not in result.stdout
    assert "provider-a" not in result.stdout
    assert "SECRET" not in result.stdout + result.stderr
    assert inventory(tmp_path) == before_tree
    assert logical(database) == before_db


@pytest.mark.parametrize("activated", [False, True])
def test_valid_pi_supply_output_matches_frozen_baseline_bytes(
    tmp_path: Path, activated: bool
) -> None:
    import json

    from paper_radar.pi_supply import activate_supply
    from tests.config_test_support import run_cli
    from tests.pi_supply_support import inputs, prepare

    source = inputs(tmp_path)
    identities = {}
    if activated:
        prepared = prepare(tmp_path, source)
        current = activate_supply(source[0], prepared.supply_id, source[1])
        identities = {
            "<activation>": str(current.activation_id),
            "<supply>": current.supply_id,
            "<install>": current.install_id,
        }
    golden = json.loads(
        (Path(__file__).parent / "doctor_pi_supply_golden.json").read_text()
    )[int(activated)]
    expected = golden["stdout"]
    for placeholder, identity in identities.items():
        expected = expected.replace(placeholder, identity)
    result = run_cli(
        tmp_path,
        "doctor",
        "--scope",
        "pi-supply",
        "--database",
        str(source[0]),
        "--snapshot",
        source[1],
    )
    assert result.returncode == golden["exit_code"]
    assert result.stdout.encode("utf-8") == expected.encode("utf-8")
    assert result.stderr.encode("utf-8") == golden["stderr"].encode("utf-8")


def test_unreadable_database_is_invalid_and_never_creates_directories(
    tmp_path: Path,
) -> None:
    database = tmp_path / "SECRET.sqlite3"
    upgrade_database(database)
    before = database.read_bytes()
    database.chmod(0)
    try:
        result = invoke(tmp_path, "--scope", "basic", "--database", str(database))
    finally:
        database.chmod(0o600)
    assert result.returncode == 2
    assert "check=database result=invalid reason=database_unreadable" in result.stdout
    assert "SECRET" not in result.stdout + result.stderr
    assert database.read_bytes() == before
    assert not any(
        (tmp_path / name).exists() for name in ("data", "logs", "reports", "config")
    )


def test_unreadable_selected_settings_is_invalid(tmp_path: Path) -> None:
    settings, database = boundary_inputs(tmp_path)
    before = logical(database)
    settings.chmod(0)
    try:
        result = invoke(
            tmp_path,
            "--scope",
            "config",
            "--database",
            str(database),
            "--settings",
            str(settings),
        )
    finally:
        settings.chmod(0o600)
    assert result.returncode == 2
    assert (
        "check=selection result=invalid reason=selected_file_unreadable"
        in result.stdout
    )
    assert logical(database) == before
    assert not (tmp_path / "logs").exists()


def test_invalid_packaged_migration_is_controlled(tmp_path: Path) -> None:
    import shutil

    package_root = tmp_path / "package"
    source = Path(__file__).parents[1] / "src/paper_radar"
    shutil.copytree(
        source,
        package_root / "paper_radar",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    migration = package_root / "paper_radar/storage/migrations/versions/invalid.py"
    migration.write_text("this is invalid Python !!!\n")
    database = tmp_path / "test.sqlite3"
    upgrade_database(database)
    before = inventory(tmp_path)
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "doctor",
            "--scope",
            "basic",
            "--database",
            str(database),
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": os.pathsep.join(
                (str(Path(__file__).parent / "doctor_guard"), str(package_root))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert (
        "check=package result=invalid reason=package_migrations_invalid"
        in result.stdout
    )
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("model", ["REQUIRED", "real-model"])
def test_placeholder_or_unconfigured_slots_only_change_stage_readiness(
    tmp_path: Path, model: str
) -> None:
    settings, database = boundary_inputs(tmp_path, model=model)
    result = invoke(
        tmp_path,
        "--scope",
        "config",
        "--database",
        str(database),
        "--settings",
        str(settings),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    expected = "missing" if model == "REQUIRED" else "passed"
    assert f"stage=boundary result={expected}" in result.stdout
    assert "stage=reuse result=missing" in result.stdout
    assert "stage=read result=missing" in result.stdout
    assert "0 不代表任何阶段可运行。" in result.stdout
