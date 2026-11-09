"""开发期不可达扫描;补强直接引用,不声称分析任意动态 Python。"""

import ast
from pathlib import Path


def legacy_alias_reads(root: Path) -> tuple[str, ...]:
    findings: list[str] = []
    for source in sorted(root.rglob("*.py")):
        tree = ast.parse(source.read_text(), filename=str(source))
        for node in ast.walk(tree):
            direct = (
                isinstance(node, ast.Name)
                and node.id == "_evidence_for"
                and isinstance(node.ctx, ast.Load)
            ) or (
                isinstance(node, ast.Attribute)
                and node.attr == "_evidence_for"
                and isinstance(node.ctx, ast.Load)
            )
            constant_getattr = (
                isinstance(node, ast.Call)
                and (
                    (isinstance(node.func, ast.Name) and node.func.id == "getattr")
                    or (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "getattr"
                    )
                )
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "_evidence_for"
            )
            if isinstance(node, (ast.Name, ast.Attribute, ast.Call)) and (
                direct or constant_getattr
            ):
                findings.append(f"{source.relative_to(root)}:{node.lineno}")
    return tuple(findings)
