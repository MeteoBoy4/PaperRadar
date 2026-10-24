"""给定正文的只读消费视图;不解释或读取生产制品。"""

import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from paper_radar.reading.errors import ReadContextError, ReadErrorCategory, ReadIssue

EVIDENCE_RULE_VERSION = "read-evidence-v1"


@dataclass(frozen=True, slots=True)
class ExtractionIdentity:
    extraction_fingerprint: str
    reading_sha256: str
    evidence_map_sha256: str


@dataclass(frozen=True, slots=True)
class PageFact:
    identity: ExtractionIdentity
    page_no: int
    width: float
    height: float
    origin: Literal["top_left", "bottom_left"]


@dataclass(frozen=True, slots=True)
class SourceBlock:
    identity: ExtractionIdentity
    source_id: str = field(repr=False)
    orig: str = field(repr=False)
    kind: Literal["text", "table", "formula"] = "text"
    unreliable: bool = False


@dataclass(frozen=True, slots=True)
class Provenance:
    source_id: str = field(repr=False)
    page_no: int
    bbox: tuple[float, float, float, float]
    start: int
    end: int


@dataclass(frozen=True, slots=True, init=False)
class Evidence:
    identity: ExtractionIdentity
    evidence_id: str = field(repr=False)
    provenance: tuple[Provenance, ...]

    def __init__(
        self,
        identity: ExtractionIdentity,
        evidence_id: str,
        provenance: Sequence[Provenance],
    ) -> None:
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "evidence_id", evidence_id)
        if type(provenance) not in (tuple, list):
            _reject("$.provenance", ReadErrorCategory.INVALID_CONTEXT)
        object.__setattr__(self, "provenance", tuple(provenance))


@dataclass(frozen=True, slots=True)
class SourceSlice:
    identity: ExtractionIdentity
    evidence_id: str = field(repr=False)
    provenance: Provenance
    text: str = field(repr=False)
    kind: Literal["text", "table", "formula"]
    unreliable: bool


@dataclass(frozen=True, slots=True, init=False)
class AllowedEvidence:
    """同正文 map 已定位的有序证据范围;不证明 map 生产来源。"""

    identity: ExtractionIdentity
    evidence_ids: tuple[str, ...] = field(repr=False)

    def __init__(
        self, identity: ExtractionIdentity, evidence_ids: Sequence[str]
    ) -> None:
        if not _valid_identity(identity):
            _reject("$.allowed_evidence.identity", ReadErrorCategory.INVALID_IDENTITY)
        if type(evidence_ids) not in (tuple, list):
            _reject(
                "$.allowed_evidence.evidence_ids",
                ReadErrorCategory.INVALID_ALLOWED_EVIDENCE,
            )
        seen: set[str] = set()
        for index, identifier in enumerate(evidence_ids):
            location = f"$.allowed_evidence.evidence_ids[{index}]"
            if not valid_id(identifier):
                _reject(location, ReadErrorCategory.INVALID_EVIDENCE_ID)
            if identifier in seen:
                _reject(location, ReadErrorCategory.DUPLICATE_ID)
            seen.add(identifier)
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "evidence_ids", tuple(evidence_ids))


