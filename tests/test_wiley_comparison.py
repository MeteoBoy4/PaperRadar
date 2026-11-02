"""Issue #146 review: reproducible offline comparison through its public boundary."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.compare_wiley_abstracts import compare_wiley_abstracts, main
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service
from tests.test_wiley_abstract_v2 import MAIN, NOTE, feed


def test_comparison_reproduces_safe_fields_without_mutating_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sources = MatrixSources()
    for url in sources.feeds:
        if "wiley.com" in url:
            sources.feeds[url] = feed(
                "<dc:identifier>10.1029/synthetic</dc:identifier>"
                f"<description>{NOTE}</description>"
                "<content:encoded><![CDATA[<h2>Abstract</h2>"
                f"<p>{MAIN}</p>]]></content:encoded>"
            )
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert service.data_root
    before = service.replay_audit(view.plan.plan_id)
    report = compare_wiley_abstracts(
        service.database, service.data_root, view.plan.plan_id
    )
    assert report["original_semantic_sha256"] == before.semantic_sha256
    assert report["original_unchanged"] is True
    assert report["network_attempts"] == 0
    decoded = json.loads(json.dumps(report))
    assert len(decoded["records"]) == 2
    for record in decoded["records"]:
        assert record["changed"] == ["abstract"]
        assert (
            record["old"]["abstract"]["text_sha256"]
            == hashlib.sha256(NOTE.encode()).hexdigest()
        )
        assert (
            record["new"]["abstract"]["text_sha256"]
            == hashlib.sha256(MAIN.encode()).hexdigest()
        )
    assert service.replay_audit(view.plan.plan_id) == before
    assert MAIN not in json.dumps(report)
    assert NOTE not in json.dumps(report)

    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps(report))
    arguments = [
        "--database",
        str(service.database),
        "--data-root",
        str(service.data_root),
        "--plan-id",
        view.plan.plan_id,
        "--check",
        str(expected),
    ]
    assert main(arguments) == 0
    assert "逐字段一致" in capsys.readouterr().out
    report["status"] = "incorrect"
    expected.write_text(json.dumps(report))
    assert main(arguments) == 1
    assert "差异不一致" in capsys.readouterr().out
    assert service.replay_audit(view.plan.plan_id) == before
