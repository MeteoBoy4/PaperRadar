"""收集仅核对分母, 与执行通过和正式回执分离。"""

import json
from pathlib import Path

import pytest

from scripts.verification_scope_collection import collect_counts


def test_parameter_collection_is_isolated_from_receipts_and_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "formal-receipt.json"
    receipt.write_text("historical receipt")
    monkeypatch.setenv("PAPER_RADAR_TEST_RECEIPT", str(receipt))
    monkeypatch.setenv("PAPER_RADAR_TEST_RUN_ID", "formal-run")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p scripts.a2_test_receipt -k missing")
    monkeypatch.setenv("PYTEST_PLUGINS", "scripts.a2_test_receipt")
    (tmp_path / "test_sample.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('x', ['SECRET-ONE', 'SECRET-TWO'])\n"
        "@pytest.mark.skip(reason='SECRET-SKIP')\n"
        "def test_sample(x):\n"
        "    raise AssertionError('must never execute')\n"
    )
    expected = {"test_sample.py": 2}
    report = collect_counts(tmp_path, expected)
    assert report["reason"] == "ok"
    assert report["modules"] == {"test_sample.py": 2}
    assert report["execution"] == "not_run"
    assert receipt.read_text() == "historical receipt"
    assert "SECRET" not in json.dumps(report)
    assert not (tmp_path / ".pytest_cache").exists()
    assert not (tmp_path / "__pycache__").exists()
    assert collect_counts(tmp_path, {"test_sample.py": 1})["reason"] == "count_mismatch"


@pytest.mark.parametrize(
    "source",
    [
        "raise RuntimeError('SECRET-ERROR')\n",
        "import pytest\npytest.skip('SECRET-SKIP', allow_module_level=True)\n",
        "# deleted tests\n",
    ],
)
def test_failed_or_skipped_collection_cannot_match(
    tmp_path: Path,
    source: str,
) -> None:
    (tmp_path / "test_sample.py").write_text(source)
    report = collect_counts(tmp_path, {"test_sample.py": 1})
    assert report["reason"] != "ok"
    assert "SECRET" not in json.dumps(report)


def test_deselection_is_distinct_from_collection_and_execution(tmp_path: Path) -> None:
    (tmp_path / "test_sample.py").write_text("def test_one(): pass\n")
    (tmp_path / "conftest.py").write_text(
        "def pytest_collection_modifyitems(config, items):\n"
        "    config.hook.pytest_deselected(items=items[:])\n"
        "    items.clear()\n"
    )
    report = collect_counts(tmp_path, {"test_sample.py": 1})
    assert report["reason"] == "collection_deselected"
    assert report["deselected"] == 1
    assert report["execution"] == "not_run"
