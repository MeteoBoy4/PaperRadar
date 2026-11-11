"""D1: reviewed install recovery windows at the existing host/filesystem seams."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.live_evidence.collection import ProtectedCollection
from paper_radar.live_evidence.deployment import file_digests
from paper_radar.live_evidence.live_install import json_bytes, publish
from paper_radar.live_evidence.normal_auth_refresh import epoch_path, read_epoch
from tests.test_live_apparmor_lifecycle import lifecycle, policy_root
from tests.test_live_epoch_upgrade import UpgradeCase
from tests.test_live_epoch_upgrade import source_root as source_root
from tests.test_live_epoch_upgrade import upgrade as upgrade
from tests.test_live_resources_replacement import pending


def ledger_bytes(root: Path) -> dict[str, bytes | str]:
    return {
        path.relative_to(root).as_posix(): (
            str(path.readlink()) if path.is_symlink() else path.read_bytes()
        )
        for path in root.rglob("*")
        if path.is_symlink() or path.is_file()
    }


def test_rechecking_prepared_policy_keeps_original_phase_on_probe_failure(
    tmp_path: Path,
) -> None:
    gate, boundary = lifecycle(policy_root(tmp_path / "root"), tmp_path / "ledger")
    gate.prepare(lambda: None)
    original = gate.journal.read_bytes()
    inode = gate.journal.stat().st_ino
    writes = list(boundary.writes)

    def refused() -> None:
        raise ValueError("review_probe_refused")

    with pytest.raises(ValueError, match=r"^review_probe_refused$"):
        gate.prepare(refused)
    assert gate.journal.read_bytes() == original
    assert gate.journal.stat().st_ino == inode
    assert boundary.writes == writes
    gate.verify()
    seen = []
    gate.prepare(lambda: seen.append("probe"))
    assert seen == ["probe"]
    assert gate.journal.read_bytes() == original
    assert gate.journal.stat().st_ino == inode


@pytest.mark.parametrize("damage", ["bytes", "partial"])
def test_prepared_phase_does_not_mask_real_kernel_drift(
    tmp_path: Path, damage: str
) -> None:
    gate, boundary = lifecycle(policy_root(tmp_path / "root"), tmp_path / "ledger")
    gate.prepare(lambda: None)
    original = gate.journal.read_bytes()
    writes = list(boundary.writes)
    if damage == "bytes":
        boundary.profiles["0"]["raw_data"] = b"unknown keep"
    else:
        del boundary.profiles["0"]
    seen = []
    reason = (
        "apparmor_blob_mismatch" if damage == "bytes" else "apparmor_partial_policy"
    )
    with pytest.raises(ValueError, match="^" + reason + "$"):
        gate.prepare(lambda: seen.append("probe"), recover=True)
    assert seen == []
    assert gate.journal.read_bytes() == original
    assert boundary.writes == writes


def test_prepared_revalidation_preserves_unknown_pending_policy_marker(
    tmp_path: Path,
) -> None:
    gate, boundary = lifecycle(policy_root(tmp_path / "root"), tmp_path / "ledger")
    gate.prepare(lambda: None)
    original = gate.journal.read_bytes()
    pending_marker = gate.journal.with_name(gate.journal.name + ".new")
    pending_marker.write_bytes(b"unknown keep")
    writes = list(boundary.writes)
    seen = []
    with pytest.raises(ValueError, match=r"^placement_policy_journal_identity$"):
        gate.prepare(lambda: seen.append("probe"), recover=True)
    assert seen == []
    assert gate.journal.read_bytes() == original
    assert pending_marker.read_bytes() == b"unknown keep"
    assert boundary.writes == writes


@pytest.mark.parametrize("failure", ["native_preflight", "traced_preflight"])
def test_failed_installed_preparation_preserves_old_deployment(
    upgrade: UpgradeCase,
    failure: str,
) -> None:
    paths = upgrade.paths
    target = paths.ledger / "inbox/placement-target-v1.json"
    target.write_bytes(b"model-host current old target\n")
    journal = paths.journal.read_bytes()
    runtime = file_digests(paths.runtime)
    ledger = file_digests(paths.ledger)
    resources = {
        path: path.read_bytes()
        for path in (
            paths.sudoers,
            paths.resolver,
            *paths.executables.glob("live-evidence-*"),
            *paths.units.iterdir(),
        )
        if path.is_file()
    }
    upgrade.host.calls.clear()
    upgrade.host.fail = failure
    with pytest.raises(ValueError, match=r"^model_interruption$"):
        upgrade.deployment.install()
    assert paths.journal.read_bytes() == journal
    assert file_digests(paths.runtime) == runtime
    assert {path: path.read_bytes() for path in resources} == resources
    # This fixture shares the exact prepared policy; even that journal stays unchanged.
    assert file_digests(paths.ledger) == ledger
    assert not tuple(paths.ledger.glob("deployment-v2-history-*.json"))
    assert not tuple(paths.runtime.parent.glob(paths.runtime.name + ".archive-*"))
    assert "disable_observation" not in upgrade.host.calls
    assert "stop_and_remove" not in upgrade.host.calls
    assert upgrade.host.installed
    upgrade.host.fail = None
    assert upgrade.deployment.install(recover=True) == "installed"
    assert epoch_path(upgrade.ledger, upgrade.old).read_bytes() == upgrade.old_epoch
    assert (
        read_epoch(upgrade.ledger, upgrade.new).deployed_at
        == upgrade.descriptor.deployed_at
    )
    assert (
        ProtectedCollection(upgrade.ledger).status(
            upgrade.old.negative_plan.plan_id, now=datetime.now(UTC)
        )
        == upgrade.status
    )


def test_full_old_target_probe_precedes_first_history_write(
    upgrade: UpgradeCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = upgrade.paths
    journal = paths.journal.read_bytes()
    old = json.loads(journal)
    history = paths.journal.with_name(
        "deployment-v2-history-" + old["payload"] + ".json"
    )
    link = os.link
    observed = False
    upgrade.host.calls.clear()

    def checked_link(src: Path, dst: Path, *, follow_symlinks: bool = True) -> None:
        nonlocal observed
        if dst == history:
            observed = True
            assert paths.journal.read_bytes() == journal
            assert upgrade.host.installed
            assert upgrade.host.calls.count("native_preflight") == 1
            assert upgrade.host.calls.count("traced_preflight") == 1
            assert "disable_observation" not in upgrade.host.calls
        link(src, dst, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "link", checked_link)
    assert upgrade.deployment.install() == "installed"
    assert observed


def test_installed_history_publication_interruption_resumes_exact_history(
    upgrade: UpgradeCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = upgrade.paths
    journal = paths.journal.read_bytes()
    state = json.loads(journal)
    history = paths.journal.with_name(
        "deployment-v2-history-" + state["payload"] + ".json"
    )
    fsync = os.fsync
    fired = False

    def interrupted(fd: int) -> None:
        nonlocal fired
        fsync(fd)
        if (
            not fired
            and history.exists()
            and not history.with_suffix(".json.new").exists()
        ):
            fired = True
            raise OSError("review crash after history publication")

    monkeypatch.setattr(os, "fsync", interrupted)
    with pytest.raises(OSError, match=r"^review crash after history publication$"):
        upgrade.deployment.install()
    assert fired and paths.journal.read_bytes() == journal
    assert history.read_bytes() == journal and history.stat().st_nlink == 1
    database = upgrade.ledger.database.read_bytes()
    received = upgrade.ledger.list_received()
    assert upgrade.deployment.install(recover=True) == "installed"
    assert history.read_bytes() == journal and history.stat().st_nlink == 1
    assert upgrade.ledger.database.read_bytes() == database
    assert upgrade.ledger.list_received() == received
    assert epoch_path(upgrade.ledger, upgrade.old).read_bytes() == upgrade.old_epoch
    assert (
        read_epoch(upgrade.ledger, upgrade.new).deployed_at
        == upgrade.descriptor.deployed_at
    )
    assert (
        ProtectedCollection(upgrade.ledger).status(
            upgrade.old.negative_plan.plan_id, now=datetime.now(UTC)
        )
        == upgrade.status
    )
    assert (
        upgrade.status.network_remaining == 40 and upgrade.status.model_remaining == 40
    )


@pytest.mark.parametrize(
    "change",
    [
        "bytes",
        "noncanonical",
        "directory",
        "symlink",
        "hardlink",
        "pending",
        "pending_only",
        "archive",
        "implicit",
    ],
)
def test_existing_history_is_reused_only_when_exact_and_explicit(
    upgrade: UpgradeCase,
    change: str,
) -> None:
    paths = upgrade.paths
    journal = paths.journal.read_bytes()
    old = json.loads(journal)
    history = paths.journal.with_name(
        "deployment-v2-history-" + old["payload"] + ".json"
    )
    if change == "directory":
        history.mkdir()
    elif change == "symlink":
        history.symlink_to(paths.journal)
    else:
        publish(history, journal)
        if change == "bytes":
            history.write_bytes(json_bytes({**old, "phase": "resources"}))
        elif change == "noncanonical":
            history.write_text(json.dumps(old, indent=2))
        elif change == "hardlink":
            os.link(history, history.with_name("unrelated-link"))
        elif change in {"pending", "pending_only"}:
            history.with_name(history.name + ".new").write_bytes(b"unknown keep")
            if change == "pending_only":
                history.unlink()
        elif change == "archive":
            paths.runtime.with_name(
                paths.runtime.name + ".archive-" + old["payload"]
            ).mkdir()
    before = ledger_bytes(paths.ledger)
    runtime = file_digests(paths.runtime)
    upgrade.host.calls.clear()
    with pytest.raises(ValueError, match=r"^(archive_conflict|protected_identity)$"):
        upgrade.deployment.install(recover=change != "implicit")
    assert ledger_bytes(paths.ledger) == before
    assert file_digests(paths.runtime) == runtime
    assert upgrade.host.installed
    assert "native_preflight" not in upgrade.host.calls
    assert "disable_observation" not in upgrade.host.calls


@pytest.mark.parametrize("known_history", [False, True])
def test_resources_prepares_once_before_retirement_and_reuses_known_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, known_history: bool
) -> None:
    deployment, host, journal, _runtime = pending(tmp_path, monkeypatch)
    paths = deployment.paths
    old = json.loads(journal)
    history = paths.journal.with_name(
        "deployment-v2-history-" + old["payload"] + ".json"
    )
    inode = None
    if known_history:
        publish(history, journal)
        inode = history.stat().st_ino
    unlink = Path.unlink
    observed = False
    host.calls.clear()

    def checked_unlink(path: Path, missing_ok: bool = False) -> None:
        nonlocal observed
        if path == paths.executables / "live-evidence-collect":
            observed = True
            assert host.calls.count("native_preflight") == 1
            assert history.read_bytes() == journal
            if inode is not None:
                assert history.stat().st_ino == inode
        unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", checked_unlink)
    assert deployment.install(recover=True) == "installed"
    assert observed and history.read_bytes() == journal
    assert not history.with_name(history.name + ".new").exists()


@pytest.mark.parametrize(
    "change",
    [
        "bytes",
        "noncanonical",
        "directory",
        "symlink",
        "hardlink",
        "pending",
        "pending_only",
    ],
)
def test_resources_rejects_unknown_history_before_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    deployment, host, journal, runtime = pending(tmp_path, monkeypatch)
    paths = deployment.paths
    old = json.loads(journal)
    history = paths.journal.with_name(
        "deployment-v2-history-" + old["payload"] + ".json"
    )
    if change == "directory":
        history.mkdir()
    elif change == "symlink":
        history.symlink_to(paths.journal)
    else:
        publish(history, journal)
        if change == "bytes":
            history.write_bytes(b"unknown keep")
        elif change == "noncanonical":
            history.write_text(json.dumps(old, indent=2))
        elif change == "hardlink":
            os.link(history, history.with_name("unrelated-link"))
        elif change in {"pending", "pending_only"}:
            history.with_name(history.name + ".new").write_bytes(b"unknown keep")
            if change == "pending_only":
                history.unlink()
    before = ledger_bytes(paths.ledger)
    resources = {path: path.read_bytes() for path in (paths.sudoers, paths.resolver)}
    host.calls.clear()
    with pytest.raises(
        ValueError, match=r"^(resources_history_identity|protected_identity)$"
    ):
        deployment.install(recover=True)
    assert ledger_bytes(paths.ledger) == before
    assert file_digests(paths.runtime) == runtime
    assert {path: path.read_bytes() for path in resources} == resources
    assert "native_preflight" not in host.calls
    assert "disable_observation" not in host.calls