@dataclass(frozen=True, slots=True, init=False)
class ReadContext:
    identity: ExtractionIdentity
    pages: tuple[PageFact, ...]
    source_blocks: tuple[SourceBlock, ...] = field(repr=False)
    evidence: tuple[Evidence, ...] = field(repr=False)
    expected_language: Literal["zh", "en"] | None = None
    mode: Literal["single", "reduce"] = "single"
    allowed_evidence: AllowedEvidence | None = field(default=None, repr=False)

    def __init__(
        self,
        identity: ExtractionIdentity | None = None,
        pages: Sequence[PageFact] = (),
        source_blocks: Sequence[SourceBlock] = (),
        evidence: Sequence[Evidence] = (),
        expected_language: Literal["zh", "en"] | None = None,
        mode: Literal["single", "reduce"] = "single",
        allowed_evidence: AllowedEvidence | None = None,
    ) -> None:
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "pages", pages)
        object.__setattr__(self, "source_blocks", source_blocks)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "expected_language", expected_language)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "allowed_evidence", allowed_evidence)
        self.__post_init__()

    def __post_init__(self) -> None:
        self._validate_header()
        if not all(
            type(value) in (tuple, list)
            for value in (self.pages, self.source_blocks, self.evidence)
        ):
            _reject("$", ReadErrorCategory.INVALID_CONTEXT)
        self._validate_pages()
        self._validate_sources()
        self._validate_evidence()
        self._validate_allowance()
        object.__setattr__(self, "pages", tuple(self.pages))
        object.__setattr__(self, "source_blocks", tuple(self.source_blocks))
        object.__setattr__(
            self,
            "evidence",
            tuple(
                replace(
                    item,
                    provenance=tuple(
                        replace(p, bbox=(p.bbox[0], p.bbox[1], p.bbox[2], p.bbox[3]))
                        for p in item.provenance
                    ),
                )
                for item in self.evidence
            ),
        )

    def _validate_header(self) -> None:
        if not _valid_identity(self.identity):
            _reject("$.identity", ReadErrorCategory.INVALID_IDENTITY)
        if self.expected_language not in ("zh", "en"):
            _reject("$.expected_language", ReadErrorCategory.INVALID_CONTEXT)
        if self.mode not in ("single", "reduce"):
            _reject("$.mode", ReadErrorCategory.UNSUPPORTED_MODE)
        if self.mode == "single" and self.allowed_evidence is not None:
            _reject("$.allowed_evidence", ReadErrorCategory.UNEXPECTED_ALLOWED_EVIDENCE)
        if self.mode == "reduce" and self.allowed_evidence is None:
            _reject("$.allowed_evidence", ReadErrorCategory.MISSING_ALLOWED_EVIDENCE)
        if (
            self.allowed_evidence is not None
            and type(self.allowed_evidence) is not AllowedEvidence
        ):
            _reject("$.allowed_evidence", ReadErrorCategory.INVALID_ALLOWED_EVIDENCE)

    def _validate_allowance(self) -> None:
        allowance = self.allowed_evidence
        if allowance is None:
            return
        if allowance.identity != self.identity:
            _reject("$.allowed_evidence.identity", ReadErrorCategory.IDENTITY_MISMATCH)
        known = {item.evidence_id for item in self.evidence}
        for index, identifier in enumerate(allowance.evidence_ids):
            if identifier not in known:
                _reject(
                    f"$.allowed_evidence.evidence_ids[{index}]",
                    ReadErrorCategory.UNKNOWN_ALLOWED_EVIDENCE,
                )

    def _validate_pages(self) -> None:
        seen: set[int] = set()
        for index, page in enumerate(self.pages):
            location = f"$.pages[{index}]"
            if type(page) is not PageFact:
                _reject(location, ReadErrorCategory.INVALID_PAGE)
            if page.identity != self.identity:
                _reject(location + ".identity", ReadErrorCategory.IDENTITY_MISMATCH)
            if (
                type(page.page_no) is not int
                or page.page_no <= 0
                or not all(_positive_number(v) for v in (page.width, page.height))
                or page.origin not in ("top_left", "bottom_left")
            ):
                _reject(location, ReadErrorCategory.INVALID_PAGE)
            if page.page_no in seen:
                _reject(location, ReadErrorCategory.DUPLICATE_ID)
            seen.add(page.page_no)

    def _validate_sources(self) -> None:
        seen: set[str] = set()
        for index, source in enumerate(self.source_blocks):
            location = f"$.source_blocks[{index}]"
            if type(source) is not SourceBlock:
                _reject(location, ReadErrorCategory.INVALID_SOURCE)
            if source.identity != self.identity:
                _reject(location + ".identity", ReadErrorCategory.IDENTITY_MISMATCH)
            if (
                not valid_id(source.source_id)
                or type(source.orig) is not str
                or not _valid_unicode(source.orig)
            ):
                _reject(location, ReadErrorCategory.INVALID_SOURCE)
            if source.source_id in seen:
                _reject(location, ReadErrorCategory.DUPLICATE_ID)
            seen.add(source.source_id)
            if source.kind not in ("text", "table", "formula"):
                _reject(location + ".kind", ReadErrorCategory.INVALID_SOURCE)
            if type(source.unreliable) is not bool:
                _reject(location + ".unreliable", ReadErrorCategory.INVALID_SOURCE)

    def _validate_evidence(self) -> None:
        pages = {page.page_no: page for page in self.pages}
        sources = {source.source_id: source for source in self.source_blocks}
        seen: set[str] = set()
        for index, evidence in enumerate(self.evidence):
            location = f"$.evidence[{index}]"
            if type(evidence) is not Evidence:
                _reject(location, ReadErrorCategory.INVALID_CONTEXT)
            if evidence.identity != self.identity:
                _reject(location + ".identity", ReadErrorCategory.IDENTITY_MISMATCH)
            if not valid_id(evidence.evidence_id):
                _reject(location, ReadErrorCategory.INVALID_EVIDENCE_ID)
            if evidence.evidence_id in seen:
                _reject(location, ReadErrorCategory.DUPLICATE_ID)
            seen.add(evidence.evidence_id)
            if (
                type(evidence.provenance) not in (tuple, list)
                or not evidence.provenance
            ):
                _reject(location + ".provenance", ReadErrorCategory.EMPTY_SUPPORT)
            previous: list[Provenance] = []
            for ordinal, provenance in enumerate(evidence.provenance):
                position = f"{location}.provenance[{ordinal}]"
                if type(provenance) is not Provenance:
                    _reject(position, ReadErrorCategory.INVALID_CONTEXT)
                if (
                    type(provenance.source_id) is not str
                    or provenance.source_id not in sources
                ):
                    _reject(position + ".source_id", ReadErrorCategory.UNKNOWN_SOURCE)
                if (
                    type(provenance.page_no) is not int
                    or provenance.page_no not in pages
                ):
                    _reject(position + ".page_no", ReadErrorCategory.UNKNOWN_PAGE)
                page = pages[provenance.page_no]
                box = provenance.bbox
                if (
                    type(box) not in (tuple, list)
                    or len(box) != 4
                    or not all(_finite_number(v) for v in box)
                ):
                    _reject(position + ".bbox", ReadErrorCategory.INVALID_BBOX)
                if not (
                    0 <= box[0] < box[2] <= page.width
                    and 0 <= box[1] < box[3] <= page.height
                ):
                    _reject(position + ".bbox", ReadErrorCategory.INVALID_BBOX)
                normalized = replace(provenance, bbox=(box[0], box[1], box[2], box[3]))
                if normalized in previous:
                    _reject(position, ReadErrorCategory.DUPLICATE_PROVENANCE)
                previous.append(normalized)
                orig = sources[provenance.source_id].orig
                if (
                    type(provenance.start) is not int
                    or type(provenance.end) is not int
                    or not 0 <= provenance.start < provenance.end <= len(orig)
                ):
                    _reject(position + ".charspan", ReadErrorCategory.INVALID_CHARSPAN)
                text = orig[provenance.start : provenance.end]
                if not text or text.isspace():
                    _reject(position + ".charspan", ReadErrorCategory.EMPTY_SUPPORT)

    def replay(self) -> tuple[SourceSlice, ...]:
        sources = {item.source_id: item for item in self.source_blocks}
        return tuple(
            SourceSlice(
                self.identity,
                item.evidence_id,
                p,
                sources[p.source_id].orig[p.start : p.end],
                sources[p.source_id].kind,
                sources[p.source_id].unreliable,
            )
            for item in self.evidence
            for p in item.provenance
        )


def _reject(location: str, category: ReadErrorCategory) -> None:
    raise ReadContextError((ReadIssue(location, category),))


def _valid_unicode(value: str) -> bool:
    valid = True
    try:
        value.encode("utf-8")
    except UnicodeError:
        valid = False
    return valid


def valid_id(value: object) -> bool:
    return (
        type(value) is str
        and bool(value)
        and value == value.strip()
        and _valid_unicode(value)
        and not any(unicodedata.category(c).startswith("C") for c in value)
    )


def _valid_identity(value: object) -> bool:
    return type(value) is ExtractionIdentity and all(
        valid_id(member)
        for member in (
            value.extraction_fingerprint,
            value.reading_sha256,
            value.evidence_map_sha256,
        )
    )


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float) or not isinstance(value, int | float):
        return False
    finite = False
    try:
        finite = math.isfinite(value)
    except OverflowError:
        return False
    return finite


def _positive_number(value: object) -> bool:
    return isinstance(value, int | float) and _finite_number(value) and value > 0
