"""受控解析工具链权威清单。仅登记身份, 不导入、安装或探测外部包。"""

from dataclasses import dataclass
from typing import Literal

PDFBackend = Literal["pypdfium2", "threaded_docling_parse"]
ToolchainId = Literal["docling-2.135.0-cpu-v1", "docling-2.135.0-cpu-v2"]


@dataclass(frozen=True, slots=True)
class BackendIdentity:
    backend_id: str
    backend_version: str
    component_versions: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ToolchainSupply:
    """固定供给视图; 不表示现场库存或执行就绪, 不进入阶段语义。"""

    component_versions: tuple[tuple[str, str], ...]
    cli_constraints: tuple[tuple[str, str], ...]


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


def toolchain_supply(toolchain: ToolchainId) -> ToolchainSupply:
    """返回完整供给约束; parse 安装与 PDF 后端选择分别判断。

    v1 未冻结 CLI 供给约束, 因此 cli_constraints 为空; 不得以 v2 的 Typer
    约束重新解释旧身份。精确安装来源与传递依赖仍由产品锁文件约束。
    """
    components: tuple[tuple[str, str], ...]
    cli_constraints: tuple[tuple[str, str], ...]
    if toolchain == "docling-2.135.0-cpu-v1":
        components = _COMMON_COMPONENTS
        cli_constraints = ()
    elif toolchain == "docling-2.135.0-cpu-v2":
        components = tuple(
            (name, "2.105.0" if name == "docling-core" else version)
            for name, version in _COMMON_COMPONENTS
        )
        cli_constraints = (("typer", "0.27.2"),)
    else:
        raise ValueError("不支持的解析工具链")
    return ToolchainSupply(
        tuple(sorted((*components, ("docling-parse", "7.22.2")))), cli_constraints
    )


def backend_identity(
    toolchain: ToolchainId, pdf_backend: PDFBackend
) -> BackendIdentity:
    """只包含实际消费的 PDF 后端包。不把未选 parse 包加入语义。"""
    if pdf_backend not in ("pypdfium2", "threaded_docling_parse"):
        raise ValueError("不支持的 PDF 后端")
    components = tuple(
        (name, version)
        for name, version in toolchain_supply(toolchain).component_versions
        if name != "docling-parse" or pdf_backend == "threaded_docling_parse"
    )
    return BackendIdentity("docling", dict(components)["docling-slim"], components)
