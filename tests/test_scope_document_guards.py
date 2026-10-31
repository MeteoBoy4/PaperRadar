"""活文档防回绑与固定材料边界, 使用公开审计和仓库副本。"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.verification_scope_audit import Scope, audit_scopes, collection_targets

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_audit_rejects_rebinding_a_classified_live_document(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_bytes(b"")
    scope = Scope(
        "new group", "new_scope.py", {"fixture": (("README.md", EMPTY_SHA256),)}
    )
    report = audit_scopes(tmp_path, (scope,))
    assert report["exit_code"] == 1
    assert [(row["path"], row["reason"]) for row in report["files"]] == [
        ("README.md", "live_document_binding")
    ]
    assert report["affected_groups"] == ["new group"]
    assert collection_targets(report) is None


def prepared_repository(target: Path) -> Path:
    """仅在隔离副本按已审阅路径准备候选, 生产 scope 保留预计漂移。"""
    from tests.a2_full_support import repository_copy

    root = repository_copy(target)
    program = r"""
import hashlib
import re
from pathlib import Path
from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_registry import load_scopes
root = Path.cwd()
report = audit_scopes(root, load_scopes(root))
assert not report['issues'], report['issues']
reviewed = {
    'scripts/a9_acceptance.py',
    'scripts/a10_coverage.py',
    'scripts/verification_scope_audit.py',
    'tests/fixtures/a9_coverage.json',
    'tests/fixtures/a10_coverage.json',
    'tests/test_a9_scope.py',
    'tests/test_a9_integrity.py',
    'tests/test_a10_integrity.py',
    *report['order'],
}
unexpected = [row for row in report['files']
              if row['reason'] != 'ok' and row['path'] not in reviewed]
assert not unexpected, unexpected
pattern = re.compile(r'(\(\s*"([^"]+)",\s*")([0-9a-f]{64})(")')
def replacement(match):
    relative = match[2]
    if relative not in reviewed:
        return match[0]
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    return match[1] + digest + match[4]
for relative in report['order']:
    path = root / relative
    path.write_text(pattern.sub(replacement, path.read_text()))
report = audit_scopes(root, load_scopes(root))
assert report['exit_code'] == 0, report
"""
    subprocess.run((sys.executable, "-B", "-c", program), cwd=root, check=True)
    return root


def audit_repository(root: Path) -> dict[str, Any]:
    result = subprocess.run(
        (sys.executable, "-B", "-m", "scripts.audit_verification_scope", "--json"),
        cwd=root,
        capture_output=True,
        check=False,
    )
    report: dict[str, Any] = json.loads(result.stdout)
    assert result.returncode == report["exit_code"]
    return report


def writer_conclusion(root: Path, output: Path, group: int) -> dict[str, Any]:
    output.mkdir()
    program = f"""
