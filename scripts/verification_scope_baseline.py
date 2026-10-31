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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from scripts.verification_scope_registry import (
    CLASSIFICATION_PATH,
    AuditReason,
    AuditReport,
    BaselineCategory,
    BaselineChange,
    BaselineOrigin,
    BaselineRegistration,
    BaselineResult,
    Scope,
    valid_path,
)

GROUP_REGISTRATION_PATH = "scripts/verification_groups.py"
LEGACY_GROUP_DECLARATIONS = {
    "scripts/a1_acceptance.py": "A1_GROUP",
    "scripts/a2_acceptance.py": "A2_01_GROUP",
}


@dataclass(frozen=True)
class _TreeView:
    """单树的只读比较事实;不持有可用于再次读取文件的根路径。"""

    files: tuple[Mapping[str, Any], ...]
    counts: tuple[Mapping[str, Any], ...]
    downstream: Mapping[str, tuple[str, ...]]
    paths: Mapping[str, str]
    references_json: Mapping[str, str]
    digests: Mapping[str, str | None]
    sensitive_constants: Mapping[str, Mapping[str, str]]


def _capture_view(
    root: Path,
    report: AuditReport,
    paths: dict[str, str],
    references: dict[str, object],
    categories: Mapping[str, BaselineCategory | None],
) -> _TreeView:
    return _TreeView(
        files=tuple(MappingProxyType(dict(f)) for f in report["files"]),
        counts=tuple(MappingProxyType(dict(c)) for c in report["counts"]),
        downstream=MappingProxyType(
            {p: tuple(groups) for p, groups in report["downstream"].items()}
        ),
        paths=MappingProxyType(dict(paths)),
        references_json=MappingProxyType(
            {group: json.dumps(refs) for group, refs in references.items()}
        ),
        digests=MappingProxyType({p: _sha(root, p) for p in categories}),
        sensitive_constants=MappingProxyType(
            {
                p: MappingProxyType(_sensitive_constants(root, p))
                for p, category in categories.items()
                if category is None
            }
        ),
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


def _ordered_declarations(tree: ast.Module, name: str) -> str:
    declarations = []
    for declaration in tree.body:
        if not isinstance(declaration, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = (
            declaration.targets
            if isinstance(declaration, ast.Assign)
            else [declaration.target]
        )
        if any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            declarations.append(ast.dump(declaration, include_attributes=False))
    return json.dumps(declarations)


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
    if path == GROUP_REGISTRATION_PATH:
        # 保存完整有序声明,不能让后续追加覆盖最初的计划语义。
        result["GROUPS"] = _ordered_declarations(tree, "GROUPS")
    if path in LEGACY_GROUP_DECLARATIONS:
        name = LEGACY_GROUP_DECLARATIONS[path]
        result[name] = _ordered_declarations(tree, name)
    for node in ast.walk(tree):
        if (
            path == GROUP_REGISTRATION_PATH
            and isinstance(node, ast.ClassDef)
            and node.name == "Group"
        ):
            # 默认值与字段顺序同样决定未显式提供参数的实际生产声明。
            result["Group.fields"] = ast.dump(
                ast.Module(
                    body=[
                        item for item in node.body if isinstance(item, ast.AnnAssign)
                    ],
                    type_ignores=[],
                ),
                include_attributes=False,
            )
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and any(
                    word in target.id for word in words
                ):
                    result[target.id] = ast.dump(node, include_attributes=False)
    return result


def _path_category(
    path: str, kinds: set[str], scope_paths: set[str]
) -> BaselineCategory | None:
    """按原优先级分类;仅返回 None 的材料需要比较 AST 敏感常量。"""
    if path == CLASSIFICATION_PATH:
        return "classification"
    if path in scope_paths:
        return None
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
    return None if path.endswith(".py") else "source_support"


def _category(
    old: _TreeView,
    current: _TreeView,
    path: str,
    kinds: set[str],
    scope_paths: set[str],
) -> BaselineCategory:
    category = _path_category(path, kinds, scope_paths)
    if category is not None:
        return category
    if old.sensitive_constants.get(path, {}) != current.sensitive_constants.get(
        path, {}
    ):
        return "registration" if path in scope_paths else "format_or_criteria"
    return "source_support"


def _affected(view: _TreeView, groups: set[str]) -> set[str]:
    affected_paths = {view.paths[g] for g in groups if g in view.paths}
    for path in tuple(affected_paths):
        affected_paths.update(view.downstream.get(path, ()))
    return groups | {g for g, path in view.paths.items() if path in affected_paths}


def analyze_baseline(
    root: Path,
    *,
    base: str,
    integration_target: str,
    confirmations: object = (),
    writers: tuple[tuple[str, str], ...] | None = None,
    audit_scopes: Callable[[Path, tuple[Scope, ...]], AuditReport],
) -> AuditReport:
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
            material_paths = (
                {f["path"] for view in (baseline, report) for f in view["files"]}
                | set(old_paths.values())
                | set(paths.values())
                | {CLASSIFICATION_PATH}
            )
            scope_paths = set(old_paths.values()) | set(paths.values())
            files = (*baseline["files"], *report["files"])
            categories = {
                path: _path_category(
                    path,
                    {str(f["kind"]) for f in files if f["path"] == path},
                    scope_paths,
                )
                for path in material_paths
            }
            old_view = _capture_view(
                old, baseline, old_paths, old_references, categories
            )
            current_view = _capture_view(root, report, paths, references, categories)
            result = _changes(old_view, current_view)
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
    view: _TreeView,
    path: str,
) -> str:
    owners = {group for group, scope in view.paths.items() if scope == path}
    if not owners:
        # 中央引用展开后保留逐路径登记身份;仅中央 SHA 变化也必须可见。
        registrations = sorted(
            (f["group"], str(f["kind"]), f["expected_sha256"])
            for f in view.files
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
        for f in view.files
        if f["group"] in owners
    )
    counts = sorted(
        (c["group"], c["path"], c["expected_cases"])
        for c in view.counts
        if c["group"] in owners
    )
    refs = sorted(
        (group, json.loads(view.references_json.get(group, "[]"))) for group in owners
    )
    encoded = json.dumps(
        [sorted(owners), entries, counts, refs], sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _changes(old: _TreeView, current: _TreeView) -> list[BaselineChange]:
    files = (*old.files, *current.files)
    scope_paths = set(old.paths.values()) | set(current.paths.values())
    all_paths = {f["path"] for f in files} | scope_paths | {CLASSIFICATION_PATH}
    changes: list[BaselineChange] = []
    for path in sorted(all_paths):
        groups = {f["group"] for f in files if f["path"] == path}
        groups.update(
            g
            for mapping in (old.paths, current.paths)
            for g, p in mapping.items()
            if p == path
        )
        if path in (CLASSIFICATION_PATH, GROUP_REGISTRATION_PATH):
            # 生产声明控制整个计划的 required、产物、依赖、writer 和回执范围。
            groups.update([*current.paths, *old.paths])
        kinds = {str(f["kind"]) for f in files if f["path"] == path}
        category = _category(old, current, path, kinds, scope_paths)
        old_entry = _entry_identity(old, path)
        new_entry = _entry_identity(current, path)
        memberships = [
            {(f["group"], f["kind"]) for f in view.files if f["path"] == path}
            for view in (old, current)
        ]
        if old_entry != new_entry and (
            path in scope_paths or memberships[0] != memberships[1]
        ):
            category = "registration"
        old_sha, new_sha = old.digests[path], current.digests[path]
        drift = [
            f for f in old.files if f["path"] == path and f["reason"] != AuditReason.OK
        ]
        affected = _affected(old, groups) | _affected(current, groups)
        origins: list[BaselineOrigin] = []
        if drift:
            origins.append("baseline_drift")
        registration_changed = old_entry != new_entry and (
            path in scope_paths
            or memberships[0] == memberships[1]
            or {f["expected_sha256"] for f in old.files if f["path"] == path}
            != {f["expected_sha256"] for f in current.files if f["path"] == path}
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
                            scope_path=view.paths[f["group"]],
                            kind=f["kind"],
                            expected_sha256=f["expected_sha256"],
                        )
                        for tree, view in (("base", old), ("current", current))
                        for f in view.files
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
