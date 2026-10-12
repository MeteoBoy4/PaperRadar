"""Read 分块的受控算法身份。不执行分块或定义模型输出契约。"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError

from paper_radar.config.errors import VALIDATION_GUIDANCE, ConfigValidationReason
from paper_radar.config.schema import valid_declared_version


class ChunkingVersion(StrEnum):
    V1 = "v1"


@dataclass(frozen=True, slots=True)
class ReadSemantics:
    chunking_version: ChunkingVersion


class ReadConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: str
    chunking_version: ChunkingVersion

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return valid_declared_version(value)

    @field_validator("chunking_version", mode="before")
    @classmethod
    def supported_chunking(cls, value: object) -> ChunkingVersion:
        if isinstance(value, str):
            try:
                return ChunkingVersion(value)
            except ValueError:
                pass
        reason = ConfigValidationReason.CHUNKING_VERSION_UNSUPPORTED.value
        raise PydanticCustomError(reason, VALIDATION_GUIDANCE[reason])

    @property
    def semantics(self) -> ReadSemantics:
        return ReadSemantics(self.chunking_version)
