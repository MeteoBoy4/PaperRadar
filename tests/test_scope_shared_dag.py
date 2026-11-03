"""共享材料全迁移与无哈希 scope DAG 的公开接缝回归。"""

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import verification_scope_audit as audit
from scripts.verification_scope_registry import load_scopes
from tests.test_scope_central_registration import registration


def test_explicit_scope_references_preserve_graph_without_hashing(
    tmp_path: Path,
) -> None:
    writers = registration(tmp_path)
    scope = tmp_path / "scripts/sample_scope.py"
    scope.write_text(
        scope.read_text() + 'REQUIRED_SCOPE_REFERENCES = ("scripts/other_scope.py",)\n'
    )
    (tmp_path / "scripts/other_scope.py").write_text(
        scope.read_text().split("REQUIRED_SCOPE_REFERENCES")[0]
    )
    (tmp_path / "scripts/other_acceptance.py").write_text(
        "from scripts.other_scope import REQUIRED_TEST_MODULES\n"
    )
    writers += (("B", "scripts/other_acceptance.py"),)
    scopes = load_scopes(tmp_path, writers=writers)
    report = audit.audit_scopes(tmp_path, scopes)
    assert report["issues"] == []
    assert report["order"] == ["scripts/other_scope.py", "scripts/sample_scope.py"]
    assert report["downstream"]["scripts/other_scope.py"] == ["scripts/sample_scope.py"]
    assert {row["path"] for row in report["files"]} == {"material.py"}
    assert audit.audit_scopes(tmp_path, (scopes[0],))["exit_code"] == 0
    changed = replace(
        scopes[1],
        bindings={**scopes[1].bindings, "source": ((scopes[0].path, "0" * 64),)},
    )
    rejected = audit.audit_scopes(tmp_path, (scopes[0], changed))
    assert rejected["order"] == []
    assert "cycle" in [row["reason"] for row in rejected["issues"]]


def test_reference_change_is_sensitive_and_uses_old_and_new_graphs(
    tmp_path: Path,
) -> None:
    from tests.test_scope_baseline_audit import git, repository

    repository(tmp_path)
    for group in ("other", "third"):
        (tmp_path / f"scripts/{group}_scope.py").write_bytes(
            (tmp_path / "scripts/sample_scope.py").read_bytes()
        )
        (tmp_path / f"scripts/{group}_acceptance.py").write_text(
            f"from scripts.{group}_scope import (REQUIRED_SOURCE_MODULES, "
            "REQUIRED_TEST_MODULES, REQUIRED_TEST_CASE_COUNTS)\n"
        )
    scope = tmp_path / "scripts/sample_scope.py"
    scope.write_text(
        scope.read_text() + 'REQUIRED_SCOPE_REFERENCES = ("scripts/other_scope.py",)\n'
    )
    third = tmp_path / "scripts/third_scope.py"
    third.write_text(
        third.read_text() + 'REQUIRED_SCOPE_REFERENCES = ("scripts/sample_scope.py",)\n'
    )
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "refs",
    )
    base = git(tmp_path, "rev-parse", "HEAD")
    scope.write_text(scope.read_text().replace('("scripts/other_scope.py",)', "()"))
    third.write_text(
        third.read_text().replace(
            '("scripts/sample_scope.py",)', '("scripts/other_scope.py",)'
        )
    )
    writers = (
        ("A", "scripts/sample_acceptance.py"),
        ("B", "scripts/other_acceptance.py"),
        ("C", "scripts/third_acceptance.py"),
    )
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="main", writers=writers
    )
    change = next(
        row
        for row in report["baseline"]["changes"]
        if row["path"] == "scripts/sample_scope.py"
    )
    assert change["category"] == "registration"
    assert change["sensitivity"] == "sensitive"
    assert change["old_entry_sha256"] != change["new_entry_sha256"]
    assert change["affected_groups"] == ["A", "C"]
    assert [
        (row["group"], row["path"])
        for row in report["issues"]
        if row["reason"] == "confirmation_required"
    ] == [
        ("A", "scripts/sample_scope.py"),
        ("C", "scripts/sample_scope.py"),
        ("C", "scripts/third_scope.py"),
    ]


