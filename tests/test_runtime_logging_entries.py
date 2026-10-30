"""已交付执行入口必须装配文件汇;只读入口不创建日志。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service

# 新的生产入口必须加入此公共执行守卫,服务调用仍可显式选 NullSink。
DELIVERED_EXECUTION_ENTRIES = ("run", "resume")


@pytest.mark.parametrize("command", DELIVERED_EXECUTION_ENTRIES)
def test_real_audit_entry_constructs_sink_for_selected_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    from paper_radar.fixture_audit import acquisition_service

    original = sampling_service(tmp_path, MatrixSources())
    assert original.data_root is not None
    original.data_root.mkdir(exist_ok=True)
    plan = original.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    monkeypatch.setattr(
        acquisition_service,
        "SourceHTTPExecutor",
        lambda: original.acquisitions.executors["http"],
    )
    # resume 的代码身份按既有生产策略匹配本地 checkout。
    if command == "resume":
        from paper_radar.fixture_audit.acquisition_identity import capture_code_identity

        plan = original.create_audit_plan(
            contact_email="audit@example.org", code_identity=capture_code_identity()
        )
    result = CliRunner().invoke(
        app,
        [
            "audit",
            command,
            *([plan.plan_id] if command == "resume" else []),
            "--database",
            str(original.database),
            "--data-root",
            str(original.data_root),
            "--contact-email",
            "audit@example.org",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    logged = [
        json.loads(line)
        for line in (original.data_root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert logged[0]["event"] == "run_started" and logged[-1]["event"] == "run_finished"
    assert (
        "audit@example.org"
        not in (original.data_root / "logs/runtime.jsonl").read_text()
    )
