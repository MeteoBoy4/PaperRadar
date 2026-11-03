"""Docling 轻量探测结果的中文四态投影,不把范围 passed 当成 fixture 通过。"""

import json

from paper_radar.config import RuntimeConfigSnapshot
from paper_radar.config.compile import MaterialKind
from paper_radar.docling_runtime import RuntimeReason, probe_docling_runtime
from paper_radar.doctor.service import Check, Result

_GUIDANCE = {
    RuntimeReason.NOT_REQUESTED: "请显式请求 Docling 依赖检查；不由安装推定启用。",
    RuntimeReason.UNSELECTED: (
        "所选材料未选择 extraction；请显式配置工具链和 PDF 后端。"
    ),
    RuntimeReason.SELECTION_INVALID: "选择不完整；请重新 check/load 显式配置。",
    RuntimeReason.PLATFORM_UNKNOWN: (
        "平台关键事实未知；请确认 Linux x86_64、glibc "
        ">=2.28、普通 GIL CPython 3.12–3.14。"
    ),
    RuntimeReason.PLATFORM_UNSUPPORTED: (
        "平台不受支持；请使用 Linux x86_64、glibc >=2.28、普通 GIL CPython 3.12–3.14。"
    ),
    RuntimeReason.PLATFORM_SUPPORTED: "仅平台元数据匹配；native ABI 与模型运行仍未验。",
    RuntimeReason.DEPENDENCY_MISSING: (
        "缺少组件；在支持平台显式执行 uv sync --locked "
        "--extra docling；安装不启用 extraction。"
    ),
    RuntimeReason.DEPENDENCY_INCONSISTENT: (
        "distribution metadata 与顶层模块发现不一致或不可读；"
        "请检查隔离环境并重新按锁安装。"
    ),
    RuntimeReason.VERSION_MISMATCH: (
        "组件精确版本与所选工具链不匹配；按历史清单准备隔离环境，"
        "或显式声明新工具链配置；不自动改选或 fallback。"
    ),
    RuntimeReason.PASSED: (
        "此刻组件可发现且版本匹配；"
        "延迟 import、native ABI、模型与解析错误仍由 Body 处理。"
    ),
}


def _result(reason: RuntimeReason) -> Result:
    if reason in {RuntimeReason.PASSED, RuntimeReason.PLATFORM_SUPPORTED}:
        return Result.PASSED
    if reason in {RuntimeReason.UNSELECTED, RuntimeReason.DEPENDENCY_MISSING}:
        return Result.MISSING
    if reason is RuntimeReason.NOT_REQUESTED:
        return Result.NOT_ASSESSED
    return Result.INVALID


def runtime_checks(selected: RuntimeConfigSnapshot) -> tuple[Check, ...]:
    """只消费 check/load 已验证的快照;现场事实不来自历史快照。"""
    declaration = next(
        (
            json.loads(material.config_json)
            for material in selected.materials.values()
            if material.kind is MaterialKind.EXTRACTION
        ),
        None,
    )
    probe = probe_docling_runtime(
        declaration["toolchain"] if declaration else None,
        declaration["pdf_backend"] if declaration else None,
        requested=True,
        enabled=declaration is not None,
    )
    checks = [
        Check(
            "docling_fixture.selection",
            Result.PASSED if probe.enabled else Result.MISSING,
            "extraction_selected" if probe.enabled else RuntimeReason.UNSELECTED.value,
            (
                f"明确选择 toolchain={probe.toolchain} backend={probe.pdf_backend}；"
                "安装不改变选择。"
                if probe.enabled
                else _GUIDANCE[RuntimeReason.UNSELECTED]
            ),
        )
    ]
    if probe.platform is not None:
        checks.append(
            Check(
                "docling_fixture.platform",
                _result(probe.platform.reason),
                probe.platform.reason.value,
                _GUIDANCE[probe.platform.reason],
            )
        )
    checks.extend(
        Check(
            f"docling_fixture.dependency.{fact.distribution}",
            _result(fact.reason),
            fact.reason.value,
            f"组件={fact.distribution} 顶层模块={fact.module} "
            f"要求版本={fact.expected_version or '产品锁约束'}；"
            f"{_GUIDANCE[fact.reason]}",
        )
        for fact in probe.dependencies
    )
    return tuple(checks)


def unassessed_checks() -> tuple[Check, ...]:
    return tuple(
        Check(
            f"docling_fixture.{name}",
            Result.NOT_ASSESSED,
            f"{name}_not_assessed",
            next_step,
        )
        for name, next_step in (
            (
                "models",
                "依赖安装不代表模型已取得或可运行；Body 显式管理缓存与模型运行。",
            ),
            (
                "native_abi",
                "可发现和版本匹配不证明 native ABI；Body 仍须处理延迟 import 异常。",
            ),
            (
                "quality",
                "由 Body/F 验收逐文档质量与四刊 fixture；本范围不开放 Read/reuse。",
            ),
            ("resources", "由 Body/F 验收资源能力；不执行解析或测量内存。"),
        )
    )
