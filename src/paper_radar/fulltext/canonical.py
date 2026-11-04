"""受控 parser 的唯一 canonical 权威;不接收论文外部元数据。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Origin = Literal["top_left", "bottom_left"]


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CanonicalPage(CanonicalModel):
    page_no: int = Field(gt=0)
    width: float = Field(gt=0, allow_inf_nan=False)
    height: float = Field(gt=0, allow_inf_nan=False)
    origin: Origin = "top_left"


class CanonicalProvenance(CanonicalModel):
    page_no: int
    bbox: tuple[float, float, float, float]
    charspan: tuple[int, int]
    origin: Origin = "top_left"


class CanonicalBlock(CanonicalModel):
    ref: str = Field(min_length=1)
    # Parser 给出的文档阅读路径,与 SDK item 容器的枚举顺序分离。
    order: tuple[int, ...] = Field(min_length=1)
    label: str = Field(min_length=1)
    orig: str = ""
    text: str = ""
    parent_ref: str | None = None
    heading_level: int | None = None
    content_layer: Literal["body", "furniture", "background"] = "body"
    role: Literal["source", "generated", "placeholder"] = "source"
    generated_text: str | None = None
    unreliable: bool = False
    formula_mode: Literal["display", "inline", "unknown"] = "unknown"
    provenance: tuple[CanonicalProvenance, ...] = ()


class CanonicalDocument(CanonicalModel):
    format_version: Literal[1] = 1
    conversion_status: Literal["success", "partial", "failure"] = "success"
    pages_complete: bool = True
    has_text_layer: bool = True
    pages: tuple[CanonicalPage, ...]
    blocks: tuple[CanonicalBlock, ...]
