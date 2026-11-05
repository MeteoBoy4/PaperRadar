"""正文规范制品的可回放数据;哈希身份只在 manifest 中保存。"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from paper_radar.eligibility import QualityFailure
from paper_radar.fulltext.canonical import (
    CanonicalModel,
    CanonicalPage,
    CanonicalProvenance,
)
from paper_radar.fulltext.execution_audit import ExtractionExecutionAudit
from paper_radar.reading.context import ExtractionIdentity, ReadContext, SourceSlice


class Source(CanonicalModel):
    source_id: str
    orig: str
    text: str
    kind: Literal["text", "table", "formula"]
    unreliable: bool
    provenance: tuple[CanonicalProvenance, ...]


class ReadingBlock(CanonicalModel):
    block_id: str
    source_id: str | None
    parent_id: str | None
    label: str
    content_layer: Literal["body", "furniture", "background"]
    role: Literal["source", "generated", "placeholder"]
    heading_level: int | None
    excluded: Literal["cover", "furniture", "background"] | None
    display_text: str
    generated_text: str | None
    formula_mode: Literal["display", "inline", "unknown"]
    provenance: tuple[CanonicalProvenance, ...]


class EvidenceEntry(CanonicalModel):
    evidence_id: str
    source_id: str


class EvidenceMap(CanonicalModel):
    format_version: Literal[1] = 1
    normalization_version: Literal["v1"] = "v1"
    has_text_layer: bool
    pages: tuple[CanonicalPage, ...]
    source_blocks: tuple[Source, ...]
    reading_blocks: tuple[ReadingBlock, ...]
    evidence: tuple[EvidenceEntry, ...]


class ExtractionManifest(CanonicalModel):
    format_version: Literal[1] = 1
    normalization_version: Literal["v1"] = "v1"
    extraction_fingerprint: str
    reading_sha256: str
    evidence_map_sha256: str
    document_sha256: str
    backend_config_hash: str
    model_artifacts_hash: str
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    peak_memory_bytes: int = Field(ge=0)
    warnings: tuple[str, ...] = ()
    execution_audit: ExtractionExecutionAudit | None = None

    @model_validator(mode="after")
    def coherent_audit(self) -> "ExtractionManifest":
        audit = self.execution_audit
        if audit is not None and (
            audit.backend_config_hash != self.backend_config_hash
            or audit.model_artifacts_hash != self.model_artifacts_hash
            or audit.normalization_version != self.normalization_version
        ):
            raise ValueError("执行审计与manifest身份不符")
        return self


@dataclass(frozen=True)
class QualityIssue:
    failure: QualityFailure
    location: str


@dataclass(frozen=True)
class AutomaticQuality:
    issues: tuple[QualityIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class FormulaCoverage:
    mode: Literal["display", "inline", "unknown"]
    total: int
    with_parent_source: int
    placeholder_only: int


@dataclass(frozen=True)
class ExtractionStatistics:
    formula: tuple[FormulaCoverage, ...]
    member_bytes: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class PublishedExtraction:
    artifact_id: str
    identity: ExtractionIdentity
    quality: AutomaticQuality
    statistics: ExtractionStatistics


@dataclass(frozen=True)
class LoadedExtraction:
    artifact_id: str
    identity: ExtractionIdentity
    context: ReadContext = field(repr=False)
    reading: bytes = field(repr=False)
    quality: AutomaticQuality
    statistics: ExtractionStatistics

    def lookup(self, evidence_id: str) -> tuple[SourceSlice, ...]:
        return tuple(p for p in self.context.replay() if p.evidence_id == evidence_id)


class FulltextReason(StrEnum):
    CONVERSION_INCOMPLETE = "conversion_incomplete"
    AMBIGUOUS_READING_ORDER = "ambiguous_reading_order"
    UNKNOWN_PARENT = "unknown_parent"
    INVALID_HIERARCHY = "invalid_hierarchy"
    INVALID_ENCODING = "invalid_encoding"
    INVALID_MEMBERS = "invalid_members"
    IDENTITY_MISMATCH = "identity_mismatch"
    QUALITY_FAILED = "quality_failed"
    UNKNOWN_EVIDENCE = "unknown_evidence"


class FulltextError(ValueError):
    """有限安全原因,不携带正文、路径或 parser 原异常。"""

    def __init__(self, reason: str, quality: AutomaticQuality | None = None) -> None:
        self.reason = FulltextReason(reason)
        self.quality = quality
        guidance = {
            FulltextReason.CONVERSION_INCOMPLETE: "请核对 PDF 与解析配置后重新提取",
            FulltextReason.AMBIGUOUS_READING_ORDER: (
                "请核对 PDF 阅读顺序与解析配置后重新提取"
            ),
            FulltextReason.UNKNOWN_PARENT: "请核对正文层级与解析配置后重新提取",
            FulltextReason.INVALID_HIERARCHY: "请核对正文层级与解析配置后重新提取",
            FulltextReason.INVALID_ENCODING: "请核对原 PDF 字符与解析配置后重新提取",
            FulltextReason.INVALID_MEMBERS: "请从完整备份恢复正文制品后重试",
            FulltextReason.IDENTITY_MISMATCH: (
                "请核对引用的正文身份或从完整备份恢复后重试"
            ),
            FulltextReason.QUALITY_FAILED: (
                "请人工核对 PDF 与质量诊断,修正输入或解析配置后重新提取"
            ),
            FulltextReason.UNKNOWN_EVIDENCE: (
                "请使用该分析保留的合法 evidence ID 回查"
            ),
        }[self.reason]
        super().__init__(f"正文制品拒绝：{self.reason}；{guidance}。")


def manifest_payload(manifest: ExtractionManifest) -> dict[str, object]:
    """旧 manifest 未声明审计时保持原字节编码;不写缺省 null。"""
    return manifest.model_dump(
        mode="json",
        exclude={"execution_audit"} if manifest.execution_audit is None else set(),
    )
