"""只使用合成 transport/RPC/Docling parser 的正文选择工厂。"""

import json

from typer.testing import Result

from paper_radar.body import BodyService
from paper_radar.config import compile_config
from paper_radar.reading.context import ExtractionIdentity
from tests.config_projection_support import new_yaml_version
from tests.experiment_layout_support import LayoutFixture
from tests.test_experiment_candidates_cli import invoke


def configure_another_extraction(prepared: LayoutFixture) -> None:
    root = prepared.extraction.root
    new_yaml_version(
        root.settings,
        "extraction",
        lambda c: c["models"]["layout"].update(commit_sha="9" * 40),
    )
    manifest = prepared.extraction.models / "deployment.json"
    deployment = json.loads(manifest.read_text())
    for model in deployment["models"]:
        if "layout" in model["repo_id"]:
            model["commit_sha"] = "9" * 40
    manifest.write_text(json.dumps(deployment))
    prepared.extraction.snapshot = compile_config(
        root.settings, root.database
    ).snapshot_id


def second_body(prepared: LayoutFixture) -> ExtractionIdentity:
    root = prepared.extraction.root
    configure_another_extraction(prepared)
    result = prepared.extraction.extract()
    assert result.exit_code == 0, result.output
    views = BodyService(root.database, root.data_root).extractions(
        prepared.extraction.prepared.paper_id
    )
    identities = [v.identity for v in views if v.identity != prepared.identity]
    assert len(identities) == 1 and identities[0] is not None
    return identities[0]


def choose(prepared: LayoutFixture, *, request: str = "choose-1") -> Result:
    return invoke(
        *prepared.args("body-select"),
        "--selector",
        "owner",
        "--recorder",
        "agent",
        "--request-id",
        request,
    )
