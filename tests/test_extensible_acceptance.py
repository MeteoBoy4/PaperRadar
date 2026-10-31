"""独立预期与真实合成组贯通完整入口、执行回执及历史查询。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.a2_full_support import ROOT, repository_copy


def test_help_uses_registration_without_loading_writers(tmp_path: Path) -> None:
    root = repository_copy(tmp_path / "repo")
    registry = root / "scripts/verification_groups.py"
    with registry.open("a") as stream:
        stream.write(
            '\nGROUPS += (Group("合成组", ".synthetic.json", True, '
            '"scripts.missing_writer:write_group", "scripts.missing_scope"),)\n'
        )
    result = subprocess.run(
        (str(root / "scripts/check-offline"), "--help"),
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests/deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "合成组" in result.stdout
    assert "共 15 份 JSON" in result.stdout
    assert not (root / "verification-runs").exists()


def test_receipt_collects_new_registered_module(tmp_path: Path) -> None:
    root = repository_copy(tmp_path / "repo")
    (root / "scripts/synthetic_scope.py").write_text(
        'REQUIRED_TEST_MODULES = (("tests/test_synthetic.py", "0" * 64),)\n'
        'REQUIRED_TEST_CASE_COUNTS = {"tests/test_synthetic.py": 1}\n'
    )
    (root / "tests/test_synthetic.py").write_text(
        "def test_real():\n    assert 2 + 2 == 4\n"
    )
    with (root / "scripts/verification_groups.py").open("a") as stream:
        stream.write(
            '\nGROUPS += (Group("合成组", ".synthetic.json", True, '
            '"scripts.missing_writer:write_group", "scripts.synthetic_scope"),)\n'
        )
    receipt = tmp_path / "receipt.json"
    result = subprocess.run(
        (
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-p",
            "scripts.a2_test_receipt",
            "tests/test_synthetic.py",
        ),
        cwd=root,
        env={
            **os.environ,
            "PAPER_RADAR_TEST_RUN_ID": "synthetic",
            "PAPER_RADAR_TEST_RECEIPT": str(receipt),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(receipt.read_bytes())["modules"]["tests/test_synthetic.py"] == {
        "collected": 1,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "deselected": 0,
        "incomplete": 0,
    }


def test_real_registered_group_reaches_terminal_and_readonly_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.offline_evidence import file_sha256
    from tests.extensible_acceptance_support import query, synthetic_run

    root, result, group = synthetic_run(tmp_path, monkeypatch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "synthetic-executed").read_text() == "real pytest"
    assert group["status"] == "passed"
    assert all(row["result"] == "passed" for row in group["test_modules"])
    assert all(row["result"] == "passed" for row in group["source_modules"])
    audited = subprocess.run(
        (sys.executable, "-B", "-m", "scripts.audit_verification_scope", "--json"),
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert audited.returncode == 0, audited.stdout + audited.stderr
    assert json.loads(audited.stdout)["issues"] == []
    assert group["test_execution"] == [
        {
            "path": "tests/test_synthetic.py",
            "expected_cases": 2,
            "collected": 2,
            "passed": 2,
            "failed": 0,
            "skipped": 0,
            "deselected": 0,
            "incomplete": 0,
            "result": "passed",
        }
    ]
    output = root / "verification-runs"
    terminal = json.loads(next(output.glob("*.terminal.json")).read_bytes())
    assert terminal["groups"][-1] == {
        "suffix": ".synthetic.json",
        "required": True,
        "format_version": 1,
        "sha256": file_sha256(next(output.glob("*.synthetic.json"))),
    }
    # 在副本冷进程使用副本自己的人工预期,准备后旧测试原字节不改。
    checked = subprocess.run(
        (
            sys.executable,
            "-B",
            "-c",
            "from pathlib import Path; "
            "from tests.verification_expectations import assert_output_files; "
            'assert_output_files(Path("verification-runs"))',
        ),
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr
    before = {p: p.read_bytes() for p in output.iterdir()}
    report = query(root, group["run_id"])
    assert (report["status"], report["reason"], report["applicability"]) == (
        "passed",
        "verified",
        "same",
    )
    assert {p: p.read_bytes() for p in output.iterdir()} == before


@pytest.mark.parametrize(
    "mode",
    [
        "skipped",
        "deselected",
        "failed",
        "collect_only",
        "missing_execution",
        "missing_module",
        "wrong_count",
        "missing_record",
    ],
)
def test_real_target_cannot_pass_without_full_fixed_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from tests.extensible_acceptance_support import query, synthetic_run

    root, result, group = synthetic_run(tmp_path, monkeypatch, mode)
    assert result.returncode != 0
    assert group["status"] == "failed"
    assert {reason["item"] for reason in group["reasons"]} == {
        "tests/test_synthetic.py"
    }
    assert {reason["code"] for reason in group["reasons"]} == (
        {"test_execution_not_passed", "scope_drift"}
        if mode == "missing_module"
        else {"test_execution_not_passed"}
    )
    record = group["test_execution"][0]
    if mode in {"skipped", "deselected"}:
        assert record[mode] == 1
    elif mode == "collect_only":
        assert record["incomplete"] == 2
    elif mode == "missing_execution":
        assert record["collected"] == record["passed"] == 0
    elif mode == "failed":
        assert record["failed"] == 1
    assert query(root, group["run_id"])["status"] != "passed"


def test_production_addition_cannot_silently_update_independent_expectations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.extensible_acceptance_support import synthetic_run

    root, result, _ = synthetic_run(tmp_path, monkeypatch, expectation=False)
    assert result.returncode == 0, result.stdout
    check = subprocess.run(
        (
            sys.executable,
            "-B",
            "-c",
            "from scripts.verification_groups import help_text; "
            "from tests.verification_expectations import assert_help; "
            "assert_help(help_text())",
        ),
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert check.returncode != 0
    # 帮助和产物各自敏感,避免第一个失败掩盖第二个。
    output = subprocess.run(
        (
            sys.executable,
            "-B",
            "-c",
            "from pathlib import Path; "
            "from tests.verification_expectations import assert_output_files; "
            'assert_output_files(Path("verification-runs"))',
        ),
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert output.returncode != 0
    transcript = subprocess.run(
        (
            sys.executable,
            "-B",
            "-c",
            "import sys; "
            "from tests.verification_expectations import historical_stdout_bytes; "
            "historical_stdout_bytes(sys.stdin.buffer.read())",
        ),
        cwd=root,
        input=result.stdout,
        capture_output=True,
        text=True,
    )
    assert transcript.returncode != 0


@pytest.mark.parametrize("required", [True, False])
def test_historical_reader_requires_its_own_suffix_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required: bool
) -> None:
    from tests.extensible_acceptance_support import query, synthetic_run

    root, result, group = synthetic_run(tmp_path, monkeypatch, reader=False)
    assert result.returncode == 0
    path = next((root / "verification-runs").glob("*.terminal.json"))
    terminal = json.loads(path.read_bytes())
    terminal["groups"][-1]["required"] = required
    path.write_text(json.dumps(terminal))
    report = query(root, group["run_id"])
    assert (report["status"], report["reason"]) == ("failed", "unsupported_format")


@pytest.mark.parametrize("change", ["missing", "unknown_version", "broken_registry"])
def test_synthetic_history_keeps_material_and_format_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from scripts.offline_evidence import file_sha256
    from tests.extensible_acceptance_support import query, synthetic_run

    root, result, group = synthetic_run(tmp_path, monkeypatch)
    assert result.returncode == 0
    output = root / "verification-runs"
    path = next(output.glob("*.synthetic.json"))
    if change == "missing":
        path.unlink()
        expected = ("unavailable", "material_unavailable")
    elif change == "unknown_version":
        group["format_version"] = 999
        path.write_text(json.dumps(group))
        terminal_path = next(output.glob("*.terminal.json"))
        terminal = json.loads(terminal_path.read_bytes())
        terminal["groups"][-1].update(format_version=999, sha256=file_sha256(path))
        terminal_path.write_text(json.dumps(terminal))
        expected = ("failed", "unsupported_format")
    else:
        (root / "scripts/verification_groups.py").write_text("invalid registry SECRET")
        expected = ("passed", "verified")
    before = {p: p.read_bytes() for p in output.iterdir()}
    report = query(root, group["run_id"])
    assert (report["status"], report["reason"]) == expected
    assert before == {p: p.read_bytes() for p in output.iterdir()}


def test_production_registry_expectation_and_reader_are_independent() -> None:
    from scripts.a2_full_acceptance import acceptance_groups
    from scripts.verification_status import SUPPORTED_GROUP_FORMATS
    from tests.verification_expectations import expected_groups

    assert [(g.name, g.suffix, g.required) for g in acceptance_groups()] == [
        (g["name"], g["suffix"], g["required"]) for g in expected_groups()
    ]
    assert all(g["suffix"] in SUPPORTED_GROUP_FORMATS for g in expected_groups())
    assert ".synthetic.json" not in SUPPORTED_GROUP_FORMATS


@pytest.mark.parametrize(
    "operation", ["socket.socket()", "sqlite3.connect(':memory:')"]
)
def test_dynamic_help_keeps_external_io_sentinel_active(
    tmp_path: Path, operation: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    registry = root / "scripts/verification_groups.py"
    registry.write_text(
        registry.read_text() + f"\nimport socket, sqlite3\n{operation}\n"
    )
    result = subprocess.run(
        (str(root / "scripts/check-offline"), "--help"),
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "tests/deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "帮助命令不应访问网络或数据库" in result.stderr


def test_new_group_publication_failure_cannot_publish_completed_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.extensible_acceptance_support import query, synthetic_run

    root, result, group = synthetic_run(tmp_path, monkeypatch, "publication_failure")
    assert result.returncode != 0
    output = root / "verification-runs"
    assert not list(output.glob("*.synthetic.json"))
    assert not list(output.glob("*.terminal.json"))
    assert not list(output.glob("*.tmp"))
    assert next(output.glob("*.a10.json")).is_file()
    report = query(root, group["run_id"])
    assert (report["status"], report["reason"]) == ("unconfirmed", "terminal_missing")


def test_expected_data_remains_sensitive_for_every_consuming_group(
    tmp_path: Path,
) -> None:
    from tests.extensible_acceptance_support import REVIEWED
    from tests.scope_document_support import prepared_repository
    from tests.test_scope_baseline_audit import git

    root = prepared_repository(
        tmp_path / "repo",
        reviewed=REVIEWED,
        verified_groups=frozenset({"A8", "A9", "A10"}),
    )
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-qm",
        "prepared fixture",
    )
    git(root, "branch", "target")
    expected = root / "tests/fixtures/verification_group_expectations.json"
    expected.write_bytes(expected.read_bytes() + b"\n")
    result = subprocess.run(
        (
            sys.executable,
            "-B",
            "-m",
            "scripts.audit_verification_scope",
            "--base",
            "HEAD",
            "--integration-target",
            "target",
            "--json",
        ),
        cwd=root,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 1
    change = next(
        row
        for row in report["baseline"]["changes"]
        if row["path"] == expected.relative_to(root).as_posix()
    )
    assert change["sensitivity"] == "sensitive"
    assert change["affected_groups"] == [
        "A10",
        "A3",
        "A4",
        "A5",
        "A6",
        "A7",
        "A8",
        "A9",
        "完整 A2",
    ]
