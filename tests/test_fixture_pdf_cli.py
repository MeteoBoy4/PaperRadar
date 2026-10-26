"""固定四个 fixture 子命令的本地 PDF 与 backend 登记路径。"""

import json
from pathlib import Path

from typer.testing import CliRunner

from paper_radar.cli import app
from tests.fixture_pdf_support import PDF_BYTES, PDF_SHA256, registered_jgr


def test_cli_registers_pdf_then_backend_and_reports_separate_evidence_check(
    tmp_path: Path,
) -> None:
    service, record_id = registered_jgr(tmp_path)
    assert service.data_root is not None
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    request = tmp_path / "pdf-request.json"
    request.write_text(
        json.dumps(
            {
                "sample_record_id": record_id,
                "request_key": "pdf-cli",
                "source_url": "https://repository.example.org/pdf",
                "access_basis": "manual",
                "license_basis": "synthetic public fixture",
                "observed_date": "2026-10-26",
            }
        )
    )
    runner = CliRunner()
    arguments = [
        "--database",
        str(service.database),
        "--data-root",
        str(service.data_root),
        "--json",
    ]
    result = runner.invoke(
        app,
        ["fixture", "register", str(request), "--pdf-file", str(source), *arguments],
    )
    assert result.exit_code == 0, result.output
    pdf_id = json.loads(result.output)["pdf_id"]
    backend = tmp_path / "backend.json"
    backend.write_text(
        json.dumps(
            {
                "request_key": "backend-cli",
                "pdf_id": pdf_id,
                "pdf_sha256": PDF_SHA256,
                "backend_component": "docling",
                "backend_version": "synthetic-v1",
                "extraction_fingerprint": "a" * 64,
                "reading_sha256": "b" * 64,
                "methods_data": {"state": "unverified"},
                "availability_open_research": {
                    "state": "confirmed_absent",
                    "inspection_basis": "explicit synthetic inspection",
                },
            }
        )
    )
    result = runner.invoke(
        app, ["fixture", "register", str(backend), "--backend", *arguments]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["proof_level"] == "shape_only"
    checked = runner.invoke(app, ["fixture", "check", record_id, "--pdf", *arguments])
    assert checked.exit_code == 0, checked.output
    assert json.loads(checked.output)["backend_expectation_count"] == 1
    source.unlink()
    request.unlink()
    shown = runner.invoke(app, ["fixture", "show", record_id, *arguments])
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.output)["pdf"]["current_pdf_id"] == pdf_id
