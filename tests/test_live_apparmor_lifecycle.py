"""D1: sealed AppArmor lifecycle at OS boundaries; never loads host policy."""

from pathlib import Path

import pytest

from paper_radar.live_evidence.placement_policy import PlacementPolicyLifecycle
from tests.live_apparmor_support import PolicyOS
from tests.test_live_epoch_upgrade import (
    UpgradeCase,
)
from tests.test_live_epoch_upgrade import (
    source_root as source_root,
)
from tests.test_live_epoch_upgrade import (
    upgrade as upgrade,
)


def test_policy_inventory_missing_build_is_not_legacy(tmp_path: Path) -> None:
    from paper_radar.live_evidence.placement_policy import read_placement_policy

    (tmp_path / "placement").mkdir()
    (tmp_path / "placement/apparmor.bin").write_bytes(b"unknown")
    with pytest.raises(ValueError, match="placement_seal_incomplete"):
        read_placement_policy(tmp_path)


def policy_root(root: Path) -> Path:
    import hashlib
    import json

    from paper_radar.live_evidence.placement_policy import MEMBERS, PROFILES, SYSCTLS

    (root / "placement").mkdir(parents=True, exist_ok=True)
    for name in MEMBERS:
        (root / name).write_bytes(name.encode())
    (root / "placement/apparmor.bin").write_bytes(
        b"\x04\x08\x00version\x00\x02\x05\x00\x00\x00sealed-test"
    )

    def sha(name: str) -> str:
        return hashlib.sha256((root / name).read_bytes()).hexdigest()

    fields = {
        "source_sha256": "placement/apparmor.source",
        "binary_sha256": "placement/apparmor.bin",
        "abi_sha256": "placement/abi-5.0",
        "parser_config_sha256": "placement/parser.conf",
        "native_source_sha256": "placement/placement_native.c",
        "native_header_sha256": "placement/placement_config.h",
        "program_sha256": "placement/program.json",
    }
    build = {
        "format_version": 1,
        "profiles": [{"name": name, "attachment": attach} for name, attach in PROFILES],
        "raw_abi": "v5",
        "abi": "v5",
        "parser_flags": ["-Q", "-K", "--zstd-compress-level=0", "--Werror"],
        **{field: sha(name) for field, name in fields.items()},
        "includes": {"abi-5.0": sha("placement/abi-5.0")},
        "native_sha256": {
            stage: sha("placement-" + stage) for stage in ("pre", "post")
        },
        "initial_namespaces": {"user": [4, 9], "mnt": [4, 10]},
        "tools": {
            "apparmor_parser": {"path": "/usr/sbin/apparmor_parser", "sha256": "a" * 64}
        },
        "resolver_source": "/run/paper-radar/resolv.conf",
        "resolver_mount_flags": 0,
        "resolver_target": "/run/systemd/resolve/stub-resolv.conf",
    }
    (root / "placement/build.json").write_text(json.dumps(build))
    (root / "placement/security.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "sysctls": dict.fromkeys(SYSCTLS, 1),
                "tools": {
                    "/usr/sbin/apparmor_parser": {
                        "resolved": "/usr/sbin/apparmor_parser",
                        "sha256": "a" * 64,
                    },
                    "/usr/bin/true": {"resolved": "/usr/bin/true", "sha256": "b" * 64},
                    "/usr/bin/systemd-run": {
                        "resolved": "/usr/bin/systemd-run",
                        "sha256": "b" * 64,
                    },
                    "/usr/bin/systemctl": {
                        "resolved": "/usr/bin/systemctl",
                        "sha256": "b" * 64,
                    },
                    "/usr/bin/loginctl": {
                        "resolved": "/usr/bin/loginctl",
                        "sha256": "b" * 64,
                    },
                },
            }
        )
    )
    root.chmod(0o755)
    for path in root.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    return root


