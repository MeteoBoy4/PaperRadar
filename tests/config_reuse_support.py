"""A2-04 的固定合成材料。不要求 value、PDF 或正文解析。"""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.config_test_support import boundary_inputs


def reuse_inputs(root: Path) -> tuple[Path, Path]:
    settings, db = boundary_inputs(root)
    models = root / "config/models/models-v1.yaml"
    models.write_text(
        models.read_text().replace(
            "reuse_assessment: null",
            "reuse_assessment:\n  provider: provider-a\n"
            "  model: real-model\n  protocol: json_schema",
        )
    )
    (root / "config/screening").mkdir()
    (root / "config/screening/reuse-escalation-v1.yaml").write_text(
        "version: reuse-escalation-v1\n"
        "reuse_escalation_research_values: [3]\n"
        "excerpt_priority: [availability, methods]\n"
        "excerpt_selector_version: v1\n"
        "suggestion_rule_version: v1\n"
    )
    (root / "prompts/screening/reuse-v1.md").write_bytes(b"Reuse prompt\n")
    for name in ("reuse-assessment", "decision-reasons"):
        source = Path(__file__).resolve().parents[1] / "contracts/screening" / name
        shutil.copytree(source, root / "contracts/screening" / name)
    settings.write_text(
        "profile: profile-v1\nmodels: models-v1\n"
        "escalation: reuse-escalation-v1\n"
        "prompts:\n  boundary: v1\n  reuse: v1\n"
        "contracts:\n  boundary: v1\n  reuse_assessment: v1\n"
        "  decision_reasons: v1\n"
    )
    return settings, db
