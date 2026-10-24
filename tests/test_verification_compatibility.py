"""从重构前实现取得的终端字节, 覆盖原启动入口与各组发布中断。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.a2_full_support import ROOT, fake_checks, repository_copy
from tests.a8_acceptance_support import passed_receipt


@pytest.mark.parametrize(
    "case",
    [
        "passed",
        "failed",
        "interrupted",
        "legacy_mismatch",
        "a1_before_publication",
        "a1_after_publication",
        "a2_before_publication",
        "a2_after_publication",
    ],
)
def test_full_entry_preserves_original_terminal_bytes_and_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    expected = json.loads(
        (ROOT / "tests/fixtures/verification_transcripts.json").read_bytes()
    )[case]
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    monkeypatch.setenv("A2_TEST_STOP", case)
    if case == "legacy_mismatch":
        scope = root / "scripts/a2_scope.py"
        scope.write_text(
            scope.read_text(encoding="utf-8").replace(
                "SNAPSHOT_FORMAT_VERSION = 1", "SNAPSHOT_FORMAT_VERSION = 0"
            ),
            encoding="utf-8",
        )
    if "publication" in case:
        stage, moment, _ = case.split("_")
        command = (
            sys.executable,
            "-c",
            f"""
import os, sys
from scripts.a2_full_acceptance import main
original = os.link
fired = False
def publish(source, target):
    global fired
    if str(target).endswith('.{stage}.json') and not fired:
        fired = True
        if {moment == "after"!r}:
            original(source, target)
        raise KeyboardInterrupt
    original(source, target)
os.link = publish
sys.exit(main())
""",
        )
    else:
        command = (sys.executable, "-m", "scripts.a1_acceptance")
    result = subprocess.run(command, cwd=root, capture_output=True, check=False)
    output = root / "verification-runs"
    full = json.loads(next(output.glob("*.a2-full.json")).read_bytes())
    stdout = result.stdout.replace(str(output).encode(), b"<OUTPUT>").replace(
        full["run_id"].encode(), b"<RUN>"
    )
    # 历史 transcript 逐字比较; A8/A9 新输出与终态另有独立测试。
    historical_stdout = b"".join(
        line
        for line in stdout.splitlines(keepends=True)
        if not line.startswith(("[A8 验收]".encode(), "[A9 验收]".encode()))
    )
    assert historical_stdout == expected["stdout"].encode()
    assert result.stderr == expected["stderr"].encode()
    assert result.returncode == expected["exit_code"]
    assert len(log.read_text(encoding="utf-8").splitlines()) == (
        5 if case in {"failed", "interrupted"} else 6
    )
    assert len(list(output.glob("*.json"))) == (
        12 if case in {"failed", "interrupted"} else 13
    )
    assert not list(output.glob("*.tmp"))
    legacy = json.loads(next(output.glob("*.a2.json")).read_bytes())
    if case.startswith("a2_"):
        assert legacy["status"] == "passed"
        assert full["status"] == "incomplete"


def test_final_publication_interrupt_does_not_overwrite_previous_conclusions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.a2_full_acceptance import run_full_verification

    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    original = os.link
    published: dict[Path, bytes] = {}

    def interrupt_full(source: Path, target: Path) -> None:
        if target.name.endswith(".a2-full.json"):
            raise KeyboardInterrupt
        original(source, target)
        published[target] = target.read_bytes()

    monkeypatch.setattr(os, "link", interrupt_full)
    output = tmp_path / "runs"
    with pytest.raises(KeyboardInterrupt):
        run_full_verification(root, output)
    assert len(published) == 2
    assert all(path.read_bytes() == raw for path, raw in published.items())
    assert not list(output.glob("*.a2-full.json"))
    assert not list(output.glob("*.tmp"))
