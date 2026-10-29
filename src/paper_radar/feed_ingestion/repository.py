"""生产 Feed 取得及逐条目回执的短事务与只读校验。"""

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, select

from paper_radar.feed_ingestion.models import FeedCheck, FeedItem
from paper_radar.feed_ingestion.parser import parse_items
from paper_radar.feed_ingestion.tables import checks, items
from paper_radar.fixture_audit.acquisition_models import (
    SourceRequest,
    require_utc_timestamp,
)
from paper_radar.fixture_audit.acquisition_policy import (
    FEED_ENDPOINTS,
    normalize_request,
)
from paper_radar.fixture_audit.source_http import safe_condition_header
from paper_radar.papers.conflict_tables import conflicts
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.repository import saved_acquisition_result
from paper_radar.papers.tables import (
    acquisitions,
    feed_interpretations,
    feeds,
)
from paper_radar.storage.artifacts import ArtifactStore


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def corrupt() -> PaperError:
    return PaperError(PaperReason.CORRUPT_REFERENCE, path="feed_check")


def require_feed(connection: Connection, feed_id: str) -> str:
    url = connection.execute(
        select(feeds.c.url).where(feeds.c.feed_id == feed_id)
    ).scalar()
    expected = next(item.url for item in FEED_ENDPOINTS if item.journal == "jgr")
    if url != expected:
        raise PaperError(PaperReason.INVALID_OBSERVATION, path="feed_id")
    return url


def check_identity(row: dict[str, Any]) -> str:
    return sha(
        canonical(
            {
                key: row[key]
                for key in (
                    "feed_id",
                    "request_id",
                    "checked_at",
                    "request_json",
                    "prior_check_id",
                )
            }
        )
    )


