"""显式替代宿主I/O的Live封印工程模型;不伪称真实OS证明。"""

import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from paper_radar.live_evidence.live_bundle import build_live_bundle, derive_site
from paper_radar.live_evidence.live_install import InstallationPaths
from paper_radar.live_evidence.model_manifest import USES, ModelManifest
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from tests.site_collector_support import site_configuration


def bundle_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    real_freeze: bool = False,
    upgrade_from: tuple[str, str] | None = None,
) -> tuple[Path, InstallationPaths]:
    site = site_configuration(tmp_path).model_copy(update={"claim_uses": USES})
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
    output = tmp_path / "review"
    hashes = build_live_bundle(
        output,
        site,
        starts_at=start,
        ends_at=start + timedelta(days=14),
        source_root=Path(__file__).resolve().parents[1],
        upgrade_from=upgrade_from,
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

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail == name:
            raise ValueError("model_interruption")

    def preflight(self, site: SiteConfiguration) -> None:
        self._call("preflight")

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

    def disable_observation(self) -> None:
        self._call("disable_observation")

    def stop_and_remove(self) -> None:
        self._call("stop_and_remove")
        self.installed = False

    def verify_absent(self) -> None:
        self._call("verify_absent")
        if self.installed:
            raise ValueError("model_host_still_installed")
