"""按需读取平台和顶层包事实。仅使用 stdlib;导入不探测、不加载 SDK。"""

import importlib.metadata
import importlib.util
import os
import platform
import sys
import sysconfig
from dataclasses import dataclass
from enum import StrEnum

from paper_radar.docling_toolchain import (
    PDFBackend,
    ToolchainId,
    backend_identity,
    toolchain_supply,
)


class RuntimeReason(StrEnum):
    NOT_REQUESTED = "runtime_not_requested"
    UNSELECTED = "extraction_unselected"
    SELECTION_INVALID = "runtime_selection_invalid"
    PLATFORM_UNKNOWN = "platform_unknown"
    PLATFORM_UNSUPPORTED = "platform_unsupported"
    PLATFORM_SUPPORTED = "platform_supported"
    DEPENDENCY_MISSING = "dependency_missing"
    DEPENDENCY_INCONSISTENT = "dependency_inconsistent"
    VERSION_MISMATCH = "dependency_version_mismatch"
    PASSED = "dependencies_discoverable"


class RuntimeNextStep(StrEnum):
    REQUEST = "request_runtime_check"
    CONFIGURE = "configure_extraction"
    PLATFORM = "prepare_supported_platform"
    INSTALL = "sync_locked_extra"
    REPAIR = "repair_environment"
    TOOLCHAIN = "match_selected_toolchain"
    CONSUMER = "consumer_runtime_checks"


_NEXT_STEPS = {
    RuntimeReason.NOT_REQUESTED: RuntimeNextStep.REQUEST,
    RuntimeReason.UNSELECTED: RuntimeNextStep.CONFIGURE,
    RuntimeReason.SELECTION_INVALID: RuntimeNextStep.CONFIGURE,
    RuntimeReason.PLATFORM_UNKNOWN: RuntimeNextStep.PLATFORM,
    RuntimeReason.PLATFORM_UNSUPPORTED: RuntimeNextStep.PLATFORM,
    RuntimeReason.PLATFORM_SUPPORTED: RuntimeNextStep.CONSUMER,
    RuntimeReason.DEPENDENCY_MISSING: RuntimeNextStep.INSTALL,
    RuntimeReason.DEPENDENCY_INCONSISTENT: RuntimeNextStep.REPAIR,
    RuntimeReason.VERSION_MISMATCH: RuntimeNextStep.TOOLCHAIN,
    RuntimeReason.PASSED: RuntimeNextStep.CONSUMER,
}


@dataclass(frozen=True, slots=True)
class PlatformFacts:
    system: str
    machine: str
    implementation: str
    python_version: tuple[int, int, int]
    libc: str | None
    libc_version: tuple[int, int] | None
    gil_disabled: bool | None
    reason: RuntimeReason


@dataclass(frozen=True, slots=True)
class DependencyFact:
    distribution: str
    module: str
    expected_version: str | None
    installed_version: str | None
    discoverable: bool | None
    reason: RuntimeReason


@dataclass(frozen=True, slots=True)
class RuntimeProbe:
    requested: bool
    enabled: bool
    toolchain: ToolchainId | None
    pdf_backend: PDFBackend | None
    reason: RuntimeReason
    platform: PlatformFacts | None = None
    dependencies: tuple[DependencyFact, ...] = ()

    @property
    def passed(self) -> bool:
        return self.reason is RuntimeReason.PASSED

    @property
    def next_step(self) -> RuntimeNextStep:
        return _NEXT_STEPS[self.reason]

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(
            fact.distribution
            for fact in self.dependencies
            if fact.reason is RuntimeReason.DEPENDENCY_MISSING
        )

    @property
    def mismatched(self) -> tuple[str, ...]:
        return tuple(
            fact.distribution
            for fact in self.dependencies
            if fact.reason
            in {RuntimeReason.VERSION_MISMATCH, RuntimeReason.DEPENDENCY_INCONSISTENT}
        )


# 仅模块名映射;版本来自 docling_toolchain 权威视图。cv2 是 TableFormer
# 必要供给检查,但其具体版本由产品锁约束,不另造语义版本清单。
_MODULES = {
    "docling-slim": "docling",
    "docling-core": "docling_core",
    "docling-ibm-models": "docling_ibm_models",
    "docling-parse": "docling_parse",
    "opencv-python-headless": "cv2",
}


