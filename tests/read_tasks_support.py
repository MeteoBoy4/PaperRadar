"""Read公共服务组合,替身仅在parser及上游RPC执行边界。"""

from dataclasses import replace
from pathlib import Path
from typing import Any

from paper_radar.body import BodyService
from paper_radar.body.models import CanonicalParser, ExtractionView
from paper_radar.config import compile_config
from paper_radar.screening.reasons import (
    DecisionReason,
    ScreeningReasonInput,
    ScreeningResult,
    ScreeningSource,
)
from paper_radar.screening_tasks import ScreeningTasks, SuccessReceipt
from tests.a7_registration_support import Archive as TaskArchive
from tests.a7_registration_support import request_for
from tests.a8_call_support import Archive
from tests.body_support import CHECKS, PDF, Parser
from tests.config_extraction_support import EXTRACTION_YAML
from tests.pi_rpc_source_support import NOW, candidate, source_archive
from tests.read_support import candidate as read_candidate


def ready(
    root: Path, *, missing: str | None = None, parser: CanonicalParser | None = None
) -> tuple[Archive, BodyService, ExtractionView]:
    data, supplied = source_archive(root)
    config = data.settings.parent
    (config / "extraction").mkdir()
    (config / "extraction/extraction-v1.yaml").write_text(EXTRACTION_YAML)
    (config / "read").mkdir()
    (config / "read/read-v1.yaml").write_text(
        "version: read-v1\nchunking_version: v1\n"
    )
    prompt_root = root / "prompts/reading"
    prompt_root.mkdir(parents=True)
    (prompt_root / "v1.md").write_text("Read synthetic prompt\n")
    import yaml

    settings = yaml.safe_load(data.settings.read_text())
    settings.update(extraction="extraction-v1", read="read-v1")
    settings["prompts"]["reading"] = "v1"
    from paper_radar.contracts import export_frozen_contract

    export_frozen_contract("read", "v1", root / "contracts")
    settings["contracts"]["read"] = "v1"
    settings["adapters"]["reading"] = settings["adapters"]["screening"]
    data.settings.write_text(yaml.safe_dump(settings))
    model_file = config / "models/models-source-v1.yaml"
    models = yaml.safe_load(model_file.read_text())
    models["version"] = "models-read-v1"
    models["reading"] = dict(models["screening"])
    (config / "models/models-read-v1.yaml").write_text(yaml.safe_dump(models))
    settings["models"] = "models-read-v1"
    data.settings.write_text(yaml.safe_dump(settings))
    data = replace(
        data, snapshot_id=compile_config(data.settings, data.database).snapshot_id
    )
    import httpx

    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.papers import PaperFacts
    from paper_radar.sources.feeds import endpoint
    from tests.feed_support import item

    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed(endpoint("jgr"))
    papers.submit(item(feed.feed_id, doi="10.1234/abc"))

    def respond(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": "10.1234/abc", "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1234/abc",
                        "title": ["Synthetic title"],
                        "abstract": (
                            "A synthetic atmospheric study with a complete abstract "
                            "describing methods and observations in detail."
                        ),
                        "type": "journal-article",
                    }
                },
            )
        return httpx.Response(403)

    metadata = JGRMetadata(
        data.database,
        data.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )
    if missing != "metadata":
        result = metadata.enrich(
            data.paper_id, request_id="metadata", contact_email="contact@example.org"
        )
        assert result.minimum_complete
    body = BodyService(data.database, data.data_root)
    body.register_root("experiment")
    pdf = body.attach_pdf(data.paper_id, PDF, request_id="pdf")
    if missing != "sample":
        body.freeze_sample(
            data.paper_id,
            feed_id=feed.feed_id,
            pdf_sha256=pdf.pdf_sha256,
            reason="synthetic selection",
            request_id="sample",
        )
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = tasks.register(
        request_for(
            TaskArchive(
                data.settings,
                data.database,
                data.data_root,
                data.snapshot_id,
                data.paper_id,
                data.version_id,
            )
        )
    )
    success = tasks.run_once(
        registered.receipt_id, lambda *_: candidate(data, supplied)
    )
    assert isinstance(success, SuccessReceipt)
    if missing != "accepted":
        body.decide(
            data.paper_id,
            ScreeningReasonInput(
                result=ScreeningResult.ACCEPTED,
                source=ScreeningSource.DIRECT_MANUAL_DECISION,
                reason=DecisionReason.USER_JUDGMENT,
            ),
            request_id="accept",
            actor="human",
            screening_references=(success.success_id,),
        )
    extracted = body.extract(
        data.paper_id, snapshot_id=data.snapshot_id, parser=parser or Parser()
    )
    assert extracted.identity
    if missing != "quality":
        body.review_layout(
            extracted.identity,
            passed=True,
            checks=CHECKS,
            note="checked",
            actor="human",
            request_id="review",
        )
    return data, body, extracted


def valid_candidate(**changes: Any) -> bytes:
    import json

    output = json.loads(read_candidate(**changes))
    for key in ("research_value_reason", "reuse_feasibility_reason"):
        if key not in changes:
            output[key]["evidence"] = [{"evidence_id": "e000002"}]
    return json.dumps(output, ensure_ascii=False).encode()
