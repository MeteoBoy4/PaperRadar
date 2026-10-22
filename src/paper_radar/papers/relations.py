"""权威版本关系归一化;无持久化依赖。"""

from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import (
    NormalizedRelation,
    ObservationInput,
    RelationInput,
    RelationKind,
    RelationState,
)
from paper_radar.papers.text_rules import normalize_text


def normalize_relations(item: ObservationInput) -> tuple[NormalizedRelation, ...]:
    if item.relations and item.source_kind not in {"publisher", "registry"}:
        raise PaperError(PaperReason.UNSUPPORTED_RELATION, path="relations")
    normalized = {}
    for value in item.relations:
        if isinstance(value, dict) and "kind" not in value:
            raise PaperError(PaperReason.UNSUPPORTED_RELATION, path="relations.kind")
        relation = RelationInput.model_validate(
            {key: getattr(value, key) for key in RelationInput.model_fields}
            if isinstance(value, NormalizedRelation)
            else value
        )
        raw_kind: RelationKind
        if relation.kind == "is-preprint-of":
            raw_kind = "is-preprint-of"
        elif relation.kind == "has-preprint":
            raw_kind = "has-preprint"
        else:
            raise PaperError(PaperReason.UNSUPPORTED_RELATION, path="relations.kind")
        source, target = (
            normalize_doi(relation.source_doi),
            normalize_doi(relation.target_doi),
        )
        pre, journal = (
            (source, target) if relation.kind == "is-preprint-of" else (target, source)
        )
        locator = normalize_text(relation.locator)
        if not locator or len(locator.encode()) > 2048 or pre == journal:
            raise PaperError(PaperReason.INVALID_RELATION, path="relations")
        doi = normalize_doi(item.doi) if item.doi else None
        if doi not in {pre, journal} or (doi == pre) != (
            item.version_kind == "preprint"
        ):
            raise PaperError(PaperReason.INVALID_RELATION, path="relations.target")
        normalized[
            (
                pre,
                journal,
                locator,
                relation.source_doi,
                relation.target_doi,
                relation.kind,
            )
        ] = NormalizedRelation(
            kind="is-preprint-of",
            source_doi=pre,
            target_doi=journal,
            locator=locator,
            raw_source_doi=relation.source_doi,
            raw_target_doi=relation.target_doi,
            raw_kind=raw_kind,
        )
    return tuple(normalized[key] for key in sorted(normalized))


def relation_state(
    preprint_paper_id: str | None, journal_paper_id: str | None
) -> RelationState:
    if preprint_paper_id is None or journal_paper_id is None:
        return "endpoint_missing"
    return "effective" if preprint_paper_id == journal_paper_id else "requires_merge"


def relation_signature(item: ObservationInput) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            {
                (relation.source_doi, relation.target_doi, relation.locator)
                for value in item.relations
                for relation in (NormalizedRelation.model_validate(value),)
            }
        )
    )