def _platform_facts() -> PlatformFacts:
    system, machine = platform.system(), platform.machine()
    implementation = sys.implementation.name
    python_version = (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    try:
        libc_text = os.confstr("CS_GNU_LIBC_VERSION")
    except (AttributeError, OSError, ValueError):
        libc_text = None
    try:
        abi_flag = sysconfig.get_config_var("Py_GIL_DISABLED")
    except (OSError, ValueError):
        abi_flag = None
    return _classify_platform(
        system=system,
        machine=machine,
        implementation=implementation,
        python_version=python_version,
        libc_text=libc_text,
        abi_flag=abi_flag,
        abiflags=getattr(sys, "abiflags", ""),
    )


def _classify_platform(
    *,
    system: str,
    machine: str,
    implementation: str,
    python_version: tuple[int, int, int],
    libc_text: str | None,
    abi_flag: object,
    abiflags: str,
) -> PlatformFacts:
    """只按给定事实分类;不读取宿主或加载 SDK。"""
    libc = None
    libc_version = None
    if libc_text:
        name, _, version = libc_text.partition(" ")
        libc = name
        parts = version.split(".")
        if len(parts) >= 2 and all(part.isdecimal() for part in parts[:2]):
            libc_version = (int(parts[0]), int(parts[1]))
    gil_disabled = (
        bool(abi_flag)
        if abi_flag in (0, 1)
        else False
        if implementation == "cpython" and python_version[:2] == (3, 12)
        else None
    )
    if "t" in abiflags:
        gil_disabled = True
    # 检查构建 ABI;free-threaded 构建即使临时启用 GIL 仍不受支持。
    if (
        (system and system != "Linux")
        or (machine and machine != "x86_64")
        or (implementation and implementation != "cpython")
        or python_version[:2] not in {(3, 12), (3, 13), (3, 14)}
        or gil_disabled is True
        or (libc is not None and libc != "glibc")
        or (libc_version is not None and libc_version < (2, 28))
    ):
        reason = RuntimeReason.PLATFORM_UNSUPPORTED
    elif (
        not system
        or not machine
        or not implementation
        or libc is None
        or libc_version is None
        or gil_disabled is None
    ):
        reason = RuntimeReason.PLATFORM_UNKNOWN
    else:
        reason = RuntimeReason.PLATFORM_SUPPORTED
    return PlatformFacts(
        system,
        machine,
        implementation,
        python_version,
        libc,
        libc_version,
        gil_disabled,
        reason,
    )


def _dependency(distribution: str, expected: str | None) -> DependencyFact:
    module = _MODULES.get(distribution, distribution)
    try:
        installed = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        installed = None
    except (OSError, ValueError):
        return _classify_dependency(distribution, module, expected, None, None)
    try:
        found = importlib.util.find_spec(module) is not None
    except (ImportError, OSError, ValueError):
        found = None
    return _classify_dependency(distribution, module, expected, installed, found)


def _classify_dependency(
    distribution: str,
    module: str,
    expected: str | None,
    installed: str | None,
    found: bool | None,
) -> DependencyFact:
    """只按 metadata/可发现性事实分类;不访问安装环境。"""
    if installed is None and found is False:
        reason = RuntimeReason.DEPENDENCY_MISSING
    elif installed is None or found is not True:
        reason = RuntimeReason.DEPENDENCY_INCONSISTENT
    elif expected is not None and installed != expected:
        reason = RuntimeReason.VERSION_MISMATCH
    else:
        reason = RuntimeReason.PASSED
    return DependencyFact(distribution, module, expected, installed, found, reason)


def probe_docling_runtime(
    toolchain: ToolchainId | None,
    pdf_backend: PDFBackend | None,
    *,
    requested: bool,
    enabled: bool,
) -> RuntimeProbe:
    """消费已验证显式选择;通过仅证明此刻可发现和版本匹配,不授予执行许可。"""
    if not requested or not enabled:
        return RuntimeProbe(
            requested,
            enabled,
            toolchain,
            pdf_backend,
            RuntimeReason.UNSELECTED if requested else RuntimeReason.NOT_REQUESTED,
        )
    if toolchain is None or pdf_backend is None:
        return RuntimeProbe(
            requested, enabled, toolchain, pdf_backend, RuntimeReason.SELECTION_INVALID
        )
    identity = backend_identity(toolchain, pdf_backend)
    required = (
        *identity.component_versions,
        *toolchain_supply(toolchain).cli_constraints,
        ("opencv-python-headless", None),
    )
    facts = _platform_facts()
    dependencies = tuple(_dependency(name, version) for name, version in required)
    reason = facts.reason
    if reason is RuntimeReason.PLATFORM_SUPPORTED:
        reason = next(
            (
                item.reason
                for item in dependencies
                if item.reason
                in {
                    RuntimeReason.DEPENDENCY_INCONSISTENT,
                    RuntimeReason.VERSION_MISMATCH,
                }
            ),
            RuntimeReason.DEPENDENCY_MISSING
            if any(
                item.reason is RuntimeReason.DEPENDENCY_MISSING for item in dependencies
            )
            else RuntimeReason.PASSED,
        )
    return RuntimeProbe(
        requested, enabled, toolchain, pdf_backend, reason, facts, dependencies
    )
