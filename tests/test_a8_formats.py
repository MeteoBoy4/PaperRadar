"""固定生产渲染默认值和封闭协议档案;不以常量冒充实际格式。"""

from dataclasses import fields
from pathlib import Path

import pytest


@pytest.mark.parametrize("domain", ["render", "render_default", "profile"])
@pytest.mark.parametrize("value", [2, True, 1.0])
def test_rpc_production_formats_cannot_drift_or_disguise_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, domain: str, value: object
) -> None:
    from paper_radar.llm import models
    from tests.a8_acceptance_support import conclude, same_a8_run

    inputs = same_a8_run(tmp_path)
    if domain == "render_default":
        field = next(
            field
            for field in fields(models.CallDescription)
            if field.name == "render_format"
        )
        monkeypatch.setattr(field, "default", value)
    elif domain == "render":
        monkeypatch.setattr(models, "RENDER_FORMAT", value)
    else:
        monkeypatch.setattr(models, "PROTOCOL_PROFILES", {"1.4.0": value})
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert "rpc_format_drift" in {reason["code"] for reason in result["reasons"]}
