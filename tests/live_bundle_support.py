"""显式替代宿主I/O的Live封印工程模型;不伪称真实OS证明。"""

import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from paper_radar.live_evidence.epoch_lineage import EpochUpgrade
from paper_radar.live_evidence.live_bundle import build_live_bundle, derive_site
from paper_radar.live_evidence.live_install import InstallationPaths
from paper_radar.live_evidence.model_manifest import USES, ModelManifest
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from tests.site_collector_support import site_configuration

if TYPE_CHECKING:
    from paper_radar.live_evidence.placement_policy import PlacementPolicyLifecycle


def bundle_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    real_freeze: bool = False,
    upgrade_from: tuple[str, str] | None = None,
    source_root: Path | None = None,
    epoch_upgrade: EpochUpgrade | None = None,
    site_override: SiteConfiguration | None = None,
    window: tuple[datetime, datetime] | None = None,
) -> tuple[Path, InstallationPaths]:
    site = site_override or site_configuration(tmp_path).model_copy(
        update={"claim_uses": USES}
    )
    monkeypatch.setattr(
        "paper_radar.pi_supply.activation_history",
        lambda database: [
            SimpleNamespace(
                snapshot_id=site.snapshot_id,
                supply_id=site.binding.supply_id,
                install_id=site.binding.install_id,
            )
        ],
    )
    site, _ = derive_site(site)

    def freeze(root: Path, source: Path) -> None:
        (root / "python/bin").mkdir(parents=True)
        (root / "python/bin/python3").write_bytes(b"synthetic interpreter")
        (root / "entry.py").write_text("raise SystemExit(2)\n")
        (root / "wrappers").mkdir()

    if not real_freeze:
        monkeypatch.setattr(
            "paper_radar.live_evidence.deployment.freeze_runtime", freeze
        )
    start = datetime.now(UTC) - timedelta(days=1)
    start, end = window or (start, start + timedelta(days=14))
    output = tmp_path / "review"
    hashes = build_live_bundle(
        output,
        site,
        starts_at=start,
        ends_at=end,
        source_root=source_root or Path(__file__).resolve().parents[1],
        upgrade_from=upgrade_from,
        epoch_upgrade=epoch_upgrade,
        network_input={
            "pool": "28.0.0.0/8",
            "router": "192.168.44.1",
            "outside": "192.0.2.1",
            "nonrouter": "192.0.2.2",
            "udp443": "192.0.2.1",
            "owner_network_applicable": True,
            "owner_window_confirmed": True,
            "owner_statement": (
                "Explicit synthetic test approval; no live applicability."
            ),
        },
    )
    staged = tmp_path / "staged"
    staged.mkdir(mode=0o755)
    with tarfile.open(output / "payload.tar") as archive:
        archive.extractall(staged, filter="data")
    (staged / "payload.sha256").write_text(hashes["payload.tar"] + "\n")
    (staged / "payload.sha256").chmod(0o644)
    paths = InstallationPaths.for_model(tmp_path)
    for path in (
        paths.runtime.parent,
        paths.ledger / "inbox",
        paths.sudoers.parent,
        paths.units,
        paths.resolver.parent,
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o755)
    for directory in tmp_path.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o755)
    return staged, paths


class ModelHost:
    def __init__(self, paths: InstallationPaths, *, fail: str | None = None) -> None:
        self.paths = paths
        self.fail = fail
        self.calls: list[str] = []
        self.installed = False
        from tests.live_apparmor_support import PolicyOS

        self.policy_os = PolicyOS()

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail == name:
            raise ValueError("model_interruption")

    def preflight(self, site: SiteConfiguration) -> None:
        self._call("preflight")

    def placement_lifecycle(self, root: Path) -> PlacementPolicyLifecycle:
        import os

        from paper_radar.live_evidence.live_apparmor_kernel import AppArmorKernel
        from paper_radar.live_evidence.placement_policy import (
            PlacementPolicyLifecycle,
            read_placement_policy,
        )

        sealed = read_placement_policy(root)
        kernel = None
        if sealed is not None:
            self.policy_os.expected = sealed.policy
            self.policy_os.parser = sealed.parser
            kernel = AppArmorKernel(self.policy_os, sealed.parser)
        return PlacementPolicyLifecycle(
            root,
            self.paths.ledger,
            owner_uid=os.getuid(),
            anchor=self.paths.anchor,
            kernel=kernel,
        )

    def preflight_placement(self, root: Path, *, recover: bool = False) -> None:
        self.placement_lifecycle(root).check(recover=recover)

    def prepare_placement(
        self, root: Path, site: SiteConfiguration, *, recover: bool = False
    ) -> None:
        lifecycle = self.placement_lifecycle(root)
        if lifecycle.sealed is not None:
            lifecycle.prepare(lambda: self._call("native_preflight"), recover=recover)

    def verify_target_preflight(self, root: Path, site: SiteConfiguration) -> None:
        lifecycle = self.placement_lifecycle(root)
        if lifecycle.sealed is not None:
            lifecycle.verify()
            self._call("traced_preflight")

    def retire_placement(self, root: Path, *, recover: bool = False) -> None:
        self.placement_lifecycle(root).remove(recover=recover)

    def verify_placement_absent(self, root: Path) -> None:
        self.placement_lifecycle(root).verify_absent()

    def preflight_nft(self, site: SiteConfiguration, manifest: ModelManifest) -> None:
        self._call("preflight_nft")

    def ensure_no_table(self) -> None:
        self._call("ensure_no_table")

    def validate_sudoers(self, path: Path) -> None:
        self._call("validate_sudoers")

    def configure(self, site: SiteConfiguration, manifest: ModelManifest) -> None:
        self._call("configure")
        self.installed = True

    def verify_installed(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        self._call("verify_installed")
        self.placement_lifecycle(self.paths.runtime).verify()
        if not self.installed:
            raise ValueError("model_host_unavailable")

    def initialize_plans(
        self, root: Path, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        self._call("initialize_plans")
        import os

        from paper_radar.live_evidence.collection import ProtectedCollection
        from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust

        ledger = EvidenceLedger(
            self.paths.ledger,
            trust=LedgerTrust(owner_uid=os.getuid(), anchor=self.paths.anchor),
        )
        ledger.initialize()
        ProtectedCollection(ledger).initialize(now=datetime.now(UTC))
        history = self.paths.ledger / "retained-history"
        if not history.exists():
            history.write_bytes(b"failed/stopped/revoked/intents/auth=13/model=9\n")

    def prepare_recovery(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        self._call("prepare_recovery")
        self.installed = False

    def check_resources_interruption(
        self,
        site: SiteConfiguration,
        manifest: ModelManifest,
        *,
        allow_stopped: bool = False,
    ) -> None:
        self._call("check_resources_interruption")

    def stop_resources_anchor(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        self._call("stop_resources_anchor")

    def verify_resources_stopped(self, site: SiteConfiguration) -> None:
        self._call("verify_resources_stopped")

    def disable_observation(self) -> None:
        self._call("disable_observation")

    def stop_and_remove(self) -> None:
        self._call("stop_and_remove")
        self.installed = False

    def verify_absent(self) -> None:
        self._call("verify_absent")
        if self.installed:
            raise ValueError("model_host_still_installed")
