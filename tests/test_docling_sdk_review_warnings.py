"""真实 SDK 数据与选项边界;转换器替身不加载模型、不解析 PDF。"""

import importlib.util
import json
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from paper_radar.docling_execution.models import WorkerRequest, WorkerResponse
from paper_radar.docling_execution.sdk import convert_document
from tests.test_docling_mapping import sample

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("docling_core") is None,
    reason="仅 extra+dev 的真实 SDK 数据与选项边界",
)


@pytest.mark.parametrize("missing", ["neither", "formula", "table", "both"])
def test_sdk_reports_only_missing_formula_candidate_and_table_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    document, _, _, formula = sample()
    if missing in {"formula", "both"}:
        formula.text = ""
    if missing in {"table", "both"}:
        TableData = import_module(
            "docling_core.types.doc.items.table.table_data"
        ).TableData
        document.add_table(data=TableData(num_rows=0, num_cols=0, table_cells=[]))
    sdk = import_module("docling.document_converter")
    backend = import_module("docling.backend.pypdfium2_backend")
    status = import_module("docling.datamodel.base_models").ConversionStatus
    input_format = import_module("docling.datamodel.base_models").InputFormat
    page = SimpleNamespace(
        get_text_cells=lambda: [SimpleNamespace(text="Synthetic native text")]
    )
    monkeypatch.setattr(backend.PyPdfiumDocumentBackend, "load_page", lambda *_: page)

    class Converter:
        def __init__(self, **options: Any) -> None:
            self.backend = options["format_options"][input_format.PDF].backend

        def initialize_pipeline(self, *_: Any) -> None:
            pass

        def convert(self, *_: Any, **__: Any) -> Any:
            # 驱动同一所选 backend 的原生文本信号,无需打开 PDF。
            self.backend.load_page(object.__new__(self.backend), 0)
            return SimpleNamespace(
                status=status.SUCCESS,
                input=SimpleNamespace(page_count=2),
                pages=[
                    SimpleNamespace(page_no=n, size=document.pages[n].size)
                    for n in (1, 2)
                ],
                document=document,
            )

    monkeypatch.setattr(sdk, "DocumentConverter", Converter)
    (tmp_path / "unused.pdf").write_bytes(b"synthetic converter input")
    response = convert_document(
        WorkerRequest(
            model_root=str(tmp_path),
            pdf_path=str(tmp_path / "unused.pdf"),
            response_path=str(tmp_path / "unused.json"),
            timeout_seconds=30.0,
            memory_limit_bytes=2**34,
            threads=1,
            backend_config_json=json.dumps(
                {
                    "pdf_backend": "pypdfium2",
                    "policy": {"do_formula_enrichment": True},
                    "table_mode": "accurate",
                }
            ),
            model_commits={"layout": "a" * 40, "formula": "b" * 40},
        )
    )
    expected = (
        ("formula_candidate_unavailable", "table_source_unavailable")
        if missing == "both"
        else ("formula_candidate_unavailable",)
        if missing == "formula"
        else ("table_source_unavailable",)
        if missing == "table"
        else ()
    )
    assert response.warnings == expected
    assert response.failure is None
    assert WorkerResponse.model_validate_json(response.model_dump_json()) == response
