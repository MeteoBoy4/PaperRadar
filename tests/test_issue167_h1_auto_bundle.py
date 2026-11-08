"""Unbound D1 automated driver artifact tests; never execute sudo/driver."""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from scripts.issue167_h1_auto_bundle import OLD_RUN, create_auto_bundle
from scripts.issue167_h1_phase import Plan


def test_separate_seal_has_no_hash_cycle_and_single_tty_sudo(tmp_path: Path) -> None:
    plan = Plan("7c93ab04d615", os.getuid(), os.getgid())
    root = create_auto_bundle(tmp_path / "review", plan)
    core = json.loads((root / "manifest.json").read_text())
    seal = json.loads((root / "review-seal.json").read_text())
    driver = (root / "owner-wizard.sh").read_text()
    assert "owner-wizard.sh" not in core["members"]
    assert "review-seal.json" not in core["members"]
    assert "owner-wizard.sh" not in (root / "members.sha256").read_text()
    assert "review-seal.json" not in (root / "members.sha256").read_text()
    assert (
        seal["manifest_sha256"]
        == hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    )
    assert seal["driver_sha256"] == hashlib.sha256(driver.encode()).hexdigest()
    assert seal["manifest_sha256"] in driver
    assert len(re.findall(r"^  if /usr/bin/sudo ", driver, re.M)) == 1
    for forbidden in (
        "sudo -S",
        "SUDO_ASKPASS",
        "ask_secret",
        "read -s",
        "pause ",
        "confirm ",
    ):
        assert forbidden not in driver
    assert "execution-started.json" in driver
    assert "O_EXCL" in driver
    assert "reserved_unknown" in driver
    assert "owner-run.json" in driver
    assert "--expected-manifest-sha" in driver
    subprocess.run(["bash", "-n", str(root / "owner-wizard.sh")], check=True)
    assert list((root / "results").iterdir()) == []
    assert (
        json.loads((root / "retry-context.json").read_text())["predecessor_run_id"]
        == OLD_RUN
    )


def test_old_case_id_cannot_be_reused_to_reset_attempt(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^old_case_cannot_be_reused$"):
        create_auto_bundle(tmp_path / "review", Plan(OLD_RUN, os.getuid(), os.getgid()))
    assert not (tmp_path / "review").exists()


@pytest.mark.parametrize(
    "state", ["unknown", "observed_expected_and_restored", "interrupted"]
)
def test_driver_finalizer_preserves_real_runner_outcomes_without_sudo(
    tmp_path: Path, state: str
) -> None:
    import sys

    from scripts.issue167_h1_auto_bundle import driver_text

    plan = Plan("7c93ab04d615", os.getuid(), os.getgid())
    driver = driver_text(plan, "a" * 64, "# literal bootstrap not executed here")
    script = driver.split("<<'LOCAL_RESULT'\n", 1)[1].split("\nLOCAL_RESULT", 1)[0]
    (tmp_path / "results").mkdir()
    output = tmp_path / "root-output"
    output.write_text(
        json.dumps(
            {
                "owner_result": state,
                "scope": "h1_owner_automation_only",
                "run_id": plan.run_id,
                "manifest_sha256": "a" * 64,
            }
        )
    )
    subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(tmp_path), str(output), "0"],
        input=script.encode(),
        capture_output=True,
        check=False,
    )
    result = json.loads((tmp_path / "results/owner-run.json").read_text())
    assert result["owner_result"] == state
    assert not output.exists()


@pytest.mark.parametrize("exit_code", [1, 130])
def test_driver_never_promotes_success_json_from_failed_root_exit(
    tmp_path: Path, exit_code: int
) -> None:
    import sys

    from scripts.issue167_h1_auto_bundle import driver_text

    plan = Plan("7c93ab04d615", os.getuid(), os.getgid())
    script = (
        driver_text(plan, "a" * 64, "#not executed")
        .split("<<'LOCAL_RESULT'\n", 1)[1]
        .split("\nLOCAL_RESULT", 1)[0]
    )
    (tmp_path / "results").mkdir()
    output = tmp_path / "root-output"
    output.write_text(
        json.dumps(
            {
                "owner_result": "observed_expected_and_restored",
                "scope": "h1_owner_automation_only",
                "run_id": plan.run_id,
                "manifest_sha256": "a" * 64,
            }
        )
    )
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-",
            str(tmp_path),
            str(output),
            str(exit_code),
        ],
        input=script.encode(),
        capture_output=True,
        check=False,
    )
    result = json.loads((tmp_path / "results/owner-run.json").read_text())
    assert result["owner_result"] in {"unknown", "interrupted"}
    assert result["failure_stage"] == "owner_exit"


@pytest.mark.parametrize("field", ["scope", "run_id", "manifest_sha256"])
def test_driver_success_must_bind_scope_run_and_core(
    tmp_path: Path, field: str
) -> None:
    import sys

    from scripts.issue167_h1_auto_bundle import driver_text

    plan = Plan("7c93ab04d615", os.getuid(), os.getgid())
    script = (
        driver_text(plan, "a" * 64, "#not executed")
        .split("<<'LOCAL_RESULT'\n", 1)[1]
        .split("\nLOCAL_RESULT", 1)[0]
    )
    (tmp_path / "results").mkdir()
    output = tmp_path / "root-output"
    value = {
        "owner_result": "observed_expected_and_restored",
        "scope": "h1_owner_automation_only",
        "run_id": plan.run_id,
        "manifest_sha256": "a" * 64,
    }
    value[field] = "wrong-binding"
    output.write_text(json.dumps(value))
    done = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(tmp_path), str(output), "0"],
        input=script.encode(),
        capture_output=True,
        check=False,
    )
    result = json.loads((tmp_path / "results/owner-run.json").read_text())
    assert result["owner_result"] == "unknown"
    assert result["failure_stage"] == "owner_identity"
    assert done.returncode != 0


def test_explicit_predecessor_keeps_latest_unknown_lineage(tmp_path: Path) -> None:
    previous = {
        "kind": "additional_attempt_after_unknown",
        "predecessor_run_id": "7c93ab04d615",
        "predecessor_manifest_sha256": "b" * 64,
        "predecessor_ledger_sha256": "c" * 64,
        "additional_attempts": 1,
    }
    plan = Plan("a840c6d21e97", os.getuid(), os.getgid())
    root = create_auto_bundle(tmp_path / "next", plan, predecessor=previous)
    assert json.loads((root / "retry-context.json").read_text()) == previous
    assert json.loads((root / "plan.json").read_text())["run_id"] == plan.run_id
    with pytest.raises(ValueError, match=r"^old_case_cannot_be_reused$"):
        create_auto_bundle(
            tmp_path / "reused",
            Plan("7c93ab04d615", os.getuid(), os.getgid()),
            predecessor=previous,
        )
