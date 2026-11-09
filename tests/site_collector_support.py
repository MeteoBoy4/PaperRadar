"""仅离线合成部署配置;不代表当前站点。"""

import os
from pathlib import Path

from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.resources import ExecutionRoots


def site_configuration(root: Path) -> SiteConfiguration:
    return SiteConfiguration(
        product_uid=os.getuid(),
        product_gid=os.getgid(),
        database=root / "data/radar.sqlite3",
        snapshot_id="c" * 64,
        install_path=root / "installs/supply/install",
        credentials_dir=root / "credentials",
        roots=ExecutionRoots(
            root / "data", root / "config", root / "materials", root / "installs"
        ),
        binding=EvidenceBinding(
            "supply",
            "install",
            "pi-launch-1.4.0-v1",
            "pi-landlock-v1",
            "<cwd>\n/srv/pi-cwd\n</cwd>",
            "openai",
            "synthetic-model",
            "low",
            "provider_default",
            None,
            None,
            "pi-rpc-1.4.0-v1",
            "chatgpt_subscription",
        ),
        use_id="boundary-low",
    )
