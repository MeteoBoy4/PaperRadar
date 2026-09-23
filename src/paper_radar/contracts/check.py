"""冻结契约快照的只读漂移检查。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from paper_radar.contracts.errors import ContractCheckError, ContractCheckErrorCategory
from paper_radar.contracts.schema import (
    ContractName,
    ContractSelectionError,
    ContractVersion,
    FrozenContract,
    build_selected_contract,
    select_contracts,
)
from paper_radar.contracts.snapshot import (
    CheckBlocked,
    CheckReady,
    verdict_for_check,
)


@dataclass(frozen=True, slots=True)
class ContractCheckResult:
    """一致快照的契约身份和磁盘位置。"""

    name: ContractName
    version: ContractVersion
    snapshot_dir: Path
    schema_sha256: str


class ContractCheckOutcome(StrEnum):
    """批量检查中单份契约的稳定结果。"""

    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ContractCheckItemResult:
    """批量检查中一份契约的完整只读报告。"""

    name: ContractName
    version: ContractVersion
    outcome: ContractCheckOutcome
    error_category: ContractCheckErrorCategory | None
    message_zh: str
    snapshot_dir: Path | None
    schema_sha256: str | None


@dataclass(frozen=True, slots=True)
class ContractBatchCheckResult:
    """完成全部已选检查后的有序汇总。"""

    items: tuple[ContractCheckItemResult, ...]

    @property
    def passed(self) -> bool:
        """仅当每份契约均一致时为真。"""
        return bool(self.items) and all(
            item.outcome is ContractCheckOutcome.PASSED for item in self.items
        )


def check_frozen_contract(
    name: ContractName | str,
    version: ContractVersion | str,
    target: Path | str,
) -> ContractCheckResult:
    """只读比较一份显式选择的冻结快照与当前权威定义。"""
    try:
        contract = build_selected_contract(name, version)
    except ContractSelectionError as error:
        raise ContractCheckError(
            ContractCheckErrorCategory.INVALID_SELECTION, str(error)
        ) from error

    verdict = verdict_for_check(target, contract)
    if isinstance(verdict, CheckBlocked):
        raise ContractCheckError(verdict.category, verdict.guidance_zh)
    return _checked_result(contract, verdict)


def _checked_result(contract: FrozenContract, ready: CheckReady) -> ContractCheckResult:
    return ContractCheckResult(
        name=contract.name,
        version=contract.version,
        snapshot_dir=ready.snapshot_dir,
        schema_sha256=contract.schema_sha256,
    )


def _select_contracts_for_check(
    names: Iterable[ContractName | str],
    version: ContractVersion | str,
) -> tuple[FrozenContract, ...]:
    try:
        return select_contracts(names, version)
    except ContractSelectionError as error:
        raise ContractCheckError(
            ContractCheckErrorCategory.INVALID_SELECTION, str(error)
        ) from error


def check_frozen_contracts(
    names: Iterable[ContractName | str],
    version: ContractVersion | str,
    target: Path | str,
) -> ContractBatchCheckResult:
    """先整体校验选择。随后按声明顺序完成全部独立只读检查。"""
    contracts = _select_contracts_for_check(names, version)
    items: list[ContractCheckItemResult] = []

    for contract in contracts:
        verdict = verdict_for_check(target, contract)
        if isinstance(verdict, CheckBlocked):
            items.append(
                ContractCheckItemResult(
                    name=contract.name,
                    version=contract.version,
                    outcome=ContractCheckOutcome.FAILED,
                    error_category=verdict.category,
                    message_zh=verdict.guidance_zh,
                    snapshot_dir=None,
                    schema_sha256=None,
                )
            )
            continue
        checked = _checked_result(contract, verdict)
        items.append(
            ContractCheckItemResult(
                name=checked.name,
                version=checked.version,
                outcome=ContractCheckOutcome.PASSED,
                error_category=None,
                message_zh="冻结契约一致：",
                snapshot_dir=checked.snapshot_dir,
                schema_sha256=checked.schema_sha256,
            )
        )

    return ContractBatchCheckResult(items=tuple(items))