@pytest.mark.parametrize(
    ("references", "reason"),
    [
        ('["scripts/sample_scope.py"]', "invalid_registration"),
        ('("../private",)', "invalid_registration"),
        ('("scripts/unknown_scope.py",)', "invalid_registration"),
        ('("scripts/sample_scope.py",)', "self_reference"),
        ('("scripts/other_scope.py", "scripts/other_scope.py")', "duplicate_path"),
        ("dynamic_call()", "unsupported_registration"),
    ],
)
def test_invalid_explicit_references_are_controlled(
    tmp_path: Path, references: str, reason: str
) -> None:
    writers = registration(tmp_path)
    other = tmp_path / "scripts/other_scope.py"
    other.write_bytes((tmp_path / "scripts/sample_scope.py").read_bytes())
    (tmp_path / "scripts/other_acceptance.py").write_text(
        "from scripts.other_scope import REQUIRED_TEST_MODULES\n"
    )
    writers += (("B", "scripts/other_acceptance.py"),)
    scope = tmp_path / "scripts/sample_scope.py"
    scope.write_text(scope.read_text() + f"REQUIRED_SCOPE_REFERENCES = {references}\n")
    report = audit.audit_scopes(tmp_path, load_scopes(tmp_path, writers=writers))
    assert report["exit_code"] == 1
    assert reason in [row["reason"] for row in report["issues"]]
    assert audit.collection_targets(report) is None


def test_production_migration_keeps_exact_materials_counts_and_graph() -> None:
    import json

    root = Path(__file__).resolve().parents[1]
    ledger = json.loads(
        (root / "docs/verification/scope-shared-dag-delivery.json").read_bytes()
    )
    scopes = load_scopes(root)
    report = audit.audit_scopes(root, scopes)
    assert report["issues"] == []
    preparation = json.loads(
        (root / "docs/verification/scope-extensible-groups-delivery.json").read_bytes()
    )
    assert len(preparation["added_bindings"]) == 28
    # #139人工预期按已批准的10组kind独立枚举,不从当前scope推导期望。
    expectation_additions = [
        {
            "group": "A2-01",
            "kind": "source",
            "path": "tests/migration_expectations.py",
        },
        *(
            {
                "group": group,
                "kind": "fixture",
                "path": "tests/migration_expectations.py",
            }
            for group in ("完整 A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10")
        ),
    ]
    assert len(expectation_additions) == 10
    # #146已授权的新生产消费闭包,不从当前登记动态推导。
    abstract_version_additions = [
        {
            "group": "A10",
            "kind": "source",
            "path": "src/paper_radar/fixture_audit/abstract_versions.py",
        },
    ]
    additions = (
        abstract_version_additions
        + expectation_additions
        + preparation["added_bindings"]
    )
    assert len(report["files"]) == 1175 + len(additions)
    assert report["order"] == ledger["original_order"]
    assert report["downstream"] == ledger["original_downstream"]
    assert (
        sum(
            len(scope.references)
            for scope in scopes
            if isinstance(scope.references, tuple)
        )
        == 41
    )
    for scope in scopes:
        assert isinstance(scope.references, tuple)
        old = next(
            row for row in ledger["original_scopes"] if row["group"] == scope.group
        )
        removed = {
            row["path"]
            for row in ledger["scope_hash_edges"]
            if row["group"] == scope.group
        }
        migrated = next(
            row for row in ledger["migration_scopes"] if row["group"] == scope.group
        )
        # 原始SHA迁移证明保持在冻结快照; 后续显式候选重绑仍可核对当前集合。
        assert migrated["bindings"] == {
            kind: [entry for entry in entries if entry[0] not in removed]
            for kind, entries in old["bindings"].items()
        }
        assert {
            kind: [path for path, _ in entries]
            for kind, entries in scope.bindings.items()
            if isinstance(entries, tuple)
        } == {
            kind: [
                row["path"]
                for row in additions
                if row["group"] == scope.group and row["kind"] == kind
            ]
            + [entry[0] for entry in entries]
            for kind, entries in migrated["bindings"].items()
        }
        assert scope.counts == old["counts"]
        assert set(scope.references) == removed
    from scripts.verification_scope_materials import SHARED_MATERIALS

    owners: dict[str, set[str]] = {}
    for row in report["files"]:
        owners.setdefault(row["path"], set()).add(row["group"])
    issue_139_central_members = {"tests/migration_expectations.py"}
    assert issue_139_central_members <= set(SHARED_MATERIALS)
    assert len(SHARED_MATERIALS) == (
        252 + len(preparation["new_central_paths"]) + len(issue_139_central_members)
    )
    assert set(SHARED_MATERIALS) == {
        path for path, groups in owners.items() if len(groups) >= 2
    }
    assert not set(SHARED_MATERIALS) & {scope.path for scope in scopes}


