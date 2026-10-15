"""A2-09 合成 Profile 与真实 SQLite 事实检查。"""

from __future__ import annotations

import os
import select
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Connection, Engine, event


def profile_inputs(root: Path, *, version: str = "profile-v1") -> Path:
    folder = root / "config/profiles"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{version}.yaml").write_text(
        f"version: {version}\n"
        "background: PRIVATE_PROFILE_MARKER\n"
        "core_questions: Monsoon variability\n"
        "transferable_methods: Bayesian inference\n"
        "available_data_and_tools: Reanalysis\n"
        "theory_and_cognitive_interests: Causal mechanisms\n"
        "constraints_and_exclusions: No proprietary data\n",
        encoding="utf-8",
    )
    settings = root / "config/settings.yaml"
    settings.write_text(f"profile: {version}\n", encoding="utf-8")
    return settings


def recovery_inputs(root: Path) -> tuple[Path, Path]:
    """为恢复场景追加 Profile 与 Prompt 两种 v2 材料。"""
    settings = profile_inputs(root, version="profile-v2")
    prompt = root / "prompts/screening/boundary-v2.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_bytes(b"PRIVATE_PROMPT_MARKER\n")
    settings.write_text(
        "profile: profile-v2\nprompts:\n  boundary: v2\n", encoding="utf-8"
    )
    return settings, prompt


def config_facts(database: Path) -> tuple[list[tuple[object, ...]], ...]:
    """重开独立连接观察全部提交事实及字节与创建时间。"""
    with sqlite3.connect(database) as connection:
        return tuple(
            connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2, 3").fetchall()
            for table in (
                "config_versions",
                "runtime_config_snapshots",
                "snapshot_version_refs",
            )
        )


@contextmanager
def before_sql(prefix: str, action: Callable[[Connection], None]) -> Iterator[None]:
    """只控制真实数据库执行边界。不替换 repository 或事务。"""

    def control(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.startswith(prefix):
            action(connection)

    event.listen(Engine, "before_cursor_execute", control)
    try:
        yield
    finally:
        event.remove(Engine, "before_cursor_execute", control)


@contextmanager
def paused_compile(
    settings: Path, database: Path, *, pause_at: str
) -> Iterator[tuple[subprocess.Popen[str], int]]:
    """管道握手固定执行位置。无 sleep、轮询或生产代码中的测试钩子。"""
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()
    process = subprocess.Popen(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "config",
            "compile",
            "--settings",
            str(settings),
            "--database",
            str(database),
        ],
        cwd=settings.parent.parent,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "config_transaction_process"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "PAPER_RADAR_TEST_PAUSE_AT": pause_at,
            "PAPER_RADAR_TEST_READY_FD": str(ready_write),
            "PAPER_RADAR_TEST_RELEASE_FD": str(release_read),
        },
        pass_fds=(ready_write, release_read),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    os.close(ready_write)
    os.close(release_read)
    try:
        readable, _, _ = select.select([ready_read], [], [], 15)
        assert readable, "编译子进程未到达测试屏障"
        assert os.read(ready_read, 1) == b"R", "编译子进程提前退出"
        yield process, release_write
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
        os.close(ready_read)
        os.close(release_write)
