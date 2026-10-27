"""开发期组合的公共选择与执行边界, 不发布验收结论。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_compatibility import select_tests

ROOT = Path(__file__).resolve().parents[1]


def test_union_preserves_order_and_executes_each_selection_once() -> None:
    acceptance = select_tests("acceptance")
    cli = select_tests("cli")
    union = select_tests("all")
    assert acceptance and cli
    assert set(union) == set(acceptance) | set(cli)
    assert len(union) == len(set(union))
    assert union[: len(acceptance)] == acceptance
    assert "tests/test_a10_entry.py" in acceptance
    assert "tests/test_verification_compatibility.py" in acceptance
    assert "tests/test_cli_help.py" in cli
    assert "tests/test_cli_import_compatibility.py" in cli


def test_developer_selection_documentation_is_generated_from_the_catalog() -> None:
    from scripts.check_compatibility import selection_documentation

    documentation = (ROOT / "docs/agents/testing.md").read_text()
    generated = documentation.split("<!-- compatibility-selections:start -->\n")[1]
    generated = generated.split("\n<!-- compatibility-selections:end -->")[0]
    assert generated == selection_documentation()


def _run_selection(
    root: Path, selections: tuple[str, ...], **extra_env: str
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, **extra_env)
    environment["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "from pathlib import Path; "
            "from scripts.check_compatibility import run_checks; "
            f"raise SystemExit(run_checks(Path({str(root)!r}), {selections!r}))",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize(
    ("selections", "reason"),
    [
        ((), "empty_selection"),
        (("test_missing.py",), "missing_module"),
        (("test_sample.py::test_missing",), "not found"),
        (("test_empty.py",), "empty_module"),
    ],
)
def test_empty_or_missing_selection_fails_without_running_other_tests(
    tmp_path: Path, selections: tuple[str, ...], reason: str
) -> None:
    (tmp_path / "test_sample.py").write_text("def test_exists(): pass\n")
    (tmp_path / "test_empty.py").write_text("# no tests\n")
    (tmp_path / "test_unselected.py").write_text(
        "raise AssertionError('full suite fallback')\n"
    )
    result = _run_selection(tmp_path, selections)
    assert result.returncode != 0
    assert reason in result.stdout + result.stderr
    assert "full suite fallback" not in result.stdout + result.stderr
    assert "耗时" in result.stdout and "结果：failed" in result.stdout


def test_runs_only_selected_unique_nodes_and_preserves_outer_receipt(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_sample.py").write_text(
        "import os\nfrom pathlib import Path\nimport pytest\n"
        "@pytest.mark.parametrize('value', [1, 2])\n"
        "def test_selected(value):\n"
        "    assert 'PAPER_RADAR_TEST_RECEIPT' not in os.environ\n"
        "    with Path('executed').open('a') as stream:\n"
        "        stream.write(str(value))\n"
    )
    (tmp_path / "test_unselected.py").write_text(
        "raise AssertionError('full suite fallback')\n"
    )
    receipt = tmp_path / "outer.pytest.json"
    receipt.write_bytes(b"outer unchanged\n")
    result = _run_selection(
        tmp_path,
        ("test_sample.py", "test_sample.py::test_selected", "test_sample.py"),
        PAPER_RADAR_TEST_RECEIPT=str(receipt),
        PAPER_RADAR_TEST_RUN_ID="outer",
        PYTEST_PLUGINS="missing_plugin",
        PYTEST_ADDOPTS="--collect-only -k never_matched",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "executed").read_text() == "12"
    assert "实际节点总数：2（已去重）" in result.stdout
    assert "2 passed" in result.stdout and "结果：passed" in result.stdout
    assert receipt.read_bytes() == b"outer unchanged\n"
    assert not (tmp_path / "verification-runs").exists()
    assert not (tmp_path / ".pytest_cache").exists()


@pytest.mark.parametrize(
    "body", ["assert False, 'selected failure'", "raise KeyboardInterrupt"]
)
def test_selected_failure_or_interruption_is_not_reported_as_success(
    tmp_path: Path, body: str
) -> None:
    (tmp_path / "test_sample.py").write_text(f"def test_selected(): {body}\n")
    result = _run_selection(tmp_path, ("test_sample.py",))
    assert result.returncode != 0
    assert "实际节点总数：1" in result.stdout
    assert "结果：failed" in result.stdout


def test_help_and_unknown_arguments_do_not_start_checks_or_write_files(
    tmp_path: Path,
) -> None:
    import shutil

    from scripts.check_compatibility import selection_documentation

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("check-compatibility", "check_compatibility.py", "__init__.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    environment = dict(os.environ)
    environment.update(
        UV_PROJECT_ENVIRONMENT=str(Path(sys.executable).parent.parent),
        PYTHONPATH=str(ROOT / "tests/deny_external_io"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    for arguments, expected_code in [(["--help"], 0), (["--unknown"], 2), ([], 2)]:
        result = subprocess.run(
            [str(scripts / "check-compatibility"), *arguments],
            cwd=tmp_path,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == expected_code, result.stdout + result.stderr
        assert "实际节点总数" not in result.stdout
        if expected_code == 0:
            assert selection_documentation() in result.stdout
            for word in ("副作用", "输出", "退出码", "未知参数", "不发布"):
                assert word in result.stdout
    assert before == sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
