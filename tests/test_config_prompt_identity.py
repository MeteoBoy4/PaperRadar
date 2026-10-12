"""提示词命名与路径重构保持已交付快照身份。"""

from collections.abc import Callable
from pathlib import Path

import pytest

from paper_radar.config import check_config, compile_config, load_config_snapshot
from tests.config_read_support import read_inputs
from tests.config_reuse_support import reuse_inputs
from tests.config_test_support import boundary_inputs, value_inputs


# 期望身份取自重构前的已验证提交 257ee92。测试不动态生成期望值。
@pytest.mark.parametrize(
    ("inputs", "expected_id"),
    [
        (
            boundary_inputs,
            "35942f627ddc5d4a7671de32ffebec1641f0a974784651d7102841e7e5fd57d3",
        ),
        (
            value_inputs,
            "66094fe3c37876b8a3967c4b7d2cae54e6df21895baa8497bac1a2bfdb50afff",
        ),
        (
            reuse_inputs,
            "bc833fa8b301b2d34fc1221b0ef0452f3ad9eee8bf8db331d290d6a4ab0d43d5",
        ),
        (
            read_inputs,
            "1f50123827c64158ff51f5bc30fab3de87321de3eacd18186a8824d3b54ba10c",
        ),
    ],
    ids=["boundary", "value", "reuse", "reading"],
)
def test_prompt_refactor_preserves_existing_snapshot_identity(
    tmp_path: Path,
    inputs: Callable[[Path], tuple[Path, Path]],
    expected_id: str,
) -> None:
    settings, db = inputs(tmp_path)
    checked = check_config(settings, db)
    assert checked.snapshot_id == expected_id
    saved = compile_config(settings, db)
    assert saved == checked == load_config_snapshot(db, expected_id)
