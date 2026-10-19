"""阶段输入身份。仅消费明确快照与事实。不访问持久化或执行环境。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from paper_radar.config import (
    RuntimeConfigSnapshot,
    StageName,
    StageReadiness,
    project_config,
)
from paper_radar.screening import ValuePredictionContext


class BuildReason(StrEnum):
    UNSUPPORTED_STAGE = "unsupported_stage"
    INVALID_SNAPSHOT = "invalid_snapshot"
    NOT_READY = "not_ready"
    INVALID_FACTS = "invalid_facts"
    INVALID_TEXT = "invalid_text"
    INVALID_ENCODING = "invalid_encoding"
    INVALID_HASH = "invalid_hash"
    INVALID_CONTEXT = "invalid_context"


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
    PDF_SHA256 = "facts.pdf_sha256"
    PAYLOAD = "payload"
    KIND = "kind"
    FORMAT_VERSION = "format_version"
    CONFIG_PROJECTION = "config_projection"
    PROJECTION_ID = "config_projection.projection_id"
    FINGERPRINT = "expected_fingerprint"
    INPUTS = "inputs"
    CONTEXT = "context"
    TITLE_LANGUAGE = "original_title_is_zh"


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
    facts: ScreeningFacts | ExtractionFacts = field(repr=False)
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
        _verify_projection(self, snapshot)
        return ValuePredictionContext(
            enabled_topic_ids=frozenset(topic.id for topic in snapshot.enabled_topics),
            original_title_is_zh=original_title_is_zh,
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.payload_bytes).hexdigest()


class ChangeComponent(StrEnum):
    CONFIG_PROJECTION = "config_projection"
    TITLE = "title"
    ABSTRACT = "abstract"
    ABSTRACT_TRUNCATED = "abstract_truncated"
    PDF = "pdf"


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
_FORMAT_VERSIONS = {
    StageName.BOUNDARY: 1,
    StageName.VALUE: 1,
    StageName.EXTRACTION: 1,
}


def _canonical(value: object) -> bytes:
    """本身份域自己的编码器。字段验证保证无浮点与非法 Unicode。"""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _facts_payload(facts: ScreeningFacts | ExtractionFacts) -> dict[str, str | bool]:
    if isinstance(facts, ExtractionFacts):
        return {"pdf_sha256": facts.pdf_sha256}
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
    facts: ScreeningFacts | ExtractionFacts,
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
    facts: ScreeningFacts | ExtractionFacts,
) -> StageInput:
    """只从已验证快照构造。配置完整性不代表 RPC 执行就绪。"""
    if type(stage) is not StageName or stage not in _FORMAT_VERSIONS:
        raise StageInputError(BuildReason.UNSUPPORTED_STAGE, InputField.STAGE)
    if type(snapshot) is not RuntimeConfigSnapshot:
        raise StageInputError(BuildReason.INVALID_SNAPSHOT, InputField.SNAPSHOT)
    readiness = snapshot.stages[stage]
    if readiness.status != "ready":
        raise StageInputError(
            BuildReason.NOT_READY, InputField.SNAPSHOT, readiness=readiness
        )
    expected_facts = (
        ExtractionFacts if stage is StageName.EXTRACTION else ScreeningFacts
    )
    if type(facts) is not expected_facts:
        raise StageInputError(BuildReason.INVALID_FACTS, InputField.FACTS)
    projection = project_config(snapshot).projections[stage]
    if not _valid_hash(projection.projection_id):
        raise StageInputError(BuildReason.INVALID_HASH, InputField.PROJECTION_ID)
    return _assemble(
        stage,
        _FORMAT_VERSIONS[stage],
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


def _replay_facts(
    stage: StageName, value: Any
) -> ScreeningFacts | ExtractionFacts | None:
    keys = (
        {"pdf_sha256"}
        if stage is StageName.EXTRACTION
        else {"title", "abstract", "abstract_truncated"}
    )
    if not _keys(value, keys):
        return None
    try:
        if stage is StageName.EXTRACTION:
            return ExtractionFacts(**value)
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
    stage = next((s for s in _FORMAT_VERSIONS if s.value == value["stage"]), None)
    if stage is None:
        raise StageInputError(ReplayReason.UNSUPPORTED_STAGE, InputField.STAGE)
    version = value["format_version"]
    if type(version) is not int or version != _FORMAT_VERSIONS[stage]:
        raise StageInputError(
            ReplayReason.UNSUPPORTED_FORMAT, InputField.FORMAT_VERSION
        )
    projection = value["config_projection"]
    if not _keys(projection, {"format_version", "projection_id"}):
        raise StageInputError(
            ReplayReason.INVALID_PAYLOAD, InputField.CONFIG_PROJECTION
        )
    projection_version = projection["format_version"]
    if type(projection_version) is not int or projection_version != 1:
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
        _verify_projection(result, snapshot)
    return result


def _verify_projection(result: StageInput, snapshot: RuntimeConfigSnapshot) -> None:
    if type(snapshot) is not RuntimeConfigSnapshot:
        raise StageInputError(ReplayReason.INVALID_SNAPSHOT, InputField.SNAPSHOT)
    known = project_config(snapshot).projections[result.stage]
    if known.format_version != result.projection_format_version:
        raise StageInputError(
            ReplayReason.PROJECTION_FORMAT_UNVERIFIABLE, InputField.CONFIG_PROJECTION
        )
    if known.projection_id != result.projection_id:
        raise StageInputError(
            ReplayReason.PROJECTION_MISMATCH, InputField.CONFIG_PROJECTION
        )


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
    if isinstance(before.facts, ExtractionFacts) and isinstance(
        after.facts, ExtractionFacts
    ):
        components += (
            (ChangeComponent.PDF, before.facts.pdf_sha256, after.facts.pdf_sha256),
        )
    elif isinstance(before.facts, ScreeningFacts) and isinstance(
        after.facts, ScreeningFacts
    ):
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
