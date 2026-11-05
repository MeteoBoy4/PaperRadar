"""#155 审查补充:展示警告与历史领取依据的公开消费。"""

import json
import sqlite3
from pathlib import Path

import pytest

from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadAnalysis, ReadTaskError, ReadTasks
from tests.read_tasks_support import ready, valid_candidate


@pytest.mark.parametrize("mode", ["numeric", "discard_only", "model_warning_only"])
def test_query_warning_distinguishes_diagnostics_from_discards_and_model_text(
    tmp_path: Path, mode: str
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    if mode == "numeric":
        raw = valid_candidate(
            main_findings=[
                {"statement": "得到 99。", "evidence": [{"evidence_id": "e000002"}]}
            ]
        )
    elif mode == "discard_only":
        raw = valid_candidate(
            key_limitations=[
                {"statement": "不保留此项。", "evidence": [{"evidence_id": "missing"}]}
            ]
        )
        refused = tasks.submit_test(tasks.claim(task.task_id), raw)
        assert not isinstance(refused, ReadAnalysis)
        assert refused.attempts[-1].failure == "output_invalid"
    else:
        raw = valid_candidate(degraded_content_warnings=["请人工复核模型自述。"])
    result = tasks.submit_test(tasks.claim(task.task_id), raw)
    assert isinstance(result, ReadAnalysis)
    assert [d["reason"] for d in result.diagnostics] == (
        ["number_not_supported"]
        if mode == "numeric"
        else ["evidence_item_discarded"]
        if mode == "discard_only"
        else []
    )
    view = ReadQueries(data.database, data.data_root).analysis(result.analysis_id)
    assert view.restricted_content_warning is (mode == "numeric")
    assert view.has_discards is (mode == "discard_only")
    assert view.output.degraded_content_warnings
    tasks.validate_all()


@pytest.mark.parametrize("damage", ["none", "missing", "extra", "bool", "int"])
def test_claim_basis_keeps_historical_shape_and_rejects_bad_keys_or_types(
    tmp_path: Path, damage: str
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    tasks.claim(task.task_id)
    basis = tasks.task(task.task_id).attempts[0].basis
    assert set(basis) == {
        "root_id",
        "purpose",
        "decision_id",
        "pdf_id",
        "sample_id",
        "quality_basis",
        "review_id",
        "execution_source",
        "recorded_at",
    }
    assert basis["purpose"] == "experiment"
    assert basis["quality_basis"] == "experiment_document_gate"
    assert basis["execution_source"] == "production"
    with sqlite3.connect(data.database) as connection:
        original = connection.execute(
            "SELECT basis_json FROM read_attempts"
        ).fetchone()[0]
        value = json.loads(original)
        if damage == "none":
            tasks.validate_all()
            assert (
                connection.execute("SELECT basis_json FROM read_attempts").fetchone()[0]
                == original
            )
            assert tasks.task(task.task_id).attempts[0].basis == basis
            return
        if damage == "missing":
            del value["sample_id"]
        elif damage == "extra":
            value["extra"] = None
        else:
            value["sample_id"] = True if damage == "bool" else 1
        connection.execute(
            "UPDATE read_attempts SET basis_json=?", (json.dumps(value),)
        )
    with pytest.raises(ReadTaskError, match="corrupt_reference"):
        tasks.validate_all()
