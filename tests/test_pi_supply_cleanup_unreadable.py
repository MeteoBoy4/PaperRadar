"""不可读的实际目录不能被静默当成完整空树。"""

from pathlib import Path

from paper_radar.pi_supply import (
    create_cleanup_plan,
    rebuild_supply,
    show_cleanup_plan,
    show_supply,
)
from tests.pi_supply_support import Run, inputs, prepare


def test_unreadable_subdirectories_make_tree_and_occupancy_unverifiable(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    instance = next(
        i
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    instance.path.chmod(0o755)
    unreadable = instance.path / "unreadable"
    unreadable.mkdir()
    (unreadable / "hidden").write_bytes(b"not an empty directory")
    staging = tmp_path / "install/.staging-unknown"
    staging.mkdir()
    private = staging / "unreadable"
    private.mkdir()
    (private / "hidden").write_bytes(b"not an empty residual")
    unreadable.chmod(0)
    private.chmod(0)
    try:
        plan = create_cleanup_plan(
            source[0],
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
        )
        item = next(i for i in plan.items if i.install_id == first.install_id)
        assert item.disposition == "unverifiable" and item.reason == "tree_invalid"
        assert item.actual_tree_hash is None and item.allocated_bytes is None
        assert plan.manual[0].allocated_bytes is None
        assert plan.manual[0].occupancy_reason == "tree_invalid"
        assert plan.occupancy_unknown and plan.candidates == ()
        assert (
            show_cleanup_plan(source[0], plan.plan_id).canonical_bytes
            == plan.canonical_bytes
        )
    finally:
        unreadable.chmod(0o700)
        private.chmod(0o700)
