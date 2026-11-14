"""回放封闭错误词表;诊断不携带私有路径或原文。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REASONS = frozenset(
    {
        "invalid_arguments",
        "restore_provenance_invalid",
        "unsafe_layout",
        "isolation_unavailable",
        "isolation_verification_failed",
        "replay_failed",
        "file_missing",
        "file_corrupt",
        "unsafe_path",
        "unexpected_entry",
        "invalid_manifest",
        "database_invalid",
        "registration_invalid",
        "config_invalid",
        "supply_invalid",
        "unsupported_revision",
        "unsupported_format",
        "unsupported_rule_version",
        "output_invalid",
        "content_corrupt",
    }
)


class ReplayError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in REASONS else "replay_failed"
        super().__init__(self.reason)


class ReplaySummary(BaseModel):
    """终端只接受封闭枚举与非负计数。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    isolation: Literal["verified"]
    descendant: Literal["verified"]
    originals_denied: int = Field(ge=0)
    missing_originals: int = Field(ge=0)
    sockets_denied: Literal[3]
    direct_connect_denied: Literal[True]
    reports: int = Field(ge=0)
    analyses: int = Field(ge=0)
    evidence_slices: int = Field(ge=0)
    exposures: int = Field(ge=0)
