"""#185 r1/r2 独立 D1:产品错误词汇与非法运行时输入。"""

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import pytest

from paper_radar.experiment.acceptance import AcceptanceError
from paper_radar.experiment.body_selection import BodySelectionError
from paper_radar.experiment.egress import EgressError
from paper_radar.experiment.extraction import ExtractionError
from paper_radar.experiment.layout_errors import LayoutError
from paper_radar.experiment.pdf import PdfError
from paper_radar.experiment.reading import ReadingError
from paper_radar.experiment.reports import ReportError
from paper_radar.experiment.screening import ScreenError


def test_mapping_result_rejects_unknown_runtime_state() -> None:
    from paper_radar.llm.rpc import RpcMappingResult
    from paper_radar.llm.rpc_types import RpcProblem, RpcReason

    runtime_constructor: Callable[..., RpcMappingResult] = RpcMappingResult
    with pytest.raises(RpcProblem) as error:
        runtime_constructor(state="PRIVATE_UNCONTROLLED_STATE")
    assert error.value.reason is RpcReason.INVALID_DESCRIPTION


@pytest.mark.parametrize(
    "error",
    [
        AcceptanceError,
        BodySelectionError,
        EgressError,
        ExtractionError,
        LayoutError,
        PdfError,
        ReadingError,
        ReportError,
        ScreenError,
    ],
)
def test_unknown_error_reason_is_controlled_without_echoing_input(
    error: type[
        AcceptanceError
        | BodySelectionError
        | EgressError
        | ExtractionError
        | LayoutError
        | PdfError
        | ReadingError
        | ReportError
        | ScreenError
    ],
) -> None:
    failure = error("PRIVATE_UNCONTROLLED_REASON")
    assert failure.reason == "invalid_reason"
    assert isinstance(failure.reason, StrEnum)
    assert "PRIVATE_UNCONTROLLED_REASON" not in str(failure)


def test_cli_rejects_unknown_stage_with_specific_reason(tmp_path: Path) -> None:
    from paper_radar.config import compile_config
    from tests.config_adapter_support import adapter_inputs
    from tests.test_stage_b_egress_preflight import invoke

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    snapshot = compile_config(settings, root / "paper-radar.sqlite3")
    result = invoke(
        "egress-authorize",
        "--root",
        str(root),
        "--snapshot",
        snapshot.snapshot_id,
        "--stage",
        "bogus",
        "--reason",
        "owner consent",
    )
    assert result.exit_code == 2, result.output
    assert "egress_scope_mismatch" in result.output
    assert "bogus" not in result.output


def test_readonly_report_history_cannot_publish_or_leave_prepared_facts(
    tmp_path: Path,
) -> None:
    from paper_radar.experiment.reports import ReportHistory, Reports
    from tests.test_stage_b_egress_preflight import invoke
    from tests.test_stage_b_report_renderer_migrations import database_facts

    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    database = root / "paper-radar.sqlite3"
    history = ReportHistory(database, root / "data")
    before = database_facts(database)
    assert history.history() == ()
    history.validate_all()
    reports = Reports(database, root / "data", None)
    with pytest.raises(ReportError) as error:
        reports.render(day="2026-11-14", timezone="Asia/Shanghai")
    assert error.value.reason == "output_directory_required"
    with pytest.raises(ReportError) as error:
        reports.rebuild("missing")
    assert error.value.reason == "output_directory_required"
    with pytest.raises(ReportError) as error:
        reports.replay()
    assert error.value.reason == "output_directory_required"
    assert database_facts(database) == before
