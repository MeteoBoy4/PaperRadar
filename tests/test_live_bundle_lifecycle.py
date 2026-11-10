"""真实生命周期状态机+显式宿主I/O替身;不证明systemd/nft现场可用。"""

from pathlib import Path

import pytest


def test_unknown_runtime_refuses_without_overwriting_or_creating_journal(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.live_install import InstallationPaths, LiveDeployment

    paths = InstallationPaths.for_model(tmp_path)
    paths.runtime.mkdir(parents=True)
    (paths.runtime / "unknown").write_bytes(b"keep")
    staged = tmp_path / "staged"
    staged.mkdir()
    deployment = LiveDeployment(
        staged, paths=paths, host=None, owner_uid=__import__("os").getuid()
    )
    with pytest.raises(ValueError, match="runtime_identity_unknown"):
        deployment.preflight_existing(None)
    assert (paths.runtime / "unknown").read_bytes() == b"keep"
    assert not paths.journal.exists()


def test_install_repeat_uninstall_recover_keep_history_and_do_not_redispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    staged, paths = bundle_model(tmp_path, monkeypatch)
    host = ModelHost(paths)
    deployment = LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid())
    assert deployment.install() == "installed"
    history = (paths.ledger / "retained-history").read_bytes()
    assert host.calls.count("initialize_plans") == 1
    assert deployment.install() == "already_installed"
    assert host.calls.count("configure") == 1
    assert host.calls.count("initialize_plans") == 1
    assert deployment.uninstall() == "uninstalled"
    assert not paths.runtime.exists() and not paths.sudoers.exists()
    assert (paths.ledger / "retained-history").read_bytes() == history
    assert deployment.uninstall() == "already_uninstalled"
    with pytest.raises(ValueError, match="explicit_recovery_required"):
        deployment.install()
    assert deployment.install(recover=True) == "installed"
    assert (paths.ledger / "retained-history").read_bytes() == history


@pytest.mark.parametrize(
    "failure", ["validate_sudoers", "configure", "verify_installed", "initialize_plans"]
)
def test_recognizable_install_interruption_resumes_same_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import os

    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    staged, paths = bundle_model(tmp_path, monkeypatch)
    host = ModelHost(paths, fail=failure)
    deployment = LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid())
    with pytest.raises(ValueError, match="model_interruption"):
        deployment.install()
    host.fail = None
    assert deployment.install() == "installed"
    assert deployment.install() == "already_installed"


@pytest.mark.parametrize("failure", ["disable_observation", "stop_and_remove"])
def test_recognizable_uninstall_interruption_keeps_history_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import os

    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    staged, paths = bundle_model(tmp_path, monkeypatch)
    host = ModelHost(paths)
    deployment = LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid())
    deployment.install()
    host.fail = failure
    with pytest.raises(ValueError, match="model_interruption"):
        deployment.uninstall()
    assert paths.journal.exists() and (paths.ledger / "retained-history").exists()
    host.fail = None
    assert deployment.uninstall() == "uninstalled"


