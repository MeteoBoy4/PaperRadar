"""两套新增纯规则守卫共用扫描形状,各自声明依赖政策。"""

import ast
from collections.abc import Set


def pure_dependency_violations(
    source: str,
    *,
    allowed_imports: Set[str],
    type_only_imports: Set[str] = frozenset(),
) -> list[str]:
    tree = ast.parse(source)
    type_only = {
        id(child)
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        for statement in node.body
        for child in ast.walk(statement)
    }
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "open",
        "vars",
    }
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.extend(
                alias.name for alias in node.names if alias.name not in allowed_imports
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level or (
                node.module not in allowed_imports
                and not (id(node) in type_only and node.module in type_only_imports)
            ):
                violations.append("." * node.level + (node.module or ""))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
        ):
            violations.append(node.func.id)
    return violations
