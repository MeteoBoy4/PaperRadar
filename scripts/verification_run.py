"""一次固定离线计划与显式验收组的组织; 不包含各组的通过判据。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.offline_evidence import default_checks, run_offline_verification
from scripts.verification_identity import RunIdentity, capture_identity

Conclusion = tuple[Path, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class AcceptanceGroup:
    """按登记顺序发布; dependencies 只声明所需前置结论, 不继承其通过状态。"""

    name: str
    suffix: str
    write: Callable[[VerificationRun, bool], Conclusion]
    required: bool
    dependencies: tuple[str, ...] = ()
    recover: Callable[[VerificationRun, Path], Conclusion] | None = None
    propagate_interrupt: bool = True
    show_evidence: bool = False
    show_reasons: bool = False


@dataclass(slots=True)
class VerificationRun:
    root: Path
    output_dir: Path
    baseline: RunIdentity
    evidence_path: Path
    run_id: str
    groups: tuple[AcceptanceGroup, ...]
    conclusions: dict[str, Conclusion] = field(default_factory=dict)
    interrupted: bool = False

    @property
    def passed(self) -> bool:
        return not self.interrupted and all(
            group.name in self.conclusions
            and self.conclusions[group.name][1]["status"] == "passed"
            for group in self.groups
            if group.required
        )


def run_verification(
    root: Path,
    output_dir: Path,
    groups: tuple[AcceptanceGroup, ...],
    *,
    capture: Callable[[Path], RunIdentity] = capture_identity,
    execute: Callable[[Path, Path], Conclusion] | None = None,
) -> VerificationRun:
    """只运行一次计划, 依次发布结论并传递中断; 恢复规则由各组提供。"""
    names: set[str] = set()
    suffixes: set[str] = set()
    for group in groups:
        if (
            group.name in names
            or group.suffix in suffixes
            or not set(group.dependencies) <= names
        ):
            raise ValueError("验收组登记重复或缺少前置结论；请检查登记顺序。")
        names.add(group.name)
        suffixes.add(group.suffix)
    baseline = capture(root)
    evidence_path, evidence = (
        execute(root, output_dir)
        if execute is not None
        else run_offline_verification(root, default_checks(), output_dir)
    )
    run = VerificationRun(
        root, output_dir, baseline, evidence_path, evidence["run_id"], groups
    )
    for group in groups:
        try:
            conclusion = group.write(run, run.interrupted)
        except KeyboardInterrupt:
            if group.propagate_interrupt:
                run.interrupted = True
            if group.recover is None:
                raise
            conclusion = group.recover(run, output_dir / f"{run.run_id}{group.suffix}")
        run.conclusions[group.name] = conclusion
        path, result = conclusion
        if group.show_evidence:
            print(f"[{group.name} 验收] 离线证据：{evidence_path}")
        print(f"[{group.name} 验收] 结论：{path}")
        print(f"[{group.name} 验收] 结果：{result['status']}")
        if group.show_reasons:
            for reason in result["reasons"]:
                print(
                    f"[{group.name} 验收] 原因：{reason['code']}："
                    f"{reason['message_zh']}"
                )
    return run
