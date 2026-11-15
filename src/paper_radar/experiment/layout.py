"""明确正文身份的版式回查与所有者核查;不重新解析 PDF。"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from pydantic import Field
from sqlalchemy import insert, select

from paper_radar.body import BodyService
from paper_radar.body.extraction import LAYOUT_CHECKS
from paper_radar.body.models import BodyError
from paper_radar.body.repository import digest, transaction
from paper_radar.calibration import visibility
from paper_radar.experiment.candidates import SnapshotModel
from paper_radar.experiment.layout_errors import LayoutError as LayoutError
from paper_radar.experiment.layout_models import LayoutBody as LayoutBody
from paper_radar.experiment.pdf import PdfError, PdfSamples
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.models import EvidenceMap, FulltextError
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.runtime_logging import FileSink, RuntimeLog
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.schema import body_layout_reviews, experiment_layout_recordings


def _visibility(capability: visibility.VisibilityCapability) -> None:
    if (
        visibility.evaluate_visibility(frozenset()).permission(capability)
        is not visibility.VisibilityPermission.ALLOWED
    ):
        raise LayoutError("visibility_denied")


def load_body(
    database: Path, data_root: Path, paper: str, identity: ExtractionIdentity
) -> LayoutBody:
    """完整事务外预验;多成功身份仍拒绝,不把显式参数变成选定事实。"""
    samples = PdfSamples(database, data_root)
    sample = samples.require_current_sample(paper)
    body = BodyService(database, data_root)
    current = body.current_body(paper)
    if current.reason:
        raise LayoutError(current.reason)
    if current.identity != identity:
        raise LayoutError("body_identity_mismatch")
    view = next((v for v in body.extractions(paper) if v.identity == identity), None)
    if view is None or view.artifact_id is None:
        raise LayoutError("body_identity_mismatch")
    store = ArtifactStore(database, data_root)
    loaded = FulltextArtifacts(store).load(view.artifact_id, expected_identity=identity)
    evidence_map = EvidenceMap.model_validate_json(
        store.read_artifact(view.artifact_id)["evidence_map"]
    )
    pdf = next(
        (p for p in body.pdfs(paper) if p.attachment_id == sample.attachment_id), None
    )
    if pdf is None or pdf.pdf_sha256 != view.pdf_sha256:
        raise LayoutError("body_identity_mismatch")
    return LayoutBody(
        sample,
        view,
        loaded,
        evidence_map,
        store.read_artifact(pdf.artifact_id)["payload"],
    )


class ReviewRecord(SnapshotModel):
    review_id: str
    sample_id: str
    paper_id: str
    reviewer: Literal["owner"]
    recorder: Literal["agent"]
    request_id: str = Field(min_length=1, max_length=128)
    fingerprint: str
    reading_sha256: str
    evidence_map_sha256: str
    checks: dict[str, bool]
    passed: bool
    reviewed_at: str


class LayoutReviews:
    """历史回查允许标准恢复 database.sqlite3 + blobs 路径。"""

    def __init__(self, database: Path, data_root: Path) -> None:
        self.database, self.data_root = database, data_root

    def record(
        self,
        root: ExperimentRoot,
        paper: str,
        identity: ExtractionIdentity,
        *,
        checks: dict[str, bool],
        reviewer: str,
        recorder: str,
        request_id: str,
        note: str = "",
    ) -> dict[str, object]:
        root.require()
        if (root.database, root.data_root) != (self.database, self.data_root):
            raise LayoutError("root_mismatch")
        if (
            reviewer != "owner"
            or recorder != "agent"
            or set(checks) != LAYOUT_CHECKS
            or any(type(v) is not bool for v in checks.values())
            or not request_id.strip()
        ):
            raise LayoutError("owner_conclusions_required")
        log = RuntimeLog(FileSink(root.root))
        with log.execution(
            "experiment",
            controlled=(LayoutError, BodyError, PdfError, FulltextError),
            paper_id=paper,
        ):
            validated = load_body(self.database, self.data_root, paper, identity)
            _visibility(visibility.VisibilityCapability.SET_DECISION)
            body = BodyService(self.database, self.data_root)
            with transaction(self.database, write=True) as connection:
                PdfSamples(
                    self.database, self.data_root
                ).require_current_sample_in_connection(connection, validated.sample)
                if (
                    body.current_body_in_connection(connection, paper).identity
                    != identity
                ):
                    raise LayoutError("body_identity_mismatch")
                old = (
                    connection.execute(
                        select(body_layout_reviews).where(
                            body_layout_reviews.c.request_id == request_id
                        )
                    )
                    .mappings()
                    .first()
                )
                if old is not None and old["recording_kind"] != "stage_b_owner_review":
                    raise LayoutError("request_conflict")
                view = body.review_layout_in_connection(
                    connection,
                    identity,
                    passed=all(checks.values()),
                    checks=checks,
                    note=note,
                    actor=recorder,
                    request_id=request_id,
                    recording_kind="stage_b_owner_review",
                )
                row = (
                    connection.execute(
                        select(body_layout_reviews).where(
                            body_layout_reviews.c.request_id == request_id
                        )
                    )
                    .mappings()
                    .one()
                )
                record = ReviewRecord(
                    review_id=row["review_id"],
                    sample_id=validated.sample.sample_id,
                    paper_id=paper,
                    reviewer="owner",
                    recorder="agent",
                    request_id=request_id,
                    fingerprint=identity.extraction_fingerprint,
                    reading_sha256=identity.reading_sha256,
                    evidence_map_sha256=identity.evidence_map_sha256,
                    checks=checks,
                    passed=all(checks.values()),
                    reviewed_at=row["reviewed_at"],
                )
                previous = (
                    connection.execute(
                        select(experiment_layout_recordings).where(
                            experiment_layout_recordings.c.review_id == record.review_id
                        )
                    )
                    .mappings()
                    .first()
                )
                if previous is None:
                    if old is not None:
                        raise LayoutError("registration_invalid")
                    connection.execute(
                        insert(experiment_layout_recordings).values(
                            review_id=record.review_id,
                            sample_id=record.sample_id,
                            paper_id=paper,
                            record_json=record.model_dump_json(),
                        )
                    )
                elif previous["record_json"] != record.model_dump_json():
                    raise LayoutError("request_conflict")
            return dict(
                **record.model_dump(mode="json"),
                quality=view.quality.basis.value,
                quality_failure=view.quality.failure.value
                if view.quality.failure
                else None,
                replayed=old is not None,
            )

    def history(self, paper_id: str | None = None) -> tuple[dict[str, object], ...]:
        with transaction(self.database) as connection:
            reviews = {
                r["review_id"]: r
                for r in connection.execute(select(body_layout_reviews)).mappings()
            }
            rows = (
                connection.execute(
                    select(experiment_layout_recordings).order_by(
                        experiment_layout_recordings.c.review_id
                    )
                )
                .mappings()
                .all()
            )
        # 先冻结只追加的关联行,再解引用其上游闭包;并发新增不会制造缺样本。
        samples = {
            s.sample_id: s for s in PdfSamples(self.database, self.data_root).samples()
        }
        if {r["review_id"] for r in rows} != {
            key
            for key, r in reviews.items()
            if r["recording_kind"] == "stage_b_owner_review"
        }:
            raise LayoutError("registration_invalid")
        if any(
            r["recording_kind"] not in {None, "stage_b_owner_review"}
            for r in reviews.values()
        ):
            raise LayoutError("registration_invalid")
        records = []
        for row in rows:
            try:
                record = ReviewRecord.model_validate_json(row["record_json"])
                review = reviews[record.review_id]
                sample = samples[record.sample_id]
                identity = ExtractionIdentity(
                    record.fingerprint,
                    record.reading_sha256,
                    record.evidence_map_sha256,
                )
                view = next(
                    v
                    for v in BodyService(self.database, self.data_root).extractions(
                        record.paper_id
                    )
                    if v.identity == identity
                )
                expected_hash = digest(
                    [
                        record.fingerprint,
                        record.reading_sha256,
                        record.evidence_map_sha256,
                        record.passed,
                        record.checks,
                        review["note"],
                        record.recorder,
                    ]
                )
                expected_hash = digest([expected_hash, "stage_b_owner_review"])
                if (
                    record.model_dump_json() != row["record_json"]
                    or record.review_id != row["review_id"]
                    or record.paper_id != row["paper_id"]
                    or record.sample_id != row["sample_id"]
                    or sample.paper_id != record.paper_id
                    or sample.pdf_sha256 != view.pdf_sha256
                    or review["recording_kind"] != "stage_b_owner_review"
                    or review["actor"] != record.recorder
                    or review["request_id"] != record.request_id
                    or review["reviewed_at"] != record.reviewed_at
                    or (
                        review["fingerprint"],
                        review["reading_sha256"],
                        review["evidence_map_sha256"],
                    )
                    != (
                        record.fingerprint,
                        record.reading_sha256,
                        record.evidence_map_sha256,
                    )
                    or json.loads(review["checks_json"]) != record.checks
                    or bool(review["passed"]) != record.passed
                    or set(record.checks) != LAYOUT_CHECKS
                    or record.passed != all(record.checks.values())
                    or review["request_hash"] != expected_hash
                ):
                    raise ValueError
                if view.artifact_id is None:
                    raise ValueError
                FulltextArtifacts(ArtifactStore(self.database, self.data_root)).load(
                    view.artifact_id, expected_identity=identity
                )
            except (ValueError, TypeError, KeyError, StopIteration):
                raise LayoutError("registration_invalid") from None
            if paper_id is None or record.paper_id == paper_id:
                records.append(record.model_dump(mode="json"))
        return tuple(records)

    def validate_all(self) -> None:
        self.history()


class Materials:
    def __init__(self, root: ExperimentRoot) -> None:
        self.root = root

    def generate(self, paper: str, identity: ExtractionIdentity) -> dict[str, object]:
        from paper_radar.experiment.layout_rendering import render_materials

        self.root.require()
        _visibility(visibility.VisibilityCapability.AGENT_CONTENT)
        body = load_body(self.root.database, self.root.data_root, paper, identity)
        relative = render_materials(self.root, body)
        return dict(
            identity=asdict(identity),
            materials=relative,
            conclusions="owner_input_required",
        )
