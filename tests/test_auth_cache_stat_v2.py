"""固定 v2 基线只豁免获准对象的指定 stat 字段。"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from paper_radar.live_evidence.auth_cache_stat import metadata_digest
from paper_radar.live_evidence.baseline import metadata_digest as v1_digest
from paper_radar.live_evidence.ledger import LedgerError


def test_atomic_refresh_keeps_v2_baseline_and_does_not_upgrade_v1(
    tmp_path: Path,
) -> None:
    root = tmp_path / "credentials"
    root.mkdir(mode=0o700)
    for name in ("auth.json", "models-store.json", "exp2-installation-id"):
        (root / name).write_text("initial")
    old_v1, baseline = v1_digest((root,)), metadata_digest((root,))
    for name in ("auth.json", "models-store.json"):
        replacement = tmp_path / "replacement"
        replacement.write_text("longer refreshed value")
        os.replace(replacement, root / name)
        assert metadata_digest((root,)) == baseline
    assert v1_digest((root,)) != old_v1
    (root / "auth.json").write_text("content changed in place")
    assert metadata_digest((root,)) == baseline


def test_collection_and_current_binding_share_fixed_v2_invariants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.pi_execution import current_binding
    from paper_radar.pi_execution.admission import EvidenceBinding

    root = tmp_path / "credentials"
    root.mkdir(mode=0o700)
    (root / "auth.json").write_text("initial")
    (root / "exp2-installation-id").write_text("fixed")

    @contextmanager
    def install(*args: object) -> Iterator[SimpleNamespace]:
        yield SimpleNamespace(
            record=SimpleNamespace(
                manifest=SimpleNamespace(
                    node_version="22.0.0", expected_tree="a" * 64, pi_version="1.4.0"
                )
            )
        )

    monkeypatch.setattr(current_binding, "acquire_install", install)
    monkeypatch.setattr(current_binding, "site_binding_components", lambda: {})
    binding = EvidenceBinding(
        "supply",
        "install",
        "policy",
        "isolation",
        "cwd",
        "openai",
        "gpt-test",
        "low",
        "provider_default",
        None,
        None,
        "pi-rpc-1.4.0-v1",
        "chatgpt_subscription",
    )
    collected = current_binding.local_binding_components(
        tmp_path / "unused.db", binding, credentials_dir=root
    )
    (root / "auth.json").write_text("normal subscription refresh")
    current = current_binding.local_binding_components(
        tmp_path / "unused.db", binding, credentials_dir=root
    )
    assert current == collected
    assert collected[B.AUTH_CACHE_BASELINE] != v1_digest((root,))
    (root / "unexpected").write_text("not admitted")
    changed = current_binding.local_binding_components(
        tmp_path / "unused.db", binding, credentials_dir=root
    )
    assert changed[B.AUTH_CACHE_BASELINE] != collected[B.AUTH_CACHE_BASELINE]


@pytest.mark.parametrize(
    "change",
    [
        "add",
        "delete",
        "rename",
        "immutable-content",
        "immutable-replace",
        "immutable-time",
        "auth-mode",
        "root-mode",
        "directory",
        "nested-auth",
    ],
)
def test_unapproved_changes_never_rebase_the_fixed_baseline(
    tmp_path: Path, change: str
) -> None:
    root = tmp_path / "credentials"
    root.mkdir(mode=0o700)
    (root / "auth.json").write_text("initial")
    fixed = root / "exp2-installation-id"
    fixed.write_text("installation")
    registered = root / "registered"
    registered.mkdir()
    (registered / "auth.json").write_text("nested is immutable")
    baseline = metadata_digest((root,))
    if change == "add":
        (root / "new").write_text("unknown")
    elif change == "delete":
        fixed.unlink()
    elif change == "rename":
        fixed.rename(root / "renamed")
    elif change == "immutable-content":
        fixed.write_text("different installation")
    elif change == "immutable-replace":
        replacement = tmp_path / "replacement"
        replacement.write_text("installation")
        os.replace(replacement, fixed)
    elif change == "immutable-time":
        os.utime(fixed, ns=(1, 2))
    elif change == "auth-mode":
        (root / "auth.json").chmod(0o400)
    elif change == "root-mode":
        root.chmod(0o755)
    elif change == "directory":
        (root / "unregistered").mkdir()
    else:
        (registered / "auth.json").write_text("nested refresh is not exempt")
    assert metadata_digest((root,)) != baseline
    # 再次读取不能把变化重新解释成已批准成员。
    assert metadata_digest((root,)) != baseline


@pytest.mark.parametrize(
    "node", ["symlink", "hardlink", "fifo", "compile-cache", "auth-directory"]
)
def test_unsafe_member_shapes_are_rejected_without_content_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, node: str
) -> None:
    root = tmp_path / "credentials"
    root.mkdir()
    member = root / "auth.json"
    member.write_text("secret")
    if node == "symlink":
        member.unlink()
        member.symlink_to(tmp_path / "outside")
    elif node == "hardlink":
        os.link(member, tmp_path / "outside-link")
    elif node == "fifo":
        os.mkfifo(root / "fifo")
    elif node == "compile-cache":
        (root / "node-compile-cache").mkdir()
    else:
        member.unlink()
        member.mkdir()
    original = os.open

    def directories_only(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        assert flags & os.O_DIRECTORY, "credential content must never be opened"
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", directories_only)
    with pytest.raises(LedgerError, match="binding_observation_unavailable"):
        metadata_digest((root,))


@pytest.mark.parametrize("field", ["st_uid", "st_gid", "st_dev"])
def test_evolving_member_owner_group_and_device_are_not_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    from types import SimpleNamespace

    root = tmp_path / "credentials"
    root.mkdir()
    (root / "auth.json").write_text("synthetic")
    baseline = metadata_digest((root,))
    original = os.stat

    def changed(
        path: str | os.PathLike[str],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result | SimpleNamespace:
        info = original(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        if path == "auth.json":
            values = {
                key: getattr(info, key)
                for key in (
                    "st_dev",
                    "st_ino",
                    "st_mode",
                    "st_uid",
                    "st_gid",
                    "st_nlink",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                )
            }
            values[field] += 1
            return SimpleNamespace(**values)
        return info

    monkeypatch.setattr(os, "stat", changed)
    assert metadata_digest((root,)) != baseline


def test_concurrent_refresh_is_rejected_even_for_evolving_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "credentials"
    root.mkdir()
    member = root / "auth.json"
    member.write_text("initial")
    original = os.stat
    calls = 0

    def racing(
        path: str | os.PathLike[str],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal calls
        if path == "auth.json":
            calls += 1
            if calls == 2:
                member.write_text("concurrent refresh must be resampled")
        return original(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "stat", racing)
    with pytest.raises(LedgerError, match="observation_unavailable"):
        metadata_digest((root,))


@pytest.mark.parametrize("limit", ["MAX_DEPTH", "MAX_MEMBERS"])
def test_metadata_sampling_remains_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    from paper_radar.live_evidence import auth_cache_stat

    root = tmp_path / "credentials"
    root.mkdir()
    (root / "subdirectory").mkdir()
    monkeypatch.setattr(auth_cache_stat, limit, 0 if limit == "MAX_DEPTH" else 1)
    with pytest.raises(LedgerError, match="binding_observation_unavailable"):
        metadata_digest((root,))


@pytest.mark.parametrize("old_v1", [False, True])
def test_shared_admission_preserves_refresh_and_rejects_old_or_changed_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, old_v1: bool
) -> None:
    from paper_radar.live_evidence.types import BindingComponent as B
    from paper_radar.live_evidence.types import Capability
    from tests.screening_live_admission_support import (
        projected_admission,
        protected_admission,
    )

    root = tmp_path / "credentials"
    root.mkdir()
    (root / "auth.json").write_text("synthetic")
    components = {component: "a" * 64 for component in B}
    components[B.AUTH_CACHE_BASELINE] = (v1_digest if old_v1 else metadata_digest)(
        (root,)
    )
    _, _, components = protected_admission(
        tmp_path / "protected", monkeypatch, components=components
    )
    (root / "auth.json").write_text("refreshed synthetic")
    components[B.AUTH_CACHE_BASELINE] = metadata_digest((root,))
    projected = projected_admission(components, "boundary-low")
    assert projected.decision.executable is (not old_v1)
    for capability in (Capability.AUTH_CACHE_HISTORY, Capability.AUTH_CACHE_WRITER):
        disclosure = projected.decision.for_capability(capability)
        assert not disclosure.qualified
    if not old_v1:
        (root / "unexpected").write_text("unknown")
        components[B.AUTH_CACHE_BASELINE] = metadata_digest((root,))
        projected = projected_admission(components, "boundary-low")
        assert not projected.decision.executable
        affected = projected.decision.for_capability(Capability.AUTH_CACHE_BASELINE)
        assert not affected.qualified
        assert {reason.token for reason in affected.reasons} == {
            "binding_drift:auth_cache_baseline"
        }
        assert projected.decision.for_capability(Capability.RPC_EOF).qualified
