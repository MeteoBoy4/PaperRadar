"""组合读面默认只返回依据和受控状态。"""

from dataclasses import dataclass
from typing import Any, Literal

from paper_radar.feed_ingestion.models import FeedItemReason
from paper_radar.feed_metadata.models import MetadataResult
from paper_radar.papers.models import ConflictView
from paper_radar.screening_tasks.models import RequestReceipt


@dataclass(frozen=True)
class PreparedItem:
    position: int
    paper_id: str | None
    metadata_request_key: str | None = None
    metadata: MetadataResult | None = None
    conflict_id: str | None = None
    reason: FeedItemReason | Literal["metadata_incomplete"] | None = None


@dataclass(frozen=True)
class Preparation:
    check_id: str
    items: tuple[PreparedItem, ...]
    scope: str = "仅为工程准备结果;真实来源、B入口及自动执行资格未验证"


@dataclass(frozen=True)
class ValueRegistration:
    purpose: Literal["production", "test"]
    receipt: RequestReceipt
    metadata_request_key: str
    boundary_success_id: str
    language_basis: dict[str, Any]
    scope: str = "仅登记任务;不执行模型、不授予B或自动Read资格"


@dataclass(frozen=True)
class PipelineTrace:
    paper_id: str
    version_id: str
    revision_no: int
    metadata: tuple[MetadataResult, ...]
    conflicts: tuple[ConflictView, ...]
    language: dict[str, Any]
    receipts: tuple[RequestReceipt, ...]
