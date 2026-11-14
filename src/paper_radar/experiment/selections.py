"""选样即接受授权:只追加单链,不创建决定、任务或模型许可。"""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from sqlalchemy import Connection, insert, select

from paper_radar.body.queries import root_fact
from paper_radar.calibration import visibility
from paper_radar.eligibility import RootPurpose
from paper_radar.experiment.candidates import (
    CandidateItem,
    SnapshotModel,
    load_candidate_snapshot,
)
from paper_radar.experiment.root import ExperimentError
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.feed_metadata.repository import canonical, sha, transaction
from paper_radar.papers.conflicts import read_all
from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.queries import load_trace, resolve_revision
from paper_radar.screening_tasks.language import derive
from paper_radar.storage.history import (
    HistoryBoundary,
    HistoryKeys,
    HistoryPage,
    history_boundaries,
    history_page,
)
from paper_radar.storage.schema import experiment_selections


class SelectionError(ValueError):
    def __init__(self, reason: str, differences: tuple[str, ...] = ()) -> None:
        self.reason = reason
        self.differences = differences
        guidance = {
            "invalid_request": (
                "请提供视图、唯一编号或 DOI、原文理由及 owner/agent 录入者。"
            ),
            "candidate_not_found": "请从该检查的候选视图选择唯一编号或 DOI。",
            "candidate_not_ready": (
                "请补齐元数据、非截断摘要与语言并处理冲突，再生成新视图。"
            ),
            "basis_changed": "所见依据已变化；请生成新候选视图，由所有者重新选样。",
            "request_conflict": (
                "同一 request 内容不同；请回查原授权，新的选择使用新 request。"
            ),
            "replacement_required": (
                "已有有效选择；请显式引用当前 selection-id 并填写换样理由。"
            ),
            "selection_changed": (
                "当前选择已变化；请回查 selection 后重新作出换样决定。"
            ),
            "visibility_denied": (
                "共享 visibility 拒绝普通决定动作；请先完成专用校准流程。"
            ),
            "registration_invalid": "选样授权登记不完整或被篡改；请核对可信备份。",
            "invalid_clock": "时钟必须提供带时区的 UTC 时间；请修正时钟后重试。",
        }
        suffix = f"（{','.join(differences)}）" if differences else ""
        super().__init__(f"{reason}{suffix}：{guidance[reason]}")


class SelectionRequest(SnapshotModel):
    view_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1, max_length=128)
    position: int | None = Field(default=None, ge=1)
    doi: str | None = None
    reason: str = Field(min_length=1, repr=False)
    authorizer: Literal["owner"] = "owner"
    actor: Literal["owner", "agent"]
    replaces: str | None = None
    replacement_reason: str | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def valid_action(self) -> Self:
        if (
            (self.position is None) == (self.doi is None)
            or not self.reason.strip()
            or not self.request_id.strip()
            or (self.replaces is None and self.replacement_reason is not None)
            or (
                self.replaces is not None
                and not (self.replacement_reason and self.replacement_reason.strip())
            )
        ):
            raise ValueError("invalid_request")
        return self


class SelectionRecord(SnapshotModel):
    selection_id: str
    sequence: int
    root_id: str
    request: SelectionRequest
    check_id: str
    source_check_id: str
    position: int
    discovery_id: str
    paper_id: str
    version_id: str
    revision_no: int
    doi: str | None
    metadata_request_key: str
    selected_at: str


def _item(request: SelectionRequest, items: tuple[CandidateItem, ...]) -> CandidateItem:
    matches = [
        i
        for i in items
        if (
            i.position == request.position
            if request.position is not None
            else i.doi == request.doi
        )
    ]
    if len(matches) != 1:
        raise SelectionError("candidate_not_found")
    return matches[0]


def _ready(item: CandidateItem) -> bool:
    metadata = item.metadata
    return bool(
        item.revision
        and item.current_revision
        and metadata
        and metadata.minimum_complete
        and metadata.nontruncated_complete
        and metadata.current_version
        and metadata.routes_settled
        and not metadata.missing
        and not item.reasons
        and not item.conflicts
        and item.language
        and item.language["status"] == "resolved"
        and item.feed_item.result
        and item.feed_item.result.discovery_id
    )