def lifecycle(root: Path, ledger: Path) -> tuple[PlacementPolicyLifecycle, PolicyOS]:
    import os

    from paper_radar.live_evidence.live_apparmor_kernel import AppArmorKernel
    from paper_radar.live_evidence.placement_policy import read_placement_policy

    sealed = read_placement_policy(root)
    assert sealed is not None
    boundary = PolicyOS(expected=sealed.policy, parser=sealed.parser)
    return PlacementPolicyLifecycle(
        root,
        ledger,
        owner_uid=os.getuid(),
        anchor=root.parent,
        kernel=AppArmorKernel(boundary, sealed.parser),
    ), boundary


def test_policy_preparation_then_exact_verify_and_retirement_keeps_history(
    tmp_path: Path,
) -> None:
    root = policy_root(tmp_path / "root")
    gate, boundary = lifecycle(root, tmp_path / "ledger")
    seen = []
    gate.prepare(lambda: seen.append("no-secret-preflight"))
    gate.verify()
    assert seen == ["no-secret-preflight"]
    assert len(boundary.writes) == 1
    gate.prepare(lambda: None)
    assert len(boundary.writes) == 1
    gate.remove()
    gate.verify_absent()
    assert gate.journal.exists()


def test_unknown_policy_rejected_before_policy_journal_write(tmp_path: Path) -> None:
    root = policy_root(tmp_path / "root")
    gate, boundary = lifecycle(root, tmp_path / "ledger")
    boundary.load_binary(b"foreign")
    boundary.writes.clear()
    with pytest.raises(ValueError, match="apparmor_blob_mismatch"):
        gate.prepare(lambda: None)
    assert not gate.journal.exists()
    assert boundary.writes == []


def test_preflight_failure_remains_identifiable_and_resumes_same_bytes(
    tmp_path: Path,
) -> None:
    root = policy_root(tmp_path / "root")
    gate, boundary = lifecycle(root, tmp_path / "ledger")

    def refused() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match="placement_preflight_refused"):
        gate.prepare(refused)
    assert b'"phase":"preparing"' in gate.journal.read_bytes()
    gate.prepare(lambda: None)
    gate.verify()
    assert len(boundary.writes) == 1


def test_known_partial_requires_explicit_recovery_and_never_replaces_unknown(
    tmp_path: Path,
) -> None:
    root = policy_root(tmp_path / "root")
    gate, boundary = lifecycle(root, tmp_path / "ledger")
    with pytest.raises(ValueError, match="placement_preflight_refused"):
        gate.prepare(
            lambda: (_ for _ in ()).throw(ValueError("placement_preflight_refused"))
        )
    del boundary.profiles["0"]
    with pytest.raises(ValueError, match="apparmor_partial_policy"):
        gate.prepare(lambda: None)
    gate.prepare(lambda: None, recover=True)
    gate.verify()
    assert len(boundary.profiles) == 2
    boundary.profiles["0"]["raw_data"] = b"foreign"
    before = list(boundary.writes)
    with pytest.raises(ValueError, match="apparmor_blob_mismatch"):
        gate.remove(recover=True)
    assert boundary.writes == before


@pytest.mark.parametrize(
    "member",
    [
        "placement/apparmor.source",
        "placement/apparmor.bin",
        "placement/abi-5.0",
        "placement/placement_config.h",
        "placement-pre",
        "placement-post",
    ],
)
def test_sealed_source_binary_build_association_refuses_changed_member(
    tmp_path: Path, member: str
) -> None:
    from paper_radar.live_evidence.placement_policy import read_placement_policy

    root = policy_root(tmp_path / "root")
    (root / member).write_bytes(b"changed")
    with pytest.raises(ValueError, match="placement_seal_identity"):
        read_placement_policy(root)


