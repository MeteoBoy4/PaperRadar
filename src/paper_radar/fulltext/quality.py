"""完整规范制品的自动质量检查;不授予人工/正式质量资格。"""

import json
import math
import re
from collections.abc import Mapping

from paper_radar.eligibility import QualityFailure
from paper_radar.fulltext.models import (
    AutomaticQuality,
    EvidenceMap,
    QualityIssue,
    Source,
)
from paper_radar.fulltext.normalization import render_reading
from paper_radar.reading.context import (
    Evidence,
    ExtractionIdentity,
    PageFact,
    Provenance,
    ReadContext,
    SourceBlock,
)
from paper_radar.reading.errors import ReadContextError

EMBEDDED_BINARY = re.compile(
    rb"(?:data:[^\s;,]+(?:;[^,\s]+)*;base64,|[\"'](?:base64|image_data)[\"']\s*:)", re.I
)


def reconstruct_context(
    evidence_map: EvidenceMap,
    identity: ExtractionIdentity,
    *,
    expected_language: str = "zh",
) -> ReadContext:
    if expected_language not in ("zh", "en"):
        raise ValueError("expected_language 必须是 zh 或 en")
    by_source = {source.source_id: source for source in evidence_map.source_blocks}
    pages = {page.page_no: page for page in evidence_map.pages}
    evidence: list[Evidence] = []
    for entry in evidence_map.evidence:
        source = by_source[entry.source_id]
        provenance = []
        for p in source.provenance:
            page = pages[p.page_no]
            bbox = p.bbox
            if p.origin != page.origin:
                bbox = (bbox[0], page.height - bbox[3], bbox[2], page.height - bbox[1])
            provenance.append(
                Provenance(source.source_id, p.page_no, bbox, *p.charspan)
            )
        evidence.append(Evidence(identity, entry.evidence_id, provenance))
    return ReadContext(
        identity=identity,
        pages=tuple(
            PageFact(identity, page.page_no, page.width, page.height, page.origin)
            for page in evidence_map.pages
        ),
        source_blocks=tuple(
            SourceBlock(
                identity, source.source_id, source.orig, source.kind, source.unreliable
            )
            for source in evidence_map.source_blocks
        ),
        evidence=tuple(evidence),
        expected_language="zh" if expected_language == "zh" else "en",
    )


def check_quality(
    evidence_map: EvidenceMap,
    identity: ExtractionIdentity,
    members: Mapping[str, bytes],
) -> AutomaticQuality:
    issues: list[QualityIssue] = []

    def fail(failure: QualityFailure, location: str) -> None:
        issue = QualityIssue(failure, location)
        if issue not in issues:
            issues.append(issue)

    if not evidence_map.has_text_layer or not any(
        s.orig.strip() for s in evidence_map.source_blocks
    ):
        fail(QualityFailure.PDF_TEXT_LAYER, "$.source_blocks")
    if not evidence_map.evidence:
        fail(QualityFailure.BODY_BOUNDARY, "$.evidence")
    try:
        reconstruct_context(evidence_map, identity)
    except (ReadContextError, KeyError):
        fail(QualityFailure.EVIDENCE_REPLAY, "$.evidence")
    for index, source in enumerate(evidence_map.source_blocks):
        if not source_is_replayable(source, evidence_map, identity):
            fail(QualityFailure.EVIDENCE_REPLAY, f"$.source_blocks[{index}]")
    if members["reading"] != render_reading(evidence_map):
        fail(QualityFailure.CONTENT_IDENTITY, "$.reading")
    for role, raw in sorted(members.items()):
        inspected = raw
        if role != "reading":
            try:
                # 只检查已解码内容形态;document 不用于重建任何源块。
                inspected = json.dumps(json.loads(raw), ensure_ascii=False).encode(
                    "utf-8"
                )
            except (UnicodeError, ValueError):
                fail(QualityFailure.TEXT_INTEGRITY, f"$.{role}")
        if EMBEDDED_BINARY.search(inspected):
            fail(QualityFailure.EMBEDDED_BINARY, f"$.{role}")
        try:
            text = inspected.decode("utf-8")
        except UnicodeError:
            fail(QualityFailure.TEXT_INTEGRITY, f"$.{role}")
        else:
            if "\ufffd" in text:
                fail(QualityFailure.TEXT_INTEGRITY, f"$.{role}")
    sources = {source.source_id: source for source in evidence_map.source_blocks}
    pages = {page.page_no: page for page in evidence_map.pages}
    for index, block in enumerate(evidence_map.reading_blocks):
        location = f"$.reading_blocks[{index}]"
        associated_source = sources.get(block.source_id or "")
        if (block.role != "source" and associated_source is not None) or (
            block.role == "source"
            and associated_source is not None
            and block.display_text != associated_source.orig
        ):
            fail(QualityFailure.SOURCE_GENERATED_SEPARATION, location)
        if (
            block.role == "source"
            and associated_source is None
            and block.label not in {"formula", "picture", "chart"}
            and block.display_text.strip()
        ):
            fail(QualityFailure.SOURCE_GENERATED_SEPARATION, location)
        if block.label in {"formula", "picture", "chart"} and associated_source is None:
            if not block.provenance:
                fail(QualityFailure.EVIDENCE_REPLAY, location + ".provenance")
            for p in block.provenance:
                page = pages.get(p.page_no)
                if (
                    page is None
                    or not all(math.isfinite(value) for value in p.bbox)
                    or not 0 <= p.bbox[0] < p.bbox[2] <= page.width
                    or not 0 <= p.bbox[1] < p.bbox[3] <= page.height
                    or p.charspan != (0, 0)
                ):
                    fail(QualityFailure.EVIDENCE_REPLAY, location + ".provenance")
    return AutomaticQuality(tuple(issues))


def source_is_replayable(
    source: Source, evidence_map: EvidenceMap, identity: ExtractionIdentity
) -> bool:
    """统计与质量共用:完整定位、非空逐字切片,且覆盖所有非空白 orig。"""
    from paper_radar.fulltext.models import EvidenceEntry

    view = evidence_map.model_copy(
        update={
            "source_blocks": (source,),
            "evidence": (
                EvidenceEntry(evidence_id="quality-check", source_id=source.source_id),
            ),
        }
    )
    try:
        reconstruct_context(view, identity)
    except (ReadContextError, KeyError):
        return False
    cursor = 0
    for p in sorted(source.provenance, key=lambda p: p.charspan):
        start, end = p.charspan
        if source.orig[cursor:start].strip():
            return False
        cursor = max(cursor, end)
    return not source.orig[cursor:].strip()
