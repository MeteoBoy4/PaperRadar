"""Fixture 与摘要审计的安全受控错误。"""

from enum import StrEnum


class FixtureReason(StrEnum):
    INVALID_DECLARATION = "invalid_declaration"
    UNSUPPORTED_FORMAT = "unsupported_format"
    DECLARATION_CONFLICT = "declaration_conflict"
    SOURCE_UNAVAILABLE = "source_unavailable"
    RECORD_NOT_FOUND = "record_not_found"
    INVALID_REFERENCE = "invalid_reference"
    EVIDENCE_REQUIRED = "evidence_required"
    CORRUPT_REFERENCE = "corrupt_reference"
    DATABASE_BUSY = "database_busy"


_GUIDANCE = {
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
