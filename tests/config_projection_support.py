"""#23 合成材料与公开服务支撑。不新增生产算法或契约。"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from paper_radar.config import upgrade_database
from tests.config_adapter_support import SYSTEM_PROMPT, SYSTEM_PROMPT_SHA256
from tests.config_extraction_support import EXTRACTION_YAML
from tests.config_journals_support import JOURNALS
from tests.config_test_support import value_inputs


def full_inputs(root: Path) -> tuple[Path, Path]:
    settings, database = value_inputs(
        root,
        "\n  - id: active\n    name: 启用方向\n    description: storms\n"
        "    enabled: true\n  - id: inactive\n    name: 停用方向\n"
        "    description: old topic\n    enabled: false",
    )
    config = settings.parent
    (config / "models/models-v1.yaml").write_text(
        "version: models-v1\n"
        + "".join(
            f"{slot}:\n  provider: provider-a\n  model: shared-model\n"
            "  protocol: prompt_only\n"
            for slot in ("screening", "reuse_assessment", "reading")
        ),
        encoding="utf-8",
    )
    for folder in (
        "screening",
        "extraction",
        "journals",
        "read",
        "adapters",
        "prompts",
    ):
        (config / folder).mkdir()
    (config / "screening/escalation-v1.yaml").write_text(
        "version: escalation-v1\nreuse_escalation_research_values: [3]\n"
        "excerpt_priority: [availability, methods]\nexcerpt_selector_version: v1\n"
        "suggestion_rule_version: v1\n",
        encoding="utf-8",
    )
    (config / "extraction/extraction-v1.yaml").write_text(
        EXTRACTION_YAML, encoding="utf-8"
    )
    (config / "journals/journals-v1.yaml").write_text(JOURNALS, encoding="utf-8")
    (config / "read/read-v1.yaml").write_text(
        "version: read-v1\nchunking_version: v1\n", encoding="utf-8"
    )
    (config / "prompts/pi-system-v1.md").write_bytes(SYSTEM_PROMPT)
    (config / "adapters/pi-v1.yaml").write_text(
        "version: pi-v1\npi_version: 1.1.0\nadapter_version: transport-v1\n"
        "thinking_level: low\nresources:\n"
        f"  - version: v1\n    sha256: {SYSTEM_PROMPT_SHA256}\n",
        encoding="utf-8",
    )
    (root / "prompts/screening/reuse-v1.md").write_bytes(b"Reuse prompt\n")
    (root / "prompts/reading").mkdir()
    (root / "prompts/reading/v1.md").write_bytes(b"Read prompt\n")
    for name in ("reuse-assessment", "decision-reasons"):
        shutil.copytree(
            Path(__file__).resolve().parents[1] / "contracts/screening" / name,
            root / "contracts/screening" / name,
        )
    settings.write_text(
        "profile: profile-v1\nmodels: models-v1\ntopics: topics-v1\n"
        "journals: journals-v1\nescalation: escalation-v1\n"
        "extraction: extraction-v1\nread: read-v1\n"
        "prompts:\n  boundary: v1\n  value: v1\n  reuse: v1\n  reading: v1\n"
        "contracts:\n  boundary: v1\n  value_prediction: v1\n"
        "  reuse_assessment: v1\n  decision_reasons: v1\n"
        "adapters:\n  screening: pi-v1\n  reuse_assessment: pi-v1\n  reading: pi-v1\n",
        encoding="utf-8",
    )
    return settings, database


def new_yaml_version(
    settings: Path,
    category: str,
    mutate: Callable[[dict[str, Any]], None],
) -> Path:
    selectors = yaml.safe_load(settings.read_text(encoding="utf-8"))
    if category.startswith("adapters."):
        group, slot = category.split(".")
        old = selectors[group][slot]
        folder = group
    else:
        old = selectors[category]
        folder = {"profile": "profiles", "escalation": "screening"}.get(
            category, category
        )
    new = old.replace("v1", "v2")
    source = settings.parent / folder / f"{old}.yaml"
    content = yaml.safe_load(source.read_text(encoding="utf-8"))
    content["version"] = new
    mutate(content)
    target = source.with_name(f"{new}.yaml")
    target.write_text(yaml.safe_dump(content, allow_unicode=True), encoding="utf-8")
    if category.startswith("adapters."):
        selectors[group][slot] = new
    else:
        selectors[category] = new
    settings.write_text(yaml.safe_dump(selectors), encoding="utf-8")
    return target


def empty_inputs(root: Path) -> tuple[Path, Path]:
    settings = root / "config/settings.yaml"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}\n", encoding="utf-8")
    database = root / "db.sqlite3"
    upgrade_database(database)
    return settings, database
