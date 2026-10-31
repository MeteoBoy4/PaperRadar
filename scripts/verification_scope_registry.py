"""固定登记的数据类型、接收校验与静态解释;不依赖审计或基线编排。"""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Literal, NotRequired, TypedDict, TypeGuard

CENTRAL_REGISTRATION_PATH = "scripts/verification_scope_materials.py"
CLASSIFICATION_PATH = "docs/verification/scope-material-inventory.json"


class AuditReason(StrEnum):
    OK = "ok"
    HASH_DRIFT = "hash_drift"
    MISSING_FILE = "missing_file"
    UNREADABLE_FILE = "unreadable_file"
    LIVE_DOCUMENT_BINDING = "live_document_binding"
    CLASSIFICATION_UNAVAILABLE = "classification_unavailable"
    INVALID_CLASSIFICATION = "invalid_classification"
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
    INVALID_BASELINE = "invalid_baseline"
    BASELINE_UNAVAILABLE = "baseline_unavailable"
    BASELINE_REGISTRATION_UNAVAILABLE = "baseline_registration_unavailable"
    BASELINE_TARGET_MISMATCH = "baseline_target_mismatch"
    BASELINE_NOT_ANCESTOR = "baseline_not_ancestor"
    BASELINE_DRIFT = "baseline_drift"
    BASELINE_IDENTITY_CHANGED = "baseline_identity_changed"
    INVALID_CONFIRMATION = "invalid_confirmation"
    CONFIRMATION_REQUIRED = "confirmation_required"


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


BaselineOrigin = Literal["baseline_drift", "current_change"]
BaselineCategory = Literal[
    "source_support",
    "registration",
    "test",
    "fixture",
    "evidence",
    "classification",
    "format_or_criteria",
]


class BaselineRegistration(TypedDict):
    tree: Literal["base", "current"]
    group: str
    scope_path: str
    kind: FileKind
    expected_sha256: str


class BaselineChange(TypedDict):
    path: str
    origin: BaselineOrigin
    sensitivity: Literal["mechanical", "sensitive"]
    category: BaselineCategory
    old_sha256: str | None
    new_sha256: str | None
    old_entry_sha256: str
    new_entry_sha256: str
    registered_sha256: list[str]
    groups: list[str]
    affected_groups: list[str]
    confirmed_groups: list[str]
    registrations: list[BaselineRegistration]


class BaselineResult(TypedDict):
    base: str
    head: str
    integration_target: str
    target_commit: str
    worktree_sha256: str
    dirty: bool
    baseline_issues: list[IssueRecord]
    changes: list[BaselineChange]


class AuditReport(TypedDict):
    baseline: NotRequired[BaselineResult]
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
    references: object = ()
    reference_registry: frozenset[str] = frozenset()


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


CENTRAL_PATH = CENTRAL_REGISTRATION_PATH
CENTRAL_NAME = "SHARED_MATERIALS"

# writer 与 scope 的显式维护契约。新常量/导入形式需人工审查此契约。
BINDINGS = {
    "REQUIRED_TEST_MODULES": FileKind.TEST,
    "REQUIRED_SOURCE_MODULES": FileKind.SOURCE,
    "REQUIRED_FIXTURE_FILES": FileKind.FIXTURE,
}
COUNTS = "REQUIRED_TEST_CASE_COUNTS"
REFERENCES = "REQUIRED_SCOPE_REFERENCES"
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
        file = root / path
        resolved = file.resolve()
        if (
            not resolved.is_relative_to(root.resolve())
            or resolved != root.resolve() / path
            or not file.is_file()
        ):
            raise OSError
        return ast.parse(file.read_bytes())
    except (OSError, ValueError, SyntaxError, RuntimeError):
        raise RegistrationError(AuditReason.REGISTRATION_UNAVAILABLE) from None


class _Constants:
    def __init__(self, tree: ast.Module, shared: dict[str, str] | None = None) -> None:
        self.shared = shared
        self.central_import = False
        self.nodes: dict[str, ast.expr] = {}
        for node in tree.body:
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "scripts.verification_scope_materials"
            ):
                if (
                    self.central_import
                    or node.level
                    or len(node.names) != 1
                    or node.names[0].name != CENTRAL_NAME
                    or node.names[0].asname is not None
                    or shared is None
                ):
                    raise RegistrationError(AuditReason.INVALID_REGISTRATION)
                self.central_import = True
                continue
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
                if shared is not None and target.id == CENTRAL_NAME:
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
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == CENTRAL_NAME
            and self.central_import
            and self.shared is not None
        ):
            key = self._value(node.slice)
            if not isinstance(key, str) or key not in self.shared:
                raise RegistrationError(AuditReason.INVALID_REGISTRATION)
            return self.shared[key]
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


