"""显式 Git 基线与逐变化确认;临时副本仅用于读取历史登记。"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from scripts.verification_scope_audit import (
    CLASSIFICATION_PATH,
    AuditReason,
    AuditReport,
    BaselineCategory,
    BaselineChange,
    BaselineOrigin,
    BaselineRegistration,
    BaselineResult,
    valid_path,
)


class BaselineError(ValueError):
    def __init__(self, reason: AuditReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


def _git(root: Path, *arguments: str, input_data: bytes | None = None) -> bytes:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            input=input_data,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        raise BaselineError(AuditReason.BASELINE_UNAVAILABLE) from None


def _commit(root: Path, revision: str) -> str:
    return (
        _git(root, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}")
        .decode()
        .strip()
    )


def _identity(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in sorted(
        set(
            _git(
                root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
            ).split(b"\0")
        )
        - {b""}
    ):
        path = root / os.fsdecode(relative)
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        if not os.path.lexists(path):
            digest.update(b"missing\0")
            continue
        digest.update(stat.S_IMODE(path.lstat().st_mode).to_bytes(2, "big"))
        if path.is_symlink():
            digest.update(b"link\0" + os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(b"file\0" + hashlib.sha256(path.read_bytes()).digest())
        else:
            digest.update(b"other\0")
    return digest.hexdigest()


def _report(
    root: Path, writers: tuple[tuple[str, str], ...] | None
) -> tuple[AuditReport, dict[str, str], dict[str, object]]:
    # 冷进程从被检查树导入 registry,避免宿主模块缓存污染历史组清单。
    program = """
import json, sys
from pathlib import Path
sys.path[:0] = [sys.argv[1], str(Path(sys.argv[1]) / "src")]
from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_registry import load_scopes
writers = json.loads(sys.argv[2])
scopes = load_scopes(Path(sys.argv[1]), writers=writers)
print(json.dumps({'report': audit_scopes(Path(sys.argv[1]), scopes),
                  'paths': {s.group: s.path for s in scopes},
                  'references': {s.group: getattr(s, 'references', ())
                                 for s in scopes}}))
