"""独立 D1:报告回放组合端口实核登记、旧投影与发布字节。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.experiment.reports import ReportError, Reports
from tests.test_experiment_reports_cli import report


def prepared(tmp_path: Path) -> tuple[Reports, dict[str, object], Path]:
    root = tmp_path / "synthetic"
    result = CliRunner().invoke(app, ["experiment", "init", "--root", str(root)])
    assert result.exit_code == 0, result.output
    result = report(
        root, "render", "--date", "2026-11-14", "--timezone", "Asia/Shanghai"
    )
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    return (
        Reports(root / "paper-radar.sqlite3", root / "data", root / "views"),
        receipt,
        root,
    )


def test_report_replay_rebuilds_all_frozen_bytes_and_keeps_database_and_logs(
    tmp_path: Path,
) -> None:
    service, receipt, root = prepared(tmp_path)
    result = report(
        root, "render", "--date", "2026-11-15", "--timezone", "Asia/Shanghai"
    )
    assert result.exit_code == 0, result.output
    second = json.loads(result.stdout)
    expected = {
        str(r["relative_path"]): (root / "views" / str(r["relative_path"])).read_bytes()
        for r in (receipt, second)
    }
    before = service.database.read_bytes()
    log = (root / "logs/runtime.jsonl").read_bytes()
    for relative in expected:
        (root / "views" / relative).unlink()
    assert service.replay() == (receipt, second)
    assert service.replay() == (receipt, second)
    for relative, content in expected.items():
        assert (root / "views" / relative).read_bytes() == content
    assert service.database.read_bytes() == before
    assert (root / "logs/runtime.jsonl").read_bytes() == log


def test_report_replay_rejects_changed_existing_projection_across_calls(
    tmp_path: Path,
) -> None:
    service, receipt, root = prepared(tmp_path)
    assert service.replay() == (receipt,)
    path = root / "views" / str(receipt["relative_path"])
    path.write_bytes(b"PRIVATE_CHANGED_REPORT")
    with pytest.raises(ReportError, match=r"^content_corrupt"):
        service.replay()
    assert path.read_bytes() == b"PRIVATE_CHANGED_REPORT"


def test_report_replay_rejects_changed_registration_across_calls(
    tmp_path: Path,
) -> None:
    service, receipt, _ = prepared(tmp_path)
    assert service.replay() == (receipt,)
    # 只损坏本用例创建的合成文件;不关闭 append-only 保护或改生产写入规则。
    original = service.database.read_bytes()
    altered = original.replace(b'"renderer_version":1', b'"renderer_version":9')
    assert altered != original and len(altered) == len(original)
    service.database.write_bytes(altered)
    with pytest.raises(ReportError, match=r"^registration_invalid"):
        service.replay()