import json
from pathlib import Path
from tests.a{group}_acceptance_support import conclude, same_a{group}_run
root = Path.cwd()
output = Path({str(output)!r})
_, result = conclude(output, same_a{group}_run(output, root=root), root=root)
print(json.dumps(result))
"""
    result = subprocess.run(
        (sys.executable, "-B", "-c", program),
        cwd=root,
        capture_output=True,
        check=True,
    )
    value: dict[str, Any] = json.loads(result.stdout)
    return value


@pytest.mark.parametrize(
    "category", ["specification", "summary", "glossary", "contracts"]
)
def test_live_edits_keep_audit_and_all_three_writers_passed(
    tmp_path: Path, category: str
) -> None:
    root = prepared_repository(tmp_path / "repo")
    inventory = json.loads(
        (root / "docs/verification/scope-material-inventory.json").read_bytes()
    )
    contracts = sorted(
        {
            row["path"]
            for row in inventory["bindings"]
            if row["disposition"] == "remove_after_migration"
            and row["path"].startswith("docs/contracts/")
        }
    )
    assert len(contracts) == 9
    documents = {
        "specification": ["intent/draft.md"],
        "summary": ["README.md"],
        "glossary": ["GLOSSARY.md"],
        "contracts": contracts,
    }[category]
    scopes = {
        path: (root / path).read_bytes() for path in audit_repository(root)["order"]
    }
    for relative in documents:
        path = root / relative
        path.write_bytes(path.read_bytes() + b"\nCurrent documentation may evolve.\n")
    report = audit_repository(root)
    assert report["exit_code"] == 0
    assert report["issues"] == report["affected_groups"] == []
    assert scopes == {path: (root / path).read_bytes() for path in scopes}
    for group in (8, 9, 10):
        result = writer_conclusion(root, tmp_path / f"writer-{group}", group)
        assert result["status"] == "passed", result["reasons"]
        assert result[f"a{group}_verified"] is True
        assert all(reason["code"] != "scope_drift" for reason in result["reasons"])


@pytest.mark.parametrize(
    "relative",
    [
        "docs/verification/contracts-fixture-audit-history.md",
        "docs/verification/a10-requirements.md",
        "tests/fixtures/a10_coverage.json",
        "src/paper_radar/cli.py",
        "tests/test_a10_scope.py",
        "fixtures/a10/historical-v1.json",
        "uv.lock",
    ],
)
def test_frozen_material_damage_still_fails_audit_and_writer(
    tmp_path: Path, relative: str
) -> None:
    root = prepared_repository(tmp_path / "repo")
    path = root / relative
    path.write_bytes(path.read_bytes() + b"\n")
    report = audit_repository(root)
    assert report["exit_code"] == 1
    assert any(
        row["path"] == relative and row["reason"] == "hash_drift"
        for row in report["files"]
    )
    assert "A10" in report["affected_groups"]
    result = writer_conclusion(root, tmp_path / "writer", 10)
    assert result["status"] == "failed"
    assert any(reason["code"] == "scope_drift" for reason in result["reasons"])


def test_live_edit_preserves_history_but_changes_its_applicability(
    tmp_path: Path,
) -> None:
    from scripts.verification_identity import capture_identity
    from scripts.verification_status import query_status

    root = prepared_repository(tmp_path / "repo")
    history = tmp_path / "synthetic-history"
    history.mkdir()
    run_id = "0123456789abcdef0123456789abcdef"
    identity = capture_identity(root)
    common = dict(
        format_version=1,
        run_id=run_id,
        code=identity.code,
        lockfile_sha256=identity.lockfile_sha256,
        worktree_sha256=identity.worktree_sha256,
    )
    # 临时协议材料只测试状态读者, 不调用正式入口/发布器, 不写 verification-runs。
    evidence = dict(
        common,
        completed=True,
        overall="passed",
        checks=[
            dict(id=name, status="passed", reason="none", exit_code=0)
            for name in ("lockfile", "format", "lint", "types", "tests", "contracts")
        ],
    )
    receipt = dict(
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
    )
    group = dict(common, status="passed")
    for suffix, value in (
        (".json", evidence),
        (".pytest.json", receipt),
        (".a1.json", group),
    ):
        (history / f"{run_id}{suffix}").write_text(json.dumps(value))

    def digest(suffix: str) -> str:
        return hashlib.sha256((history / f"{run_id}{suffix}").read_bytes()).hexdigest()

    terminal = dict(
        common,
        exit_code=0,
        interrupted=False,
        materials_consistent=True,
        evidence_sha256=digest(".json"),
        pytest_receipt_sha256=digest(".pytest.json"),
        groups=[
            dict(
                suffix=".a1.json",
                format_version=1,
                required=True,
                sha256=digest(".a1.json"),
            )
        ],
    )
    (history / f"{run_id}.terminal.json").write_text(json.dumps(terminal))
    before = {path.name: path.read_bytes() for path in history.iterdir()}
    first = query_status(root, history, run_id)
    assert (first["status"], first["reason"], first["applicability"]) == (
        "passed",
        "verified",
        "same",
    )
    path = root / "README.md"
    path.write_bytes(path.read_bytes() + b"\nUpdated live summary.\n")
    assert audit_repository(root)["exit_code"] == 0
    after = query_status(root, history, run_id)
    assert (after["status"], after["reason"], after["applicability"]) == (
        "passed",
        "verified",
        "different",
    )
    assert {key: value for key, value in after.items() if key != "applicability"} == {
        key: value for key, value in first.items() if key != "applicability"
    }
    assert before == {path.name: path.read_bytes() for path in history.iterdir()}


@pytest.mark.parametrize("kind", ["source", "test", "fixture"])
@pytest.mark.parametrize("document", ["intent/draft.md", "docs/contracts/pi-rpc.md"])
def test_every_binding_kind_rejects_classified_paths(
    tmp_path: Path, kind: str, document: str
) -> None:
    target = tmp_path / document
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"")
    report = audit_scopes(
        tmp_path, (Scope("synthetic", "scope.py", {kind: ((document, EMPTY_SHA256),)}),)
    )
    assert report["files"][0]["reason"] == "live_document_binding"
    assert report["exit_code"] == 1


def test_unknown_markdown_is_still_fixed_material(tmp_path: Path) -> None:
    target = tmp_path / "docs/contracts/unknown.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"")
    scope = Scope(
        "new",
        "scope.py",
        {"fixture": ((target.relative_to(tmp_path).as_posix(), EMPTY_SHA256),)},
    )
    assert audit_scopes(tmp_path, (scope,))["exit_code"] == 0
    target.write_text("changed")
    assert audit_scopes(tmp_path, (scope,))["files"][0]["reason"] == "hash_drift"


def test_python_audit_consumes_repository_copy_classification(tmp_path: Path) -> None:
    from tests.a2_full_support import repository_copy

    root = repository_copy(tmp_path / "repo")
    relative = "docs/contracts/explicitly-reviewed-new.md"
    target = root / relative
    target.write_bytes(b"")
    scope = Scope("new", "scope.py", {"source": ((relative, EMPTY_SHA256),)})
    assert audit_scopes(root, (scope,))["exit_code"] == 0
    path = root / "docs/verification/scope-material-inventory.json"
    value = json.loads(path.read_bytes())
    value["classification_rules"]["live_documents"]["exact_paths"].append(relative)
    path.write_text(json.dumps(value))
    report = audit_scopes(root, (scope,))
    assert report["exit_code"] == 1
    assert report["files"][0]["reason"] == "live_document_binding"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "missing_and_auditor",
        "invalid_json",
        "invalid_path",
        "duplicate",
        "wrong_type",
    ],
)
def test_repository_classification_damage_is_controlled(
    tmp_path: Path, fault: str
) -> None:
    from tests.a2_full_support import repository_copy

    root = repository_copy(tmp_path / "repo")
    path = root / "docs/verification/scope-material-inventory.json"
    value = json.loads(path.read_bytes())
    if fault in {"missing", "missing_and_auditor"}:
        path.unlink()
        if fault == "missing_and_auditor":
            (root / "scripts/verification_scope_audit.py").unlink()
    elif fault == "invalid_json":
        path.write_text("SECRET not JSON")
    else:
        value["classification_rules"]["live_documents"]["exact_paths"] = {
            "invalid_path": ["../SECRET"],
            "duplicate": ["README.md", "README.md"],
            "wrong_type": [False],
        }[fault]
        path.write_text(json.dumps(value))
    scope = Scope("new", "scope.py", {"source": (("README.md", EMPTY_SHA256),)})
    report = audit_scopes(root, (scope,))
    assert report["exit_code"] == 1
    assert report["issues"] == [
        {
            "group": "registry",
            "path": "docs/verification/scope-material-inventory.json",
            "reason": "classification_unavailable"
            if fault in {"missing", "missing_and_auditor"}
            else "invalid_classification",
        }
    ]
    assert "SECRET" not in str(report)
    assert collection_targets(report) is None
