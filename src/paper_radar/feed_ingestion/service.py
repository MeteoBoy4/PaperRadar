"""JGR显式取得与可恢复逐条目导入;HTTP外不替代事实权威。"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.feed_ingestion.models import (
    FeedCheck,
    FeedCheckReason,
    FeedItem,
    FeedItemReason,
    FeedView,
)
from paper_radar.feed_ingestion.parser import parse_items
from paper_radar.feed_ingestion.repository import (
    canonical,
    check_identity,
    read_check,
    require_feed,
    sha,
    validate_checks,
)
from paper_radar.feed_ingestion.tables import checks, items
from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.fixture_audit.acquisition_policy import (
    normalize_request,
    validate_contact,
)
from paper_radar.fixture_audit.errors import FixtureError
from paper_radar.fixture_audit.models import ConditionalHeaders
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.fixture_audit.source_validation import inspect_source
from paper_radar.papers import PaperFacts
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.sources.errors import controlled
from paper_radar.storage.artifact_contract import ArtifactError
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


class JGRFeed:
    def __init__(
        self, database: Path, data_root: Path, *, http: SourceHTTPExecutor | None = None
    ) -> None:
        self.database, self.data_root = database, data_root
        self.http = http or SourceHTTPExecutor()

    @controlled("feed_check")
    def replay(self, check_id: str) -> FeedCheck:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                row = (
                    connection.execute(
                        select(checks).where(checks.c.check_id == check_id)
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    raise PaperError(PaperReason.CORRUPT_REFERENCE, path="check_id")
                return read_check(connection, dict(row), self.database, self.data_root)
        except (ArtifactError, SQLAlchemyError):
            raise PaperError(PaperReason.CORRUPT_REFERENCE, path="feed_check") from None
        finally:
            engine.dispose()

    @controlled("feed_check")
    def view(self, feed_id: str) -> FeedView:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                url = require_feed(connection, feed_id)
                history = tuple(
                    read_check(connection, dict(row), self.database, self.data_root)
                    for row in connection.execute(
                        select(checks)
                        .where(checks.c.feed_id == feed_id)
                        .order_by(checks.c.event_no)
                    ).mappings()
                )
                successful = [item for item in history if item.reason == "acquired"]
                last = successful[-1] if successful else None
                return FeedView(
                    feed_id=feed_id,
                    url=url,
                    checks=history,
                    last_successful_check=last.checked_at if last else None,
                    etag=last.etag if last else None,
                    last_modified=last.last_modified if last else None,
                )
        except (ArtifactError, SQLAlchemyError):
            raise PaperError(PaperReason.CORRUPT_REFERENCE, path="feed_check") from None
        finally:
            engine.dispose()

    @controlled("feed_check")
    def check(self, feed_id: str, *, request_id: str, contact_email: str) -> FeedCheck:
        validate_contact(contact_email)
        if (
            not isinstance(request_id, str)
            or not request_id.strip()
            or len(request_id) > 128
        ):
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="request_id")
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                require_feed(connection, feed_id)
                previous = connection.execute(
                    select(checks.c.check_id).where(
                        checks.c.feed_id == feed_id, checks.c.request_id == request_id
                    )
                ).scalar()
                if previous:
                    check_id = previous
                else:
                    latest = (
                        connection.execute(
                            select(checks)
                            .where(
                                checks.c.feed_id == feed_id,
                                checks.c.artifact_id.is_not(None),
                            )
                            .order_by(checks.c.event_no.desc())
                        )
                        .mappings()
                        .first()
                    )
                    last = (
                        read_check(
                            connection, dict(latest), self.database, self.data_root
                        )
                        if latest
                        else None
                    )
                    conditions = (
                        ConditionalHeaders(
                            if_none_match=last.etag,
                            if_modified_since=last.last_modified,
                            prior_artifact_id=last.artifact_id,
                        )
                        if last and (last.etag or last.last_modified)
                        else ConditionalHeaders()
                    )
                    request = normalize_request(
                        SourceRequest(
                            journal="jgr", route="feed", conditional_headers=conditions
                        )
                    )
                    row = dict(
                        feed_id=feed_id,
                        request_id=request_id,
                        checked_at=datetime.now(UTC).isoformat(),
                        request_json=request.model_dump_json(),
                        prior_check_id=last.check_id if last else None,
                    )
                    check_id = check_identity(row)
                    connection.execute(checks.insert().values(check_id=check_id, **row))
                    connection.commit()
        finally:
            engine.dispose()
        return self.resume(check_id, contact_email=contact_email)

    @controlled("feed_check")
    def resume(self, check_id: str, *, contact_email: str) -> FeedCheck:
        view = self.replay(check_id)
        if view.complete:
            return view
        if view.http is None:
            response = self.http.fetch(view.request, contact_email=contact_email)
            artifact_id = None
            reason: FeedCheckReason = response.facts.reason
            etag, last_modified = response.etag, response.last_modified
            content_decoding = response.facts.decoding
            if reason == "acquired" and response.facts.status_code == 304:
                artifact_id = view.request.conditional_headers.prior_artifact_id
                if view.prior_check_id:
                    content_decoding = self.replay(view.prior_check_id).content_decoding
                etag = etag or view.request.conditional_headers.if_none_match
                last_modified = (
                    last_modified or view.request.conditional_headers.if_modified_since
                )
                if artifact_id is None:
                    reason = "invalid_response"
            elif reason == "acquired" and response.body is not None:
                try:
                    inspection = inspect_source(
                        view.request, response.body, response.facts.decoding or "utf-8"
                    )
                    if not inspection.retain:
                        raise ValueError("invalid_feed")
                    parse_items(response.body, response.facts.decoding or "utf-8")
                except (FixtureError, ValueError):
                    reason = "invalid_feed"
                else:
                    artifact_id = (
                        ArtifactStore(self.database, self.data_root)
                        .publish_single("source_snapshot", (response.body,))
                        .artifact_id
                    )
            if reason != "acquired":
                etag = last_modified = None
            settlement = canonical(
                dict(
                    http=response.facts.model_dump(mode="json"),
                    reason=reason,
                    status_code=response.facts.status_code,
                    artifact_id=artifact_id,
                    etag=etag,
                    last_modified=last_modified,
                    content_decoding=content_decoding,
                )
            )
            engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
            try:
                with engine.connect() as connection:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                    connection.execute(
                        checks.update()
                        .where(
                            checks.c.check_id == check_id,
                            checks.c.settlement_json.is_(None),
                        )
                        .values(
                            settlement_json=settlement,
                            settlement_sha256=sha(check_id + settlement),
                            artifact_id=artifact_id,
                        )
                    )
                    connection.commit()
            finally:
                engine.dispose()
            view = self.replay(check_id)
        if view.complete:
            return view
        assert view.artifact_id is not None
        raw = ArtifactStore(self.database, self.data_root).read_artifact(
            view.artifact_id
        )["payload"]
        parsed = parse_items(raw, view.content_decoding or "utf-8")
        done = {item.position for item in view.items}
        papers = PaperFacts(self.database, self.data_root)
        for position, value in enumerate(parsed, 1):
            if position in done:
                continue
            result = None
            item_reason: FeedItemReason | None = value.reason
            if item_reason is None:
                result = papers.submit(
                    dict(
                        source_kind="feed",
                        feed_id=view.feed_id,
                        entry_id=value.candidate.entry_id,
                        doi=value.candidate.doi,
                        version_kind="journal",
                        observed_at=datetime.fromisoformat(view.checked_at),
                        parser_version=1,
                        interpretation="complete",
                        payload_scope="single_item",
                        payload=raw[value.start : value.end],
                        fields=value.fields,
                    )
                )
                item_reason = result.reason
                if result.reason in (
                    PaperReason.DATABASE_BUSY,
                    PaperReason.CORRUPT_REFERENCE,
                ):
                    raise PaperError(result.reason, path="feed_item_commit")
            outcome = FeedItem(
                position=position,
                entry_id=value.candidate.entry_id,
                doi=value.candidate.doi,
                raw_categories=value.candidate.raw_categories,
                reason=item_reason,
                result=result,
            )
            serialized = outcome.model_dump_json()
            engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
            try:
                with engine.connect() as connection:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                    existing = connection.execute(
                        select(items.c.result_json).where(
                            items.c.check_id == check_id, items.c.position == position
                        )
                    ).scalar()
                    if existing is None:
                        connection.execute(
                            items.insert().values(
                                check_id=check_id,
                                position=position,
                                result_json=serialized,
                                result_sha256=sha(
                                    check_id + str(position) + serialized
                                ),
                            )
                        )
                    elif existing != serialized:
                        raise PaperError(
                            PaperReason.CORRUPT_REFERENCE, path="feed_item_commit"
                        )
                    connection.commit()
            finally:
                engine.dispose()
        return self.replay(check_id)

    @controlled("feed_check")
    def item_bytes(self, check_id: str, position: int) -> bytes:
        view = self.replay(check_id)
        if view.artifact_id is None or type(position) is not int or position <= 0:
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="position")
        raw = ArtifactStore(self.database, self.data_root).read_artifact(
            view.artifact_id
        )["payload"]
        values = parse_items(raw, view.content_decoding or "utf-8")
        if position > len(values):
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="position")
        value = values[position - 1]
        return raw[value.start : value.end]

    @controlled("feed_check")
    def validate_all(self) -> None:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                validate_checks(connection, self.database, self.data_root)
        finally:
            engine.dispose()