def _check_current(
    connection: Connection, database: Path, data_root: Path, item: CandidateItem
) -> None:
    assert item.revision is not None and item.current_revision is not None
    paper_id = item.revision.paper_id
    trace = load_trace(connection, paper_id)
    current = resolve_revision(
        connection,
        version_id=trace.current.version_id,
        revision_no=trace.current.revision_no,
    )
    metadata = JGRMetadata(database, data_root).result_in_connection(
        connection, paper_id
    )
    language = derive(connection, paper_id, "v1")
    conflicts = tuple(
        value.conflict_id
        for value in read_all(connection, database, data_root, paper_id=paper_id)
    )
    differences = []
    if current != item.current_revision:
        differences.append(
            "version_changed"
            if current.version_id != item.current_revision.version_id
            else "revision_changed"
        )
    if metadata != item.metadata:
        differences.append("metadata_changed")
    if language != item.language:
        differences.append("language_changed")
    if conflicts != item.conflicts:
        differences.append("conflict_changed")
    if differences:
        raise SelectionError("basis_changed", tuple(differences))


class Selections:
    """显式 database/data_root 支持恢复副本查询;clock 仅供受控测试注入。"""

    def exposure_scope_in_connection(
        self, connection: Connection
    ) -> dict[str, HistoryBoundary]:
        """短写事务使用的只读事件范围元数据;不加载历史或文件。"""
        return history_boundaries(connection, (experiment_selections,))

    def exposure_history_in_connection(
        self, connection: Connection, through: dict[str, HistoryKeys] | None = None
    ) -> tuple[HistoryPage, ...]:
        """持久历史安全投影;保留全部事件,与当前执行资格无关。"""
        return (
            history_page(
                connection,
                experiment_selections,
                ("sequence", "selection_id", "paper_id", "version_id", "record_json"),
                through=through,
                hashed=("record_json",),
            ),
        )

    def __init__(
        self,
        database: Path,
        data_root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database = database
        self.data_root = data_root
        self.clock = clock or (lambda: datetime.now(UTC))

    def history_in_connection(
        self, connection: Connection
    ) -> tuple[SelectionRecord, ...]:
        registered = root_fact(connection)
        records: list[SelectionRecord] = []
        for row in connection.execute(
            select(experiment_selections).order_by(experiment_selections.c.sequence)
        ).mappings():
            try:
                record = SelectionRecord.model_validate_json(row["record_json"])
                request = record.request
                snapshot = load_candidate_snapshot(
                    self.database, self.data_root, request.view_id
                )
                item = _item(request, snapshot.items)
                revision = item.revision
                expected = record.model_dump(mode="json", exclude={"selection_id"})
                if (
                    registered.purpose is not RootPurpose.EXPERIMENT
                    or record.root_id != registered.root_id
                    or record.sequence != len(records) + 1
                    or request.replaces
                    != (records[-1].selection_id if records else None)
                    or (
                        bool(records)
                        != bool(
                            request.replacement_reason
                            and request.replacement_reason.strip()
                        )
                    )
                    or not request.reason.strip()
                    or not _ready(item)
                    or revision is None
                    or item.metadata is None
                    or item.feed_item.result is None
                    or (
                        record.check_id,
                        record.source_check_id,
                        record.position,
                        record.discovery_id,
                        record.paper_id,
                        record.version_id,
                        record.revision_no,
                        record.doi,
                        record.metadata_request_key,
                    )
                    != (
                        snapshot.check_id,
                        snapshot.source_check_id,
                        item.position,
                        item.feed_item.result.discovery_id,
                        revision.paper_id,
                        revision.version_id,
                        revision.revision_no,
                        item.doi,
                        item.metadata.request_key,
                    )
                    or record.selection_id != sha(canonical(expected))
                    or (
                        row["selection_id"],
                        row["sequence"],
                        row["request_id"],
                        row["replaces"],
                        row["view_id"],
                        row["paper_id"],
                        row["version_id"],
                    )
                    != (
                        record.selection_id,
                        record.sequence,
                        request.request_id,
                        request.replaces,
                        request.view_id,
                        record.paper_id,
                        record.version_id,
                    )
                    or row["record_json"] != canonical(record.model_dump(mode="json"))
                    or datetime.fromisoformat(record.selected_at).utcoffset()
                    != UTC.utcoffset(None)
                ):
                    raise ValueError
            except (ValueError, TypeError, KeyError, AttributeError):
                raise SelectionError("registration_invalid") from None
            records.append(record)
        return tuple(records)

    def current_in_connection(self, connection: Connection) -> SelectionRecord | None:
        """下游领取短事务内重读当前授权;不代表 Screening/Read 已获执行许可。"""
        records = self.history_in_connection(connection)
        return records[-1] if records else None

    def require_current_in_connection(
        self, connection: Connection, validated: SelectionRecord
    ) -> None:
        """复核事务外完整预验的不可变授权;只读当前行与根,无制品/文件 I/O。"""
        registered = root_fact(connection)
        row = (
            connection.execute(
                select(experiment_selections)
                .order_by(experiment_selections.c.sequence.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if row is None or row["selection_id"] != validated.selection_id:
            raise SelectionError("selection_changed")
        if (
            registered.purpose is not RootPurpose.EXPERIMENT
            or registered.root_id != validated.root_id
            or row["record_json"] != canonical(validated.model_dump(mode="json"))
            or row["sequence"] != validated.sequence
            or row["paper_id"] != validated.paper_id
            or row["version_id"] != validated.version_id
            or row["request_id"] != validated.request.request_id
            or row["replaces"] != validated.request.replaces
            or row["view_id"] != validated.request.view_id
        ):
            raise SelectionError("registration_invalid")

    def history(self) -> tuple[SelectionRecord, ...]:
        with transaction(self.database) as connection:
            return self.history_in_connection(connection)

    def select(self, **values: object) -> tuple[SelectionRecord, bool]:
        try:
            request = SelectionRequest.model_validate(values)
            if (request.position is None) == (
                request.doi is None
            ) or not request.reason.strip():
                raise ValueError
            if request.doi is not None:
                request = request.model_copy(update={"doi": normalize_doi(request.doi)})
            if request.replaces is None and request.replacement_reason is not None:
                raise ValueError
            if request.replaces is not None and not (
                request.replacement_reason and request.replacement_reason.strip()
            ):
                raise ValueError
        except ValueError:
            raise SelectionError("invalid_request") from None
        # 普通决定动作在打开写事务之前检查;当前尚无隐藏事实生产者。
        permission = visibility.evaluate_visibility(frozenset()).permission(
            visibility.VisibilityCapability.SET_DECISION
        )
        if permission is not visibility.VisibilityPermission.ALLOWED:
            raise SelectionError("visibility_denied")
        # 先只读核对请求身份,异内容不能因新视图不存在而变成另一类错误。
        # 写锁内仍重复检查,以处理两个并发新 request 的竞争。
        for old in self.history():
            if old.request.request_id == request.request_id:
                if old.request != request:
                    raise SelectionError("request_conflict")
                return old, True
        snapshot = load_candidate_snapshot(
            self.database, self.data_root, request.view_id
        )
        with transaction(self.database, write=True) as connection:
            registered = root_fact(connection)
            if registered.purpose is not RootPurpose.EXPERIMENT:
                raise ExperimentError("root_not_experiment")
            history = self.history_in_connection(connection)
            for old in history:
                if old.request.request_id == request.request_id:
                    if old.request != request:
                        raise SelectionError("request_conflict")
                    return old, True
            current = history[-1] if history else None
            if current is not None and request.replaces is None:
                raise SelectionError("replacement_required")
            if request.replaces != (current.selection_id if current else None):
                raise SelectionError("selection_changed")
            item = _item(request, snapshot.items)
            if not _ready(item):
                raise SelectionError("candidate_not_ready")
            _check_current(connection, self.database, self.data_root, item)
            now = self.clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise SelectionError("invalid_clock")
            assert (
                registered.root_id
                and item.revision
                and item.metadata
                and item.feed_item.result
            )
            payload = dict(
                sequence=len(history) + 1,
                root_id=registered.root_id,
                request=request.model_dump(mode="json"),
                check_id=snapshot.check_id,
                source_check_id=snapshot.source_check_id,
                position=item.position,
                discovery_id=item.feed_item.result.discovery_id,
                paper_id=item.revision.paper_id,
                version_id=item.revision.version_id,
                revision_no=item.revision.revision_no,
                doi=item.doi,
                metadata_request_key=item.metadata.request_key,
                selected_at=now.astimezone(UTC).isoformat(),
            )
            record = SelectionRecord.model_validate(
                {"selection_id": sha(canonical(payload)), **payload}
            )
            connection.execute(
                insert(experiment_selections).values(
                    sequence=record.sequence,
                    selection_id=record.selection_id,
                    request_id=request.request_id,
                    replaces=request.replaces,
                    view_id=request.view_id,
                    paper_id=record.paper_id,
                    version_id=record.version_id,
                    record_json=canonical(record.model_dump(mode="json")),
                )
            )
            return record, False

    def validate_all(self) -> None:
        self.history()


def receipt(record: SelectionRecord, *, replayed: bool = False) -> dict[str, object]:
    return dict(
        selection_id=record.selection_id,
        root_id=record.root_id,
        view_id=record.request.view_id,
        check_id=record.check_id,
        position=record.position,
        discovery_id=record.discovery_id,
        paper_id=record.paper_id,
        version_id=record.version_id,
        revision_no=record.revision_no,
        doi=record.doi,
        authorizer=record.request.authorizer,
        actor=record.request.actor,
        replaces=record.request.replaces,
        selected_at=record.selected_at,
        replayed=replayed,
    )
