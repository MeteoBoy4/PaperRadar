"""仅从持久事实与制品验证 Body 闭包;备份/恢复共享,无执行副作用。"""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from paper_radar.body import tables
from paper_radar.body.extraction import LAYOUT_CHECKS, PERMANENT, extraction_view
from paper_radar.body.facts import execution_source
from paper_radar.body.models import BodyError
from paper_radar.body.pdf import valid_pdf_bytes
from paper_radar.body.repository import digest, required, transaction
from paper_radar.config import load_config_snapshot
from paper_radar.eligibility import QualityBasis, RootPurpose
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.models import ExtractionManifest, FulltextError
from paper_radar.papers import PaperFacts
from paper_radar.papers.queries import load_trace
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.stage_inputs import ExtractionFacts, replay_stage_input
from paper_radar.storage.artifacts import ArtifactStore


def require(condition: bool) -> None:
    if not condition:
        raise BodyError("corrupt_reference")


def timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    offset = parsed.utcoffset()
    require(offset is not None and offset.total_seconds() == 0)


def validate_all(database: Path, root: Path) -> None:
    from paper_radar.body.queries import decision_events, root_fact

    store = ArtifactStore(database, root)
    try:
        PaperFacts(database, root).validate_all()
        ScreeningTasks(database, root).validate_all()
        with transaction(database) as connection:
            roots = connection.execute(select(tables.roots)).mappings().all()
            require(
                not roots or root_fact(connection).purpose is not RootPurpose.UNKNOWN
            )
            if roots:
                timestamp(roots[0]["registered_at"])
            pdfs = connection.execute(select(tables.pdfs)).mappings().all()
            for table in (tables.pdfs, tables.samples):
                for paper_id in set(
                    connection.execute(select(table.c.paper_id)).scalars()
                ):
                    history = list(
                        connection.execute(
                            select(table.c.sequence)
                            .where(table.c.paper_id == paper_id)
                            .order_by(table.c.sequence)
                        ).scalars()
                    )
                    require(history == list(range(1, len(history) + 1)))
            paper_ids = set(
                connection.execute(select(tables.decisions.c.paper_id)).scalars()
            )
            for paper_id in paper_ids:
                events = decision_events(connection, paper_id)
                require(
                    [e.fact.sequence for e in events] == list(range(1, len(events) + 1))
                )
                for event in events:
                    required(event.actor)
                    timestamp(event.decided_at)
                    row = (
                        connection.execute(
                            select(tables.decisions).where(
                                tables.decisions.c.decision_id == event.fact.reference
                            )
                        )
                        .mappings()
                        .one()
                    )
                    require(
                        row["request_hash"]
                        == digest(
                            [
                                paper_id,
                                event.fact.record.model_dump(mode="json"),
                                event.actor,
                                event.screening_references,
                            ]
                        )
                    )
                    execution_source(connection, paper_id, event)
            for row in pdfs:
                trace = load_trace(connection, row["paper_id"])
                require(
                    row["version_id"]
                    in {version.version_id for version in trace.versions}
                )
                record = store.get_artifact(row["artifact_id"])
                require(record.kind == "original_pdf")
                raw = store.read_artifact(row["artifact_id"])["payload"]
                require(valid_pdf_bytes(raw, row["pdf_sha256"]))
                require(
                    row["request_hash"]
                    == digest(
                        [
                            row["paper_id"],
                            row["requested_version_id"],
                            row["pdf_sha256"],
                        ]
                    )
                )
                require(
                    row["requested_version_id"] in {None, row["version_id"]}
                    and row["access_basis"] == "manual"
                )
                timestamp(row["attached_at"])
            for row in connection.execute(select(tables.samples)).mappings():
                trace = load_trace(connection, row["paper_id"])
                require(
                    any(
                        p["paper_id"] == row["paper_id"]
                        and p["version_id"] == row["version_id"]
                        and p["pdf_sha256"] == row["pdf_sha256"]
                        for p in pdfs
                    )
                )
                require(
                    any(
                        d.feed_id == row["feed_id"]
                        and d.version_id == row["version_id"]
                        for d in trace.discoveries
                    )
                )
                required(row["reason"])
                timestamp(row["frozen_at"])
                require(
                    row["request_hash"]
                    == digest(
                        [
                            row["paper_id"],
                            row["feed_id"],
                            row["pdf_sha256"],
                            row["reason"],
                        ]
                    )
                )
                require(root_fact(connection).purpose is RootPurpose.EXPERIMENT)
            inputs = connection.execute(select(tables.inputs)).mappings().all()
            for row in inputs:
                snapshot = load_config_snapshot(database, row["snapshot_id"])
                stage = replay_stage_input(
                    row["payload"], row["fingerprint"], snapshot=snapshot
                )
                semantics = snapshot.extraction
                require(
                    isinstance(stage.facts, ExtractionFacts)
                    and stage.facts.pdf_sha256 == row["pdf_sha256"]
                )
                require(
                    semantics is not None
                    and semantics.backend.backend_id == row["backend"]
                )
                assert semantics is not None
                require(any(p["pdf_sha256"] == row["pdf_sha256"] for p in pdfs))
                view = extraction_view(connection, row["fingerprint"])
                assert view is not None
                require(
                    [a.ordinal for a in view.attempts]
                    == list(range(1, len(view.attempts) + 1))
                    and 1 <= len(view.attempts) <= 2
                )
                for index, attempt in enumerate(view.attempts):
                    timestamp(attempt.claimed_at)
                    if attempt.executor_audit is not None:
                        require(attempt.executor_audit.matches(semantics))
                    backend = connection.execute(
                        select(tables.attempts.c.backend).where(
                            tables.attempts.c.attempt_id == attempt.attempt_id
                        )
                    ).scalar_one()
                    require(backend == row["backend"])
                    if attempt.settled_at is None:
                        require(index == len(view.attempts) - 1)
                        continue
                    timestamp(attempt.settled_at)
                    require(
                        attempt.elapsed_seconds is not None
                        and attempt.elapsed_seconds >= 0
                        and attempt.peak_memory_bytes is not None
                        and attempt.peak_memory_bytes >= 0
                    )
                    if attempt.artifact_id is None:
                        require(attempt.failure is not None)
                    else:
                        require(
                            index == len(view.attempts) - 1
                            and view.identity is not None
                        )
                        assert view.identity is not None
                        try:
                            loaded = FulltextArtifacts(store).load(
                                attempt.artifact_id, expected_identity=view.identity
                            )
                        except FulltextError as error:
                            require(
                                error.reason == "quality_failed"
                                and error.quality is not None
                            )
                            assert error.quality is not None
                            require(
                                view.quality.basis is QualityBasis.FAILED
                                and view.quality.failure
                                == error.quality.issues[0].failure
                                and attempt.failure in PERMANENT
                            )
                        else:
                            require(loaded.quality.passed and attempt.failure is None)
                            require(
                                connection.execute(
                                    select(tables.successes.c.attempt_id).where(
                                        tables.successes.c.fingerprint
                                        == row["fingerprint"]
                                    )
                                ).scalar_one_or_none()
                                == attempt.attempt_id
                            )
                        manifest = ExtractionManifest.model_validate_json(
                            store.read_artifact(attempt.artifact_id)["manifest"]
                        )
                        require(
                            manifest.backend_config_hash
                            == semantics.backend_config_hash
                            and manifest.model_artifacts_hash
                            == semantics.model_artifacts_hash
                        )
                        # manifest 转换时间在发布前采样,attempt 包含发布耗时。
                        require(
                            manifest.execution_audit == attempt.executor_audit
                            and manifest.peak_memory_bytes == attempt.peak_memory_bytes
                            and attempt.elapsed_seconds is not None
                            and manifest.elapsed_seconds <= attempt.elapsed_seconds
                        )
                    if attempt.failure in PERMANENT:
                        require(index == len(view.attempts) - 1)
            for row in connection.execute(select(tables.reviews)).mappings():
                view = extraction_view(connection, row["fingerprint"])
                require(
                    view is not None
                    and view.identity is not None
                    and view.artifact_id is not None
                )
                checks = json.loads(row["checks_json"])
                require(
                    set(checks) == LAYOUT_CHECKS
                    and all(type(v) is bool for v in checks.values())
                    and bool(row["passed"]) == all(checks.values())
                )
                required(row["note"], row["actor"])
                timestamp(row["reviewed_at"])
                require(
                    row["request_hash"]
                    == digest(
                        [
                            row["fingerprint"],
                            row["reading_sha256"],
                            row["evidence_map_sha256"],
                            bool(row["passed"]),
                            checks,
                            row["note"],
                            row["actor"],
                        ]
                    )
                )
    except BodyError:
        raise
    except (ValueError, KeyError, TypeError, AssertionError):
        raise BodyError("corrupt_reference") from None
