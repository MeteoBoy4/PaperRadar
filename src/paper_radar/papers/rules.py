"""候选集合身份与同出版者流获选规则;不依赖持久化。"""

import hashlib
import json
from dataclasses import dataclass

from paper_radar.papers.models import CandidateInput, ObservationInput


@dataclass(frozen=True, slots=True)
class RankedObservation:
    observed_at: str
    payload_sha256: str
    parser_version: int
    fields: dict[str, tuple[str, str]]


def digest(fields: dict[str, CandidateInput]) -> str:
    serialized = {key: value.model_dump(mode="json") for key, value in fields.items()}
    return hashlib.sha256(
        json.dumps(
            serialized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def choose_fields(
    observations: tuple[RankedObservation, ...],
) -> dict[str, tuple[str, str]]:
    highest: dict[str, int] = {}
    for observation in observations:
        highest[observation.payload_sha256] = max(
            highest.get(observation.payload_sha256, 0), observation.parser_version
        )
    ordered = sorted(
        (
            item
            for item in observations
            if item.parser_version == highest[item.payload_sha256]
        ),
        key=lambda item: (item.observed_at, item.payload_sha256, item.parser_version),
        reverse=True,
    )
    winners: dict[str, tuple[str, str]] = {}
    for item in ordered:
        for field, candidate_id in item.fields.items():
            winners.setdefault(field, candidate_id)
    return winners


def interpretation_digest(item: ObservationInput) -> str:
    value = {
        "fields": {
            name: candidate.model_dump(mode="json")
            for name, candidate in item.fields.items()
        },
        "version_kind": item.version_kind,
        "target_paper_id": item.target_paper_id,
        "target_version_id": item.target_version_id,
    }
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
