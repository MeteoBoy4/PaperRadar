"""论文事实公共服务:来源先发布,业务短事务,查询一致视图。"""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from paper_radar.papers.conflict_tables import conflicts as conflict_table
from paper_radar.papers.conflicts import read_all
from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.feed import normalize_feed_url
from paper_radar.papers.feed_queries import validate_feed_registry
from paper_radar.papers.feed_repository import submit_feed
from paper_radar.papers.manual import (
    parse_correction,
    retry_correction,
    save_correction,
    validate_manual_payload,
)
from paper_radar.papers.mapping import map_screening_inputs
from paper_radar.papers.mapping_models import ScreeningMappingResult
from paper_radar.papers.models import (
    ConflictView,
    FeedFact,
    PaperTrace,
    PaperView,
    RevisionView,
    WriteResult,
)
from paper_radar.papers.queries import (
    load_trace,
    resolve_revision,
    validate_unbound_acquisitions,
)
from paper_radar.papers.relation_repository import (
    validate_relation_references,
)
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
                    result = submit_feed(
                        engine, self.database, self.data_root, item, doi, fields
                    )
                    if result.conflict_id:
                        self.conflicts(conflict_id=result.conflict_id)
                    return result
                if doi is None:
                    raise PaperError(PaperReason.INVALID_OBSERVATION, path="doi")
                artifact_id = None
                if needs_source(engine, item, doi, fields):
                    artifact_id = (
                        ArtifactStore(self.database, self.data_root)
                        .publish_single("source_snapshot", (item.payload,))
                        .artifact_id
                    )
                result = save_observation(engine, item, doi, fields, artifact_id)
                if result.conflict and not result.conflict_id:
                    artifact_id = (
                        ArtifactStore(self.database, self.data_root)
                        .publish_single("source_snapshot", (item.payload,))
                        .artifact_id
                    )
                    result = save_observation(engine, item, doi, fields, artifact_id)
                if result.conflict_id:
                    self.conflicts(conflict_id=result.conflict_id)
                return result
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

    def conflicts(
        self,
        *,
        conflict_id: str | None = None,
        feed_id: str | None = None,
        entry_id: str | None = None,
        paper_id: str | None = None,
    ) -> tuple[ConflictView, ...]:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                return read_all(
                    connection,
                    self.database,
                    self.data_root,
                    conflict_id=conflict_id,
                    feed_id=feed_id,
                    entry_id=entry_id,
                    paper_id=paper_id,
                )
        except ArtifactError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def conflict_bytes(self, conflict_id: str) -> bytes:
        records = self.conflicts(conflict_id=conflict_id)
        if not records or self.data_root is None:
            raise PaperError(PaperReason.CORRUPT_REFERENCE, path="conflict_id")
        return ArtifactStore(self.database, self.data_root).read_artifact(
            records[0].artifact_id
        )["payload"]

    def conflict_assertion(self, conflict_id: str) -> dict[str, object]:
        """显式展开原断言;普通冲突查询不展开题名、摘要或原字节。"""
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                records = read_all(
                    connection, self.database, self.data_root, conflict_id=conflict_id
                )
                if not records:
                    raise PaperError(PaperReason.CORRUPT_REFERENCE, path="conflict_id")
                value: dict[str, object] = json.loads(
                    connection.execute(
                        select(conflict_table.c.assertion_json).where(
                            conflict_table.c.conflict_id == conflict_id
                        )
                    ).scalar_one()
                )
                return value
        except ArtifactError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def correct(self, correction: object) -> WriteResult:
        try:
            item, payload = parse_correction(correction)
            if self.data_root is None:
                raise PaperError(
                    PaperReason.INVALID_MANUAL_CORRECTION, path="data_root"
                )
            engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
            try:
                require_current_revision(engine)
                with engine.connect() as connection:
                    connection.exec_driver_sql("BEGIN")
                    retry = retry_correction(connection, item, payload)
                    if retry:
                        return retry
                artifact_id = (
                    ArtifactStore(self.database, self.data_root)
                    .publish_single("source_snapshot", (payload,))
                    .artifact_id
                )
                return save_correction(engine, item, payload, artifact_id)
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
        if verify_source_bytes and self.data_root is None:
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="data_root")
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                result = load_trace(connection, paper_id)
            if verify_source_bytes:
                assert self.data_root is not None
                store = ArtifactStore(self.database, self.data_root)
                for relation in result.relations:
                    store.read_artifact(relation.artifact_id)
                for source in result.observations:
                    payload = store.read_artifact(source.artifact_id)["payload"]
                    if source.source_kind == "manual":
                        validate_manual_payload(result, source, payload)
            return result
        except ArtifactError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def show(self, paper_id: str) -> PaperView:
        return self.trace(paper_id).current

    def revision(self, version_id: str, revision_no: int) -> RevisionView:
        """只接受版本与完整修订号,不拼接各字段历史。"""
        try:
            engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
            try:
                require_current_revision(engine)
                with engine.connect() as connection:
                    connection.exec_driver_sql("BEGIN")
                    return resolve_revision(
                        connection, version_id=version_id, revision_no=revision_no
                    )
            finally:
                engine.dispose()
        except SQLAlchemyError as error:
            raise _database_error(error) from None

    def map_screening_inputs(
        self,
        *,
        snapshot_id: str,
        paper_id: str | None = None,
        version_id: str | None = None,
        revision_no: int | None = None,
    ) -> ScreeningMappingResult:
        return map_screening_inputs(
            self.database,
            snapshot_id=snapshot_id,
            paper_id=paper_id,
            version_id=version_id,
            revision_no=revision_no,
        )

    def validate_all(self) -> None:
        """备份固定数据库上的全部论文引用链校验,无修复副作用。"""
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                read_all(connection, self.database, self.data_root)
                validate_feed_registry(connection)
                validate_relation_references(connection)
                validate_unbound_acquisitions(connection)
                for paper_id in connection.execute(select(papers.c.paper_id)).scalars():
                    result = load_trace(connection, paper_id)
                    if result.corrections:
                        if self.data_root is None:
                            raise PaperError(
                                PaperReason.CORRUPT_REFERENCE, path="data_root"
                            )
                        store = ArtifactStore(self.database, self.data_root)
                        for source in result.observations:
                            if source.source_kind == "manual":
                                validate_manual_payload(
                                    result,
                                    source,
                                    store.read_artifact(source.artifact_id)["payload"],
                                )
        except ArtifactError:
            raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()
