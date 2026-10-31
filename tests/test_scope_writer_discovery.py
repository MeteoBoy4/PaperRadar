"""共享 writer 发现保留显式实现根与各公开调用者的错误策略。"""

import inspect
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import NoReturn

import pytest

from scripts import a2_full_acceptance, audit_verification_scope
from scripts.verification_run import VerificationRun
from scripts.verification_scope_registry import discover_writer_paths


def _unused_writer(run: VerificationRun, interrupted: bool) -> NoReturn:
    raise AssertionError("额外 writer 不应执行")


def test_discovery_uses_explicit_implementation_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    group = a2_full_acceptance.acceptance_groups()[0]
    monkeypatch.setattr(a2_full_acceptance, "acceptance_groups", lambda: (group,))
    source = tmp_path / "implementation/scripts/writer.py"
    monkeypatch.setattr(inspect, "getsourcefile", lambda writer: str(source))

    paths = tuple(discover_writer_paths(tmp_path / "implementation"))

    assert [(writer.group, writer.path, writer.error) for writer in paths] == [
        (group.name, "scripts/writer.py", None)
    ]


@pytest.mark.parametrize(
    ("source", "reason"),
    [(None, "writer_unavailable"), ("outside", "registry_unavailable")],
)
def test_audit_cli_keeps_writer_discovery_failures_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: str | None,
    reason: str,
) -> None:
    group = a2_full_acceptance.acceptance_groups()[0]
    monkeypatch.setattr(a2_full_acceptance, "acceptance_groups", lambda: (group,))
    outside = str(tmp_path / "private-writer.py") if source else None
    monkeypatch.setattr(inspect, "getsourcefile", lambda writer: outside)
    monkeypatch.setattr(sys, "argv", ["audit-verification-scope", "--json"])

    assert audit_verification_scope.main() == 1

    output = capsys.readouterr()
    report = json.loads(output.out)
    assert reason in {issue["reason"] for issue in report["issues"]}
    assert report["exit_code"] == 1
    assert "private-writer" not in output.out + output.err


@pytest.mark.parametrize("source", [None, "outside"])
def test_a8_skips_extra_unlocatable_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str | None
) -> None:
    from tests.a8_acceptance_support import conclude, same_a8_run

    inputs = same_a8_run(tmp_path)
    groups = a2_full_acceptance.acceptance_groups()
    extra = replace(groups[0], name="额外组", write=_unused_writer)
    monkeypatch.setattr(
        a2_full_acceptance, "acceptance_groups", lambda: (*groups, extra)
    )
    original = inspect.getsourcefile
    outside = str(tmp_path / "private-writer.py") if source else None
    monkeypatch.setattr(
        inspect,
        "getsourcefile",
        lambda writer: outside if writer is _unused_writer else original(writer),
    )

    _, result = conclude(tmp_path, inputs)

    assert result["status"] == "passed", result["reasons"]
    assert result["a8_verified"] is True
