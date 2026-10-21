"""固定登记的只读审计; 不生成或修改验收期望。"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, NotRequired, TypedDict, TypeGuard


class AuditReason(StrEnum):
    OK = "ok"
    HASH_DRIFT = "hash_drift"
    MISSING_FILE = "missing_file"
    UNREADABLE_FILE = "unreadable_file"
    EMPTY_REGISTRY = "empty_registry"
    DUPLICATE_SCOPE = "duplicate_scope"
    EMPTY_BINDING = "empty_binding"
    INVALID_BINDING = "invalid_binding"
    DUPLICATE_PATH = "duplicate_path"
    SELF_REFERENCE = "self_reference"
    INVALID_COUNTS = "invalid_counts"
    COUNT_KEYS_MISMATCH = "count_keys_mismatch"
    INVALID_COUNT = "invalid_count"
    CONFLICTING_COUNTS = "conflicting_counts"
    CYCLE = "cycle"
    REGISTRATION_UNAVAILABLE = "registration_unavailable"
    INVALID_REGISTRATION = "invalid_registration"
    UNSUPPORTED_REGISTRATION = "unsupported_registration"
    DUPLICATE_REGISTRATION = "duplicate_registration"
    DUPLICATE_COUNT_KEY = "duplicate_count_key"
    UNSUPPORTED_SCOPE_IMPORT = "unsupported_scope_import"
    UNSUPPORTED_WRITER_SCOPE = "unsupported_writer_scope"
    UNSUPPORTED_SCOPE_CONSTANT = "unsupported_scope_constant"
    UNCONSUMED_REGISTRATION = "unconsumed_registration"
    UNSUPPORTED_SECONDARY_BINDING = "unsupported_secondary_binding"
    WRITER_UNAVAILABLE = "writer_unavailable"
    REGISTRY_UNAVAILABLE = "registry_unavailable"
    NOT_REQUESTED = "not_requested"
    AUDIT_FAILED = "audit_failed"
    COLLECTION_UNAVAILABLE = "collection_unavailable"
    COLLECTION_TIMEOUT = "collection_timeout"
    COLLECTION_FAILED = "collection_failed"
    COLLECTION_SKIPPED = "collection_skipped"
    COLLECTION_DESELECTED = "collection_deselected"
    COUNT_MISMATCH = "count_mismatch"
    UNKNOWN_ARGUMENT = "unknown_argument"
    INVALID_OPTION_VALUE = "invalid_option_value"
    INVALID_ARGUMENTS = "invalid_arguments"


class FileKind(StrEnum):
    TEST = "test"
    SOURCE = "source"
    FIXTURE = "fixture"


class FileRole(StrEnum):
    TEST = "test"
    SOURCE = "source"
    FIXTURE = "fixture"
    SUPPORT = "support"


class FileRecord(TypedDict):
    group: str
    kind: FileKind
    role: FileRole
    path: str
    expected_sha256: str
    actual_sha256: str | None
    reason: AuditReason


class IssueRecord(TypedDict):
    group: str
    path: str
    reason: AuditReason


class CountRecord(TypedDict):
    group: str
    path: str
    expected_cases: int


class CollectionResult(TypedDict):
    reason: AuditReason
    execution: Literal["not_run"]
    modules: dict[str, int]
    collection_skipped: NotRequired[int]
    deselected: NotRequired[int]


class AuditReport(TypedDict):
    exit_code: int
    files: list[FileRecord]
    issues: list[IssueRecord]
    counts: list[CountRecord]
    order: list[str]
    downstream: dict[str, list[str]]
    affected_groups: list[str]
    collection: CollectionResult


@dataclass(frozen=True)
class Scope:
    group: str
    path: str
    bindings: Mapping[str, object]
    counts: object = None
    errors: tuple[AuditReason, ...] = ()


def valid_path(value: object) -> TypeGuard[str]:
    """仅允许规范的仓库相对路径, 不回显不受控载荷。"""
    return (
        isinstance(value, str)
        and bool(value)
        and not PurePosixPath(value).is_absolute()
        and all(part not in ("", ".", "..") for part in value.split("/"))
        and all(character.isprintable() for character in value)
        and "\\" not in value
        and "::" not in value
    )


def valid_case_count(value: object) -> TypeGuard[int]:
    return type(value) is int and value > 0


def parse_file_bindings(raw: object) -> list[tuple[str, str]] | None:
    if not isinstance(raw, tuple):
        return None
    result = []
    for item in raw:
        if (
            not isinstance(item, tuple)
            or len(item) != 2
            or not valid_path(item[0])
            or not isinstance(item[1], str)
            or re.fullmatch(r"[0-9a-f]{64}", item[1]) is None
        ):
            return None
        result.append((item[0], item[1]))
    return result


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
    return _audit(scopes, _read_files(root, scopes))


def _audit(
    scopes: tuple[Scope, ...],
    identities: Mapping[str, tuple[str | None, AuditReason]],
) -> AuditReport:
    """确定性校验; 不读取文件或刷新任何登记。"""
    files: list[FileRecord] = []
    issues: list[IssueRecord] = []
    counts: list[CountRecord] = []
    expected_counts: dict[str, tuple[Scope, int]] = {}
    edges: dict[str, set[str]] = {scope.path: set() for scope in scopes}

    def issue(scope: Scope, reason: AuditReason) -> None:
        issues.append(dict(group=scope.group, path=scope.path, reason=reason))

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
                if path in seen:
                    issue(scope, AuditReason.DUPLICATE_PATH)
                seen.add(path)
                actual, reason = identities[path]
                if reason == AuditReason.OK and actual != expected:
                    reason = AuditReason.HASH_DRIFT
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
