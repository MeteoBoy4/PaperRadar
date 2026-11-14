"""B-E15 独立 D1: 真实业务备份/标准恢复/冷进程字节闭包。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from tests.experiment_read_support import read_fixture
from tests.exposure_support import backup, payload
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report
from tests.test_paper_service import observation


def test_cold_restore_keeps_old_and_new_export_bytes_without_original_config_or_runtime(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    assert fixture.read().exit_code == 0
    root = fixture.layout.extraction.root
    reported = report(root.root, "render", "--date", "2026-11-14", "--timezone", "UTC")
    assert reported.exit_code == 0, reported.output
    first, _, old_bytes = payload(root)
    # 冻结之后新增权威边不进入旧清单范围;新清单取得新内容身份。
    PaperFacts(root.database, root.data_root).submit(
        observation(
            doi="10.1029/synthetic1",
            fields={},
            payload=b"late-authoritative-edge",
            relations=(
                {
                    "kind": "has-preprint",
                    "source_doi": "10.1029/synthetic1",
                    "target_doi": "10.1/missing-preprint",
                    "locator": "late/relation",
                },
            ),
        )
    )
    second, _, new_bytes = payload(root)
    assert first["export_id"] != second["export_id"]
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output
    (batch,) = (tmp_path / "backups").iterdir()
    restored = tmp_path / "arbitrary-standard-restored"
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(restored),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    forbidden = [
        root.root,
        fixture.layout.extraction.models,
        fixture.layout.extraction.prepared.credentials,
    ]
    for path in forbidden:
        path.rename(path.with_name(path.name + "-unavailable"))
    output = tmp_path / "independent-exposure-output"
    cold = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.exposure_recovery_worker",
            str(restored),
            str(output),
            first["export_id"] + "," + second["export_id"],
            *(str(p) for p in forbidden),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cold.returncode == 0, cold.stdout + cold.stderr
    assert json.loads(cold.stdout) == [first, second]
    assert (output / first["relative_path"]).read_bytes() == old_bytes
    assert (output / second["relative_path"]).read_bytes() == new_bytes
