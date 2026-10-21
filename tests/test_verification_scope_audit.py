"""固定范围审计的公开接口; 只消费显式合成登记。"""

from pathlib import Path

import pytest

from scripts.verification_scope_audit import (
    AuditReason,
    Scope,
    audit_scopes,
    collection_targets,
    merge_collection,
)

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_audit_reports_drift_and_missing_files_without_writing(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_bytes(b"")
    (tmp_path / "vector.json").write_bytes(b"changed")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    scope = Scope(
        "old slice",
        "scripts/old_scope.py",
        {
            "source": (("source.py", EMPTY_SHA256),),
            "fixture": (("vector.json", EMPTY_SHA256),),
            "test": (("tests/test_missing.py", EMPTY_SHA256),),
        },
    )

    report = audit_scopes(tmp_path, (scope,))

    assert report["exit_code"] == 1
    assert [(r["kind"], r["reason"]) for r in report["files"]] == [
        ("source", "ok"),
        ("fixture", "hash_drift"),
        ("test", "missing_file"),
    ]
    assert report["affected_groups"] == ["old slice"]
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize(
    "bindings,counts,reason",
    [
        ({"test": ()}, None, "empty_binding"),
        ({"test": None}, None, "invalid_binding"),
        ({"test": (("a.py", EMPTY_SHA256),) * 2}, None, "duplicate_path"),
        ({"test": (("a.py", EMPTY_SHA256),)}, {"b.py": 1}, "count_keys_mismatch"),
        *[
            ({"test": (("a.py", EMPTY_SHA256),)}, {"a.py": n}, "invalid_count")
            for n in (True, False, 0, -1, 1.5, "2", None)
        ],
        ({"test": (("a.py", EMPTY_SHA256),)}, [], "invalid_counts"),
        ({"test": (("a.py", "secret-not-a-hash"),)}, None, "invalid_binding"),
        ({"test": (("../secret", EMPTY_SHA256),)}, None, "invalid_binding"),
    ],
)
def test_invalid_registration_cannot_pass(
    tmp_path: Path,
    bindings: dict[str, object],
    counts: object,
    reason: str,
) -> None:
    (tmp_path / "a.py").write_bytes(b"")
    report = audit_scopes(tmp_path, (Scope("A", "a_scope.py", bindings, counts),))
    assert report["exit_code"] == 1
    assert reason in [r["reason"] for r in report["issues"]]
    assert "secret-not-a-hash" not in str(report)


def test_cascade_order_and_rebinding(tmp_path: Path) -> None:
    for path in ("shared.py", "a_scope.py", "b_scope.py", "c_scope.py"):
        (tmp_path / path).write_bytes(b"")
    scopes: tuple[Scope, ...] = (
        Scope("C", "c_scope.py", {"source": (("b_scope.py", EMPTY_SHA256),)}),
        Scope("B", "b_scope.py", {"source": (("a_scope.py", EMPTY_SHA256),)}),
        Scope("A", "a_scope.py", {"source": (("shared.py", EMPTY_SHA256),)}),
    )
    assert audit_scopes(tmp_path, scopes)["exit_code"] == 0
    (tmp_path / "shared.py").write_bytes(b"changed")
    report = audit_scopes(tmp_path, scopes)
    assert report["order"] == ["a_scope.py", "b_scope.py", "c_scope.py"]
    assert report["affected_groups"] == ["A", "B", "C"]
    assert report["downstream"]["a_scope.py"] == ["b_scope.py", "c_scope.py"]
    # 人工逐步登记候选哈希; 修改某个 scope 后下游也需重新核对。
    for index in (2, 1, 0):
        scope = scopes[index]
        path = {"A": "shared.py", "B": "a_scope.py", "C": "b_scope.py"}[scope.group]
        digest = next(
            f["actual_sha256"] for f in report["files"] if f["group"] == scope.group
        )
        replacement = Scope(scope.group, scope.path, {"source": ((path, digest),)})
        scopes = (*scopes[:index], replacement, *scopes[index + 1 :])
        (tmp_path / scope.path).write_text(str(index))
        report = audit_scopes(tmp_path, scopes)
    assert report["exit_code"] == 0


@pytest.mark.parametrize("self_reference", [True, False])
def test_cycles_are_rejected(tmp_path: Path, self_reference: bool) -> None:
    (tmp_path / "a_scope.py").write_bytes(b"")
    (tmp_path / "b_scope.py").write_bytes(b"")
    scopes = (
        Scope(
            "A",
            "a_scope.py",
            {
                "source": (
                    ("a_scope.py" if self_reference else "b_scope.py", EMPTY_SHA256),
                )
            },
        ),
        Scope("B", "b_scope.py", {"source": (("a_scope.py", EMPTY_SHA256),)}),
    )
    report = audit_scopes(tmp_path, scopes)
    assert report["exit_code"] == 1
    assert report["order"] == []
    assert ("self_reference" if self_reference else "cycle") in [
        r["reason"] for r in report["issues"]
    ]


def test_conflicting_counts_across_groups_cannot_be_silently_overwritten(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_bytes(b"")
    bindings = {"test": (("a.py", EMPTY_SHA256),)}
    report = audit_scopes(
        tmp_path,
        (
            Scope("A", "a_scope.py", bindings, {"a.py": 1}),
            Scope("B", "b_scope.py", bindings, {"a.py": 2}),
        ),
    )
    assert report["exit_code"] == 1
    assert "conflicting_counts" in [r["reason"] for r in report["issues"]]


@pytest.mark.parametrize(
    "reason",
    [
        AuditReason.COLLECTION_UNAVAILABLE,
        AuditReason.COLLECTION_TIMEOUT,
        AuditReason.COLLECTION_FAILED,
        AuditReason.INVALID_COUNTS,
        AuditReason.COLLECTION_SKIPPED,
        AuditReason.COLLECTION_DESELECTED,
    ],
)
def test_incomplete_collection_preserves_existing_affected_groups(
    tmp_path: Path,
    reason: AuditReason,
) -> None:
    (tmp_path / "a.py").write_bytes(b"")
    (tmp_path / "b.py").write_bytes(b"changed")
    scopes = (
        Scope("A", "a_scope.py", {"test": (("a.py", EMPTY_SHA256),)}, {"a.py": 1}),
        Scope("B", "b_scope.py", {"source": (("b.py", EMPTY_SHA256),)}),
    )
    report = audit_scopes(tmp_path, scopes)
    merged = merge_collection(
        report,
        scopes,
        dict(
            reason=reason,
            execution="not_run",
            modules={},
        ),
    )
    assert merged["exit_code"] == 1
    assert merged["affected_groups"] == ["B"]
    assert report["collection"]["reason"] == "not_requested"


def test_count_mismatch_adds_downstream_without_losing_previous_drift(
    tmp_path: Path,
) -> None:
    for name in ("a.py", "a_scope.py", "unrelated.py"):
        (tmp_path / name).write_bytes(b"")
    scopes = (
        Scope("A", "a_scope.py", {"test": (("a.py", EMPTY_SHA256),)}, {"a.py": 1}),
        Scope("B", "b_scope.py", {"source": (("a_scope.py", EMPTY_SHA256),)}),
        Scope("C", "c_scope.py", {"source": (("unrelated.py", EMPTY_SHA256),)}),
    )
    (tmp_path / "unrelated.py").write_bytes(b"changed")
    report = audit_scopes(tmp_path, scopes)
    assert report["affected_groups"] == ["C"]
    merged = merge_collection(
        report,
        scopes,
        dict(
            reason=AuditReason.COUNT_MISMATCH,
            execution="not_run",
            modules={"a.py": 2},
        ),
    )
    assert set(merged["affected_groups"]) == {"A", "B", "C"}
    assert report["affected_groups"] == ["C"]


@pytest.mark.parametrize("kind", ["test", "source"])
@pytest.mark.parametrize("outside_link", [False, True])
def test_missing_or_outside_material_cannot_enter_collection(
    tmp_path: Path,
    kind: str,
    outside_link: bool,
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "valid_test.py").write_bytes(b"")
    if outside_link:
        external = tmp_path / "outside.py"
        external.write_bytes(b"")
        (root / "unavailable.py").symlink_to(external)
    bindings: dict[str, object] = {"test": (("valid_test.py", EMPTY_SHA256),)}
    bindings[kind] = (("unavailable.py", EMPTY_SHA256),)
    report = audit_scopes(root, (Scope("A", "a_scope.py", bindings),))
    assert report["exit_code"] == 1
    assert collection_targets(report) is None
