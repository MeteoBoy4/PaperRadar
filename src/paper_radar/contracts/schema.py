"""从权威 Pydantic 模型生成确定性的冻结契约内容。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Any

from paper_radar.screening.reasons import screening_reason_json_schema
from paper_radar.screening.schema import (
    BoundaryOutput,
    ReuseAssessmentOutput,
    ValuePredictionOutput,
)

_SCHEMA_FILENAME = "schema.json"
_MANIFEST_FILENAME = "manifest.json"
_MANIFEST_FORMAT_VERSION = 1


class _ManifestField(StrEnum):
    CONTRACT = "contract"
    FORMAT_VERSION = "format_version"
    SCHEMA_FILE = "schema_file"
    SCHEMA_SHA256 = "schema_sha256"
    VERSION = "version"


class ContractName(StrEnum):
    """当前已经实现的冻结契约。"""

    BOUNDARY = "boundary"
    VALUE_PREDICTION = "value-prediction"
    REUSE_ASSESSMENT = "reuse-assessment"
    DECISION_REASONS = "decision-reasons"


class ContractVersion(StrEnum):
    """当前代码能够生成的声明版本。"""

    V1 = "v1"


@dataclass(frozen=True, slots=True)
class _ContractDefinition:
    schema_builder: Callable[[], dict[str, Any]]
    area: str


@dataclass(frozen=True, slots=True)
class FrozenContract:
    """一个不包含路径、时间或随机数据的完整契约快照。"""

    name: ContractName
    version: ContractVersion
    schema_bytes: bytes
    schema_sha256: str
    manifest_bytes: bytes
    snapshot_parts: tuple[str, str, str]
    schema_filename: str
    manifest_filename: str


_CONTRACTS: dict[
    tuple[ContractName, ContractVersion],
    _ContractDefinition,
] = {
    (ContractName.BOUNDARY, ContractVersion.V1): _ContractDefinition(
        schema_builder=partial(BoundaryOutput.model_json_schema, mode="validation"),
        area="screening",
    ),
    (ContractName.VALUE_PREDICTION, ContractVersion.V1): _ContractDefinition(
        schema_builder=partial(
            ValuePredictionOutput.model_json_schema,
            mode="validation",
        ),
        area="screening",
    ),
    (ContractName.REUSE_ASSESSMENT, ContractVersion.V1): _ContractDefinition(
        schema_builder=partial(
            ReuseAssessmentOutput.model_json_schema,
            mode="validation",
        ),
        area="screening",
    ),
    (ContractName.DECISION_REASONS, ContractVersion.V1): _ContractDefinition(
        schema_builder=screening_reason_json_schema,
        area="screening",
    ),
}

_SUPPORTED_CONTRACT_NAMES = "、".join(
    dict.fromkeys(name.value for name, _version in _CONTRACTS)
)
_SUPPORTED_CONTRACT_VERSIONS = "、".join(
    dict.fromkeys(version.value for _name, version in _CONTRACTS)
)


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    ).encode()


class ContractSelectionError(ValueError):
    """受控契约选择无效。消息为脱敏的中文操作指引。"""


def build_selected_contract(
    name: ContractName | str,
    version: ContractVersion | str,
) -> FrozenContract:
    """从受控契约名与声明版本生成冻结契约。选择无效时给出稳定指引。"""
    try:
        controlled_name = ContractName(name)
    except ValueError as error:
        raise ContractSelectionError(
            f"未知契约；当前支持：{_SUPPORTED_CONTRACT_NAMES}。"
        ) from error

    try:
        controlled_version = ContractVersion(version)
    except ValueError as error:
        raise ContractSelectionError(
            f"无效声明版本；当前支持：{_SUPPORTED_CONTRACT_VERSIONS}。"
        ) from error

    try:
        return build_frozen_contract(controlled_name, controlled_version)
    except KeyError as error:
        raise ContractSelectionError(
            "所选契约与声明版本组合尚未实现；请查看命令帮助中的可用组合。"
        ) from error


def select_contracts(
    names: Iterable[ContractName | str],
    version: ContractVersion | str,
) -> tuple[FrozenContract, ...]:
    """整体校验并去重。随后按受控声明顺序返回契约。"""
    requested = tuple(names)
    if not requested:
        raise ContractSelectionError("至少使用一次 --contract 选择一份已实现契约。")

    selected: dict[ContractName, FrozenContract] = {}
    for name in requested:
        contract = build_selected_contract(name, version)
        if contract.name in selected:
            raise ContractSelectionError(
                f"契约 {contract.name.value} 被重复选择；每份契约只能选择一次。"
            )
        selected[contract.name] = contract

    return tuple(selected[name] for name in ContractName if name in selected)


def build_frozen_contract(
    name: ContractName,
    version: ContractVersion,
) -> FrozenContract:
    """直接从已注册的权威模型生成规范 Schema、哈希和清单。"""
    definition = _CONTRACTS[(name, version)]
    schema = definition.schema_builder()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:paper-radar:contracts:{definition.area}:{name}:{version}"
    schema["x-paper-radar-contract"] = {
        "name": name.value,
        "version": version.value,
    }
    schema_bytes = _canonical_json_bytes(schema)
    schema_sha256 = hashlib.sha256(schema_bytes).hexdigest()
    manifest_bytes = _canonical_json_bytes(
        {
            _ManifestField.CONTRACT: name.value,
            _ManifestField.FORMAT_VERSION: _MANIFEST_FORMAT_VERSION,
            _ManifestField.SCHEMA_FILE: _SCHEMA_FILENAME,
            _ManifestField.SCHEMA_SHA256: schema_sha256,
            _ManifestField.VERSION: version.value,
        }
    )
    return FrozenContract(
        name=name,
        version=version,
        schema_bytes=schema_bytes,
        schema_sha256=schema_sha256,
        manifest_bytes=manifest_bytes,
        snapshot_parts=(definition.area, name.value, version.value),
        schema_filename=_SCHEMA_FILENAME,
        manifest_filename=_MANIFEST_FILENAME,
    )
