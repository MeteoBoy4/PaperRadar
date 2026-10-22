"""版本创建事务内的初始选择及单向正式升级。"""

from uuid import uuid4

from sqlalchemy import Connection, select

from paper_radar.papers.tables import selections, versions


def select_new_version(
    connection: Connection, paper_id: str, version_id: str, kind: str, now: str
) -> None:
    previous = (
        connection.execute(
            select(selections)
            .where(selections.c.paper_id == paper_id)
            .order_by(selections.c.event_no.desc())
        )
        .mappings()
        .first()
    )
    previous_kind = (
        connection.execute(
            select(versions.c.version_kind).where(
                versions.c.version_id == previous["version_id"]
            )
        ).scalar_one()
        if previous
        else None
    )
    if previous is None or (kind == "journal" and previous_kind == "preprint"):
        connection.execute(
            selections.insert().values(
                selection_id=str(uuid4()),
                paper_id=paper_id,
                version_id=version_id,
                reason="journal_upgrade" if previous else "initial",
                selected_at=now,
                event_no=previous["event_no"] + 1 if previous else 1,
            )
        )
