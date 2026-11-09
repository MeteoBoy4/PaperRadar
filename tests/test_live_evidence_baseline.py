"""认证/cache 接收基线只核成员元数据,不读取文件内容。"""

import os
from pathlib import Path

import pytest

from paper_radar.live_evidence.baseline import metadata_digest
from paper_radar.live_evidence.ledger import LedgerError


def test_baseline_detects_member_addition_with_no_content_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "auth"
    root.mkdir()
    (root / "secret").write_text("sensitive value")
    real_open = os.open

    def directories_only(
        path: Path | str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        assert flags & os.O_DIRECTORY, "不得打开凭据/cache成员的文件内容"
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", directories_only)
    before = metadata_digest((root,))
    assert metadata_digest((root,)) == before
    (root / "new-cache").write_text("another sensitive value")
    assert metadata_digest((root,)) != before


@pytest.mark.parametrize("change", ["mode", "rename", "replace", "symlink"])
def test_baseline_detects_metadata_changes_or_rejects_links(
    tmp_path: Path, change: str
) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    member = root / "member"
    member.write_text("hidden")
    before = metadata_digest((root,))
    if change == "mode":
        member.chmod(0o400)
    elif change == "rename":
        member.rename(root / "moved")
    elif change == "replace":
        member.rename(root / "old")
        member.write_text("hidden")
        (root / "old").unlink()
    else:
        member.unlink()
        member.symlink_to("/unreadable")
        with pytest.raises(LedgerError, match="binding_observation_unavailable"):
            metadata_digest((root,))
        return
    assert metadata_digest((root,)) != before
