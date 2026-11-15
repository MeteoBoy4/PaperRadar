"""B 收口独立 D1:可选封印构建消费完整准入权威,不授予Live能力。"""

import json
import shutil
from pathlib import Path

import pytest

from paper_radar.live_evidence.live_bundle import assert_source_guard
from tests.test_live_admission_source_guard import MANIFEST, ROOT, SOURCE_FILES


@pytest.mark.parametrize(
    "relative",
    (
        "src/paper_radar/experiment/egress.py",
        "src/paper_radar/experiment/model_mapping.py",
        "src/paper_radar/experiment/screening.py",
        "src/paper_radar/experiment/reading.py",
        "src/paper_radar/body/selection.py",
        "src/paper_radar/config/adapters.py",
        "src/paper_radar/read_tasks/service.py",
        "src/paper_radar/screening_tasks/execution.py",
        "src/paper_radar/screening/schema.py",
        "src/paper_radar/screening/validation.py",
        "src/paper_radar/contracts/schema.py",
        "src/paper_radar/reading/acceptance_v2/__init__.py",
    ),
)
def test_optional_bundle_refuses_changed_execution_authority(
    tmp_path: Path, relative: str
) -> None:
    assert relative in SOURCE_FILES
    vector = json.loads(MANIFEST.read_bytes())
    assert len(SOURCE_FILES) == len(set(SOURCE_FILES))
    assert set(vector["files"]) == set(SOURCE_FILES)
    for name in (*SOURCE_FILES, MANIFEST.relative_to(ROOT).as_posix()):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    assert_source_guard(tmp_path)
    changed = tmp_path / relative
    changed.write_bytes(changed.read_bytes() + b"\n# unreviewed authority change\n")
    with pytest.raises(ValueError, match=r"^source_guard_mismatch$"):
        assert_source_guard(tmp_path)
