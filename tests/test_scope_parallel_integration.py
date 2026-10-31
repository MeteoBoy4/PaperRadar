"""临时 Git 中的跨 spec 集成,只通过公开基线审计和身份边界观察。"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import verification_scope_audit as audit
from scripts.verification_identity import capture_identity
from scripts.verification_status import query_status
from tests.test_scope_baseline_audit import confirmations_for

ROOT = Path(__file__).resolve().parents[1]
WRITERS = (("A", "scripts/a_acceptance.py"), ("B", "scripts/b_acceptance.py"))
CENTRAL = "scripts/verification_scope_materials.py"


def git(
    root: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
        },
    )


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD").stdout.strip()


def snapshot(root: Path) -> dict[str, bytes]:
    paths = git(root, "ls-files").stdout.splitlines()
    return {relative: (root / relative).read_bytes() for relative in paths} | {
        ".git/index": (root / ".git/index").read_bytes()
    }


def rebind(root: Path, relative: str) -> str:
    """仅测试内受控维护指定条目;生产审计不写登记。"""
    central = root / CENTRAL
    rows = central.read_text().splitlines()
    sha = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    rows = [
        f'    "{relative}": "{sha}",' if f'"{relative}":' in row else row
        for row in rows
    ]
    central.write_text("\n".join(rows) + "\n")
    return sha


def repository(root: Path) -> str:
    (root / "scripts").mkdir()
    for name in (
        "__init__.py",
        "verification_scope_registry.py",
        "verification_scope_audit.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, root / "scripts" / name)
    (root / audit.CLASSIFICATION_PATH).parent.mkdir(parents=True)
    (root / audit.CLASSIFICATION_PATH).write_text(
        json.dumps(
            {"classification_rules": {"live_documents": {"exact_paths": ["README.md"]}}}
        )
    )
    materials = {
        "left.py": b"left = 1\n",
        "right.py": b"right = 1\n",
        "shared.fixture": b"first=1\n" + b"middle=1\n" * 12 + b"last=1\n",
    }
    for relative, content in materials.items():
        (root / relative).write_bytes(content)
    # 间隔让不相交中央条目也能由 Git 真正自动合并。
    (root / CENTRAL).write_text(
        "SHARED_MATERIALS = {\n"
        + ("\n" * 8).join(
            f'    "{relative}": "{hashlib.sha256(content).hexdigest()}",\n'
            for relative, content in materials.items()
        )
        + "}\n"
    )
    (root / "tests").mkdir()
    (root / "tests/test_sample.py").write_text("def test_sample():\n    assert True\n")
    test_sha = hashlib.sha256((root / "tests/test_sample.py").read_bytes()).hexdigest()
    for group in ("a", "b"):
        (root / f"scripts/{group}_scope.py").write_text(
            "from scripts.verification_scope_materials import SHARED_MATERIALS\n"
            'REQUIRED_SOURCE_MODULES = (("left.py", SHARED_MATERIALS["left.py"]),\n'
            '    ("right.py", SHARED_MATERIALS["right.py"]))\n'
            'REQUIRED_FIXTURE_FILES = (("shared.fixture",\n'
            '    SHARED_MATERIALS["shared.fixture"]),)\n'
            f'REQUIRED_TEST_MODULES = (("tests/test_sample.py", "{test_sha}"),)\n'
            'REQUIRED_TEST_CASE_COUNTS = {"tests/test_sample.py": 1}\n'
            + (
                'REQUIRED_SCOPE_REFERENCES = ("scripts/a_scope.py",)\n'
                if group == "b"
                else ""
            )
        )
        (root / f"scripts/{group}_acceptance.py").write_text(
            f"from scripts.{group}_scope import (REQUIRED_SOURCE_MODULES,\n"
            "    REQUIRED_FIXTURE_FILES, REQUIRED_TEST_MODULES,\n"
            "    REQUIRED_TEST_CASE_COUNTS)\n"
        )
    git(root, "init", "-b", "integration-target")
    git(root, "config", "user.name", "Integration Test")
    git(root, "config", "user.email", "integration@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    return commit(root, "fixed local baseline")


def report(root: Path, base: str, *, confirmations: object = ()) -> audit.AuditReport:
    return audit.audit_baseline(
        root,
        base=base,
        integration_target="integration-target",
        writers=WRITERS,
        confirmations=confirmations,
    )


def test_disjoint_specs_preserve_both_central_hashes_after_merge(
    tmp_path: Path,
) -> None:
    base = repository(tmp_path)
    git(tmp_path, "checkout", "-b", "spec-left")
    (tmp_path / "left.py").write_bytes(b"left = 2\n")
    left_sha = rebind(tmp_path, "left.py")
    target = commit(tmp_path, "left spec reviewed source")
    git(tmp_path, "branch", "-f", "integration-target", target)
    git(tmp_path, "checkout", "-b", "spec-right", base)
    (tmp_path / "right.py").write_bytes(b"right = 2\n")
    right_sha = rebind(tmp_path, "right.py")
    commit(tmp_path, "right spec reviewed source")

    git(tmp_path, "merge", "--no-ff", "integration-target", "-m", "merge target first")
    central_before = (tmp_path / CENTRAL).read_bytes()
    tree_before = snapshot(tmp_path)
    outcome = report(tmp_path, target)

    assert outcome["exit_code"] == 0
    assert outcome["issues"] == []
    assert all(row["reason"] == "ok" for row in outcome["files"])
    assert left_sha.encode() in central_before and right_sha.encode() in central_before
    assert {c["path"] for c in outcome["baseline"]["changes"]} == {"right.py"}
    assert all(c["sensitivity"] == "mechanical" for c in outcome["baseline"]["changes"])
    assert (tmp_path / CENTRAL).read_bytes() == central_before
    assert snapshot(tmp_path) == tree_before


@pytest.mark.parametrize("merge_kind", ["automatic", "manual"])
def test_shared_fixture_merge_requires_actual_bytes_and_all_confirmations(
    tmp_path: Path, merge_kind: str
) -> None:
    base = repository(tmp_path)
    fixture = tmp_path / "shared.fixture"
    original = fixture.read_bytes()
    git(tmp_path, "checkout", "-b", "spec-left")
    fixture.write_bytes(original.replace(b"first=1", b"first=left"))
    left_sha = rebind(tmp_path, "shared.fixture")
    target = commit(tmp_path, "review left fixture")
    git(tmp_path, "branch", "-f", "integration-target", target)
    git(tmp_path, "checkout", "-b", "spec-right", base)
    fixture.write_bytes(
        original.replace(
            b"last=1" if merge_kind == "automatic" else b"first=1",
            b"last=right" if merge_kind == "automatic" else b"first=right",
        )
    )
    right_sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if merge_kind == "manual":
        rebind(tmp_path, "shared.fixture")
    commit(tmp_path, "right fixture work")
    merged = git(
        tmp_path,
        "merge",
        "--no-ff",
        "integration-target",
        "-m",
        "merge target first",
        check=False,
    )
    if merge_kind == "manual":
        assert merged.returncode == 1
        assert set(
            git(tmp_path, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
        ) == {CENTRAL, "shared.fixture"}
        fixture.write_bytes(original.replace(b"first=1", b"first=left+right"))
        # 人工文本解冲突先保留右方候选,证明它不能当作合并后的有效登记。
        git(tmp_path, "checkout", "--ours", CENTRAL)
        commit(tmp_path, "resolve text only")
    else:
        assert merged.returncode == 0
        assert fixture.read_bytes() == original.replace(
            b"first=1", b"first=left"
        ).replace(b"last=1", b"last=right")

    before = (tmp_path / CENTRAL).read_bytes()
    stale_tree = snapshot(tmp_path)
    stale = report(tmp_path, target)
    assert stale["exit_code"] == 1
    assert {
        (row["group"], row["reason"])
        for row in stale["files"]
        if row["path"] == "shared.fixture"
    } == {("A", "hash_drift"), ("B", "hash_drift")}
    assert (tmp_path / CENTRAL).read_bytes() == before
    assert stale["baseline"]["baseline_issues"] == []
    early_confirmations = confirmations_for(stale)
    still_stale = report(tmp_path, target, confirmations=early_confirmations)
    assert still_stale["issues"] == []
    assert still_stale["exit_code"] == 1  # S3 确认不能解除真实字节漂移。
    assert snapshot(tmp_path) == stale_tree

    merged_sha = rebind(tmp_path, "shared.fixture")
    assert merged_sha not in {left_sha, right_sha}
    rebound = report(tmp_path, target)
    rebound_tree = snapshot(tmp_path)
    assert all(row["reason"] == "ok" for row in rebound["files"])
    assert rebound["exit_code"] == 1  # 重算后仍缺 S3 确认。
    invalid = report(tmp_path, target, confirmations=early_confirmations)
    assert "invalid_confirmation" in {issue["reason"] for issue in invalid["issues"]}
    confirmations = confirmations_for(rebound)
    assert {confirmation["group"] for confirmation in confirmations} == {"A", "B"}
    partial = report(tmp_path, target, confirmations=confirmations[:1])
    assert partial["exit_code"] == 1
    assert "confirmation_required" in {issue["reason"] for issue in partial["issues"]}
    confirmed = report(tmp_path, target, confirmations=confirmations)
    assert confirmed["exit_code"] == 0
    assert confirmed["issues"] == []
    assert snapshot(tmp_path) == rebound_tree
    assert {(row["path"], row["group"]) for row in confirmations} == {
        ("scripts/a_scope.py", "A"),
        ("scripts/a_scope.py", "B"),
        ("scripts/b_scope.py", "B"),
        ("shared.fixture", "A"),
        ("shared.fixture", "B"),
    }
    assert all(
        change["confirmed_groups"] == change["affected_groups"]
        for change in confirmed["baseline"]["changes"]
    )
    assert git(tmp_path, "status", "--porcelain").stdout.strip() == f"M {CENTRAL}"


@pytest.mark.parametrize(
    "invalid_base", ["target_moved", "nonancestor", "old_merge_base"]
)
def test_parallel_integration_rejects_invalid_baseline(
    tmp_path: Path, invalid_base: str
) -> None:
    base = repository(tmp_path)
    git(tmp_path, "checkout", "-b", "spec-left")
    (tmp_path / "left.py").write_bytes(b"left = 2\n")
    rebind(tmp_path, "left.py")
    target = commit(tmp_path, "target advances")
    git(tmp_path, "branch", "-f", "integration-target", target)
    git(tmp_path, "checkout", "-b", "spec-right", base)
    (tmp_path / "right.py").write_bytes(b"right = 2\n")
    rebind(tmp_path, "right.py")
    commit(tmp_path, "parallel spec")
    if invalid_base == "old_merge_base":
        git(tmp_path, "merge", "--no-ff", "integration-target", "-m", "merge target")
    chosen_base = target if invalid_base == "nonancestor" else base
    outcome = report(tmp_path, chosen_base)
    assert outcome["exit_code"] == 1
    expected = (
        "baseline_not_ancestor"
        if invalid_base == "nonancestor"
        else "baseline_target_mismatch"
    )
    assert expected in {row["reason"] for row in outcome["issues"]}
    assert "baseline" not in outcome


def test_old_history_is_read_only_and_different_even_for_same_tree_merge(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    base = repository(root)
    (root / "uv.lock").write_bytes(b"fixed synthetic lock identity\n")
    base = commit(root, "fixed lock identity for historical protocol")
    git(root, "checkout", "-b", "spec-left")
    git(root, "commit", "--allow-empty", "-m", "left identity")
    git(root, "branch", "-f", "integration-target", "HEAD")
    git(root, "checkout", "-b", "spec-right", base)
    git(root, "commit", "--allow-empty", "-m", "right identity")
    identity = capture_identity(root)
    # 沿用既有 synthetic-history 的 v1 协议场景,只供状态读者测试。
    # 不调用控制方/正式发布器,不写 verification-runs,不补造工程结论。
    history = tmp_path / "synthetic-history"
    history.mkdir()
    run_id = "0123456789abcdef0123456789abcdef"
    common = dict(
        format_version=1,
        run_id=run_id,
        code=identity.code,
        lockfile_sha256=identity.lockfile_sha256,
        worktree_sha256=identity.worktree_sha256,
    )
    documents = {
        ".json": dict(
            common,
            completed=True,
            overall="passed",
            checks=[
                dict(id=name, status="passed", reason="none", exit_code=0)
                for name in (
                    "lockfile",
                    "format",
                    "lint",
                    "types",
                    "tests",
                    "contracts",
                )
            ],
        ),
        ".a1.json": dict(common, status="passed"),
        ".pytest.json": dict(
            format_version=1,
            run_id=run_id,
            completed=True,
            exit_code=0,
            modules={
                "tests/synthetic_historical_case.py": dict(
                    collected=1,
                    passed=1,
                    failed=0,
                    skipped=0,
                    deselected=0,
                    incomplete=0,
                )
            },
        ),
    }
    for suffix, value in documents.items():
        (history / f"{run_id}{suffix}").write_text(json.dumps(value))
    digests = {
        suffix: hashlib.sha256((history / f"{run_id}{suffix}").read_bytes()).hexdigest()
        for suffix in documents
    }
    terminal = dict(
        common,
        exit_code=0,
        interrupted=False,
        materials_consistent=True,
        evidence_sha256=digests[".json"],
        pytest_receipt_sha256=digests[".pytest.json"],
        groups=[
            dict(
                suffix=".a1.json",
                format_version=1,
                required=True,
                sha256=digests[".a1.json"],
            )
        ],
    )
    (history / f"{run_id}.terminal.json").write_text(json.dumps(terminal))
    before = {path.name: path.read_bytes() for path in history.iterdir()}
    old = query_status(root, history, run_id)
    assert (old["status"], old["reason"], old["applicability"]) == (
        "passed",
        "verified",
        "same",
    )

    git(root, "merge", "--no-ff", "integration-target", "-m", "new merge identity")
    current = capture_identity(root)
    assert current.worktree_sha256 == identity.worktree_sha256
    assert current.code["commit"] != identity.code["commit"]
    after = query_status(root, history, run_id)
    assert (after["status"], after["reason"], after["applicability"]) == (
        "passed",
        "verified",
        "different",
    )
    assert {key: value for key, value in after.items() if key != "applicability"} == {
        key: value for key, value in old.items() if key != "applicability"
    }
    assert before == {path.name: path.read_bytes() for path in history.iterdir()}
