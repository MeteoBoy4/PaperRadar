"""Fixture 与摘要审计的安全受控错误。"""

from enum import StrEnum


class FixtureReason(StrEnum):
    ROUTE_ALREADY_SETTLED = "route_already_settled"
    UNSUPPORTED_HISTORY = "unsupported_history"
    INVALID_DECLARATION = "invalid_declaration"
    UNSUPPORTED_FORMAT = "unsupported_format"
    DECLARATION_CONFLICT = "declaration_conflict"
    SOURCE_UNAVAILABLE = "source_unavailable"
    RECORD_NOT_FOUND = "record_not_found"
    INVALID_REFERENCE = "invalid_reference"
    EVIDENCE_REQUIRED = "evidence_required"
    CORRUPT_REFERENCE = "corrupt_reference"
    DATABASE_BUSY = "database_busy"
    INVALID_CONTACT = "invalid_contact"
    INVALID_PLAN = "invalid_plan"
    INVALID_FEED = "invalid_feed"
    PLAN_IDENTITY_MISMATCH = "plan_identity_mismatch"
    PLAN_CONFLICT = "plan_conflict"
    INVALID_REQUEST = "invalid_request"
    REQUEST_CONFLICT = "request_conflict"
    EXECUTION_BUSY = "execution_busy"
    EXECUTION_INCOMPLETE = "execution_incomplete"
    RESULT_CONFLICT = "result_conflict"


_GUIDANCE = {
    FixtureReason.ROUTE_ALREADY_SETTLED: (
        "该计划路线已结算；复查请新建计划，继续请使用显式 resume"
    ),
    FixtureReason.UNSUPPORTED_HISTORY: (
        "不支持该历史规则或解释版本；请使用匹配版本的程序或显式提供对应解析器"
    ),
    FixtureReason.INVALID_FEED: "Feed结构、编码或XML声明不支持；请核对材料并新建计划",
    FixtureReason.PLAN_IDENTITY_MISMATCH: "执行代码或规则与计划不符；请新建计划",
    FixtureReason.INVALID_CONTACT: "邮箱缺失或非法；请显式提供 --contact-email",
    FixtureReason.INVALID_PLAN: "审计计划参数不合法；请核对 N=5–10 与规则版本",
    FixtureReason.PLAN_CONFLICT: "计划键已绑定其他内容；请新建计划",
    FixtureReason.INVALID_REQUEST: "来源请求不合法；请核对受控路线",
    FixtureReason.REQUEST_CONFLICT: "请求键已冻结其他内容、策略或通道；请新建计划",
    FixtureReason.EXECUTION_BUSY: "本计划已有执行者；请等待其退出后显式继续",
    FixtureReason.EXECUTION_INCOMPLETE: "路线未结算；请保留未知结果并显式 resume",
    FixtureReason.RESULT_CONFLICT: "结算与既有事实不一致；请核对历史，不能覆盖",
    FixtureReason.INVALID_DECLARATION: "声明字段不合法；请核对格式和字段路径后重交",
    FixtureReason.UNSUPPORTED_FORMAT: "声明格式版本不支持；请使用 format_version=1",
    FixtureReason.DECLARATION_CONFLICT: "同键声明原字节已冻结；请新建声明版本",
    FixtureReason.SOURCE_UNAVAILABLE: "声明文件无法读取；请核对文件位置和权限",
    FixtureReason.RECORD_NOT_FOUND: "登记记录不存在；请核对 ID 或先显式 register",
    FixtureReason.INVALID_REFERENCE: "替换或证据引用无效；请引用同逻辑样本的当前记录",
    FixtureReason.EVIDENCE_REQUIRED: "缺少已核验取得证据；请使用实际取得登记入口",
    FixtureReason.CORRUPT_REFERENCE: "登记历史或原字节损坏；请检查完整备份",
    FixtureReason.DATABASE_BUSY: "数据库正忙；请等待写入结束后显式重试",
}


class FixtureError(Exception):
    def __init__(self, reason: FixtureReason, *, path: str = "declaration") -> None:
        self.reason = reason
        self.path = path
        super().__init__(f"{reason.value}（{path}）：{_GUIDANCE[reason]}")
