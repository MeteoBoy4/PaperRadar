"""封印合成配置只编译,不写业务配置或任务。"""

import os
from pathlib import Path

import pytest

from paper_radar.config.service import compile_materials
from paper_radar.live_evidence.receipt import UseId
from tests.config_test_support import boundary_inputs


def test_compile_materials_does_not_require_or_create_database(tmp_path: Path) -> None:
    settings, database = boundary_inputs(tmp_path)
    database.unlink()
    snapshot = compile_materials(settings)
    assert snapshot.snapshot_id
    assert not database.exists()


@pytest.mark.parametrize(
    "use_id",
    [
        "boundary-low",
        "boundary-high",
        "value-low",
        "value-high",
        "read-low",
        "read-high",
    ],
)
def test_product_worker_uses_public_prepare_rpc_and_authority_without_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, use_id: UseId
) -> None:
    import hashlib
    import json

    import yaml

    from paper_radar.config import StageName
    from paper_radar.contracts import export_frozen_contract
    from paper_radar.live_evidence.model_manifest import ModelCell
    from paper_radar.live_evidence.model_worker import execute_model
    from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
    from paper_radar.llm import build_call, render_request
    from paper_radar.pi_execution.admission import bind_description
    from paper_radar.pi_execution.resources import LAUNCH_POLICY_VERSION
    from paper_radar.pi_supply import activation_history
    from paper_radar.stage_inputs import (
        ExtractionFacts,
        ReadFacts,
        ScreeningFacts,
        build_stage_input,
    )
    from tests.config_projection_support import full_inputs
    from tests.pi_execution_support import launch_inputs
    from tests.test_live_collection_v2 import BINDING, approved

    template = (
        Path(__file__).parent
        / (
            "read_execution_peer.py"
            if use_id.startswith("read")
            else "pi_execution_rpc_peer.py"
        )
    ).read_text()
    template = template.replace("__DATABASE__", str(tmp_path / "db.sqlite3")).replace(
        "__CREDENTIALS__", str(tmp_path / "credentials/auth.json")
    )
    database, _, roots, credentials, cwd = launch_inputs(
        tmp_path, monkeypatch, peer=template
    )
    directory = tmp_path / "runtime/materials" / use_id
    directory.mkdir(parents=True)
    settings, synthetic_database = full_inputs(directory)
    synthetic_database.unlink()
    adapter = settings.parent / "adapters/pi-v1.yaml"
    adapter.write_text(
        adapter.read_text()
        .replace("1.1.0", "1.4.0")
        .replace("thinking_level: low", "thinking_level: " + use_id.rsplit("-", 1)[1])
    )
    models = settings.parent / "models/models-v1.yaml"
    models.write_text(
        models.read_text()
        .replace("provider-a", "openai")
        .replace("shared-model", "real-model")
    )
    selectors = yaml.safe_load(settings.read_text())
    selectors["contracts"]["read"] = "v1"
    export_frozen_contract("read", "v1", directory / "contracts")
    settings.write_text(yaml.safe_dump(selectors))
    snapshot = compile_materials(settings)
    stage = StageName(use_id.rsplit("-", 1)[0])
    context = None
    reading = None
    facts: ReadFacts | ScreeningFacts
    if stage == StageName.READ:
        from paper_radar.fulltext.normalization import (
            canonical_json,
            normalize_document,
            render_reading,
        )
        from paper_radar.fulltext.quality import reconstruct_context
        from paper_radar.reading import ExtractionIdentity
        from tests.test_fulltext_artifacts import document

        extraction = build_stage_input(
            snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
        )
        (directory / "extraction.json").write_text(json.dumps({"pdf_sha256": "1" * 64}))
        evidence = normalize_document(document())
        evidence_raw = canonical_json(evidence.model_dump(mode="json"))
        (directory / "evidence-map.json").write_bytes(evidence_raw)
        reading = render_reading(evidence)
        (directory / "reading.md").write_bytes(reading)
        identity = ExtractionIdentity(
            extraction.fingerprint,
            hashlib.sha256(reading).hexdigest(),
            hashlib.sha256(evidence_raw).hexdigest(),
        )
        context = reconstruct_context(evidence, identity)
        facts = ReadFacts(
            extraction_input=extraction,
            reading_sha256=identity.reading_sha256,
            evidence_map_sha256=identity.evidence_map_sha256,
            output_language="zh",
        )
    else:
        facts = ScreeningFacts(
            title="Synthetic weather study",
            abstract="A synthetic comparison of weather methods.",
            abstract_truncated=False,
        )
        (directory / "abstract.json").write_text(
            json.dumps(
                {
                    "title": facts.title,
                    "abstract": facts.abstract,
                    "abstract_truncated": False,
                }
            )
        )
    stage_input = build_stage_input(snapshot, stage, facts)
    description = build_call(
        stage_input, snapshot, snapshot, read_context=context, reading=reading
    )
    latest = activation_history(database)[-1]
    model = bind_description(
        description,
        supply_id=latest.supply_id,
        install_id=latest.install_id,
        launch_policy_version=LAUNCH_POLICY_VERSION,
        isolation_policy_version="pi-landlock-v1",
        cwd_section="<cwd>\n" + str(cwd) + "\n</cwd>",
        auth_mode="chatgpt_subscription",
    )
    cell = ModelCell(
        use_id=use_id,
        plan=ApprovedPlanV2.model_validate(
            {
                **approved().model_dump(),
                "cases": ["model-" + use_id],
                "max_network_requests": 0,
            }
        ),
        binding=BINDING,
        model=model,
        material_sha256="a" * 64,
        snapshot_id=snapshot.snapshot_id,
        request_sha256=hashlib.sha256(render_request(description)).hexdigest(),
    )
    site = SiteConfiguration(
        product_uid=os.getuid(),
        product_gid=os.getgid(),
        database=database,
        snapshot_id=latest.snapshot_id,
        install_path=roots.install_root / latest.supply_id / latest.install_id,
        credentials_dir=credentials,
        roots=roots,
        binding=model,
        use_id=use_id,
    )
    stages = []
    observed = execute_model(
        tmp_path / "runtime", site, cell, lambda stage, *args: stages.append(stage)
    )
    assert observed.passed, observed
    assert stages == ["auth", "prepared", "model"]
    assert observed.authority == stage.value and observed.input_tokens == 5
    assert not synthetic_database.exists()
    assert activation_history(database)[-1] == latest