def read_check(
    connection: Connection, row: dict[str, Any], database: Path, data_root: Path
) -> FeedCheck:
    try:
        if row["check_id"] != check_identity(row):
            raise corrupt()
        require_feed(connection, row["feed_id"])
        require_utc_timestamp(row["checked_at"])
        request = SourceRequest.model_validate_json(row["request_json"])
        if (
            normalize_request(request) != request
            or request.route != "feed"
            or request.journal != "jgr"
        ):
            raise corrupt()
        if row["settlement_json"] is None:
            if row["artifact_id"] is not None or row["settlement_sha256"] is not None:
                raise corrupt()
            settlement = {}
        else:
            if (
                sha(row["check_id"] + row["settlement_json"])
                != row["settlement_sha256"]
            ):
                raise corrupt()
            settlement = json.loads(row["settlement_json"])
            if settlement["artifact_id"] != row["artifact_id"]:
                raise corrupt()
        outcomes = []
        for item in connection.execute(
            select(items)
            .where(items.c.check_id == row["check_id"])
            .order_by(items.c.position)
        ).mappings():
            if (
                sha(row["check_id"] + str(item["position"]) + item["result_json"])
                != item["result_sha256"]
            ):
                raise corrupt()
            outcome = FeedItem.model_validate_json(item["result_json"])
            if outcome.position != item["position"]:
                raise corrupt()
            outcomes.append(outcome)
        view = FeedCheck.model_validate_json(
            canonical(
                dict(
                    check_id=row["check_id"],
                    feed_id=row["feed_id"],
                    request_id=row["request_id"],
                    checked_at=row["checked_at"],
                    request=json.loads(row["request_json"]),
                    prior_check_id=row["prior_check_id"],
                    items=[item.model_dump(mode="json") for item in outcomes],
                    **settlement,
                )
            )
        )
        if view.http is not None and (
            view.status_code != view.http.status_code
            or (
                view.reason != view.http.reason
                and not (
                    view.reason == "invalid_feed"
                    and view.http.reason == "acquired"
                    and view.status_code == 200
                )
            )
        ):
            raise corrupt()
        if (
            safe_condition_header(view.etag) != view.etag
            or safe_condition_header(view.last_modified) != view.last_modified
        ):
            raise corrupt()
        conditions = request.conditional_headers
        if conditions.prior_artifact_id is not None:
            if view.prior_check_id is None:
                raise corrupt()
            prior = (
                connection.execute(
                    select(checks).where(checks.c.check_id == view.prior_check_id)
                )
                .mappings()
                .one()
            )
            if (
                prior["check_id"] != check_identity(dict(prior))
                or sha(prior["check_id"] + prior["settlement_json"])
                != prior["settlement_sha256"]
            ):
                raise corrupt()
            prior_settlement = json.loads(prior["settlement_json"])
            if (
                prior["feed_id"] != view.feed_id
                or prior["artifact_id"] != conditions.prior_artifact_id
                or prior["event_no"] >= row["event_no"]
                or prior_settlement["etag"] != conditions.if_none_match
                or prior_settlement["last_modified"] != conditions.if_modified_since
            ):
                raise corrupt()
        if view.artifact_id:
            raw = ArtifactStore(database, data_root).read_artifact(view.artifact_id)[
                "payload"
            ]
            parsed = parse_items(raw, view.content_decoding or "utf-8")
            if view.status_code == 304:
                if (
                    view.items
                    or not view.prior_check_id
                    or request.conditional_headers.prior_artifact_id != view.artifact_id
                ):
                    raise corrupt()
                prior = (
                    connection.execute(
                        select(checks).where(checks.c.check_id == view.prior_check_id)
                    )
                    .mappings()
                    .one()
                )
                if (
                    prior["feed_id"] != view.feed_id
                    or prior["artifact_id"] != view.artifact_id
                    or prior["event_no"] >= row["event_no"]
                ):
                    raise corrupt()
            elif view.status_code == 200:
                if view.reason != "acquired":
                    raise corrupt()
                for outcome in view.items:
                    original = parsed[outcome.position - 1]
                    if (outcome.entry_id, outcome.doi, outcome.raw_categories) != (
                        original.candidate.entry_id,
                        original.candidate.doi,
                        original.candidate.raw_categories,
                    ):
                        raise corrupt()
                    result = outcome.result
                    if result and result.acquisition_id:
                        acquired = (
                            connection.execute(
                                select(acquisitions).where(
                                    acquisitions.c.acquisition_id
                                    == result.acquisition_id
                                )
                            )
                            .mappings()
                            .one()
                        )
                        expected = saved_acquisition_result(connection, acquired)
                        if result.model_copy(update={"discovery_id": None}) != expected:
                            raise corrupt()
                        discovery_id = connection.execute(
                            select(feed_interpretations.c.discovery_id).where(
                                feed_interpretations.c.acquisition_id
                                == result.acquisition_id
                            )
                        ).scalar_one()
                        if discovery_id != result.discovery_id:
                            raise corrupt()
                        if (
                            acquired["source_kind"] != "feed"
                            or acquired["provider"] != view.feed_id
                            or acquired["query_key"] != outcome.entry_id
                            or acquired["payload_sha256"]
                            != hashlib.sha256(
                                raw[original.start : original.end]
                            ).hexdigest()
                        ):
                            raise corrupt()
                    elif result and result.conflict_id:
                        conflict = (
                            connection.execute(
                                select(conflicts).where(
                                    conflicts.c.conflict_id == result.conflict_id
                                )
                            )
                            .mappings()
                            .one()
                        )
                        assertion = json.loads(conflict["assertion_json"])
                        if (
                            assertion["feed_id"] != view.feed_id
                            or assertion["entry_id"] != outcome.entry_id
                        ):
                            raise corrupt()
                if len(view.items) > len(parsed):
                    raise corrupt()
            else:
                raise corrupt()
            complete = view.status_code == 304 or len(view.items) == len(parsed)
        else:
            if view.items or view.reason == "acquired":
                raise corrupt()
            complete = view.http is not None
        return view.model_copy(update={"complete": complete})
    except PaperError:
        raise
    except (ValueError, KeyError, IndexError, TypeError):
        raise corrupt() from None


def validate_checks(
    connection: Connection, database: Path, data_root: Path | None
) -> None:
    for row in connection.execute(select(checks)).mappings():
        if data_root is None:
            raise corrupt()
        read_check(connection, dict(row), database, data_root)
