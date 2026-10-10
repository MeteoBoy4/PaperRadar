"""配置边界的脱敏错误。"""

from enum import StrEnum
from types import MappingProxyType


class ConfigValidationReason(StrEnum):
    V1_OCR_DISABLED = "v1_ocr_disabled"


VALIDATION_GUIDANCE = MappingProxyType(
    {
        ConfigValidationReason.V1_OCR_DISABLED.value: (
            "V1 不支持 OCR；请将 do_ocr 设为 false 或省略；扫描稿需等待 V2"
        ),
    }
)


class ConfigError(Exception):
    """仅包含字段路径和可操作的中文原因。输入内容不出现在错误中。"""
