"""只在隔离副本登记合成组,旧组 fixture 与目标真实 pytest 事实分开。"""

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.a2_full_support import fake_checks
from tests.a8_acceptance_support import passed_receipt
from tests.scope_document_support import prepared_repository

# 本票及132-134实际触及的逐材料白名单,不接受其他漂移。
REVIEWED = frozenset(
    {
        "tests/a2_full_support.py",
        "scripts/verification_groups.py",
        "tests/verification_expectations.py",
        "tests/fixtures/verification_group_expectations.json",
        "scripts/a2_full_acceptance.py",
        "scripts/a2_test_receipt.py",
        "scripts/a8_acceptance.py",
        "scripts/audit_verification_scope.py",
        "scripts/check-offline",
        "scripts/verification_scope_audit.py",
        "scripts/verification_scope_baseline.py",
        "scripts/verification_scope_registry.py",
        "tests/test_a2_full_entry.py",
        "tests/test_a4_entry.py",
        "tests/test_a5_entry.py",
        "tests/test_a6_entry.py",
        "tests/test_a7_entry.py",
        "tests/test_a8_entry.py",
        "tests/test_a9_entry.py",
        "tests/test_a10_entry.py",
        "tests/test_verification_run.py",
        "tests/test_verification_compatibility.py",
    }
)

SYNTHETIC_WRITER = """from scripts.synthetic_scope import (
    REQUIRED_TEST_MODULES, REQUIRED_TEST_CASE_COUNTS, REQUIRED_SOURCE_MODULES,
)
from scripts.offline_evidence import file_sha256
from scripts.verification_checks import file_records, receipt_completed, receipt_records
from scripts.verification_publication import publish_conclusion
import json

def write_group(run, interrupted):
    path = run.output_dir / f"{run.run_id}.pytest.json"
    receipt = json.loads(path.read_bytes()) if path.exists() else {}
    records = receipt_records(receipt.get("modules", {}), REQUIRED_TEST_CASE_COUNTS)
    modules = file_records(run.root, REQUIRED_TEST_MODULES)
    sources = file_records(run.root, REQUIRED_SOURCE_MODULES)
    passed = receipt_completed(receipt, run.run_id) and all(
        r["result"] == "passed" for r in [*records, *modules, *sources]
    )
    result = {
        "format_version": 1, "run_id": run.run_id,
        "status": "passed" if passed and not interrupted else "failed",
        "code": run.baseline.code,
        "worktree_sha256": run.baseline.worktree_sha256,
        "lockfile_sha256": run.baseline.lockfile_sha256,
        "pytest_receipt_file": path.name,
        "pytest_receipt_sha256": file_sha256(path),
        "test_execution": records, "test_modules": modules, "source_modules": sources,
        "reasons": [
            {"code": "test_execution_not_passed", "item": r["path"],
             "message_zh": "合成固定分母未通过"}
            for r in records if r["result"] != "passed"
        ] + [
            {"code": "scope_drift", "item": r["path"],
             "message_zh": "合成固定材料未通过"}
            for r in [*modules, *sources] if r["result"] != "passed"
        ],
    }
    path = publish_conclusion(run.output_dir, run.run_id, ".synthetic.json", result)
    return path, result
"""


def frozen_bytes(root: Path) -> dict[str, str]:
    paths = [
        *root.glob("scripts/a[0-9]*_scope.py"),
        *(root / p for p in REVIEWED if p.startswith("tests/test_")),
    ]
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }


def register_synthetic(
    root: Path, *, update_expectation: bool = True, reader: bool = True
) -> None:
    (root / "scripts/synthetic_acceptance.py").write_text(SYNTHETIC_WRITER)
    (root / "tests/test_synthetic.py").write_text(
        "from pathlib import Path\n"
        'def test_first():\n    Path("synthetic-executed").write_text("real pytest")\n'
        "def test_second():\n    assert True\n"
    )
    test_sha = hashlib.sha256(
        (root / "tests/test_synthetic.py").read_bytes()
    ).hexdigest()
    writer_sha = hashlib.sha256(
        (root / "scripts/synthetic_acceptance.py").read_bytes()
    ).hexdigest()
    (root / "scripts/synthetic_scope.py").write_text(
        "from scripts.verification_scope_materials import SHARED_MATERIALS\n"
        f'REQUIRED_TEST_MODULES = (("tests/test_synthetic.py", "{test_sha}"),)\n'
        'REQUIRED_TEST_CASE_COUNTS = {"tests/test_synthetic.py": 2}\n'
        "REQUIRED_SOURCE_MODULES = (\n"
        f'    ("scripts/synthetic_acceptance.py", "{writer_sha}"),\n'
        '    ("scripts/verification_checks.py", '
        'SHARED_MATERIALS["scripts/verification_checks.py"]),\n'
        '    ("scripts/verification_publication.py", '
        'SHARED_MATERIALS["scripts/verification_publication.py"]),\n'
        ")\n"
    )
    # 专属目标 scope 单独登记,不加到旧scope。
    with (root / "scripts/verification_groups.py").open("a") as stream:
        stream.write(
            '\nGROUPS += (Group("合成新组", ".synthetic.json", True, '
            '"scripts.synthetic_acceptance:write_group", '
            '"scripts.synthetic_scope", ("A1",)),)\n'
        )
    if update_expectation:
        expectation = root / "tests/fixtures/verification_group_expectations.json"
        data = json.loads(expectation.read_bytes())
        data["groups"].append(
            {"name": "合成新组", "suffix": ".synthetic.json", "required": True}
        )
        data["fixture_receipt_modules"]["tests/test_synthetic.py"] = 2
        expectation.write_text(json.dumps(data, ensure_ascii=False))
    if reader:
        status = root / "scripts/verification_status.py"
        status.write_text(
            status.read_text().replace(
                "class _Invalid",
                'SUPPORTED_GROUP_FORMATS[".synthetic.json"] = (1,)\n\n\nclass _Invalid',
            )
        )
    # 允许修改的数据只在中央改SHA,不改旧scope/测试字节。
    central = root / "scripts/verification_scope_materials.py"
    import re

    text = central.read_text()
    for relative in (
        "scripts/verification_groups.py",
        "scripts/verification_status.py",
        "tests/fixtures/verification_group_expectations.json",
    ):
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        text = re.sub(
            r'("' + re.escape(relative) + r'":\s*(?:\(\s*)?")[0-9a-f]{64}',
            r"\g<1>" + digest,
            text,
        )
    central.write_text(text)


