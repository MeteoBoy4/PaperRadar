"""根中性的论文工作流只读组合;组件当前性与资格各由原权威计算。"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from paper_radar.body import BodyService
from paper_radar.body.models import RootRegistration
from paper_radar.calibration import visibility
from paper_radar.eligibility import (
    ArtifactFact,
    Concept,
    Eligibility,
    PaperProjection,
    Presence,
    ScreeningTaskFacts,
    evaluate_paper,
)
from paper_radar.experiment.acceptance import Acceptances
from paper_radar.experiment.acceptance import receipt as acceptance_receipt
from paper_radar.experiment.extraction import Extractions, extraction_payload
from paper_radar.experiment.pdf import PdfSamples
from paper_radar.experiment.pdf import receipt as pdf_receipt
from paper_radar.experiment.selections import Selections
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.feed_pipeline import FeedPipeline
from paper_radar.feed_pipeline.models import PipelineTrace
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks, TaskError, TaskReason
from paper_radar.screening_tasks.query_models import TaskQueryResult
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


@dataclass(frozen=True)
class SelectionReference:
    selection_id: str
    paper_id: str
    version_id: str
    revision_no: int
    replaces: str | None
    authorizer: str
    actor: str
    current: bool
    selected_at: str


@dataclass(frozen=True)
class AgentContent:
    success_id: str
    stage: str
    output: dict[str, object]


@dataclass(frozen=True)
class PaperWorkflowTrace:
    root: RootRegistration
    feed: PipelineTrace
    selections: tuple[SelectionReference, ...]
    screening: tuple[TaskQueryResult, ...]
    projection: PaperProjection
    eligibility: dict[Concept, Eligibility]
    agent_content: tuple[AgentContent, ...] = ()
    delegated_acceptances: tuple[dict[str, object], ...] = ()
    pdfs: tuple[dict[str, object], ...] = ()
    pdf_confirmations: tuple[dict[str, object], ...] = ()
    frozen_samples: tuple[dict[str, object], ...] = ()
    extractions: tuple[dict[str, object], ...] = ()
    bounded_executions: tuple[dict[str, object], ...] = ()
    scope: str = (
        "前置通过不代表名额、预算或领取许可；各组件独立只读视图，允许并发滞后。"
        "Screening 需显式 --snapshot；代执行接受依预先选样授权，"
        "不声称所有者看过模型输出。"
        "PDF 归属与合法性确认独立保存；冻结样本理由仅引用选样。"
        "PDF 确认不替代六项版式核查；Read/报告由后续组合承接。"
    )

    def safe_payload(self) -> dict[str, object]:
        # 资格只展示结果/原因/支持范围,不隐式展开决定或完整内部输入。
        payload = asdict(self)
        del payload["projection"]
        payload["eligibility"] = {
            concept.value: dict(
                eligible=result.eligible,
                reasons=[reason.value for reason in result.reasons],
                support=result.support.value,
                scope=result.scope,
                owner=result.owner,
            )
            for concept, result in self.eligibility.items()
        }
        return payload


def query_paper_trace(
    database: Path,
    data_root: Path,
    paper_id: str,
    *,
    snapshot_id: str | None = None,
    include_agent_content: bool = False,
) -> PaperWorkflowTrace:
    """默认安全投影;模型结构结果仅在显式许可后读取。"""
    current = PaperFacts(database, data_root).show(paper_id)
    permissions = visibility.evaluate_visibility(frozenset())
    if (
        include_agent_content
        and permissions.permission(visibility.VisibilityCapability.AGENT_CONTENT)
        is not visibility.VisibilityPermission.ALLOWED
    ):
        raise TaskError(TaskReason.VISIBILITY_DENIED)
    if include_agent_content and not snapshot_id:
        raise TaskError(TaskReason.INVALID_REQUEST)
    body = BodyService(database, data_root)
    root = body.root()
    feed = FeedPipeline(database, data_root).trace(paper_id)
    selections = Selections(database, data_root).history()
    tasks = ScreeningTasks(database, data_root, clock=lambda: datetime.now(UTC))
    queries = (
        tuple(
            tasks.query(paper_id=paper_id, stage=stage, snapshot_id=snapshot_id)
            for stage in ("boundary", "value")
        )
        if snapshot_id
        else ()
    )
    engine = open_database(database, mode=DatabaseMode.READ_ONLY)
    try:
        require_current_revision(engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            metadata = JGRMetadata(database, data_root).facts_in_connection(
                connection, paper_id
            )
    finally:
        engine.dispose()
    artifact = (
        ArtifactFact(Presence.ABSENT)
        if queries and queries[1].reason is None
        else ArtifactFact()
    )
    if snapshot_id:
        # value 成功是筛选制品;boundary 单阶段成功不伪装成完整建议/决定。
        successes = tasks.query_successes(
            paper_id=paper_id, stage="value", snapshot_id=snapshot_id
        )
        chosen = next(
            (item for item in successes if item.applicability == "current"),
            successes[-1] if successes else None,
        )
        if chosen is not None:
            claim_version = next(
                (
                    attempt.version_id
                    for budget in queries[1].budgets
                    for task in budget.tasks
                    for attempt in task.attempts
                    if attempt.success_id == chosen.receipt.success_id
                ),
                None,
            )
            if claim_version is None:
                raise TaskError(TaskReason.CORRUPT_REFERENCE)
            artifact = ArtifactFact.from_success(chosen, version_id=claim_version)
    projection = PaperProjection(
        paper_id,
        current.version_id,
        current.version_id,
        canonical_id=paper_id,
        revision_no=current.revision_no,
        metadata=metadata,
        decisions=tuple(item.fact for item in body.decisions(paper_id)),
        root_purpose=root.purpose,
        visibility=permissions,
        screening=artifact,
        screening_tasks=ScreeningTaskFacts.from_queries(paper_id, queries)
        if snapshot_id
        else None,
    )
    agent_content = []
    if include_agent_content and snapshot_id:
        for stage in ("boundary", "value"):
            for success in tasks.query_successes(
                paper_id=paper_id, stage=stage, snapshot_id=snapshot_id
            ):
                content = tasks.load_success(success.receipt.success_id)
                agent_content.append(
                    AgentContent(
                        content.receipt.success_id,
                        stage,
                        content.output.model_dump(mode="json"),
                    )
                )
    pdf_samples = PdfSamples(database, data_root)
    return PaperWorkflowTrace(
        root,
        feed,
        tuple(
            SelectionReference(
                item.selection_id,
                item.paper_id,
                item.version_id,
                item.revision_no,
                item.request.replaces,
                item.request.authorizer,
                item.request.actor,
                item == selections[-1],
                item.selected_at,
            )
            for item in selections
        ),
        queries,
        projection,
        evaluate_paper(projection),
        tuple(agent_content),
        tuple(
            acceptance_receipt(record)
            for record in Acceptances(database, data_root).history()
            if record.request.paper_id == paper_id
        ),
        pdfs=tuple(asdict(pdf) for pdf in body.pdfs(paper_id)),
        pdf_confirmations=tuple(
            pdf_receipt(record)
            for record in pdf_samples.history()
            if record.request.paper_id == paper_id
        ),
        frozen_samples=tuple(
            sample.model_dump(mode="json")
            for sample in pdf_samples.samples()
            if sample.paper_id == paper_id
        ),
        extractions=tuple(
            extraction_payload(view) for view in body.extractions(paper_id)
        ),
        bounded_executions=Extractions(database, data_root).history(paper_id),
    )
