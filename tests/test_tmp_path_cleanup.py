"""通过独立 pytest 会话验证临时目录回收与权限恢复边界。"""

import os
import stat
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


def run_pytest(root: Path, temp_root: Path, *arguments: str) -> None:
    environment = dict(os.environ)
    environment.pop("PAPER_RADAR_TEST_RECEIPT", None)
    environment.pop("PAPER_RADAR_TEST_RUN_ID", None)
    environment["PYTEST_DEBUG_TEMPROOT"] = str(temp_root)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *arguments],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_readonly_pi_install_trees_allow_pytest_session_retention(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    temp_root = tmp_path / "sessions"
    temp_root.mkdir(mode=0o700)
    for _ in range(4):
        run_pytest(
            root,
            temp_root,
            "tests/test_pi_supply.py::"
            "test_prepare_freezes_materials_and_queries_without_network",
        )

    assert not list(temp_root.rglob("garbage-*"))
    assert all(
        path.lstat().st_mode & stat.S_IWUSR
        for path in temp_root.rglob("*")
        if stat.S_ISDIR(path.lstat().st_mode)
    )
    assert (
        len(
            [
                path
                for path in temp_root.glob("pytest-of-*/pytest-*")
                if not path.is_symlink()
            ]
        )
        == 3
    )


def isolated_suite(tmp_path: Path, source: str) -> tuple[Path, Path]:
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (suite / "conftest.py").write_bytes(
        Path(__file__).with_name("conftest.py").read_bytes()
    )
    (suite / "test_cleanup.py").write_text(dedent(source), encoding="utf-8")
    temp_root = tmp_path / "sessions"
    temp_root.mkdir(mode=0o700)
    return suite, temp_root


@pytest.mark.parametrize("dynamic", [False, True])
def test_teardown_restores_only_directory_owner_write_without_following_links(
    tmp_path: Path, dynamic: bool
) -> None:
    suite, temp_root = isolated_suite(
        tmp_path,
        "from pathlib import Path\n"
        f"def test_readonly_tree({'request' if dynamic else 'tmp_path'}):\n"
        + ("    tmp_path = request.getfixturevalue('tmp_path')\n" if dynamic else "")
        + "    suite = Path(__file__).parent\n"
        "    nested = tmp_path / 'tree' / 'nested'\n"
        "    nested.mkdir(parents=True)\n"
        "    payload = nested / 'payload'\n"
        "    payload.write_text('retained')\n"
        "    payload.chmod(0o444)\n"
        "    (nested / 'outside').symlink_to(suite / 'outside', "
        "target_is_directory=True)\n"
        "    (nested / 'file-link').symlink_to(suite / 'outside' / 'payload')\n"
        "    (nested / 'dangling').symlink_to(suite / 'missing')\n"
        "    (nested / 'cycle').symlink_to(tmp_path, target_is_directory=True)\n"
        "    nested.chmod(0o550)\n"
        "    nested.parent.chmod(0o555)\n"
        "    tmp_path.chmod(0o555)\n"
        "    assert nested.stat().st_mode & 0o777 == 0o550\n"
        "    assert tmp_path.stat().st_mode & 0o777 == 0o555\n"
        "    (suite / 'used-path').write_text(str(tmp_path))\n",
    )
    outside = suite / "outside"
    outside.mkdir()
    (outside / "payload").write_text("outside", encoding="utf-8")
    (outside / "payload").chmod(0o444)
    outside.chmod(0o555)

    run_pytest(suite, temp_root)

    used = Path((suite / "used-path").read_text())
    assert stat.S_IMODE(used.stat().st_mode) == 0o755
    assert stat.S_IMODE((used / "tree").stat().st_mode) == 0o755
    assert stat.S_IMODE((used / "tree/nested").stat().st_mode) == 0o750
    assert stat.S_IMODE((used / "tree/nested/payload").stat().st_mode) == 0o444
    assert (used / "tree/nested/payload").read_text() == "retained"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o555
    assert stat.S_IMODE((outside / "payload").stat().st_mode) == 0o444
    assert (outside / "payload").read_text() == "outside"


@pytest.mark.parametrize("replacement", ["deleted", "directory", "symlink", "file"])
def test_removed_or_replaced_tmp_path_is_left_untouched(
    tmp_path: Path, replacement: str
) -> None:
    suite, temp_root = isolated_suite(
        tmp_path,
        f"""
        from pathlib import Path

        def test_replace(tmp_path):
            suite = Path(__file__).parent
            (suite / "used-path").write_text(str(tmp_path))
            if {replacement!r} == "deleted":
                tmp_path.rmdir()
                return
            (tmp_path / "nested").mkdir()
            (tmp_path / "nested").chmod(0o555)
            tmp_path.rename(suite / "moved")
            (suite / "moved").chmod(0o555)
            if {replacement!r} == "directory":
                tmp_path.mkdir()
                tmp_path.chmod(0o550)
            elif {replacement!r} == "symlink":
                tmp_path.symlink_to(suite / "outside", target_is_directory=True)
            else:
                tmp_path.write_text("replacement")
                tmp_path.chmod(0o444)
        """,
    )
    outside = suite / "outside"
    outside.mkdir(mode=0o555)

    run_pytest(suite, temp_root)

    used = Path((suite / "used-path").read_text())
    assert stat.S_IMODE(outside.stat().st_mode) == 0o555
    if replacement == "deleted":
        assert not used.exists()
    else:
        assert stat.S_IMODE((suite / "moved").stat().st_mode) == 0o555
        assert stat.S_IMODE((suite / "moved/nested").stat().st_mode) == 0o555
        if replacement == "directory":
            assert stat.S_IMODE(used.stat().st_mode) == 0o550
        elif replacement == "symlink":
            assert used.is_symlink() and used.readlink() == outside
        else:
            assert stat.S_IMODE(used.stat().st_mode) == 0o444
            assert used.read_text() == "replacement"


def test_unused_tmp_path_does_not_create_temporary_directories(tmp_path: Path) -> None:
    suite, temp_root = isolated_suite(
        tmp_path, "def test_without_tmp_path():\n    pass\n"
    )

    run_pytest(suite, temp_root)

    assert list(temp_root.iterdir()) == []
