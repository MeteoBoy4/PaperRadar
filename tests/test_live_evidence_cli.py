from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "arguments",
    [
        ["live-evidence", "--help"],
        ["live-evidence", "show", "--help"],
        ["live-evidence", "receive", "--help"],
    ],
)
def test_live_evidence_help_is_local_and_does_not_open_ledger(
    tmp_path: Path, arguments: list[str]
) -> None:
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        [str(Path(sys.executable).with_name("paper-radar")), *arguments],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "准入" in result.stdout
    assert "当前用途" in result.stdout
    assert "副作用" in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_unknown_contract_keeps_historical_guidance_and_new_choice(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "contracts",
            "check",
            "--contract",
            "unknown",
            "--version",
            "v1",
            "--target",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert (
        "未知契约；当前支持：boundary、value-prediction、reuse-assessment、decision-reasons、read。"
        in result.stderr
    )
    assert "另支持：live-evidence。" in result.stderr
    assert list(tmp_path.iterdir()) == []
