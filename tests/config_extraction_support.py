"""A2-05 合成模型声明。没有模型文件或 PDF。"""

from pathlib import Path

from paper_radar.config import upgrade_database

FORMULA_YAML = """  formula:
    commit_sha: 'ecedbe111d15c2dc60bfd4a823cbe80127b58af4'
    files:
""" + "".join(
    f"      - path: {name}\n        sha256: '{'f' * 64}'\n"
    for name in (
        "added_tokens.json",
        "chat_template.json",
        "config.json",
        "generation_config.json",
        "model.safetensors",
        "preprocessor_config.json",
        "processor_config.json",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
    )
)

EXTRACTION_YAML = (
    """version: extraction-v1
toolchain: docling-2.135.0-cpu-v1
normalization_version: v1
models:
  layout:
    commit_sha: '77ede7cc7bed96d853c58f319734803d6ea2ea5c'
    files:
      - path: config.json
        sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
      - path: model.safetensors
        sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
      - path: preprocessor_config.json
        sha256: 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
  table:
    commit_sha: 'fc0f2d45e2218ea24bce5045f58a389aed16dc23'
    files:
      - path: model_artifacts/tableformer/accurate/tableformer_accurate.safetensors
        sha256: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'
      - path: model_artifacts/tableformer/accurate/tm_config.json
        sha256: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
"""
    + FORMULA_YAML
)


def extraction_inputs(root: Path) -> tuple[Path, Path, Path]:
    folder = root / "config/extraction"
    folder.mkdir(parents=True)
    settings = root / "config/settings.yaml"
    settings.write_text("extraction: extraction-v1\n", encoding="utf-8")
    path = folder / "extraction-v1.yaml"
    path.write_text(EXTRACTION_YAML, encoding="utf-8")
    database = root / "db.sqlite3"
    upgrade_database(database)
    return settings, path, database
