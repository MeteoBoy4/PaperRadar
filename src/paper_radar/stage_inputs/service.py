"""阶段输入身份。仅消费明确快照与事实。不访问持久化或执行环境。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from paper_radar.config import (
    RuntimeConfigSnapshot,
    StageName,
    StageReadiness,
    project_config,
)
from paper_radar.screening import (
    ExcerptKind,
    ReuseAssessmentContext,
    ValuePredictionContext,
)


class BuildReason(StrEnum):
    UNSUPPORTED_STAGE = "unsupported_stage"
    INVALID_SNAPSHOT = "invalid_snapshot"
    NOT_READY = "not_ready"
    INVALID_FACTS = "invalid_facts"
    INVALID_TEXT = "invalid_text"
    INVALID_ENCODING = "invalid_encoding"
    INVALID_HASH = "invalid_hash"
    INVALID_CONTEXT = "invalid_context"
    PROJECTION_FORMAT_UNVERIFIABLE = "projection_format_unverifiable"
    PROJECTION_MISMATCH = "projection_mismatch"
    DUPLICATE_EXCERPT_ID = "duplicate_excerpt_id"
    INCONSISTENT_EXTRACTION_SOURCE = "inconsistent_extraction_source"


class ReplayReason(StrEnum):
    INVALID_PAYLOAD = "invalid_payload"
    UNSUPPORTED_STAGE = "unsupported_stage"
    UNSUPPORTED_FORMAT = "unsupported_format"
    INVALID_FINGERPRINT = "invalid_fingerprint"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    NON_CANONICAL = "non_canonical"
    INVALID_SNAPSHOT = "invalid_snapshot"
    PROJECTION_FORMAT_UNVERIFIABLE = "projection_format_unverifiable"
    PROJECTION_MISMATCH = "projection_mismatch"


class ComparisonReason(StrEnum):
    DIFFERENT_STAGE = "different_stage"
    INCOMPATIBLE_FORMAT = "incompatible_format"
    INVALID_INPUT = "invalid_input"


class InputField(StrEnum):
    STAGE = "stage"
    SNAPSHOT = "snapshot"
    FACTS = "facts"
    TITLE = "facts.title"
    ABSTRACT = "facts.abstract"
    ABSTRACT_TRUNCATED = "facts.abstract_truncated"
    PAYLOAD = "payload"
    KIND = "kind"
    FORMAT_VERSION = "format_version"
    CONFIG_PROJECTION = "config_projection"
    PROJECTION_ID = "config_projection.projection_id"
    FINGERPRINT = "expected_fingerprint"
    INPUTS = "inputs"
    CONTEXT = "context"
    TITLE_LANGUAGE = "original_title_is_zh"
    PDF_SHA256 = "facts.pdf_sha256"
    EXCERPTS = "facts.excerpts"
    EXCERPT_ID = "facts.excerpts.excerpt_id"
    EXCERPT_KIND = "facts.excerpts.kind"
    EXCERPT_TEXT = "facts.excerpts.text"
    EXCERPT_SOURCE = "facts.excerpts.source"
    SOURCE_HASH = "facts.excerpts.source.content_sha256"
    SOURCE_LOCATOR = "facts.excerpts.source.locator"
    EXTRACTION_INPUT = "facts.excerpts.source.extraction_input"
    EXTRACTION_FINGERPRINT = "facts.excerpts.source.extraction_fingerprint"
    READING_HASH = "facts.excerpts.source.reading_sha256"
    EVIDENCE_MAP_HASH = "facts.excerpts.source.evidence_map_sha256"


class StageInputError(ValueError):
    """错误仅保存封闭原因、位置及已有配置就绪事实。不保存提交内容。"""

    def __init__(
        self,
        reason: BuildReason | ReplayReason,
        field: InputField,
        *,
        readiness: StageReadiness | None = None,
    ) -> None:
        self.reason = reason
        self.field = field
        self.readiness = readiness
        super().__init__(f"{reason.value}: {field.value}")


_MISSING = object()


def _valid_text(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _utf8_valid(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _valid_hash(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, slots=True, init=False)
class ScreeningFacts:
    """上游已选定的精确题名、摘要与截断事实。不规范化论文文本。"""

    title: str = field(repr=False)
    abstract: str = field(repr=False)
    abstract_truncated: bool

    def __init__(
        self,
        *,
        title: Any = _MISSING,
        abstract: Any = _MISSING,
        abstract_truncated: Any = _MISSING,
        **extra: Any,
    ) -> None:
        if extra:
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.FACTS)
        for value, location in (
            (title, InputField.TITLE),
            (abstract, InputField.ABSTRACT),
        ):
            if not _valid_text(value):
                raise StageInputError(BuildReason.INVALID_TEXT, location)
            if not _utf8_valid(value):
                raise StageInputError(BuildReason.INVALID_ENCODING, location)
        if type(abstract_truncated) is not bool:
            raise StageInputError(
                BuildReason.INVALID_FACTS, InputField.ABSTRACT_TRUNCATED
            )
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "abstract", abstract)
        object.__setattr__(self, "abstract_truncated", abstract_truncated)


def _reuse_context(kinds: dict[str, Any]) -> ReuseAssessmentContext | None:
    try:
        return ReuseAssessmentContext(excerpt_kinds=kinds)
    except ValidationError:
        return None


def _frozen_locator(locator: Any) -> tuple[str, ...]:
    if type(locator) not in (tuple, list) or not locator:
        raise StageInputError(BuildReason.INVALID_FACTS, InputField.SOURCE_LOCATOR)
    for part in locator:
        if not _valid_text(part):
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.SOURCE_LOCATOR)
        if not _utf8_valid(part):
            raise StageInputError(
                BuildReason.INVALID_ENCODING, InputField.SOURCE_LOCATOR
            )
    return tuple(locator)


@dataclass(frozen=True, slots=True, init=False)
class SourceSnapshotRef:
    """结构化快照 payload 成员内容身份与生产者定义的定位。"""

    content_sha256: str
    locator: tuple[str, ...] = field(repr=False)

    def __init__(
        self, *, content_sha256: Any = _MISSING, locator: Any = _MISSING, **extra: Any
    ) -> None:
        if extra:
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.EXCERPT_SOURCE)
        if not _valid_hash(content_sha256):
            raise StageInputError(BuildReason.INVALID_HASH, InputField.SOURCE_HASH)
        frozen_locator = _frozen_locator(locator)
        object.__setattr__(self, "content_sha256", content_sha256)
        object.__setattr__(self, "locator", frozen_locator)


@dataclass(frozen=True, slots=True, init=False)
class ExtractionRef:
    """明确正文配方及实际消费的两份内容身份。不查询当前制品。"""

    extraction_fingerprint: str
    reading_sha256: str
    evidence_map_sha256: str
    locator: tuple[str, ...] = field(repr=False)

    def __init__(
        self,
        *,
        extraction_input: Any = _MISSING,
        reading_sha256: Any = _MISSING,
        evidence_map_sha256: Any = _MISSING,
        locator: Any = _MISSING,
        **extra: Any,
    ) -> None:
        if extra:
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.EXCERPT_SOURCE)
        if (
            type(extraction_input) is not StageInput
            or extraction_input.stage is not StageName.EXTRACTION
        ):
            raise StageInputError(
                BuildReason.INVALID_FACTS, InputField.EXTRACTION_INPUT
            )
        _set_extraction_ref(
            self,
            extraction_input.fingerprint,
            reading_sha256,
            evidence_map_sha256,
            locator,
        )

    @property
    def identity(self) -> tuple[str, str, str]:
        """正文消费身份不包含片段定位; 同次调用可选同一正文的多个片段。"""
        return (
            self.extraction_fingerprint,
            self.reading_sha256,
            self.evidence_map_sha256,
        )


def _set_extraction_ref(
    result: ExtractionRef,
    extraction_fingerprint: Any,
    reading_sha256: Any,
    evidence_map_sha256: Any,
    locator: Any,
) -> None:
    # 回放只验证哈希编码。仅公共构造检查 extraction 输入对象的身份域。
    for value, location in (
        (extraction_fingerprint, InputField.EXTRACTION_FINGERPRINT),
        (reading_sha256, InputField.READING_HASH),
        (evidence_map_sha256, InputField.EVIDENCE_MAP_HASH),
    ):
        if not _valid_hash(value):
            raise StageInputError(BuildReason.INVALID_HASH, location)
    frozen_locator = _frozen_locator(locator)
    for name, value in (
        ("extraction_fingerprint", extraction_fingerprint),
        ("reading_sha256", reading_sha256),
        ("evidence_map_sha256", evidence_map_sha256),
        ("locator", frozen_locator),
    ):
        object.__setattr__(result, name, value)


@dataclass(frozen=True, slots=True, init=False)
class SelectedExcerpt:
    """一次模型输入中显式选定的摘录。不实现选段或来源回查。"""

    excerpt_id: str = field(repr=False)
    kind: ExcerptKind
    text: str = field(repr=False)
    source: SourceSnapshotRef | ExtractionRef = field(repr=False)

    def __init__(
        self,
        *,
        excerpt_id: Any = _MISSING,
        kind: Any = _MISSING,
        text: Any = _MISSING,
        source: Any = _MISSING,
        **extra: Any,
    ) -> None:
        if extra:
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.EXCERPTS)
        # 先限制为可安全用作映射键的文本。ID/种类语义仍由权威上下文验证。
        if type(excerpt_id) is not str:
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.EXCERPT_ID)
        if not _utf8_valid(excerpt_id):
            raise StageInputError(BuildReason.INVALID_ENCODING, InputField.EXCERPT_ID)
        context = _reuse_context({excerpt_id: kind})
        if context is None:
            # 用已知合法种类交由同一权威上下文区分 ID 与种类错误。
            # 不复制其规则, 也不保留带实际 ID/值的 Pydantic 异常。
            location = (
                InputField.EXCERPT_ID
                if _reuse_context({excerpt_id: ExcerptKind.AVAILABILITY}) is None
                else InputField.EXCERPT_KIND
            )
            raise StageInputError(BuildReason.INVALID_FACTS, location)
        if not _valid_text(text):
            raise StageInputError(BuildReason.INVALID_TEXT, InputField.EXCERPT_TEXT)
        if not _utf8_valid(text):
            raise StageInputError(BuildReason.INVALID_ENCODING, InputField.EXCERPT_TEXT)
        if type(source) not in (SourceSnapshotRef, ExtractionRef):
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.EXCERPT_SOURCE)
        object.__setattr__(self, "excerpt_id", excerpt_id)
        object.__setattr__(self, "kind", context.excerpt_kinds[excerpt_id])
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "source", source)


@dataclass(frozen=True, slots=True, init=False)
class ReuseFacts:
    """非空、有序且 ID 唯一的冻结摘录。"""

    excerpts: tuple[SelectedExcerpt, ...] = field(repr=False)

    def __init__(self, *, excerpts: Any = _MISSING, **extra: Any) -> None:
        if extra or type(excerpts) not in (tuple, list) or not excerpts:
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.EXCERPTS)
        seen: set[str] = set()
        body_identity: tuple[str, str, str] | None = None
        for excerpt in excerpts:
            if type(excerpt) is not SelectedExcerpt:
                raise StageInputError(BuildReason.INVALID_FACTS, InputField.EXCERPTS)
            if excerpt.excerpt_id in seen:
                raise StageInputError(
                    BuildReason.DUPLICATE_EXCERPT_ID, InputField.EXCERPTS
                )
            seen.add(excerpt.excerpt_id)
            if isinstance(excerpt.source, ExtractionRef):
                identity = excerpt.source.identity
                if body_identity is not None and identity != body_identity:
                    raise StageInputError(
                        BuildReason.INCONSISTENT_EXTRACTION_SOURCE,
                        InputField.EXCERPT_SOURCE,
                    )
                body_identity = identity
        object.__setattr__(self, "excerpts", tuple(excerpts))


@dataclass(frozen=True, slots=True, init=False)
class ExtractionFacts:
    """上游计算的原始 PDF 完整字节身份。不读取文件或解析环境。"""

    pdf_sha256: str = field(repr=False)

    def __init__(self, *, pdf_sha256: Any = _MISSING, **extra: Any) -> None:
        if extra:
            raise StageInputError(BuildReason.INVALID_FACTS, InputField.FACTS)
        if not _valid_hash(pdf_sha256):
            raise StageInputError(BuildReason.INVALID_HASH, InputField.PDF_SHA256)
        object.__setattr__(self, "pdf_sha256", pdf_sha256)


@dataclass(frozen=True, slots=True, init=False)
class StageInput:
    """仅 build/replay 返回的对象是已验证输入。载荷是敏感业务数据。"""

    stage: StageName
    format_version: int
    projection_format_version: int
    projection_id: str
    facts: ScreeningFacts | ExtractionFacts | ReuseFacts = field(repr=False)
    payload_bytes: bytes = field(repr=False)

    def __init__(self, **unvalidated: Any) -> None:
        raise StageInputError(BuildReason.INVALID_FACTS, InputField.INPUTS)

    def value_prediction_context(
        self,
        snapshot: RuntimeConfigSnapshot,
        *,
        original_title_is_zh: Any = _MISSING,
        **extra: object,
    ) -> ValuePredictionContext:
        """从匹配本次 value 输入的明确快照派生权威上下文。"""
        if self.stage is not StageName.VALUE:
            raise StageInputError(BuildReason.INVALID_CONTEXT, InputField.STAGE)
        if extra:
            raise StageInputError(BuildReason.INVALID_CONTEXT, InputField.CONTEXT)
        if type(original_title_is_zh) is not bool:
            raise StageInputError(
                BuildReason.INVALID_CONTEXT, InputField.TITLE_LANGUAGE
            )
        _verify_projection(self, snapshot, BuildReason)
        return ValuePredictionContext(
            enabled_topic_ids=frozenset(topic.id for topic in snapshot.enabled_topics),
            original_title_is_zh=original_title_is_zh,
        )

    def reuse_assessment_context(self, **extra: object) -> ReuseAssessmentContext:
        """唯一使用本输入冻结摘录派生权威 ID/种类映射。"""
        if self.stage is not StageName.REUSE or not isinstance(self.facts, ReuseFacts):
            raise StageInputError(BuildReason.INVALID_CONTEXT, InputField.STAGE)
        if extra:
            raise StageInputError(BuildReason.INVALID_CONTEXT, InputField.CONTEXT)
        context = _reuse_context(
            {item.excerpt_id: item.kind for item in self.facts.excerpts}
        )
        if context is None:
            raise StageInputError(BuildReason.INVALID_CONTEXT, InputField.CONTEXT)
        return context

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.payload_bytes).hexdigest()


class ChangeComponent(StrEnum):
    CONFIG_PROJECTION = "config_projection"
    TITLE = "title"
    ABSTRACT = "abstract"
    ABSTRACT_TRUNCATED = "abstract_truncated"
    PDF = "pdf"
    EXCERPTS = "excerpts"
    EXCERPT_SOURCES = "excerpt_sources"


class ComparisonStatus(StrEnum):
    SAME = "same"
    CHANGED = "changed"
    INCOMPARABLE = "incomparable"


@dataclass(frozen=True, slots=True)
class StageInputComparison:
    status: ComparisonStatus
    changed_components: tuple[ChangeComponent, ...] = ()
    reason: ComparisonReason | None = None


# 领取集合有意独立于 StageName。后续阶段随其业务票加入。
STAGE_INPUT_FORMAT_VERSIONS: Mapping[StageName, int] = MappingProxyType(
    {
        StageName.BOUNDARY: 1,
        StageName.VALUE: 1,
        StageName.REUSE: 1,
        StageName.EXTRACTION: 1,
    }
)

# 描述回放已实现的历史投影格式。独立于 config 当前写出格式; 升级写出器不自动
# 授权未知历史格式。扩展此集合前必须实现相应重建/核对策略并登记验收。
_SUPPORTED_REPLAY_PROJECTION_FORMATS = frozenset({1})


def _canonical(value: object) -> bytes:
    """本身份域自己的编码器。字段验证保证无浮点与非法 Unicode。"""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _source_payload(source: SourceSnapshotRef | ExtractionRef) -> dict[str, Any]:
    if isinstance(source, ExtractionRef):
        return {
            "kind": "extraction",
            "extraction_fingerprint": source.extraction_fingerprint,
            "reading_sha256": source.reading_sha256,
            "evidence_map_sha256": source.evidence_map_sha256,
            "locator": list(source.locator),
        }
    return {
        "kind": "source_snapshot",
        "content_sha256": source.content_sha256,
        "locator": list(source.locator),
    }


def _facts_payload(
    facts: ScreeningFacts | ExtractionFacts | ReuseFacts,
) -> dict[str, Any]:
    if isinstance(facts, ExtractionFacts):
        return {"pdf_sha256": facts.pdf_sha256}
    if isinstance(facts, ReuseFacts):
        return {
            "excerpts": [
                {
                    "excerpt_id": item.excerpt_id,
                    "kind": item.kind.value,
                    "text": item.text,
                    "source": _source_payload(item.source),
                }
                for item in facts.excerpts
            ]
        }
    return {
        "title": facts.title,
        "abstract": facts.abstract,
        "abstract_truncated": facts.abstract_truncated,
    }


def _assemble(
    stage: StageName,
    format_version: int,
    projection_format: int,
    projection_id: str,
    facts: ScreeningFacts | ExtractionFacts | ReuseFacts,
) -> StageInput:
    payload = _canonical(
        {
            "kind": "stage_input",
            "stage": stage.value,
            "format_version": format_version,
            "config_projection": {
                "format_version": projection_format,
                "projection_id": projection_id,
            },
            "facts": _facts_payload(facts),
        }
    )
    result = object.__new__(StageInput)
    for name, value in (
        ("stage", stage),
        ("format_version", format_version),
        ("projection_format_version", projection_format),
        ("projection_id", projection_id),
        ("facts", facts),
        ("payload_bytes", payload),
    ):
        object.__setattr__(result, name, value)
    return result


def build_stage_input(
    snapshot: RuntimeConfigSnapshot,
    stage: StageName,
    facts: ScreeningFacts | ExtractionFacts | ReuseFacts,
) -> StageInput:
    """只从已验证快照构造。配置完整性不代表 RPC 执行就绪。"""
    if type(stage) is not StageName or stage not in STAGE_INPUT_FORMAT_VERSIONS:
        raise StageInputError(BuildReason.UNSUPPORTED_STAGE, InputField.STAGE)
    if type(snapshot) is not RuntimeConfigSnapshot:
        raise StageInputError(BuildReason.INVALID_SNAPSHOT, InputField.SNAPSHOT)
    readiness = snapshot.stages[stage]
    if readiness.status != "ready":
        raise StageInputError(
            BuildReason.NOT_READY, InputField.SNAPSHOT, readiness=readiness
        )
    expected_type = {
        StageName.BOUNDARY: ScreeningFacts,
        StageName.VALUE: ScreeningFacts,
        StageName.REUSE: ReuseFacts,
        StageName.EXTRACTION: ExtractionFacts,
    }[stage]
    if type(facts) is not expected_type:
        raise StageInputError(BuildReason.INVALID_FACTS, InputField.FACTS)
    projection = project_config(snapshot).projections[stage]
    if not _valid_hash(projection.projection_id):
        raise StageInputError(BuildReason.INVALID_HASH, InputField.PROJECTION_ID)
    return _assemble(
        stage,
        STAGE_INPUT_FORMAT_VERSIONS[stage],
        projection.format_version,
        projection.projection_id,
        facts,
    )


def _parse(payload: bytes) -> Any:
    # 返回后再抛受控错误。避免在异常链中保留 JSON doc 或 Unicode 原文。
    try:
        return json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None


def _keys(value: object, expected: set[str]) -> bool:
    return type(value) is dict and value.keys() == expected


def _replay_source(value: Any) -> SourceSnapshotRef | ExtractionRef | None:
    try:
        if (
            _keys(value, {"kind", "content_sha256", "locator"})
            and value["kind"] == "source_snapshot"
        ):
            return SourceSnapshotRef(
                content_sha256=value["content_sha256"], locator=value["locator"]
            )
        if (
            _keys(
                value,
                {
                    "kind",
                    "extraction_fingerprint",
                    "reading_sha256",
                    "evidence_map_sha256",
                    "locator",
                },
            )
            and value["kind"] == "extraction"
        ):
            result = object.__new__(ExtractionRef)
            _set_extraction_ref(
                result,
                value["extraction_fingerprint"],
                value["reading_sha256"],
                value["evidence_map_sha256"],
                value["locator"],
            )
            return result
    except StageInputError:
        return None
    return None


def _replay_facts(
    stage: StageName, value: Any
) -> ScreeningFacts | ExtractionFacts | ReuseFacts | None:
    if stage is StageName.EXTRACTION:
        if not _keys(value, {"pdf_sha256"}):
            return None
        try:
            return ExtractionFacts(**value)
        except StageInputError:
            return None
    if stage is StageName.REUSE:
        if not _keys(value, {"excerpts"}) or type(value["excerpts"]) is not list:
            return None
        excerpts: list[SelectedExcerpt] = []
        for item in value["excerpts"]:
            if not _keys(item, {"excerpt_id", "kind", "text", "source"}):
                return None
            reference = _replay_source(item["source"])
            if reference is None:
                return None
            try:
                excerpts.append(
                    SelectedExcerpt(
                        excerpt_id=item["excerpt_id"],
                        kind=item["kind"],
                        text=item["text"],
                        source=reference,
                    )
                )
            except StageInputError:
                return None
        try:
            return ReuseFacts(excerpts=excerpts)
        except StageInputError:
            return None
    if not _keys(value, {"title", "abstract", "abstract_truncated"}):
        return None
    try:
        return ScreeningFacts(**value)
    except StageInputError:
        return None


def replay_stage_input(
    payload_bytes: bytes,
    expected_fingerprint: str,
    *,
    snapshot: RuntimeConfigSnapshot | None = None,
) -> StageInput:
    """严格回放。可选择核对明确历史快照。不推断当前配置或来源存在。"""
    if type(payload_bytes) is not bytes:
        raise StageInputError(ReplayReason.INVALID_PAYLOAD, InputField.PAYLOAD)
    if not _valid_hash(expected_fingerprint):
        raise StageInputError(ReplayReason.INVALID_FINGERPRINT, InputField.FINGERPRINT)
    value = _parse(payload_bytes)
    if not _keys(
        value, {"kind", "stage", "format_version", "config_projection", "facts"}
    ):
        raise StageInputError(ReplayReason.INVALID_PAYLOAD, InputField.PAYLOAD)
    if value["kind"] != "stage_input":
        raise StageInputError(ReplayReason.INVALID_PAYLOAD, InputField.KIND)
    stage = next(
        (s for s in STAGE_INPUT_FORMAT_VERSIONS if s.value == value["stage"]), None
    )
    if stage is None:
        raise StageInputError(ReplayReason.UNSUPPORTED_STAGE, InputField.STAGE)
    version = value["format_version"]
    if type(version) is not int or version != STAGE_INPUT_FORMAT_VERSIONS[stage]:
        raise StageInputError(
            ReplayReason.UNSUPPORTED_FORMAT, InputField.FORMAT_VERSION
        )
    projection = value["config_projection"]
    if not _keys(projection, {"format_version", "projection_id"}):
        raise StageInputError(
            ReplayReason.INVALID_PAYLOAD, InputField.CONFIG_PROJECTION
        )
    projection_version = projection["format_version"]
    if (
        type(projection_version) is not int
        or projection_version not in _SUPPORTED_REPLAY_PROJECTION_FORMATS
    ):
        raise StageInputError(
            ReplayReason.PROJECTION_FORMAT_UNVERIFIABLE, InputField.CONFIG_PROJECTION
        )
    if not _valid_hash(projection["projection_id"]):
        raise StageInputError(ReplayReason.INVALID_PAYLOAD, InputField.PROJECTION_ID)
    facts = _replay_facts(stage, value["facts"])
    if facts is None:
        raise StageInputError(ReplayReason.INVALID_PAYLOAD, InputField.FACTS)
    result = _assemble(
        stage, version, projection_version, projection["projection_id"], facts
    )
    if result.payload_bytes != payload_bytes:
        raise StageInputError(ReplayReason.NON_CANONICAL, InputField.PAYLOAD)
    if result.fingerprint != expected_fingerprint:
        raise StageInputError(ReplayReason.FINGERPRINT_MISMATCH, InputField.FINGERPRINT)
    if snapshot is not None:
        _verify_projection(result, snapshot, ReplayReason)
    return result


def _verify_projection(
    result: StageInput,
    snapshot: RuntimeConfigSnapshot,
    reasons: type[BuildReason] | type[ReplayReason],
) -> None:
    if type(snapshot) is not RuntimeConfigSnapshot:
        raise StageInputError(reasons.INVALID_SNAPSHOT, InputField.SNAPSHOT)
    known = project_config(snapshot).projections[result.stage]
    if known.format_version != result.projection_format_version:
        raise StageInputError(
            reasons.PROJECTION_FORMAT_UNVERIFIABLE, InputField.CONFIG_PROJECTION
        )
    if known.projection_id != result.projection_id:
        raise StageInputError(reasons.PROJECTION_MISMATCH, InputField.CONFIG_PROJECTION)


def compare_stage_inputs(before: StageInput, after: StageInput) -> StageInputComparison:
    """只解释组件变化。不推导资格、缓存、预算或校准等级。"""
    if type(before) is not StageInput or type(after) is not StageInput:
        return StageInputComparison(
            ComparisonStatus.INCOMPARABLE, reason=ComparisonReason.INVALID_INPUT
        )
    if before.stage != after.stage:
        return StageInputComparison(
            ComparisonStatus.INCOMPARABLE, reason=ComparisonReason.DIFFERENT_STAGE
        )
    if (
        before.format_version != after.format_version
        or before.projection_format_version != after.projection_format_version
    ):
        return StageInputComparison(
            ComparisonStatus.INCOMPARABLE, reason=ComparisonReason.INCOMPATIBLE_FORMAT
        )
    components: tuple[tuple[ChangeComponent, object, object], ...] = (
        (ChangeComponent.CONFIG_PROJECTION, before.projection_id, after.projection_id),
    )
    if before.stage is StageName.REUSE:
        assert isinstance(before.facts, ReuseFacts) and isinstance(
            after.facts, ReuseFacts
        )
        components += (
            (
                ChangeComponent.EXCERPTS,
                tuple(
                    (item.excerpt_id, item.kind, item.text)
                    for item in before.facts.excerpts
                ),
                tuple(
                    (item.excerpt_id, item.kind, item.text)
                    for item in after.facts.excerpts
                ),
            ),
            (
                ChangeComponent.EXCERPT_SOURCES,
                tuple(_source_payload(item.source) for item in before.facts.excerpts),
                tuple(_source_payload(item.source) for item in after.facts.excerpts),
            ),
        )
    elif isinstance(before.facts, ExtractionFacts) and isinstance(
        after.facts, ExtractionFacts
    ):
        components += (
            (ChangeComponent.PDF, before.facts.pdf_sha256, after.facts.pdf_sha256),
        )
    else:
        assert isinstance(before.facts, ScreeningFacts) and isinstance(
            after.facts, ScreeningFacts
        )
        components += (
            (ChangeComponent.TITLE, before.facts.title, after.facts.title),
            (ChangeComponent.ABSTRACT, before.facts.abstract, after.facts.abstract),
            (
                ChangeComponent.ABSTRACT_TRUNCATED,
                before.facts.abstract_truncated,
                after.facts.abstract_truncated,
            ),
        )
    changed = tuple(name for name, old, new in components if old != new)
    return StageInputComparison(
        ComparisonStatus.CHANGED if changed else ComparisonStatus.SAME, changed
    )
