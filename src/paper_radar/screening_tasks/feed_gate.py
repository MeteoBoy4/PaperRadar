"""组合value登记的冻结前置引用;和预算/语言依据同一事务。"""

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy import Connection, select

from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.storage.schema import metadata

proofs = sa.Table(
    "feed_value_registrations",
    metadata,
    sa.Column("request_key", sa.String(64), primary_key=True),
    sa.Column(
        "receipt_id",
        sa.String(64),
        sa.ForeignKey("screening_requests.receipt_id"),
        nullable=False,
    ),
    sa.Column("basis_json", sa.Text, nullable=False),
    sa.Column("basis_sha256", sa.String(64), nullable=False),
)


@dataclass(frozen=True)
class FeedGate:
    request_key: str
    metadata_request_key: str
    boundary_success_id: str
    purpose: Literal["production", "test"]
    version_id: str
    revision_no: int
    boundary_fingerprint: str


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def request_key(raw: object, metadata_key: str, boundary_id: str, purpose: str) -> str:
    try:
        return sha(encode([raw, metadata_key, boundary_id, purpose]))
    except (ValueError, TypeError):
        raise TaskError(TaskReason.INVALID_REQUEST) from None


def find(connection: Connection, key: str) -> dict[str, Any] | None:
    row = (
        connection.execute(select(proofs).where(proofs.c.request_key == key))
        .mappings()
        .first()
    )
    if row is None:
        return None
    if sha(row["receipt_id"] + row["basis_json"]) != row["basis_sha256"]:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    try:
        basis = json.loads(row["basis_json"])
        gate = FeedGate(**basis)
        if (
            gate.request_key != key
            or gate.purpose not in {"production", "test"}
            or type(gate.revision_no) is not int
            or gate.revision_no < 1
            or not all(
                type(value) is str
                for value in (
                    gate.metadata_request_key,
                    gate.boundary_success_id,
                    gate.version_id,
                    gate.boundary_fingerprint,
                )
            )
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
    return {"receipt_id": row["receipt_id"], **basis}


def retain(connection: Connection, gate: FeedGate, receipt_id: str) -> None:
    previous = find(connection, gate.request_key)
    if previous:
        if previous["receipt_id"] != receipt_id:
            raise TaskError(TaskReason.REQUEST_CONFLICT)
        return
    basis = encode(asdict(gate))
    connection.execute(
        proofs.insert().values(
            request_key=gate.request_key,
            receipt_id=receipt_id,
            basis_json=basis,
            basis_sha256=sha(receipt_id + basis),
        )
    )
