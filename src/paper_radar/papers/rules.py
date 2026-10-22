"""候选集合身份与同出版者流获选规则;不依赖持久化。"""

import hashlib
import json
from dataclasses import dataclass

from paper_radar.papers.models import (
    CandidateDecision,
    CandidateInput,
    NormalizedRelation,
    ObservationInput,
)

SOURCE_PRIORITY = {"manual": 3, "publisher": 2, "registry": 1, "feed": 0}


@dataclass(frozen=True, slots=True)
class RankedObservation:
    observed_at: str
    payload_sha256: str
    parser_version: int
    fields: dict[str, tuple[str, str]]
    event_no: int = 0
    source_kind: str = "publisher"
    stream: tuple[str, str] = ("", "")


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
    highest: dict[tuple[str, tuple[str, str], str], int] = {}
    for observation in observations:
        highest[
            (observation.source_kind, observation.stream, observation.payload_sha256)
        ] = max(
            highest.get(
                (
                    observation.source_kind,
                    observation.stream,
                    observation.payload_sha256,
                ),
                0,
            ),
            observation.parser_version,
        )
    ordered = sorted(
        (
            item
            for item in observations
            if item.parser_version
            == highest[(item.source_kind, item.stream, item.payload_sha256)]
        ),
        key=lambda item: (
            SOURCE_PRIORITY[item.source_kind],
            item.event_no if item.source_kind == "manual" else 0,
            item.observed_at,
            item.payload_sha256,
            item.parser_version,
            item.stream,
        ),
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
        **(
            {
                "relations": sorted(
                    {
                        json.dumps(
                            NormalizedRelation.model_validate(relation).model_dump(
                                mode="json",
                                exclude={
                                    "raw_source_doi",
                                    "raw_target_doi",
                                    "raw_kind",
                                },
                            ),
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                        for relation in item.relations
                    }
                )
            }
            if item.relations
            else {}
        ),
        "interpretation": item.interpretation,
        "version_kind": item.version_kind,
        "target_paper_id": item.target_paper_id,
        "target_version_id": item.target_version_id,
    }
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def explain_fields(
    version_id: str, observations: tuple[RankedObservation, ...]
) -> tuple[CandidateDecision, ...]:
    """与获选权威共用输入及规则,为每个候选引用给出受控说明。"""
    winners = choose_fields(observations)
    selected = {
        reference: item
        for item in observations
        for reference in item.fields.values()
        if reference in winners.values()
    }
    highest: dict[tuple[str, tuple[str, str], str], int] = {}
    for item in observations:
        key = (item.source_kind, item.stream, item.payload_sha256)
        highest[key] = max(highest.get(key, 0), item.parser_version)
    result = []
    for item in observations:
        key = (item.source_kind, item.stream, item.payload_sha256)
        for name, reference in item.fields.items():
            if winners.get(name) == reference:
                reason = "selected"
            elif item.parser_version < highest[key]:
                reason = "superseded_interpretation"
            elif (
                name in winners
                and SOURCE_PRIORITY[item.source_kind]
                < SOURCE_PRIORITY[selected[winners[name]].source_kind]
            ):
                reason = "lower_source_priority"
            elif item.source_kind == "manual":
                reason = "earlier_manual_event"
            else:
                reason = "earlier_observation_or_stable_tiebreak"
            result.append(
                CandidateDecision.model_validate(
                    {
                        "version_id": version_id,
                        "field_name": name,
                        "candidate_id": reference[0],
                        "acquisition_id": reference[1],
                        "reason": reason,
                    }
                )
            )
    return tuple(result)
