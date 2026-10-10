"""严格解析声明。缺项、禁止能力、文件身份与脱敏。"""

from pathlib import Path

import pytest

from paper_radar.config import ConfigError, check_config, compile_config
from tests.config_extraction_support import FORMULA_YAML, extraction_inputs


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("device", "gpu"),
        ("device", "auto"),
        ("paper_execution", "parallel"),
        ("do_ocr", "true"),
        ("do_table_structure", "false"),
        ("do_cell_matching", "false"),
        ("do_code_enrichment", "true"),
        ("do_picture_classification", "true"),
        ("do_picture_description", "true"),
        ("do_chart_extraction", "true"),
        ("enable_remote_services", "true"),
        ("allow_external_plugins", "true"),
        ("trust_remote_code", "true"),
        ("generate_page_images", "true"),
        ("generate_picture_images", "true"),
        ("generate_table_images", "true"),
        ("json_image_mode", "embedded"),
        ("markdown_image_mode", "embedded"),
        ("preserve_source_text", "false"),
        ("preserve_provenance", "false"),
        ("separate_formula_source", "false"),
        ("formula_pdf_crop_review", "false"),
        ("do_ocr", "0"),
        ("do_table_structure", "1"),
        ("do_formula_enrichment", "'true'"),
        ("do_ocr", "'false'"),
        ("heading_hierarchy", "false"),
        ("keep_empty_clusters", "true"),
        ("force_backend_text", "true"),
        ("use_reading_order_separators", "false"),
    ],
)
def test_v1_policy_rejects_forbidden_values_and_wrong_types(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    path.write_text(path.read_text() + f"policy:\n  {field}: {value}\n")
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=rf"extraction\.policy\.{field}"):
            operation(settings, db)


@pytest.mark.parametrize(
    "field",
    [
        "timeout",
        "memory_limit",
        "peak_memory",
        "threads",
        "batch_size",
        "queue_size",
        "model_directory",
        "password",
        "api_key",
        "token",
        "credential_ref",
        "secret",
        "backend_version",
        "docling_parse_version",
        "model_artifacts_hash",
        "excerpt_selector_version",
        "chunking_version",
        "options",
        "backends",
    ],
)
def test_unknown_resource_credential_and_duplicate_identity_fields_are_rejected(
    tmp_path: Path,
    field: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    path.write_text(path.read_text() + f"{field}: PRIVATE_MARKER\n")
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=rf"extraction\.{field}") as error:
            operation(settings, db)
        assert "PRIVATE_MARKER" not in str(error.value)


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ("version: extraction-v1\n", "", "version"),
        ("version: extraction-v1", "version: extraction-v2", "version"),
        ("toolchain: docling-2.135.0-cpu-v1\n", "", "toolchain"),
        ("docling-2.135.0-cpu-v1", "PRIVATE_MARKER", "toolchain"),
        (
            "normalization_version: v1",
            "normalization_version: v2",
            "normalization_version",
        ),
        ("normalization_version: v1\n", "", "normalization_version"),
        (
            "normalization_version: v1",
            "normalization_version: true",
            "normalization_version",
        ),
        ("models:\n", "models:\n  ocr: PRIVATE_MARKER\n", "models.ocr"),
        ("  layout:\n", "  layout:\n    engine: onnx\n", "models.layout.engine"),
        (
            "  layout:\n",
            "  layout:\n    repo_id: PRIVATE_MARKER\n",
            "models.layout.repo_id",
        ),
        (
            "'77ede7cc7bed96d853c58f319734803d6ea2ea5c'",
            "main",
            "models.layout.commit_sha",
        ),
        (
            "'77ede7cc7bed96d853c58f319734803d6ea2ea5c'",
            "'123'",
            "models.layout.commit_sha",
        ),
        ("'" + "a" * 64 + "'", "PRIVATE_MARKER", "models.layout.files.0.sha256"),
        ("'" + "a" * 64 + "'", "'" + "A" * 64 + "'", "models.layout.files.0.sha256"),
        ("  table:\n", "  table:\n    mode: fast\n", "models.table"),
        (
            "  formula:\n",
            "  formula:\n    expansion_factor: 0.05\n",
            "models.formula.expansion_factor",
        ),
        ("  formula:\n", "  formula:\n    engine: remote\n", "models.formula.engine"),
        (FORMULA_YAML, "", "extraction"),
    ],
)
def test_required_and_controlled_model_identities_fail_without_echoing_values(
    tmp_path: Path,
    old: str,
    new: str,
    field: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace(old, new))
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=field) as error:
            operation(settings, db)
        assert "PRIVATE_MARKER" not in str(error.value)


@pytest.mark.parametrize(
    "path_value",
    [
        "/tmp/model",
        "../model",
        "a/../b",
        "./config.json",
        "a//b",
        "a\\b",
        "https://example/model",
    ],
)
def test_model_paths_are_relative_artifact_identity_not_host_paths(
    tmp_path: Path,
    path_value: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    path.write_text(
        path.read_text().replace("path: config.json", f"path: '{path_value}'")
    )
    with pytest.raises(ConfigError, match=r"models\.layout\.files\.0\.path"):
        compile_config(settings, db)


@pytest.mark.parametrize(
    "mutation", ["missing_config", "duplicate_file", "missing_weight"]
)
def test_model_file_manifest_must_be_complete_and_unique(
    tmp_path: Path,
    mutation: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    raw = path.read_text()
    if mutation == "duplicate_file":
        raw = raw.replace("path: model.safetensors", "path: config.json", 1)
    else:
        name = "config.json" if mutation == "missing_config" else "model.safetensors"
        hash_char = "a" if mutation == "missing_config" else "b"
        raw = raw.replace(
            f"      - path: {name}\n        sha256: '{hash_char * 64}'\n", "", 1
        )
    path.write_text(raw)
    with pytest.raises(ConfigError, match=r"models\.layout\.files"):
        compile_config(settings, db)


@pytest.mark.parametrize("selector", ["../escape", "V1", "v1/other", " v1"])
def test_extraction_selector_cannot_escape_config_directory(
    tmp_path: Path,
    selector: str,
) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    settings.write_text(f"extraction: '{selector}'\n")
    with pytest.raises(ConfigError, match=r"settings\.extraction"):
        check_config(settings, db)
