"""检查 ConfigError 负例的 match 或绑定后断言形式。

支持显式导入别名与局部简单赋值。只区分 if/else 互斥分支与后续绑定覆盖,
不做一般控制流、导入名遮蔽或跨函数分析。仅泄漏断言也能通过本形式检查;
受控字段路径或错误类别是否得到验证仍须人工审查。
"""

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


def _if_branches(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> dict[ast.If, bool]:
    branches = {}
    while node in parents:
        parent = parents[node]
        if isinstance(parent, ast.If):
            branches[parent] = node in parent.body
        node = parent
    return branches


def _asserts_bound_error(
    statement: ast.With, binding: ast.Name, parents: dict[ast.AST, ast.AST]
) -> bool:
    """只跟踪同作用域后续赋值、with 绑定与断言。"""
    scope: ast.AST = statement
    while scope in parents:
        scope = parents[scope]
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            break
    tracked = {binding.id}
    branches = _if_branches(statement, parents)
    for node in sorted(_local_nodes(scope), key=lambda n: getattr(n, "lineno", 0)):
        if getattr(node, "lineno", 0) <= (statement.end_lineno or statement.lineno):
            continue
        later_branches = _if_branches(node, parents)
        if any(
            later_branches.get(parent, branch) != branch
            for parent, branch in branches.items()
        ):
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
        elif isinstance(node, ast.With):
            tracked.difference_update(
                item.optional_vars.id
                for item in node.items
                if isinstance(item.optional_vars, ast.Name)
            )
        elif isinstance(node, ast.Assert) and any(
            isinstance(reference, ast.Name) and reference.id in tracked
            for reference in ast.walk(node.test)
        ):
            return True
    return False


def config_error_assertion_violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    pytest_modules = {"pytest"}
    raises_functions: set[str] = set()
    config_errors = {"ConfigError"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            pytest_modules.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "pytest"
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module == "pytest":
                raises_functions.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "raises"
                )
            elif node.module in {"paper_radar.config", "paper_radar.config.errors"}:
                config_errors.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "ConfigError"
                )
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
            and (
                (isinstance(node.func, ast.Name) and node.func.id in raises_functions)
                or (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in pytest_modules
                    and node.func.attr == "raises"
                )
            )
            and node.args
            and (
                (
                    isinstance(node.args[0], ast.Name)
                    and node.args[0].id in config_errors
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


@pytest.mark.parametrize(
    ("imports", "context", "expected"),
    [
        (
            "from pytest import raises\nfrom paper_radar.config import ConfigError\n",
            "raises(ConfigError)",
            ["tests/example.py:3"],
        ),
        (
            "import pytest as pt\nfrom paper_radar.config import ConfigError\n",
            "pt.raises(ConfigError)",
            ["tests/example.py:3"],
        ),
        (
            "import pytest\nfrom paper_radar.config import ConfigError as CE\n",
            "pytest.raises(CE)",
            ["tests/example.py:3"],
        ),
        (
            "from pytest import raises as expect\n"
            "from paper_radar.config import ConfigError as CE\n",
            'expect(CE, match="field")',
            [],
        ),
        (
            "import pytest as pt\n"
            "from paper_radar.config.errors import ConfigError as CE\n",
            "pt.raises(CE) as error",
            [],
        ),
    ],
)
def test_explicit_import_aliases_keep_the_config_error_constraint(
    imports: str, context: str, expected: list[str]
) -> None:
    source = (
        imports
        + f"with {context}:\n"
        + "    compile_config()\n"
        + 'assert str(error.value).startswith("field：")\n'
    )
    assert config_error_assertion_violations(source, "tests/example.py") == expected


def test_rebinding_an_error_cannot_borrow_the_later_error_assertion() -> None:
    source = (
        "with pytest.raises(ConfigError) as error:\n"
        "    first_operation()\n"
        "with pytest.raises(ConfigError) as error:\n"
        "    second_operation()\n"
        'assert str(error.value).startswith("second.field：")\n'
    )
    assert config_error_assertion_violations(source, "tests/example.py") == [
        "tests/example.py:1"
    ]


def test_alternative_branches_can_share_an_error_assertion() -> None:
    source = (
        "if enabled:\n"
        "    with pytest.raises(ConfigError) as error:\n"
        "        first_operation()\n"
        "else:\n"
        "    with pytest.raises(ConfigError) as error:\n"
        "        second_operation()\n"
        'assert str(error.value).startswith("field：")\n'
    )
    assert config_error_assertion_violations(source, "tests/example.py") == []


def test_saved_error_can_be_asserted_after_the_capture_name_is_reused() -> None:
    source = (
        "with pytest.raises(ConfigError) as error:\n"
        "    first_operation()\n"
        "first = error\n"
        "with pytest.raises(ConfigError) as error:\n"
        "    second_operation()\n"
        'assert str(first.value).startswith("first.field：")\n'
        'assert str(error.value).startswith("second.field：")\n'
    )
    assert config_error_assertion_violations(source, "tests/example.py") == []
