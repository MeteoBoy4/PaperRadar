"""#151 独立覆盖。新工具链配置、语义与历史回放。不扩充历史验收组。"""

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    StageName,
    check_config,
    compile_config,
    load_config_snapshot,
    project_config,
)
from paper_radar.stage_inputs import (
    ExtractionFacts,
    build_stage_input,
    replay_stage_input,
)
from tests.config_extraction_support import extraction_inputs
from tests.config_test_support import run_cli


@pytest.mark.parametrize("backend", ["pypdfium2", "threaded_docling_parse"])
def test_v2_checks_compiles_and_loads_with_exact_selected_components(
    tmp_path: Path, backend: str
) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(
        path.read_text().replace("docling-2.135.0-cpu-v1", "docling-2.135.0-cpu-v2")
        + f"pdf_backend: {backend}\n"
    )
    checked = check_config(settings, database)
    saved = compile_config(settings, database)
    assert saved == checked == load_config_snapshot(database, saved.snapshot_id)
    assert saved.stages[StageName.EXTRACTION].status == "ready"
    assert saved.extraction is not None
    expected = {
        "docling-slim": "2.135.0",
        "docling-core": "2.105.0",
        "docling-ibm-models": "4.0.3",
        "torch": "2.14.1+cpu",
        "torchvision": "0.29.1+cpu",
        "transformers": "5.19.0",
        "pypdfium2": "5.14.0",
    }
    if backend == "threaded_docling_parse":
        expected["docling-parse"] = "7.22.2"
    assert dict(saved.extraction.backend.component_versions) == expected
    assert saved.extraction.backend.backend_id == "docling"
    assert saved.extraction.backend.backend_version == "2.135.0"


def test_supply_view_is_stdlib_only_and_separates_cli_from_parser_semantics() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from paper_radar.docling_toolchain import "
            "toolchain_supply, backend_identity; "
            "s = toolchain_supply('docling-2.135.0-cpu-v2'); "
            "assert dict(s.cli_constraints) == {'typer': '0.27.2'}; "
            "assert dict(s.component_versions)['docling-parse'] == '7.22.2'; "
            "assert dict(s.component_versions)['docling-core'] == '2.105.0'; "
            "b = backend_identity('docling-2.135.0-cpu-v2', 'pypdfium2'); "
            "assert 'typer' not in dict(b.component_versions); "
            "assert 'docling-parse' not in dict(b.component_versions); "
            "assert not any(x.split('.')[0] in "
            "{'pydantic', 'docling', 'torch', 'typer'} for x in sys.modules)",
            str(Path(__file__).resolve().parents[1] / "src"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "name", ["settings-extraction-v2.yaml", "settings-extraction-v2-threaded.yaml"]
)
def test_new_synthetic_examples_work_through_public_configuration_entries(
    tmp_path: Path, name: str
) -> None:
    from paper_radar.config import upgrade_database

    source = Path(__file__).resolve().parents[1] / "examples/config"
    shutil.copytree(source, tmp_path / "config")
    settings = tmp_path / "config" / name
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    args = ("--settings", str(settings), "--database", str(database))
    checked = run_cli(tmp_path, "config", "check", *args)
    assert checked.returncode == 0, checked.stderr
    saved = run_cli(tmp_path, "config", "compile", *args)
    assert saved.returncode == 0, saved.stderr
    assert saved.stdout == checked.stdout
    snapshot_id = saved.stdout.splitlines()[0].split("：")[1]
    loaded = load_config_snapshot(database, snapshot_id)
    assert loaded == check_config(settings, database)
    assert loaded.extraction is not None
    assert (
        dict(loaded.extraction.backend.component_versions)["docling-core"] == "2.105.0"
    )


@pytest.mark.parametrize("backend", ["pypdfium2", "threaded_docling_parse"])
def test_v2_projection_and_stage_input_match_independent_literals(
    tmp_path: Path, backend: str
) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    original = compile_config(settings, database)
    new_path = path.with_name("extraction-v2.yaml")
    new_path.write_text(
        path.read_text()
        .replace("version: extraction-v1", "version: extraction-v2")
        .replace("docling-2.135.0-cpu-v1", "docling-2.135.0-cpu-v2")
        + f"pdf_backend: {backend}\n"
    )
    settings.write_text("extraction: extraction-v2\n")
    current = compile_config(settings, database)
    fixture = Path(__file__).parent / "fixtures/docling_v2" / backend
    expected_projection = (fixture / "projection.json").read_bytes()
    expected_input = (fixture / "stage-input.json").read_bytes()
    expected_fingerprint = (fixture / "stage-input.sha256").read_text().strip()
    projection = project_config(current).projections[StageName.EXTRACTION]
    assert projection.payload_json.encode() == expected_projection
    assert projection.projection_id == hashlib.sha256(expected_projection).hexdigest()
    result = build_stage_input(
        current, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    assert result.payload_bytes == expected_input
    assert result.fingerprint == expected_fingerprint
    assert (
        replay_stage_input(expected_input, expected_fingerprint, snapshot=current)
        == result
    )
    before = json.loads(
        project_config(original).projections[StageName.EXTRACTION].payload_json
    )
    old = before["components"]["extraction"]
    new = json.loads(projection.payload_json)["components"]["extraction"]
    assert old["model_artifacts"] == new["model_artifacts"]
    assert old["normalization_version"] == new["normalization_version"] == "v1"
    old["backend"]["component_versions"]["docling-core"] = "2.105.0"
    if backend == "threaded_docling_parse":
        old["backend"]["component_versions"]["docling-parse"] = "7.22.2"
        old["backend_config"]["pdf_backend"] = "threaded_docling_parse"
        old["backend_config"]["pdf_options"] = {
            "enforce_same_font": True,
            "include_bitmap_images": False,
            "render_pages": True,
            "render_scale": 1.0,
        }
    assert old == new
    assert load_config_snapshot(database, original.snapshot_id) == original


def test_new_declared_version_does_not_change_v2_semantics(tmp_path: Path) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace("cpu-v1", "cpu-v2"))
    original = compile_config(settings, database)
    path.with_name("extraction-copy.yaml").write_text(
        path.read_text().replace("version: extraction-v1", "version: extraction-copy")
        + "# a new registered declaration, with identical semantics\n"
    )
    settings.write_text("extraction: extraction-copy\n")
    changed = compile_config(settings, database)
    assert original.snapshot_id != changed.snapshot_id
    assert project_config(original) == project_config(changed)
    facts = ExtractionFacts(pdf_sha256="1" * 64)
    assert build_stage_input(
        original, StageName.EXTRACTION, facts
    ) == build_stage_input(changed, StageName.EXTRACTION, facts)


