"""Feed 发现的只读语义闭包,覆盖 blob 与所有解释归属。"""

import re

from sqlalchemy import Connection, select

from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.feed import normalize_feed_url
from paper_radar.papers.models import DiscoveryFact, FeedInterpretationFact
from paper_radar.papers.tables import (
    acquisitions,
    feed_discoveries,
    feed_entries,
    feed_interpretations,
    feeds,
    observations,
)
from paper_radar.storage.schema import artifact_members, artifacts


def load_discoveries(
    connection: Connection, version_id: str
) -> tuple[DiscoveryFact, ...]:
    from paper_radar.papers.queries import _utc, _uuid, corrupt

    found = []
    acquired_ids = set()
    source_ids = set()
    for entry in connection.execute(
        select(feed_entries).where(feed_entries.c.version_id == version_id)
    ).mappings():
        feed = (
            connection.execute(select(feeds).where(feeds.c.feed_id == entry["feed_id"]))
            .mappings()
            .one()
        )
        _uuid(feed["feed_id"])
        if normalize_feed_url(feed["url"]) != feed["url"] or not entry["entry_id"]:
            raise corrupt()
        rows = (
            connection.execute(
                select(feed_discoveries).where(
                    feed_discoveries.c.feed_id == entry["feed_id"],
                    feed_discoveries.c.entry_id == entry["entry_id"],
                )
            )
            .mappings()
            .all()
        )
        if not rows:
            raise corrupt()
        for row in rows:
            _uuid(row["discovery_id"])
            _utc(row["first_seen"])
            _utc(row["last_seen"])
            if (
                row["last_seen"] < row["first_seen"]
                or re.fullmatch(r"[0-9a-f]{64}", row["item_fingerprint"]) is None
            ):
                raise corrupt()
            payload = connection.execute(
                select(artifacts.c.kind, artifact_members.c.sha256)
                .join(
                    artifact_members,
                    artifacts.c.artifact_id == artifact_members.c.artifact_id,
                )
                .where(
                    artifacts.c.artifact_id == row["artifact_id"],
                    artifact_members.c.role == "payload",
                )
            ).one()
            if (
                payload.kind != "source_snapshot"
                or payload.sha256 != row["item_fingerprint"]
            ):
                raise corrupt()
            interpretations = (
                connection.execute(
                    select(feed_interpretations)
                    .where(feed_interpretations.c.discovery_id == row["discovery_id"])
                    .order_by(feed_interpretations.c.parser_version)
                )
                .mappings()
                .all()
            )
            if not interpretations:
                raise corrupt()
            ids = []
            explanations = []
            for interpretation in interpretations:
                _utc(interpretation["submitted_at"])
                acquired = (
                    connection.execute(
                        select(acquisitions).where(
                            acquisitions.c.acquisition_id
                            == interpretation["acquisition_id"]
                        )
                    )
                    .mappings()
                    .one()
                )
                if (
                    acquired["source_kind"] != "feed"
                    or acquired["version_id"] != version_id
                    or acquired["provider"] != entry["feed_id"]
                    or acquired["query_key"] != entry["entry_id"]
                    or acquired["observed_at"] != row["first_seen"]
                    or acquired["payload_sha256"] != row["item_fingerprint"]
                    or acquired["parser_version"] != interpretation["parser_version"]
                ):
                    raise corrupt()
                acquired_ids.add(acquired["acquisition_id"])
                source_id = acquired["source_observation_id"]
                explanations.append(
                    FeedInterpretationFact(
                        parser_version=interpretation["parser_version"],
                        submitted_at=interpretation["submitted_at"],
                        acquisition_id=acquired["acquisition_id"],
                        observation_id=source_id,
                    )
                )
                if source_id:
                    source = (
                        connection.execute(
                            select(observations).where(
                                observations.c.observation_id == source_id
                            )
                        )
                        .mappings()
                        .one()
                    )
                    if (
                        source["artifact_id"] != row["artifact_id"]
                        or source["payload_sha256"] != row["item_fingerprint"]
                        or source["parser_version"] != acquired["parser_version"]
                        or source["source_kind"] != "feed"
                    ):
                        raise corrupt()
                    source_ids.add(source_id)
                    ids.append(source_id)
            found.append(
                DiscoveryFact(
                    discovery_id=row["discovery_id"],
                    version_id=version_id,
                    feed_id=feed["feed_id"],
                    feed_url=feed["url"],
                    entry_id=entry["entry_id"],
                    item_fingerprint=row["item_fingerprint"],
                    artifact_id=row["artifact_id"],
                    first_seen=row["first_seen"],
                    last_seen=row["last_seen"],
                    observation_ids=tuple(ids),
                    interpretations=tuple(explanations),
                )
            )
    if acquired_ids != set(
        connection.execute(
            select(acquisitions.c.acquisition_id).where(
                acquisitions.c.version_id == version_id,
                acquisitions.c.source_kind == "feed",
            )
        ).scalars()
    ) or source_ids != set(
        connection.execute(
            select(observations.c.observation_id).where(
                observations.c.version_id == version_id,
                observations.c.source_kind == "feed",
            )
        ).scalars()
    ):
        raise PaperError(PaperReason.CORRUPT_REFERENCE)
    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.first_seen,
                item.feed_id,
                item.entry_id,
                item.item_fingerprint,
            ),
        )
    )


def validate_feed_registry(connection: Connection) -> None:
    """没有发现记录的合法 Feed 也属于备份语义闭包。"""
    from paper_radar.papers.queries import _uuid, corrupt

    try:
        for feed in connection.execute(select(feeds)).mappings():
            _uuid(feed["feed_id"])
            if normalize_feed_url(feed["url"]) != feed["url"]:
                raise corrupt()
    except (PaperError, ValueError, TypeError):
        raise corrupt() from None