@pytest.mark.parametrize(
    ("material", "direct", "sensitivity"),
    [
        (
            "src/paper_radar/cli.py",
            ["A10", "A2-01", "A3", "A4", "A6", "A9", "完整 A2"],
            "mechanical",
        ),
        ("tests/test_boundary_validation.py", ["A1", "完整 A2"], "sensitive"),
        ("scripts/a1_scope.py", ["A1"], "mechanical"),
    ],
)
def test_material_or_scope_change_never_rewrites_other_scopes(
    tmp_path: Path, material: str, direct: list[str], sensitivity: str
) -> None:
    import json
    import subprocess
    import sys

    from tests.scope_document_support import prepared_repository
    from tests.test_scope_baseline_audit import git

    root = prepared_repository(
        tmp_path / "repo",
        reviewed=frozenset(
            {
                "scripts/verification_scope_audit.py",
                "scripts/verification_scope_registry.py",
                "scripts/verification_scope_baseline.py",
                "scripts/audit_verification_scope.py",
                "scripts/a8_acceptance.py",
            }
        ),
        verified_groups=frozenset({"A8", "A9", "A10"}),
    )
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "reviewed candidate",
        "--allow-empty",
    )
    git(root, "branch", "target")
    base = git(root, "rev-parse", "HEAD")
    program = r"""
import hashlib, json
from pathlib import Path
from scripts.verification_scope_audit import audit_baseline
from scripts.verification_scope_registry import load_scopes
root = Path.cwd()
scopes = load_scopes(root)
before = {s.path: (root / s.path).read_bytes() for s in scopes}
material = MATERIAL_VALUE
path = root / material
path.write_bytes(path.read_bytes() + b'\n# independent controlled change\n')
central = root / 'scripts/verification_scope_materials.py'
old_central = central.read_text()
if material not in before:
    from scripts.verification_scope_materials import SHARED_MATERIALS
    old_sha = SHARED_MATERIALS[material]
    # Replace this exact key's SHA once; no scope SHA maintenance or propagation.
    import ast
    tree = ast.parse(old_central)
    mapping = tree.body[1].value
    target = next(value for key, value in zip(mapping.keys, mapping.values)
                  if key.value == material)
    lines = old_central.splitlines(keepends=True)
    offset = sum(len(line) for line in lines[:target.lineno - 1]) + target.col_offset
    end_line = sum(len(line) for line in lines[:target.end_lineno - 1])
    end = end_line + target.end_col_offset
    assert old_central[offset:end] == repr(old_sha).replace("'", '"')
    new_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    central.write_text(old_central[:offset] + '"' + new_sha + '"' + old_central[end:])
report = audit_baseline(root, base=BASE, integration_target='target')
assert report['baseline']['baseline_issues'] == []
after = {s.path: (root / s.path).read_bytes() for s in scopes
         if s.path != material}
assert after == {p: value for p, value in before.items() if p != material}
assert not [row for row in report['files'] if row['reason'] != 'ok']
print(json.dumps(report))
"""
    program = program.replace("MATERIAL_VALUE", repr(material)).replace(
        "BASE", repr(base)
    )
    result = subprocess.run(
        (sys.executable, "-B", "-c", program), cwd=root, capture_output=True, check=True
    )
    report = json.loads(result.stdout)
    change = next(
        row for row in report["baseline"]["changes"] if row["path"] == material
    )
    assert change["groups"] == direct
    assert change["sensitivity"] == sensitivity
    assert change["affected_groups"] == (
        ["A1", "A10", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "完整 A2"]
        if material != "src/paper_radar/cli.py"
        else ["A10", "A2-01", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "完整 A2"]
    )
    required = [
        row for row in report["issues"] if row["reason"] == "confirmation_required"
    ]
    if sensitivity == "sensitive":
        assert {row["group"] for row in required if row["path"] == material} == set(
            change["affected_groups"]
        )
    else:
        assert required == []


@pytest.mark.parametrize(
    "change", ["unlisted_scope", "non_scope_reference", "invalid_graph"]
)
def test_writer_rejects_unverified_scope_metadata_pointer(
    tmp_path: Path, change: str
) -> None:
    import hashlib

    from tests.scope_document_support import prepared_repository, writer_conclusion

    root = prepared_repository(
        tmp_path / "repo",
        reviewed=frozenset(
            {
                "scripts/verification_scope_audit.py",
                "scripts/verification_scope_registry.py",
                "scripts/verification_scope_baseline.py",
                "scripts/audit_verification_scope.py",
                "scripts/a8_acceptance.py",
            }
        ),
        verified_groups=frozenset({"A8"}),
    )
    assert writer_conclusion(root, tmp_path / "before", 8)["status"] == "passed"
    scope = root / "scripts/a8_scope.py"
    if change == "invalid_graph":
        scope.write_text(
            scope.read_text().replace(
                '"scripts/a7_scope.py",', '"scripts/a8_scope.py",'
            )
        )
    else:
        fixture = root / "tests/fixtures/a8_capabilities.json"
        old_sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
        pointer = (
            "scripts/a2_scope.py"
            if change == "unlisted_scope"
            else "src/paper_radar/cli.py"
        )
        fixture.write_text(fixture.read_text().replace("scripts/a7_scope.py", pointer))
        new_sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
        scope.write_text(scope.read_text().replace(old_sha, new_sha))
        if change == "non_scope_reference":
            scope.write_text(
                scope.read_text().replace('"scripts/a7_scope.py",', f'"{pointer}",')
            )
    result = writer_conclusion(root, tmp_path / "after", 8)
    assert result["status"] == "failed"
    assert "scope_drift" in [reason["code"] for reason in result["reasons"]]


