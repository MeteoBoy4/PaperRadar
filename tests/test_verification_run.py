"""同次验收可显式登记额外组, 顺序与整体通过资格彼此独立。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.verification_publication import publish_conclusion
from scripts.verification_run import AcceptanceGroup, VerificationRun, run_verification
from tests.a2_full_support import repository_copy
from tests.a3_acceptance_support import fake_checks


@pytest.mark.parametrize("required", [False, True])
def test_registered_group_publishes_same_run_and_can_affect_overall_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required: bool
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))

    def extra(run: VerificationRun, interrupted: bool) -> tuple[Path, dict[str, Any]]:
        a1_path, a1 = run.conclusions["A1"]
        assert a1_path.is_file() and a1["a1_verified"]
        result = {"run_id": run.run_id, "status": "failed", "reasons": []}
        return publish_conclusion(
            run.output_dir, run.run_id, ".extra.json", result
        ), result

    group = AcceptanceGroup(
        name="合成组",
        suffix=".extra.json",
        write=extra,
        required=required,
        dependencies=("A1",),
    )
    run = run_verification(root, tmp_path / "runs", (*acceptance_groups(), group))
    path, result = run.conclusions["合成组"]
    assert path.name == f"{run.run_id}.extra.json"
    assert json.loads(path.read_bytes()) == result
    assert run.conclusions["完整 A2"][1]["a2_verified"]
    assert run.conclusions["A3"][1]["a3_verified"]
    assert run.passed is (not required)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 6
    assert len(list(run.output_dir.glob("*.json"))) == 7


@pytest.mark.parametrize(
    "case", ["duplicate_name", "duplicate_output", "missing_dependency"]
)
def test_invalid_registration_is_rejected_before_any_checks(
    tmp_path: Path, case: str
) -> None:
    from dataclasses import replace

    first = acceptance_groups()[0]
    if case == "duplicate_name":
        extra = replace(first, suffix=".extra.json")
    elif case == "duplicate_output":
        extra = replace(first, name="合成组")
    else:
        extra = replace(
            first, name="合成组", suffix=".extra.json", dependencies=("缺组",)
        )
    output = tmp_path / "runs"
    with pytest.raises(ValueError, match="验收组登记"):
        run_verification(tmp_path, output, (first, extra))
    assert not output.exists()
