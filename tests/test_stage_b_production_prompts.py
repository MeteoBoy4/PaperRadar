"""B D1:公开业务 Prompt 的离线 CLI 消费;全部配置与正文均为合成材料。"""

import hashlib
import json
from pathlib import Path

import pytest

from paper_radar.config import (
    RuntimeConfigSnapshot,
    StageName,
    load_config_snapshot,
    project_config,
)
from paper_radar.llm import build_call, render_request
from paper_radar.llm.rpc import validate_request
from paper_radar.llm.rpc_frames import command_frame
from paper_radar.pi_execution import check_system_prompt
from paper_radar.read_inputs import build_read_correction, read_input_budget
from paper_radar.reading.acceptance_v2 import ReadV2Category, ReadV2Issue
from paper_radar.reading.context import (
    Evidence,
    ExtractionIdentity,
    PageFact,
    Provenance,
    ReadContext,
    SourceBlock,
)
from paper_radar.screening_tasks import FailureKind
from paper_radar.screening_tasks.attempt_rules import correction_for
from paper_radar.stage_inputs import (
    ExtractionFacts,
    ReadFacts,
    ScreeningFacts,
    build_stage_input,
)
from tests.config_test_support import run_cli
from tests.test_read_stage_input import read_configuration

REPOSITORY = Path(__file__).resolve().parents[1]
PUBLIC_PROMPTS = (
    "prompts/screening/boundary-v1.md",
    "prompts/screening/value-v1.md",
    "prompts/reading/v1.md",
    "config/prompts/pi-system-v1.md",
)


def production_inputs(root: Path) -> tuple[Path, Path]:
    """只复制公开指令;模型、Profile、主题等全部来自既有合成工厂。"""
    settings, database = read_configuration(root)
    system_path = root / PUBLIC_PROMPTS[-1]
    old_hash = hashlib.sha256(system_path.read_bytes()).hexdigest()
    for relative in PUBLIC_PROMPTS:
        (root / relative).write_bytes((REPOSITORY / relative).read_bytes())
    adapter = settings.parent / "adapters/pi-v1.yaml"
    adapter.write_text(
        adapter.read_text().replace(
            old_hash, hashlib.sha256(system_path.read_bytes()).hexdigest()
        ),
        encoding="utf-8",
    )
    return settings, database


