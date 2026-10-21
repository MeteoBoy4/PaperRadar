"""从生产 writer 登记推导 scope; 只解释固定常量, 不扫描路径/哈希形状。"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from scripts.verification_scope_audit import AuditReason, FileKind, Scope

# writer 与 scope 的显式维护契约。新常量/导入形式需人工审查此契约。
BINDINGS = {
    "REQUIRED_TEST_MODULES": FileKind.TEST,
    "REQUIRED_SOURCE_MODULES": FileKind.SOURCE,
    "REQUIRED_FIXTURE_FILES": FileKind.FIXTURE,
}
COUNTS = "REQUIRED_TEST_CASE_COUNTS"
METADATA = {
    "SCOPE",
    "ISSUE",
    "PARENT_ISSUE",
    "FORMAT_VERSION",
    "FORMAT_VERSIONS",
    "MIGRATION_REVISION",
    "SUFFIX",
    "REQUIRED_CHECKS",
    "REQUIRED_DEPENDENCIES",
    "CAPABILITIES",
    "NOT_ASSESSED",
    "NOT_IMPLEMENTED",
    "SNAPSHOT_FORMAT_VERSION",
}


class RegistrationError(ValueError):
    """受控原因, 不携带文件内容或异常文本。"""

    def __init__(self, reason: AuditReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


def _read_tree(root: Path, path: str) -> ast.Module:
    try:
        return ast.parse((root / path).read_bytes())
    except (OSError, ValueError, SyntaxError):
        raise RegistrationError(AuditReason.REGISTRATION_UNAVAILABLE) from None


class _Constants:
    def __init__(self, tree: ast.Module) -> None:
        self.nodes: dict[str, ast.expr] = {}
        for node in tree.body:
            targets: list[ast.expr]
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
            elif isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.Import, ast.ImportFrom)) or (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            else:
                raise RegistrationError(AuditReason.UNSUPPORTED_REGISTRATION)
            for target in targets:
                if not isinstance(target, ast.Name) or node.value is None:
                    raise RegistrationError(AuditReason.UNSUPPORTED_REGISTRATION)
                if target.id in self.nodes:
                    raise RegistrationError(AuditReason.DUPLICATE_REGISTRATION)
                self.nodes[target.id] = node.value
        self.active: set[str] = set()

    def get(self, name: str) -> Any:
        if name not in self.nodes or name in self.active:
            raise RegistrationError(AuditReason.INVALID_REGISTRATION)
        self.active.add(name)
        try:
            return self._value(self.nodes[name])
        finally:
            self.active.remove(name)

    def _value(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.get(node.id)
        if isinstance(node, (ast.Tuple, ast.List)):
            items: list[Any] = []
            for child in node.elts:
                if isinstance(child, ast.Starred):
                    expanded = self._value(child.value)
                    if not isinstance(expanded, (tuple, list)):
                        raise RegistrationError(AuditReason.INVALID_REGISTRATION)
                    items.extend(expanded)
                else:
                    items.append(self._value(child))
            return tuple(items) if isinstance(node, ast.Tuple) else items
        if isinstance(node, ast.Dict):
            result: dict[str, Any] = {}
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None:
                    entries = self._value(value)
                    if not isinstance(entries, dict):
                        raise RegistrationError(AuditReason.INVALID_REGISTRATION)
                else:
                    decoded = self._value(key)
                    if not isinstance(decoded, str):
                        raise RegistrationError(AuditReason.INVALID_REGISTRATION)
                    entries = {decoded: self._value(value)}
                if result.keys() & entries.keys():
                    raise RegistrationError(AuditReason.DUPLICATE_COUNT_KEY)
                result.update(entries)
            return result
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            operand = self._value(node.operand)
            if type(operand) is int:
                return -operand
        raise RegistrationError(AuditReason.UNSUPPORTED_REGISTRATION)


def _writer_scope(root: Path, group: str, writer: str) -> Scope:
    imports: dict[str, list[ast.alias]] = {}
    try:
        tree = _read_tree(root, writer)
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name.endswith("_scope") for alias in node.names
            ):
                raise RegistrationError(AuditReason.UNSUPPORTED_SCOPE_IMPORT)
            # 明确的 writer 命名契约, 与常量值的形状无关。
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("scripts.")
                and node.module.endswith("_scope")
            ):
                imports.setdefault(node.module.replace(".", "/") + ".py", []).extend(
                    node.names
                )
            if isinstance(node, ast.ImportFrom) and node.module == "scripts":
                for alias in node.names:
                    if not alias.name.endswith("_scope"):
                        continue
                    uses = [
                        n
                        for n in ast.walk(tree)
                        if isinstance(n, ast.Name)
                        and isinstance(n.ctx, ast.Load)
                        and n.id == (alias.asname or alias.name)
                    ]
                    if not uses:
                        raise RegistrationError(AuditReason.UNSUPPORTED_SCOPE_IMPORT)
                    for use in uses:
                        parent = parents[use]
                        if (
                            not isinstance(parent, ast.Attribute)
                            or parent.attr not in METADATA
                        ):
                            raise RegistrationError(
                                AuditReason.UNSUPPORTED_SCOPE_IMPORT
                            )
        primary = [
            path
            for path, aliases in imports.items()
            if any(
                a.name == "REQUIRED_TEST_MODULES" and a.asname in (None, a.name)
                for a in aliases
            )
        ]
        if len(primary) != 1:
            raise RegistrationError(AuditReason.UNSUPPORTED_WRITER_SCOPE)
        path = primary[0]
        bindings: dict[str, object] = {}
        tests: list[tuple[str, str]] = []
        counts: object = None
        for imported_path, aliases in imports.items():
            constants = _Constants(_read_tree(root, imported_path))
            names = {a.name for a in aliases}
            if names - (BINDINGS.keys() | METADATA | {COUNTS}):
                raise RegistrationError(AuditReason.UNSUPPORTED_SCOPE_CONSTANT)
            if imported_path == path:
                expected = constants.nodes.keys() & (BINDINGS.keys() | {COUNTS})
                if not expected <= names:
                    raise RegistrationError(AuditReason.UNCONSUMED_REGISTRATION)
            for alias in aliases:
                if alias.name in BINDINGS:
                    if imported_path != path and alias.name != "REQUIRED_TEST_MODULES":
                        raise RegistrationError(
                            AuditReason.UNSUPPORTED_SECONDARY_BINDING
                        )
                    raw = constants.get(alias.name)
                    if imported_path == path:
                        bindings[BINDINGS[alias.name]] = raw
                    if alias.name == "REQUIRED_TEST_MODULES":
                        if not isinstance(raw, tuple):
                            raise RegistrationError(AuditReason.INVALID_REGISTRATION)
                        tests.extend(raw)
                elif alias.name == COUNTS:
                    if imported_path != path:
                        raise RegistrationError(
                            AuditReason.UNSUPPORTED_SECONDARY_BINDING
                        )
                    counts = constants.get(COUNTS)
                    if not isinstance(counts, dict):
                        raise RegistrationError(AuditReason.INVALID_COUNTS)
        # A2 完整回执明确消费 A1 测试; 同时核对这些导入的文件哈希。
        bindings[FileKind.TEST] = tuple(tests)
        return Scope(group, path, bindings, counts)
    except RegistrationError as error:
        return Scope(group, writer, {}, errors=(error.reason,))


def load_scopes(
    root: Path,
    *,
    writers: tuple[tuple[str, str], ...] | None = None,
) -> tuple[Scope, ...]:
    """正常导入生产 registry; 随后按 writer 导入解析清单 AST, 不 eval 清单。"""
    if writers is None:
        from scripts.a2_full_acceptance import acceptance_groups

        writers_list = []
        for group in acceptance_groups():
            source = inspect.getsourcefile(group.write)
            if source is None:
                return (
                    Scope(
                        group.name,
                        "scripts",
                        {},
                        errors=(AuditReason.WRITER_UNAVAILABLE,),
                    ),
                )
            writers_list.append(
                (
                    group.name,
                    Path(source).resolve().relative_to(root.resolve()).as_posix(),
                )
            )
        writers = tuple(writers_list)
    return tuple(_writer_scope(root, group, writer) for group, writer in writers)
