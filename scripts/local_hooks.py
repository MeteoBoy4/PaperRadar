"""显式管理本工具精确拥有的 pre-commit,不设置 hooksPath 或接管其他 hooks。"""

import subprocess
from pathlib import Path

HOOK_CONTENT = b"""#!/bin/sh
# PaperRadar managed check-local pre-commit v1
exec ./scripts/check-local --staged
"""


def manage_hook(root: Path, *, install: bool) -> str:
    configured = subprocess.run(
        ["git", "config", "--get-all", "core.hooksPath"],
        cwd=root,
        capture_output=True,
    )
    if configured.returncode == 0:
        raise ValueError(
            "hooks_path_conflict：已有 core.hooksPath；保持配置。"
            "请在现有 hook 手工调用 ./scripts/check-local --staged，"
            "或自行撤销配置后重试。"
        )
    if configured.returncode != 1:
        raise ValueError("git_config_error：无法读取 Git 配置；请检查仓库。")
    result = subprocess.run(
        [
            "git",
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "hooks/pre-commit",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    hook = Path(result.stdout.strip())
    if hook.is_symlink() or (hook.exists() and hook.read_bytes() != HOOK_CONTENT):
        raise ValueError(
            "hook_conflict：已有非本工具的 pre-commit；保持原文件。"
            "请手工集成 ./scripts/check-local --staged；不自动 chaining 或覆盖。"
        )
    if install:
        hook.parent.mkdir(parents=True, exist_ok=True)
        if not hook.exists():
            with hook.open("xb") as stream:
                stream.write(HOOK_CONTENT)
        hook.chmod(0o755)
        return "hook 已安装（重复安装幂等）；linked worktrees 共用此 hook。"
    if hook.exists():
        hook.unlink()
    return "hook 已卸载；未修改 Git 配置。"
