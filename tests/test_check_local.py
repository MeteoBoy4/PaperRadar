"""D1: 轻量 CLI 的工作树与 staged 快照边界。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_local_document_links import document_tree

ROOT = Path(__file__).resolve().parents[1]


def invoke(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys; from pathlib import Path; "
            "from scripts.check_local import main; "
            "raise SystemExit(main(Path(sys.argv.pop(1))))",
            str(root),
            *args,
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        capture_output=True,
    )


def test_worktree_cli_reports_checks_and_preserves_bad_source(tmp_path: Path) -> None:
    document_tree(tmp_path, "# Valid\n[ok](#valid)\n")
    for name in ("src", "tests", "scripts"):
        (tmp_path / name).mkdir()
    bad = tmp_path / "src/example.py"
    bad.write_bytes(b"import os\nx=  1\n")
    result = invoke(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert all(name in result.stdout for name in ("format", "lint", "docs", "总耗时"))
    assert "F401" in result.stdout
    assert bad.read_bytes() == b"import os\nx=  1\n"
    assert not list(tmp_path.rglob("__pycache__"))
    assert not list(tmp_path.rglob(".ruff_cache"))


@pytest.fixture
def git_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache/uv"))
    home = tmp_path / "private-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("UV_CACHE_DIR", cache)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    monkeypatch.delenv("GIT_CONFIG_PARAMETERS", raising=False)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(key, raising=False)
    git(tmp_path, "-c", "init.templateDir=", "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Offline Test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    document_tree(tmp_path, "# Valid\n[ok](#valid)\n")
    for name in ("src", "tests", "scripts"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "empty.py").write_text("")
    return tmp_path


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )


@pytest.mark.parametrize("index_bad", [True, False])
def test_staged_checks_index_independently_of_worktree(
    git_root: Path, index_bad: bool
) -> None:
    source = git_root / "src/example.py"
    bad, good = b"import os\nx=1\n", b"x = 1\n"
    source.write_bytes(bad if index_bad else good)
    git(git_root, "add", "README.md", "src", "tests", "scripts", "docs")
    source.write_bytes(good if index_bad else bad)
    index_before = git(git_root, "ls-files", "--stage", "-z").stdout
    index_bytes = (git_root / ".git/index").read_bytes()
    result = invoke(git_root, "--staged")
    assert result.returncode == int(index_bad), result.stdout + result.stderr
    assert "staged" in result.stdout
    assert source.read_bytes() == (good if index_bad else bad)
    assert git(git_root, "ls-files", "--stage", "-z").stdout == index_before
    assert (git_root / ".git/index").read_bytes() == index_bytes


def test_staged_document_cannot_use_unstaged_target(git_root: Path) -> None:
    (git_root / "README.md").write_text("[new](target.md)\n")
    git(git_root, "add", "README.md", "src", "tests", "scripts", "docs")
    (git_root / "target.md").write_text("# Present only in worktree\n")
    assert invoke(git_root).returncode == 0
    result = invoke(git_root, "--staged")
    assert result.returncode == 1
    assert "README.md:1 -> target.md: missing_target" in result.stdout


def test_help_and_checks_deny_external_io(
    git_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "tests/deny_external_io"))
    monkeypatch.setenv("PAPER_RADAR_TEST_RECEIPT", str(git_root / "must-not-exist"))
    result = invoke(git_root, "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "用法：" in result.stdout
    assert "uv run --offline --locked" in result.stdout
    result = invoke(git_root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (git_root / "must-not-exist").exists()
    assert not (git_root / "verification-runs").exists()


def test_missing_uv_is_controlled(
    git_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "/missing-tools")
    result = invoke(git_root)
    assert result.returncode == 1
    assert "launch_error" in result.stderr
    assert "uv run --offline --locked" in result.stderr
    assert "Traceback" not in result.stderr
