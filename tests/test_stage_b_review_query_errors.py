"""D1:组合只读 CLI 的受控故障诊断,不调用外部执行器。"""

from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import pytest
from typer.testing import CliRunner

from paper_radar.body import BodyError
from paper_radar.cli import app
from paper_radar.config import ConfigError
from paper_radar.experiment.acceptance import AcceptanceError
from paper_radar.experiment.extraction import ExtractionError
from paper_radar.experiment.layout import LayoutError
from paper_radar.experiment.pdf import PdfError
from paper_radar.experiment.selections import SelectionError
from paper_radar.feed_pipeline import PipelineError
from paper_radar.fulltext.models import FulltextError
from paper_radar.papers import PaperError
from paper_radar.papers.errors import PaperReason
from paper_radar.read_tasks import ReadTaskError
from paper_radar.screening_tasks import TaskError, TaskReason
from paper_radar.stage_inputs import BuildReason, InputField, StageInputError
from paper_radar.storage.errors import StorageError, StorageReason

type QueryError = (
    PdfError
    | ReadTaskError
    | AcceptanceError
    | LayoutError
    | ExtractionError
    | SelectionError
    | BodyError
    | PipelineError
    | FulltextError
    | PaperError
    | ConfigError
    | TaskError
    | StorageError
    | StageInputError
)


@pytest.mark.parametrize("command", ("show", "trace"))
@pytest.mark.parametrize(
    "error",
    (
        PdfError("registration_invalid"),
        ReadTaskError("corrupt_reference"),
        AcceptanceError("registration_invalid"),
        LayoutError("registration_invalid"),
        ExtractionError("registration_invalid"),
        SelectionError("registration_invalid"),
        BodyError("database_failed"),
        PipelineError("corrupt_reference"),
        FulltextError("invalid_members"),
        PaperError(PaperReason.CORRUPT_REFERENCE, path="PRIVATE-PATH"),
        ConfigError("PRIVATE-CONFIG"),
        TaskError(TaskReason.CORRUPT_REFERENCE),
        StorageError("PRIVATE-STORAGE", reason=StorageReason.DATABASE_MISSING),
        StageInputError(BuildReason.NOT_READY, InputField.SNAPSHOT),
    ),
)
def test_paper_composition_fault_is_controlled(
    command: str, error: QueryError, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = SimpleNamespace(model_dump=lambda **kwargs: {})
    monkeypatch.setattr("paper_radar.papers.service.PaperFacts.show", lambda *a: fake)
    monkeypatch.setattr(
        "paper_radar.papers.service.PaperFacts.trace", lambda *a, **kw: fake
    )

    def fail(*args: object, **kwargs: object) -> NoReturn:
        raise error

    monkeypatch.setattr("paper_radar.paper_trace.query_paper_trace", fail)
    missing = tmp_path / "private-location" / "never-opened.sqlite3"
    result = CliRunner().invoke(
        app,
        [
            "paper",
            command,
            "private-input",
            "--database",
            str(missing),
            "--json",
            "--workflow",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "论文查询失败" in result.output
    assert "请核对" in result.output
    assert f"[{error.reason}]" in result.output
    assert "PRIVATE-" not in result.output
    assert "private-input" not in result.output
    assert str(missing) not in result.output
    assert not missing.parent.exists()


def test_screening_root_query_fault_is_controlled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail(*args: object) -> NoReturn:
        raise BodyError("database_failed")

    monkeypatch.setattr("paper_radar.body.service.BodyService.root", fail)
    result = CliRunner().invoke(
        app,
        [
            "screening",
            "failures",
            "--database",
            str(tmp_path / "missing.sqlite3"),
            "--snapshot",
            "private-snapshot",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "Screening 拒绝 [database_failed]" in result.output
    assert "请回查" in result.output
    assert "private-snapshot" not in result.output
