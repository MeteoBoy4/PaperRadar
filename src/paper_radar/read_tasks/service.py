"""显式单篇Read:短事务领取,事务外模型,有限预算和追加历史。"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from sqlalchemy import Connection, insert, select
from sqlalchemy.engine import RowMapping

from paper_radar.body import BodyService
from paper_radar.config import load_config_snapshot
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.read_inputs import (
    PreparedReadInput,
    build_read_correction,
    prepare_read_input,
)
from paper_radar.read_tasks import tables as t
from paper_radar.read_tasks.models import (
    ReadAnalysis,
    ReadFailure,
    ReadHandle,
    ReadTask,
    ReadTaskError,
)
from paper_radar.read_tasks.preconditions import require_facts
from paper_radar.read_tasks.queries import budget_for, deadline, identity_of, task_view
from paper_radar.read_tasks.repository import (
    canonical,
    digest,
    required,
    transaction,
)
from paper_radar.reading.context import SourceSlice
from paper_radar.runtime_logging import RuntimeLog, Sink
from paper_radar.storage.artifacts import ArtifactStore

if TYPE_CHECKING:
    from paper_radar.read_tasks.pi_rpc import PiReadCandidate

LEASE_SECONDS = 600


class ReadTasks:
    def __init__(
        self,
        database: Path,
        data_root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
        sink: Sink | None = None,
    ):
        self.database, self.data_root = database, data_root
        self.clock = clock or (lambda: datetime.now(UTC))
        self.body = BodyService(database, data_root)
        self.artifacts = FulltextArtifacts(ArtifactStore(database, data_root))
        self.log = RuntimeLog(sink)

    def _now(self) -> datetime:
        value = self.clock()
        if (
            type(value) is not datetime
            or value.tzinfo is None
            or value.utcoffset() != timedelta(0)
        ):
            raise ReadTaskError("invalid_request")
        return value

    def _prepare(self, budget: RowMapping) -> PreparedReadInput:
        with transaction(self.database) as connection:
            extraction = self.body.extraction_input_in_connection(
                connection, budget["extraction_fingerprint"]
            )
        snapshot = load_config_snapshot(self.database, budget["snapshot_id"])
        prepared = prepare_read_input(
            self.artifacts,
            budget["artifact_id"],
            extraction,
            snapshot,
            snapshot,
            expected_identity=identity_of(budget),
            output_language=budget["output_language"],
        )
        if (
            prepared.stage_input.payload_bytes != budget["payload"]
            or prepared.stage_input.fingerprint != budget["fingerprint"]
        ):
            raise ReadTaskError("corrupt_reference")
        if not prepared.budget.accepted:
            raise ReadTaskError("read_input_over_budget")
        return prepared

    def register(
        self,
        paper_id: str,
        *,
        snapshot_id: str,
        extraction_fingerprint: str,
        request_id: str,
        output_language: Literal["zh", "en"] = "zh",
        label: str = "manual",
    ) -> ReadTask:
        required(paper_id, snapshot_id, extraction_fingerprint, request_id, label)
        if output_language not in ("zh", "en"):
            raise ReadTaskError("invalid_request")
        snapshot = load_config_snapshot(self.database, snapshot_id)
        with transaction(self.database) as connection:
            extraction = self.body.extraction_input_in_connection(
                connection, extraction_fingerprint
            )
            facts = self.body.facts_in_connection(
                connection, paper_id, fingerprint=extraction_fingerprint
            )
            view = facts.extraction
            if view is None or view.identity is None or view.artifact_id is None:
                raise ReadTaskError(
                    "prerequisites_failed", reasons=tuple(map(str, facts.reasons))
                )
        prepared = prepare_read_input(
            self.artifacts,
            view.artifact_id,
            extraction,
            snapshot,
            snapshot,
            expected_identity=view.identity,
            output_language=output_language,
        )
        if not prepared.budget.accepted:
            raise ReadTaskError("read_input_over_budget")
        request_hash = digest(
            [paper_id, snapshot_id, extraction_fingerprint, output_language, label]
        )
        with transaction(self.database, write=True) as connection:
            require_facts(self.body, connection, paper_id, view.identity)
            old = (
                connection.execute(
                    select(t.registrations).where(
                        t.registrations.c.request_id == request_id
                    )
                )
                .mappings()
                .first()
            )
            if old:
                if old["request_hash"] != request_hash:
                    raise ReadTaskError("request_conflict")
                return task_view(connection, old["task_id"])
            budget = (
                connection.execute(
                    select(t.budgets).where(
                        t.budgets.c.paper_id == paper_id,
                        t.budgets.c.fingerprint == prepared.stage_input.fingerprint,
                    )
                )
                .mappings()
                .first()
            )
            if budget is None:
                budget_id, task_id = str(uuid4()), str(uuid4())
                connection.execute(
                    insert(t.budgets).values(
                        budget_id=budget_id,
                        paper_id=paper_id,
                        fingerprint=prepared.stage_input.fingerprint,
                        stage="read",
                        snapshot_id=snapshot_id,
                        payload=prepared.stage_input.payload_bytes,
                        extraction_fingerprint=extraction_fingerprint,
                        artifact_id=view.artifact_id,
                        reading_sha256=view.identity.reading_sha256,
                        evidence_map_sha256=view.identity.evidence_map_sha256,
                        output_language=output_language,
                        created_at=self._now().isoformat(),
                    )
                )
                connection.execute(
                    insert(t.tasks).values(
                        task_id=task_id,
                        budget_id=budget_id,
                        generation=1,
                        created_at=self._now().isoformat(),
                    )
                )
            else:
                task_id = connection.execute(
                    select(t.tasks.c.task_id)
                    .where(t.tasks.c.budget_id == budget["budget_id"])
                    .order_by(t.tasks.c.generation.desc())
                ).scalar_one()
            connection.execute(
                insert(t.registrations).values(
                    request_id=request_id,
                    request_hash=request_hash,
                    request_json=canonical(
                        [
                            paper_id,
                            snapshot_id,
                            extraction_fingerprint,
                            output_language,
                            label,
                        ]
                    ),
                    task_id=task_id,
                    snapshot_id=snapshot_id,
                    label=label,
                    registered_at=self._now().isoformat(),
                )
            )
            return task_view(connection, task_id)

    def task(self, task_id: str) -> ReadTask:
        with transaction(self.database) as connection:
            return task_view(connection, task_id)

    def history(self, paper_id: str) -> tuple[ReadTask, ...]:
        with transaction(self.database) as connection:
            ids = connection.execute(
                select(t.tasks.c.task_id)
                .select_from(
                    t.tasks.join(
                        t.budgets, t.tasks.c.budget_id == t.budgets.c.budget_id
                    )
                )
                .where(t.budgets.c.paper_id == paper_id)
                .order_by(t.tasks.c.created_at, t.tasks.c.generation)
            ).scalars()
            return tuple(task_view(connection, key) for key in ids)

    def prepare(self, task_id: str) -> PreparedReadInput:
        with transaction(self.database) as connection:
            budget = budget_for(connection, task_id)
        return self._prepare(budget)

    def correction(self, task_id: str) -> str | None:
        view = self.task(task_id)
        return (
            build_read_correction(view.attempts[-1].issues)
            if view.attempts and view.attempts[-1].issues
            else None
        )

    def claim(
        self,
        task_id: str,
        *,
        preclaim: Callable[[PreparedReadInput, str | None], None] | None = None,
    ) -> ReadHandle:
        prepared = self.prepare(task_id)
        with transaction(self.database, write=True) as connection:
            budget = budget_for(connection, task_id)
            facts = require_facts(
                self.body, connection, budget["paper_id"], identity_of(budget)
            )
            basis = self.body.read_basis_in_connection(connection, facts)
            from paper_radar.feed_metadata import JGRMetadata

            metadata = JGRMetadata(self.database, self.data_root).result_in_connection(
                connection, budget["paper_id"]
            )
            if metadata is None or not metadata.minimum_complete:
                raise ReadTaskError("corrupt_reference")
            metadata_basis = {
                "request_key": metadata.request_key,
                "version_id": metadata.version_id,
                "revision_no": metadata.revision_no,
            }
            view = task_view(connection, task_id)
            if view.status == "succeeded":
                raise ReadTaskError("already_succeeded")
            if view.status == "running":
                raise ReadTaskError("task_running")
            if view.status == "failed":
                raise ReadTaskError("budget_exhausted")
            successor = connection.execute(
                select(t.tasks.c.task_id).where(t.tasks.c.parent_task_id == task_id)
            ).first()
            if successor:
                raise ReadTaskError("not_latest")
            correction = (
                build_read_correction(view.attempts[-1].issues)
                if view.attempts and view.attempts[-1].issues
                else None
            )
            if preclaim:
                preclaim(prepared, correction)
            now = self._now()
            if (
                view.attempts
                and view.attempts[-1].settled_at is not None
                and now < view.attempts[-1].settled_at
            ):
                raise ReadTaskError("invalid_request")
            handle = ReadHandle(
                task_id,
                str(uuid4()),
                len(view.attempts) + 1,
                str(uuid4()),
                now + timedelta(seconds=LEASE_SECONDS),
                prepared.description,
                correction,
            )
            connection.execute(
                insert(t.attempts).values(
                    attempt_id=handle.attempt_id,
                    task_id=task_id,
                    ordinal=handle.ordinal,
                    token=handle.token,
                    claimed_at=now.isoformat(),
                    lease_until=handle.lease_until.isoformat(),
                    basis_json=canonical(basis),
                    metadata_json=canonical(metadata_basis),
                )
            )
        self.log.emit(
            "claimed",
            component="read",
            stage="read",
            task_id=task_id,
            paper_id=budget["paper_id"],
            fingerprint=budget["fingerprint"],
            attempt=handle.ordinal,
        )
        return handle

    def _owned(
        self, connection: Connection, handle: ReadHandle, *, settled: bool = False
    ) -> tuple[RowMapping, RowMapping | None]:
        if (
            type(handle) is not ReadHandle
            or type(handle.ordinal) is not int
            or handle.ordinal not in (1, 2)
        ):
            raise ReadTaskError("invalid_credential")
        row = (
            connection.execute(
                select(t.attempts).where(t.attempts.c.attempt_id == handle.attempt_id)
            )
            .mappings()
            .first()
        )
        if row is None or (row["task_id"], row["token"], row["ordinal"]) != (
            handle.task_id,
            handle.token,
            handle.ordinal,
        ):
            raise ReadTaskError("invalid_credential")
        outcome = (
            connection.execute(
                select(t.outcomes).where(t.outcomes.c.attempt_id == handle.attempt_id)
            )
            .mappings()
            .first()
        )
        if outcome is not None and not settled:
            raise ReadTaskError("settlement_conflict")
        if outcome is None:
            renewed_at = connection.execute(
                select(t.renewals.c.renewed_at)
                .where(t.renewals.c.attempt_id == handle.attempt_id)
                .order_by(t.renewals.c.sequence.desc())
            ).scalar()
            now = self._now()
            if now < datetime.fromisoformat(
                renewed_at or row["claimed_at"]
            ) or now >= deadline(connection, row):
                raise ReadTaskError("invalid_credential")
        return row, outcome

    def renew(self, handle: ReadHandle) -> datetime:
        with transaction(self.database, write=True) as connection:
            self._owned(connection, handle)
            sequence = (
                len(
                    connection.execute(
                        select(t.renewals.c.sequence).where(
                            t.renewals.c.attempt_id == handle.attempt_id
                        )
                    ).all()
                )
                + 1
            )
            now = self._now()
            until = now + timedelta(seconds=LEASE_SECONDS)
            connection.execute(
                insert(t.renewals).values(
                    attempt_id=handle.attempt_id,
                    sequence=sequence,
                    renewed_at=now.isoformat(),
                    lease_until=until.isoformat(),
                )
            )
            return until

    def reclaim(self, task_id: str) -> ReadTask:
        with transaction(self.database, write=True) as connection:
            task_view(connection, task_id)
            for row in connection.execute(
                select(t.attempts).where(t.attempts.c.task_id == task_id)
            ).mappings():
                if connection.execute(
                    select(t.outcomes.c.attempt_id).where(
                        t.outcomes.c.attempt_id == row["attempt_id"]
                    )
                ).first() is None and self._now() >= deadline(connection, row):
                    connection.execute(
                        insert(t.outcomes).values(
                            attempt_id=row["attempt_id"],
                            failure="outcome_unknown",
                            issues_json="[]",
                            settled_at=self._now().isoformat(),
                        )
                    )
            return task_view(connection, task_id)

    def fail(self, handle: ReadHandle, failure: ReadFailure | str) -> ReadTask:
        try:
            failure = ReadFailure(failure)
        except ValueError:
            raise ReadTaskError("invalid_request") from None
        if failure in (ReadFailure.OUTPUT_INVALID, ReadFailure.OUTCOME_UNKNOWN):
            raise ReadTaskError("invalid_request")
        with transaction(self.database, write=True) as connection:
            self._owned(connection, handle)
            connection.execute(
                insert(t.outcomes).values(
                    attempt_id=handle.attempt_id,
                    failure=failure.value,
                    issues_json="[]",
                    settled_at=self._now().isoformat(),
                )
            )
            result = task_view(connection, handle.task_id)
        self.log.emit(
            "failed",
            component="read",
            stage="read",
            task_id=handle.task_id,
            attempt=handle.ordinal,
            kind=failure.value,
        )
        return result

    def prepare_correction(self, task_id: str) -> str | None:
        return self.correction(task_id)

    def run_pi_once(
        self,
        task_id: str,
        executor: Callable[[ReadHandle], "PiReadCandidate"],
        *,
        preclaim: Callable[[PreparedReadInput, str | None], None] | None = None,
    ) -> ReadAnalysis | ReadTask:
        from paper_radar.read_tasks.pi_rpc import run_pi_once

        return run_pi_once(self, task_id, executor, preclaim=preclaim)

    def submit_test(self, handle: ReadHandle, raw: bytes) -> ReadAnalysis | ReadTask:
        from paper_radar.read_tasks.acceptance import submit

        return submit(self, handle, raw)

    def run_once(
        self, task_id: str, executor: Callable[[ReadHandle], bytes]
    ) -> ReadAnalysis | ReadTask:
        """test执行器只能返回原始字节,不能声明生产来源或末次序号。"""
        from paper_radar.read_tasks.execution import execution_resource

        with execution_resource(self.data_root):
            handle = self.claim(task_id)
            try:
                raw = executor(handle)
            except Exception:
                return self.fail(handle, "executor_error")
            return self.submit_test(handle, raw)

    def retry(
        self, task_id: str, *, request_id: str, reason: str, actor: str
    ) -> ReadTask:
        required(task_id, request_id, reason, actor)
        request_hash = digest(["retry", task_id, reason, actor])
        with transaction(self.database, write=True) as connection:
            view = task_view(connection, task_id)
            old = (
                connection.execute(
                    select(t.registrations).where(
                        t.registrations.c.request_id == request_id
                    )
                )
                .mappings()
                .first()
            )
            if old:
                if old["request_hash"] != request_hash:
                    raise ReadTaskError("request_conflict")
                return task_view(connection, old["task_id"])
            child = connection.execute(
                select(t.tasks.c.task_id).where(t.tasks.c.parent_task_id == task_id)
            ).scalar()
            if child:
                budget = budget_for(connection, task_id)
                connection.execute(
                    insert(t.registrations).values(
                        request_id=request_id,
                        request_hash=request_hash,
                        request_json=canonical(["retry", task_id, reason, actor]),
                        task_id=child,
                        snapshot_id=budget["snapshot_id"],
                        label="retry",
                        registered_at=self._now().isoformat(),
                    )
                )
                return task_view(connection, child)
            budget = budget_for(connection, task_id)
            latest = connection.execute(
                select(t.tasks.c.task_id)
                .where(t.tasks.c.budget_id == budget["budget_id"])
                .order_by(t.tasks.c.generation.desc())
            ).scalar()
            if latest != task_id:
                raise ReadTaskError("not_latest")
            if view.status != "failed":
                raise ReadTaskError("not_failed")
            new_id = str(uuid4())
            connection.execute(
                insert(t.tasks).values(
                    task_id=new_id,
                    budget_id=budget["budget_id"],
                    generation=view.generation + 1,
                    parent_task_id=task_id,
                    retry_reason=reason,
                    retry_actor=actor,
                    created_at=self._now().isoformat(),
                )
            )
            connection.execute(
                insert(t.registrations).values(
                    request_id=request_id,
                    request_hash=request_hash,
                    request_json=canonical(["retry", task_id, reason, actor]),
                    task_id=new_id,
                    snapshot_id=budget["snapshot_id"],
                    label="retry",
                    registered_at=self._now().isoformat(),
                )
            )
            return task_view(connection, new_id)

    def analysis(self, analysis_id: str, *, ordinary: bool = False) -> ReadAnalysis:
        import json

        from paper_radar.read_tasks.models import ReadAnalysis
        from paper_radar.reading.schema import ReadAnalysisOutput

        with transaction(self.database) as connection:
            row = (
                connection.execute(
                    select(t.analyses).where(t.analyses.c.analysis_id == analysis_id)
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ReadTaskError("analysis_not_found")
            from paper_radar.read_tasks.validation import replay_analysis

            replay_analysis(self, connection, row)
            budget = budget_for(connection, row["task_id"])
            facts = self.body.facts_in_connection(
                connection,
                budget["paper_id"],
                identity=identity_of(budget),
                ordinary=ordinary,
            )
            if ordinary and (
                facts.root.purpose != "production"
                or row["executor_kind"] != "pi_rpc"
                or facts.extraction is None
                or facts.extraction.quality.basis != "formal_gate"
            ):
                raise ReadTaskError("ordinary_consumption_denied")
            raw = self.artifacts.store.read_artifact(row["candidate_artifact_id"])[
                "payload"
            ]
            return ReadAnalysis(
                row["analysis_id"],
                row["task_id"],
                budget["paper_id"],
                budget["fingerprint"],
                identity_of(budget),
                budget["artifact_id"],
                row["candidate_artifact_id"],
                row["attempt_ordinal"],
                row["executor_kind"],
                facts.root.purpose.value,
                facts.extraction.quality.basis.value if facts.extraction else "unknown",
                ReadAnalysisOutput.model_validate_json(row["output_json"]),
                raw,
                tuple(json.loads(row["discards_json"])),
                tuple(json.loads(row["diagnostics_json"])),
                tuple(json.loads(row["warnings_json"])),
                row["evidence_rule_version"],
                row["numeric_rule_version"],
                row["limitation_rule_version"],
                audit=json.loads(row["audit_json"]),
            )

    def analyses(
        self, paper_id: str, *, ordinary: bool = False
    ) -> tuple[ReadAnalysis, ...]:
        with transaction(self.database) as connection:
            keys = (
                connection.execute(
                    select(t.analyses.c.analysis_id)
                    .select_from(
                        t.analyses.join(
                            t.tasks, t.analyses.c.task_id == t.tasks.c.task_id
                        ).join(t.budgets, t.tasks.c.budget_id == t.budgets.c.budget_id)
                    )
                    .where(t.budgets.c.paper_id == paper_id)
                    .order_by(t.analyses.c.settled_at)
                )
                .scalars()
                .all()
            )
        return tuple(self.analysis(key, ordinary=ordinary) for key in keys)

    def evidence(
        self, analysis_id: str, evidence_id: str, *, ordinary: bool = False
    ) -> tuple[SourceSlice, ...]:
        analysis = self.analysis(analysis_id, ordinary=ordinary)
        with transaction(self.database) as connection:
            if (
                connection.execute(
                    select(t.evidence.c.evidence_id).where(
                        t.evidence.c.analysis_id == analysis_id,
                        t.evidence.c.evidence_id == evidence_id,
                    )
                ).first()
                is None
            ):
                raise ReadTaskError("corrupt_reference")
        return self.artifacts.lookup(
            analysis.artifact_id, analysis.identity, evidence_id
        )

    def validate_all(self) -> None:
        from paper_radar.read_tasks.validation import validate_all

        validate_all(self)
