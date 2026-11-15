"""从同一Connection的持久事实装配完整Read资格,不接受调用方投影。"""

from dataclasses import replace

from sqlalchemy import Connection

from paper_radar.body import BodyService
from paper_radar.body.facts import project_facts
from paper_radar.body.models import BodyFacts
from paper_radar.body.pdf import valid_pdf_bytes
from paper_radar.eligibility import Concept, evaluate_paper
from paper_radar.read_tasks.models import ReadTaskError
from paper_radar.reading.context import ExtractionIdentity


def verify_pdf(body: BodyService, facts: BodyFacts) -> None:
    """业务写事务外验证实际 PDF 字节;领取事务仍重核其身份和全部资格。"""
    if facts.pdf is not None:
        raw = body.store.read_artifact(facts.pdf.artifact_id)["payload"]
        if not valid_pdf_bytes(raw, facts.pdf.pdf_sha256):
            raise ReadTaskError("facts_changed")


def require_facts(
    body: BodyService,
    connection: Connection,
    paper_id: str,
    identity: ExtractionIdentity,
) -> BodyFacts:
    facts = body.facts_in_connection(connection, paper_id, identity=identity)
    from paper_radar.feed_metadata import JGRMetadata

    metadata = JGRMetadata(body.database, body.data_root).facts_in_connection(
        connection, paper_id
    )
    projection = replace(project_facts(facts), metadata=metadata)
    eligibility = evaluate_paper(projection)[Concept.READ_PREREQUISITES]
    reasons = tuple(
        sorted(set((*map(str, facts.reasons), *map(str, eligibility.reasons))))
    )
    if reasons:
        raise ReadTaskError("prerequisites_failed", reasons=reasons)
    return facts