@pytest.mark.parametrize(
    "old,new,field",
    [
        ("cpu-v1", "cpu-unknown", "toolchain"),
        (
            "normalization_version: v1",
            "component_versions: {}\nnormalization_version: v1",
            "component_versions",
        ),
        (
            "normalization_version: v1",
            "backend_version: 9\nnormalization_version: v1",
            "backend_version",
        ),
        (
            "normalization_version: v1",
            "pdf_backend: unknown\nnormalization_version: v1",
            "pdf_backend",
        ),
    ],
)
def test_unknown_or_independently_overridden_components_are_rejected(
    tmp_path: Path, old: str, new: str, field: str
) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace(old, new))
    with pytest.raises(ConfigError, match=rf"^extraction\.{field}："):
        check_config(settings, database)


@pytest.mark.parametrize("toolchain", ["cpu-v1", "cpu-v2"])
def test_rehashed_archive_cannot_override_its_original_toolchain(
    tmp_path: Path, toolchain: str
) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace("cpu-v1", toolchain))
    saved = compile_config(settings, database)
    payload = json.loads(saved.payload_json)
    entry = next(x for x in payload["materials"] if x["kind"] == "extraction")
    entry["config"]["backend"]["component_versions"]["docling-core"] = "9.9.9"
    tampered = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    tampered_id = hashlib.sha256(tampered.encode()).hexdigest()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE runtime_config_snapshots SET payload_json = ?, snapshot_id = ?",
            (tampered, tampered_id),
        )
        connection.execute(
            "UPDATE snapshot_version_refs SET snapshot_id = ?", (tampered_id,)
        )
    with pytest.raises(ConfigError, match="快照内容或版本引用损坏"):
        load_config_snapshot(database, tampered_id)


def test_old_history_replays_without_sdk_or_runtime_inventory_in_cold_process(
    tmp_path: Path,
) -> None:
    settings, path, database = extraction_inputs(tmp_path)
    original = compile_config(settings, database)
    path.with_name("extraction-v2.yaml").write_text(
        path.read_text()
        .replace("extraction-v1", "extraction-v2")
        .replace("cpu-v1", "cpu-v2")
    )
    settings.write_text("extraction: extraction-v2\n")
    current = compile_config(settings, database)
    script = """
import importlib.abc
import importlib.metadata
import socket
import ssl
import sys
from pathlib import Path
class RejectSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'docling', 'docling_core', 'docling_parse',
             'docling_ibm_models', 'torch', 'torchvision', 'transformers',
             'pypdfium2', 'cv2'}:
            raise AssertionError('SDK import')
def deny(*args, **kwargs):
    raise AssertionError('runtime inventory or network access')
sys.meta_path.insert(0, RejectSDK())
socket.socket = deny
socket.create_connection = deny
from paper_radar.config import check_config, compile_config, load_config_snapshot
importlib.metadata.version = deny
importlib.metadata.distribution = deny
if len(sys.argv) == 5:
    checked = check_config(Path(sys.argv[4]), Path(sys.argv[1]))
    assert checked == compile_config(Path(sys.argv[4]), Path(sys.argv[1]))
    assert checked.snapshot_id == sys.argv[3]
for identifier, expected_core in ((sys.argv[2], '2.101.1'), (sys.argv[3], '2.105.0')):
    s = load_config_snapshot(Path(sys.argv[1]), identifier)
    core = dict(s.extraction.backend.component_versions)['docling-core']
    assert core == expected_core
    print(s.snapshot_id)
"""
    for additional in ((str(settings),), ()):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(database),
                original.snapshot_id,
                current.snapshot_id,
                *additional,
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [original.snapshot_id, current.snapshot_id]
        if additional:
            shutil.rmtree(settings.parent)
