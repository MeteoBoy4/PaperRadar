"""真实独立进程强杀的发布/事务边界, 不执行 Pi 或网络。"""

import sys
from pathlib import Path

import pytest

from paper_radar.pi_supply import SupplyError, list_supplies
from tests.artifact_support import paused_operation
from tests.pi_supply_support import inputs, prepare


@pytest.mark.parametrize(
    "prefix", ["INSERT INTO pi_supplies", "INSERT INTO pi_install_checks"]
)
def test_kill_after_tree_publication_never_creates_partial_success(
    tmp_path: Path, prefix: str
) -> None:
    source = inputs(tmp_path)
    code = (
        "from pathlib import Path;import sys;"
        "from tests.pi_supply_support import Download,Run,prepare;"
        "p=Path(sys.argv[1]);prepare(p,(p/'db.sqlite3',sys.argv[2],p/'request.json',Download(),Run()))"
    )
    with paused_operation(code, [str(tmp_path), source[1]], prefix) as process:
        published = tuple((tmp_path / "install").glob("[0-9a-f]*/[0-9a-f]*"))
        assert len(published) == 1
        process.kill()
        process.wait(timeout=15)
    assert list_supplies(source[0]) == ()
    prepared = prepare(tmp_path, source)
    assert list_supplies(source[0])[0].installs[0].path == published[0]
    assert list_supplies(source[0])[0].installs[0].install_id == prepared.install_id
    # 强杀残留不是本次 staging, 不自动删除。
    assert tuple((tmp_path / "install").glob(".staging-*"))


def test_kill_after_commit_keeps_complete_success_and_rejects_repeat(
    tmp_path: Path,
) -> None:
    from tests.a3_process_support import paused_subprocess

    source = inputs(tmp_path)
    code = """
from pathlib import Path
import sys
from tests.a3_process_support import checkpoint
from tests.pi_supply_support import Download, Run, prepare
original = Path.unlink
def unlink(path, *args, **kwargs):
    if path.name.startswith('.pending-'):
        checkpoint()
    return original(path, *args, **kwargs)
Path.unlink = unlink
p = Path(sys.argv[1])
prepare(p, (p/'db.sqlite3', sys.argv[2], p/'request.json', Download(), Run()))
"""
    with paused_subprocess(
        [sys.executable, "-c", code, str(tmp_path), source[1]],
        Path(__file__).parent / "deny_network",
        {},
        "未到提交屏障",
        "提前退出",
    ) as (process, _):
        process.kill()
        process.wait(timeout=15)
    records = list_supplies(source[0])
    assert len(records) == len(records[0].installs) == 1
    with pytest.raises(SupplyError, match="already_prepared_use_rebuild"):
        prepare(tmp_path, source)
