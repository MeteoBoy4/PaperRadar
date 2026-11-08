"""Independent E01 credentials metadata D1; all file bodies are synthetic."""

import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from scripts import issue167_live_signal_bundle as bundle
from scripts import issue167_live_signal_case as contract
from scripts import issue167_live_signal_worker as worker


@pytest.fixture(autouse=True)
def actual_generated_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "scripts.issue167_live_signal_cleanup"
    module = types.ModuleType(name)
    module.__file__ = "<sealed-synthetic-cleanup>"
    monkeypatch.setitem(sys.modules, name, module)
    exec(compile(bundle.cleanup_source(), module.__file__, "exec"), module.__dict__)


def directory(root: Path, *, cache_files: int = 2) -> Path:
    root.mkdir(mode=0o700, parents=True)
    for name in ("auth.json", "models-store.json", "exp2-installation-id"):
        (root / name).write_bytes(b"public synthetic sentinel")
        (root / name).chmod(0o600)
    cache = root / "node-compile-cache/v1"
    cache.mkdir(parents=True, mode=0o700)
    cache.parent.chmod(0o700)
    for i in range(cache_files):
        (cache / f"{i:04x}").write_bytes(b"synthetic bytecode sentinel")
        (cache / f"{i:04x}").chmod(0o600)
    return root


def snapshot(root: Path) -> dict[str, Any]:
    return worker.credential_snapshot(
        root, os.getuid(), os.getgid(), run_id=contract.RUN, phase="before"
    )


def test_ancestor_alias_between_check_and_open_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = directory(tmp_path / "parent/credentials")
    other = directory(tmp_path / "other/credentials")
    original = os.open
    injected = False

    def replace_parent(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal injected
        if (
            not injected
            and flags & os.O_DIRECTORY
            and (Path(path) == source or str(path) == "credentials")
        ):
            injected = True
            source.parent.rename(tmp_path / "old-parent")
            source.parent.symlink_to(other.parent, target_is_directory=True)
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", replace_parent)
    with pytest.raises(contract.CaseRejected, match="signal_auth_snapshot_unknown"):
        snapshot(source)
    assert injected


def test_regular_files_are_never_opened_and_only_four_metadata_values_exported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = directory(tmp_path / "credentials")
    original = os.open

    def directories_only(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        assert flags & os.O_DIRECTORY, "snapshot_opened_regular_file"
        return original(path, flags, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", directories_only)
        result = snapshot(source)
    body = result["snapshot"]
    assert body["integrity"] == "complete" and body["node_count"] == 8
    assert body["regular_contents_read"] is False
    assert body["marker_content_used_as_authority"] is False
    assert all(
        set(v) == {"inode", "size", "mtime_ns", "ctime_ns"}
        for v in body["nodes"].values()
    )
    assert len(json.dumps(body, sort_keys=True).encode()) <= 16384
    contract.validate_snapshot(body)


@pytest.mark.parametrize(
    "kind", ["unknown_top", "symlink", "hardlink", "special", "missing"]
)
def test_unknown_member_or_alias_blocks_without_regular_reads(
    tmp_path: Path, kind: str
) -> None:
    source = directory(tmp_path / "credentials")
    if kind == "unknown_top":
        (source / "unexpected").touch()
    elif kind == "symlink":
        (source / "node-compile-cache/v1/alias").symlink_to(source / "auth.json")
    elif kind == "hardlink":
        os.link(source / "auth.json", source / "node-compile-cache/v1/alias")
    elif kind == "special":
        os.mkfifo(source / "node-compile-cache/v1/fifo")
    else:
        (source / "exp2-installation-id").unlink()
    with pytest.raises(contract.CaseRejected, match="signal_auth_snapshot_unknown"):
        snapshot(source)


def test_count_and_depth_limits_are_not_truncated(tmp_path: Path) -> None:
    source = directory(tmp_path / "credentials", cache_files=59)
    with pytest.raises(contract.CaseRejected, match="signal_auth_snapshot_unknown"):
        snapshot(source)
    other = directory(tmp_path / "deep")
    (other / "node-compile-cache/a/b/c/d/e/f").mkdir(parents=True)
    with pytest.raises(contract.CaseRejected, match="signal_auth_snapshot_unknown"):
        snapshot(other)
