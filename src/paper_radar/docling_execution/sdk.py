"""仅在受限 worker 内调用的真实 SDK 入口。"""

import json
from collections.abc import Iterator
from importlib import import_module
from io import BytesIO
from pathlib import Path
from typing import Any

from paper_radar.body.models import ParserFailure
from paper_radar.docling_execution.mapping import map_document
from paper_radar.docling_execution.models import (
    WorkerRequest,
    WorkerResponse,
    WorkerWarning,
)


def convert_document(request: WorkerRequest) -> WorkerResponse:
    # 所有 SDK/native/model import 必须留在此函数,在 sandbox 建立之后。
    config = json.loads(request.backend_config_json)
    selected: Any = (
        import_module("docling.backend.pypdfium2_backend").PyPdfiumDocumentBackend
        if config["pdf_backend"] == "pypdfium2"
        else import_module(
            "docling.backend.docling_parse_backend"
        ).ThreadedDoclingParseDocumentBackend
    )
    AcceleratorDevice = import_module(
        "docling.datamodel.accelerator_options"
    ).AcceleratorDevice
    AcceleratorOptions = import_module(
        "docling.datamodel.accelerator_options"
    ).AcceleratorOptions
    ThreadedDoclingParseBackendOptions = import_module(
        "docling.datamodel.backend_options"
    ).ThreadedDoclingParseBackendOptions
    ConversionStatus = import_module("docling.datamodel.base_models").ConversionStatus
    InputFormat = import_module("docling.datamodel.base_models").InputFormat
    TransformersObjectDetectionEngineOptions = import_module(
        "docling.datamodel.object_detection_engine_options"
    ).TransformersObjectDetectionEngineOptions
    CodeFormulaVlmOptions = import_module(
        "docling.datamodel.pipeline_options"
    ).CodeFormulaVlmOptions
    HeadingHierarchyOptions = import_module(
        "docling.datamodel.pipeline_options"
    ).HeadingHierarchyOptions
    LayoutObjectDetectionOptions = import_module(
        "docling.datamodel.pipeline_options"
    ).LayoutObjectDetectionOptions
    PdfPipelineOptions = import_module(
        "docling.datamodel.pipeline_options"
    ).PdfPipelineOptions
    TableFormerMode = import_module(
        "docling.datamodel.pipeline_options"
    ).TableFormerMode
    TableStructureOptions = import_module(
        "docling.datamodel.pipeline_options"
    ).TableStructureOptions
    TransformersVlmEngineOptions = import_module(
        "docling.datamodel.vlm_engine_options"
    ).TransformersVlmEngineOptions
    DocumentConverter = import_module("docling.document_converter").DocumentConverter
    PdfFormatOption = import_module("docling.document_converter").PdfFormatOption
    ConversionError = import_module("docling.exceptions").ConversionError
    DocumentStream = import_module("docling_core.types.io").DocumentStream

    formula = config["policy"]["do_formula_enrichment"]
    layout = LayoutObjectDetectionOptions.from_preset(
        "layout_egret_medium",
        engine_options=TransformersObjectDetectionEngineOptions(
            torch_dtype="float32", compile_model=False
        ),
        keep_empty_clusters=False,
    )
    layout.model_spec.revision = request.model_commits["layout"]
    options = PdfPipelineOptions(
        artifacts_path=Path(request.model_root),
        document_timeout=request.timeout_seconds,
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CPU, num_threads=request.threads
        ),
        do_ocr=False,
        do_formula_enrichment=formula,
        do_code_enrichment=False,
        do_picture_classification=False,
        do_picture_description=False,
        do_chart_extraction=False,
        enable_remote_services=False,
        allow_external_plugins=False,
        do_table_structure=True,
        table_structure_options=TableStructureOptions(
            mode=TableFormerMode(config["table_mode"]), do_cell_matching=True
        ),
        layout_options=layout,
        heading_hierarchy_options=HeadingHierarchyOptions(enabled=True),
        force_backend_text=False,
        use_reading_order_separators=True,
        generate_page_images=False,
        generate_picture_images=False,
        generate_table_images=False,
        generate_parsed_pages=False,
        ocr_batch_size=1,
        layout_batch_size=1,
        table_batch_size=1,
        queue_max_size=8,
    )
    if formula:
        code_formula = CodeFormulaVlmOptions.from_preset(
            "codeformulav2",
            engine_options=TransformersVlmEngineOptions(
                device=AcceleratorDevice.CPU,
                load_in_8bit=False,
                quantized=False,
                torch_dtype="float32",
                trust_remote_code=False,
                compile_model=False,
            ),
            extract_code=False,
            extract_formulas=True,
            expansion_factor=0.18,
        )
        code_formula.model_spec.revision = request.model_commits["formula"]
        options.code_formula_options = code_formula
    native_text = [False]

    class ObservedBackend(selected):  # type: ignore[misc]
        # 同一所选后端的原生 cell 信号;不改变 generate_parsed_pages 与标题语义。
        def load_page(self, page_no: int) -> Any:
            page = super().load_page(page_no)
            if any(cell.text.strip() for cell in page.get_text_cells()):
                native_text[0] = True
            return page

        def iter_pages(self) -> Iterator[Any]:
            for page in super().iter_pages():
                if any(cell.text.strip() for cell in page.get_text_cells()):
                    native_text[0] = True
                yield page

    backend_options = None
    if config["pdf_backend"] == "threaded_docling_parse":
        backend_options = ThreadedDoclingParseBackendOptions(
            kind="threaded-docling-parse",
            enable_remote_fetch=False,
            enable_local_fetch=False,
            release_native_memory_every_n_pages=128,
            enforce_same_font=True,
            include_bitmap_images=False,
            render_pages=True,
            render_scale=1.0,
            parser_threads=request.threads,
        )
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                backend=ObservedBackend,
                backend_options=backend_options,
                pipeline_options=options,
            )
        },
    )
    # 明确将模型初始化失败与已进入文档转换的失败分开。
    try:
        converter.initialize_pipeline(InputFormat.PDF)
    except MemoryError:
        raise
    except Exception:
        raise ParserFailure("executor_error") from None
    try:
        result = converter.convert(
            DocumentStream(
                name="input.pdf", stream=BytesIO(Path(request.pdf_path).read_bytes())
            ),
            raises_on_error=False,
        )
    except (ConversionError, ValueError):
        raise ParserFailure("extraction_failed_quality_gate") from None
    if result.status != ConversionStatus.SUCCESS:
        raise ParserFailure("extraction_failed_quality_gate")
    if len(result.pages) != result.input.page_count or any(
        page.size is None
        or page.page_no not in result.document.pages
        or page.size != result.document.pages[page.page_no].size
        for page in result.pages
    ):
        raise ParserFailure("extraction_failed_quality_gate")
    if not native_text[0]:
        raise ParserFailure("extraction_failed_no_text_layer")
    document, raw = map_document(
        result.document,
        page_count=result.input.page_count,
        processed_pages=tuple(page.page_no for page in result.pages),
        has_text_layer=native_text[0],
        formula_enabled=formula,
    )
    warnings: list[WorkerWarning] = []
    if any(b.label == "formula" and not b.generated_text for b in document.blocks):
        warnings.append("formula_candidate_unavailable")
    if any(b.label == "table" and not b.orig for b in document.blocks):
        warnings.append("table_source_unavailable")
    return WorkerResponse(
        document=document, document_json=raw.decode("utf-8"), warnings=tuple(warnings)
    )
