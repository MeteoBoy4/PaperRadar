"""主摘要区块切分、实体解码、标签清洗及段落连接规则 v1。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

from paper_radar.fixture_audit.abstract_models import (
    AbstractCandidate,
    ExcludedBlock,
    Signal,
)
from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.fixture_audit.models import Journal
from paper_radar.papers.text_rules import normalize_text

_MARKUP = re.compile(
    r"<!--|<![A-Za-z]|<\?|</?[A-Za-z][A-Za-z0-9:_-]*(?:\s+[^<>]*|\s*/?)>"
)
_LABELS = {
    "abstract": "main",
    "摘要": "main",
    "significance statement": "significance",
    "plain language summary": "plain_language_summary",
    "key points": "key_points",
}
_EXTRA_TOKENS = {
    "abstract-en": "abstract_en",
    "significance": "significance",
    "plain-language-summary": "plain_language_summary",
    "key-points": "key_points",
}

_BLOCKS = {"p", "div", "section", "br", "li", "jats:p"}


@dataclass(repr=False)
class Node:
    tag: str
    attrs: dict[str, str | None] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)


class Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if len(self.stack) > 100:
            raise ValueError("html_depth")
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {"meta", "link", "br", "hr", "img", "input", "source", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def nodes(node: Node) -> list[Node]:
    return [node] + [
        value
        for child in node.children
        if isinstance(child, Node)
        for value in nodes(child)
    ]


def text(node: Node, *, headings: bool = False) -> str:
    if node.tag in {"script", "style", "form", "nav"} or (
        not headings and re.fullmatch(r"h[1-6]", node.tag)
    ):
        return ""
    pieces = []
    for child in node.children:
        if isinstance(child, str):
            pieces.append(child)
        else:
            value = text(child, headings=headings)
            if child.tag in _BLOCKS:
                if pieces and not pieces[-1].endswith("\n"):
                    pieces.append("\n")
                pieces.append(value)
                if not value.endswith("\n"):
                    pieces.append("\n")
            else:
                pieces.append(value)
    return "".join(pieces)


def signals(value: str, *, residue: bool = False) -> tuple[Signal, ...]:
    result: list[Signal] = []
    tail = value.rstrip().rstrip("\"'”’»）)]}】》」』")
    if len(value) < 100:
        result.append("short_under_100")
    if tail.endswith(("...", "…")):
        result.append("trailing_ellipsis")
    if re.search(r"(?:read\s+more|阅读更多)[\s.!。！…]*$", tail, re.I):
        result.append("read_more")
    if residue or _MARKUP.search(value):
        result.append("markup_residue")
    if not tail.endswith((".", "?", "!", "。", "？", "！")) or tail.endswith(
        ("...", "…")
    ):
        result.append("missing_terminal_punctuation")
    return tuple(result)


def _clean(value: str) -> tuple[str, bool]:
    residue = bool(_MARKUP.search(value))
    # 实体解码后仍呈真实标签的字面残留单独披露,清除后才进入 A6 规范形式。
    return normalize_text(_MARKUP.sub("", value)), residue


def _fragment(
    raw: str, *, journal: Journal, feed: bool = False
) -> tuple[str, tuple[ExcludedBlock, ...]]:
    tree = Tree()
    tree.feed(raw)
    root = tree.root
    excluded: list[ExcludedBlock] = []

    def prune(node: Node) -> None:
        kept: list[Node | str] = []
        for index, child in enumerate(node.children):
            if isinstance(child, Node):
                tokens = set((child.attrs.get("class") or "").split()) | {
                    child.attrs.get("id") or ""
                }
                kind = next(
                    (kind for token, kind in _EXTRA_TOKENS.items() if token in tokens),
                    None,
                )
                if kind:
                    excluded.append(
                        ExcludedBlock.model_validate(
                            dict(kind=kind, locator=f"{node.tag}/child[{index}]")
                        )
                    )
                    continue
                prune(child)
            kept.append(child)
        node.children = kept

    prune(root)
    if feed and journal == "dqkx":
        paragraphs = [node for node in nodes(root) if node.tag == "p"]
        if paragraphs:

            def outside(node: Node) -> str:
                if node.tag == "p":
                    return ""
                return "".join(
                    child if isinstance(child, str) else outside(child)
                    for child in node.children
                )

            if outside(root).strip():
                excluded.append(
                    ExcludedBlock(kind="citation_tail", locator="description/outside-p")
                )
            return "\n".join(text(node).strip() for node in paragraphs), tuple(excluded)
        return "", tuple(excluded)
    # 标签可为标题、粗体、独立段落;只有完整字面标签才建立区块边界。
    flat = nodes(root)
    labels = [
        (node, _LABELS[text(node, headings=True).strip().rstrip(":：").lower()])
        for node in flat
        if node.tag in {"h1", "h2", "h3", "h4", "h5", "b", "strong", "p", "jats:title"}
        and text(node, headings=True).strip().rstrip(":：").lower() in _LABELS
    ]
    if labels:
        target: list[str] = []
        mode = "preface"
        label_ids = {id(node): kind for node, kind in labels}
        for _node, kind in labels:
            if kind != "main":
                excluded.append(
                    ExcludedBlock.model_validate(
                        dict(kind=kind, locator=f"label/{kind}")
                    )
                )
        if (
            text(root, headings=True)
            .split(text(labels[0][0], headings=True), 1)[0]
            .strip()
        ):
            excluded.append(ExcludedBlock(kind="preface", locator="before-first-label"))

        def walk(node: Node) -> None:
            nonlocal mode
            if id(node) in label_ids:
                mode = label_ids[id(node)]
                return
            for child in node.children:
                if isinstance(child, str):
                    if mode == "main":
                        target.append(child)
                else:
                    if child.tag in {"script", "style", "form"}:
                        continue
                    if (
                        child.tag in _BLOCKS
                        and mode == "main"
                        and target
                        and not target[-1].endswith("\n")
                    ):
                        target.append("\n")
                    walk(child)
                    if (
                        child.tag in _BLOCKS
                        and mode == "main"
                        and target
                        and not target[-1].endswith("\n")
                    ):
                        target.append("\n")

        walk(root)
        return "".join(target).strip(), tuple(excluded)
    return text(root).strip(), tuple(excluded)


def parse_material(
    request: SourceRequest,
    raw: bytes,
    *,
    decoding: str,
    acquisition_id: str,
    entry_locator: str | None = None,
    feed_item: ET.Element | None = None,
) -> tuple[
    tuple[AbstractCandidate, ...], tuple[ExcludedBlock, ...], dict[str, str], bool
]:
    """返回安全候选、额外区块定位、显式读取用文本及可识别主区块形状。"""
    source_kind = (
        "feed"
        if request.route == "feed"
        else "publisher"
        if request.route == "publisher"
        else "registry"
    )
    title, abstract, locator = "", "", ""
    title_locator = "title"
    excluded: tuple[ExcludedBlock, ...] = ()
    recognized = True
    decoded = raw.decode(decoding)
    if request.route == "feed":
        root = ET.fromstring(decoded)
        # audit-abstract-v1 retains its historical tolerant container semantics.
        # Production supplies its already validated root-level physical item.
        if feed_item is None:
            container = (
                next(
                    (
                        child
                        for child in root
                        if child.tag.rsplit("}", 1)[-1] == "channel"
                    ),
                    root,
                )
                if root.tag.rsplit("}", 1)[-1] == "rss"
                else root
            )
            items = [
                node
                for node in container
                if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}
            ]
            index = int((entry_locator or "item[1]").split("[")[1].rstrip("]")) - 1
            item = items[index]
        else:
            item = feed_item
        for child in item:
            name = child.tag.rsplit("}", 1)[-1]
            if name == "title":
                title = "".join(child.itertext())
                title_locator = f"{entry_locator}/title"
            elif name in {"description", "summary", "content"} and not locator:
                # XML child markup stays markup; escaped HTML goes to HTMLParser.
                inner = (child.text or "") + "".join(
                    ET.tostring(part, encoding="unicode") for part in child
                )
                abstract, excluded = _fragment(
                    inner, journal=request.journal, feed=True
                )
                locator = f"{entry_locator}/{name}"
    elif request.route == "publisher":
        tree = Tree()
        tree.feed(decoded)
        all_nodes = nodes(tree.root)
        title = next(
            (
                node.attrs.get("content") or ""
                for node in all_nodes
                if node.tag == "meta" and node.attrs.get("name") == "citation_title"
            ),
            "",
        )
        title_locator = "meta[name=citation_title]@content"
        selectors = (
            {"abstract-cn"}
            if request.journal == "dqkx"
            else {"abstract", "article-section__abstract", "abstractSection"}
        )
        primary = []
        extras: list[ExcludedBlock] = []
        for index, node in enumerate(all_nodes):
            tokens = set((node.attrs.get("class") or "").split()) | {
                node.attrs.get("id") or ""
            }
            for token, kind in _EXTRA_TOKENS.items():
                if token in tokens:
                    extras.append(
                        ExcludedBlock.model_validate(
                            dict(kind=kind, locator=f"html/node[{index}]")
                        )
                    )
            if tokens & selectors:
                primary.append((index, node))
        recognized = len(primary) == 1
        if recognized:
            index, node = primary[0]
            # 同一主容器中的附加区块也按标签隔离。
            abstract, within = _fragment(_serialize(node), journal=request.journal)
            excluded = tuple(extras) + within
            locator = f"html/node[{index}]"
        else:
            excluded = tuple(extras)
    elif request.route == "registry_crossref":
        message = json.loads(raw)["message"]
        title_locator = "message.title[0]"
        titles = message.get("title", [])
        title = (
            titles[0]
            if isinstance(titles, list) and titles and isinstance(titles[0], str)
            else ""
        )
        value = message.get("abstract", "")
        if isinstance(value, str):
            abstract, excluded = _fragment(value, journal=request.journal)
        locator = "message.abstract"
    elif request.route == "registry_datacite":
        attributes = json.loads(raw)["data"]["attributes"]
        titles = attributes.get("titles", [])
        if isinstance(titles, list):
            title_locator = "data.attributes.titles/title"
            title = next(
                (
                    value["title"]
                    for value in titles
                    if isinstance(value, dict) and isinstance(value.get("title"), str)
                ),
                "",
            )
        descriptions = attributes.get("descriptions", [])
        if isinstance(descriptions, list):
            for index, value in enumerate(descriptions):
                if (
                    isinstance(value, dict)
                    and value.get("descriptionType") == "Abstract"
                    and isinstance(value.get("description"), str)
                ):
                    abstract, excluded = _fragment(
                        value["description"], journal=request.journal
                    )
                    locator = f"data.attributes.descriptions[{index}]"
                    break
    results: list[AbstractCandidate] = []
    texts: dict[str, str] = {}
    for name, value, location in (
        ("title", title, title_locator),
        ("abstract", abstract, locator),
    ):
        clean, residue = _clean(value)
        if not clean:
            continue
        digest = hashlib.sha256(clean.encode()).hexdigest()
        identity = hashlib.sha256(
            (
                f"{acquisition_id}\0{entry_locator or ''}\0{name}\0{location}\0{digest}"
            ).encode()
        ).hexdigest()
        flags = signals(clean, residue=residue) if name == "abstract" else ()
        results.append(
            AbstractCandidate.model_validate(
                dict(
                    candidate_id=identity,
                    field=name,
                    source_kind=source_kind,
                    locator=location,
                    text_sha256=digest,
                    codepoints=len(clean),
                    signals=flags,
                    suspected_truncated=bool(flags),
                )
            )
        )
        texts[identity] = clean
    return tuple(results), excluded, texts, recognized


def _serialize(node: Node) -> str:
    from html import escape

    attributes = " ".join(
        f'{key}="{escape(value or "", quote=True)}"'
        for key, value in node.attrs.items()
    )
    body = "".join(
        escape(child) if isinstance(child, str) else _serialize(child)
        for child in node.children
    )
    return f"<{node.tag} {attributes}>{body}</{node.tag}>"
