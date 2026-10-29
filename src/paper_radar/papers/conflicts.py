"""冲突请求的独立证据;不写成功发现、候选或关系。"""

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, select

from paper_radar.papers.conflict_tables import conflicts
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import (
    ConflictKind,
    ConflictView,
    ObservationInput,
    WriteResult,
)
from paper_radar.papers.tables import feed_entries, identifiers, versions
from paper_radar.storage.artifacts import ArtifactStore


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def request(item: ObservationInput) -> tuple[str, str, str]:
    assertion = canonical(item.model_dump(mode="json", exclude={"payload"}))
    payload_hash = hashlib.sha256(item.payload).hexdigest()
    return sha(assertion + payload_hash), assertion, payload_hash


def result(row: dict[str, Any]) -> WriteResult:
    return WriteResult(
        status="rejected",
        reason=PaperReason.IDENTITY_CONFLICT,
        conflict=row["conflict"],
        conflict_id=row["conflict_id"],
    )


def replay(connection: Connection, item: ObservationInput) -> WriteResult | None:
    row = (
        connection.execute(
            select(conflicts).where(conflicts.c.request_sha256 == request(item)[0])
        )
        .mappings()
        .first()
    )
    if row:
        checked = dict(row)
        identity = checked.pop("conflict_id")
        if identity != sha(canonical(checked)):
            raise PaperError(PaperReason.CORRUPT_REFERENCE, path="identity_conflict")
        return result(dict(row))
    return None


def retain(
    connection: Connection,
    item: ObservationInput,
    artifact_id: str | None,
    category: ConflictKind,
) -> WriteResult:
    if artifact_id is None:
        return WriteResult(
            status="rejected", reason=PaperReason.IDENTITY_CONFLICT, conflict=category
        )
    key, assertion, payload_hash = request(item)
    previous = replay(connection, item)
    if previous:
        return previous
    known: set[str] = set()
    if item.target_version_id:
        known.update(
            connection.execute(
                select(versions.c.version_id).where(
                    versions.c.version_id == item.target_version_id
                )
            ).scalars()
        )
    if item.feed_id:
        known.update(
            connection.execute(
                select(feed_entries.c.version_id).where(
                    feed_entries.c.feed_id == item.feed_id,
                    feed_entries.c.entry_id == item.entry_id,
                )
            ).scalars()
        )
    if item.doi:
        from paper_radar.papers.doi import normalize_doi

        known.update(
            connection.execute(
                select(identifiers.c.version_id).where(
                    identifiers.c.normalized_value == normalize_doi(item.doi)
                )
            ).scalars()
        )
    row = dict(
        request_sha256=key,
        assertion_json=assertion,
        payload_sha256=payload_hash,
        artifact_id=artifact_id,
        conflict=category,
        version_ids_json=canonical(sorted(known)),
    )
    row["conflict_id"] = sha(canonical(row))
    connection.execute(conflicts.insert().values(**row))
    connection.commit()
    return result(row)


def read_all(
    connection: Connection,
    database: Path,
    data_root: Path | None,
    *,
    conflict_id: str | None = None,
    feed_id: str | None = None,
    entry_id: str | None = None,
    paper_id: str | None = None,
) -> tuple[ConflictView, ...]:
    output = []
    for source in connection.execute(select(conflicts)).mappings():
        row = dict(source)
        identity = row.pop("conflict_id")
        try:
            if identity != sha(canonical(row)):
                raise ValueError
            assertion = json.loads(row["assertion_json"])
            known = tuple(json.loads(row["version_ids_json"]))
            if row["request_sha256"] != sha(
                row["assertion_json"] + row["payload_sha256"]
            ):
                raise ValueError
            for version_id in known:
                if (
                    connection.execute(
                        select(versions.c.version_id).where(
                            versions.c.version_id == version_id
                        )
                    ).scalar()
                    is None
                ):
                    raise ValueError
            if data_root is None:
                raise ValueError
            payload = ArtifactStore(database, data_root).read_artifact(
                row["artifact_id"]
            )["payload"]
            if hashlib.sha256(payload).hexdigest() != row["payload_sha256"]:
                raise ValueError
            if conflict_id is not None and identity != conflict_id:
                continue
            if feed_id is not None and assertion["feed_id"] != feed_id:
                continue
            if entry_id is not None and assertion["entry_id"] != entry_id:
                continue
            if (
                paper_id is not None
                and not connection.execute(
                    select(versions.c.version_id).where(
                        versions.c.paper_id == paper_id,
                        versions.c.version_id.in_(known),
                    )
                ).first()
            ):
                continue
            output.append(
                ConflictView(
                    conflict_id=identity,
                    conflict=row["conflict"],
                    artifact_id=row["artifact_id"],
                    payload_sha256=row["payload_sha256"],
                    source_kind=assertion["source_kind"],
                    feed_id=assertion["feed_id"],
                    entry_id=assertion["entry_id"],
                    parser_version=assertion["parser_version"],
                    observed_at=assertion["observed_at"],
                    raw_doi=assertion["doi"],
                    version_ids=known,
                )
            )
        except (ValueError, KeyError, TypeError):
            raise PaperError(
                PaperReason.CORRUPT_REFERENCE, path="identity_conflict"
            ) from None
    return tuple(output)
