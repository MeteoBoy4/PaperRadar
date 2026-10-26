"""由冻结来源和事件链派生选样视图,不以登记时间选择当前项。"""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import Connection, select

from paper_radar.fixture_audit.acquisition_models import (
    CATEGORY_RULES_VERSION,
    SAMPLING_RULES_VERSION,
    AuditView,
    identity_sha256,
)
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.models import Journal
from paper_radar.fixture_audit.sampling_models import (
    FrozenFeed,
    JournalSampling,
    SamplingAuditView,
    SamplingMember,
    SamplingOutcome,
)
from paper_radar.fixture_audit.sampling_rules import (
    category_result,
    duplicate_identity,
    member_identity,
)
from paper_radar.fixture_audit.sampling_tables import sampling_events, sampling_feeds


def project_journal(
    view: AuditView,
    journal: Journal,
    feed: FrozenFeed | None,
    history: tuple[SamplingOutcome, ...],
) -> JournalSampling:
    latest: dict[int, SamplingOutcome] = {}
    for event in history:
        if event.position is not None:
            latest[event.position] = event
    entries = tuple(latest[position] for position in sorted(latest))
    finals = tuple(event for event in entries if event.result != "blocked_pending")
    members = tuple(
        SamplingMember(
            member_id=event.member_id or "",
            journal=journal,
            position=event.position or 0,
            doi=event.doi,
            entry_id=event.entry_id,
            feed_freeze_id=feed.freeze_id if feed else "",
            selection_event_id=event.event_id,
        )
        for event in finals
        if event.result == "selected"
    )
    complete = feed is not None and (
        len(members) >= view.plan.target_count
        or len(finals) >= min(50, feed.total_candidates)
    )
    blocked = bool(history and history[-1].result == "blocked_pending")
    status = (
        "complete"
        if complete
        else "blocked_pending"
        if blocked
        else "selecting"
        if feed
        else "feed_pending"
    )
    return JournalSampling.model_validate(
        {
            "journal": journal,
            "feed": feed,
            "status": status,
            "next_position": len(finals) + 1,
            "target_count": view.plan.target_count,
            "total_candidates": feed.total_candidates if feed else None,
            "considered": len(entries),
            "shortfall": view.plan.target_count - len(members) if complete else None,
            "members": members,
            "entries": entries,
            "history": history,
        }
    )


def load_sampling(
    connection: Connection, views: tuple[AuditView, ...]
) -> tuple[SamplingAuditView, ...]:
    try:
        indexed = {view.plan.plan_id: view for view in views}
        feeds: dict[tuple[str, Journal], FrozenFeed] = {}
        executions = {
            value.execution_id: value for view in views for value in view.executions
        }
        for row in connection.execute(select(sampling_feeds)).mappings():
            frozen = FrozenFeed.model_validate_json(row["content_json"])
            key = frozen.plan_id, frozen.journal
            source = executions.get(frozen.acquisition_id)
            if (
                frozen.plan_id not in indexed
                or key in feeds
                or frozen.freeze_id != row["freeze_id"]
                or frozen.plan_id != row["plan_id"]
                or frozen.journal != row["journal"]
                or frozen.acquisition_id != row["acquisition_id"]
                or frozen.artifact_id != row["artifact_id"]
                or identity_sha256(frozen.model_copy(update={"freeze_id": ""}))
                != frozen.freeze_id
                or frozen.model_dump_json() != row["content_json"]
                or source is None
                or source.plan_id != frozen.plan_id
                or source.request.journal != frozen.journal
                or source.request.route != "feed"
                or source.settlement is None
                or source.reason != "acquired"
                or source.settlement.artifact_id != frozen.artifact_id
                or source.settlement.payload_sha256 != frozen.payload_sha256
                or frozen.parser_version != indexed[frozen.plan_id].plan.parser_version
                or len(frozen.candidates) != min(50, frozen.total_candidates)
                or [candidate.position for candidate in frozen.candidates]
                != list(range(1, len(frozen.candidates) + 1))
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="sampling.feed"
                )
            feeds[key] = frozen
        histories: dict[tuple[str, Journal], list[SamplingOutcome]] = {}
        for row in connection.execute(
            select(sampling_events).order_by(sampling_events.c.event_no)
        ).mappings():
            event = SamplingOutcome.model_validate_json(row["content_json"])
            key = event.plan_id, event.journal
            history = histories.setdefault(key, [])
            if (
                event.plan_id not in indexed
                or event.plan_id != row["plan_id"]
                or event.journal != row["journal"]
                or event.event_id != row["event_id"]
                or event.previous_event_id != row["previous_event_id"]
                or event.previous_event_id
                != (history[-1].event_id if history else None)
                or identity_sha256(event.model_copy(update={"event_id": ""}))
                != event.event_id
                or event.model_dump_json() != row["content_json"]
                or event.sampling_rules_version != SAMPLING_RULES_VERSION
                or event.category_rules_version != CATEGORY_RULES_VERSION
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="sampling.event"
                )
            feed = feeds.get(key)
            for route in event.routes:
                if route.acquisition_id is not None:
                    source = executions.get(route.acquisition_id)
                    if (
                        source is None
                        or source.plan_id != event.plan_id
                        or source.request.journal != event.journal
                        or source.request.route != route.route
                        or route.reason != (source.reason or "outcome_unknown")
                    ):
                        raise FixtureError(
                            FixtureReason.CORRUPT_REFERENCE, path="sampling.route"
                        )
            if event.position is not None:
                if (
                    feed is None
                    or event.position > len(feed.candidates)
                    or event.candidate != feed.candidates[event.position - 1]
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="sampling.candidate"
                    )
                previous = project_journal(
                    indexed[event.plan_id], event.journal, feed, tuple(history)
                )
                if (
                    previous.status == "complete"
                    or event.position != previous.next_position
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="sampling.position"
                    )
                if event.result == "selected" and (
                    event.reason != "selected"
                    or category_result(event.category_bases) != "journal_article"
                    or (event.doi is None and event.entry_id is None)
                    or duplicate_identity(event.doi, event.entry_id, previous.entries)
                    or event.member_id
                    != member_identity(
                        event.plan_id,
                        event.journal,
                        event.position,
                        event.doi,
                        event.entry_id,
                    )
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="sampling.member"
                    )
                if event.result != "selected" and event.member_id is not None:
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="sampling.member"
                    )
            elif (
                event.result != "blocked_pending"
                or event.reason not in {"feed_unavailable", "invalid_feed"}
                or event.candidate is not None
                or event.member_id is not None
                or len(event.routes) != 1
                or event.routes[0].route != "feed"
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="sampling.feed_event"
                )
            history.append(event)
        return tuple(
            SamplingAuditView(
                plan=view.plan,
                executions=view.executions,
                sampling=tuple(
                    project_journal(
                        view,
                        endpoint.journal,
                        feeds.get((view.plan.plan_id, endpoint.journal)),
                        tuple(histories.get((view.plan.plan_id, endpoint.journal), [])),
                    )
                    for endpoint in view.plan.endpoints
                ),
            )
            for view in views
        )
    except (ValidationError, TypeError, ValueError):
        raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="sampling") from None
