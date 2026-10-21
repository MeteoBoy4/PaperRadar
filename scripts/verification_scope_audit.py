"""固定登记的只读审计; 不生成或修改验收期望。"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True)
class Scope:
    group: str
    path: str
    bindings: Mapping[str, object]
    counts: object = None
    count_tests: object = None
    errors: tuple[str, ...] = ()


def valid_path(value: object) -> bool:
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


def _bindings(raw: object) -> list[tuple[str, str]] | None:
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


def audit_scopes(root: Path, scopes: tuple[Scope, ...]) -> dict[str, Any]:
    """核对明确范围及绑定 DAG; 失败不隐藏为未登记的空集合。"""
    files: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    counts: list[dict[str, Any]] = []
    expected_counts: dict[str, tuple[Scope, int]] = {}
    edges: dict[str, set[str]] = {scope.path: set() for scope in scopes}

    def issue(scope: Scope, reason: str) -> None:
        issues.append(dict(group=scope.group, path=scope.path, reason=reason))

    if not scopes:
        issues.append(dict(group="registry", path="scripts", reason="empty_registry"))
    if len(edges) != len(scopes) or len({s.group for s in scopes}) != len(scopes):
        issues.append(dict(group="registry", path="scripts", reason="duplicate_scope"))
    for scope in scopes:
        for reason in scope.errors:
            issue(scope, reason)
        seen: set[str] = set()
        if not scope.bindings:
            issue(scope, "empty_binding")
        for kind, raw in scope.bindings.items():
            bindings = _bindings(raw)
            if bindings is None:
                issue(scope, "invalid_binding")
                continue
            if not bindings:
                issue(scope, "empty_binding")
            for path, expected in bindings:
                if path in seen:
                    issue(scope, "duplicate_path")
                seen.add(path)
                try:
                    file_path = root / path
                    if not file_path.resolve().is_relative_to(root.resolve()):
                        raise OSError
                    with file_path.open("rb") as stream:
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    reason = "ok" if actual == expected else "hash_drift"
                except FileNotFoundError:
                    actual, reason = None, "missing_file"
                except (OSError, ValueError):
                    actual, reason = None, "unreadable_file"
                files.append(
                    dict(
                        group=scope.group,
                        kind=kind,
                        role="support"
                        if kind == "source" and path.startswith(("scripts/", "tests/"))
                        else kind,
                        path=path,
                        expected_sha256=expected,
                        actual_sha256=actual,
                        reason=reason,
                    )
                )
                if path in edges:
                    edges[path].add(scope.path)
                    if path == scope.path:
                        issue(scope, "self_reference")
        if scope.counts is not None:
            tests = _bindings(
                scope.count_tests
                if scope.count_tests is not None
                else scope.bindings.get("test")
            )
            if not isinstance(scope.counts, dict):
                issue(scope, "invalid_counts")
                continue
            if tests is None or set(scope.counts) != {path for path, _ in tests}:
                issue(scope, "count_keys_mismatch")
            for path, expected in scope.counts.items():
                if not valid_path(path) or type(expected) is not int or expected <= 0:
                    issue(scope, "invalid_count")
                    continue
                counts.append(
                    dict(group=scope.group, path=path, expected_cases=expected)
                )
                if path in expected_counts and expected_counts[path][1] != expected:
                    issue(scope, "conflicting_counts")
                    issue(expected_counts[path][0], "conflicting_counts")
                expected_counts[path] = (scope, expected)

    # Kahn 排序保持原登记的相对顺序; 引用必须先于绑定它的 scope。
    pending = list(edges)
    order: list[str] = []
    while pending:
        ready = [p for p in pending if not any(p in edges[q] for q in pending)]
        if not ready:
            for scope in scopes:
                if scope.path in pending:
                    issue(scope, "cycle")
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
    directly_affected = {f["group"] for f in files if f["reason"] != "ok"}
    directly_affected.update(i["group"] for i in issues)
    affected_paths = {s.path for s in scopes if s.group in directly_affected}
    for path in tuple(affected_paths):
        affected_paths.update(downstream[path])
    affected = [
        s.group
        for path in (order or list(edges))
        for s in scopes
        if s.path == path and s.path in affected_paths
    ]
    return dict(
        exit_code=int(bool(issues or directly_affected)),
        files=files,
        issues=issues,
        counts=counts,
        order=order,
        downstream=downstream,
        affected_groups=affected,
    )
