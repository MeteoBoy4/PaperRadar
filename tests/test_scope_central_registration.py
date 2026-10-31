"""中央登记经公开审计视图和真实 writer 接缝消费。"""

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import verification_scope_audit as audit
from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_registry import load_scopes
from tests.scope_document_support import prepared_repository, writer_conclusion
from tests.test_scope_baseline_audit import confirmations_for, git, repository


def registration(root: Path) -> tuple[tuple[str, str], ...]:
    (root / "scripts").mkdir(exist_ok=True)
    (root / "material.py").write_bytes(b"value = 1\n")
    sha = hashlib.sha256(b"value = 1\n").hexdigest()
    (root / "scripts/verification_scope_materials.py").write_text(
        f'SHARED_MATERIALS = {{"material.py": "{sha}"}}\n'
    )
    (root / "scripts/sample_scope.py").write_text(
        "from scripts.verification_scope_materials import SHARED_MATERIALS\n"
        'REQUIRED_TEST_MODULES = (("material.py", SHARED_MATERIALS["material.py"]),)\n'
    )
    (root / "scripts/sample_acceptance.py").write_text(
        "from scripts.sample_scope import REQUIRED_TEST_MODULES\n"
    )
    return (("A", "scripts/sample_acceptance.py"),)


def test_central_reference_expands_without_changing_public_tuple(
    tmp_path: Path,
) -> None:
    writers = registration(tmp_path)
    scopes = load_scopes(tmp_path, writers=writers)
    assert scopes[0].bindings["test"] == (
        (
            "material.py",
            "585c93666fcb046b7b264d3fa73202aa2a38254ae82a4b3ba19e873c2d5a9886",
        ),
    )
    assert audit_scopes(tmp_path, scopes)["exit_code"] == 0
    (tmp_path / "material.py").write_bytes(b"changed\n")
    report = audit_scopes(tmp_path, load_scopes(tmp_path, writers=writers))
    assert [(i["path"], i["reason"]) for i in report["files"]] == [
        ("material.py", "hash_drift")
    ]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("missing", "invalid_registration"),
        ("unknown", "invalid_registration"),
        ("invalid", "invalid_registration"),
        ("duplicate", "duplicate_count_key"),
        ("cycle", "invalid_registration"),
        ("dynamic", "unsupported_registration"),
        ("conflict", "invalid_registration"),
        ("repeated_member", "duplicate_path"),
        ("unknown_import", "invalid_registration"),
    ],
)
def test_invalid_central_registration_is_controlled(
    tmp_path: Path, change: str, reason: str
) -> None:
    writers = registration(tmp_path)
    central = tmp_path / "scripts/verification_scope_materials.py"
    scope = tmp_path / "scripts/sample_scope.py"
    if change == "missing":
        central.unlink()
    elif change == "unknown":
        scope.write_text(scope.read_text().replace('["material.py"]', '["unknown.py"]'))
    elif change == "invalid":
        central.write_text('SHARED_MATERIALS = {"../bad": "secret"}\n')
    elif change == "duplicate":
        central.write_text('SHARED_MATERIALS = {"p": "a", "p": "a"}\n')
    elif change == "cycle":
        central.write_text("SHARED_MATERIALS = SHARED_MATERIALS\n")
    elif change == "dynamic":
        central.write_text("SHARED_MATERIALS = dict()\n")
    elif change == "unknown_import":
        scope.write_text(
            scope.read_text()
            .replace("import SHARED_MATERIALS", "import SHARED_MATERIALS as OTHER")
            .replace("SHARED_MATERIALS[", "OTHER[")
        )
    else:
        original = scope.read_text().replace(
            "),)\n",
            f'), ("material.py", "{"0" * 64}"),)\n'
            if change == "conflict"
            else '), ("material.py", SHARED_MATERIALS["material.py"]),)\n',
        )
        scope.write_text(original)
    report = audit_scopes(tmp_path, load_scopes(tmp_path, writers=writers))
    assert report["exit_code"] == 1
    assert reason in [i["reason"] for i in report["issues"]]


