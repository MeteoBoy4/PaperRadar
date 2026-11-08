"""独立未绑定预算原型:重启/中断/失明/超额拒绝。"""

import sqlite3
from pathlib import Path

import pytest

from scripts.issue167_budget import LAYERS, BudgetBook, BudgetRejected, FrozenPlan


def plan(total: int = 2) -> FrozenPlan:
    return FrozenPlan(
        ("case-a", "case-b"), dict.fromkeys(LAYERS, 1), dict.fromkeys(LAYERS, total)
    )


def test_restart_new_run_and_zero_usage_never_refund(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    first = BudgetBook.create(path, plan())
    first.reserve("case-a", "run-first")
    first.close()  # 模拟dispatch后的controller中断,没有结算。
    second = BudgetBook(path, plan())
    try:
        with pytest.raises(BudgetRejected, match=r"^case_already_reserved$"):
            second.reserve("case-a", "new-run-id")
        with pytest.raises(BudgetRejected, match=r"^previous_attempt_unsettled$"):
            second.reserve("case-b", "cannot_skip_cleanup")
        second.settle("case-a", dict.fromkeys(LAYERS, 0), cleanup_verified=True)
        with pytest.raises(BudgetRejected, match=r"^case_already_reserved$"):
            second.reserve("case-a", "after-zero-report")
        second.reserve("case-b", "next-case")
    finally:
        second.close()


def test_independent_connections_share_upper_bound(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    first = BudgetBook.create(path, plan(1))
    second = BudgetBook(path, plan(1))
    try:
        first.reserve("case-a", "run-a")
        first.settle("case-a", dict.fromkeys(LAYERS, 1), cleanup_verified=True)
        with pytest.raises(BudgetRejected, match=r"^budget_exhausted$"):
            second.reserve("case-b", "run-b")
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize(
    "actual",
    [
        None,
        {"model_operation": 1},
        dict.fromkeys(LAYERS, 2),
        dict.fromkeys(LAYERS, True),
    ],
)
def test_unknown_excess_or_invalid_observation_blocks_after_restart(
    tmp_path: Path, actual: dict[str, int] | None
) -> None:
    path = tmp_path / "ledger.db"
    first = BudgetBook.create(path, plan())
    first.reserve("case-a", "run-a")
    with pytest.raises(BudgetRejected, match=r"^observation_unknown_or_excess$"):
        first.settle("case-a", actual, cleanup_verified=True)
    first.close()
    second = BudgetBook(path, plan())
    try:
        with pytest.raises(BudgetRejected, match=r"^ledger_blocked$"):
            second.reserve("case-b", "new-run-id")
    finally:
        second.close()


def test_no_overwrite_no_recreate_and_plan_drift(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    first = BudgetBook.create(path, plan())
    first.close()
    with pytest.raises(FileExistsError):
        BudgetBook.create(path, plan())
    with pytest.raises(BudgetRejected, match=r"^ledger_invalid$"):
        BudgetBook(path, plan(1))
    path.unlink()
    with pytest.raises(sqlite3.OperationalError):
        BudgetBook(path, plan())
    assert not path.exists()


def test_unapproved_case_duplicate_settlement_and_mutated_plan(tmp_path: Path) -> None:
    frozen = plan()
    book = BudgetBook.create(tmp_path / "ledger.db", frozen)
    try:
        with pytest.raises(BudgetRejected, match=r"^case_unapproved$"):
            book.reserve("not-in-frozen-plan", "run")
        book.reserve("case-a", "run")
        book.settle("case-a", dict.fromkeys(LAYERS, 1), cleanup_verified=True)
        with pytest.raises(BudgetRejected, match=r"^reservation_not_pending$"):
            book.settle("case-a", dict.fromkeys(LAYERS, 0))
        frozen.per_case["prompt"] = 0
        with pytest.raises(BudgetRejected, match=r"^plan_mutated$"):
            book.reserve("case-b", "run-b")
    finally:
        book.close()


def test_missing_cleanup_blocks_even_with_known_zero_counts(tmp_path: Path) -> None:
    book = BudgetBook.create(tmp_path / "ledger.db", plan())
    try:
        book.reserve("case-a", "run-a")
        with pytest.raises(BudgetRejected, match=r"^observation_unknown_or_excess$"):
            book.settle("case-a", dict.fromkeys(LAYERS, 0))
        with pytest.raises(BudgetRejected, match=r"^ledger_blocked$"):
            book.reserve("case-b", "run-b")
    finally:
        book.close()


def test_invalid_plan_at_settlement_persists_block_even_after_restore(
    tmp_path: Path,
) -> None:
    frozen = plan()
    path = tmp_path / "ledger.db"
    book = BudgetBook.create(path, frozen)
    book.reserve("case-a", "run-a")
    frozen.per_case["prompt"] = -1
    with pytest.raises(BudgetRejected, match=r"^observation_unknown_or_excess$"):
        book.settle("case-a", dict.fromkeys(LAYERS, 0), cleanup_verified=True)
    book.close()
    reopened = BudgetBook(path, plan())
    try:
        with pytest.raises(BudgetRejected, match=r"^ledger_blocked$"):
            reopened.reserve("case-b", "after-plan-restored")
    finally:
        reopened.close()
