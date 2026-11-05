"""预检原因闭集与外部 worker 警告协议的安全边界。"""

import pytest
from pydantic import ValidationError

from paper_radar.docling_execution.models import WorkerResponse
from paper_radar.docling_executor import DoclingPreflightError, DoclingPreflightReason


@pytest.mark.parametrize(
    "reason,guidance",
    [
        ("dependency_missing", "uv sync --offline --locked --extra docling"),
        ("dependency_inconsistent", "修复模块发现与发行包元数据不一致"),
        ("dependency_version_mismatch", "匹配所选工具链精确版本"),
        ("platform_unknown", "核对 Linux x86_64、glibc 与 CPython"),
        ("platform_unsupported", "使用受支持的 Linux x86_64 CPython"),
        ("selection_invalid", "check/compile"),
        ("runtime_selection_invalid", "check/compile"),
        ("model_deployment_invalid", "deployment.json"),
    ],
)
def test_preflight_reasons_keep_existing_values_and_safe_guidance(
    reason: str, guidance: str
) -> None:
    error = DoclingPreflightError(reason)
    assert isinstance(error.reason, DoclingPreflightReason)
    assert error.reason == reason
    assert guidance in str(error) and "未领取尝试" in str(error)


def test_unknown_preflight_reason_is_rejected_without_echo() -> None:
    with pytest.raises(ValueError, match="Docling 预检原因无效") as error:
        DoclingPreflightError("PRIVATE PATH OR EXTERNAL EXCEPTION")
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize(
    "warnings,error_type",
    [
        (("formula_candidate_unavailable",) * 3, "too_long"),
        (("not_a_worker_warning",), "literal_error"),
    ],
)
def test_worker_warning_protocol_retains_length_and_closed_values(
    warnings: tuple[str, ...], error_type: str
) -> None:
    with pytest.raises(ValidationError) as error:
        WorkerResponse.model_validate(
            {"failure": "executor_error", "warnings": warnings}
        )
    assert [(e["loc"], e["type"]) for e in error.value.errors()] == [
        (("warnings",) if error_type == "too_long" else ("warnings", 0), error_type)
    ]
