"""B-E14 独立 D1:空/失败日报发布后晚到成功不会改写同日run。"""

import json
from pathlib import Path

import pytest

from tests.experiment_read_support import read_fixture
from tests.pi_execution_support import PeerRun
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report


@pytest.mark.parametrize("failed", [False, True])
def test_late_success_keeps_original_empty_or_failure_run_and_can_publish_paper(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    if failed:
        original = PeerRun.__init__

        def initialize(self: PeerRun, peer: str) -> None:
            lines = []
            for line in peer.splitlines():
                if (
                    line.startswith("        raw = ")
                    and "PRIVATE_READ_CONCLUSION" in line
                ):
                    expression = line.split(" = ", 1)[1]
                    line = (
                        '        raw = "{}" if os.environ.get("OPENAI_API_KEY") == '
                        '"oauth-test-only-sensitive-sentinel" else ' + expression
                    )
                lines.append(line)
            original(self, "\n".join(lines))

        monkeypatch.setattr(PeerRun, "__init__", initialize)
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    if failed:
        failure = fixture.read()
        assert failure.exit_code == 4, failure.output
    options = (
        "--date",
        "2026-11-14",
        "--timezone",
        "Asia/Shanghai",
        "--snapshot",
        fixture.snapshot,
    )
    initial = report(root.root, "render", *options)
    assert initial.exit_code == 0, initial.output
    original_receipt = json.loads(initial.stdout)
    assert original_receipt["members"] == []
    path = root.views / original_receipt["relative_path"]
    frozen = path.read_bytes()
    assert ("因故障没有结果" if failed else "无新结果") in frozen.decode()
    if failed:
        # 仅替换本测试自行创建的合成认证供给;不读取任何凭据内容。
        (fixture.layout.extraction.prepared.credentials / "auth.json").write_text(
            '{"token":"synthetic-report-recovered"}'
        )
        retry = fixture.query(
            "retry",
            fixture.layout.extraction.prepared.paper_id,
            "--snapshot",
            fixture.snapshot,
            "--request-id",
            "report-retry",
            "--reason",
            "PRIVATE_REPORT_RETRY",
            "--actor",
            "owner",
        )
        assert retry.exit_code == 0, retry.output
        child = json.loads(retry.stdout)["task_id"]
        success = fixture.read(request=None, task=child)
    else:
        success = fixture.read()
    assert success.exit_code == 0, success.output
    analysis = json.loads(success.stdout)["task"]["analysis_id"]
    again = report(root.root, "render", *options)
    assert again.exit_code == 0 and json.loads(again.stdout) == original_receipt
    assert path.read_bytes() == frozen
    single = report(root.root, "render", *options, "--analysis-id", analysis)
    assert single.exit_code == 0, single.output
    assert [m["primary_ref"] for m in json.loads(single.stdout)["members"]] == [
        analysis
    ]
    next_day = report(
        root.root,
        "render",
        "--date",
        "2026-11-15",
        "--timezone",
        "Asia/Shanghai",
        "--snapshot",
        fixture.snapshot,
    )
    assert next_day.exit_code == 0, next_day.output
    assert [m["primary_ref"] for m in json.loads(next_day.stdout)["members"]] == [
        analysis
    ]
    assert report(root.root, "rebuild", original_receipt["report_id"]).exit_code == 0
    assert path.read_bytes() == frozen
