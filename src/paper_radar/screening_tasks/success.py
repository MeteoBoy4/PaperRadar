"""候选接收:预检、事务外发布与受 fenced 身份约束的原子结算。"""

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import Connection, select

from paper_radar.config import ConfigError
from paper_radar.papers import PaperFacts
from paper_radar.screening import (
    BoundaryOutput,
    OutputValidationError,
    OutputValidationIssue,
    ValuePredictionOutput,
)
from paper_radar.screening_tasks.attempt_models import (
    Claim,
    FailureKind,
    FailureReceipt,
)
from paper_radar.screening_tasks.attempt_rules import (
    digest,
    read_timestamp,
    timestamp,
    utc_now,
)
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.execution import AttemptService
from paper_radar.screening_tasks.frozen import load_frozen
from paper_radar.screening_tasks.repository import receipt_row
from paper_radar.screening_tasks.rules import canonical
from paper_radar.screening_tasks.success_models import (
    SuccessCandidate,
    SuccessContent,
    SuccessReceipt,
    SuccessView,
)
from paper_radar.screening_tasks.success_rules import (
    candidate_audit,
    decode_issues,
    encode_issues,
    model_matches,
    require_success_id,
    stored_candidate,
    submission_digest,
    validate_candidate_output,
)
from paper_radar.screening_tasks.tables import budgets, failures, successes
from paper_radar.stage_inputs import StageInputError
from paper_radar.storage.artifacts import ArtifactStore


