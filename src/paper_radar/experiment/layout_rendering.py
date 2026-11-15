"""仅从登记 PDF 渲染私有六项对照;字符事实仍由持久 map 提供。"""

import hashlib
import html
import importlib
import json
import math
import os
import tempfile
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from paper_radar.experiment.layout_errors import LayoutError
from paper_radar.fulltext.models import EvidenceMap, ReadingBlock

if TYPE_CHECKING:
    from paper_radar.experiment.layout import LayoutBody
    from paper_radar.experiment.root import ExperimentRoot


class PdfRenderer:
    """延迟导入的 PDFium/Pillow 外部边界;不 import Docling 或模型。"""

    def render(self, pdf: bytes, evidence_map: EvidenceMap, directory: Path) -> None:
        try:
            pdfium = importlib.import_module("pypdfium2")
            drawing = importlib.import_module("PIL.ImageDraw")
        except ImportError:
            raise LayoutError("renderer_dependency_missing") from None
        try:
            with pdfium.PdfDocument(pdf) as document:
                if len(document) != len(evidence_map.pages) or len(document) > 1000:
                    raise LayoutError("pdf_pages_mismatch")
                pixels = 0
                for fact in evidence_map.pages:
                    with closing(document[fact.page_no - 1]) as page:
                        left, bottom, right, top = page.get_bbox()
                        if (
                            abs(right - left - fact.width) > 1
                            or abs(top - bottom - fact.height) > 1
                        ):
                            raise LayoutError("pdf_geometry_mismatch")
                        width, height = page.get_size()
                        scale = min(1.5, 1600 / max(width, height))
                        pixels += math.ceil(width * scale) * math.ceil(height * scale)
                        if pixels > 100_000_000:
                            raise LayoutError("render_limit_exceeded")
                        with closing(page.render(scale=scale)) as bitmap:
                            image = bitmap.to_pil().copy()
                            converter = bitmap.get_posconv(page)
                            overlay = image.copy()
                            draw = drawing.Draw(overlay)
                            for number, block in enumerate(
                                evidence_map.reading_blocks, 1
                            ):
                                for index, location in enumerate(block.provenance):
                                    if location.page_no != fact.page_no:
                                        continue
                                    x0, y0, x1, y1 = location.bbox
                                    # PDFium 使用原生坐标;top_left 按页面上边翻转。
                                    # 然后由位图位置转换器处理页面 rotation/cropbox。
                                    points = []
                                    for x in (x0, x1):
                                        for y in (y0, y1):
                                            px = left + x
                                            py = (
                                                top - y
                                                if location.origin == "top_left"
                                                else bottom + y
                                            )
                                            points.append(converter.to_bitmap(px, py))
                                    box = (
                                        max(0, min(p[0] for p in points)),
                                        max(0, min(p[1] for p in points)),
                                        min(image.width, max(p[0] for p in points)),
                                        min(image.height, max(p[1] for p in points)),
                                    )
                                    if box[2] <= box[0] or box[3] <= box[1]:
                                        raise LayoutError("pdf_geometry_mismatch")
                                    crop = image.crop(box)
                                    crop.save(directory / f"block-{number}-{index}.png")
                                    crop.close()
                                    draw.rectangle(box, outline="red", width=2)
                                    draw.text(
                                        (box[0], box[1]), str(number), fill="blue"
                                    )
                            image.save(directory / f"page-{fact.page_no}.png")
                            overlay.save(directory / f"order-{fact.page_no}.png")
                            # 全页上下边缘也供发现 parser 未识别的家具;旋转后视觉边缘。
                            for label, box in (
                                ("top", (0, 0, image.width, max(1, image.height // 6))),
                                (
                                    "bottom",
                                    (
                                        0,
                                        image.height * 5 // 6,
                                        image.width,
                                        image.height,
                                    ),
                                ),
                            ):
                                margin = image.crop(box)
                                margin.save(
                                    directory / f"margin-{fact.page_no}-{label}.png"
                                )
                                margin.close()
                            overlay.close()
                            image.close()
        except LayoutError:
            raise
        except Exception:
            raise LayoutError("pdf_render_failed") from None


def _text(value: object) -> str:
    return html.escape(str(value))


def _image(name: str, directory: Path) -> str:
    if not (directory / name).is_file():
        return "<p>裁切缺失或无可定位来源；请对照整页。</p>"
    return (
        f'<a href="{name}"><img loading="lazy" style="max-width:100%" src="{name}"></a>'
    )


def _block(number: int, block: ReadingBlock, directory: Path) -> str:
    result = (
        f"<h3>块 {number}: {_text(block.block_id)}</h3>"
        f"<pre>{_text(block.display_text)}</pre>"
    )
    result += (
        f"<p>parent={_text(block.parent_id)} label={_text(block.label)} "
        f"层级={_text(block.heading_level)} 去留={_text(block.excluded or '保留')}</p>"
    )
    if not block.provenance:
        result += "<p>无定位来源；不能构造 bbox 或 evidence。</p>"
    for index, location in enumerate(block.provenance):
        result += (
            f"<p>PDF页={location.page_no} bbox={_text(location.bbox)} "
            f"原点={location.origin} charspan={_text(location.charspan)}</p>"
        )
        result += _image(f"block-{number}-{index}.png", directory)
    return result


def render_materials(root: "ExperimentRoot", body: "LayoutBody") -> list[str]:
    identity = body.loaded.identity
    material_id = hashlib.sha256(
        json.dumps(asdict(identity), sort_keys=True).encode()
    ).hexdigest()
    destination = root.views / f"layout-{material_id}"
    if destination.is_symlink():
        raise LayoutError("unsafe_material_path")
    root.views.mkdir(exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".layout-", dir=root.views) as temporary:
        stage = Path(temporary)
        PdfRenderer().render(body.pdf, body.evidence_map, stage)
        blocks = list(enumerate(body.evidence_map.reading_blocks, 1))
        included = [(n, b) for n, b in blocks if b.excluded is None]
        source_by_id = {s.source_id: s for s in body.evidence_map.source_blocks}
        pages = "".join(
            f"<h3>PDF页 {p.page_no}</h3>" + _image(f"page-{p.page_no}.png", stage)
            for p in body.evidence_map.pages
        )
        boundary = (
            "<p>首尾按持久阅读顺序；容器无定位如实展示，"
            "整页用于核对所有正文与排除区。</p>"
        )
        for name, selected in (("起点", included[:1]), ("终点", included[-1:])):
            boundary += f"<h2>{name}</h2>" + "".join(
                _block(n, b, stage) for n, b in selected
            )
        boundary += pages
        order = (
            "<p>编号是持久 canonical reading_blocks 顺序；"
            "排除块也列出，不声称恢复 SDK 原遍历路径。</p>"
        )
        order += "".join(
            _image(f"order-{p.page_no}.png", stage) for p in body.evidence_map.pages
        )
        order += "".join(_block(n, b, stage) for n, b in blocks)
        headings = [(n, b) for n, b in blocks if b.heading_level is not None]
        sections = (
            "<p>层级为持久 normalize 结果；无逐项修复理由。</p>"
            + (
                "".join(_block(n, b, stage) for n, b in headings)
                or "<p>标题类别未覆盖；请核对整页。</p>"
            )
            + pages
        )
        furniture = (
            "<p>列出全部块去留并裁切；具体排除规则理由未持久化。"
            "上下页边可发现 parser 未识别家具。</p>"
        )
        furniture += "".join(
            _image(f"margin-{p.page_no}-{side}.png", stage)
            for p in body.evidence_map.pages
            for side in ("top", "bottom")
        )
        furniture += "".join(_block(n, b, stage) for n, b in blocks)
        evidence = (
            "<p>确定性抽样：首/中/尾 evidence 及首个 "
            "table/formula/unreliable evidence；无模型判断。"
            "charspan 为 source.orig 半开索引。</p>"
        )
        entries = body.evidence_map.evidence
        selected_ids = set()
        if entries:
            selected_ids = {
                entries[0].evidence_id,
                entries[len(entries) // 2].evidence_id,
                entries[-1].evidence_id,
            }
            for entry in entries:
                source = source_by_id[entry.source_id]
                if source.kind != "text" or source.unreliable:
                    selected_ids.add(entry.evidence_id)
                    break
        for entry in entries:
            if entry.evidence_id not in selected_ids:
                continue
            source = source_by_id[entry.source_id]
            evidence += (
                f"<h2>{_text(entry.evidence_id)} "
                f"source={_text(entry.source_id)}</h2>"
                f"<p>orig 完整源：</p><pre>{_text(source.orig)}</pre>"
            )
            for part in body.loaded.lookup(entry.evidence_id):
                p = part.provenance
                evidence += (
                    '<div class="comparison"><div>'
                    f"<p>PDF页={p.page_no} bbox={_text(p.bbox)} "
                    f"charspan=[{p.start},{p.end})</p>"
                    f"<pre>{_text(part.text)}</pre>"
                    "</div><div>"
                )
                for number, block in blocks:
                    if block.source_id == entry.source_id:
                        for index, location in enumerate(block.provenance):
                            if location.page_no == p.page_no and location.charspan == (
                                p.start,
                                p.end,
                            ):
                                evidence += _image(f"block-{number}-{index}.png", stage)
                evidence += "</div></div>"
        restricted = (
            "<p>表格精确值、公式科学符号、不可靠字符均待人工核对；"
            "候选与占位没有 evidence。零类别是未覆盖，"
            "不表示 PDF 没有该类别。</p>"
        )
        for category in ("formula", "table", "unreliable"):
            candidates = [
                (n, b)
                for n, b in blocks
                if (
                    b.label == category
                    or (
                        b.source_id in source_by_id
                        and (
                            source_by_id[b.source_id].unreliable
                            if category == "unreliable"
                            else source_by_id[b.source_id].kind == category
                        )
                    )
                )
            ]
            restricted += f"<h2>{category}</h2>"
            if not candidates:
                restricted += "<p>未覆盖</p>"
            for number, block in candidates:
                restricted += (
                    f"<p>降级：受限内容待核对；role={_text(block.role)} "
                    f"formula_mode={_text(block.formula_mode)}；生成候选不可作为原文："
                    f"{_text(block.generated_text)}</p>" + _block(number, block, stage)
                )
        names = (
            "body-boundary",
            "reading-order",
            "sections",
            "headers-footers",
            "provenance",
            "restricted-content",
        )
        titles = (
            "正文起止",
            "阅读顺序",
            "标题层级",
            "页眉页脚",
            "抽样 evidence",
            "受限内容降级",
        )
        contents = (boundary, order, sections, furniture, evidence, restricted)
        header = (
            "<!doctype html><html lang=zh><meta charset=utf-8>"
            "<meta name=referrer content=no-referrer><title>私有版式对照</title>"
            "<style>.comparison{display:grid;grid-template-columns:1fr 1fr;gap:1rem}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>"
        )
        header += (
            "<p>六项材料仅供所有者核查；未填写任何结论。</p><pre>"
            + _text(json.dumps(asdict(identity), sort_keys=True))
            + "</pre>"
        )
        for name, title, content in zip(names, titles, contents, strict=True):
            (stage / f"{name}.html").write_text(
                header + f"<h1>{title}</h1>" + content + "</html>"
            )
        (stage / "index.html").write_text(
            header
            + "".join(
                f'<p><a href="{name}.html">{title}</a></p>'
                for name, title in zip(names, titles, strict=True)
            )
            + "</html>"
        )
        for path in stage.iterdir():
            path.chmod(0o600)
        if destination.exists():
            if not destination.is_dir() or any(
                p.is_symlink() or not p.is_file() for p in destination.iterdir()
            ):
                raise LayoutError("unsafe_material_path")
            if {p.name: p.read_bytes() for p in destination.iterdir()} != {
                p.name: p.read_bytes() for p in stage.iterdir()
            }:
                raise LayoutError("materials_conflict")
        else:
            os.rename(stage, destination)
            # TemporaryDirectory 可回收已移动路径;不删除发布目录。
        return [
            str((destination / f"{name}.html").relative_to(root.root)) for name in names
        ]
