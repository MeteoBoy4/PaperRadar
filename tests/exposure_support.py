"""合成持久事实工厂;导出断言通过真实产品 CLI。"""

from pathlib import Path
from typing import Any

from pydantic import TypeAdapter
from typer.testing import CliRunner, Result

from paper_radar.body import BodyService
from paper_radar.cli import app
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.papers import PaperFacts
from paper_radar.screening.reasons import ScreeningReasonInput
from tests.test_experiment_candidates_cli import invoke
from tests.test_experiment_exposure_cli import export
from tests.test_paper_service import observation


def initialized(path: Path) -> ExperimentRoot:
    assert invoke("init", "--root", str(path)).exit_code == 0
    return ExperimentRoot(path)


def decision(
    root: ExperimentRoot, paper_id: str, request: str = "manual-exposure"
) -> None:
    BodyService(root.database, root.data_root).decide(
        paper_id,
        ScreeningReasonInput.model_validate(
            {
                "source": "direct_manual_decision",
                "result": "denied",
                "reason": "low_value",
            }
        ),
        request_id=request,
        actor="owner",
    )


def exposed(
    root: ExperimentRoot,
    *,
    doi: str | None = "10.1/exposed",
    version_kind: str = "journal",
) -> tuple[str, str]:
    papers = PaperFacts(root.database, root.data_root)
    if doi is None:
        from tests.feed_support import item

        source = papers.register_feed("https://feeds.example/exposure")
        result = papers.submit(item(source.feed_id))
    else:
        result = papers.submit(observation(doi=doi, version_kind=version_kind))
    assert result.paper_id and result.version_id
    decision(root, result.paper_id)
    return result.paper_id, result.version_id


def payload(root: ExperimentRoot) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    receipt = export(root.root)
    raw = (root.views / receipt["relative_path"]).read_bytes()
    return receipt, TypeAdapter(dict[str, Any]).validate_json(raw), raw


def backup(root: ExperimentRoot, output: Path) -> Result:
    return CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(output),
        ],
    )
