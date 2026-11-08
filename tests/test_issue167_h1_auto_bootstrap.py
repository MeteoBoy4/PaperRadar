"""Unbound D1 bootstrap validation; no sudo/root install/exec."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts.issue167_h1_auto_bootstrap import (
    BootstrapRejected,
    read_member,
    source_bytes,
)
from scripts.issue167_h1_phase import Plan


def source(tmp_path: Path) -> tuple[Path, str, Plan]:
    root = tmp_path / "source"
    root.mkdir(mode=0o700)
    plan = Plan("7c93ab04d615", os.getuid(), os.getgid())
    files = {
        name: b"synthetic-code-only"
        for name in (
            "synthetic-python",
            "issue167_h1_owner_run.py",
            "issue167_h1_owner_ops.py",
            "issue167_h1_guardian.py",
            "issue167_h1_phase.py",
            "issue167_h1_network_worker.py",
            "host-context.json",
            "retry-context.json",
        )
    }
    files["plan.json"] = plan.to_json().encode()
    for name, raw in files.items():
        (root / name).write_bytes(raw)
        (root / name).chmod(0o644)
    manifest = {
        "kind": "h1_synthetic_local_review",
        "members": {
            name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()
        },
        "tools": {},
    }
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    (root / "manifest.json").chmod(0o644)
    return root, hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(), plan


def test_all_bytes_validated_before_any_install(tmp_path: Path) -> None:
    root, sha, plan = source(tmp_path)
    data, target = source_bytes(root, sha, os.getuid(), os.getgid())
    assert target == plan.install_root
    assert set(data) == set(
        json.loads((root / "manifest.json").read_text())["members"]
    ) | {"manifest.json"}
    assert data["plan.json"] == plan.to_json().encode()
    assert not (root / "results").exists()


@pytest.mark.parametrize("mutation", ["digest", "symlink", "hardlink", "mode", "owner"])
def test_changed_or_unsafe_member_never_becomes_root_input(
    tmp_path: Path, mutation: str
) -> None:
    root, sha, _plan = source(tmp_path)
    member = root / "issue167_h1_phase.py"
    uid = os.getuid()
    if mutation == "digest":
        member.write_bytes(b"changed")
    elif mutation == "symlink":
        member.unlink()
        member.symlink_to(root / "synthetic-python")
    elif mutation == "hardlink":
        os.link(member, root / "additional-link")
    elif mutation == "mode":
        member.chmod(0o666)
    else:
        uid += 1
    with pytest.raises((BootstrapRejected, OSError)):
        source_bytes(root, sha, uid, os.getgid())


def test_pinned_manifest_and_duplicate_fields_cannot_be_substituted(
    tmp_path: Path,
) -> None:
    root, sha, _plan = source(tmp_path)
    (root / "manifest.json").write_text('{"kind":"a","kind":"b"}')
    with pytest.raises(BootstrapRejected, match=r"^manifest_changed$"):
        source_bytes(root, sha, os.getuid(), os.getgid())
    altered = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    with pytest.raises(BootstrapRejected, match=r"^duplicate_key$"):
        source_bytes(root, altered, os.getuid(), os.getgid())


def test_fd_relative_names_and_size_bound_precede_read(tmp_path: Path) -> None:
    (tmp_path / "large").write_bytes(b"x" * 9)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(BootstrapRejected, match=r"^member_name_invalid$"):
            read_member(fd, "../outside", os.getuid(), 10)
        with pytest.raises(BootstrapRejected, match=r"^source_metadata_invalid$"):
            read_member(fd, "large", os.getuid(), 8)
    finally:
        os.close(fd)
