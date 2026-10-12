"""A2-06 公共服务的 Read 配置行为。"""

import hashlib
import json
from pathlib import Path

import pytest

from paper_radar.config import (
    ChunkingVersion,
    check_config,
    compile_config,
    load_config_snapshot,
)
from paper_radar.config.compile import StageName
from tests.config_read_support import READ_PROMPT, read_inputs
from tests.config_test_support import boundary_inputs


def test_read_configuration_is_saved_but_requires_authoritative_contract(
    tmp_path: Path,
) -> None:
    settings, db = read_inputs(tmp_path)
    checked = check_config(settings, db)
    saved = compile_config(settings, db)
    assert saved == checked == load_config_snapshot(db, saved.snapshot_id)
    assert saved.model_slots["reading"] == "configured"
    assert saved.stages[StageName.READ].status == "not_ready"
    assert saved.stages[StageName.READ].missing == ("read_contract",)
    assert saved.stages[StageName.BOUNDARY].status == "ready"
    assert saved.read is not None
    assert saved.read.chunking_version is ChunkingVersion.V1
    materials = json.loads(saved.payload_json)["materials"]
    assert next(m for m in materials if m["kind"] == "read")["config"] == {
        "version": "read-v1",
        "chunking_version": "v1",
    }
    prompt = next(m for m in materials if m["name"] == "reading")
    assert prompt["kind"] == "prompt"
    assert prompt["config"] == {"text": READ_PROMPT.decode()}


@pytest.mark.parametrize(
    ("model", "status", "reason"),
    [
        ("null", "unconfigured", "read_model"),
        ("{}", "unconfigured", "read_model"),
        ("{provider: provider-a, model: read-model}", "unconfigured", "read_model"),
        (
            "{provider: REQUIRED_FOR_READ, model: read-model, protocol: prompt_only}",
            "placeholder",
            "read_model_placeholder",
        ),
        (
            "{provider: provider-a, model: REQUIRED, protocol: prompt_only}",
            "placeholder",
            "read_model_placeholder",
        ),
    ],
)
def test_read_model_status_does_not_change_boundary_readiness(
    tmp_path: Path, model: str, status: str, reason: str
) -> None:
    settings, db = read_inputs(tmp_path)
    path = settings.parent / "models/models-v1.yaml"
    path.write_text(path.read_text().split("reading:")[0] + f"reading: {model}\n")
    saved = compile_config(settings, db)
    assert saved.model_slots["reading"] == status
    assert saved.stages[StageName.READ].missing == (reason, "read_contract")
    assert saved.stages[StageName.BOUNDARY].status == "ready"


@pytest.mark.parametrize("prompt", [b"", b" \n", b" ... \n"])
def test_read_prompt_placeholder_is_distinct_from_missing_contract(
    tmp_path: Path, prompt: bytes
) -> None:
    settings, db = read_inputs(tmp_path)
    (tmp_path / "prompts/reading/v1.md").write_bytes(prompt)
    saved = compile_config(settings, db)
    assert saved.stages[StageName.READ].missing == (
        "read_prompt_placeholder",
        "read_contract",
    )


def test_unselected_read_materials_are_missing_even_when_files_exist(
    tmp_path: Path,
) -> None:
    settings, db = read_inputs(tmp_path)
    settings.write_text(
        settings.read_text()
        .replace("  reading: v1\n", "")
        .replace("read: read-v1\n", "")
    )
    saved = compile_config(settings, db)
    assert saved.read is None
    assert saved.stages[StageName.READ].missing == (
        "read_prompt",
        "read_contract",
        "chunking_version",
    )


def test_boundary_only_snapshot_retains_identity_and_read_is_unconfigured(
    tmp_path: Path,
) -> None:
    settings, db = boundary_inputs(tmp_path)
    saved = compile_config(settings, db)
    assert saved.read is None
    assert saved.stages[StageName.READ].missing == (
        "read_model",
        "read_prompt",
        "read_contract",
        "chunking_version",
    )
    assert "read" not in json.loads(saved.payload_json)["selectors"]


def test_read_adapter_system_prompt_placeholder_remains_a_required_input(
    tmp_path: Path,
) -> None:
    settings, db = read_inputs(tmp_path)
    (settings.parent / "adapters").mkdir()
    (settings.parent / "prompts").mkdir()
    prompt = b"...\n"
    (settings.parent / "prompts/pi-system-v1.md").write_bytes(prompt)
    (settings.parent / "adapters/pi-v1.yaml").write_text(
        "version: pi-v1\npi_version: 1.1.0\nadapter_version: transport-v1\n"
        "thinking_level: low\nresources:\n  - version: v1\n"
        f"    sha256: {hashlib.sha256(prompt).hexdigest()}\n"
    )
    settings.write_text(settings.read_text() + "adapters:\n  reading: pi-v1\n")
    saved = compile_config(settings, db)
    assert saved.adapter_slots["reading"] == "placeholder"
    assert saved.stages[StageName.READ].missing == (
        "read_adapter_prompt_placeholder",
        "read_contract",
    )
    assert saved.stages[StageName.BOUNDARY].status == "ready"