def compile_via_cli(
    root: Path, settings: Path, database: Path
) -> RuntimeConfigSnapshot:
    result = run_cli(
        root,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    snapshot_id = result.stdout.split("快照身份：", 1)[1].splitlines()[0]
    return load_config_snapshot(database, snapshot_id)


@pytest.mark.parametrize("command", ["check", "compile"])
def test_public_prompts_are_ready_through_offline_configuration_cli(
    tmp_path: Path, command: str
) -> None:
    settings, database = production_inputs(tmp_path)
    result = run_cli(
        tmp_path,
        "config",
        command,
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    for stage in ("boundary", "value", "read"):
        assert f"{stage}：ready" in result.stdout
    if command == "compile":
        snapshot_id = result.stdout.split("快照身份：", 1)[1].splitlines()[0]
        snapshot = load_config_snapshot(database, snapshot_id)
        saved_hashes = {item.raw_sha256 for item in snapshot.materials.values()}
        for relative in PUBLIC_PROMPTS:
            assert (
                hashlib.sha256((REPOSITORY / relative).read_bytes()).hexdigest()
                in saved_hashes
            )
    for relative in PUBLIC_PROMPTS:
        assert (REPOSITORY / relative).read_text() not in result.stdout + result.stderr


@pytest.mark.parametrize("relative", PUBLIC_PROMPTS)
def test_registered_public_prompt_version_cannot_change_bytes(
    tmp_path: Path, relative: str
) -> None:
    settings, database = production_inputs(tmp_path)
    original = compile_via_cli(tmp_path, settings, database)
    path = tmp_path / relative
    old_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(path.read_bytes() + b"\n")
    if relative.startswith("config/"):
        # 新 adapter 声明合法引用换字节的旧系统 Prompt 版本。
        # 不得被资源哈希校验提前挡住。
        adapter = settings.parent / "adapters/pi-v1.yaml"
        adapter.with_name("pi-v2.yaml").write_text(
            adapter.read_text()
            .replace("version: pi-v1", "version: pi-v2")
            .replace(old_hash, hashlib.sha256(path.read_bytes()).hexdigest())
        )
        settings.write_text(settings.read_text().replace(": pi-v1", ": pi-v2"))
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 2
    assert "声明版本已登记不同字节" in result.stderr
    assert "请" in result.stderr
    assert path.read_text() not in result.stdout + result.stderr
    assert load_config_snapshot(database, original.snapshot_id) == original


def test_new_read_prompt_version_preserves_screening_inputs_and_calibration(
    tmp_path: Path,
) -> None:
    settings, database = production_inputs(tmp_path)
    before = compile_via_cli(tmp_path, settings, database)
    prompt = tmp_path / "prompts/reading/v1.md"
    prompt.with_name("v2.md").write_bytes(
        prompt.read_bytes() + "\n额外核查说明：保留尚未核对的限制。\n".encode()
    )
    settings.write_text(settings.read_text().replace("reading: v1", "reading: v2"))
    after = compile_via_cli(tmp_path, settings, database)
    first, second = project_config(before), project_config(after)
    assert before.snapshot_id != after.snapshot_id
    assert first.baseline.baseline_id == second.baseline.baseline_id
    facts = ScreeningFacts(
        title="Synthetic title 中文😀",
        abstract='Synthetic abstract with "quotes" and\nnewlines.',
        abstract_truncated=False,
    )
    for stage in (StageName.BOUNDARY, StageName.VALUE):
        assert (
            build_stage_input(before, stage, facts).fingerprint
            == build_stage_input(after, stage, facts).fingerprint
        )
    extraction = build_stage_input(
        before, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
    )
    read_facts = ReadFacts(
        extraction_input=extraction,
        reading_sha256="2" * 64,
        evidence_map_sha256="3" * 64,
        output_language="zh",
    )
    assert (
        build_stage_input(before, StageName.READ, read_facts).fingerprint
        != build_stage_input(after, StageName.READ, read_facts).fingerprint
    )


@pytest.mark.parametrize("stage", [StageName.BOUNDARY, StageName.VALUE, StageName.READ])
def test_public_prompts_fit_complete_frames_and_single_system_argument(
    tmp_path: Path, stage: StageName
) -> None:
    settings, database = production_inputs(tmp_path)
    snapshot = compile_via_cli(tmp_path, settings, database)
    corrections: tuple[str | None, ...]
    if stage is StageName.READ:
        # 直接构造已确认的合成正文消费上下文,不启动或替换任何真实解析器。
        reading = '[evidence:e1]\n合成正文 "引号" 与换行😀。\n'.encode()
        extraction = build_stage_input(
            snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
        )
        facts = ReadFacts(
            extraction_input=extraction,
            reading_sha256=hashlib.sha256(reading).hexdigest(),
            evidence_map_sha256="3" * 64,
            output_language="zh",
        )
        identity = ExtractionIdentity(*facts.identity)
        context = ReadContext(
            identity=identity,
            pages=(PageFact(identity, 1, 600.0, 800.0, "top_left"),),
            source_blocks=(SourceBlock(identity, "s1", "合成正文"),),
            evidence=(
                Evidence(identity, "e1", (Provenance("s1", 1, (0, 0, 20, 20), 0, 4),)),
            ),
            expected_language="zh",
        )
        description = build_call(
            build_stage_input(snapshot, stage, facts),
            snapshot,
            snapshot,
            read_context=context,
            reading=reading,
        )
        long_path = "$.main_findings" + "[1234567890123456789]" * 8 + "[0]" * 3
        assert len(long_path) == 192
        corrections = (
            build_read_correction(
                ReadV2Issue(long_path, item) for item in ReadV2Category
            ),
        )
        budget = read_input_budget(description)
        assert budget.accepted
        assert budget.correction_frame_bytes <= 262144
        assert json.loads(description.user_payload_json)["output_language"] == "zh"
    else:
        screening_facts = ScreeningFacts(
            title="Synthetic title 中文😀",
            abstract='Synthetic abstract with "quotes" and\nnewlines.',
            abstract_truncated=False,
        )
        description = build_call(
            build_stage_input(snapshot, stage, screening_facts), snapshot, snapshot
        )
        corrections = tuple(correction_for(kind) for kind in FailureKind)
    assert (
        check_system_prompt(description.system_prompt).encode()
        == (REPOSITORY / PUBLIC_PROMPTS[-1]).read_bytes()
    )
    assert len(description.system_prompt) + 1 <= 131072
    payload = json.loads(description.user_payload_json)
    assert "journals" not in payload and "reputation" not in payload
    assert "期刊集合" not in description.user_payload_json
    for correction in (None, *corrections):
        request = render_request(description, correction)
        assert validate_request(request) is None
        frame = command_frame("rpc-9", "prompt", message=request.decode())
        assert len(frame) <= 262144
        if stage is StageName.READ:
            assert len(frame) <= budget.correction_frame_bytes