def host_security_fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import hashlib
    import json

    from paper_radar.live_evidence import placement_policy as module

    proc = root.parent / "proc-model"
    (proc / "sys/kernel").mkdir(parents=True)
    for name in module.SYSCTLS:
        (proc / "sys/kernel" / name).write_text("1\n")
    build_path = root / "placement/build.json"
    build = json.loads(build_path.read_bytes())
    for namespace in ("user", "mnt"):
        for process in ("self", "1"):
            directory = proc / process / "ns"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / namespace).symlink_to("/proc/self/ns/" + namespace)
        info = (proc / "self/ns" / namespace).stat()
        build["initial_namespaces"][namespace] = [info.st_dev, info.st_ino]
    build["resolver_target"] = str(Path("/etc/resolv.conf").resolve())
    tools = {
        name: {
            "resolved": str(Path(name).resolve()),
            "sha256": hashlib.sha256(Path(name).resolve().read_bytes()).hexdigest(),
        }
        for name in module.RUNTIME_TOOLS
    }
    build["tools"]["apparmor_parser"] = {
        "path": tools["/usr/sbin/apparmor_parser"]["resolved"],
        "sha256": tools["/usr/sbin/apparmor_parser"]["sha256"],
    }
    build_path.write_text(json.dumps(build))
    security_path = root / "placement/security.json"
    security = json.loads(security_path.read_bytes())
    security["tools"] = tools
    security_path.write_text(json.dumps(security))
    monkeypatch.setattr(module, "_PROC_ROOT", proc)
    return proc


@pytest.mark.parametrize(
    "damage,reason",
    [
        ("user", "placement_namespace_identity"),
        ("mnt", "placement_namespace_identity"),
        ("sysctl", "placement_sysctl_identity"),
        ("sysctl_missing", "placement_sysctl_unavailable"),
        ("parser", "placement_tool_identity"),
        ("resolver", "placement_resolver_target"),
    ],
)
def test_host_namespace_sysctl_and_tools_are_current_preconditions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str, reason: str
) -> None:
    import json

    from paper_radar.live_evidence.placement_policy import (
        read_placement_policy,
        verify_host_security,
    )

    root = policy_root(tmp_path / "root")
    proc = host_security_fixture(root, monkeypatch)
    sealed = read_placement_policy(root)
    assert sealed is not None
    verify_host_security(sealed)
    if damage in {"user", "mnt"}:
        (proc / "1/ns" / damage).unlink()
        (proc / "1/ns" / damage).write_bytes(b"different namespace")
    elif damage == "sysctl":
        (proc / "sys/kernel/apparmor_restrict_unprivileged_unconfined").write_text(
            "0\n"
        )
    elif damage == "sysctl_missing":
        (proc / "sys/kernel/apparmor_restrict_unprivileged_userns").unlink()
    else:
        path = root / (
            "placement/security.json" if damage == "parser" else "placement/build.json"
        )
        value = json.loads(path.read_bytes())
        if damage == "parser":
            # Preserve parser consistency; alter the fixed true tool identity.
            value["tools"]["/usr/bin/true"]["sha256"] = "c" * 64
        else:
            value["resolver_target"] = "/unreviewed-resolver"
        path.write_text(json.dumps(value))
        sealed = read_placement_policy(root)
        assert sealed is not None
    with pytest.raises(ValueError, match=reason):
        verify_host_security(sealed)


