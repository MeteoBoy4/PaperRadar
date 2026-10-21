"""ConfigError 负例须匹配目标原因或绑定异常供后续断言。"""

import ast
from pathlib import Path

import pytest


def config_error_assertion_violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    bound_contexts = {
        item.context_expr
        for node in ast.walk(tree)
        if isinstance(node, ast.With)
        for item in node.items
        if item.optional_vars is not None
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
            and node not in bound_contexts
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
    assert not violations, "ConfigError 负例须带 match= 或 as 绑定异常：\n" + "\n".join(
        violations
    )
