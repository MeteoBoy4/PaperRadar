"""Pi 配置固定合成材料。不需要 Pi、Node 或模型凭据。"""

from pathlib import Path

from tests.config_test_support import value_inputs

SYSTEM_PROMPT = b"Frozen effective Pi system prompt\n"
SYSTEM_PROMPT_SHA256 = (
    "212c2cd595c12aaf7ca2a4b6783b3f43f85ce077745c2a55f4f18d6c07b9e2d1"
)


def adapter_inputs(root: Path) -> tuple[Path, Path, Path]:
    settings, db = value_inputs(root)
    models = settings.parent / "models/models-v1.yaml"
    models.write_text(models.read_text().replace("json_schema", "prompt_only"))
    (settings.parent / "adapters").mkdir()
    (settings.parent / "prompts").mkdir()
    (settings.parent / "prompts/pi-system-v1.md").write_bytes(SYSTEM_PROMPT)
    path = settings.parent / "adapters/pi-v1.yaml"
    path.write_text(
        "version: pi-v1\npi_version: 1.1.0\nadapter_version: transport-v1\n"
        "thinking_level: low\nresources:\n"
        f"  - version: v1\n    sha256: {SYSTEM_PROMPT_SHA256}\n"
    )
    settings.write_text(
        settings.read_text() + "adapters:\n  screening: pi-v1\n"
        "  reuse_assessment: pi-v1\n  reading: pi-v1\n"
    )
    return settings, path, db