@pytest.mark.parametrize("damage", ["missing", "bytes", "permission", "revision"])
def test_observer_distinguishes_policy_drift_from_temporary_readback_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from datetime import timedelta

    from paper_radar.live_evidence import placement_policy as kernel_module
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.observation import load_current_observation
    from paper_radar.live_evidence.protected_observer import (
        observer_identity,
        refresh_once,
    )
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.live_evidence.types import BindingComponent as B
    from tests.live_evidence_ledger_support import NOW
    from tests.test_observation_refresh import refresh_site

    ledger, runtime, _, previous = refresh_site(tmp_path, monkeypatch)
    policy_root(runtime)
    host_security_fixture(runtime, monkeypatch)
    for name in ("placement_policy.py", "live_apparmor_kernel.py"):
        member = runtime / "site-packages/paper_radar/live_evidence" / name
        member.write_bytes(b"synthetic sealed observer module")
        member.chmod(0o644)
    gate, boundary = lifecycle(runtime, ledger.root)
    gate.prepare(lambda: None)
    monkeypatch.setattr(kernel_module, "LinuxKernelPolicyIO", lambda: boundary)
    identity = observer_identity(runtime, ledger)
    source = ledger.root / "inbox/current-observation.json"
    source.write_bytes(
        canonical_bytes(
            previous.model_copy(
                update={"binding": previous.binding | {B.OBSERVER: identity}}
            )
        )
    )
    assert refresh_once(runtime, ledger, now=NOW) == "available"
    before = source.read_bytes()
    if damage == "missing":
        boundary.profiles.clear()
    elif damage == "bytes":
        boundary.profiles["0"]["raw_data"] = b"foreign bytes"
    elif damage == "permission":
        boundary.unavailable = True
    else:
        original = boundary.profile_identity

        def changed(handle: str) -> tuple[str, ...]:
            boundary.revision_value += 1
            return original(handle)

        monkeypatch.setattr(boundary, "profile_identity", changed)
    drift = damage in {"missing", "bytes"}
    reason = "observation_drift" if drift else "observation_unavailable"
    at = NOW + timedelta(seconds=1)
    assert refresh_once(runtime, ledger, now=at) == reason
    if not drift:
        assert source.read_bytes() == before
    reopened = EvidenceLedger(ledger.root, trust=ledger.trust)
    with pytest.raises(LedgerError, match=reason):
        load_current_observation(reopened, now=at)
    evidence = EvidenceLifecycle(reopened).snapshot(now=at).evidence
    assert any(item.revoked for item in evidence) is drift


# Installer fixtures use the complete current source and real compile-only
# native/profile builds. Only host operations and selected Python freezer inputs
# are modeled; these offline tests do not load policies or prove live placement.


def require_compiled_policy(root: Path) -> None:
    from paper_radar.live_evidence.placement_policy import read_placement_policy

    assert read_placement_policy(root) is not None


def test_upgrade_unknown_policy_refuses_before_any_old_state_write(
    upgrade: UpgradeCase,
) -> None:
    require_compiled_policy(upgrade.deployment.staged)
    host = upgrade.host
    stage = upgrade.deployment.staged
    gate = host.placement_lifecycle(stage)
    assert gate.sealed is not None
    host.policy_os.load_binary(b"foreign policy")
    host.policy_os.writes.clear()
    before = upgrade.paths.journal.read_bytes()
    policy_before = gate.journal.read_bytes() if gate.journal.exists() else None
    old_epoch = upgrade.old_epoch
    with pytest.raises(ValueError, match="apparmor_blob_mismatch"):
        upgrade.deployment.install()
    assert upgrade.paths.journal.read_bytes() == before
    assert (
        gate.journal.read_bytes() if gate.journal.exists() else None
    ) == policy_before
    assert host.policy_os.writes == []
    assert upgrade.old_epoch == old_epoch


@pytest.mark.parametrize(
    "failure",
    [
        "native_preflight",
        "disable_observation",
        "stop_and_remove",
        "validate_sudoers",
        "configure",
        "traced_preflight",
        "verify_installed",
        "initialize_plans",
    ],
)
def test_policy_and_original_epoch_survive_each_installer_interruption(
    upgrade: UpgradeCase,
    failure: str,
) -> None:
    from datetime import UTC, datetime

    from paper_radar.live_evidence.collection import ProtectedCollection
    from paper_radar.live_evidence.normal_auth_refresh import read_epoch

    require_compiled_policy(upgrade.deployment.staged)
    host = upgrade.host
    host.fail = failure
    received = upgrade.ledger.list_received()
    with pytest.raises(ValueError, match="model_interruption"):
        upgrade.deployment.install()
    host.fail = None
    assert upgrade.deployment.install() == "installed"
    assert (
        read_epoch(upgrade.ledger, upgrade.new).deployed_at
        == upgrade.descriptor.deployed_at
    )
    assert upgrade.ledger.list_received() == received
    status = ProtectedCollection(upgrade.ledger).status(
        upgrade.old.negative_plan.plan_id, now=datetime.now(UTC)
    )
    assert status.network_remaining == 40
    assert status.model_remaining == 40
    host.placement_lifecycle(upgrade.paths.runtime).verify()
    assert upgrade.deployment.uninstall() == "uninstalled"
    host.placement_lifecycle(upgrade.deployment.staged).verify_absent()
    assert upgrade.ledger.list_received() == received
    assert upgrade.deployment.install(recover=True) == "installed"
    assert (
        read_epoch(upgrade.ledger, upgrade.new).deployed_at
        == upgrade.descriptor.deployed_at
    )


