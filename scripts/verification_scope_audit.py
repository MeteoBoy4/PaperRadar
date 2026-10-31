"""固定登记的只读审计; 不生成或修改验收期望。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from scripts.verification_scope_registry import (
    CENTRAL_REGISTRATION_PATH as CENTRAL_REGISTRATION_PATH,
)
from scripts.verification_scope_registry import (
    CLASSIFICATION_PATH as CLASSIFICATION_PATH,
)
from scripts.verification_scope_registry import (
    AuditReason as AuditReason,
)
from scripts.verification_scope_registry import (
    AuditReport as AuditReport,
)
from scripts.verification_scope_registry import (
    BaselineCategory as BaselineCategory,
)
from scripts.verification_scope_registry import (
    BaselineChange as BaselineChange,
)
from scripts.verification_scope_registry import (
    BaselineOrigin as BaselineOrigin,
)
from scripts.verification_scope_registry import (
    BaselineRegistration as BaselineRegistration,
)
from scripts.verification_scope_registry import (
    BaselineResult as BaselineResult,
)
from scripts.verification_scope_registry import (
    CollectionResult as CollectionResult,
)
from scripts.verification_scope_registry import (
    CountRecord as CountRecord,
)
from scripts.verification_scope_registry import (
    FileKind as FileKind,
)
from scripts.verification_scope_registry import (
    FileRecord as FileRecord,
)
from scripts.verification_scope_registry import (
    FileRole as FileRole,
)
from scripts.verification_scope_registry import (
    IssueRecord as IssueRecord,
)
from scripts.verification_scope_registry import (
    Scope as Scope,
)
from scripts.verification_scope_registry import (
    parse_file_bindings as parse_file_bindings,
)
from scripts.verification_scope_registry import (
    valid_case_count as valid_case_count,
)
from scripts.verification_scope_registry import (
    valid_path as valid_path,
)


def _read_files(
    root: Path,
    scopes: tuple[Scope, ...],
) -> dict[str, tuple[str | None, AuditReason]]:
    """唯一文件 I/O 边界, 采集已通过格式校验的显式路径。"""
    identities: dict[str, tuple[str | None, AuditReason]] = {}
    for scope in scopes:
        for raw in scope.bindings.values():
            for path, _ in parse_file_bindings(raw) or ():
                if path in identities:
                    continue
                try:
                    file_path = root / path
                    if not file_path.resolve().is_relative_to(root.resolve()):
                        raise OSError
                    with file_path.open("rb") as stream:
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    identities[path] = (actual, AuditReason.OK)
                except FileNotFoundError:
                    identities[path] = (None, AuditReason.MISSING_FILE)
                except (OSError, ValueError):
                    identities[path] = (None, AuditReason.UNREADABLE_FILE)
    return identities


def audit_scopes(root: Path, scopes: tuple[Scope, ...]) -> AuditReport:
    """先采集文件事实, 再用纯逻辑核对固定登记与引用图。"""
    live_documents, classification_error = _live_documents(root)
    return _audit(
        scopes, _read_files(root, scopes), live_documents, classification_error
    )


def _live_documents(root: Path) -> tuple[frozenset[str], AuditReason | None]:
    # 纯合成材料目录沿用本实现的分类; 完整仓库副本必须消费自己的规则,
    # 即使它的规则已缺失也不能回退宿主, 否则副本损坏会静默通过。
    repository = root
    if not any(
        (root / marker).exists() or (root / marker).is_symlink()
        for marker in (CLASSIFICATION_PATH, "pyproject.toml", ".git")
    ):
        repository = Path(__file__).resolve().parents[1]
        # 兼容仅复制审计脚本的旧合成 CLI fixture。没有项目/Git/分类材料的
        # 纯合成支撑目录不声明生产分类事实; 真实仓库缺规则仍在下方拒绝。
        if not any(
            (repository / marker).exists() or (repository / marker).is_symlink()
            for marker in (CLASSIFICATION_PATH, "pyproject.toml", ".git")
        ):
            return frozenset(), None
    try:
        path = repository / CLASSIFICATION_PATH
        if not path.resolve().is_relative_to(repository.resolve()):
            raise OSError
        value = json.loads(path.read_bytes())
    except OSError:
        return frozenset(), AuditReason.CLASSIFICATION_UNAVAILABLE
    except (ValueError, RecursionError):
        return frozenset(), AuditReason.INVALID_CLASSIFICATION
    try:
        paths = value["classification_rules"]["live_documents"]["exact_paths"]
    except (KeyError, TypeError):
        return frozenset(), AuditReason.INVALID_CLASSIFICATION
    if (
        not isinstance(paths, list)
        or not paths
        or any(not valid_path(path) for path in paths)
        or len(set(paths)) != len(paths)
    ):
        return frozenset(), AuditReason.INVALID_CLASSIFICATION
    return frozenset(paths), None


def _audit(
    scopes: tuple[Scope, ...],
    identities: Mapping[str, tuple[str | None, AuditReason]],
    live_documents: frozenset[str],
    classification_error: AuditReason | None,
) -> AuditReport:
    """确定性校验; 不读取文件或刷新任何登记。"""
    files: list[FileRecord] = []
    issues: list[IssueRecord] = []
    counts: list[CountRecord] = []
    expected_counts: dict[str, tuple[Scope, int]] = {}
    edges: dict[str, set[str]] = {scope.path: set() for scope in scopes}

    def issue(scope: Scope, reason: AuditReason) -> None:
        issues.append(dict(group=scope.group, path=scope.path, reason=reason))

    if classification_error is not None:
        issues.append(
            dict(
                group="registry", path=CLASSIFICATION_PATH, reason=classification_error
            )
        )

    if not scopes:
        issues.append(
            dict(group="registry", path="scripts", reason=AuditReason.EMPTY_REGISTRY)
        )
    if len(edges) != len(scopes) or len({s.group for s in scopes}) != len(scopes):
        issues.append(
            dict(group="registry", path="scripts", reason=AuditReason.DUPLICATE_SCOPE)
        )
    for scope in scopes:
        for reason in scope.errors:
            issue(scope, reason)
        if not isinstance(scope.references, tuple):
            issue(scope, AuditReason.INVALID_REGISTRATION)
        else:
            seen_references: set[str] = set()
            for reference in scope.references:
                if not valid_path(reference) or (
                    reference not in edges and reference not in scope.reference_registry
                ):
                    issue(scope, AuditReason.INVALID_REGISTRATION)
                    continue
                if reference in seen_references:
                    issue(scope, AuditReason.DUPLICATE_PATH)
                seen_references.add(reference)
                if reference in edges:
                    edges[reference].add(scope.path)
                if reference == scope.path:
                    issue(scope, AuditReason.SELF_REFERENCE)
        seen: set[str] = set()
        if not scope.bindings:
            issue(scope, AuditReason.EMPTY_BINDING)
        for raw_kind, raw in scope.bindings.items():
            try:
                kind = FileKind(raw_kind)
            except ValueError:
                issue(scope, AuditReason.INVALID_BINDING)
                continue
            bindings = parse_file_bindings(raw)
            if bindings is None:
                issue(scope, AuditReason.INVALID_BINDING)
                continue
            if not bindings:
                issue(scope, AuditReason.EMPTY_BINDING)
            for path, expected in bindings:
                if path == CENTRAL_REGISTRATION_PATH:
                    issue(scope, AuditReason.INVALID_BINDING)
                if path in seen:
                    issue(scope, AuditReason.DUPLICATE_PATH)
                seen.add(path)
                actual, reason = identities[path]
                if reason == AuditReason.OK and actual != expected:
                    reason = AuditReason.HASH_DRIFT
                if path in live_documents:
                    reason = AuditReason.LIVE_DOCUMENT_BINDING
                files.append(
                    dict(
                        group=scope.group,
                        kind=kind,
                        role=FileRole.SUPPORT
                        if kind == FileKind.SOURCE
                        and path.startswith(("scripts/", "tests/"))
                        else FileRole(kind),
                        path=path,
                        expected_sha256=expected,
                        actual_sha256=actual,
                        reason=reason,
                    )
                )
                if path in edges:
                    edges[path].add(scope.path)
                    if path == scope.path:
                        issue(scope, AuditReason.SELF_REFERENCE)
        if scope.counts is not None:
            tests = parse_file_bindings(scope.bindings.get(FileKind.TEST))
            if not isinstance(scope.counts, dict):
                issue(scope, AuditReason.INVALID_COUNTS)
                continue
            if tests is None or set(scope.counts) != {path for path, _ in tests}:
                issue(scope, AuditReason.COUNT_KEYS_MISMATCH)
            for path, expected in scope.counts.items():
                if not valid_path(path) or not valid_case_count(expected):
                    issue(scope, AuditReason.INVALID_COUNT)
                    continue
                counts.append(
                    dict(group=scope.group, path=path, expected_cases=expected)
                )
                if path in expected_counts and expected_counts[path][1] != expected:
                    issue(scope, AuditReason.CONFLICTING_COUNTS)
                    issue(expected_counts[path][0], AuditReason.CONFLICTING_COUNTS)
                expected_counts[path] = (scope, expected)

    # Kahn 排序保持原登记的相对顺序; 引用必须先于绑定它的 scope。
    pending = list(edges)
    order: list[str] = []
    while pending:
        ready = [p for p in pending if not any(p in edges[q] for q in pending)]
        if not ready:
            for scope in scopes:
                if scope.path in pending:
                    issue(scope, AuditReason.CYCLE)
            order = []
            break
        for path in ready:
            order.append(path)
            pending.remove(path)
    downstream = {}
    for path in edges:
        reached: set[str] = set()
        frontier = list(edges[path])
        while frontier:
            target = frontier.pop()
            if target not in reached:
                reached.add(target)
                frontier.extend(edges[target])
        downstream[path] = [p for p in order if p in reached]
    directly_affected = {f["group"] for f in files if f["reason"] != AuditReason.OK}
    directly_affected.update(i["group"] for i in issues)
    return dict(
        exit_code=int(bool(issues or directly_affected)),
        files=files,
        issues=issues,
        counts=counts,
        order=order,
        downstream=downstream,
        affected_groups=_affected_groups(scopes, order, downstream, directly_affected),
        collection=dict(
            reason=AuditReason.NOT_REQUESTED, execution="not_run", modules={}
        ),
    )


def _affected_groups(
    scopes: tuple[Scope, ...],
    order: list[str],
    downstream: Mapping[str, list[str]],
    directly_affected: set[str],
) -> list[str]:
    affected_paths = {s.path for s in scopes if s.group in directly_affected}
    for path in tuple(affected_paths):
        affected_paths.update(downstream[path])
    return [
        s.group
        for path in (order or [s.path for s in scopes])
        for s in scopes
        if s.path == path and s.path in affected_paths
    ]


def collection_targets(report: AuditReport) -> dict[str, int | None] | None:
    """只收集已明确列入测试清单的模块; 未登记/非法分母以 None 表达。"""
    count_issues = {
        AuditReason.COUNT_KEYS_MISMATCH,
        AuditReason.INVALID_COUNT,
        AuditReason.INVALID_COUNTS,
        AuditReason.CONFLICTING_COUNTS,
    }
    if any(issue["reason"] not in count_issues for issue in report["issues"]):
        return None
    if any(
        record["reason"] not in (AuditReason.OK, AuditReason.HASH_DRIFT)
        for record in report["files"]
    ):
        return None
    targets: dict[str, int | None] = {
        record["path"]: None
        for record in report["files"]
        if record["kind"] == FileKind.TEST
    }
    grouped: dict[str, set[int]] = {}
    for count in report["counts"]:
        grouped.setdefault(count["path"], set()).add(count["expected_cases"])
    for path in targets:
        expected = grouped.get(path, set())
        if len(expected) == 1:
            targets[path] = next(iter(expected))
    return targets or None


def merge_collection(
    report: AuditReport,
    scopes: tuple[Scope, ...],
    collection: CollectionResult,
) -> AuditReport:
    """合并收集诊断; 只有完整计数差异才能新增文件所属组的影响。"""
    merged: AuditReport = {**report, "collection": collection}
    if collection["reason"] in (AuditReason.OK, AuditReason.NOT_REQUESTED):
        return merged
    merged["exit_code"] = 1
    if collection["reason"] == AuditReason.COUNT_MISMATCH:
        targets = collection_targets(report) or {}
        mismatched = {
            p for p, n in targets.items() if collection["modules"].get(p) != n
        }
        affected = set(report["affected_groups"])
        affected.update(
            r["group"]
            for r in report["files"]
            if r["kind"] == FileKind.TEST and r["path"] in mismatched
        )
        merged["affected_groups"] = _affected_groups(
            scopes,
            report["order"],
            report["downstream"],
            affected,
        )
    return merged


def audit_baseline(
    root: Path,
    *,
    base: str,
    integration_target: str,
    confirmations: object = (),
    writers: tuple[tuple[str, str], ...] | None = None,
) -> AuditReport:
    """只读比较显式基线;确认仅为逐变化审阅依据,不写回登记。"""
    from scripts.verification_scope_baseline import analyze_baseline

    return analyze_baseline(
        root,
        base=base,
        integration_target=integration_target,
        confirmations=confirmations,
        writers=writers,
        audit_scopes=audit_scopes,
    )
