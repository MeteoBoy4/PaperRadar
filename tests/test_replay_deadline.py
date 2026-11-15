"""独立 D1:合成恢复副本的总时限与受控失败分类。"""

import subprocess
from pathlib import Path

import pytest

from paper_radar.replay.contract import ReplayError
from paper_radar.replay.service import replay
from tests.replay_support import restored_demo


def test_worker_timeout_is_not_isolation_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, originals = restored_demo(tmp_path)

    def expired(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(
            "PRIVATE_COMMAND", 120, output=b"PRIVATE_PARTIAL_RESPONSE"
        )

    monkeypatch.setattr(subprocess, "run", expired)
    with pytest.raises(ReplayError, match=r"^replay_timeout$"):
        replay(root, originals)
    assert list((root / "views").iterdir()) == []


@pytest.mark.parametrize("limit", [0, -1, 3601, True, 1.5])
def test_invalid_deadline_refuses_before_layout(limit: int) -> None:
    with pytest.raises(ReplayError, match=r"^invalid_arguments$"):
        replay(Path("PRIVATE_UNOPENED_ROOT"), (), timeout_seconds=limit)


def test_cli_timeout_has_chinese_next_step_without_private_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from paper_radar.cli import app
    from tests.replay_support import replay_args

    root, originals = restored_demo(tmp_path)

    def expired(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("PRIVATE_COMMAND", 7, output=b"PRIVATE_BODY")

    monkeypatch.setattr(subprocess, "run", expired)
    result = CliRunner().invoke(
        app, [*replay_args(root, originals), "--timeout-seconds", "7"]
    )
    assert result.exit_code == 2
    assert "replay_timeout：完整 worker 超过总时限" in result.output
    assert "保留副本" in result.output and "--timeout-seconds" in result.output
    assert "isolation_unavailable" not in result.output
    assert "PRIVATE" not in result.output and str(tmp_path) not in result.output


def test_real_preexec_failure_remains_isolation_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.replay.isolation import ReplayBoundary

    root, originals = restored_demo(tmp_path)

    def unavailable(self: ReplayBoundary) -> None:
        raise RuntimeError("PRIVATE_ISOLATION_START")

    monkeypatch.setattr(ReplayBoundary, "__call__", unavailable)
    with pytest.raises(ReplayError, match=r"^isolation_unavailable$"):
        replay(root, originals)
    assert list((root / "views").iterdir()) == []


def test_actual_subprocess_deadline_stops_confined_child_and_cleans_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    root, originals = restored_demo(tmp_path)
    run = subprocess.run

    def delayed(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        # 真实服务的 OS 边界/时限/管道/清理,只替换 worker 为本地合成休眠程序。
        return run(  # type: ignore[call-overload,no-any-return]
            [sys.executable, "-I", "-B", "-c", "import time; time.sleep(10)"],
            **kwargs,
        )

    monkeypatch.setattr(subprocess, "run", delayed)
    with pytest.raises(ReplayError, match=r"^replay_timeout$"):
        replay(root, originals, timeout_seconds=1)
    assert list((root / "views").iterdir()) == []


def test_selected_deadline_preserves_closed_success_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    root, originals = restored_demo(tmp_path)
    expected = dict(
        isolation="verified",
        descendant="verified",
        originals_denied=6,
        missing_originals=0,
        sockets_denied=3,
        direct_connect_denied=True,
        reports=0,
        analyses=0,
        evidence_slices=0,
        exposures=0,
    )

    def completed(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        assert kwargs["timeout"] == 73
        return subprocess.CompletedProcess([], 0, json.dumps(expected).encode())

    monkeypatch.setattr(subprocess, "run", completed)
    assert replay(root, originals, timeout_seconds=73) == expected


@pytest.mark.parametrize(
    "reason, expected",
    [("content_corrupt", "content_corrupt"), ("PRIVATE_REASON", "replay_failed")],
)
def test_worker_business_failures_remain_distinct_from_isolation_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str, expected: str
) -> None:
    import json

    root, originals = restored_demo(tmp_path)

    def failed(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            [], 2, json.dumps({"reason": reason}).encode()
        )

    monkeypatch.setattr(subprocess, "run", failed)
    with pytest.raises(ReplayError, match=f"^{expected}$"):
        replay(root, originals)


@pytest.mark.parametrize("value", ["0", "3601", "PRIVATE_INVALID"])
def test_cli_deadline_arguments_are_controlled_and_private(value: str) -> None:
    from typer.testing import CliRunner

    from paper_radar.cli import app

    result = CliRunner().invoke(app, ["replay", "--timeout-seconds", value])
    assert result.exit_code == 2 and "invalid_arguments" in result.output
    assert "PRIVATE" not in result.output


def test_deadline_help_is_cold_and_explains_bound(tmp_path: Path) -> None:
    from tests.config_test_support import run_cli

    result = run_cli(tmp_path, "replay", "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert "--timeout-seconds" in result.stdout and "600" in result.stdout
    assert "3600" in result.stdout and "replay_timeout" in result.stdout
    assert list(tmp_path.iterdir()) == []
