"""任务专属封闭原因;不携调用方文本。"""

from enum import StrEnum

from paper_radar.stage_inputs import BuildReason, InputField

REASON_CATALOG_VERSION = 1


class TaskReason(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_CONTEXT = "invalid_context"
    CONTEXT_CONFLICT = "context_conflict"
    REQUEST_CONFLICT = "request_conflict"
    REQUEST_NOT_FOUND = "request_not_found"
    FACTS_CHANGED = "facts_changed"
    CORRUPT_REFERENCE = "corrupt_reference"
    DATABASE_BUSY = "database_busy"


GUIDANCE = {
    TaskReason.INVALID_REQUEST: "请核对受支持阶段、来源及请求字段。",
    TaskReason.INVALID_CONTEXT: "请提供严格布尔的原题名语言事实。",
    TaskReason.CONTEXT_CONFLICT: "请沿用该输入首次冻结的语言事实。",
    TaskReason.REQUEST_CONFLICT: "请为不同内容使用新的请求 ID。",
    TaskReason.REQUEST_NOT_FOUND: "请核对已登记请求的回执 ID。",
    TaskReason.FACTS_CHANGED: "论文事实已变化,请重新登记当前请求。",
    TaskReason.CORRUPT_REFERENCE: "请停止写入并检查档案库及备份。",
    TaskReason.DATABASE_BUSY: "请在其他写入结束后显式重试。",
}


class TaskError(Exception):
    def __init__(
        self,
        reason: TaskReason,
        *,
        build_reason: BuildReason | None = None,
        field: InputField | None = None,
    ) -> None:
        self.reason = reason
        self.build_reason = build_reason
        self.field = field
        super().__init__(f"{reason.value}：{GUIDANCE[reason]}")