def _shared_materials(root: Path) -> dict[str, str] | None:
    file = root / CENTRAL_PATH
    if not file.exists() and not file.is_symlink():
        return None
    try:
        contained = file.resolve() == root.resolve() / CENTRAL_PATH and file.is_file()
    except (OSError, RuntimeError):
        contained = False
    if not contained:
        raise RegistrationError(AuditReason.INVALID_REGISTRATION)
    tree = _read_tree(root, CENTRAL_PATH)
    if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body):
        raise RegistrationError(AuditReason.UNSUPPORTED_REGISTRATION)
    constants = _Constants(tree)
    if constants.nodes.keys() != {CENTRAL_NAME}:
        raise RegistrationError(AuditReason.INVALID_REGISTRATION)
    raw = constants.get(CENTRAL_NAME)
    if (
        not isinstance(raw, dict)
        or not raw
        or parse_file_bindings(tuple(raw.items())) is None
    ):
        raise RegistrationError(AuditReason.INVALID_REGISTRATION)
    if CENTRAL_PATH in raw:
        raise RegistrationError(AuditReason.SELF_REFERENCE)
    return raw


def _writer_scope(
    root: Path, group: str, writer: str, shared: dict[str, str] | None
) -> Scope:
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
        references: object = ()
        for imported_path, aliases in imports.items():
            constants = _Constants(_read_tree(root, imported_path), shared)
            if imported_path == path and REFERENCES in constants.nodes:
                references = constants.get(REFERENCES)
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
                    entries = parse_file_bindings(raw)
                    if entries is not None and any(
                        p == CENTRAL_PATH
                        or (shared and p in shared and shared[p] != sha)
                        for p, sha in entries
                    ):
                        raise RegistrationError(AuditReason.INVALID_REGISTRATION)
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
        return Scope(group, path, bindings, counts, references=references)
    except RegistrationError as error:
        return Scope(group, writer, {}, errors=(error.reason,))


@dataclass(frozen=True)
class WriterPath:
    group: str
    path: str | None
    error: ValueError | None = None


def discover_writer_paths(implementation_root: Path) -> Iterator[WriterPath]:
    """从当前执行的 registry 发现 writer;调用者决定缺失/树外路径的处置。"""
    from scripts.a2_full_acceptance import acceptance_groups

    for group in acceptance_groups():
        source = inspect.getsourcefile(group.write)
        if source is None:
            yield WriterPath(group.name, None)
            continue
        try:
            path = Path(source).resolve().relative_to(implementation_root.resolve())
        except ValueError as error:
            yield WriterPath(group.name, None, error)
        else:
            yield WriterPath(group.name, path.as_posix())


def load_scopes(
    root: Path,
    *,
    writers: tuple[tuple[str, str], ...] | None = None,
) -> tuple[Scope, ...]:
    """正常导入生产 registry; 随后按 writer 导入解析清单 AST, 不 eval 清单。"""
    try:
        shared = _shared_materials(root)
    except RegistrationError as error:
        return tuple(
            Scope(group, writer, {}, errors=(error.reason,))
            for group, writer in (writers or (("registry", CENTRAL_PATH),))
        )
    if writers is None:
        writers_list = []
        for writer in discover_writer_paths(root):
            if writer.error is not None:
                raise writer.error
            if writer.path is None:
                return (
                    Scope(
                        writer.group,
                        "scripts",
                        {},
                        errors=(AuditReason.WRITER_UNAVAILABLE,),
                    ),
                )
            writers_list.append((writer.group, writer.path))
        writers = tuple(writers_list)
    scopes = tuple(
        _writer_scope(root, group, writer, shared) for group, writer in writers
    )
    # 保留局部 audit_scopes(root, (selected,)) 接口:未传入但本次已解析的
    # 上游是合法外部引用,局部图仅包含传入节点;未知引用仍受控拒绝。
    paths = frozenset(scope.path for scope in scopes if not scope.errors)
    return tuple(replace(scope, reference_registry=paths) for scope in scopes)
