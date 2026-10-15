"""快照发现的只读摘要类型。不携带配置正文或完整性结论。"""

from dataclasses import dataclass
from datetime import datetime

from paper_radar.config.compile import MaterialKind


@dataclass(frozen=True, slots=True)
class SnapshotVersion:
    kind: MaterialKind
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class ConfigSnapshotSummary:
    snapshot_id: str
    short_reference: str
    created_at: datetime | None
    versions: tuple[SnapshotVersion, ...]