def test_bootstrap_uses_exact_embedded_archive_then_refuses_extra_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import subprocess

    from tests.live_bundle_support import bundle_model

    bundle_model(tmp_path, monkeypatch)
    runner = (tmp_path / "review/run-live.sh").read_text()
    source = runner.split("<<'LIVE_FROZEN_BOOTSTRAP'\n", 1)[1].rsplit(
        "LIVE_FROZEN_BOOTSTRAP", 1
    )[0]
    host = tmp_path / "bootstrap-host"
    host.mkdir(mode=0o755)
    source = source.replace("/var/lib/paperradar/live-bundles", str(host / "bundles"))
    source = source.replace(
        'for directory in /var /var/lib /var/lib/paperradar "$base";',
        'for directory in "$base";',
    )
    source = source.replace("$(/usr/bin/id -u)", "0")
    source = source.replace('$(/usr/bin/stat -c %u "$current")', "0")
    source = source.replace('[ "$current" != / ]', f'[ "$current" != "{host}" ]')
    source = source.replace(" -o root -g root", "").replace(
        "! -user root", f"! -user {os.getuid()}"
    )
    source = source.replace(
        'exec /usr/bin/env -i "$stage/runtime/python/bin/python3" -I -S -B '
        '"$stage/runtime/install-live.py" "$action"',
        "/usr/bin/printf bootstrap_verified",
    )
    result = subprocess.run(
        ["/bin/sh", "-s", "--", "install"],
        input=source.encode(),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == b"bootstrap_verified", (
        result.stderr
    )
    again = subprocess.run(
        ["/bin/sh", "-s", "--", "install"],
        input=source.encode(),
        capture_output=True,
        check=False,
    )
    assert again.returncode == 0
    deployed = next((host / "bundles").glob("*/runtime"))
    (deployed / "sitecustomize.py").write_bytes(b"unknown extra member")
    (deployed / "sitecustomize.py").chmod(0o644)
    failed = subprocess.run(
        ["/bin/sh", "-s", "--", "install"],
        input=source.encode(),
        capture_output=True,
        check=False,
    )
    assert failed.returncode == 2 and b"inventory" in failed.stderr
    assert (deployed / "sitecustomize.py").read_bytes() == b"unknown extra member"


@pytest.mark.parametrize("tamper", ["extra", "symlink", "hardlink", "writable"])
def test_runtime_inventory_tampering_refuses_without_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    import os

    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    staged, paths = bundle_model(tmp_path, monkeypatch)
    host = ModelHost(paths)
    deployment = LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid())
    deployment.install()
    unknown = paths.runtime / "unknown"
    if tamper == "extra":
        unknown.write_bytes(b"preserve")
    elif tamper == "symlink":
        unknown.symlink_to(tmp_path)
    elif tamper == "hardlink":
        os.link(paths.runtime / "site.json", unknown)
    else:
        (paths.runtime / "site.json").chmod(0o666)
    before = list(host.calls)
    with pytest.raises(ValueError):
        deployment.install()
    assert host.calls == before
    if tamper != "writable":
        assert os.path.lexists(unknown)


def test_real_collection_counters_stopped_and_intent_bytes_survive_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.live_evidence.collection import ProtectedCollection
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model
    from tests.live_evidence_ledger_support import NOW
    from tests.test_live_collection_v2 import BINDING, approved

    staged, paths = bundle_model(tmp_path, monkeypatch)
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=tmp_path)
    )
    ledger.initialize()
    collection = ProtectedCollection(ledger)
    collection.initialize(now=NOW)
    collection.approve_plan(approved(), now=NOW)
    run = collection.start_round("live-plan", binding=BINDING, now=NOW)
    collection.reserve(run.round_id, "auth-model", "auth", now=NOW)
    collection.recover_interrupted(now=NOW)
    before = collection.status("live-plan", now=NOW)
    (paths.ledger / "preserved-intent").write_bytes(
        b"opaque append-only intent fixture\n"
    )
    database_bytes = ledger.database.read_bytes()
    deployment = LiveDeployment(
        staged, paths=paths, host=ModelHost(paths), owner_uid=os.getuid()
    )
    deployment.install()
    deployment.uninstall()
    deployment.install(recover=True)
    after = ProtectedCollection(ledger).status("live-plan", now=NOW)
    assert after == before and after.network_used == 1 and after.stopped
    assert ledger.database.read_bytes() == database_bytes
    assert (
        paths.ledger / "preserved-intent"
    ).read_bytes() == b"opaque append-only intent fixture\n"


