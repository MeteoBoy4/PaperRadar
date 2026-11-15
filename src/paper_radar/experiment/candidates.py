"""候选事实冻结与 Markdown 投影;不取得来源、不调用模型。"""

import json
import os as os  # 保留既有发布故障注入路径;helper 使用同一个 os 模块。
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_radar.calibration import visibility
from paper_radar.experiment.root import ExperimentError, ExperimentRoot
from paper_radar.feed_ingestion import JGRFeed
from paper_radar.feed_ingestion.models import FeedCheck, FeedItem
from paper_radar.feed_ingestion.parser import ParsedItem, parse_items
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.feed_metadata.models import MetadataResult
from paper_radar.feed_metadata.projection import project_metadata
from paper_radar.feed_metadata.repository import load_run, transaction
from paper_radar.papers import PaperFacts
from paper_radar.papers.conflicts import read_all
from paper_radar.papers.models import AbstractValue, RevisionView
from paper_radar.papers.queries import load_trace, resolve_revision
from paper_radar.screening_tasks.language import LanguageResolution, derive
from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.filesystem import controlled_path, publish_projection


def invalid_snapshot() -> ArtifactError:
    return ArtifactError(
        ArtifactReason.REGISTRATION_CORRUPT,
        "候选依据不完整或格式不受支持；请核对备份及原 Feed 检查。",
    )


class SnapshotModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, hide_input_in_errors=True
    )


class CandidateItem(SnapshotModel):
    position: int = Field(ge=1)
    feed_item: FeedItem
    title: str | None
    abstract: str | None
    doi: str | None
    source_url: str | None
    revision: RevisionView | None
    current_revision: RevisionView | None
    metadata: MetadataResult | None
    language: LanguageResolution | None
    conflicts: tuple[str, ...]
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.position != self.feed_item.position:
            raise ValueError("invalid position")
        if self.revision is not None:
            if (
                self.feed_item.result is None
                or self.revision.paper_id != self.feed_item.result.paper_id
            ):
                raise ValueError("invalid paper")
            if self.doi != self.revision.doi:
                raise ValueError("invalid DOI")
            if self.metadata is not None and (
                self.metadata.paper_id,
                self.metadata.version_id,
                self.metadata.revision_no,
            ) != (
                self.revision.paper_id,
                self.revision.version_id,
                self.revision.revision_no,
            ):
                raise ValueError("invalid metadata")
        return self


