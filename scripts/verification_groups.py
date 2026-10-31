"""完整离线入口的轻量生产登记。帮助不加载 writer 或业务模块。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.verification_run import AcceptanceGroup


@dataclass(frozen=True, slots=True)
class Group:
    name: str
    suffix: str
    required: bool
    writer: str
    receipt_scope: str | None
    dependencies: tuple[str, ...] = ()


GROUPS = (
    Group("A1", ".a1.json", True, "scripts.a1_acceptance:A1_GROUP", "scripts.a1_scope"),
    Group(
        "A2-01", ".a2.json", False, "scripts.a2_acceptance:A2_01_GROUP", None, ("A1",)
    ),
    Group(
        "完整 A2",
        ".a2-full.json",
        True,
        "scripts.a2_full_acceptance:_write_group",
        "scripts.a2_full_scope",
        ("A1",),
    ),
    Group(
        "A3",
        ".a3.json",
        True,
        "scripts.a3_acceptance:write_group",
        "scripts.a3_scope",
        ("A1", "完整 A2"),
    ),
    Group(
        "A4",
        ".a4.json",
        True,
        "scripts.a4_acceptance:write_group",
        "scripts.a4_scope",
        ("A1", "完整 A2", "A3"),
    ),
    Group(
        "A5",
        ".a5.json",
        True,
        "scripts.a5_acceptance:write_group",
        "scripts.a5_scope",
        ("A1", "完整 A2", "A3"),
    ),
    Group(
        "A6",
        ".a6.json",
        True,
        "scripts.a6_acceptance:write_group",
        "scripts.a6_scope",
        ("A1", "完整 A2", "A3", "A5"),
    ),
    Group(
        "A7",
        ".a7.json",
        True,
        "scripts.a7_acceptance:write_group",
        "scripts.a7_scope",
        ("A1", "完整 A2", "A3", "A5", "A6"),
    ),
    Group(
        "A8",
        ".a8.json",
        True,
        "scripts.a8_acceptance:write_group",
        "scripts.a8_scope",
        ("A1", "完整 A2", "A3", "A5", "A6", "A7"),
    ),
    Group(
        "A9",
        ".a9.json",
        True,
        "scripts.a9_acceptance:write_group",
        "scripts.a9_scope",
        ("A1", "完整 A2", "A3"),
    ),
    Group(
        "A10",
        ".a10.json",
        True,
        "scripts.a10_acceptance:write_group",
        "scripts.a10_scope",
        ("A1", "完整 A2", "A3", "A6"),
    ),
)


def help_text() -> str:
    """只读取轻量登记, 不触发环境同步、writer、测试、数据库或证据发布。"""
    names = "、".join(group.name for group in GROUPS)
    required = "、".join(group.name for group in GROUPS if group.required)
    return (
        "用法：./scripts/check-offline\n\n"
        "执行固定完整离线检查：lockfile、格式、静态规则、类型、全部测试与 "
        "A1 四份冻结契约；"
        "A9 另显式检查 Read v1。\n"
        "副作用：离线测试与迁移验收使用临时数据库，不操作用户数据库；不访问网络或模型。\n"
        f"输出：在 verification-runs/ 新建同次离线证据与 {names} 独立结论"
        f"（{len(GROUPS) + 1} 份主要文件，另有 pytest 执行回执与控制方终态记录，"
        f"共 {len(GROUPS) + 3} 份 JSON）。\n"
        "查询：./scripts/verification-status <run_id> [--runs-dir <目录>] [--json]；"
        "缺少终态记录不证明完成。\n"
        f"结果：只有本次 {required} 都通过才返回 0；阶段 A、live 与自动精读未验收。\n"
        "常见失败：依赖未准备、检查失败、快照缺失或漂移、运行中断；"
        "按结论 reasons 与离线证据定位。\n"
        "未知参数：返回 2 并提示查看本帮助。\n"
        "示例：./scripts/check-offline"
    )


def receipt_modules() -> tuple[str, ...]:
    """登记的 scope 显式决定回执模块母集; 未执行模块仍有零计数记录。"""
    from importlib import import_module

    return tuple(
        dict.fromkeys(
            name
            for group in GROUPS
            if group.receipt_scope is not None
            for name, _ in import_module(group.receipt_scope).REQUIRED_TEST_MODULES
        )
    )


def acceptance_groups() -> tuple[AcceptanceGroup, ...]:
    """只在正式执行/审计需要时加载 writer, 保留已有恢复与发布行为。"""
    from dataclasses import replace
    from importlib import import_module

    from scripts.verification_run import AcceptanceGroup

    groups = []
    for group in GROUPS:
        module, attribute = group.writer.split(":")
        writer = getattr(import_module(module), attribute)
        if isinstance(writer, AcceptanceGroup):
            registered = replace(
                writer,
                name=group.name,
                suffix=group.suffix,
                required=group.required,
                dependencies=group.dependencies,
            )
        else:
            registered = AcceptanceGroup(
                name=group.name,
                suffix=group.suffix,
                required=group.required,
                dependencies=group.dependencies,
                write=writer,
                show_reasons=True,
            )
        groups.append(registered)
    return tuple(groups)
