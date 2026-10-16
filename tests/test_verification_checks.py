"""共享验收原语在各组公开数据上的复用边界。"""

from pathlib import Path

import pytest

from scripts.verification_checks import receipt_records, same_run_document


@pytest.mark.parametrize("invalid", [True, False, -1, None, "1"])
def test_receipt_counts_require_real_nonnegative_integers(invalid: object) -> None:
    records = receipt_records(
        {
            "tests/synthetic.py": {
                "collected": 1,
                "passed": invalid,
                "failed": 0,
                "skipped": 0,
                "deselected": 0,
                "incomplete": 0,
            }
        },
        {"tests/synthetic.py": 1},
    )
    assert records == [
        {
            "path": "tests/synthetic.py",
            "expected_cases": 1,
            "collected": 1,
            "passed": None,
            "failed": 0,
            "skipped": 0,
            "deselected": 0,
            "incomplete": 0,
            "result": "failed",
        }
    ]


def test_same_run_document_requires_filename_identity_and_returned_content(
    tmp_path: Path,
) -> None:
    path = tmp_path / "run.synthetic.json"
    path.write_text('{"run_id":"run","verified":true}', encoding="utf-8")
    returned = {"run_id": "run", "verified": True}
    assert same_run_document(path, "run", ".synthetic.json", returned)
    assert not same_run_document(path, "other", ".synthetic.json", returned)
    assert not same_run_document(path, "run", ".other.json", returned)
    assert not same_run_document(
        path, "run", ".synthetic.json", {"run_id": "run", "verified": False}
    )
