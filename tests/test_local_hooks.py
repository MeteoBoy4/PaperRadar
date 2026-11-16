"""D1: 隔离 Git 配置、临时仓库中的 hook 生命周期。"""

import shutil
import subprocess
from pathlib import Path

from tests.test_check_local import ROOT, git, invoke
from tests.test_check_local import git_root as git_root


def test_install_is_idempotent_and_uninstall_is_safe(git_root: Path) -> None:
    result = invoke(git_root, "install")
    assert result.returncode == 0, result.stdout + result.stderr
    hook = Path(
        git(git_root, "rev-parse", "--git-path", "hooks/pre-commit").stdout.strip()
    )
    if not hook.is_absolute():
        hook = git_root / hook
    original = hook.read_bytes()
    assert hook.stat().st_mode & 0o111
    assert invoke(git_root, "install").returncode == 0
    assert hook.read_bytes() == original
    hook.write_bytes(original + b"# user change\n")
    result = invoke(git_root, "uninstall")
    assert result.returncode == 1
    assert "hook_conflict" in result.stderr
    assert hook.read_bytes() == original + b"# user change\n"
    hook.write_bytes(original)
    assert invoke(git_root, "uninstall").returncode == 0
    assert not hook.exists()
    assert invoke(git_root, "uninstall").returncode == 0


def prepare_hook_repository(root: Path) -> None:
    for name in (
        "check-local",
        "check_local.py",
        "local_hooks.py",
        "live_document_links.py",
        "offline_evidence.py",
        "__init__.py",
    ):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    for name in ("pyproject.toml", "uv.lock", ".python-version", ".gitignore"):
        shutil.copy2(ROOT / name, root / name)
    package = root / "src/paper_radar"
    package.mkdir()
    (package / "__init__.py").write_text("")
    git(root, "add", ".")


def commit(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "commit", "-qm", "temporary offline check"],
        cwd=root,
        text=True,
        capture_output=True,
    )


def test_hook_blocks_bad_index_then_allows_commit_and_uninstall(git_root: Path) -> None:
    prepare_hook_repository(git_root)
    source = git_root / "src/example.py"
    source.write_bytes(b"import os\nx=1\n")
    git(git_root, "add", "src/example.py")
    source.write_bytes(b"x = 1\n")
    index = git(git_root, "diff", "--cached", "--binary").stdout
    assert invoke(git_root, "install").returncode == 0
    result = commit(git_root)
    assert result.returncode != 0
    assert "F401" in result.stdout + result.stderr
    assert git(git_root, "diff", "--cached", "--binary").stdout == index
    assert source.read_bytes() == b"x = 1\n"
    git(git_root, "add", "src/example.py")
    result = commit(git_root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "staged" in result.stdout + result.stderr
    assert invoke(git_root, "uninstall").returncode == 0
    source.write_bytes(b"import os\nx=1\n")
    git(git_root, "add", "src/example.py")
    assert commit(git_root).returncode == 0


def test_existing_hook_and_hooks_path_preserve_original_bytes(git_root: Path) -> None:
    hook = git_root / ".git/hooks/pre-commit"
    hook.parent.mkdir()
    original = b"#!/bin/sh\nexit 23\n"
    hook.write_bytes(original)
    result = invoke(git_root, "install")
    assert result.returncode == 1
    assert "hook_conflict" in result.stderr
    assert hook.read_bytes() == original
    hook.unlink()
    git(git_root, "config", "core.hooksPath", "custom-hooks")
    configuration = (git_root / ".git/config").read_bytes()
    result = invoke(git_root, "install")
    assert result.returncode == 1
    assert "hooks_path_conflict" in result.stderr
    assert (git_root / ".git/config").read_bytes() == configuration
    assert not hook.exists()


def test_linked_worktree_install_and_hook_invocation(git_root: Path) -> None:
    prepare_hook_repository(git_root)
    assert commit(git_root).returncode == 0
    linked = git_root.parent / (git_root.name + "-linked")
    try:
        git(git_root, "worktree", "add", "-qb", "linked-test", str(linked))
        assert (linked / ".git").is_file()
        assert invoke(linked, "install").returncode == 0
        (linked / "src/empty.py").write_text("x = 2\n")
        git(linked, "add", "src/empty.py")
        result = commit(linked)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "staged" in result.stdout + result.stderr
        assert invoke(linked, "uninstall").returncode == 0
    finally:
        git(git_root, "worktree", "remove", "--force", str(linked))