def synthetic_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str = "passed",
    *,
    expectation: bool = True,
    reader: bool = True,
) -> tuple[Path, subprocess.CompletedProcess[str], dict[str, Any]]:
    root = prepared_repository(
        tmp_path / "repo",
        reviewed=REVIEWED,
        verified_groups=frozenset({"A8", "A9", "A10"}),
    )
    before = frozen_bytes(root)
    register_synthetic(root, update_expectation=expectation, reader=reader)
    assert {
        p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in before
    } == before
    (root / ".gitignore").write_text(
        (root / ".gitignore").read_text() + "\nsynthetic-executed\n"
    )
    target = root / "tests/test_synthetic.py"
    args = ["tests/test_synthetic.py"]
    if mode == "skipped":
        target.write_text(
            "import pytest\n"
            + target.read_text().replace(
                "def test_second():",
                '@pytest.mark.skip(reason="fixture")\ndef test_second():',
            )
        )
    elif mode == "deselected":
        args += ["-k", "first"]
    elif mode == "failed":
        target.write_text(target.read_text().replace("assert True", "assert False"))
    elif mode == "collect_only":
        args += ["--collect-only"]
    elif mode == "missing_execution":
        (root / "tests/test_other.py").write_text(
            "def test_other():\n    assert True\n"
        )
        args = ["tests/test_other.py"]
    elif mode == "missing_module":
        target.unlink()
    elif mode == "wrong_count":
        scope = root / "scripts/synthetic_scope.py"
        scope.write_text(scope.read_text().replace(": 2}", ": 3}"))
    # 各变体在运行身份采集之前显式登记自己的已知测试材料;不在运行中重绑。
    if target.exists():
        scope = root / "scripts/synthetic_scope.py"
        import re

        scope.write_text(
            re.sub(
                r'(\("tests/test_synthetic.py", ")[0-9a-f]{64}',
                r"\g<1>" + hashlib.sha256(target.read_bytes()).hexdigest(),
                scope.read_text(),
            )
        )
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    writer = tmp_path / "write_receipt.py"
    # 旧组继续用既有fixture;目标只取真实pytest原始结果,不能回填目标passed/collected。
    writer.write_text(
        "import json, os, subprocess, sys\nfrom pathlib import Path\n"
        'command = [sys.executable, "-B", "-m", "pytest", "-q", "-p", '
        f'"scripts.a2_test_receipt", {", ".join(repr(a) for a in args)}]\n'
        "completed = subprocess.run(command)\n"
        'path = Path(os.environ["PAPER_RADAR_TEST_RECEIPT"])\n'
        "actual = json.loads(path.read_bytes())\n"
        f"old = {passed_receipt('fixture')!r}\n"
        'assert "tests/test_synthetic.py" not in old["modules"]\n'
        'actual["modules"].update(old["modules"])\n'
        + (
            'actual["modules"].pop("tests/test_synthetic.py")\n'
            if mode == "missing_record"
            else ""
        )
        + "path.write_text(json.dumps(actual))\n"
        "sys.exit(completed.returncode)\n"
    )
    # fake_checks原shell总返回0;保留真实目标进程退出码以免掩盖失败。
    uv = binary / "uv"
    uv.write_text(
        uv.read_text().replace(
            f"{shlex.quote(sys.executable)} {shlex.quote(str(writer))} ;;",
            f"{shlex.quote(sys.executable)} {shlex.quote(str(writer))}; exit $? ;;",
        )
    )
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    # 模拟边界脚本位于/tmp,身份采集之后不再改树。
    command = (sys.executable, "-B", "-m", "scripts.a1_acceptance")
    if mode == "publication_failure":
        program = """
import os
from scripts.a2_full_acceptance import main
original = os.link
def fail(source, target):
    if str(target).endswith('.synthetic.json'):
        raise OSError('synthetic publication failure')
    original(source, target)
os.link = fail
raise SystemExit(main())
"""
        command = (sys.executable, "-B", "-c", program)
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    output = root / "verification-runs"
    paths = list(output.glob("*.synthetic.json"))
    group = (
        json.loads(paths[0].read_bytes())
        if paths
        else {"run_id": next(output.glob("*.json")).name[:32]}
    )
    return root, result, group


def query(root: Path, run_id: str) -> dict[str, Any]:
    from tests.a2_full_support import ROOT

    result = subprocess.run(
        (str(root / "scripts/verification-status"), run_id, "--json"),
        cwd=root,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(ROOT / ".venv")},
        capture_output=True,
        text=True,
    )
    value: dict[str, Any] = json.loads(result.stdout)
    assert result.returncode == (0 if value["status"] == "passed" else 1), result.stderr
    return value
