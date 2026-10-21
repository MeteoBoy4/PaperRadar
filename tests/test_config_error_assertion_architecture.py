"""ConfigError 负例须匹配目标原因或绑定异常供后续断言。"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest


def _local_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    for child in ast.iter_child_nodes(scope):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        yield child
        yield from _local_nodes(child)


def _asserts_bound_error(
    statement: ast.With, binding: ast.Name, parents: dict[ast.AST, ast.AST]
) -> bool:
    """只跟踪同作用域后续赋值与断言, 不分析控制流或跨函数传播。"""
    scope: ast.AST = statement
    while scope in parents:
        scope = parents[scope]
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            break
    tracked = {binding.id}
    for node in sorted(_local_nodes(scope), key=lambda n: getattr(n, "lineno", 0)):
        if getattr(node, "lineno", 0) <= (statement.end_lineno or statement.lineno):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if node.value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {target.id for target in targets if isinstance(target, ast.Name)}
            derived = any(
                isinstance(reference, ast.Name) and reference.id in tracked
                for reference in ast.walk(node.value)
            )
            tracked.difference_update(names)
            if derived:
                tracked.update(names)
        elif isinstance(node, ast.Assert) and any(
            isinstance(reference, ast.Name) and reference.id in tracked
            for reference in ast.walk(node.test)
        ):
            return True
    return False


def config_error_assertion_violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    asserted_contexts = {
        item.context_expr
        for node in ast.walk(tree)
        if isinstance(node, ast.With)
        for item in node.items
        if isinstance(item.optional_vars, ast.Name)
        and _asserts_bound_error(node, item.optional_vars, parents)
    }
    violations = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest"
            and node.func.attr == "raises"
            and node.args
            and (
                (
                    isinstance(node.args[0], ast.Name)
                    and node.args[0].id == "ConfigError"
                )
                or (
                    isinstance(node.args[0], ast.Attribute)
                    and node.args[0].attr == "ConfigError"
                )
            )
            and not any(keyword.arg == "match" for keyword in node.keywords)
            and node not in asserted_contexts
        ):
            violations.append(f"{filename}:{node.lineno}")
    return violations


def test_bare_config_error_raises_reports_the_call_location() -> None:
    source = (
        "from paper_radar.config import ConfigError\n"
        "import pytest\n"
        "with pytest.raises(ConfigError):\n"
        "    compile_config()\n"
    )
    assert config_error_assertion_violations(source, "tests/example.py") == [
        "tests/example.py:3"
    ]


@pytest.mark.parametrize(
    "context",
    [
        'pytest.raises(ConfigError, match=r"^read\\.chunking_version：")',
        "pytest.raises(ConfigError) as error",
    ],
)
def test_constrained_config_error_raises_is_allowed(context: str) -> None:
    source = (
        f"with {context}:\n"
        "    compile_config()\n"
        'assert str(error.value).startswith("read.chunking_version：")\n'
    )
    assert config_error_assertion_violations(source, "tests/example.py") == []


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        ("pytest.raises(config.ConfigError)", ["tests/example.py:2"]),
        ('pytest.raises(config.ConfigError, match="field")', []),
        ("pytest.raises(config.ConfigError) as error", []),
        ("pytest.raises(ValueError)", []),
        ("other.raises(ConfigError)", []),
    ],
)
def test_module_attribute_errors_and_unrelated_calls(
    context: str, expected: list[str]
) -> None:
    source = (
        "from paper_radar import config\n"
        f"with {context}:\n"
        "    compile_config()\n"
        'assert str(error.value).startswith("read.chunking_version：")\n'
    )
    assert config_error_assertion_violations(source, "tests/example.py") == expected


def test_config_error_raises_in_tests_match_a_reason_or_bind_the_error() -> None:
    root = Path(__file__).resolve().parents[1]
    violations = [
        violation
        for path in sorted((root / "tests").rglob("*.py"))
        for violation in config_error_assertion_violations(
            path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()
        )
    ]
    assert not violations, (
        "ConfigError 负例须带 match= 或 as 绑定异常后断言：\n" + "\n".join(violations)
    )


@pytest.mark.parametrize(
    "following",
    [
        "",
        "assert unrelated\n",
        "error = None\nassert error\n",
        "def another_scope():\n    assert error.value\n",
    ],
)
def test_bound_error_requires_a_subsequent_assertion_on_that_error(
    following: str,
) -> None:
    source = (
        "with pytest.raises(ConfigError) as error:\n    compile_config()\n" + following
    )
    assert config_error_assertion_violations(source, "tests/example.py") == [
        "tests/example.py:1"
    ]


@pytest.mark.parametrize("block", ["if enabled:", "for operation in operations:"])
def test_bound_error_can_be_asserted_outside_a_block_through_its_message(
    block: str,
) -> None:
    source = (
        f"{block}\n"
        "    with pytest.raises(ConfigError) as error:\n"
        "        compile_config()\n"
        "message: str = str(error.value)\n"
        'assert message.startswith("read.chunking_version：")\n'
    )
    assert config_error_assertion_violations(source, "tests/example.py") == []
