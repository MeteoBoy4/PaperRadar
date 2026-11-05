"""显式运行参数及有界 worker 协议。"""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from paper_radar.fulltext.canonical import CanonicalDocument, CanonicalModel


class DoclingRun(CanonicalModel):
    model_root: Path = Field(repr=False)
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
    memory_limit_bytes: int = Field(gt=0, le=2**63 - 1)
    threads: int = Field(default=4, ge=1, le=32)


class WorkerRequest(CanonicalModel):
    model_root: str
    pdf_path: str
    response_path: str
    timeout_seconds: float
    memory_limit_bytes: int
    threads: int
    backend_config_json: str
    model_commits: dict[str, str]


WorkerWarning = Literal["formula_candidate_unavailable", "table_source_unavailable"]


class WorkerResponse(CanonicalModel):
    failure: (
        Literal[
            "timeout",
            "resource_exhausted",
            "executor_error",
            "extraction_failed_no_text_layer",
            "extraction_failed_quality_gate",
        ]
        | None
    ) = None
    document: CanonicalDocument | None = Field(default=None, repr=False)
    document_json: str | None = Field(default=None, repr=False)
    peak_memory_bytes: int = Field(default=0, ge=0)
    warnings: tuple[WorkerWarning, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def complete_response(self) -> Self:
        if self.failure is None:
            if self.document is None or self.document_json is None:
                raise ValueError("成功响应缺少完整制品")
        elif self.document is not None or self.document_json is not None:
            raise ValueError("失败响应不得携带成功制品")
        return self
