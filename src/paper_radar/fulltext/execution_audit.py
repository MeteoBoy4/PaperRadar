"""可选提取执行审计;运行身份不进入 extraction 语义。"""

import json
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from paper_radar.docling_toolchain import PDFBackend, ToolchainId, backend_identity
from paper_radar.fulltext.canonical import CanonicalModel

if TYPE_CHECKING:
    from paper_radar.config.extraction import ExtractionSemantics


class ExtractionExecutionAudit(CanonicalModel):
    format_version: Literal[1] = 1
    toolchain: ToolchainId
    pdf_backend: PDFBackend
    component_versions: tuple[tuple[str, str], ...]
    backend_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_artifacts_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalization_version: Literal["v1"] = "v1"
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
    memory_limit_bytes: int = Field(gt=0, le=2**63 - 1)
    memory_limit_method: Literal["rlimit_as_virtual_address_space_bytes"] = (
        "rlimit_as_virtual_address_space_bytes"
    )
    peak_memory_method: Literal["linux_wait4_worker_ru_maxrss_kib_x1024"] = (
        "linux_wait4_worker_ru_maxrss_kib_x1024"
    )
    sandbox: Literal["linux_x86_64_seccomp_v1"] = "linux_x86_64_seccomp_v1"
    hf_hub_offline: Literal["1"] = "1"
    transformers_offline: Literal["1"] = "1"
    hf_hub_disable_telemetry: Literal["1"] = "1"
    do_not_track: Literal["1"] = "1"
    device: Literal["cpu"] = "cpu"
    threads: int = Field(ge=1, le=32)
    stage_batch_size: Literal[1] = 1
    queue_max_size: Literal[8] = 8
    generate_parsed_pages: Literal[False] = False
    native_text_signal: Literal["selected_backend_native_cells"] = (
        "selected_backend_native_cells"
    )

    @model_validator(mode="after")
    def controlled_toolchain(self) -> "ExtractionExecutionAudit":
        if (
            self.component_versions
            != backend_identity(self.toolchain, self.pdf_backend).component_versions
        ):
            raise ValueError("执行审计组件与工具链不符")
        return self

    def matches(self, semantics: "ExtractionSemantics") -> bool:
        return (
            backend_identity(self.toolchain, self.pdf_backend) == semantics.backend
            and self.component_versions == semantics.backend.component_versions
            and self.pdf_backend
            == json.loads(semantics.backend_config_json)["pdf_backend"]
            and self.backend_config_hash == semantics.backend_config_hash
            and self.model_artifacts_hash == semantics.model_artifacts_hash
            and self.normalization_version == semantics.normalization_version
        )