def test_explicit_legacy_upgrade_checks_old_bytes_and_archives_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import os

    from paper_radar.live_evidence.deployment import file_digests
    from paper_radar.live_evidence.live_install import InstallationPaths, LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    paths = InstallationPaths.for_model(tmp_path)
    old = paths.runtime
    (old / "wrappers").mkdir(parents=True)
    for name in ("collect", "tighten", "owner"):
        raw = ("old sealed " + name + "\n").encode()
        (old / "wrappers" / name).write_bytes(raw)
        (paths.executables / ("live-evidence-" + name)).write_bytes(raw)
    (old / "sudoers").write_bytes(b"old exact sudoers\n")
    paths.sudoers.parent.mkdir(parents=True)
    paths.sudoers.write_bytes((old / "sudoers").read_bytes())
    manifest_raw = "".join(
        f"{sha}  {name}\n" for name, sha in file_digests(old).items()
    ).encode()
    (old / "manifest.sha256").write_bytes(manifest_raw)
    (old / "payload.sha256").write_bytes(("a" * 64 + "\n").encode())
    identity = ("a" * 64, hashlib.sha256(manifest_raw).hexdigest())
    before = file_digests(old)
    staged, paths = bundle_model(tmp_path, monkeypatch, upgrade_from=identity)
    for path in old.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    for path in (
        paths.executables / "live-evidence-collect",
        paths.executables / "live-evidence-tighten",
        paths.executables / "live-evidence-owner",
        paths.sudoers,
    ):
        path.chmod(0o440 if path == paths.sudoers else 0o755)
    deployment = LiveDeployment(
        staged, paths=paths, host=ModelHost(paths), owner_uid=os.getuid()
    )
    assert deployment.install() == "installed"
    archive = old.with_name(old.name + ".archive-" + identity[0])
    assert file_digests(archive) == before
    assert deployment.install() == "already_installed"
    assert file_digests(archive) == before


def test_interrupted_partial_runtime_is_preserved_and_not_automatically_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    staged, paths = bundle_model(tmp_path, monkeypatch)
    pending = paths.runtime.with_name(paths.runtime.name + ".new")
    pending.mkdir(mode=0o755)
    (pending / "unknown").write_bytes(b"partial-copy")
    deployment = LiveDeployment(
        staged, paths=paths, host=ModelHost(paths), owner_uid=os.getuid()
    )
    with pytest.raises((ValueError, OSError)):
        deployment.install()
    assert (pending / "unknown").read_bytes() == b"partial-copy"
    assert not paths.runtime.exists()


def test_explicit_successive_v2_upgrade_preserves_prior_runtime_and_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import os

    from paper_radar.live_evidence.deployment import file_digests
    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    first, paths = bundle_model(tmp_path, monkeypatch)
    host = ModelHost(paths)
    deployment = LiveDeployment(first, paths=paths, host=host, owner_uid=os.getuid())
    deployment.install()
    before = file_digests(paths.runtime)
    old_payload = (paths.runtime / "payload.sha256").read_text().strip()
    old_manifest = hashlib.sha256(
        (paths.runtime / "manifest.sha256").read_bytes()
    ).hexdigest()
    journal = paths.journal.read_bytes()
    next_root = tmp_path / "next-build"
    next_root.mkdir(mode=0o755)
    staged, _ = bundle_model(
        next_root, monkeypatch, upgrade_from=(old_payload, old_manifest)
    )
    changed = LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid())
    assert changed.install() == "installed"
    archive = paths.runtime.with_name(paths.runtime.name + ".archive-" + old_payload)
    assert file_digests(archive) == before
    assert (
        paths.journal.with_name(
            "deployment-v2-history-" + old_payload + ".json"
        ).read_bytes()
        == journal
    )
    assert changed.install() == "already_installed"


def test_explicit_recovery_rechecks_host_preserving_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from paper_radar.live_evidence.live_install import LiveDeployment
    from tests.live_bundle_support import ModelHost, bundle_model

    staged, paths = bundle_model(tmp_path, monkeypatch)
    host = ModelHost(paths)
    deployment = LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid())
    deployment.install()
    history = (paths.ledger / "retained-history").read_bytes()
    paths.resolver.unlink()
    host.installed = False  # 模拟reboot丢失/run与cgroup/nft事实。
    with pytest.raises(OSError):
        deployment.install()
    assert deployment.install(recover=True) == "installed"
    assert host.calls.count("prepare_recovery") == 1
    assert paths.resolver.exists()
    assert (paths.ledger / "retained-history").read_bytes() == history
