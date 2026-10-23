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
    INVALID_CLOCK = "invalid_clock"
    TASK_RUNNING = "task_running"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_CREDENTIAL = "invalid_credential"
    SETTLEMENT_CONFLICT = "settlement_conflict"
    INVALID_FAILURE = "invalid_failure"
    INVALID_CANDIDATE = "invalid_candidate"
    ALREADY_SUCCEEDED = "already_succeeded"
    SUCCESS_NOT_FOUND = "success_not_found"
    DATA_ROOT_REQUIRED = "data_root_required"


GUIDANCE = {
    TaskReason.INVALID_CANDIDATE: "请提交受支持的原始响应和执行审计字段。",
    TaskReason.ALREADY_SUCCEEDED: "该输入已有成功筛选制品。",
    TaskReason.SUCCESS_NOT_FOUND: "请核对筛选制品 ID。",
    TaskReason.DATA_ROOT_REQUIRED: "请显式提供制品根目录。",
    TaskReason.INVALID_REQUEST: "请核对受支持阶段、来源及请求字段。",
    TaskReason.INVALID_CONTEXT: "请提供严格布尔的原题名语言事实。",
    TaskReason.CONTEXT_CONFLICT: "请沿用该输入首次冻结的语言事实。",
    TaskReason.REQUEST_CONFLICT: "请为不同内容使用新的请求 ID。",
    TaskReason.REQUEST_NOT_FOUND: "请核对已登记请求的回执 ID。",
    TaskReason.FACTS_CHANGED: "论文事实已变化,请重新登记当前请求。",
    TaskReason.CORRUPT_REFERENCE: "请停止写入并检查档案库及备份。",
    TaskReason.DATABASE_BUSY: "请在其他写入结束后显式重试。",
    TaskReason.INVALID_CLOCK: "请为执行操作注入有效的 UTC 时钟。",
    TaskReason.TASK_RUNNING: "任务已有未结算的有效租约。",
    TaskReason.BUDGET_EXHAUSTED: "该任务代际的两次尝试预算已用尽。",
    TaskReason.INVALID_CREDENTIAL: "领取凭据无效或该尝试已结算。",
    TaskReason.SETTLEMENT_CONFLICT: "该尝试已提交不同的结算事实。",
    TaskReason.INVALID_FAILURE: "请使用受支持的执行失败类别。",
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
