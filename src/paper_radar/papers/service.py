"""论文事实公共服务:来源先发布,业务短事务,查询一致视图。"""

import sqlite3
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.feed import normalize_feed_url
from paper_radar.papers.models import FeedFact, PaperTrace, PaperView, WriteResult
from paper_radar.papers.queries import load_trace, validate_unbound_acquisitions
from paper_radar.papers.repository import needs_source, save_observation
from paper_radar.papers.tables import feeds, papers
from paper_radar.papers.text import normalize_fields, parse_observation
from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError


def _database_error(error: SQLAlchemyError) -> PaperError:
    if (
        isinstance(error, DBAPIError)
        and isinstance(error.orig, sqlite3.Error)
        and (getattr(error.orig, "sqlite_errorcode", 0) & 0xFF) == sqlite3.SQLITE_BUSY
    ):
        return PaperError(PaperReason.DATABASE_BUSY)
    return PaperError(PaperReason.CORRUPT_REFERENCE)


class PaperFacts:
    def __init__(self, database: Path, data_root: Path | None = None) -> None:
        self.database = database
        self.data_root = data_root

    def register_feed(self, url: str) -> FeedFact:
        normalized = normalize_feed_url(url)
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                row = (
                    connection.execute(select(feeds).where(feeds.c.url == normalized))
                    .mappings()
                    .first()
                )
                if row is None:
                    feed_id = str(uuid4())
                    connection.execute(
                        feeds.insert().values(feed_id=feed_id, url=normalized)
                    )
                    connection.commit()
                    return FeedFact(feed_id=feed_id, url=normalized)
                return FeedFact.model_validate(dict(row))
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def submit(self, observation: object) -> WriteResult:
        try:
            item = parse_observation(observation)
            doi = normalize_doi(item.doi) if item.doi is not None else None
            fields = normalize_fields(item.fields)
            if self.data_root is None:
                raise PaperError(PaperReason.INVALID_OBSERVATION, path="data_root")
            engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
            try:
                require_current_revision(engine)
                if item.source_kind == "feed":
                    from paper_radar.papers.feed_repository import submit_feed

                    return submit_feed(
                        engine, self.database, self.data_root, item, doi, fields
                    )
                if doi is None:
                    raise PaperError(PaperReason.INVALID_OBSERVATION, path="doi")
                artifact_id = None
                if needs_source(engine, item, doi, fields):
                    artifact_id = (
                        ArtifactStore(self.database, self.data_root)
                        .publish_single("source_snapshot", (item.payload,))
                        .artifact_id
                    )
                return save_observation(engine, item, doi, fields, artifact_id)
            finally:
                engine.dispose()
        except PaperError as error:
            return WriteResult(status="rejected", reason=error.reason)
        except ArtifactError as error:
            return WriteResult(
                status="rejected",
                reason=PaperReason.DATABASE_BUSY
                if error.reason == ArtifactReason.DATABASE_BUSY
                else PaperReason.CORRUPT_REFERENCE,
            )
        except StorageError:
            return WriteResult(status="rejected", reason=PaperReason.CORRUPT_REFERENCE)
        except SQLAlchemyError as error:
            return WriteResult(status="rejected", reason=_database_error(error).reason)

    def trace(self, paper_id: str, *, verify_source_bytes: bool = False) -> PaperTrace:
        try:
            engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        except StorageError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                result = load_trace(connection, paper_id)
            if verify_source_bytes:
                if self.data_root is None:
                    raise PaperError(PaperReason.CORRUPT_REFERENCE, path="data_root")
                store = ArtifactStore(self.database, self.data_root)
                for source in result.observations:
                    store.read_artifact(source.artifact_id)
            return result
        except StorageError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def show(self, paper_id: str) -> PaperView:
        return self.trace(paper_id).current

    def validate_all(self) -> None:
        """备份固定数据库上的全部论文引用链校验,无修复副作用。"""
        try:
            engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        except StorageError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                from paper_radar.papers.feed_queries import validate_feed_registry

                validate_feed_registry(connection)
                validate_unbound_acquisitions(connection)
                for paper_id in connection.execute(select(papers.c.paper_id)).scalars():
                    load_trace(connection, paper_id)
        except StorageError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()
