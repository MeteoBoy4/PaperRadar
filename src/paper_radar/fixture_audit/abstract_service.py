"""摘要矩阵执行和历史解释;外部取得与短事务分开。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.fixture_audit.abstract_models import (
    AbstractAuditView,
    AbstractCandidate,
    ExcludedBlock,
    MatrixRow,
)
from paper_radar.fixture_audit.abstract_parser import parse_material
from paper_radar.fixture_audit.abstract_records import load_abstracts as load_abstracts
from paper_radar.fixture_audit.abstract_rules import (
    applicable_requests,
    matrix_request_key,
    retained_acquisition,
)
from paper_radar.fixture_audit.abstract_tables import abstract_rows
from paper_radar.fixture_audit.acquisition_models import (
    CodeIdentity,
    RouteExecution,
    SourceRequest,
    identity_sha256,
)
from paper_radar.fixture_audit.acquisition_policy import validate_contact
from paper_radar.fixture_audit.acquisition_records import load_audits
from paper_radar.fixture_audit.acquisition_service import AcquisitionService
from paper_radar.fixture_audit.audit_protection import AuditProtection
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.resume_rules import (
    can_continue,
    validate_execution_identity,
)
from paper_radar.fixture_audit.sampling_models import SamplingAuditView, SamplingMember
from paper_radar.fixture_audit.sampling_records import load_sampling
from paper_radar.fixture_audit.sampling_service import SamplingService
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


class AbstractService:
    def __init__(
        self,
        database: Path,
        data_root: Path | None,
        acquisitions: AcquisitionService,
        sampling: SamplingService,
    ) -> None:
        self.database, self.data_root, self.acquisitions, self.sampling = (
            database,
            data_root,
            acquisitions,
            sampling,
        )

    def list_audits(self) -> tuple[AbstractAuditView, ...]:
        return read_snapshot(
            self.database,
            lambda connection: load_abstracts(
                connection, load_sampling(connection, load_audits(connection))
            ),
            path="abstract.matrix",
        )

    def show_audit(self, plan_id: str) -> AbstractAuditView:
        return find_plan(self.list_audits(), plan_id)

    def _raw(self, execution: RouteExecution) -> bytes:
        return read_material(
            self.database, self.data_root, execution, path="abstract.material"
        )

    def _interpret(
        self,
        view: SamplingAuditView,
        member: SamplingMember,
        request: SourceRequest,
        execution: RouteExecution,
    ) -> tuple[MatrixRow, dict[str, str]]:
        settlement = execution.settlement
        assert settlement is not None
        candidates: tuple[AbstractCandidate, ...] = ()
        excluded: tuple[ExcludedBlock, ...] = ()
        texts: dict[str, str] = {}
        reason = settlement.reason
        valid = False
        if settlement.artifact_id is not None:
            state = next(
                state for state in view.sampling if state.journal == member.journal
            )
            event = next(
                event
                for event in state.history
                if event.event_id == member.selection_event_id
            )
            assert event.candidate is not None
            try:
                candidates, excluded, texts, recognized = parse_material(
                    request,
                    self._raw(execution),
                    decoding=settlement.content_decoding or "utf-8",
                    acquisition_id=execution.execution_id,
                    entry_locator=event.candidate.entry_locator
                    if request.route == "feed"
                    else None,
                )
            except (ValueError, TypeError, KeyError, LookupError):
                reason = "invalid_response"
            else:
                valid = True
                if request.route == "publisher" and (
                    not member.doi or settlement.identity_doi != member.doi
                ):
                    candidates, texts = (), {}
                    reason, valid = "identity_mismatch", False
                elif request.route == "publisher" and not recognized:
                    candidates, texts = (), {}
                    reason = "unrecognized_page_shape"
                else:
                    reason = (
                        "acquired"
                        if any(
                            candidate.field == "abstract" for candidate in candidates
                        )
                        else "record_without_abstract"
                    )
        row = MatrixRow(
            row_id="",
            plan_id=view.plan.plan_id,
            member_id=member.member_id,
            request=request,
            acquisition_id=execution.execution_id,
            reason=reason,
            valid_record=valid,
            observed_at=settlement.settled_at,
            payload_sha256=settlement.payload_sha256,
            candidates=candidates,
            excluded_blocks=excluded,
        )
        return row.model_copy(update={"row_id": identity_sha256(row)}), texts

    def _append(self, row: MatrixRow) -> None:
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                connection.execute(
                    abstract_rows.insert().values(
                        row_id=row.row_id,
                        generation=row.generation,
                        previous_row_id=row.previous_row_id,
                        plan_id=row.plan_id,
                        member_id=row.member_id,
                        route=row.request.route,
                        strategy_version=row.request.acquisition_strategy_version,
                        channel=row.request.channel,
                        acquisition_id=row.acquisition_id,
                        content_json=row.model_dump_json(),
                    )
                )
                load_abstracts(
                    connection, load_sampling(connection, load_audits(connection))
                )
                connection.commit()
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
            ) from None
        finally:
            engine.dispose()

    def run(
        self,
        *,
        contact_email: str | None,
        target_count: int = 5,
        plan_key: str | None = None,
        code_identity: CodeIdentity | None = None,
    ) -> AbstractAuditView:
        contact = validate_contact(contact_email)
        plan = self.acquisitions.create_audit_plan(
            contact_email=contact,
            target_count=target_count,
            plan_key=plan_key,
            code_identity=code_identity,
        )
        self.acquisitions.log.bind(plan_id=plan.plan_id)
        with self.acquisitions.audit_execution(plan.plan_id) as guard:
            view = self.sampling.advance(
                plan.plan_id,
                contact_email=contact,
                code_identity=code_identity,
                protection=guard,
            )
            self.advance_matrix(view, contact=contact, guard=guard, continuing=False)
        return self.show_audit(plan.plan_id)

    def resume(
        self,
        plan_id: str,
        *,
        contact_email: str | None,
        code_identity: CodeIdentity | None = None,
    ) -> AbstractAuditView:
        contact = validate_contact(contact_email)
        try:
            view = self.show_audit(plan_id)
        except FixtureError as error:
            if error.reason == FixtureReason.UNSUPPORTED_HISTORY:
                raise FixtureError(
                    FixtureReason.PLAN_IDENTITY_MISMATCH, path="plan_versions"
                ) from None
            raise
        validate_execution_identity(view.plan, code_identity)
        with self.acquisitions.audit_execution(plan_id) as guard:
            sampled = self.sampling.advance(
                plan_id,
                contact_email=contact,
                code_identity=code_identity,
                continuing=True,
                protection=guard,
            )
            self.advance_matrix(sampled, contact=contact, guard=guard, continuing=True)
        return self.show_audit(plan_id)

    def advance_matrix(
        self,
        view: SamplingAuditView,
        *,
        contact: str,
        guard: AuditProtection,
        continuing: bool,
    ) -> None:
        plan_id = view.plan.plan_id
        for member, request in applicable_requests(view):
            current = self.show_audit(plan_id)
            own = [
                row
                for row in current.matrix_history
                if row.member_id == member.member_id and row.request == request
            ]
            latest = own[-1] if own else None
            root_id = retained_acquisition(current, member, request)
            execution = next(
                (
                    value
                    for value in current.executions
                    if value.execution_id == root_id
                    or (
                        root_id is None
                        and value.request_key
                        == matrix_request_key(member.member_id, request)
                    )
                ),
                None,
            )
            existed = execution is not None
            if execution is None:
                execution = self.acquisitions.acquire_source(
                    plan_id,
                    request_key=matrix_request_key(member.member_id, request),
                    request=request,
                    contact_email=contact,
                    protection=guard,
                )
            chain = [execution]
            while child := next(
                (
                    value
                    for value in current.executions
                    if value.previous_execution_id == chain[-1].execution_id
                ),
                None,
            ):
                chain.append(child)
            # 已取得但未解释的执行仍需引用原事实,不能重新抓取或追认未结算成功。
            for execution in chain:
                if any(row.acquisition_id == execution.execution_id for row in own):
                    continue
                if execution.settlement is None:
                    if not continuing:
                        break
                    execution = self.acquisitions.close_unknown_source(
                        execution.execution_id, protection=guard
                    )
                row, _ = self._interpret(current, member, request, execution)
                row = self.with_previous(row, latest)
                self._append(row)
                latest = row
            execution = next(
                value
                for value in self.acquisitions.show_audit(plan_id).executions
                if value.execution_id == chain[-1].execution_id
            )
            if continuing and existed and can_continue(execution):
                assert latest is not None
                execution = self.acquisitions.acquire_source(
                    plan_id,
                    request_key=(
                        matrix_request_key(member.member_id, request)
                        + f"-resume-{len(chain)}"
                    ),
                    request=request,
                    contact_email=contact,
                    protection=guard,
                    previous_execution_id=execution.execution_id,
                )
                row, _ = self._interpret(current, member, request, execution)
                self._append(self.with_previous(row, latest))

    @staticmethod
    def with_previous(row: MatrixRow, previous: MatrixRow | None) -> MatrixRow:
        row = row.model_copy(
            update={
                "generation": previous.generation + 1 if previous else 1,
                "previous_row_id": previous.row_id if previous else None,
                "row_id": "",
            }
        )
        return row.model_copy(update={"row_id": identity_sha256(row)})

    def _validated_texts(
        self, view: AbstractAuditView, row: MatrixRow
    ) -> dict[str, str]:
        member = next(
            member
            for state in view.sampling
            for member in state.members
            if member.member_id == row.member_id
        )
        execution = next(
            value
            for value in view.executions
            if value.execution_id == row.acquisition_id
        )
        replay, texts = self._interpret(view, member, row.request, execution)
        replay = self.with_previous(replay, None).model_copy(
            update={
                "generation": row.generation,
                "previous_row_id": row.previous_row_id,
                "row_id": "",
            }
        )
        replay = replay.model_copy(update={"row_id": identity_sha256(replay)})
        if replay != row:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="abstract.interpretation"
            )
        return texts

    def read_text(self, plan_id: str, candidate_id: str) -> str:
        view = self.show_audit(plan_id)
        for row in view.matrix:
            if any(
                candidate.candidate_id == candidate_id for candidate in row.candidates
            ):
                return self._validated_texts(view, row)[candidate_id]
        raise FixtureError(FixtureReason.RECORD_NOT_FOUND, path="candidate_id")

    def validate_all(self) -> None:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                views = load_abstracts(
                    connection, load_sampling(connection, load_audits(connection))
                )
                stored_ids = set(
                    connection.execute(select(abstract_rows.c.row_id)).scalars()
                )
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="abstract.matrix"
            ) from None
        finally:
            engine.dispose()
        for view in views:
            for row in view.matrix_history:
                # Pending projections carry no persisted interpretation to verify.
                if row.row_id not in stored_ids:
                    continue
                self._validated_texts(view, row)