@pytest.mark.parametrize("kind", ["source", "fixture", "mixed"])
def test_central_only_rebinding_is_mapped_and_requires_sensitive_confirmation(
    tmp_path: Path, kind: str
) -> None:
    repository(tmp_path)
    sha = hashlib.sha256((tmp_path / "sample.py").read_bytes()).hexdigest()
    central = tmp_path / "scripts/verification_scope_materials.py"
    central.write_text(f'SHARED_MATERIALS = {{"sample.py": "{sha}"}}\n')
    scope = tmp_path / "scripts/sample_scope.py"
    binding_kind = ("source" if kind == "mixed" else kind).upper()
    scope.write_text(
        "from scripts.verification_scope_materials import SHARED_MATERIALS\n"
        f"REQUIRED_{binding_kind}_MODULES = (\n"
        '    ("sample.py", SHARED_MATERIALS["sample.py"]),)\n'
        + scope.read_text().split("\n", 1)[1]
    )
    # fixture 使用 writer 的正式常量契约。
    if kind == "fixture":
        scope.write_text(scope.read_text().replace("FIXTURE_MODULES", "FIXTURE_FILES"))
        writer = tmp_path / "scripts/sample_acceptance.py"
        writer.write_text(writer.read_text().replace("SOURCE_MODULES", "FIXTURE_FILES"))
    writers: tuple[tuple[str, str], ...] = (("A", "scripts/sample_acceptance.py"),)
    if kind == "mixed":
        (tmp_path / "scripts/other_scope.py").write_text(
            scope.read_text().replace("SOURCE_MODULES", "FIXTURE_FILES")
        )
        (tmp_path / "scripts/other_acceptance.py").write_text(
            "from scripts.other_scope import (REQUIRED_TEST_MODULES, "
            "REQUIRED_FIXTURE_FILES, REQUIRED_TEST_CASE_COUNTS)\n"
        )
        writers += (("B", "scripts/other_acceptance.py"),)
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "central",
    )
    git(tmp_path, "branch", "-f", "target", "HEAD")
    base = git(tmp_path, "rev-parse", "HEAD")
    central.write_text(central.read_text().replace(sha, "0" * 64))
    report = audit.audit_baseline(
        tmp_path, base=base, integration_target="target", writers=writers
    )
    change = next(c for c in report["baseline"]["changes"] if c["path"] == "sample.py")
    assert change["sensitivity"] == ("mechanical" if kind == "source" else "sensitive")
    assert change["groups"] == (["A", "B"] if kind == "mixed" else ["A"])
    assert {r["expected_sha256"] for r in change["registrations"]} == {sha, "0" * 64}
    if kind != "source":
        assert "confirmation_required" in [i["reason"] for i in report["issues"]]
        confirmed = audit.audit_baseline(
            tmp_path,
            base=base,
            integration_target="target",
            writers=writers,
            confirmations=confirmations_for(report),
        )
        assert confirmed["issues"] == []
        assert confirmed["exit_code"] == 1  # 确认不能抹除真实 hash_drift。


def test_writer_checks_actual_centrally_referenced_material(tmp_path: Path) -> None:
    root = prepared_repository(
        tmp_path / "repo",
        reviewed=frozenset(
            {
                "scripts/verification_scope_audit.py",
                "scripts/verification_scope_registry.py",
                "scripts/verification_scope_baseline.py",
                "scripts/audit_verification_scope.py",
            }
        ),
        verified_groups=frozenset({"A8"}),
    )
    assert writer_conclusion(root, tmp_path / "before", 8)["status"] == "passed"
    material = root / "docs/verification/offline-evidence.md"
    material.write_bytes(material.read_bytes() + b"\n# changed actual bytes\n")
    result = writer_conclusion(root, tmp_path / "after", 8)
    assert result["status"] == "failed"
    assert "scope_drift" in [r["code"] for r in result["reasons"]]


def test_raw_scope_cannot_hash_the_central_registration(tmp_path: Path) -> None:
    writers = registration(tmp_path)
    scope = load_scopes(tmp_path, writers=writers)[0]
    relative = "scripts/verification_scope_materials.py"
    sha = hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
    injected = replace(scope, bindings={**scope.bindings, "source": ((relative, sha),)})
    report = audit_scopes(tmp_path, (injected,))
    assert "invalid_binding" in [i["reason"] for i in report["issues"]]


def test_literals_and_central_references_coexist_in_one_binding(tmp_path: Path) -> None:
    writers = registration(tmp_path)
    (tmp_path / "other.py").write_bytes(b"")
    path = tmp_path / "scripts/sample_scope.py"
    path.write_text(
        path.read_text().replace(
            "),)\n",
            '), ("other.py", '
            '"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),)\n',
        )
    )
    scopes = load_scopes(tmp_path, writers=writers)
    assert scopes[0].bindings["test"] == (
        (
            "material.py",
            "585c93666fcb046b7b264d3fa73202aa2a38254ae82a4b3ba19e873c2d5a9886",
        ),
        (
            "other.py",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
    )
    assert audit_scopes(tmp_path, scopes)["exit_code"] == 0


def test_invalid_central_structure_is_rejected_before_default_registry_import(
    tmp_path: Path,
) -> None:
    registration(tmp_path)
    (tmp_path / "scripts/verification_scope_materials.py").write_text(
        "SHARED_MATERIALS = unknown_dynamic_call()\n"
    )
    report = audit_scopes(tmp_path, load_scopes(tmp_path))
    assert "unsupported_registration" in [i["reason"] for i in report["issues"]]
