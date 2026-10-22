"""论文事实封闭原因词表;错误不携带原始输入。"""

from enum import StrEnum

REASON_CATALOG_VERSION = 1


class PaperReason(StrEnum):
    UNSUPPORTED_FORM = "unsupported_form"
    INVALID_DOI = "invalid_doi"
    IDENTITY_CONFLICT = "identity_conflict"
    REQUIRES_MERGE = "requires_merge"
    NOT_RETAINED = "not_retained"
    TRUNCATION_UNKNOWN = "truncation_unknown"
    DATABASE_BUSY = "database_busy"
    CONFIG_NOT_READY = "config_not_ready"
    CORRUPT_REFERENCE = "corrupt_reference"
    MISSING_TITLE = "missing_title"
    MISSING_ABSTRACT = "missing_abstract"
    PAPER_NOT_FOUND = "paper_not_found"
    VERSION_NOT_FOUND = "version_not_found"
    REVISION_NOT_FOUND = "revision_not_found"
    SNAPSHOT_NOT_FOUND = "snapshot_not_found"
    UNSUPPORTED_SCHEME = "unsupported_scheme"
    UNSUPPORTED_SOURCE = "unsupported_source"
    UNSUPPORTED_FIELD = "unsupported_field"
    UNSUPPORTED_RELATION = "unsupported_relation"
    INVALID_OBSERVATION = "invalid_observation"
    INVALID_TEXT = "invalid_text"
    MISSING_ENTRY_ID = "missing_entry_id"
    INVALID_FEED_URL = "invalid_feed_url"
    INVALID_RELATION = "invalid_relation"
    INVALID_MANUAL_CORRECTION = "invalid_manual_correction"


GUIDANCE = {
    PaperReason.UNSUPPORTED_FORM: "请改用受支持的裸 DOI 或规范 URL",
    PaperReason.INVALID_DOI: "请核对 DOI 字面值",
    PaperReason.IDENTITY_CONFLICT: "请核对已登记身份，勿自动换绑",
    PaperReason.REQUIRES_MERGE: "请查看 trace 的等待合并依据",
    PaperReason.NOT_RETAINED: "无需重试相同内容",
    PaperReason.TRUNCATION_UNKNOWN: "请补充文本和明确截断标记",
    PaperReason.DATABASE_BUSY: "请在写入结束后显式重试",
    PaperReason.CONFIG_NOT_READY: "请补齐该阶段配置",
    PaperReason.CORRUPT_REFERENCE: "请停止使用该批次并检查备份",
    PaperReason.MISSING_TITLE: "请补齐该版本题名",
    PaperReason.MISSING_ABSTRACT: "请补齐该版本摘要",
    PaperReason.PAPER_NOT_FOUND: "请核对论文 ID",
    PaperReason.VERSION_NOT_FOUND: "请核对版本 ID",
    PaperReason.REVISION_NOT_FOUND: "请核对版本及修订号",
    PaperReason.SNAPSHOT_NOT_FOUND: "请使用已登记配置快照",
    PaperReason.UNSUPPORTED_SCHEME: "请使用 DOI，其他标识待后续支持",
    PaperReason.UNSUPPORTED_SOURCE: "请使用当前已实现来源入口",
    PaperReason.UNSUPPORTED_FIELD: "请移除未支持字段后重交",
    PaperReason.UNSUPPORTED_RELATION: "请使用出版者或注册机构的预印本到正式版关系",
    PaperReason.INVALID_OBSERVATION: "请核对受控字段与单条原始材料",
    PaperReason.INVALID_TEXT: "请先解析为无 HTML 的合法文本",
    PaperReason.MISSING_ENTRY_ID: "请由适配器提供真实 entry ID",
    PaperReason.INVALID_FEED_URL: "请提供受支持的 Feed 端点 URL",
    PaperReason.INVALID_RELATION: "请核对关系两端与来源定位",
    PaperReason.INVALID_MANUAL_CORRECTION: "只能用非空完整值追加覆盖，不能清除或撤销",
}


class PaperError(Exception):
    def __init__(self, reason: PaperReason, *, path: str = "observation") -> None:
        self.reason = reason
        self.path = path
        super().__init__(f"{reason.value}（{path}）：{GUIDANCE[reason]}")
