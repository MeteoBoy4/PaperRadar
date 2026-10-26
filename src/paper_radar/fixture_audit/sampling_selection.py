"""固定选择逻辑;取得由显式接口提供,离线验证重放同一来源依据。"""

from collections.abc import Callable

from paper_radar.fixture_audit.acquisition_models import (
    Route,
    RouteExecution,
    SourceRequest,
    SourceSettlement,
)
from paper_radar.fixture_audit.acquisition_policy import normalize_request
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.sampling_models import (
    FeedCandidate,
    JournalSampling,
    SamplingOutcome,
    SamplingReason,
    SamplingRoute,
)
from paper_radar.fixture_audit.sampling_rules import (
    category_bases,
    category_result,
    duplicate_identity,
    member_identity,
)


def material_decoding(settlement: SourceSettlement) -> str:
    # #103's pending integrity fix adds the retained-content field. Until that
    # integration arrives the original non-304 source still carries http.decoding.
    retained = getattr(settlement, "content_decoding", None)
    return (
        retained
        if isinstance(retained, str)
        else settlement.http.decoding
        if settlement.http and settlement.http.decoding
        else "utf-8"
    )


def evaluate_candidate(
    plan_id: str,
    state: JournalSampling,
    candidate: FeedCandidate,
    *,
    source: Callable[[Route, SourceRequest], RouteExecution],
    read_material: Callable[[RouteExecution], bytes],
) -> SamplingOutcome:
    bases = list(
        category_bases(
            state.journal,
            "feed",
            candidate,
            acquisition_id=state.feed.acquisition_id if state.feed else None,
        )
    )
    routes: list[SamplingRoute] = []
    doi = candidate.doi
    previous_event = state.history[-1].event_id if state.history else None

    def outcome(result: str, reason: SamplingReason) -> SamplingOutcome:
        return SamplingOutcome.model_validate(
            {
                "event_id": "",
                "plan_id": plan_id,
                "journal": state.journal,
                "previous_event_id": previous_event,
                "position": candidate.position,
                "candidate": candidate,
                "result": result,
                "reason": reason,
                "doi": doi,
                "entry_id": candidate.entry_id,
                "category_bases": tuple(bases),
                "routes": tuple(routes),
                "member_id": member_identity(
                    plan_id,
                    state.journal,
                    candidate.position,
                    doi,
                    candidate.entry_id,
                )
                if result == "selected"
                else None,
            }
        )

    def acquire(route: Route, request: SourceRequest) -> RouteExecution:
        value = source(route, request)
        routes.append(
            SamplingRoute(
                route=route,
                acquisition_id=value.execution_id,
                reason=value.reason or "outcome_unknown",
            )
        )
        return value

    if candidate.identity_issue:
        return outcome(
            "excluded_deterministic",
            "identity_conflict"
            if candidate.identity_issue == "conflicting_dois"
            else "invalid_identity",
        )
    if duplicate_identity(doi, candidate.entry_id, state.entries):
        return outcome("excluded_deterministic", "duplicate")
    if doi is None and state.journal == "aies":
        if candidate.publisher_url is None:
            if candidate.publisher_link_reason:
                routes.append(
                    SamplingRoute(
                        route="publisher", reason=candidate.publisher_link_reason
                    )
                )
                return outcome("blocked_pending", "source_blocked")
        else:
            publisher = acquire(
                "publisher",
                SourceRequest(
                    journal=state.journal,
                    route="publisher",
                    publisher_url=candidate.publisher_url,
                ),
            )
            if publisher.reason == "identity_mismatch":
                return outcome("excluded_deterministic", "identity_conflict")
            if publisher.reason == "acquired" and publisher.settlement:
                doi = publisher.settlement.identity_doi
            elif publisher.reason == "not_found":
                return outcome("excluded_deterministic", "identity_unavailable")
            else:
                return outcome("blocked_pending", "source_blocked")
    if doi is None and candidate.entry_id is None:
        return outcome("excluded_deterministic", "no_stable_identifier")
    if duplicate_identity(doi, candidate.entry_id, state.entries):
        return outcome("excluded_deterministic", "duplicate")
    if doi is not None:
        agency = acquire(
            "doi_ra", SourceRequest(journal=state.journal, route="doi_ra", doi=doi)
        )
        if agency.reason == "identity_mismatch":
            return outcome("excluded_deterministic", "identity_conflict")
        if (
            agency.reason not in {"acquired", "agency_unsupported"}
            or agency.settlement is None
        ):
            return outcome("blocked_pending", "source_blocked")
        if agency.settlement.agency in ("Crossref", "DataCite"):
            registry_route: Route = (
                "registry_crossref"
                if agency.settlement.agency == "Crossref"
                else "registry_datacite"
            )
            registry = acquire(
                registry_route,
                SourceRequest(journal=state.journal, route=registry_route, doi=doi),
            )
            if registry.reason == "identity_mismatch":
                return outcome("excluded_deterministic", "identity_conflict")
            if registry.reason == "acquired" and registry.settlement:
                bases.extend(
                    category_bases(
                        state.journal,
                        registry_route,
                        candidate,
                        raw=read_material(registry),
                        acquisition_id=registry.execution_id,
                        decoding=material_decoding(registry.settlement),
                    )
                )
            elif registry.reason != "not_found":
                return outcome("blocked_pending", "source_blocked")
        if state.journal == "dqkx":
            publisher = acquire(
                "publisher",
                SourceRequest(journal=state.journal, route="publisher", doi=doi),
            )
            if publisher.reason == "identity_mismatch":
                return outcome("excluded_deterministic", "identity_conflict")
            if publisher.reason == "acquired" and publisher.settlement:
                bases.extend(
                    category_bases(
                        state.journal,
                        "publisher",
                        candidate,
                        raw=read_material(publisher),
                        acquisition_id=publisher.execution_id,
                        decoding=material_decoding(publisher.settlement),
                    )
                )
            elif publisher.reason != "not_found":
                return outcome("blocked_pending", "source_blocked")
    else:
        routes.append(
            SamplingRoute(
                route="doi_ra", reason="not_applicable_no_doi", applicable=False
            )
        )
    verdict = category_result(tuple(bases))
    if verdict == "journal_article":
        return outcome("selected", "selected")
    return outcome(
        "excluded_deterministic",
        "category_conflict"
        if verdict == "conflict"
        else "not_journal_article"
        if verdict == "non_journal_article"
        else "category_unknown",
    )


class RecordedSelectionSources:
    """将一项旧事件的确切来源序列提供给只读重放。"""

    def __init__(
        self,
        references: tuple[SamplingRoute, ...],
        executions: dict[str, RouteExecution],
    ) -> None:
        self.references = iter(
            tuple(item for item in references if item.acquisition_id is not None)
        )
        self.executions = executions

    def __call__(self, route: Route, request: SourceRequest) -> RouteExecution:
        reference = next(self.references, None)
        if reference is None or reference.acquisition_id is None:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="sampling.route")
        execution = self.executions[reference.acquisition_id]
        if reference.route != route or execution.request != normalize_request(request):
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="sampling.identity"
            )
        return execution

    def has_unused(self) -> bool:
        return next(self.references, None) is not None