def test_new_source_inventory_cannot_omit_entire_policy(tmp_path: Path) -> None:
    import json

    from paper_radar.live_evidence.placement_policy import read_placement_policy

    (tmp_path / "source-identity.json").write_text(
        json.dumps(
            {"source_auxiliary_sha256": {"pi_execution/placement_native.c": "f" * 64}}
        )
    )
    with pytest.raises(ValueError, match="placement_seal_incomplete"):
        read_placement_policy(tmp_path)


def test_policy_retirement_preserves_unrelated_kernel_resources(tmp_path: Path) -> None:
    root = policy_root(tmp_path / "root")
    gate, boundary = lifecycle(root, tmp_path / "ledger")
    foreign = {
        "name": b"other-project\n",
        "mode": b"enforce\n",
        "attach": b"/other/project\n",
        "raw_abi": b"v5\n",
        "raw_sha256": b"f" * 64 + b"\n",
        "raw_data": b"foreign bytes",
    }
    boundary.profiles["unrelated"] = foreign.copy()
    gate.prepare(lambda: None)
    gate.remove()
    assert boundary.profiles == {"unrelated": foreign}


@pytest.mark.parametrize(
    "failure", ["before_rename", "after_rename", "none", "unknown_archive"]
)
def test_target_retirement_interruption_and_repeated_cycles_keep_exact_sources(
    upgrade: UpgradeCase, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import os

    from paper_radar.live_evidence.live_host import LinuxLiveHost
    from paper_radar.live_evidence.receipt import canonical_bytes
    from tests.test_live_bundle_host import material

    paths = upgrade.paths
    # OS metadata adapter: model root ownership only for this private fixture.
    original_lstat = Path.lstat

    def lstat(path: Path) -> os.stat_result:
        info = original_lstat(path)
        if path.is_relative_to(paths.anchor) or path in paths.anchor.parents:
            values = list(info)
            values[4] = 0
            if path in paths.anchor.parents:
                values[0] = info.st_mode & ~0o022
            return os.stat_result(values)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    original_fstat = os.fstat

    def fstat(descriptor: int) -> os.stat_result:
        info = original_fstat(descriptor)
        try:
            path = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        except OSError:
            return info
        if path.is_relative_to(paths.anchor):
            values = list(info)
            values[4] = 0
            return os.stat_result(values)
        return info

    monkeypatch.setattr(os, "fstat", fstat)
    target, _ = material()
    original_exists = Path.exists

    def exists(path: Path, **kwargs: bool) -> bool:
        if path.is_relative_to("/sys/fs/cgroup"):
            return False
        return original_exists(path, **kwargs)

    monkeypatch.setattr(Path, "exists", exists)
    target_path = paths.ledger / "inbox/placement-target-v1.json"
    target_path.write_bytes(canonical_bytes(target))
    target_path.chmod(0o644)

    class RetirementOS(LinuxLiveHost):
        def _run(
            self,
            argv: tuple[str, ...],
            *,
            product: bool = False,
            data: bytes | None = None,
        ) -> bytes:
            if argv == ("/usr/sbin/nft", "-j", "list", "tables"):
                return b'{"nftables":[]}'
            assert argv == ("/usr/bin/systemctl", "--user", "stop", "paperradar.slice")
            return b""

        def unit_properties(self, name: str) -> dict[str, str]:
            values = {
                "FragmentPath": str(paths.units / name),
                "DropInPaths": "",
                "ActiveState": "inactive",
            }
            if name == "paperradar-anchor.service":
                values.update(
                    {
                        key: ""
                        for key in (
                            "ExecStartPre",
                            "ExecStartPost",
                            "ExecStop",
                            "ExecStopPost",
                            "ExecReload",
                            "ExecCondition",
                        )
                    }
                )
                executable = str(paths.runtime / "anchor")
                values.update(
                    Slice="paperradar.slice",
                    LimitCORE="0",
                    LimitCORESoft="0",
                    ExecStart=f"path={executable} ; argv[]={executable} ;",
                )
            return values

    host = RetirementOS(paths)
    if failure == "unknown_archive":
        import hashlib

        raw = canonical_bytes(target)
        archive = target_path.with_name(
            "placement-target-retired-" + hashlib.sha256(raw).hexdigest() + ".json"
        )
        archive.write_bytes(raw)
        archive.chmod(0o644)
        with pytest.raises(ValueError, match="target_archive_conflict"):
            host.stop_and_remove()
        assert target_path.read_bytes() == raw
        assert not tuple(paths.ledger.glob("placement-target-retirement-v1-*.json"))
        return
    original_rename = Path.rename
    interrupted = False

    def rename(path: Path, destination: str | Path) -> Path:
        nonlocal interrupted
        if path == target_path and not interrupted:
            interrupted = True
            if failure == "before_rename":
                raise OSError("synthetic_before_rename")
            result = original_rename(path, destination)
            if failure == "after_rename":
                raise OSError("synthetic_after_rename")
            return result
        return original_rename(path, destination)

    monkeypatch.setattr(Path, "rename", rename)
    if failure != "none":
        with pytest.raises(OSError, match=r"synthetic_.*_rename"):
            host.stop_and_remove()
    host.stop_and_remove()
    host.stop_and_remove()
    first_archives = tuple(paths.ledger.glob("inbox/placement-target-retired-*.json"))
    assert len(first_archives) == 1
    first_raw = first_archives[0].read_bytes()
    # Same sealed SHA, a later explicit recovery has a different actual target.
    next_target = target.model_copy(update={"anchor_start": target.anchor_start + 1})
    target_path.write_bytes(canonical_bytes(next_target))
    target_path.chmod(0o644)
    host.stop_and_remove()
    assert len(tuple(paths.ledger.glob("inbox/placement-target-retired-*.json"))) == 2
    assert first_archives[0].read_bytes() == first_raw
    assert not target_path.exists()


def test_interrupted_exact_removal_recovers_only_remaining_known_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = policy_root(tmp_path / "root")
    gate, boundary = lifecycle(root, tmp_path / "ledger")
    gate.prepare(lambda: None)
    original = boundary.remove_profile
    interrupted = False

    def remove(name: str) -> None:
        nonlocal interrupted
        original(name)
        if not interrupted:
            interrupted = True
            raise OSError("synthetic_policy_remove_interrupted")

    monkeypatch.setattr(boundary, "remove_profile", remove)
    with pytest.raises(OSError, match="synthetic_policy_remove_interrupted"):
        gate.remove()
    assert b'"phase":"removing"' in gate.journal.read_bytes()
    with pytest.raises(ValueError, match="apparmor_partial_policy"):
        gate.remove()
    gate.remove(recover=True)
    gate.verify_absent()
    assert boundary.profiles == {}


def test_real_offline_native_build_is_accepted_by_lifecycle_seal_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import placement_policy
    from paper_radar.live_evidence.placement_build import freeze_placement
    from tests.site_collector_support import site_configuration

    root = tmp_path / "built"
    (root / "resources").mkdir(parents=True)
    (root / "resources/resolv.conf").write_bytes(b"nameserver 192.0.2.1\n")
    # Only the sysctl read OS boundary is modeled. Compiler/parser really run
    # in compile-only mode; neither native entry nor kernel writer executes.
    proc = tmp_path / "proc"
    (proc / "sys/kernel").mkdir(parents=True)
    for name in placement_policy.SYSCTLS:
        (proc / "sys/kernel" / name).write_text("1\n")
    monkeypatch.setattr(placement_policy, "_PROC_ROOT", proc)
    frozen = freeze_placement(root, site_configuration(tmp_path), Path.cwd())
    placement_policy.freeze_security(root)
    sealed = placement_policy.read_placement_policy(root)
    assert sealed is not None
    assert sealed.policy.binary == frozen.profile_binary.read_bytes()
    assert sealed.policy.profiles == frozen.profiles
    assert sealed.policy.raw_abi == "v5"


@pytest.mark.parametrize(
    "failure", ["stop_resources_anchor", "verify_resources_stopped", "traced_preflight"]
)
def test_unexecuted_resources_replacement_retains_policy_and_exact_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_root: Path, failure: str
) -> None:
    import json
    import os

    from paper_radar.live_evidence.deployment import file_digests
    from paper_radar.live_evidence.live_install import (
        InstallationPaths,
        LiveDeployment,
        digest,
    )
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
    from tests.live_bundle_support import ModelHost, bundle_model

    paths = InstallationPaths.for_model(tmp_path)
    (paths.runtime / "wrappers").mkdir(parents=True)
    paths.sudoers.parent.mkdir(parents=True)
    for name in ("collect", "tighten", "owner"):
        raw = ("synthetic legacy " + name).encode()
        (paths.runtime / "wrappers" / name).write_bytes(raw)
        entry = paths.executables / ("live-evidence-" + name)
        entry.write_bytes(raw)
        entry.chmod(0o755)
    (paths.runtime / "sudoers").write_bytes(b"synthetic legacy sudoers")
    paths.sudoers.write_bytes(b"synthetic legacy sudoers")
    paths.sudoers.chmod(0o440)
    raw_manifest = "".join(
        f"{sha}  {name}\n" for name, sha in file_digests(paths.runtime).items()
    ).encode()
    (paths.runtime / "manifest.sha256").write_bytes(raw_manifest)
    (paths.runtime / "payload.sha256").write_text("a" * 64 + "\n")
    first, paths = bundle_model(
        tmp_path,
        monkeypatch,
        source_root=source_root,
        upgrade_from=("a" * 64, digest(raw_manifest)),
    )
    for member in paths.runtime.rglob("*"):
        member.chmod(0o755 if member.is_dir() else 0o644)
    host = ModelHost(paths, fail="configure")
    previous = LiveDeployment(first, paths=paths, host=host, owner_uid=os.getuid())
    with pytest.raises(ValueError, match="model_interruption"):
        previous.install()
    old = json.loads(paths.journal.read_bytes())
    assert old["phase"] == "resources"
    next_root = tmp_path / "next"
    next_root.mkdir(mode=0o755)
    staged, _ = bundle_model(
        next_root,
        monkeypatch,
        source_root=source_root,
        upgrade_from=(old["payload"], old["manifest"]),
        real_freeze=True,
        site_override=SiteConfiguration.model_validate_json(
            (paths.runtime / "site.json").read_bytes()
        ),
    )
    require_compiled_policy(staged)
    deployed = LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid())
    host.fail = failure
    with pytest.raises(ValueError, match="model_interruption"):
        deployed.install(recover=True)
    host.fail = None
    assert deployed.install(recover=True) == "installed"
    host.placement_lifecycle(paths.runtime).verify()
    archive = paths.runtime.with_name(paths.runtime.name + ".archive-" + old["payload"])
    assert (archive / "payload.sha256").read_text().strip() == old["payload"]
    assert deployed.uninstall() == "uninstalled"
    host.placement_lifecycle(staged).verify_absent()


