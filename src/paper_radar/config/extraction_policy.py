"""封闭的 Docling 有效策略。不继承上游默认值。"""

from typing import Literal

from pydantic import field_validator
from pydantic_core import PydanticCustomError

from paper_radar.config.errors import VALIDATION_GUIDANCE, ConfigValidationReason
from paper_radar.config.extraction_models import FrozenExtractionConfig


class DoclingPolicy(FrozenExtractionConfig):
    """有效值显式冻结。禁止继承随上游版本漂移的 options 默认。"""

    device: Literal["cpu"] = "cpu"
    paper_execution: Literal["serial"] = "serial"
    do_ocr: Literal[False] = False
    do_formula_enrichment: bool = True
    do_code_enrichment: Literal[False] = False
    do_picture_classification: Literal[False] = False
    do_picture_description: Literal[False] = False
    do_chart_extraction: Literal[False] = False
    enable_remote_services: Literal[False] = False
    allow_external_plugins: Literal[False] = False
    do_table_structure: Literal[True] = True
    do_cell_matching: Literal[True] = True
    heading_hierarchy: Literal[True] = True
    keep_empty_clusters: Literal[False] = False
    force_backend_text: Literal[False] = False
    use_reading_order_separators: Literal[True] = True
    generate_page_images: Literal[False] = False
    generate_picture_images: Literal[False] = False
    generate_table_images: Literal[False] = False
    json_image_mode: Literal["placeholder"] = "placeholder"
    markdown_image_mode: Literal["placeholder"] = "placeholder"
    preserve_provenance: Literal[True] = True
    preserve_source_text: Literal[True] = True
    preserve_content_layer: Literal[True] = True
    formula_evidence: Literal["candidate_requires_pdf_review"] = (
        "candidate_requires_pdf_review"
    )
    separate_formula_source: Literal[True] = True
    formula_pdf_crop_review: Literal[True] = True
    trust_remote_code: Literal[False] = False
    formula_load_in_8bit: Literal[False] = False

    @field_validator("do_ocr", mode="before")
    @classmethod
    def reject_unsupported_ocr(cls, value: object) -> object:
        if value is True:
            reason = ConfigValidationReason.V1_OCR_DISABLED.value
            raise PydanticCustomError(reason, VALIDATION_GUIDANCE[reason])
        return value

    @field_validator("*", mode="before")
    @classmethod
    def strict_fixed_values(cls, value: object) -> object:
        # Pydantic Literal[False/True] 本身会接受 0/1。这里拒绝类型混用。
        if not isinstance(value, (str, bool)):
            raise ValueError("固定策略只接受明确的文本或布尔值")
        return value