class CandidateSnapshot(SnapshotModel):
    domain: Literal["paper-radar.candidate-snapshot"] = "paper-radar.candidate-snapshot"
    format_version: Literal[1] = 1
    render_version: Literal[1] = 1
    check_id: str
    source_check_id: str
    feed_artifact_id: str
    parser_identity: str
    items: tuple[CandidateItem, ...]

    @model_validator(mode="after")
    def unique_order(self) -> Self:
        positions = tuple(item.position for item in self.items)
        if positions != tuple(sorted(set(positions))):
            raise ValueError("invalid order")
        return self

    def payload(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


class CandidateViews:
    """公共持久候选边界;view_id 是 candidate_snapshot 制品身份。"""

    def __init__(self, root: ExperimentRoot) -> None:
        self.root = root
        self.store = ArtifactStore(root.database, root.data_root)

    def create(self, check_id: str) -> str:
        self.root.require()
        check, basis = _checks(self.root.database, self.root.data_root, check_id)
        assert basis.artifact_id is not None
        raw = self.store.read_artifact(basis.artifact_id)["payload"]
        parsed = parse_items(
            raw, basis.content_decoding or "utf-8", parser_version=basis.parser_version
        )
        if len(parsed) != len(basis.items):
            raise invalid_snapshot()
        metadata_service = JGRMetadata(self.root.database, self.root.data_root)
        items = []
        # 全部当前展示依据在同一个只读数据库视图内固定。
        with transaction(self.root.database) as connection:
            for item, source in zip(basis.items, parsed, strict=True):
                revision = None
                current_revision = None
                metadata = None
                language = None
                conflicts: tuple[str, ...] = ()
                result = item.result
                if result is not None and result.paper_id is not None:
                    current = load_trace(connection, result.paper_id).current
                    current_revision = resolve_revision(
                        connection,
                        version_id=current.version_id,
                        revision_no=current.revision_no,
                    )
                    metadata = metadata_service.result_in_connection(
                        connection, result.paper_id
                    )
                    revision = resolve_revision(
                        connection,
                        version_id=metadata.version_id
                        if metadata
                        else current.version_id,
                        revision_no=metadata.revision_no
                        if metadata
                        else current.revision_no,
                    )
                    language = derive(connection, result.paper_id, "v1")
                    conflicts = tuple(
                        value.conflict_id
                        for value in read_all(
                            connection,
                            self.root.database,
                            self.root.data_root,
                            paper_id=result.paper_id,
                        )
                    )
                items.append(
                    _candidate(
                        item,
                        source,
                        revision,
                        metadata,
                        language,
                        conflicts,
                        current_revision,
                    )
                )
        snapshot = CandidateSnapshot(
            check_id=check.check_id,
            source_check_id=basis.check_id,
            feed_artifact_id=basis.artifact_id,
            parser_identity=basis.parser_identity,
            items=tuple(items),
        )
        return self.store.publish_single(
            "candidate_snapshot", [snapshot.payload()]
        ).artifact_id

    def load(self, view_id: str) -> CandidateSnapshot:
        self.root.require()
        return load_candidate_snapshot(self.root.database, self.root.data_root, view_id)

    def render(self, view_id: str) -> dict[str, str | int]:
        snapshot = self.load(view_id)
        # 当前没有隐藏事实生产者;空集合仍必须实际调用共享 visibility。
        permission = visibility.evaluate_visibility(frozenset()).permission(
            visibility.VisibilityCapability.PAPER_FACTS
        )
        if permission is not visibility.VisibilityPermission.ALLOWED:
            raise invalid_snapshot()
        text = _markdown(snapshot, view_id).encode()
        relative = f"views/candidates/{view_id}.md"
        try:
            path = controlled_path(
                self.root.root,
                relative,
                create_directory=lambda directory: directory.mkdir(
                    mode=0o700, exist_ok=True
                ),
            )
            publish_projection(path, text, prefix=".candidate-")
        except (OSError, ValueError):
            raise ExperimentError("unsafe_layout") from None
        return dict(
            view_id=view_id,
            check_id=snapshot.check_id,
            source_check_id=snapshot.source_check_id,
            count=len(snapshot.items),
            view=relative,
        )

    def validate_all(self) -> None:
        self.root.require()
        validate_candidate_snapshots(self.root.database, self.root.data_root)


def _checks(
    database: Path, data_root: Path, check_id: str
) -> tuple[FeedCheck, FeedCheck]:
    feed = JGRFeed(database, data_root)
    check = basis = feed.replay(check_id)
    seen = {basis.check_id}
    while basis.status_code == 304:
        if basis.prior_check_id is None or basis.prior_check_id in seen:
            raise invalid_snapshot()
        basis = feed.replay(basis.prior_check_id)
        seen.add(basis.check_id)
    if basis.reason != "acquired" or basis.artifact_id is None:
        raise invalid_snapshot()
    return check, basis


def load_candidate_snapshot(
    database: Path, data_root: Path, view_id: str
) -> CandidateSnapshot:
    store = ArtifactStore(database, data_root)
    record = store.get_artifact(view_id)
    if record.kind != "candidate_snapshot":
        raise invalid_snapshot()
    raw = store.read_artifact(view_id)["payload"]
    try:
        snapshot = CandidateSnapshot.model_validate_json(raw)
    except (ValueError, TypeError):
        raise invalid_snapshot() from None
    _, basis = _checks(database, data_root, snapshot.check_id)
    if (
        (
            snapshot.source_check_id,
            snapshot.feed_artifact_id,
            snapshot.parser_identity,
        )
        != (basis.check_id, basis.artifact_id, basis.parser_identity)
        or tuple(item.feed_item for item in snapshot.items) != basis.items
        or raw != snapshot.payload()
    ):
        raise invalid_snapshot()
    papers = PaperFacts(database, data_root)
    metadata = JGRMetadata(database, data_root)
    assert basis.artifact_id is not None
    parsed = parse_items(
        store.read_artifact(basis.artifact_id)["payload"],
        basis.content_decoding or "utf-8",
        parser_version=basis.parser_version,
    )
    for item, source in zip(snapshot.items, parsed, strict=True):
        if (
            item.revision is not None
            and papers.revision(item.revision.version_id, item.revision.revision_no)
            != item.revision
        ):
            raise invalid_snapshot()
        if (
            item.current_revision is not None
            and papers.revision(
                item.current_revision.version_id, item.current_revision.revision_no
            )
            != item.current_revision
        ):
            raise invalid_snapshot()
        if item.metadata is not None:
            request = metadata.replay(item.metadata.request_key)
            if (request.paper_id, request.version_id) != (
                item.metadata.paper_id,
                item.metadata.version_id,
            ):
                raise invalid_snapshot()
            if item.revision is None or item.current_revision is None:
                raise invalid_snapshot()
            with transaction(database) as connection:
                basis_fact, _ = load_run(connection, item.metadata.request_key)
            projected = project_metadata(
                item.metadata.request_key,
                basis_fact,
                item.revision,
                item.current_revision,
                item.metadata.routes,
                item.metadata.revision_no if item.metadata.routes_settled else None,
            )
            if projected != item.metadata:
                raise invalid_snapshot()
        if (
            _candidate(
                item.feed_item,
                source,
                item.revision,
                item.metadata,
                item.language,
                item.conflicts,
                item.current_revision,
            )
            != item
        ):
            raise invalid_snapshot()
    return snapshot


def validate_candidate_snapshots(database: Path, data_root: Path) -> None:
    """显式库路径的 B 聚合接缝;不要求备份或恢复库采用实验命令文件名。"""
    for artifact in ArtifactStore(database, data_root).list_artifacts():
        if artifact.kind == "candidate_snapshot":
            load_candidate_snapshot(database, data_root, artifact.artifact_id)


def _candidate(
    item: FeedItem,
    source: ParsedItem,
    revision: RevisionView | None,
    metadata: MetadataResult | None,
    language: LanguageResolution | None,
    conflicts: tuple[str, ...],
    current_revision: RevisionView | None,
) -> CandidateItem:
    fields = revision.fields if revision else source.fields
    title = fields.get("title")
    abstract = fields.get("abstract")
    url = fields.get("source_url")
    feed_url = source.fields.get("source_url")
    abstract_value = (
        abstract.value
        if abstract and isinstance(abstract.value, AbstractValue)
        else None
    )
    reasons = []
    if item.reason is not None:
        reasons.append(str(item.reason))
    if metadata is None:
        reasons.append("metadata_missing")
    else:
        reasons.extend(metadata.missing)
    if abstract_value is not None and abstract_value.is_truncated is not False:
        reasons.append(
            "suspected_truncated"
            if abstract_value.is_truncated
            else "unknown_truncation"
        )
    if language is None or language["status"] != "resolved":
        reasons.append("language_unresolved")
    result = item.result
    all_conflicts = tuple(
        sorted(
            set(
                conflicts
                + ((result.conflict_id,) if result and result.conflict_id else ())
            )
        )
    )
    if all_conflicts:
        reasons.append("identity_conflict")
    source_url = (
        feed_url.value
        if feed_url and isinstance(feed_url.value, str)
        else source.candidate.publisher_url
    )
    if source_url is None and url and isinstance(url.value, str):
        source_url = url.value
    return CandidateItem(
        position=item.position,
        feed_item=item,
        title=title.value if title and isinstance(title.value, str) else None,
        abstract=abstract_value.text if abstract_value else None,
        doi=revision.doi if revision else item.doi,
        source_url=source_url,
        revision=revision,
        current_revision=current_revision,
        metadata=metadata,
        language=language,
        conflicts=all_conflicts,
        reasons=tuple(sorted(set(reasons))),
    )


def _markdown(snapshot: CandidateSnapshot, view_id: str) -> str:
    lines = [
        "# 实验候选清单",
        "",
        f"视图：`{view_id}`",
        f"Feed 检查：`{snapshot.check_id}`；成员依据：`{snapshot.source_check_id}`",
        "",
        "此私有视图固定事实修订；不调用模型、不占自动配额。选样前须重新核对当前就绪条件。",
        "",
    ]
    for item in snapshot.items:
        metadata = item.metadata
        minimum = "就绪" if metadata and metadata.minimum_complete else "未就绪"
        abstract_status = (
            "非截断"
            if metadata and metadata.nontruncated_complete
            else "缺失或非截断依据未就绪"
        )
        current = "是" if metadata and metadata.current_version else "未就绪"
        language = item.language["status"] if item.language else "missing"
        lines.extend(
            [
                f"## {item.position}. {item.title or '（缺少原题名）'}",
                "",
                f"DOI：{item.doi or '缺失'}",
                f"原文链接：{item.source_url or '缺失'}",
                f"最低元数据：{minimum}",
                f"主摘要：{abstract_status}",
                f"当前版本：{current}",
                f"语言：{language}（JGR false 只表示非中文）",
                f"强冲突：{'、'.join(item.conflicts) or '无'}",
                f"就绪：{'否' if item.reasons else '是'}",
                f"原因：{'、'.join(item.reasons) or '无'}",
            ]
        )
        if item.revision is not None:
            lines.append(
                f"版本／修订：`{item.revision.version_id}`"
                f" / {item.revision.revision_no}"
            )
        if metadata is not None:
            lines.append(f"元数据请求：`{metadata.request_key}`")
        lines.extend(
            [
                "",
                "### 完整主摘要（来源语言）",
                "",
                item.abstract
                if item.abstract is not None
                else "未取得主摘要；不生成替代文本。",
                "",
                "下一步："
                + (
                    "先补齐元数据／非截断摘要、核对版本与语言、处理强冲突，再生成新视图并选样。"
                    if item.reasons
                    else "按本检查原编号或 DOI 选样；选样时重新核对当前依据。"
                ),
                "",
            ]
        )
    return "\n".join(lines)
