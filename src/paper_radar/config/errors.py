"""配置边界的脱敏错误。"""


class ConfigError(Exception):
    """仅包含字段路径和可操作的中文原因。输入内容不出现在错误中。"""
