"""最终结论保留原字节格式、不可覆盖发布和失败清理。"""

from pathlib import Path

import pytest

from scripts.verification_publication import publish_conclusion


def test_publication_preserves_serialization_and_never_overwrites(
    tmp_path: Path,
) -> None:
    path = publish_conclusion(
        tmp_path, "same-run", ".extra.json", {"中文": "结论", "a": 1}
    )
    expected = '{\n  "a": 1,\n  "中文": "结论"\n}\n'.encode()
    assert path.read_bytes() == expected
    with pytest.raises(FileExistsError):
        publish_conclusion(tmp_path, "same-run", ".extra.json", {"a": 2})
    assert path.read_bytes() == expected
    assert set(tmp_path.iterdir()) == {path}


def test_failed_flush_leaves_no_conclusion_or_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    def fail_sync(_fd: int) -> None:
        raise OSError("synthetic write failure")

    monkeypatch.setattr(os, "fsync", fail_sync)
    with pytest.raises(OSError):
        publish_conclusion(tmp_path, "same-run", ".extra.json", {"status": "passed"})
    assert list(tmp_path.iterdir()) == []