def test_probe_closes_real_inherited_write_fds_before_permanent_uid_drop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ctypes
    import json
    import os

    from paper_radar.live_evidence import placement_policy as module
    from tests.site_collector_support import site_configuration

    root = policy_root(tmp_path / "root")
    host_security_fixture(root, monkeypatch)
    resolver = tmp_path / "canonical-resolver"
    resolver.write_bytes(b"public resolver fixture")
    build_path = root / "placement/build.json"
    build = json.loads(build_path.read_bytes())
    build["resolver_target"] = str(resolver)
    build_path.write_text(json.dumps(build))
    gate, boundary = lifecycle(root, tmp_path / "ledger")
    assert gate.sealed is not None
    boundary.load_binary(gate.sealed.policy.binary)
    monkeypatch.setattr(module, "LinuxKernelPolicyIO", lambda: boundary)
    monkeypatch.setattr(module, "_RESOLVER_PATH", resolver)
    monkeypatch.setattr(
        module, "_RESOLVER_SOURCE_PATH", tmp_path / "private-run/resolv.conf"
    )
    monkeypatch.setattr(module, "RUNTIME_ROOT", tmp_path / "private-runtime")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    write_fd = os.open(tmp_path / "collector.lock", os.O_RDWR | os.O_CREAT, 0o600)
    unrelated_fd = os.open(tmp_path / "ledger-write", os.O_RDWR | os.O_CREAT, 0o600)
    witness = tmp_path / "child-fd-proof"
    calls: list[str] = []

    def closed() -> None:
        for descriptor in (write_fd, unrelated_fd):
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            raise AssertionError("inherited root write fd reached product transition")

    def groups(values: list[int]) -> None:
        closed()
        assert values == []
        calls.append("groups")

    def gid(real: int, effective: int, saved: int) -> None:
        closed()
        assert real == effective == saved == os.getgid()
        calls.append("gid")

    def uid(real: int, effective: int, saved: int) -> None:
        closed()
        assert real == effective == saved == os.getuid()
        calls.append("uid")

    class RootSyscalls:
        def unshare(self, flags: int) -> int:
            assert flags == 0x00020000
            return 0

        def mount(self, *arguments: object) -> int:
            return 0

        def prctl(self, *arguments: int) -> int:
            return 0

    monkeypatch.setattr(ctypes, "CDLL", lambda *args, **kwargs: RootSyscalls())
    monkeypatch.setattr(os, "setgroups", groups)
    monkeypatch.setattr(os, "setresgid", gid)
    monkeypatch.setattr(os, "setresuid", uid)

    def execute(path: str, argv: tuple[str, ...], env: dict[str, str]) -> None:
        closed()
        assert argv == (str(tmp_path / "private-runtime/placement-pre"), "--preflight")
        assert env == {} and calls == ["groups", "gid", "uid"]
        witness.write_bytes(b"closed before product uid; no root tracer\n")
        os._exit(0)

    monkeypatch.setattr(os, "execve", execute)
    try:
        module.native_preflight(root, site_configuration(tmp_path), gate.sealed)
        assert witness.read_bytes() == b"closed before product uid; no root tracer\n"
        # The real fork closes only the child's copies; parent still owns lock.
        assert os.fstat(write_fd).st_ino == (tmp_path / "collector.lock").stat().st_ino
        assert (
            os.fstat(unrelated_fd).st_ino == (tmp_path / "ledger-write").stat().st_ino
        )
    finally:
        os.close(write_fd)
        os.close(unrelated_fd)


def test_root_observer_rejects_policy_symlink_before_reading_its_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.protected_observer import observer_identity
    from tests.test_observation_refresh import refresh_site

    ledger, runtime, _, _ = refresh_site(tmp_path, monkeypatch)
    policy_root(runtime)
    source = runtime / "placement/apparmor.source"
    source.unlink()
    marker = tmp_path / "credential-read-forbidden-marker"
    marker.write_bytes(b"synthetic forbidden data; never root-read")
    source.symlink_to(marker)
    original = Path.read_bytes
    read_untrusted = False

    def read(path: Path) -> bytes:
        nonlocal read_untrusted
        if path == source:
            read_untrusted = True
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(LedgerError, match="source_untrusted"):
        observer_identity(runtime, ledger)
    assert not read_untrusted


def test_invalid_runtime_tool_metadata_is_controlled_seal_refusal(
    tmp_path: Path,
) -> None:
    import json

    from paper_radar.live_evidence.placement_policy import read_placement_policy

    root = policy_root(tmp_path / "root")
    path = root / "placement/security.json"
    value = json.loads(path.read_bytes())
    value["tools"]["/usr/bin/true"] = "unrecognized tool descriptor"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="placement_seal_identity"):
        read_placement_policy(root)
