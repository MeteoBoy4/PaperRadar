"""正文提取的严格声明与 backend 中立只读语义。不执行解析。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from pydantic import field_validator, model_validator

from paper_radar.config.extraction_models import (
    ExtractionModels,
    FormulaModel,
    FrozenExtractionConfig,
    LayoutModel,
    ModelFile,
    TableModel,
)
from paper_radar.config.extraction_policy import DoclingPolicy
from paper_radar.config.extraction_toolchain import (
    BackendIdentity,
    PDFBackend,
    ToolchainId,
    backend_identity,
)
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.schema import valid_declared_version


class NormalizationVersion(StrEnum):
    V1 = "v1"


class ModelStage(StrEnum):
    LAYOUT = "layout"
    TABLE = "table"
    FORMULA = "formula"


@dataclass(frozen=True, slots=True)
class ModelArtifactIdentity:
    stage: ModelStage
    model_id: str
    repo_id: str
    commit_sha: str
    files: tuple[ModelFile, ...]


@dataclass(frozen=True, slots=True)
class ExtractionSemantics:
    backend: BackendIdentity
    model_artifacts: tuple[ModelArtifactIdentity, ...]
    backend_config_json: str
    normalization_version: NormalizationVersion

    @property
    def backend_config_hash(self) -> str:
        return sha256(self.backend_config_json.encode("utf-8"))

    @property
    def model_artifacts_hash(self) -> str | None:
        if not self.model_artifacts:
            return None
        return sha256(
            canonical_json(
                [
                    {
                        "stage": model.stage,
                        "model_id": model.model_id,
                        "repo_id": model.repo_id,
                        "commit_sha": model.commit_sha,
                        "files": [file.model_dump() for file in model.files],
                    }
                    for model in self.model_artifacts
                ]
            )
        )


class Extraction(FrozenExtractionConfig):
    version: str
    toolchain: ToolchainId
    pdf_backend: PDFBackend = "pypdfium2"
    models: ExtractionModels
    policy: DoclingPolicy = DoclingPolicy()
    normalization_version: NormalizationVersion

    @model_validator(mode="after")
    def formula_flag_matches_model_slot(self) -> Self:
        if self.policy.do_formula_enrichment != (self.models.formula is not None):
            raise ValueError("启用公式候选必须声明模型身份；关闭时不得登记未使用模型")
        return self

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return valid_declared_version(value)

    @field_validator("normalization_version", mode="before")
    @classmethod
    def supported_normalization(cls, value: object) -> NormalizationVersion:
        if not isinstance(value, str):
            raise ValueError("正文规范化只支持受控 v1")
        return NormalizationVersion(value)

    def compiled_config(self) -> dict[str, object]:
        """将受控工具链展开存档。历史加载会核对清单是否漂移。"""
        backend = backend_identity(self.toolchain, self.pdf_backend)
        return {
            **self.model_dump(mode="json"),
            "backend": {
                "backend_id": backend.backend_id,
                "backend_version": backend.backend_version,
                "component_versions": dict(backend.component_versions),
            },
            "backend_config": json.loads(self.semantics.backend_config_json),
        }

    @property
    def semantics(self) -> ExtractionSemantics:
        models: list[tuple[ModelStage, LayoutModel | TableModel | FormulaModel]] = [
            (ModelStage.LAYOUT, self.models.layout),
            (ModelStage.TABLE, self.models.table),
        ]
        if self.models.formula is not None:
            models.append((ModelStage.FORMULA, self.models.formula))
        backend_config: dict[str, object] = {
            "pdf_backend": self.pdf_backend,
            "pdf_options": (
                {}
                if self.pdf_backend == "pypdfium2"
                else {
                    "enforce_same_font": True,
                    "include_bitmap_images": False,
                    "render_pages": True,
                    "render_scale": 1.0,
                }
            ),
            "policy": self.policy.model_dump(mode="json"),
            "layout_engine": self.models.layout.engine,
            "table_mode": self.models.table.mode,
        }
        if self.models.formula is not None:
            backend_config["formula"] = self.models.formula.model_dump(
                mode="json", exclude={"commit_sha", "files", "repo_id", "model_id"}
            )
        return ExtractionSemantics(
            backend_identity(self.toolchain, self.pdf_backend),
            tuple(
                ModelArtifactIdentity(
                    stage, model.model_id, model.repo_id, model.commit_sha, model.files
                )
                for stage, model in models
            ),
            canonical_json(backend_config).decode("utf-8"),
            self.normalization_version,
        )
