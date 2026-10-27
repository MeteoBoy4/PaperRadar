"""冻结 Feed 到固定成员的公共服务实现;等待/HTTP 位于写事务外。"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from paper_radar.fixture_audit.acquisition_models import (
    CodeIdentity,
    Route,
    RouteExecution,
    SourceRequest,
    identity_sha256,
)
from paper_radar.fixture_audit.acquisition_policy import (
    validate_contact,
)
from paper_radar.fixture_audit.acquisition_records import load_audits
from paper_radar.fixture_audit.acquisition_service import AcquisitionService
from paper_radar.fixture_audit.audit_protection import AuditProtection
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.models import Journal
from paper_radar.fixture_audit.resume_rules import (
    can_continue,
    validate_execution_identity,
)
from paper_radar.fixture_audit.sampling_models import (
    FeedCandidate,
    FrozenFeed,
    JournalSampling,
    SamplingAuditView,
    SamplingOutcome,
    SamplingReason,
    SamplingRoute,
)
from paper_radar.fixture_audit.sampling_parser import parse_feed
from paper_radar.fixture_audit.sampling_records import load_sampling, project_journal
from paper_radar.fixture_audit.sampling_selection import (
    RecordedSelectionSources,
    evaluate_candidate,
    material_decoding,
)
from paper_radar.fixture_audit.sampling_tables import sampling_events, sampling_feeds
from paper_radar.fixture_audit.service_reads import (
    find_plan,
    read_material,
    read_snapshot,
)
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def retryable(execution: RouteExecution) -> bool:
    return can_continue(execution)


class SamplingService:
    def __init__(
        self, database: Path, data_root: Path | None, acquisitions: AcquisitionService
    ) -> None:
        self.database, self.data_root, self.acquisitions = (
            database,
            data_root,
            acquisitions,
        )

    def list_audits(self) -> tuple[SamplingAuditView, ...]:
        return read_snapshot(
            self.database,
            lambda connection: load_sampling(connection, load_audits(connection)),
            path="sampling",
        )

    def show_audit(self, plan_id: str) -> SamplingAuditView:
        return find_plan(self.list_audits(), plan_id)

    def _raw(self, execution: RouteExecution) -> bytes:
        return read_material(
            self.database, self.data_root, execution, path="sampling.material"
        )

    def _route(
        self,
        plan_id: str,
        journal: Journal,
        position: int | None,
        route: Route,
        request: SourceRequest,
        *,
        contact: str,
        guard: AuditProtection,
        continuing: bool,
        force_retry: bool = False,
    ) -> RouteExecution:
        prefix = f"sample-{journal}-{position or 'feed'}-{route}-"
        previous: RouteExecution | None = None
        executions = self.acquisitions.show_audit(plan_id).executions
        matches = [item for item in executions if item.request_key.startswith(prefix)]
        if not matches and route != "feed":
            reusable = next(
                (
                    item
                    for item in reversed(executions)
                    if item.request == request
                    and item.reason
                    in {
                        "acquired",
                        "agency_unsupported",
                        "not_found",
                        "identity_mismatch",
                    }
                ),
                None,
            )
            if reusable is not None:
                return reusable
        if matches:
            previous = matches[-1]
            if previous.request != request:
                raise FixtureError(
                    FixtureReason.REQUEST_CONFLICT, path="sampling.request"
                )
            if (
                previous.reason == "channel_not_installed"
                or not continuing
                or (not retryable(previous) and not force_retry)
            ):
                return previous
            if previous.settlement is None:
                previous = self.acquisitions.close_unknown_source(
                    previous.execution_id, protection=guard
                )
        return self.acquisitions.acquire_source(
            plan_id,
            request_key=f"{prefix}{len(matches) + 1}",
            request=request,
            contact_email=contact,
            protection=guard,
            previous_execution_id=previous.execution_id if previous else None,
        )

    def _append(self, event: SamplingOutcome) -> SamplingOutcome:
        event = event.model_copy(update={"event_id": identity_sha256(event)})
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    sampling_events.insert().values(
                        event_id=event.event_id,
                        plan_id=event.plan_id,
                        journal=event.journal,
                        previous_event_id=event.previous_event_id,
                        content_json=event.model_dump_json(),
                    )
                )
                load_sampling(connection, load_audits(connection))
                connection.commit()
            return event
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="sampling"
            ) from None
        finally:
            engine.dispose()

    def _freeze(
        self, plan_id: str, state: JournalSampling, execution: RouteExecution
    ) -> FrozenFeed:
        settlement = execution.settlement
        if (
            settlement is None
            or settlement.artifact_id is None
            or settlement.payload_sha256 is None
        ):
            raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="sampling.feed")
        total, candidates = parse_feed(
            state.journal, self._raw(execution), material_decoding(settlement)
        )
        feed = FrozenFeed(
            freeze_id="",
            plan_id=plan_id,
            journal=state.journal,
            acquisition_id=execution.execution_id,
            artifact_id=settlement.artifact_id,
            payload_sha256=settlement.payload_sha256,
            parser_version=self.acquisitions.show_audit(plan_id).plan.parser_version,
            total_candidates=total,
            candidates=candidates,
        )
        feed = feed.model_copy(update={"freeze_id": identity_sha256(feed)})
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    sampling_feeds.insert().values(
                        freeze_id=feed.freeze_id,
                        plan_id=feed.plan_id,
                        journal=feed.journal,
                        acquisition_id=feed.acquisition_id,
                        artifact_id=feed.artifact_id,
                        content_json=feed.model_dump_json(),
                    )
                )
                load_sampling(connection, load_audits(connection))
                connection.commit()
            return feed
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="sampling.feed"
            ) from None
        finally:
            engine.dispose()

    def _evaluate(
        self,
        plan_id: str,
        state: JournalSampling,
        candidate: FeedCandidate,
        *,
        contact: str,
        guard: AuditProtection,
        continuing: bool,
    ) -> SamplingOutcome:
        def acquire(route: Route, request: SourceRequest) -> RouteExecution:
            return self._route(
                plan_id,
                state.journal,
                candidate.position,
                route,
                request,
                contact=contact,
                guard=guard,
                continuing=continuing,
            )

        return evaluate_candidate(
            plan_id, state, candidate, source=acquire, read_material=self._raw
        )

    def advance(
        self,
        plan_id: str,
        *,
        contact_email: str | None,
        code_identity: CodeIdentity | None = None,
        continuing: bool = False,
        protection: AuditProtection | None = None,
    ) -> SamplingAuditView:
        contact = validate_contact(contact_email)
        view = self.show_audit(plan_id)
        validate_execution_identity(view.plan, code_identity)
        with (
            nullcontext(protection)
            if protection is not None
            else self.acquisitions.audit_execution(plan_id)
        ) as guard:
            for endpoint in view.plan.endpoints:
                state = next(
                    item
                    for item in self.show_audit(plan_id).sampling
                    if item.journal == endpoint.journal
                )
                if state.status == "complete" or (
                    state.status == "blocked_pending" and not continuing
                ):
                    continue
                if state.feed is None:
                    source = self._route(
                        plan_id,
                        endpoint.journal,
                        None,
                        "feed",
                        SourceRequest(journal=endpoint.journal, route="feed"),
                        contact=contact,
                        guard=guard,
                        continuing=continuing,
                        force_retry=continuing,
                    )
                    reason: SamplingReason | None = None
                    if source.reason != "acquired":
                        reason = "feed_unavailable"
                    else:
                        try:
                            self._freeze(plan_id, state, source)
                        except FixtureError as error:
                            if error.reason != FixtureReason.INVALID_FEED:
                                raise
                            reason = "invalid_feed"
                    if reason is not None:
                        self._append(
                            SamplingOutcome(
                                event_id="",
                                plan_id=plan_id,
                                journal=endpoint.journal,
                                previous_event_id=state.history[-1].event_id
                                if state.history
                                else None,
                                result="blocked_pending",
                                reason=reason,
                                routes=(
                                    SamplingRoute(
                                        route="feed",
                                        acquisition_id=source.execution_id,
                                        reason=source.reason or "outcome_unknown",
                                    ),
                                ),
                            )
                        )
                        continue
                while True:
                    state = next(
                        item
                        for item in self.show_audit(plan_id).sampling
                        if item.journal == endpoint.journal
                    )
                    if state.status == "complete":
                        break
                    assert state.feed is not None
                    candidate = state.feed.candidates[state.next_position - 1]
                    result = self._evaluate(
                        plan_id,
                        state,
                        candidate,
                        contact=contact,
                        guard=guard,
                        continuing=continuing,
                    )
                    self._append(result)
                    if result.result == "blocked_pending":
                        break
        return self.show_audit(plan_id)

    def validate_all(self) -> None:
        for view in self.list_audits():
            for state in view.sampling:
                if state.feed is None:
                    continue
                feed = state.feed
                source = next(
                    item
                    for item in view.executions
                    if item.execution_id == feed.acquisition_id
                )
                assert source.settlement is not None
                total, candidates = parse_feed(
                    state.journal,
                    self._raw(source),
                    material_decoding(source.settlement),
                )
                if total != feed.total_candidates or candidates != feed.candidates:
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE, path="sampling.feed"
                    )
                executions = {value.execution_id: value for value in view.executions}
                for index, event in enumerate(state.history):
                    if event.position is None:
                        continue
                    assert event.candidate is not None
                    recorded_source = RecordedSelectionSources(event.routes, executions)

                    previous = project_journal(
                        view, state.journal, feed, state.history[:index]
                    )
                    replay = evaluate_candidate(
                        view.plan.plan_id,
                        previous,
                        event.candidate,
                        source=recorded_source,
                        read_material=self._raw,
                    )
                    if recorded_source.has_unused() or replay != event.model_copy(
                        update={"event_id": ""}
                    ):
                        raise FixtureError(
                            FixtureReason.CORRUPT_REFERENCE, path="sampling.selection"
                        )