def test_baseline_keeps_invalid_reference_input_controlled(tmp_path: Path) -> None:
    from tests.test_scope_baseline_audit import repository

    base = repository(tmp_path)
    scope = tmp_path / "scripts/sample_scope.py"
    scope.write_text(scope.read_text() + "REQUIRED_SCOPE_REFERENCES = None\n")
    report = audit.audit_baseline(
        tmp_path,
        base=base,
        integration_target="main",
        writers=(("A", "scripts/sample_acceptance.py"),),
    )
    assert report["exit_code"] == 1
    assert "invalid_registration" in [row["reason"] for row in report["issues"]]


def test_writer_scope_pointer_does_not_depend_on_unrelated_group_structure(
    tmp_path: Path,
) -> None:
    from tests.scope_document_support import prepared_repository, writer_conclusion

    root = prepared_repository(
        tmp_path / "repo",
        reviewed=frozenset(
            {
                "scripts/verification_scope_audit.py",
                "scripts/verification_scope_registry.py",
                "scripts/verification_scope_baseline.py",
                "scripts/audit_verification_scope.py",
                "scripts/a8_acceptance.py",
            }
        ),
        verified_groups=frozenset({"A8"}),
    )
    writer = root / "scripts/a9_acceptance.py"
    writer.write_text(
        writer.read_text() + "\nfrom scripts.a9_scope import UNRELATED_METADATA\n"
    )
    scope = root / "scripts/a9_scope.py"
    scope.write_text(
        scope.read_text()
        + '\nUNRELATED_METADATA = "runtime valid, static unsupported"\n'
    )
    result = writer_conclusion(root, tmp_path / "run", 8)
    assert result["status"] == "passed", result["reasons"]
    import json
    import subprocess
    import sys

    completed = subprocess.run(
        (sys.executable, "-B", "-m", "scripts.audit_verification_scope", "--json"),
        cwd=root,
        check=False,
        capture_output=True,
    )
    report = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert any(
        row["group"] == "A9" and row["reason"] == "unsupported_scope_constant"
        for row in report["issues"]
    )


@pytest.mark.parametrize(
    ("target", "link_kind", "reason"),
    [
        ("sample_scope.py", "outside", "registration_unavailable"),
        ("sample_scope.py", "loop", "registration_unavailable"),
        ("sample_acceptance.py", "outside", "registration_unavailable"),
        ("verification_scope_materials.py", "outside", "invalid_registration"),
        ("verification_scope_materials.py", "loop", "invalid_registration"),
    ],
)
def test_registration_ast_rejects_unprotected_symlink_bytes(
    tmp_path: Path, target: str, link_kind: str, reason: str
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    writers = registration(root)
    path = root / "scripts" / target
    external = tmp_path / "external.py"
    external.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(external if link_kind == "outside" else path.name)
    report = audit.audit_scopes(root, load_scopes(root, writers=writers))
    assert report["exit_code"] == 1
    assert reason in [row["reason"] for row in report["issues"]]
    assert report["files"] == []
    assert audit.collection_targets(report) is None


@pytest.mark.parametrize(
    "target", ["sample_scope.py", "verification_scope_materials.py"]
)
def test_registration_metadata_cannot_follow_ignored_in_tree_target(
    tmp_path: Path, target: str
) -> None:
    writers = registration(tmp_path)
    (tmp_path / ".gitignore").write_text(".scratch/\n")
    ignored = tmp_path / ".scratch"
    ignored.mkdir()
    path = tmp_path / "scripts" / target
    redirected = ignored / "metadata.py"
    redirected.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(redirected)
    report = audit.audit_scopes(tmp_path, load_scopes(tmp_path, writers=writers))
    assert report["exit_code"] == 1
    assert (
        "registration_unavailable"
        if target == "sample_scope.py"
        else "invalid_registration"
    ) in [row["reason"] for row in report["issues"]]
    assert report["files"] == []
