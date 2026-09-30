"""配置回归测试的材料工厂、真实 CLI 入口与导入检查支撑。"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

from paper_radar.config import upgrade_database


def boundary_inputs(root: Path, *, model: str = "real-model") -> tuple[Path, Path]:
    config = root / "config"
    (config / "profiles").mkdir(parents=True)
    (config / "models").mkdir()
    (root / "prompts/screening").mkdir(parents=True)
    (root / "contracts/screening/boundary/v1").mkdir(parents=True)
    for filename in ("schema.json", "manifest.json"):
        source = (
            Path(__file__).resolve().parents[1]
            / "contracts/screening/boundary/v1"
            / filename
        )
        (root / "contracts/screening/boundary/v1" / filename).write_bytes(
            source.read_bytes()
        )
    (config / "profiles/profile-v1.yaml").write_text(
        "version: profile-v1\n"
        "background: climate\ncore_questions: rain\ntransferable_methods: statistics\n"
        "available_data_and_tools: reanalysis\n"
        "theory_and_cognitive_interests: mechanisms\n"
        "constraints_and_exclusions: none\n",
        encoding="utf-8",
    )
    (config / "models/models-v1.yaml").write_text(
        "version: models-v1\n"
        "screening:\n  provider: provider-a\n"
        f"  model: {model}\n  protocol: json_schema\n"
        "reuse_assessment: null\nreading: null\n",
        encoding="utf-8",
    )
    (root / "prompts/screening/boundary-v1.md").write_bytes(b"Boundary prompt\n")
    settings = config / "settings.yaml"
    settings.write_text(
        "profile: profile-v1\nmodels: models-v1\n"
        "prompts:\n  boundary: v1\ncontracts:\n  boundary: v1\n",
        encoding="utf-8",
    )
    db = root / "db.sqlite3"
    upgrade_database(db)
    return settings, db


def value_inputs(root: Path, topics: str = "[]") -> tuple[Path, Path]:
    settings, db = boundary_inputs(root)
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


def run_cli(
    tmp_path: Path, *args: str, help_only: bool = False
) -> subprocess.CompletedProcess[str]:
    sentinel = "deny_external_io" if help_only else "deny_network"
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / sentinel),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [str(Path(sys.executable).with_name("paper-radar")), *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
