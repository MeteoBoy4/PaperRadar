"""仅用于配置文件边界的严格 YAML 读取。"""

from __future__ import annotations

import math
import re
from collections.abc import Hashable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError
from yaml.events import AliasEvent
from yaml.nodes import MappingNode

from paper_radar.config.errors import ConfigError


class _StrictLoader(yaml.SafeLoader):
    yaml_implicit_resolvers = {  # noqa: RUF012
        key: [
            (tag, pattern)
            for tag, pattern in resolvers
            if tag == "tag:yaml.org,2002:str"
        ]
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):
            raise ConfigError("YAML 不允许别名或锚点引用")
        event = self.peek_event()  # type: ignore[no-untyped-call]
        if getattr(event, "anchor", None) is not None:
            raise ConfigError("YAML 不允许锚点")
        return super().compose_node(parent, index)

    def construct_mapping(
        self, node: MappingNode, deep: bool = False
    ) -> dict[Hashable, Any]:
        result: dict[Hashable, Any] = {}
        for key_node, value_node in node.value:
            if key_node.value == "<<":
                raise ConfigError("YAML 不允许合并键")
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ConfigError("YAML 字段名必须是文本")
            if key in result:
                raise ConfigError(f"YAML 字段 {key} 重复")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


_StrictLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf")
)
_StrictLoader.add_implicit_resolver(
    "tag:yaml.org,2002:null", re.compile(r"^(?:null|~)$"), list("n~")
)
_StrictLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int", re.compile(r"^-?(?:0|[1-9][0-9]*)$"), list("-0123456789")
)
_StrictLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        r"^(?:-?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?|\.(?:nan|inf|Inf|NaN))$"
    ),
    list("-0123456789."),
)


def _reject_nonfinite(value: Any, path: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ConfigError(f"{path}：不允许非有限浮点数")
    if isinstance(value, str) and re.fullmatch(r"[+-]?\.(?:nan|inf)", value, re.I):
        raise ConfigError(f"{path}：不允许非有限浮点数")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_nonfinite(item, f"{path}[{index}]")


def validate_yaml_bytes[T: BaseModel](raw: bytes, model: type[T], label: str) -> T:
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ConfigError(f"{label}：必须是 UTF-8 文本") from None
    try:
        documents = list(yaml.load_all(source, Loader=_StrictLoader))
    except ConfigError:
        raise
    except yaml.YAMLError:
        raise ConfigError(f"{label}：YAML 语法或 tag 无效") from None
    if len(documents) != 1 or not isinstance(documents[0], dict):
        raise ConfigError(f"{label}：必须是单文档字段映射")
    _reject_nonfinite(documents[0], label)
    try:
        return model.model_validate(documents[0])
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise ConfigError(f"{label}.{location}：字段缺失、类型错误或不受支持") from None


def read_yaml[T: BaseModel](path: Path, model: type[T], label: str) -> tuple[bytes, T]:
    try:
        raw = path.read_bytes()
    except OSError:
        raise ConfigError(f"{label}：无法读取文件；请检查路径和权限") from None
    return raw, validate_yaml_bytes(raw, model, label)
