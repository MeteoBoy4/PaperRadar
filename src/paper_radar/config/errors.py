"""配置边界的脱敏错误。"""

from enum import StrEnum
from types import MappingProxyType


class ConfigValidationReason(StrEnum):
    V1_OCR_DISABLED = "v1_ocr_disabled"
    PI_VERSION_INVALID = "pi_version_invalid"
    RESOURCE_HASH_INVALID = "resource_hash_invalid"


VALIDATION_GUIDANCE = MappingProxyType(
    {
        ConfigValidationReason.PI_VERSION_INVALID.value: (
            "请填写无前导零的精确三段版本（如 1.1.0），不能使用范围、latest 或路径"
        ),
        ConfigValidationReason.RESOURCE_HASH_INVALID.value: (
            "请填写所选系统 Prompt 精确字节的 64 位小写 SHA-256"
        ),
        # 以下键来自 Pydantic ValidationError.errors() 的 type 字段。
        "missing": "必填字段缺失；请补充配置契约要求的字段",
        "extra_forbidden": "未知字段；请删除或使用配置契约支持的字段",
        "literal_error": "类型错误或取值不受支持；请使用配置契约的受控值或固定 V1 策略",
        "string_type": "必须为文本；请检查类型，不要使用数字、布尔或 null",
        "tuple_type": "必须为列表；请使用配置契约规定的资源或工具清单",
        "missing_argument": "必填清单成员缺失；请补充配置契约规定的资源",
        ConfigValidationReason.V1_OCR_DISABLED.value: (
            "V1 不支持 OCR；请将 do_ocr 设为 false 或省略；扫描稿需等待 V2"
        ),
    }
)


class ConfigError(Exception):
    """仅包含字段路径和可操作的中文原因。输入内容不出现在错误中。"""
