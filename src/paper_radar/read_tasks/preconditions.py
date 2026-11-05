"""从同一Connection的持久事实装配完整Read资格,不接受调用方投影。"""

from sqlalchemy import Connection

from paper_radar.body import BodyService
from paper_radar.body.models import BodyFacts
from paper_radar.body.pdf import valid_pdf_bytes
from paper_radar.calibration.visibility import evaluate_visibility
from paper_radar.eligibility import (
    ArtifactFact,
    Concept,
    ExtractionFact,
    ExtractionState,
    PaperProjection,
    Presence,
    QualityFact,
    evaluate_paper,
)
from paper_radar.papers.queries import load_trace
from paper_radar.read_tasks.models import ReadTaskError
from paper_radar.reading.context import ExtractionIdentity


def require_facts(
    body: BodyService,
    connection: Connection,
    paper_id: str,
    identity: ExtractionIdentity,
) -> BodyFacts:
    facts = body.facts_in_connection(connection, paper_id, identity=identity)
    if facts.pdf is not None:
        raw = body.store.read_artifact_in_connection(connection, facts.pdf.artifact_id)[
            "payload"
        ]
        if not valid_pdf_bytes(raw, facts.pdf.pdf_sha256):
            raise ReadTaskError("facts_changed")
    trace = load_trace(connection, paper_id)
    current = trace.current
    from paper_radar.feed_metadata import JGRMetadata

    metadata = JGRMetadata(body.database, body.data_root).facts_in_connection(
        connection, paper_id
    )
    pdf, extraction = facts.pdf, facts.extraction
    projection = PaperProjection(
        paper_id,
        current.version_id,
        current.version_id,
        canonical_id=paper_id,
        revision_no=current.revision_no,
        metadata=metadata,
        decisions=(facts.decision.fact,) if facts.decision else (),
        pdf=ArtifactFact(Presence.PRESENT, pdf.artifact_id, pdf.version_id, "current")
        if pdf
        else ArtifactFact(Presence.ABSENT),
        extraction=ExtractionFact(
            ExtractionState.SUCCEEDED,
            extraction.artifact_id,
            pdf.artifact_id,
            "current",
        )
        if extraction and extraction.artifact_id and pdf
        else ExtractionFact(ExtractionState.ABSENT),
        quality=extraction.quality if extraction else QualityFact(),
        root_purpose=facts.root.purpose,
        execution_source=facts.execution_source,
        visibility=evaluate_visibility(frozenset()),
    )
    eligibility = evaluate_paper(projection)[Concept.READ_PREREQUISITES]
    reasons = tuple(
        sorted(set((*map(str, facts.reasons), *map(str, eligibility.reasons))))
    )
    if reasons:
        raise ReadTaskError("prerequisites_failed", reasons=reasons)
    return facts
