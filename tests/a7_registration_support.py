"""A7 公共登记夹具;未来任务消费者沿用相同真实档案库。"""

from dataclasses import dataclass
from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


@dataclass(frozen=True)
class Archive:
    settings: Path
    database: Path
    data_root: Path
    snapshot_id: str
    paper_id: str
    version_id: str


def archive(root: Path) -> Archive:
    settings, database = value_inputs(root)
    snapshot = compile_config(settings, database)
    data_root = root / "data"
    saved = PaperFacts(database, data_root).submit(
        observation(fields=screening_fields())
    )
    assert saved.paper_id and saved.version_id
    return Archive(
        settings,
        database,
        data_root,
        snapshot.snapshot_id,
        saved.paper_id,
        saved.version_id,
    )


def request_for(archive: Archive, **changes: object) -> dict[str, object]:
    return {
        "paper_id": archive.paper_id,
        "snapshot_id": archive.snapshot_id,
        "stage": "boundary",
        "source": "scheduled",
        "scheduled_day": "2026-01-01",
        **changes,
    }
