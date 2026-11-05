"""Read业务恢复闭包;只读,不激活配置、不回收租约、不调用模型。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from paper_radar.read_tasks.service import ReadTasks

from datetime import datetime, timedelta

from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.read_tasks import tables as t
from paper_radar.read_tasks.acceptance import referenced_ids
from paper_radar.read_tasks.models import ReadTaskError
from paper_radar.read_tasks.queries import budget_for, task_view
from paper_radar.read_tasks.repository import canonical, records, sha, transaction
from paper_radar.reading import validate_read_output
from paper_radar.reading.acceptance_v2 import (
    CONTENT_LIMITATION_RULE_VERSION,
    EVIDENCE_RULE_VERSION,
    NUMERIC_RULE_VERSION,
    ReadV2Result,
    validate_read_output_v2,
)
from paper_radar.reading.result import ReadValidationResult


def invalid() -> None:
    raise ReadTaskError("corrupt_reference")


def domain(reason: str) -> str:
    if reason == "evidence_item_discarded":
        return "evidence"
    if reason == "restricted_source_reference":
        return "limitation"
    if reason in {
        "number_not_supported",
        "range_not_supported",
        "unit_not_supported",
        "unrecognized_numeric_form",
        "restricted_numeric_support",
    }:
        return "numeric"
    return "unsupported"


def replay_analysis(
    service: ReadTasks, connection: Connection, row: RowMapping
) -> None:
    budget = budget_for(connection, row["task_id"])
    attempt = (
        connection.execute(
            select(t.attempts).where(t.attempts.c.attempt_id == row["attempt_id"])
        )
        .mappings()
        .one()
    )
    if (attempt["task_id"], attempt["ordinal"]) != (
        row["task_id"],
        row["attempt_ordinal"],
    ):
        invalid()
    outcome = (
        connection.execute(
            select(t.outcomes).where(t.outcomes.c.attempt_id == row["attempt_id"])
        )
        .mappings()
        .one()
    )
    if (
        outcome["failure"] is not None
        or outcome["issues_json"] != "[]"
        or outcome["settled_at"] != row["settled_at"]
    ):
        invalid()
    artifact = service.artifacts.store.get_artifact(row["candidate_artifact_id"])
    if artifact.kind != "model_success_response":
        invalid()
    raw = service.artifacts.store.read_artifact(row["candidate_artifact_id"])["payload"]
    if sha(raw) != row["candidate_sha256"]:
        invalid()
    prepared = service._prepare(budget)
    version = row["evidence_rule_version"]
    result: ReadV2Result | ReadValidationResult
    if version == EVIDENCE_RULE_VERSION:
        result = validate_read_output_v2(
            raw,
            prepared.context,
            degrade_policy=row["degrade_policy"],
            attempt_ordinal=attempt["ordinal"],
        )
        discards = records(result.discards)
        numeric_known = row["numeric_rule_version"] == NUMERIC_RULE_VERSION
        limitation_known = (
            row["limitation_rule_version"] == CONTENT_LIMITATION_RULE_VERSION
        )
    elif version == "read-evidence-v1":
        if row["degrade_policy"] != "none" or row["discards_json"] != "[]":
            invalid()
        result = validate_read_output(raw, prepared.context)
        discards = "[]"
        numeric_known = row["numeric_rule_version"] == "read-numeric-v1"
        limitation_known = row["limitation_rule_version"] == "none"
    else:
        raise ReadTaskError("unsupported_rule_version")
    if row["discards_json"] != discards:
        invalid()
    saved_output = json.loads(row["output_json"])
    expected_output = json.loads(result.analysis.model_dump_json())
    saved_diagnostics = json.loads(row["diagnostics_json"])
    saved_warnings = json.loads(row["warnings_json"])
    expected_diagnostics = json.loads(records(result.diagnostics))
    expected_warnings = json.loads(records(result.warnings))
    if numeric_known and limitation_known:
        if (
            saved_output != expected_output
            or saved_diagnostics != expected_diagnostics
            or saved_warnings != expected_warnings
        ):
            invalid()
    else:
        # 未支持的历史诊断策略只保留历史记录;不声称重算等价。
        supported = (
            {"evidence"}
            | ({"numeric"} if numeric_known else set())
            | ({"limitation"} if limitation_known else set())
        )
        if not isinstance(saved_diagnostics, list) or not isinstance(
            saved_warnings, list
        ):
            invalid()

        def selected(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [v for v in values if domain(v["reason"]) in supported]

        if selected(saved_diagnostics) != selected(expected_diagnostics):
            invalid()

        def supported_warnings(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                v
                for v in values
                if v["origin"] == "model"
                or (
                    v["diagnostic"] is not None
                    and domain(v["diagnostic"]["reason"]) in supported
                )
            ]

        if supported_warnings(saved_warnings) != supported_warnings(expected_warnings):
            invalid()
        original_warnings = saved_output.pop("degraded_content_warnings")
        expected_output.pop("degraded_content_warnings")
        if saved_output != expected_output or original_warnings != [
            v["text"] for v in saved_warnings
        ]:
            invalid()
    expected_ids = referenced_ids(result.analysis)
    refs = (
        connection.execute(
            select(t.evidence)
            .where(t.evidence.c.analysis_id == row["analysis_id"])
            .order_by(t.evidence.c.evidence_id)
        )
        .mappings()
        .all()
    )
    if tuple(r["evidence_id"] for r in refs) != expected_ids or any(
        r["artifact_id"] != budget["artifact_id"] for r in refs
    ):
        invalid()
    if row["executor_kind"] == "test":
        if row["audit_json"] != "{}":
            invalid()
    else:
        from paper_radar.read_tasks.pi_rpc import validate_audit

        validate_audit(service, prepared, row["audit_json"])


def validate_all(service: ReadTasks) -> None:
    try:
        with transaction(service.database) as connection:
            budgets = connection.execute(select(t.budgets)).mappings().all()
            for budget in budgets:
                prepared = service._prepare(budget)
                if (
                    prepared.stage_input.fingerprint != budget["fingerprint"]
                    or budget["stage"] != "read"
                ):
                    invalid()
                generations = (
                    connection.execute(
                        select(t.tasks)
                        .where(t.tasks.c.budget_id == budget["budget_id"])
                        .order_by(t.tasks.c.generation)
                    )
                    .mappings()
                    .all()
                )
                if not generations or [r["generation"] for r in generations] != list(
                    range(1, len(generations) + 1)
                ):
                    invalid()
                previous = None
                for generation in generations:
                    if generation["parent_task_id"] != (
                        previous["task_id"] if previous else None
                    ):
                        invalid()
                    if previous and (
                        task_view(connection, previous["task_id"]).status != "failed"
                        or not generation["retry_reason"]
                        or not generation["retry_actor"]
                    ):
                        invalid()
                    requests = (
                        connection.execute(
                            select(t.registrations).where(
                                t.registrations.c.task_id == generation["task_id"]
                            )
                        )
                        .mappings()
                        .all()
                    )
                    if not requests:
                        invalid()
                    if previous and not any(
                        json.loads(r["request_json"])
                        == [
                            "retry",
                            previous["task_id"],
                            generation["retry_reason"],
                            generation["retry_actor"],
                        ]
                        for r in requests
                    ):
                        invalid()
                    view = task_view(connection, generation["task_id"])
                    if [a.ordinal for a in view.attempts] != list(
                        range(1, len(view.attempts) + 1)
                    ):
                        invalid()
                    for index, a in enumerate(view.attempts):
                        from paper_radar.read_tasks.queries import identity_of

                        service.body.validate_read_basis_in_connection(
                            connection, budget["paper_id"], identity_of(budget), a.basis
                        )
                        from paper_radar.feed_metadata import JGRMetadata

                        m = a.metadata_basis
                        if (
                            set(m) != {"request_key", "version_id", "revision_no"}
                            or type(m["request_key"]) is not str
                            or type(m["version_id"]) is not str
                            or type(m["revision_no"]) is not int
                        ):
                            invalid()
                        metadata = JGRMetadata(
                            service.database, service.data_root
                        ).historical_result_in_connection(
                            connection,
                            budget["paper_id"],
                            str(m["request_key"]),
                            str(m["version_id"]),
                            int(m["revision_no"]),
                        )
                        if not metadata.minimum_complete:
                            invalid()
                        if index and view.attempts[index - 1].settled_at is None:
                            invalid()
                        claimed = (
                            connection.execute(
                                select(t.attempts).where(
                                    t.attempts.c.attempt_id == a.attempt_id
                                )
                            )
                            .mappings()
                            .one()
                        )
                        until = datetime.fromisoformat(claimed["lease_until"])
                        if until != a.claimed_at + timedelta(seconds=600):
                            invalid()
                        renewals = (
                            connection.execute(
                                select(t.renewals)
                                .where(t.renewals.c.attempt_id == a.attempt_id)
                                .order_by(t.renewals.c.sequence)
                            )
                            .mappings()
                            .all()
                        )
                        if [r["sequence"] for r in renewals] != list(
                            range(1, len(renewals) + 1)
                        ):
                            invalid()
                        for renewal in renewals:
                            renewed = datetime.fromisoformat(renewal["renewed_at"])
                            if (
                                renewed < a.claimed_at
                                or renewed >= until
                                or datetime.fromisoformat(renewal["lease_until"])
                                != renewed + timedelta(seconds=600)
                            ):
                                invalid()
                            until = datetime.fromisoformat(renewal["lease_until"])
                        if a.settled_at is not None:
                            if (
                                a.settled_at < a.claimed_at
                                or (
                                    a.failure == "outcome_unknown"
                                    and a.settled_at < until
                                )
                                or (
                                    a.failure != "outcome_unknown"
                                    and a.settled_at >= until
                                )
                            ):
                                invalid()
                            if (a.failure is None) != (
                                view.analysis_id is not None
                                and index == len(view.attempts) - 1
                            ):
                                invalid()
                            if bool(a.issues) != (a.failure == "output_invalid"):
                                invalid()
                    previous = generation
            for row in connection.execute(select(t.analyses)).mappings():
                replay_analysis(service, connection, row)
            for row in connection.execute(select(t.registrations)).mappings():
                budget = budget_for(connection, row["task_id"])
                from paper_radar.config import load_config_snapshot

                load_config_snapshot(service.database, row["snapshot_id"])
                values = json.loads(row["request_json"])
                if (
                    canonical(values) != row["request_json"]
                    or sha(row["request_json"].encode()) != row["request_hash"]
                ):
                    invalid()
                if (
                    isinstance(values, list)
                    and len(values) == 4
                    and values[0] == "retry"
                ):
                    generation = (
                        connection.execute(
                            select(t.tasks).where(t.tasks.c.task_id == row["task_id"])
                        )
                        .mappings()
                        .one()
                    )
                    if (
                        not isinstance(values, list)
                        or len(values) != 4
                        or values[:2] != ["retry", generation["parent_task_id"]]
                        or not all(type(v) is str and v.strip() for v in values)
                    ):
                        invalid()
                else:
                    if values != [
                        budget["paper_id"],
                        row["snapshot_id"],
                        budget["extraction_fingerprint"],
                        budget["output_language"],
                        row["label"],
                    ]:
                        invalid()
                    from paper_radar.read_inputs import prepare_read_input

                    snapshot = load_config_snapshot(
                        service.database, row["snapshot_id"]
                    )
                    extraction = service.body.extraction_input_in_connection(
                        connection, budget["extraction_fingerprint"]
                    )
                    from paper_radar.read_tasks.queries import identity_of

                    prepared = prepare_read_input(
                        service.artifacts,
                        budget["artifact_id"],
                        extraction,
                        snapshot,
                        snapshot,
                        expected_identity=identity_of(budget),
                        output_language=budget["output_language"],
                    )
                    if prepared.stage_input.fingerprint != budget["fingerprint"]:
                        invalid()
                if (
                    not row["request_id"]
                    or not row["label"]
                    or len(row["request_hash"]) != 64
                ):
                    invalid()
    except ReadTaskError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise ReadTaskError("corrupt_reference") from None
