"""Read 配置的固定合成材料。不提供 Read 输出契约或论文输入。"""

from pathlib import Path

from tests.config_test_support import boundary_inputs

READ_PROMPT = b"Synthetic Read business prompt\n"


def read_inputs(root: Path) -> tuple[Path, Path]:
    settings, db = boundary_inputs(root)
    (settings.parent / "read").mkdir()
    (settings.parent / "read/read-v1.yaml").write_text(
        "version: read-v1\nchunking_version: v1\n", encoding="utf-8"
    )
    (root / "prompts/reading").mkdir()
    (root / "prompts/reading/v1.md").write_bytes(READ_PROMPT)
    models = settings.parent / "models/models-v1.yaml"
    models.write_text(
        "version: models-v1\n"
        "screening:\n  provider: provider-a\n"
        "  model: real-model\n  protocol: json_schema\n"
        "reuse_assessment: null\n"
        "reading:\n  provider: provider-a\n"
        "  model: read-model\n  protocol: prompt_only\n",
        encoding="utf-8",
    )
    settings.write_text(
        "profile: profile-v1\nmodels: models-v1\n"
        "prompts:\n  boundary: v1\n  reading: v1\n"
        "contracts:\n  boundary: v1\n"
        "read: read-v1\n",
        encoding="utf-8",
    )
    return settings, db
