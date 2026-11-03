"""兼容旧配置 import; stdlib-only 权威清单位于 paper_radar.docling_toolchain。"""

from paper_radar.docling_toolchain import (
    BackendIdentity,
    PDFBackend,
    ToolchainId,
    backend_identity,
)

__all__ = ["BackendIdentity", "PDFBackend", "ToolchainId", "backend_identity"]
