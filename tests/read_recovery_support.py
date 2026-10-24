"""固定 Read 消费材料与恢复观察;上下文不是持久化制品。"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from paper_radar.backup import create_backup, verify_backup
from paper_radar.config import (
    StageName,
    compile_config,
    list_config_snapshots,
    load_config_snapshot,
    project_config,
)
from paper_radar.reading import (
    AllowedEvidence,
    Evidence,
    ExtractionIdentity,
    PageFact,
    Provenance,
    ReadContext,
    ReadErrorCategory,
    ReadOutputError,
    SourceBlock,
    validate_read_output,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.backup_support import tree
from tests.read_config_support import read_contract_inputs
from tests.read_support import candidate

IDENTITY = ExtractionIdentity("read-extraction-v1", "read-content-v1", "read-map-v1")
TEXT = (
    "PRIVATE_READ_SOURCE\nRainfall increased by 30%.\n全角字符３０与 e\u0301 保持原样。"
)
TABLE = "PRIVATE_READ_TABLE: Basin comparison 42%."
PROGRAM_ZH = (
    "请核对 $.main_findings[0].statement 的数值“99%”"
    "（number_not_supported）；所引片段未提供可匹配支持。"
)
PROGRAM_EN = (
    "Please verify the number '99%' at $.main_findings[0].statement "
    "(number_not_supported); cited spans do not provide matching support."
)


@dataclass(frozen=True)
class RecoveryCase:
    language: Literal["zh", "en"]
    mode: Literal["single", "reduce"]
    raw: bytes = field(repr=False)

    @property
    def name(self) -> str:
        return f"{self.language}-{self.mode}"


def recovery_cases() -> tuple[RecoveryCase, ...]:
    cases = []
    for language in ("zh", "en"):
        for mode in ("single", "reduce"):
            english = language == "en"
            reason = {
                "statement": "The method permits comparison."
                if english
                else "方法可用于比较。",
                "evidence": [{"evidence_id": "e-text"}],
            }
            raw = candidate(
                output_language=language,
                one_sentence_conclusion="PRIVATE_READ_CANDIDATE: comparison."
                if english
                else "PRIVATE_READ_CANDIDATE：比较预测方法。",
                research_question="How can forecasts be compared?"
                if english
                else "如何比较预测？",
                methods_summary="Compare independent forecasts."
                if english
                else "比较独立预测。",
                data_summary="Use public observations."
                if english
                else "使用公开观测数据。",
                main_findings=[
                    {
                        "statement": "Rainfall increased by 99%."
                        if english
                        else "降水增加了99%。",
                        "evidence": [{"evidence_id": "e-text"}],
                    }
                ],
                research_value_reason=reason,
                reuse_feasibility_reason=reason,
                key_limitations=[
                    {
                        "statement": "The unreviewed table gives 42%."
                        if english
                        else "未复核表格给出42%。",
                        "evidence": [{"evidence_id": "e-table"}],
                    }
                ],
                why_it_matters="It helps compare predictions."
                if english
                else "有助于比较预测。",
                next_action="Inspect the assumptions." if english else "检查研究假设。",
                degraded_content_warnings=[
                    "PRIVATE_MODEL_WARNING: inspect evidence.",
                    "PRIVATE_MODEL_WARNING: inspect evidence.",
                    PROGRAM_EN if english else PROGRAM_ZH,
                ],
            )
            # 相同语言的模式不属于模型字段;不同空白使四份原始候选均独立可寻址。
            raw = (b" \n" if mode == "single" else b"\n\t") + raw + b"\n "
            cases.append(RecoveryCase(language, mode, raw))
    return tuple(cases)


def recovery_context(case: RecoveryCase) -> ReadContext:
    return ReadContext(
        IDENTITY,
        [
            PageFact(IDENTITY, 3, 600, 800, "top_left"),
            PageFact(IDENTITY, 8, 700, 900, "bottom_left"),
        ],
        [
            SourceBlock(IDENTITY, "s-text", TEXT),
            SourceBlock(IDENTITY, "s-table", TABLE, "table"),
        ],
        [
            Evidence(
                IDENTITY,
                "e-text",
                [Provenance("s-text", 3, (0, 0, 600, 800), 0, len(TEXT))],
            ),
            Evidence(
                IDENTITY,
                "e-table",
                [Provenance("s-table", 8, (0, 0, 700, 900), 0, len(TABLE))],
            ),
        ],
        expected_language=case.language,
        mode=case.mode,
        allowed_evidence=AllowedEvidence(IDENTITY, ["e-text", "e-table"])
        if case.mode == "reduce"
        else None,
    )


def digest(value: object) -> str:
    raw = (
        value
        if isinstance(value, bytes)
        else json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    )
    return hashlib.sha256(raw).hexdigest()


def assert_no_business_facts(database: Path) -> None:
    # 明确的副作用审计;没有为这一断言制造 Paper/任务或新增查询 API。
    with closing(
        sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    ) as connection:
        for table in (
            "papers",
            "screening_requests",
            "screening_tasks",
            "screening_attempts",
            "screening_successes",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                0,
            )


def recovery_view(
    database: Path, data_root: Path, artifacts: dict[str, str]
) -> dict[str, Any]:
    store = ArtifactStore(database, data_root)
    snapshots = []
    for summary in list_config_snapshots(database):
        snapshot = load_config_snapshot(database, summary.snapshot_id)
        assert "PRIVATE_" not in repr(snapshot) + str(snapshot)
        semantics = project_config(snapshot)
        snapshots.append(
            {
                "id": snapshot.snapshot_id,
                "payload_sha256": digest(snapshot.payload_json),
                "read_projection": semantics.projections[StageName.READ].projection_id,
                "baseline": semantics.baseline.baseline_id,
                "read_status": snapshot.stages[StageName.READ].status,
            }
        )
    cases = []
    for case in recovery_cases():
        artifact_id = artifacts[case.name]
        record = store.get_artifact(artifact_id)
        assert record.kind == "model_success_response"
        raw = store.read_artifact(artifact_id)["payload"]
        assert raw == case.raw
        context = recovery_context(case)
        result = validate_read_output(raw, context)
        assert [item.reason.value for item in result.diagnostics] == [
            "restricted_numeric_support",
            "number_not_supported",
        ]
        assert result.identity == IDENTITY and result.mode == case.mode
        assert result.analysis.research_value == result.analysis.reuse_feasibility == 3
        assert result.model_warnings[0] == result.model_warnings[1]
        assert result.warnings[2].text == result.warnings[-1].text
        assert (result.warnings[2].origin, result.warnings[-1].origin) == (
            "model",
            "program",
        )
        assert "PRIVATE_" not in repr(result) + repr(context) + repr(result.analysis)
        cases.append(
            {
                "name": case.name,
                "artifact_id": artifact_id,
                "raw_sha256": digest(raw),
                "analysis_sha256": digest(result.analysis.model_dump(mode="json")),
                "identity": asdict(result.identity),
                "mode": result.mode,
                "rules": [result.evidence_rule_version, result.numeric_rule_version],
                "diagnostics": [asdict(item) for item in result.diagnostics],
                "warnings_sha256": digest([asdict(item) for item in result.warnings]),
                "model_warnings_sha256": digest(result.model_warnings),
                "support_sha256": digest([asdict(item) for item in result.support]),
            }
        )
    assert_no_business_facts(database)
    return {"snapshots": snapshots, "cases": cases}


def assert_restored_policy_rejections(
    database: Path, data_root: Path, artifacts: dict[str, str]
) -> None:
    store = ArtifactStore(database, data_root)
    case = next(case for case in recovery_cases() if case.name == "zh-reduce")
    original = store.read_artifact(artifacts[case.name])["payload"]
    context = recovery_context(case)
    data = json.loads(original)
    data["main_findings"] = [
        {
            "statement": "PRIVATE_REJECTED: 表格数值42%。",
            "evidence": [{"evidence_id": "e-table"}],
        }
    ]
    try:
        validate_read_output(json.dumps(data, ensure_ascii=False).encode(), context)
    except ReadOutputError as error:
        assert [(item.location, item.category) for item in error.issues] == [
            (
                "$.main_findings[0].statement",
                ReadErrorCategory.RESTRICTED_NUMERIC_SUPPORT,
            )
        ]
        assert "PRIVATE_" not in str(error) + repr(error) + repr(error.diagnostics)
        assert "42%" not in str(error) + repr(error)
        assert error.__cause__ is error.__context__ is None
    else:
        raise AssertionError("expected_restricted_numeric_rejection")
    limited = ReadContext(
        context.identity,
        context.pages,
        context.source_blocks,
        context.evidence,
        expected_language=case.language,
        mode="reduce",
        allowed_evidence=AllowedEvidence(IDENTITY, ["e-text"]),
    )
    try:
        validate_read_output(original, limited)
    except ReadOutputError as error:
        assert {item.category for item in error.issues} == {
            ReadErrorCategory.EVIDENCE_NOT_ALLOWED,
            ReadErrorCategory.EVIDENCE_REQUIRED,
        }
        assert "PRIVATE_" not in str(error) + repr(error)
    else:
        raise AssertionError("expected_allowed_evidence_rejection")
    try:
        validate_read_output(original.rstrip()[:-1], context)
    except ReadOutputError as error:
        assert [(item.location, item.category) for item in error.issues] == [
            ("$", ReadErrorCategory.INVALID_JSON)
        ]
        assert "PRIVATE_" not in str(error) + repr(error)
        assert error.__cause__ is error.__context__ is None
    else:
        raise AssertionError("expected_invalid_json_rejection")
    # 无效候选仅在内存中测试,没有作为成功响应重新登记。
    assert store.read_artifact(artifacts[case.name])["payload"] == original
    assert len(store.list_artifacts()) == 4
    assert_no_business_facts(database)


@dataclass(frozen=True)
class RecoveryArchive:
    root: Path
    database: Path
    data_root: Path
    artifacts: dict[str, str]
    expected: dict[str, Any] = field(repr=False)


def archive(root: Path) -> RecoveryArchive:
    settings, database = read_contract_inputs(root)
    profile = settings.parent / "profiles/profile-v1.yaml"
    profile.write_text(
        profile.read_text().replace(
            "background: climate", "background: PRIVATE_PROFILE"
        ),
        encoding="utf-8",
    )
    (root / "prompts/reading/v1.md").write_bytes(b"PRIVATE_READING_PROMPT\n")
    chosen = settings.read_text()
    settings.write_text(chosen.replace("  read: v1\n", ""), encoding="utf-8")
    old = compile_config(settings, database)
    settings.write_text(chosen, encoding="utf-8")
    new = compile_config(settings, database)
    assert "PRIVATE_" not in repr(old) + repr(new)
    assert old.snapshot_id != new.snapshot_id
    assert old.stages[StageName.READ].status == "not_ready"
    assert new.stages[StageName.READ].status == "ready"
    assert (
        project_config(old).baseline.baseline_id
        == project_config(new).baseline.baseline_id
    )
    store = ArtifactStore(database, root / "data")
    artifacts = {}
    for case in recovery_cases():
        validate_read_output(case.raw, recovery_context(case))
        artifacts[case.name] = store.publish_single(
            "model_success_response", [case.raw]
        ).artifact_id
    assert len(store.list_artifacts()) == 4
    expected = recovery_view(database, root / "data", artifacts)
    return RecoveryArchive(root, database, root / "data", artifacts, expected)


def recover_in_new_process(
    data: RecoveryArchive, temporary_root: Path
) -> dict[str, Any]:
    batch = create_backup(data.database, data.data_root, temporary_root / "backups")
    assert verify_backup(batch.batch_dir).manifest == batch.manifest
    before_batch = tree(batch.batch_dir)
    original_data = tree(data.data_root)
    unavailable = data.root.rename(temporary_root / "unavailable-original")
    data.root.write_text("original_path_sentinel", encoding="utf-8")
    assert data.root.is_file() and not data.database.exists()
    expected_file = temporary_root / "expectation.json"
    expected_file.write_text(
        json.dumps({"artifacts": data.artifacts, "view": data.expected}),
        encoding="utf-8",
    )
    assert "PRIVATE_" not in expected_file.read_text()
    repo = Path(__file__).resolve().parents[1]
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.read_recovery_worker",
            str(batch.batch_dir),
            str(temporary_root / "restored"),
            str(temporary_root / "moved-restored"),
            str(expected_file),
            str(data.root),
            str(unavailable),
        ],
        cwd=temporary_root,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": os.pathsep.join(
                (str(repo), str(repo / "tests/deny_network"))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "PRIVATE_" not in child.stdout + child.stderr
    assert child.returncode == 0, child.stdout + child.stderr
    assert tree(batch.batch_dir) == before_batch
    assert tree(unavailable / "data") == original_data
    moved = temporary_root / "moved-restored"
    for entry in batch.manifest.blobs:
        copied = moved / entry.path
        assert copied.stat().st_ino != (batch.batch_dir / entry.path).stat().st_ino
        assert copied.stat().st_ino != (unavailable / "data" / entry.path).stat().st_ino
    result: dict[str, Any] = json.loads(child.stdout)
    return result
