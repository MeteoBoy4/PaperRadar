"""给定合成 PDF 与固定 JGR 声明的公共登记准备。"""

from pathlib import Path

from paper_radar.fixture_audit import FixtureAudit
from paper_radar.storage.database import upgrade_database

PDF_BYTES = b"%PDF-1.7\nsynthetic test fixture\n%%EOF\n"
PDF_SHA256 = "89a0c849f8a6bc4d7fc2724e26f535f1e0112c0772582a1d519532543eeb3376"


def registered_jgr(root: Path) -> tuple[FixtureAudit, str]:
    database = root / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(database, root / "data")
    records = service.register(
        Path(__file__).parents[1] / "fixtures/a10/historical-v1.json"
    )
    record = next(
        item
        for item in records.entries
        if item.entry.purpose == "pdf" and item.entry.journal == "jgr"
    )
    return service, record.record_id
