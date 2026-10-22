"""A6 必须核对映射结果模型实际格式,严格拒绝伪整数版本。"""

from pathlib import Path

import pytest

from tests.a6_acceptance_support import conclude, same_a6_run


def test_a6_records_actual_mapping_result_format(tmp_path: Path) -> None:
    _, result = conclude(tmp_path, same_a6_run(tmp_path))
    assert result["format_versions"]["mapping_result"] == 1
    assert result["status"] == "passed"
    assert type(result["format_versions"]["mapping_result"]) is int


@pytest.mark.parametrize("version", [2, True, 1.0])
def test_mapping_result_model_format_drift_blocks_a6(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: object,
) -> None:
    from paper_radar.papers.mapping_models import ScreeningMappingResult

    inputs = same_a6_run(tmp_path)
    current = ScreeningMappingResult.__dataclass_fields__["format_version"]
    monkeypatch.setattr(current, "default", version)
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert result["a6_verified"] is False
    assert "paper_fact_format_drift" in {reason["code"] for reason in result["reasons"]}
    assert type(result["format_versions"]["mapping_result"]) is type(version)