class SuccessService:
    def __init__(self, attempts: AttemptService, data_root: Path | None) -> None:
        self.attempts = attempts
        self.data_root = data_root

    def store(self) -> ArtifactStore:
        if self.data_root is None:
            raise TaskError(TaskReason.DATA_ROOT_REQUIRED)
        return ArtifactStore(self.attempts.database, self.data_root)

    def _precheck(
        self, connection: Connection, claim: Claim, submission: str
    ) -> tuple[dict[str, Any], SuccessReceipt | FailureReceipt | None]:
        rows = self.attempts._attempt_rows(connection, claim.task_id)
        row = next(
            (item for item in rows if item["attempt_no"] == claim.attempt_no), None
        )
        if row is None or row["credential_sha256"] != digest(claim.credential):
            raise TaskError(TaskReason.INVALID_CREDENTIAL)
        if row["success_id"] is not None:
            success = self._row(connection, row["success_id"])
            if success["submission_sha256"] != submission:
                raise TaskError(TaskReason.SETTLEMENT_CONFLICT)
            return row, self._receipt(success)
        if row["kind"] is not None:
            failure = (
                connection.execute(
                    select(failures).where(
                        failures.c.task_id == claim.task_id,
                        failures.c.attempt_no == claim.attempt_no,
                    )
                )
                .mappings()
                .one()
            )
            if failure["origin"] == "recovery":
                raise TaskError(TaskReason.INVALID_CREDENTIAL)
            if failure["submission_sha256"] == submission:
                return row, self.attempts._failure_receipt(row)
            raise TaskError(TaskReason.SETTLEMENT_CONFLICT)
        if row["attempt_no"] != rows[-1]["attempt_no"]:
            raise TaskError(TaskReason.INVALID_CREDENTIAL)
        return row, None

    def submit(
        self, claim: Claim, candidate: SuccessCandidate
    ) -> SuccessReceipt | FailureReceipt:
        if type(claim) is not Claim:
            raise TaskError(TaskReason.INVALID_CREDENTIAL)
        self.attempts._require_secret(claim.credential)
        audit = candidate_audit(candidate)
        submission = submission_digest(candidate.raw_response, audit)
        with self.attempts.connection(write=False) as connection:
            row, replayed = self._precheck(connection, claim, submission)
            if replayed is not None:
                return replayed
            request = receipt_row(connection, row["receipt_id"])
            if request is None or request["stage"] not in {"boundary", "value"}:
                raise TaskError(TaskReason.INVALID_CANDIDATE)
            budget = dict(
                connection.execute(
                    select(budgets).where(budgets.c.budget_id == request["budget_id"])
                )
                .mappings()
                .one()
            )
            try:
                frozen = load_frozen(self.attempts.database, connection, budget)
            except (ConfigError, StageInputError):
                raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
        kind: FailureKind | None = None
        issues: tuple[OutputValidationIssue, ...] = ()
        output: BoundaryOutput | ValuePredictionOutput | None = None
        if not model_matches(candidate, frozen.snapshot):
            kind = FailureKind.MODEL_MISMATCH
        else:
            try:
                output = validate_candidate_output(frozen, candidate.raw_response)
            except OutputValidationError as error:
                kind, issues = (
                    FailureKind.OUTPUT_INVALID,
                    decode_issues(encode_issues(error.issues), stage=request["stage"]),
                )
        # 发布不能位于业务写事务内。竞争失败时仅可能留下完整的未引用 A3 制品。
        artifact_id = (
            self.store()
            .publish_single("model_success_response", (candidate.raw_response,))
            .artifact_id
            if kind is None
            else None
        )
        with self.attempts.connection(write=True) as connection:
            row, replayed = self._precheck(connection, claim, submission)
            if replayed is not None:
                return replayed
            now = utc_now(self.attempts.clock)
            self.attempts._require_time(row, now)
            if kind is not None:
                connection.execute(
                    failures.insert().values(
                        task_id=claim.task_id,
                        attempt_no=claim.attempt_no,
                        kind=kind.value,
                        origin="executor",
                        settled_at=timestamp(now),
                        issues_json=encode_issues(issues),
                        submission_sha256=submission,
                        audit_json=audit,
                    )
                )
                return FailureReceipt(
                    claim.task_id, claim.attempt_no, kind, "executor", now, issues
                )
            assert output is not None and artifact_id is not None
            if (
                connection.execute(
                    select(successes.c.success_id).where(
                        successes.c.budget_id == budget["budget_id"]
                    )
                ).first()
                is not None
            ):
                raise TaskError(TaskReason.SETTLEMENT_CONFLICT)
            identifier = str(uuid4())
            connection.execute(
                successes.insert().values(
                    success_id=identifier,
                    budget_id=budget["budget_id"],
                    task_id=claim.task_id,
                    attempt_no=claim.attempt_no,
                    artifact_id=artifact_id,
                    structured_json=canonical(output.model_dump(mode="json")).decode(
                        "utf-8"
                    ),
                    submission_sha256=submission,
                    audit_json=audit,
                    settled_at=timestamp(now),
                )
            )
            return self._receipt(self._row(connection, identifier))

    @staticmethod
    def _row(connection: Connection, success_id: str) -> dict[str, Any]:
        row = (
            connection.execute(
                select(
                    successes,
                    budgets.c.paper_id,
                    budgets.c.stage,
                    budgets.c.fingerprint,
                )
                .join(budgets, successes.c.budget_id == budgets.c.budget_id)
                .where(successes.c.success_id == success_id)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise TaskError(TaskReason.SUCCESS_NOT_FOUND)
        return dict(row)

    @staticmethod
    def _receipt(row: dict[str, Any]) -> SuccessReceipt:
        require_success_id(row["success_id"])
        return SuccessReceipt(
            row["success_id"],
            row["task_id"],
            row["attempt_no"],
            row["artifact_id"],
            row["fingerprint"],
            row["stage"],
            "test",
            read_timestamp(row["settled_at"]),
        )

    def load(self, success_id: str) -> SuccessContent:
        try:
            return self._load_content(success_id)
        except (
            ConfigError,
            StageInputError,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
        ):
            raise TaskError(TaskReason.CORRUPT_REFERENCE) from None

    def _load_content(self, success_id: str) -> SuccessContent:
        with self.attempts.connection(write=False) as connection:
            row = self._row(connection, success_id)
            budget = dict(
                connection.execute(
                    select(budgets).where(budgets.c.budget_id == row["budget_id"])
                )
                .mappings()
                .one()
            )
            frozen = load_frozen(self.attempts.database, connection, budget)
        store = self.store()
        if store.get_artifact(row["artifact_id"]).kind != "model_success_response":
            raise TaskError(TaskReason.CORRUPT_REFERENCE)
        raw = store.read_artifact(row["artifact_id"])["payload"]
        candidate = stored_candidate(raw, row["audit_json"])
        if not model_matches(candidate, frozen.snapshot):
            raise TaskError(TaskReason.CORRUPT_REFERENCE)
        try:
            output = validate_candidate_output(frozen, raw)
            if (
                canonical(output.model_dump(mode="json")).decode("utf-8")
                != row["structured_json"]
                or submission_digest(raw, row["audit_json"]) != row["submission_sha256"]
            ):
                raise TaskError(TaskReason.CORRUPT_REFERENCE)
        except OutputValidationError:
            raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
        return SuccessContent(
            self._receipt(row), raw, output, json.loads(row["audit_json"])
        )

    def query(
        self, *, paper_id: str, stage: str, snapshot_id: str
    ) -> tuple[SuccessView, ...]:
        if type(stage) is not str or stage not in {"boundary", "value"}:
            raise TaskError(TaskReason.INVALID_REQUEST)
        # PaperFacts 持有自己的只读一致视图;允许相对任务读取的并发提交滞后。
        mapping = PaperFacts(self.attempts.database).map_screening_inputs(
            paper_id=paper_id, snapshot_id=snapshot_id
        )
        mapped = mapping.boundary if stage == "boundary" else mapping.value
        with self.attempts.connection(write=False) as connection:
            ids = (
                connection.execute(
                    select(successes.c.success_id)
                    .join(budgets, successes.c.budget_id == budgets.c.budget_id)
                    .where(budgets.c.paper_id == paper_id, budgets.c.stage == stage)
                    .order_by(successes.c.success_id)
                )
                .scalars()
                .all()
            )
            result = []
            for identifier in ids:
                row = self._row(connection, identifier)
                applicability: Literal["current", "historical", "undeterminable"] = (
                    "undeterminable"
                    if mapped.reason is not None
                    else "current"
                    if mapped.value is not None
                    and mapped.value.fingerprint == row["fingerprint"]
                    else "historical"
                )
                result.append(
                    SuccessView(self._receipt(row), applicability, mapped.reason)
                )
            return tuple(result)
