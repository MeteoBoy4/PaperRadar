"""当前正文选择事实:文件预验在锁外,轻量绑定与追加在同一写事务。"""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, insert, select

from paper_radar.body import tables
from paper_radar.body.extraction import extraction_view
from paper_radar.body.models import BodyError
from paper_radar.body.pdf import valid_pdf_bytes
from paper_radar.body.query_records import current_pdf, root_fact
from paper_radar.body.repository import digest, sequence, transaction
from paper_radar.calibration import visibility
from paper_radar.eligibility import RootPurpose
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.papers.queries import resolve_revision
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.storage.artifact_contract import ArtifactError
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.schema import (
    body_selections,
    experiment_frozen_samples,
    experiment_pdf_confirmations,
    experiment_selections,
)


class BodySelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    body_selection_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1, max_length=128)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    root_id: str
    paper_id: str
    version_id: str
    revision_no: int = Field(gt=0)
    sequence: int = Field(gt=0)
    sample_id: str
    attachment_id: str
    authorization_id: str
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    reading_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_map_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selector: Literal["owner"]
    recorder: Literal["agent"]
    selected_at: str

    @property
    def identity(self) -> ExtractionIdentity:
        return ExtractionIdentity(
            self.fingerprint, self.reading_sha256, self.evidence_map_sha256
        )

    def request_digest(self) -> str:
        return digest(
            self.model_dump(
                exclude={"body_selection_id", "sequence", "selected_at", "request_hash"}
            )
        )


def require_visibility() -> None:
    if (
        visibility.evaluate_visibility(frozenset()).permission(
            visibility.VisibilityCapability.SET_DECISION
        )
        is not visibility.VisibilityPermission.ALLOWED
    ):
        raise BodyError("visibility_denied")


def bound(connection: Connection, record: BodySelection, *, current: bool) -> bool:
    """只读关系与当前元数据,不读取制品或配置。"""
    root = root_fact(connection)
    pdf = (
        connection.execute(
            select(tables.pdfs).where(
                tables.pdfs.c.attachment_id == record.attachment_id
            )
        )
        .mappings()
        .first()
    )
    sample = (
        connection.execute(
            select(tables.samples).where(tables.samples.c.sample_id == record.sample_id)
        )
        .mappings()
        .first()
    )
    relation = (
        connection.execute(
            select(
                experiment_pdf_confirmations.c.selection_id,
                experiment_selections.c.record_json,
            )
            .select_from(experiment_pdf_confirmations)
            .join(
                experiment_frozen_samples,
                experiment_frozen_samples.c.confirmation_id
                == experiment_pdf_confirmations.c.confirmation_id,
            )
            .join(
                experiment_selections,
                experiment_selections.c.selection_id
                == experiment_pdf_confirmations.c.selection_id,
            )
            .where(
                experiment_frozen_samples.c.sample_id == record.sample_id,
                experiment_frozen_samples.c.attachment_id == record.attachment_id,
            )
        )
        .mappings()
        .first()
    )
    try:
        frozen = json.loads(relation["record_json"]) if relation is not None else {}
        frozen_binding = (
            frozen["root_id"],
            frozen["paper_id"],
            frozen["version_id"],
            frozen["revision_no"],
        )
    except (ValueError, KeyError, TypeError):
        return False
    view = extraction_view(connection, record.fingerprint)
    success = connection.execute(
        select(tables.successes.c.fingerprint).where(
            tables.successes.c.fingerprint == record.fingerprint
        )
    ).scalar_one_or_none()
    if (
        root.root_id != record.root_id
        or root.purpose is not RootPurpose.EXPERIMENT
        or pdf is None
        or sample is None
        or relation is None
        or relation["selection_id"] != record.authorization_id
        or frozen_binding
        != (record.root_id, record.paper_id, record.version_id, record.revision_no)
        or (pdf["paper_id"], pdf["version_id"], pdf["pdf_sha256"])
        != (record.paper_id, record.version_id, record.pdf_sha256)
        or (sample["paper_id"], sample["version_id"], sample["pdf_sha256"])
        != (record.paper_id, record.version_id, record.pdf_sha256)
        or success is None
        or view is None
        or view.identity != record.identity
        or view.pdf_sha256 != record.pdf_sha256
    ):
        return False
    if not current:
        return True
    revision = resolve_revision(connection, paper_id=record.paper_id)
    latest_pdf = current_pdf(connection, record.paper_id, revision.version_id)
    latest_sample = connection.execute(
        select(tables.samples.c.sample_id)
        .where(tables.samples.c.paper_id == record.paper_id)
        .order_by(tables.samples.c.sequence.desc())
    ).scalar()
    latest_authorization = connection.execute(
        select(experiment_selections.c.selection_id).order_by(
            experiment_selections.c.sequence.desc()
        )
    ).scalar()
    return (
        (revision.version_id, revision.revision_no)
        == (record.version_id, record.revision_no)
        and latest_pdf is not None
        and latest_pdf.attachment_id == record.attachment_id
        and latest_sample == record.sample_id
        and latest_authorization == record.authorization_id
    )


