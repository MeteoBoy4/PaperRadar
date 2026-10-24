"""Read 契约配置集成的合成材料,不提供执行许可。"""

from pathlib import Path

from paper_radar.contracts import export_frozen_contract
from tests.config_read_support import read_inputs


def read_contract_inputs(root: Path) -> tuple[Path, Path]:
    settings, database = read_inputs(root)
    export_frozen_contract("read", "v1", root / "contracts")
    settings.write_text(
        settings.read_text().replace(
            "  boundary: v1\nread:", "  boundary: v1\n  read: v1\nread:"
        ),
        encoding="utf-8",
    )
    return settings, database
