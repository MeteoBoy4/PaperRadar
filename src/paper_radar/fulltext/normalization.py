"""normalization v1:源块粒度、稳定序号和版面信号;不读取 SDK/数据库。"""

import hashlib
import json
from collections import Counter
from typing import Literal

from paper_radar.content_reliability import is_unreliable
from paper_radar.fulltext.canonical import CanonicalBlock, CanonicalDocument
from paper_radar.fulltext.models import (
    EvidenceEntry,
    EvidenceMap,
    FulltextError,
    ReadingBlock,
    Source,
)

NORMALIZATION_VERSION = "v1"
FORMULA_LABELS = frozenset({"formula"})
TABLE_LABELS = frozenset({"table"})
PLACEHOLDER_LABELS = frozenset({"picture", "chart"})
FURNITURE_LABELS = frozenset({"page_header", "page_footer", "page_number"})
COVER_HEADINGS = frozenset(
    {
        "repository cover sheet",
        "cover sheet",
        "license",
        "licence",
        "copyright and permissions",
        "授权许可",
        "版权声明",
    }
)


def canonical_json(value: object) -> bytes:
    """UTF-8、排序键、无额外空白/末尾换行、不转义非 ASCII、拒绝 NaN。"""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        raise FulltextError("invalid_encoding") from None


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_kind(label: str) -> Literal["text", "table", "formula"]:
    if label in FORMULA_LABELS:
        return "formula"
    if label in TABLE_LABELS:
        return "table"
    return "text"


def normalize_document(document: CanonicalDocument) -> EvidenceMap:
    if document.conversion_status != "success" or not document.pages_complete:
        raise FulltextError("conversion_incomplete")
    if not document.pages:
        raise FulltextError("conversion_incomplete")
    blocks = sorted(document.blocks, key=lambda block: block.order)
    if (
        len({block.ref for block in blocks}) != len(blocks)
        or len({block.order for block in blocks}) != len(blocks)
        or any(any(part < 0 for part in block.order) for block in blocks)
    ):
        raise FulltextError("ambiguous_reading_order")
    identifiers = {block.ref: f"b{index:06d}" for index, block in enumerate(blocks, 1)}
    if any(block.parent_ref not in identifiers for block in blocks if block.parent_ref):
        raise FulltextError("unknown_parent")
    parents = {block.ref: block.parent_ref for block in blocks}
    for block in blocks:
        seen: set[str] = set()
        current: str | None = block.ref
        while current is not None:
            if current in seen:
                raise FulltextError("invalid_hierarchy")
            seen.add(current)
            current = parents[current]
    cover_pages: set[int] = set()
    for page in sorted(document.pages, key=lambda page: page.page_no):
        page_blocks = [
            b for b in blocks if any(p.page_no == page.page_no for p in b.provenance)
        ]
        if any(b.orig.strip().casefold() in COVER_HEADINGS for b in page_blocks):
            cover_pages.add(page.page_no)
        else:
            break
    marginal = _repeated_marginal(blocks, document)
    sources: list[Source] = []
    reading: list[ReadingBlock] = []
    evidence: list[EvidenceEntry] = []
    previous_heading = 0
    for index, block in enumerate(blocks, 1):
        block_id = identifiers[block.ref]
        source_id = f"s{index:06d}" if bool(block.orig.strip()) else None
        excluded: Literal["cover", "furniture", "background"] | None = None
        if block.content_layer == "background":
            excluded = "background"
        elif (
            block.label in FURNITURE_LABELS
            or block.content_layer == "furniture"
            or block.ref in marginal
        ):
            excluded = "furniture"
        elif block.provenance and all(
            p.page_no in cover_pages for p in block.provenance
        ):
            excluded = "cover"
        heading = None
        if block.label in ("title", "section_header") and excluded is None:
            heading = min(max(block.heading_level or 1, 1), previous_heading + 1)
            previous_heading = heading
        if source_id:
            sources.append(
                Source(
                    source_id=source_id,
                    orig=block.orig,
                    text=block.text,
                    kind=source_kind(block.label),
                    unreliable=is_unreliable(block.orig, declared=block.unreliable),
                    provenance=block.provenance,
                )
            )
            if (
                excluded is None
                and block.label not in PLACEHOLDER_LABELS
                and block.role == "source"
            ):
                evidence.append(
                    EvidenceEntry(evidence_id=f"e{index:06d}", source_id=source_id)
                )
        display = block.orig if source_id and block.role == "source" else block.text
        if block.label in FORMULA_LABELS | PLACEHOLDER_LABELS and source_id is None:
            pages = ",".join(str(p.page_no) for p in block.provenance) or "?"
            kind = "公式" if block.label in FORMULA_LABELS else "图片"
            display = f"[{kind}不可用，见 PDF 第 {pages} 页]"
        reading.append(
            ReadingBlock(
                block_id=block_id,
                source_id=source_id,
                parent_id=identifiers.get(block.parent_ref)
                if block.parent_ref
                else None,
                label=block.label,
                content_layer=block.content_layer,
                role=block.role,
                heading_level=heading,
                excluded=excluded,
                display_text=display,
                generated_text=block.generated_text,
                formula_mode=block.formula_mode,
                provenance=block.provenance,
            )
        )
    return EvidenceMap(
        has_text_layer=document.has_text_layer,
        pages=tuple(sorted(document.pages, key=lambda page: page.page_no)),
        source_blocks=tuple(sources),
        reading_blocks=tuple(reading),
        evidence=tuple(evidence),
    )


def render_reading(evidence_map: EvidenceMap) -> bytes:
    evidence = {entry.source_id: entry.evidence_id for entry in evidence_map.evidence}
    sections: list[str] = []
    for block in evidence_map.reading_blocks:
        if block.excluded:
            continue
        text = _escape_anchors(block.display_text)
        if block.heading_level:
            text = "#" * block.heading_level + " " + text
        if block.source_id in evidence:
            text = f"[evidence:{evidence[block.source_id]}]\n" + text
        if block.role != "source":
            text = "[生成展示，非证据]\n" + text
        sections.append(text)
        if block.generated_text:
            sections.append(
                "[生成候选，非证据]\n" + _escape_anchors(block.generated_text)
            )
    return ("\n\n".join(sections) + "\n").encode("utf-8", errors="replace")


def _escape_anchors(text: str) -> str:
    return text.replace("[evidence:", "[evidence\\:")


def _repeated_marginal(
    blocks: list[CanonicalBlock], document: CanonicalDocument
) -> set[str]:
    pages = {page.page_no: page for page in document.pages}
    candidates: list[tuple[str, int, str]] = []
    for block in blocks:
        if (
            block.label != "text"
            or len(block.provenance) != 1
            or not block.orig.strip()
        ):
            continue
        p = block.provenance[0]
        page = pages.get(p.page_no)
        if page and (
            p.bbox[3] <= page.height * 0.08 or p.bbox[1] >= page.height * 0.92
        ):
            candidates.append((block.orig.strip(), p.page_no, block.ref))
    repeated = Counter((text, page_no) for text, page_no, _ in candidates)
    occurrences = Counter(text for text, _ in repeated)
    return {ref for text, _, ref in candidates if occurrences[text] >= 2}
