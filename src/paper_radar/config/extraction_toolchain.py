"""受控解析工具链清单。仅登记身份。不导入或安装这些包。"""

from dataclasses import dataclass
from typing import Literal

PDFBackend = Literal["pypdfium2", "threaded_docling_parse"]
ToolchainId = Literal["docling-2.135.0-cpu-v1"]


@dataclass(frozen=True, slots=True)
class BackendIdentity:
    backend_id: str
    backend_version: str
    component_versions: tuple[tuple[str, str], ...]


# 依据已冻结的 live probe 环境。新增组合须新增身份。既有清单不得改写。
# 这里是版本声明权威。并不证明生产 slim 安装或四刊 fixture 已通过。
_COMMON_COMPONENTS = (
    ("docling-slim", "2.135.0"),
    ("docling-core", "2.101.1"),
    ("docling-ibm-models", "4.0.3"),
    ("torch", "2.14.1+cpu"),
    ("torchvision", "0.29.1+cpu"),
    ("transformers", "5.19.0"),
    ("pypdfium2", "5.14.0"),
)


def backend_identity(
    toolchain: ToolchainId, pdf_backend: PDFBackend
) -> BackendIdentity:
    """只包含实际消费的 PDF 后端包。不把未选 parse 包加入语义。"""
    if toolchain != "docling-2.135.0-cpu-v1":
        raise ValueError("不支持的解析工具链")
    pdf_components = (
        () if pdf_backend == "pypdfium2" else (("docling-parse", "7.22.2"),)
    )
    return BackendIdentity(
        "docling",
        dict(_COMMON_COMPONENTS)["docling-slim"],
        tuple(sorted((*_COMMON_COMPONENTS, *pdf_components))),
    )
