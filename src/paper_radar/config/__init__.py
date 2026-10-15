"""公共配置服务。延迟导入存储层以保持 CLI --help 无数据库副作用。"""

from pathlib import Path

from paper_radar.config.adapters import AdapterSemantics
from paper_radar.config.compile import (
    RuntimeConfigSnapshot,
    SnapshotMaterial,
    StageName,
    StageReadiness,
)
from paper_radar.config.diff import (
    ComponentChange,
    ConfigCategory,
    ConfigIdentity,
    ConfigIdentityChange,
    ConfigSnapshotDiff,
    StageProjectionChange,
    compare_config_snapshots,
)
from paper_radar.config.errors import ConfigError
from paper_radar.config.escalation import (
    EscalationSemantics,
    ExcerptSelectorVersion,
    SuggestionRuleVersion,
)
from paper_radar.config.extraction import (
    ExtractionSemantics,
    ModelStage,
    NormalizationVersion,
)
from paper_radar.config.journals import JournalSemantics, JournalsStatus, JournalTier
from paper_radar.config.projections import (
    CalibrationBaseline,
    ConfigSemantics,
    StageConfigProjection,
    project_config,
)
from paper_radar.config.read import ChunkingVersion, ReadSemantics
from paper_radar.config.snapshot_summary import ConfigSnapshotSummary, SnapshotVersion
from paper_radar.config.topics import TopicsStatus


def check_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    from paper_radar.config.service import check_config as run

    return run(settings_path, database)


def compile_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    from paper_radar.config.service import compile_config as run

    return run(settings_path, database)


def load_config_snapshot(database: Path, snapshot_id: str) -> RuntimeConfigSnapshot:
    from paper_radar.config.service import load_config_snapshot as run

    return run(database, snapshot_id)


def diff_config_snapshots(
    database: Path, before_id: str, after_id: str
) -> ConfigSnapshotDiff:
    from paper_radar.config.service import diff_config_snapshots as run

    return run(database, before_id, after_id)


def list_config_snapshots(database: Path) -> tuple[ConfigSnapshotSummary, ...]:
    from paper_radar.config.snapshot_queries import list_config_snapshots as run

    return run(database)


def resolve_config_snapshot_reference(database: Path, reference: str) -> str:
    from paper_radar.config.snapshot_queries import (
        resolve_config_snapshot_reference as run,
    )

    return run(database, reference)


def upgrade_database(path: Path) -> str:
    from paper_radar.storage.database import upgrade_database as run
    from paper_radar.storage.errors import StorageError

    try:
        return run(path)
    except StorageError as error:
        raise ConfigError(str(error)) from None


__all__ = [
    "AdapterSemantics",
    "CalibrationBaseline",
    "ChunkingVersion",
    "ComponentChange",
    "ConfigCategory",
    "ConfigError",
    "ConfigIdentity",
    "ConfigIdentityChange",
    "ConfigSemantics",
    "ConfigSnapshotDiff",
    "ConfigSnapshotSummary",
    "EscalationSemantics",
    "ExcerptSelectorVersion",
    "ExtractionSemantics",
    "JournalSemantics",
    "JournalTier",
    "JournalsStatus",
    "ModelStage",
    "NormalizationVersion",
    "ReadSemantics",
    "RuntimeConfigSnapshot",
    "SnapshotMaterial",
    "SnapshotVersion",
    "StageConfigProjection",
    "StageName",
    "StageProjectionChange",
    "StageReadiness",
    "SuggestionRuleVersion",
    "TopicsStatus",
    "check_config",
    "compare_config_snapshots",
    "compile_config",
    "diff_config_snapshots",
    "list_config_snapshots",
    "load_config_snapshot",
    "project_config",
    "resolve_config_snapshot_reference",
    "upgrade_database",
]
