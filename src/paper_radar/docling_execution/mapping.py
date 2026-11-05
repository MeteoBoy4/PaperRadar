"""真实 Docling export 的无损源映射;不导入 SDK,不修补源区间。"""

from typing import Any, Protocol

from paper_radar.body.models import ParserFailure
from paper_radar.fulltext.canonical import (
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalProvenance,
)
from paper_radar.fulltext.normalization import canonical_json
from paper_radar.fulltext.quality import EMBEDDED_BINARY


class ExportableDocument(Protocol):
    def export_to_dict(self) -> dict[str, Any]: ...


def map_document(
    document: ExportableDocument,
    *,
    page_count: int,
    processed_pages: tuple[int, ...],
    has_text_layer: bool,
    formula_enabled: bool,
) -> tuple[CanonicalDocument, bytes]:
    try:
        return _map(
            document.export_to_dict(),
            page_count,
            processed_pages,
            has_text_layer,
            formula_enabled,
        )
    except ParserFailure:
        raise
    except (KeyError, ValueError, TypeError, IndexError, RecursionError):
        raise ParserFailure("extraction_failed_quality_gate") from None


def _map(
    raw: dict[str, Any],
    page_count: int,
    processed_pages: tuple[int, ...],
    has_text_layer: bool,
    formula_enabled: bool,
) -> tuple[CanonicalDocument, bytes]:
    if not has_text_layer:
        raise ParserFailure("extraction_failed_no_text_layer")
    expected = set(range(1, page_count + 1))
    if (
        page_count < 1
        or set(processed_pages) != expected
        or len(processed_pages) != page_count
    ):
        raise ValueError("缺页")
    if {int(p) for p in raw["pages"]} != expected:
        raise ValueError("缺页")
    pages = tuple(
        CanonicalPage(
            page_no=p["page_no"],
            width=float(p["size"]["width"]),
            height=float(p["size"]["height"]),
        )
        for p in raw["pages"].values()
    )
    if {p.page_no for p in pages} != expected:
        raise ValueError("页号不符")
    nodes: dict[str, dict[str, Any]] = {}
    for value in raw.values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "self_ref" in item:
                    if item["self_ref"] in nodes:
                        raise ValueError("重复节点")
                    nodes[item["self_ref"]] = item
    body = raw["body"]
    nodes[body["self_ref"]] = body
    furniture = raw.get("furniture")
    roots = [body]
    if furniture and furniture.get("children"):
        nodes[furniture["self_ref"]] = furniture
        roots.append(furniture)
    blocks: list[CanonicalBlock] = []
    visited: set[str] = set()

    def visit(
        item: dict[str, Any], order: tuple[int, ...], parent: str | None, in_table: bool
    ) -> None:
        ref = item["self_ref"]
        if ref in visited or (
            parent is not None and item.get("parent", {}).get("$ref") != parent
        ):
            raise ValueError("重复或父关系不符")
        visited.add(ref)
        layer = item.get("content_layer", "body")
        if layer not in {"body", "furniture", "background"}:
            raise ValueError("未知内容层")
        label = item.get("label", "group")
        orig = item.get("orig", "")
        text = item.get("text", "")
        if "text" in item and (
            "orig" not in item or (text and not orig and label != "formula")
        ):
            raise ValueError("文本缺少源字符")
        provenance = []
        for p in item.get("prov", []):
            bbox = p["bbox"]
            origin = bbox["coord_origin"]
            coords = (
                (bbox["l"], bbox["t"], bbox["r"], bbox["b"])
                if origin == "TOPLEFT"
                else (bbox["l"], bbox["b"], bbox["r"], bbox["t"])
            )
            if origin not in {"TOPLEFT", "BOTTOMLEFT"} or p["page_no"] not in expected:
                raise ValueError("定位不符")
            provenance.append(
                CanonicalProvenance(
                    page_no=p["page_no"],
                    bbox=(
                        float(coords[0]),
                        float(coords[1]),
                        float(coords[2]),
                        float(coords[3]),
                    ),
                    charspan=tuple(p["charspan"]),
                    origin="top_left" if origin == "TOPLEFT" else "bottom_left",
                )
            )
        if label == "table" and "orig" not in item:
            # 普通 cell.text 仅供受限展示;不伪造 orig 或字符证据。
            text = "\n".join(
                c["text"] for c in item.get("data", {}).get("table_cells", [])
            )
        source_label = "table" if in_table and orig else label
        blocks.append(
            CanonicalBlock(
                ref=ref,
                order=order,
                parent_ref=parent,
                label=source_label,
                orig=orig,
                text=text,
                content_layer=layer,
                role="source" if orig else "placeholder",
                heading_level=item.get("level"),
                generated_text=text
                if label == "formula" and formula_enabled and text
                else None,
                provenance=tuple(provenance),
            )
        )
        for index, child in enumerate(item.get("children", [])):
            visit(
                nodes[child["$ref"]], (*order, index), ref, in_table or label == "table"
            )

    for index, root in enumerate(roots):
        visit(root, (index,), None, False)
    if set(nodes) != visited or not any(b.orig.strip() for b in blocks):
        raise ValueError("孤立节点或缺正文")
    # 只删除 SDK 的已知 image 字段;源字符串完全保留,残余嵌入数据拒绝。
    for page in raw["pages"].values():
        page.pop("image", None)
    for node in nodes.values():
        node.pop("image", None)
    audit = canonical_json(raw)
    if EMBEDDED_BINARY.search(audit):
        raise ValueError("残留嵌入二进制")
    if not has_text_layer:
        raise ParserFailure("extraction_failed_no_text_layer")
    return CanonicalDocument(
        pages=pages, blocks=tuple(blocks), has_text_layer=has_text_layer
    ), audit
