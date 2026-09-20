"""从权威 Pydantic 模型生成确定性的冻结契约内容。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from paper_radar.screening.schema import BoundaryOutput


class ContractName(StrEnum):
    """当前已经实现的冻结契约。"""

    BOUNDARY = "boundary"


class ContractVersion(StrEnum):
    """当前代码能够生成的声明版本。"""

    V1 = "v1"


@dataclass(frozen=True, slots=True)
class _ContractDefinition:
    model: type[BaseModel]
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
    schema_filename: str = "schema.json"
    manifest_filename: str = "manifest.json"


_CONTRACTS: dict[
    tuple[ContractName, ContractVersion],
    _ContractDefinition,
] = {
    (ContractName.BOUNDARY, ContractVersion.V1): _ContractDefinition(
        model=BoundaryOutput,
        area="screening",
    ),
}


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


def build_frozen_contract(
    name: ContractName,
    version: ContractVersion,
) -> FrozenContract:
    """直接从已注册的权威模型生成规范 Schema、哈希和清单。"""
    definition = _CONTRACTS[(name, version)]
    schema: dict[str, Any] = definition.model.model_json_schema(mode="validation")
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
            "contract": name.value,
            "format_version": 1,
            "schema_file": "schema.json",
            "schema_sha256": schema_sha256,
            "version": version.value,
        }
    )
    return FrozenContract(
        name=name,
        version=version,
        schema_bytes=schema_bytes,
        schema_sha256=schema_sha256,
        manifest_bytes=manifest_bytes,
        snapshot_parts=(definition.area, name.value, version.value),
    )
