"""按启用阶段冻结的模型声明。仅验证身份格式和清单完整性。"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FrozenExtractionConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, validate_default=True
    )


class ModelFile(FrozenExtractionConfig):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def relative_artifact_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or path.is_absolute()
            or any(part in ("", ".", "..") for part in value.split("/"))
            or "\\" in value
            or ":" in value
            or any(char.isspace() or ord(char) < 32 for char in value)
        ):
            raise ValueError("模型文件必须使用仓库内规范相对路径")
        return value


class _Model(FrozenExtractionConfig):
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[ModelFile, ...] = Field(min_length=1)

    @field_validator("files", mode="before")
    @classmethod
    def file_list(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("files")
    @classmethod
    def unique_sorted_files(cls, value: tuple[ModelFile, ...]) -> tuple[ModelFile, ...]:
        if len({file.path for file in value}) != len(value):
            raise ValueError("模型文件路径不得重复")
        return tuple(sorted(value, key=lambda file: file.path))


class LayoutModel(_Model):
    model_id: Literal["layout_egret_medium"] = "layout_egret_medium"
    repo_id: Literal["docling-project/docling-layout-egret-medium"] = (
        "docling-project/docling-layout-egret-medium"
    )
    engine: Literal["transformers"] = "transformers"

    @field_validator("files")
    @classmethod
    def required_files(cls, value: tuple[ModelFile, ...]) -> tuple[ModelFile, ...]:
        if {file.path for file in value} != {
            "config.json",
            "model.safetensors",
            "preprocessor_config.json",
        }:
            raise ValueError("版面模型必须完整冻结权重、配置与 processor")
        return value


class TableModel(_Model):
    model_id: Literal["docling_tableformer"] = "docling_tableformer"
    repo_id: Literal["docling-project/docling-models"] = (
        "docling-project/docling-models"
    )
    mode: Literal["accurate", "fast"] = "accurate"

    @model_validator(mode="after")
    def files_match_mode(self) -> Self:
        prefix = f"model_artifacts/tableformer/{self.mode}/"
        if {file.path for file in self.files} != {
            prefix + f"tableformer_{self.mode}.safetensors",
            prefix + "tm_config.json",
        }:
            raise ValueError("表格模式必须与完整模型文件清单一致")
        return self


class FormulaModel(_Model):
    model_id: Literal["CodeFormulaV2"] = "CodeFormulaV2"
    repo_id: Literal["docling-project/CodeFormulaV2"] = "docling-project/CodeFormulaV2"
    engine: Literal["transformers"] = "transformers"
    torch_dtype: Literal["float32"] = "float32"
    expansion_factor: float = 0.18

    @field_validator("expansion_factor")
    @classmethod
    def fixed_expansion(cls, value: float) -> float:
        if value != 0.18:
            raise ValueError(
                "公式候选裁切扩展固定为 0.18，改变须重新冻结策略与 fixture"
            )
        return value

    @field_validator("files")
    @classmethod
    def required_files(cls, value: tuple[ModelFile, ...]) -> tuple[ModelFile, ...]:
        if {file.path for file in value} != {
            "added_tokens.json",
            "chat_template.json",
            "config.json",
            "generation_config.json",
            "model.safetensors",
            "preprocessor_config.json",
            "processor_config.json",
            "special_tokens_map.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
        }:
            raise ValueError(
                "公式模型必须完整冻结权重、processor、tokenizer 与生成配置"
            )
        return value


class ExtractionModels(FrozenExtractionConfig):
    layout: LayoutModel
    table: TableModel
    formula: FormulaModel | None = None
