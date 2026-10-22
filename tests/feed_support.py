"""Feed 公共输入 fixture,不访问私有实现。"""

from datetime import UTC, datetime
from pathlib import Path

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database


def facts(root: Path) -> PaperFacts:
    database = root / "facts.sqlite"
    upgrade_database(database)
    return PaperFacts(database, root / "data")


def item(feed_id: str, **changes: object) -> dict[str, object]:
    return {
        "source_kind": "feed",
        "feed_id": feed_id,
        "entry_id": "entry-1",
        "doi": None,
        "version_kind": "journal",
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "parser_version": 1,
        "interpretation": "complete",
        "payload_scope": "single_item",
        "payload": b"<item><guid>entry-1</guid><title>A</title></item>",
        "fields": {"title": {"value": "A", "locator": "item/title"}},
        **changes,
    }
