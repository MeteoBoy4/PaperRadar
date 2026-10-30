"""通过公共事件入口守卫领域原因覆盖和独立安全白名单。"""

from pathlib import Path
from typing import get_args

import pytest

from paper_radar.fixture_audit.acquisition_models import SourceReason
from paper_radar.runtime_logging import FileSink, RuntimeLog
from paper_radar.screening_tasks import FailureKind
from paper_radar.screening_tasks.errors import TaskReason
from tests.test_runtime_logging_files import records


@pytest.mark.parametrize(
    ("event", "component", "field", "value"),
    [
        *[("route_settled", "audit", "category", v) for v in get_args(SourceReason)],
        *[("failed", "screening", "kind", v.value) for v in FailureKind],
        *[("submit_rejected", "screening", "reason", v.value) for v in TaskReason],
    ],
)
def test_all_domain_reasons_can_be_logged_without_implicit_allowing(
    tmp_path: Path, event: str, component: str, field: str, value: str
) -> None:
    # 领域侧新增值会经过独立运行期白名单;尚未审查放行就必须失败。
    RuntimeLog(FileSink(tmp_path)).emit(event, component=component, **{field: value})
    assert [record[field] for record in records(tmp_path)] == [value]


@pytest.mark.parametrize("field", ["category", "kind", "reason"])
@pytest.mark.parametrize(
    "value",
    ["new_unreviewed_reason", "https://host/?token=PRIVATE", "PRIVATE_RAW_RESPONSE"],
)
def test_unknown_or_payload_reason_rejects_the_whole_event(
    tmp_path: Path, capfd: pytest.CaptureFixture[str], field: str, value: str
) -> None:
    RuntimeLog(FileSink(tmp_path)).emit(
        "failed", component="screening", **{field: value}
    )
    assert not (tmp_path / "logs").exists()
    out, err = capfd.readouterr()
    assert out == ""
    assert err in {"", "运行日志写入失败，业务继续。\n"}