def current_selection(connection: Connection, paper_id: str) -> BodySelection | None:
    row = (
        connection.execute(
            select(body_selections)
            .where(body_selections.c.paper_id == paper_id)
            .order_by(body_selections.c.sequence.desc())
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    try:
        record = BodySelection.model_validate(dict(row))
        if record.request_hash != record.request_digest() or not bound(
            connection, record, current=False
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise BodyError("corrupt_reference") from None
    return record if bound(connection, record, current=True) else None


class BodySelections:
    def __init__(self, database: Path, data_root: Path) -> None:
        self.database, self.data_root = database, data_root

    def history(self, paper_id: str | None = None) -> tuple[BodySelection, ...]:
        store = ArtifactStore(self.database, self.data_root)
        try:
            with transaction(self.database) as connection:
                rows = (
                    connection.execute(
                        select(body_selections).order_by(
                            body_selections.c.paper_id, body_selections.c.sequence
                        )
                    )
                    .mappings()
                    .all()
                )
                records = tuple(BodySelection.model_validate(dict(row)) for row in rows)
                sequences: dict[str, int] = {}
                for record in records:
                    sequences[record.paper_id] = sequences.get(record.paper_id, 0) + 1
                    selected = datetime.fromisoformat(record.selected_at)
                    offset = selected.utcoffset()
                    if (
                        record.request_hash != record.request_digest()
                        or record.sequence != sequences[record.paper_id]
                        or offset is None
                        or offset.total_seconds() != 0
                        or not bound(connection, record, current=False)
                    ):
                        raise ValueError
                    view = extraction_view(connection, record.fingerprint)
                    assert view is not None and view.artifact_id is not None
                    FulltextArtifacts(store).load(
                        view.artifact_id, expected_identity=record.identity
                    )
                return tuple(
                    r for r in records if paper_id is None or r.paper_id == paper_id
                )
        except (ArtifactError, ValueError, KeyError, TypeError, AssertionError):
            raise BodyError("corrupt_reference") from None

    def select(
        self, record: BodySelection, *, guard: Callable[[Connection], None]
    ) -> tuple[BodySelection, bool]:
        """协调者已完整预验样本;写锁内再次检查同一绑定。"""
        store = ArtifactStore(self.database, self.data_root)
        with transaction(self.database) as connection:
            if not bound(connection, record, current=True):
                raise BodyError("facts_changed")
            view = extraction_view(connection, record.fingerprint)
            assert view is not None and view.artifact_id is not None
            pdf_artifact = connection.execute(
                select(tables.pdfs.c.artifact_id).where(
                    tables.pdfs.c.attachment_id == record.attachment_id
                )
            ).scalar_one()
        try:
            FulltextArtifacts(store).load(
                view.artifact_id, expected_identity=record.identity
            )
            if not valid_pdf_bytes(
                store.read_artifact(pdf_artifact)["payload"], record.pdf_sha256
            ):
                raise BodyError("invalid_pdf")
        except ArtifactError:
            raise BodyError("corrupt_reference") from None
        with transaction(self.database, write=True) as connection:
            require_visibility()
            guard(connection)
            if not bound(connection, record, current=True):
                raise BodyError("facts_changed")
            old = (
                connection.execute(
                    select(body_selections).where(
                        body_selections.c.request_id == record.request_id
                    )
                )
                .mappings()
                .first()
            )
            if old is not None:
                saved = BodySelection.model_validate(dict(old))
                if saved.request_hash != record.request_digest():
                    raise BodyError("request_conflict")
                return saved, True
            saved = record.model_copy(
                update={
                    "body_selection_id": str(uuid4()),
                    "sequence": sequence(connection, body_selections, record.paper_id),
                    "request_hash": record.request_digest(),
                }
            )
            connection.execute(insert(body_selections).values(**saved.model_dump()))
            return saved, False

    def validate_all(self) -> None:
        self.history()