"""
    try:
        output = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                program,
                str(root.resolve()),
                json.dumps(writers),
            ],
            cwd=root,
            capture_output=True,
            check=True,
            timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        value = json.loads(output.stdout)
        return value["report"], value["paths"], value["references"]
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise BaselineError(AuditReason.BASELINE_REGISTRATION_UNAVAILABLE) from None


def _extract_tree(root: Path, commit: str, target: Path) -> None:
    """直接读取 blob, 不让 export-subst/export-ignore 改写历史材料。"""
    entries = []
    for record in _git(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, kind, oid = header.split()
        relative_path = os.fsdecode(raw_path)
        if kind != b"blob" or not valid_path(relative_path):
            raise BaselineError(AuditReason.BASELINE_UNAVAILABLE)
        entries.append((mode, oid, relative_path))
    content = io.BytesIO(
        _git(
            root,
            "cat-file",
            "--batch",
            input_data=b"".join(oid + b"\n" for _, oid, _ in entries),
        )
    )
    for mode, oid, relative in entries:
        actual_oid, kind, raw_size = content.readline().strip().split()
        size = int(raw_size)
        data = content.read(size)
        if (
            actual_oid != oid
            or kind != b"blob"
            or len(data) != size
            or content.read(1) != b"\n"
        ):
            raise BaselineError(AuditReason.BASELINE_UNAVAILABLE)
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == b"120000":
            link = os.fsdecode(data)
            if not (path.parent / link).resolve().is_relative_to(target):
                raise BaselineError(AuditReason.BASELINE_UNAVAILABLE)
            path.symlink_to(link)
        elif mode in (b"100644", b"100755"):
            path.write_bytes(data)
            path.chmod(0o755 if mode == b"100755" else 0o644)
        else:
            raise BaselineError(AuditReason.BASELINE_UNAVAILABLE)


def _sha(root: Path, path: str) -> str | None:
    try:
        file = root / path
        if not file.resolve().is_relative_to(root.resolve()):
            return None
        return hashlib.sha256(file.read_bytes()).hexdigest()
    except OSError:
        return None


def _sensitive_constants(root: Path, path: str) -> dict[str, str]:
    try:
        tree = ast.parse((root / path).read_bytes())
    except (OSError, ValueError, SyntaxError):
        return {}
    words = (
        "FORMAT",
        "COUNT",
        "REQUIRED_TEST",
        "FIXTURE",
        "NEGATIVE",
        "REQUIREMENT",
        "COVERAGE",
        "CAPABILIT",
        "NOT_ASSESSED",
        "NOT_IMPLEMENTED",
        "REQUIRED_CHECK",
        "DEPENDENC",
        "MIGRATION",
        "SCOPE",
        "ISSUE",
    )
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and any(
                    word in target.id for word in words
                ):
                    result[target.id] = ast.dump(node, include_attributes=False)
    return result


def _category(
    old: Path, root: Path, path: str, kinds: set[str], scope_paths: set[str]
) -> BaselineCategory:
    if path == CLASSIFICATION_PATH:
        return "classification"
    if path in scope_paths:
        return (
            "registration"
            if _sensitive_constants(old, path) != _sensitive_constants(root, path)
            else "source_support"
        )
    if "test" in kinds or path.startswith("tests/test_"):
        return "test"
    if "fixture" in kinds or path.startswith("fixtures/"):
        return "fixture"
    if (
        path.startswith(("docs/", "contracts/", "intent/"))
        or (path.startswith("tests/") and not path.endswith(".py"))
        or any(
            word in path.lower()
            for word in ("coverage", "requirements", "history", "ledger", "negative")
        )
    ):
        return "evidence"
    if path.endswith(".py") and _sensitive_constants(old, path) != _sensitive_constants(
        root, path
    ):
        return "format_or_criteria"
    return "source_support"


def _affected(report: AuditReport, paths: dict[str, str], groups: set[str]) -> set[str]:
    affected_paths = {paths[g] for g in groups if g in paths}
    for path in tuple(affected_paths):
        affected_paths.update(report["downstream"].get(path, []))
    return groups | {g for g, path in paths.items() if path in affected_paths}


def analyze_baseline(
    root: Path,
    *,
    base: str,
    integration_target: str,
    confirmations: object = (),
    writers: tuple[tuple[str, str], ...] | None = None,
) -> AuditReport:
    from scripts.verification_scope_audit import audit_scopes

    report = audit_scopes(root, ())
    try:
        if (
            not isinstance(base, str)
            or not base
            or not isinstance(integration_target, str)
            or not integration_target
        ):
            raise BaselineError(AuditReason.INVALID_BASELINE)
        actual_base = _commit(root, base)
        head = _commit(root, "HEAD")
        target_ref = (
            integration_target
            if integration_target.startswith("refs/heads/")
            else "refs/heads/" + integration_target
        )
        target = _commit(root, target_ref)
        if actual_base != target:
            raise BaselineError(AuditReason.BASELINE_TARGET_MISMATCH)
        try:
            _git(root, "merge-base", "--is-ancestor", actual_base, head)
        except BaselineError:
            raise BaselineError(AuditReason.BASELINE_NOT_ANCESTOR) from None
        identity = _identity(root)
        report, paths, references = _report(root, writers)
        with tempfile.TemporaryDirectory(
            prefix="scope-baseline-", dir="/tmp"
        ) as temporary:
            old = Path(temporary)
            _extract_tree(root, actual_base, old)
            baseline, old_paths, old_references = _report(old, writers)
            result = _changes(
                old,
                root,
                baseline,
                report,
                old_paths,
                paths,
                old_references,
                references,
            )
        report["baseline"] = BaselineResult(
            base=actual_base,
            head=head,
            integration_target=target_ref,
            target_commit=target,
            worktree_sha256=identity,
            dirty=bool(_git(root, "status", "--porcelain", "--untracked-files=normal")),
            changes=result,
            baseline_issues=baseline["issues"],
        )
        if baseline["exit_code"]:
            report["issues"].append(
                dict(
                    group="registry", path="scripts", reason=AuditReason.BASELINE_DRIFT
                )
            )
        _confirm(report, confirmations)
        affected = set(report["affected_groups"])
        for change in result:
            affected.update(change["affected_groups"])
        report["affected_groups"] = sorted(affected)
        report["exit_code"] = int(bool(report["exit_code"] or report["issues"]))
        # 运行过程中树或目标改变时不能发布混合身份的候选。
        if (
            identity != _identity(root)
            or head != _commit(root, "HEAD")
            or target != _commit(root, target_ref)
        ):
            raise BaselineError(AuditReason.BASELINE_IDENTITY_CHANGED)
        return report
    except (OSError, ValueError) as error:
        reason = (
            error.reason
            if isinstance(error, BaselineError)
            else AuditReason.BASELINE_UNAVAILABLE
        )
        report.pop("baseline", None)
        report["exit_code"] = 1
        report["issues"].append(dict(group="registry", path="scripts", reason=reason))
        return report


def _entry_identity(
    report: AuditReport,
    paths: dict[str, str],
    path: str,
    references: dict[str, object],
) -> str:
    owners = {group for group, scope in paths.items() if scope == path}
    if not owners:
        # 中央引用展开后保留逐路径登记身份;仅中央 SHA 变化也必须可见。
        registrations = sorted(
            (f["group"], str(f["kind"]), f["expected_sha256"])
            for f in report["files"]
            if f["path"] == path
        )
        return hashlib.sha256(json.dumps(registrations).encode()).hexdigest()
    # source 哈希更新是机械;成员、测试/fixture 字节与固定计数是语义边界。
    entries = sorted(
        (
            f["group"],
            str(f["kind"]),
            f["path"],
            f["expected_sha256"] if f["kind"] != "source" else "",
        )
        for f in report["files"]
        if f["group"] in owners
    )
    counts = sorted(
        (c["group"], c["path"], c["expected_cases"])
        for c in report["counts"]
        if c["group"] in owners
    )
    refs = sorted((group, references.get(group, [])) for group in owners)
    encoded = json.dumps(
        [sorted(owners), entries, counts, refs], sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _changes(
    old: Path,
    root: Path,
    baseline: AuditReport,
    report: AuditReport,
    old_paths: dict[str, str],
    paths: dict[str, str],
    old_references: dict[str, object],
    references: dict[str, object],
) -> list[BaselineChange]:
    files = [*baseline["files"], *report["files"]]
    all_paths = (
        {f["path"] for f in files} | set(paths.values()) | set(old_paths.values())
    )
    # 分类规范即使未被 scope 绑定,也控制每组的固定材料边界。
    all_paths.add(CLASSIFICATION_PATH)
    changes: list[BaselineChange] = []
    for path in sorted(all_paths):
        groups = {f["group"] for f in files if f["path"] == path}
        groups.update(
            g for mapping in (old_paths, paths) for g, p in mapping.items() if p == path
        )
        if path == CLASSIFICATION_PATH:
            groups.update([*paths, *old_paths])
        kinds = {str(f["kind"]) for f in files if f["path"] == path}
        category = _category(
            old, root, path, kinds, set(paths.values()) | set(old_paths.values())
        )
        old_entry = _entry_identity(baseline, old_paths, path, old_references)
        new_entry = _entry_identity(report, paths, path, references)
        memberships = [
            {(f["group"], f["kind"]) for f in view["files"] if f["path"] == path}
            for view in (baseline, report)
        ]
        if old_entry != new_entry and (
            path in set(paths.values()) | set(old_paths.values())
            or memberships[0] != memberships[1]
        ):
            category = "registration"
        old_sha, new_sha = _sha(old, path), _sha(root, path)
        drift = [
            f
            for f in baseline["files"]
            if f["path"] == path and f["reason"] != AuditReason.OK
        ]
        affected = _affected(baseline, old_paths, groups) | _affected(
            report, paths, groups
        )
        origins: list[BaselineOrigin] = []
        if drift:
            origins.append("baseline_drift")
        registration_changed = old_entry != new_entry and (
            path in set(paths.values()) | set(old_paths.values())
            or memberships[0] == memberships[1]
            or {f["expected_sha256"] for f in baseline["files"] if f["path"] == path}
            != {f["expected_sha256"] for f in report["files"] if f["path"] == path}
        )
        if old_sha != new_sha or registration_changed:
            origins.append("current_change")
        for origin in origins:
            changes.append(
                BaselineChange(
                    path=path,
                    origin=origin,
                    sensitivity="mechanical"
                    if category == "source_support"
                    else "sensitive",
                    category=category,
                    old_sha256=old_sha,
                    new_sha256=new_sha,
                    old_entry_sha256=old_entry,
                    new_entry_sha256=new_entry,
                    registered_sha256=sorted(
                        {f["expected_sha256"] for f in files if f["path"] == path}
                    ),
                    groups=sorted(groups),
                    affected_groups=sorted(affected),
                    confirmed_groups=[],
                    registrations=[
                        BaselineRegistration(
                            tree="base" if tree == "base" else "current",
                            group=f["group"],
                            scope_path=mapping[f["group"]],
                            kind=f["kind"],
                            expected_sha256=f["expected_sha256"],
                        )
                        for tree, source, mapping in (
                            ("base", baseline, old_paths),
                            ("current", report, paths),
                        )
                        for f in source["files"]
                        if f["path"] == path
                    ],
                )
            )
    return changes


def _confirm(report: AuditReport, confirmations: object) -> None:
    baseline = report["baseline"]
    if not isinstance(confirmations, (tuple, list)):
        report["issues"].append(
            dict(
                group="registry",
                path="scripts",
                reason=AuditReason.INVALID_CONFIRMATION,
            )
        )
        return
    expected: list[tuple[BaselineChange, str, dict[str, Any]]] = []
    identity = {
        key: dict(baseline)[key]
        for key in (
            "base",
            "head",
            "integration_target",
            "target_commit",
            "worktree_sha256",
        )
    }
    for change in baseline["changes"]:
        if (
            change["origin"] == "current_change"
            and change["sensitivity"] == "sensitive"
        ):
            for group in change["affected_groups"]:
                entry = {
                    **identity,
                    "group": group,
                    **{
                        key: dict(change)[key]
                        for key in (
                            "path",
                            "origin",
                            "category",
                            "old_sha256",
                            "new_sha256",
                            "old_entry_sha256",
                            "new_entry_sha256",
                        )
                    },
                }
                expected.append((change, group, entry))
    seen: set[int] = set()
    for confirmation in confirmations:
        if not isinstance(confirmation, dict):
            matches = []
        else:
            matches = [
                i
                for i, (_, _, entry) in enumerate(expected)
                if set(confirmation) == {*entry, "reason"}
                and all(confirmation[k] == v for k, v in entry.items())
                and isinstance(confirmation.get("reason"), str)
                and confirmation["reason"].strip()
                and confirmation["reason"].isprintable()
            ]
        if len(matches) != 1 or matches[0] in seen:
            report["issues"].append(
                dict(
                    group="registry",
                    path="scripts",
                    reason=AuditReason.INVALID_CONFIRMATION,
                )
            )
            continue
        index = matches[0]
        seen.add(index)
        change, group, _ = expected[index]
        change["confirmed_groups"].append(group)
    for index, (change, group, _) in enumerate(expected):
        if index not in seen:
            report["issues"].append(
                dict(
                    group=group,
                    path=change["path"],
                    reason=AuditReason.CONFIRMATION_REQUIRED,
                )
            )
