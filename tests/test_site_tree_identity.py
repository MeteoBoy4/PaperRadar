"""root采集整树的fd读取模型;只使用临时公开合成树。"""

import os
from pathlib import Path

import pytest

from paper_radar.pi_supply.filesystem import tree_hash


def test_root_observation_reproduces_tree_v1_from_actual_files(tmp_path: Path) -> None:
    from paper_radar.live_evidence.site_tree import observe_tree

    (tmp_path / "app").mkdir()
    (tmp_path / "app/main.js").write_bytes(b"synthetic program\n")
    (tmp_path / "entry").symlink_to("app/main.js")
    before = observe_tree(tmp_path, product_uid=os.getuid())
    assert before == tree_hash(tmp_path)
    (tmp_path / "app/main.js").write_bytes(b"changed program\n")
    assert observe_tree(tmp_path, product_uid=os.getuid()) != before


@pytest.mark.parametrize("damage", ["external_link", "hardlink", "wrong_owner"])
def test_root_tree_never_opens_foreign_or_linked_file_contents(
    tmp_path: Path, damage: str
) -> None:
    from paper_radar.live_evidence.site_tree import observe_tree

    tree = tmp_path / "tree"
    tree.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"private-never-read")
    uid = os.getuid()
    if damage == "external_link":
        (tree / "link").symlink_to(outside)
    elif damage == "hardlink":
        os.link(outside, tree / "linked")
    else:
        (tree / "file").write_bytes(b"synthetic")
        uid += 1
    with pytest.raises(ValueError, match="tree_observation_untrusted"):
        observe_tree(tree, product_uid=uid)


def test_file_replaced_with_symlink_during_scan_is_rejected_without_following(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.site_tree import observe_tree

    tree = tmp_path / "tree"
    tree.mkdir()
    victim = tree / "program"
    victim.write_bytes(b"synthetic public program")
    outside = tmp_path / "outside"
    outside.write_bytes(b"private-never-read")
    original_open = os.open

    def raced_open(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if path == "program":
            victim.unlink()
            victim.symlink_to(outside)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", raced_open)
    with pytest.raises(ValueError, match="tree_observation_untrusted"):
        observe_tree(tree, product_uid=os.getuid())
