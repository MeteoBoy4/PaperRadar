"""冻结适用路线、逐字段 A6 仲裁及真实分母投影。"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from paper_radar.fixture_audit.abstract_models import (
    AbstractAuditView,
    CandidateDecision,
    Fraction,
    JournalSummary,
    MatrixRow,
    MemberAbstract,
    RouteSummary,
)
from paper_radar.fixture_audit.acquisition_models import SourceRequest, identity_sha256
from paper_radar.fixture_audit.sampling_models import SamplingAuditView, SamplingMember
from paper_radar.papers.rules import SOURCE_PRIORITY, RankedObservation, choose_fields


def applicable_requests(
    view: SamplingAuditView,
) -> tuple[tuple[SamplingMember, SourceRequest], ...]:
    result: list[tuple[SamplingMember, SourceRequest]] = []
    for state in view.sampling:
        for member in state.members:
            event = next(
                value
                for value in state.history
                if value.event_id == member.selection_event_id
            )
            result.append((member, SourceRequest(journal=member.journal, route="feed")))
            if member.doi:
                result.append(
                    (
                        member,
                        SourceRequest(
                            journal=member.journal, route="doi_ra", doi=member.doi
                        ),
                    )
                )
                agency_id = next(
                    (
                        value.acquisition_id
                        for value in event.routes
                        if value.route == "doi_ra"
                    ),
                    None,
                )
                execution = next(
                    (
                        value
                        for value in view.executions
                        if value.execution_id == agency_id
                    ),
                    None,
                )
                agency = (
                    execution.settlement.agency
                    if execution and execution.settlement
                    else None
                )
                if agency in {"Crossref", "DataCite"}:
                    result.append(
                        (
                            member,
                            SourceRequest(
                                journal=member.journal,
                                route="registry_crossref"
                                if agency == "Crossref"
                                else "registry_datacite",
                                doi=member.doi,
                            ),
                        )
                    )
            publisher_url = event.candidate.publisher_url if event.candidate else None
            if (member.journal == "aies" and publisher_url) or (
                member.journal != "aies" and member.doi
            ):
                for channel in ("http", "browser_render"):
                    result.append(
                        (
                            member,
                            SourceRequest.model_validate(
                                dict(
                                    journal=member.journal,
                                    route="publisher",
                                    doi=None
                                    if member.journal == "aies"
                                    else member.doi,
                                    publisher_url=publisher_url,
                                    channel=channel,
                                )
                            ),
                        )
                    )
    return tuple(result)


def row_key(member_id: str, request: SourceRequest) -> tuple[str, str, str, str]:
    return (
        member_id,
        request.route,
        request.acquisition_strategy_version,
        request.channel,
    )


def matrix_request_key(member_id: str, request: SourceRequest) -> str:
    return f"matrix-{member_id[:32]}-{request.route}-{request.channel}"


def retained_acquisition(
    view: SamplingAuditView, member: SamplingMember, request: SourceRequest
) -> str | None:
    """冻结选样已取得的材料引用优先于新的矩阵执行。"""
    state = next(value for value in view.sampling if value.journal == member.journal)
    event = next(
        value for value in state.history if value.event_id == member.selection_event_id
    )
    prior = (
        state.feed.acquisition_id
        if request.route == "feed" and state.feed
        else next(
            (
                value.acquisition_id
                for value in event.routes
                if value.route == request.route
            ),
            None,
        )
        if request.channel == "http"
        else None
    )
    return next(
        (
            value.execution_id
            for value in view.executions
            if value.execution_id == prior and value.request == request
        ),
        None,
    )


def pending_row(
    view: SamplingAuditView, member: SamplingMember, request: SourceRequest
) -> MatrixRow:
    key = matrix_request_key(member.member_id, request)
    execution = next(
        (item for item in view.executions if item.request_key == key), None
    )
    row = MatrixRow(
        row_id="",
        plan_id=view.plan.plan_id,
        member_id=member.member_id,
        request=request,
        acquisition_id=execution.execution_id if execution else None,
        reason="outcome_unknown"
        if execution and execution.settlement is None
        else "channel_not_installed"
        if request.channel != "http"
        else "not_attempted",
    )
    return row.model_copy(update={"row_id": identity_sha256(row)})


def project(
    view: SamplingAuditView, stored: tuple[MatrixRow, ...]
) -> AbstractAuditView:
    by_key = {row_key(row.member_id, row.request): row for row in stored}
    rows = tuple(
        by_key.get(row_key(member.member_id, request))
        or pending_row(view, member, request)
        for member, request in applicable_requests(view)
    )
    executions = {value.execution_id: value for value in view.executions}
    members = []
    for state in view.sampling:
        for member in state.members:
            own = [row for row in rows if row.member_id == member.member_id]
            observations = tuple(
                RankedObservation(
                    observed_at=row.observed_at or "",
                    payload_sha256=row.payload_sha256 or "",
                    parser_version=1,
                    fields={
                        candidate.field: (
                            candidate.candidate_id,
                            row.acquisition_id or "",
                        )
                        for candidate in row.candidates
                    },
                    source_kind=candidate_source(row),
                    stream=(
                        view.plan.plan_id,
                        f"{member.member_id}:{row.request.route}:{row.request.acquisition_strategy_version}:{row.request.channel}",
                    ),
                )
                for row in own
                if row.candidates
            )
            settled = all(
                row.reason != "not_attempted"
                and row.acquisition_id
                and executions[row.acquisition_id].settlement is not None
                for row in own
            )
            winners = choose_fields(observations) if settled else {}
            candidates = {
                candidate.candidate_id: candidate
                for row in own
                for candidate in row.candidates
            }
            abstract_id = winners.get("abstract", (None, ""))[0]
            title_id = winners.get("title", (None, ""))[0]
            winner = candidates.get(abstract_id) if abstract_id else None
            decisions = tuple(
                CandidateDecision(
                    candidate_id=reference[0],
                    acquisition_id=reference[1],
                    field=candidates[reference[0]].field,
                    selected=winners.get(name) == reference,
                    reason="selected"
                    if winners.get(name) == reference
                    else "lower_source_priority"
                    if SOURCE_PRIORITY[item.source_kind]
                    < SOURCE_PRIORITY[candidates[winners[name][0]].source_kind]
                    else "earlier_observation_or_stable_tiebreak",
                )
                for item in observations
                for name, reference in item.fields.items()
                if settled
            )
            registry_reason = (
                "not_applicable_no_doi"
                if member.doi is None
                else "applicable"
                if any(row.request.route.startswith("registry_") for row in own)
                else "agency_unsupported"
                if any(row.reason == "agency_unsupported" for row in own)
                else "agency_unknown"
            )
            publisher_reason = (
                "applicable"
                if any(row.request.route == "publisher" for row in own)
                else "not_applicable_no_doi"
                if member.journal != "aies" and not member.doi
                else "target_unknown"
            )
            members.append(
                MemberAbstract.model_validate(
                    dict(
                        member_id=member.member_id,
                        journal=member.journal,
                        routes_settled=settled,
                        final_title_candidate_id=title_id,
                        final_abstract_candidate_id=abstract_id,
                        final_title_source=candidates[title_id].source_kind
                        if title_id
                        else None,
                        final_abstract_source=winner.source_kind if winner else None,
                        priority_truncation_conflict=bool(
                            winner
                            and winner.suspected_truncated
                            and any(
                                value.field == "abstract"
                                and not value.suspected_truncated
                                and SOURCE_PRIORITY[value.source_kind]
                                < SOURCE_PRIORITY[winner.source_kind]
                                for value in candidates.values()
                            )
                        ),
                        decisions=decisions,
                        registry_applicability=registry_reason,
                        publisher_applicability=publisher_reason,
                    )
                )
            )
    summaries: list[RouteSummary] = []
    journals: list[JournalSummary] = []
    executions = {value.execution_id: value for value in view.executions}
    for state in view.sampling:
        own = [row for row in rows if row.request.journal == state.journal]
        keys = {(row.request.route, row.request.channel) for row in own}
        keys |= {("publisher", "official_api"), ("publisher", "repository")}
        for route, channel in sorted(keys):
            group = [
                row
                for row in own
                if (row.request.route, row.request.channel) == (route, channel)
            ]
            uninstalled = sum(row.reason == "channel_not_installed" for row in group)
            attempted = sum(
                row.acquisition_id is not None
                and row.reason not in {"channel_not_installed", "not_attempted"}
                for row in group
            )
            nonempty = sum(
                any(candidate.field == "abstract" for candidate in row.candidates)
                for row in group
            )
            denominator = 0 if route == "doi_ra" else len(group) - uninstalled
            summaries.append(
                RouteSummary.model_validate(
                    dict(
                        journal=state.journal,
                        route=route,
                        strategy_version=view.plan.acquisition_strategy_version,
                        channel=channel,
                        applicable=len(group),
                        executor_delivered=channel == "http",
                        attempted=attempted,
                        not_attempted=sum(
                            row.reason == "not_attempted" for row in group
                        ),
                        channel_not_installed=uninstalled,
                        valid_records=sum(row.valid_record for row in group),
                        nonempty_abstracts=nonempty,
                        suspected_truncated=sum(
                            any(
                                candidate.field == "abstract"
                                and candidate.suspected_truncated
                                for candidate in row.candidates
                            )
                            for row in group
                        ),
                        errors=sum(
                            row.reason
                            in {"unrecognized_page_shape", "invalid_response"}
                            or bool(
                                row.acquisition_id
                                and executions[row.acquisition_id].is_failure
                            )
                            for row in group
                        ),
                        abstract_coverage=Fraction(
                            numerator=nonempty,
                            denominator=denominator,
                            ratio=nonempty / denominator if denominator else None,
                            zero_denominator=None if denominator else "not_applicable",
                        ),
                        channel_status="not_applicable"
                        if not group
                        else "channel_not_installed"
                        if uninstalled == len(group)
                        else "installed",
                    )
                )
            )
        dates = [
            entry.candidate.published_value
            for entry in state.entries
            if entry.result == "selected"
            and entry.candidate
            and entry.candidate.published_value
        ]
        own_members = [member for member in members if member.journal == state.journal]
        journals.append(
            JournalSummary(
                journal=state.journal,
                target=state.target_count,
                selected=len(state.members),
                considered=state.considered,
                excluded=sum(
                    entry.result == "excluded_deterministic" for entry in state.entries
                ),
                unknown=sum(
                    entry.reason == "category_unknown" for entry in state.entries
                ),
                conflicts=sum(
                    entry.reason in {"category_conflict", "identity_conflict"}
                    for entry in state.entries
                ),
                shortfall=state.shortfall,
                sampling_status=state.status,
                date_start=min(dates) if dates else None,
                date_end=max(dates) if dates else None,
                unknown_dates=len(state.members) - len(dates),
                priority_truncation_conflicts=sum(
                    member.priority_truncation_conflict for member in own_members
                ),
                final_abstract_sources=dict(
                    Counter(
                        (member.final_abstract_source or "none")
                        if member.routes_settled
                        else "pending"
                        for member in own_members
                    )
                ),
                registry_not_applicable_no_doi=sum(
                    member.registry_applicability == "not_applicable_no_doi"
                    for member in own_members
                ),
                registry_agency_unsupported=sum(
                    member.registry_applicability == "agency_unsupported"
                    for member in own_members
                ),
                registry_agency_unknown=sum(
                    member.registry_applicability == "agency_unknown"
                    for member in own_members
                ),
                publisher_target_unknown=sum(
                    member.publisher_applicability == "target_unknown"
                    for member in own_members
                ),
            )
        )
    return AbstractAuditView(
        **view.model_dump(),
        status="complete"
        if all(state.status == "complete" for state in view.sampling)
        and all(
            row.reason != "not_attempted"
            and row.acquisition_id
            and executions[row.acquisition_id].settlement is not None
            for row in rows
        )
        else "partial",
        matrix=rows,
        members=tuple(members),
        route_summaries=tuple(summaries),
        journal_summaries=tuple(journals),
        physical_http_requests=sum(
            value.physical_requests or 0 for value in view.executions
        ),
        physical_http_unknown_executions=sum(
            value.physical_requests is None for value in view.executions
        ),
        http_redirects=sum(
            value.settlement.http.redirect_count
            for value in view.executions
            if value.settlement and value.settlement.http
        ),
        http_retries=sum(
            value.settlement.http.retry_count
            for value in view.executions
            if value.settlement and value.settlement.http
        ),
    )


def candidate_source(row: MatrixRow) -> Literal["feed", "registry", "publisher"]:
    return row.candidates[0].source_kind
