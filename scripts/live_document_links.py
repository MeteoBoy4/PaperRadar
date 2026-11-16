"""只读校验 inventory 精确登记的活文档,目标可为任意仓库内文件。"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline, image, link
from markdown_it.token import Token


class LinkReason(StrEnum):
    INVALID_INVENTORY = "invalid_inventory"
    SOURCE_ERROR = "source_error"
    OUTSIDE_REPOSITORY = "outside_repository"
    MISSING_TARGET = "missing_target"
    MISSING_ANCHOR = "missing_anchor"
    TARGET_ERROR = "target_error"


@dataclass(frozen=True)
class LinkProblem:
    source: str
    line: int
    target: str
    reason: LinkReason

    def __str__(self) -> str:
        return f"{self.source}:{self.line} -> {self.target}: {self.reason}"


def _positioned(
    rule: Callable[[StateInline, bool], bool],
) -> Callable[[StateInline, bool], bool]:
    def positioned(state: StateInline, silent: bool) -> bool:
        start, count = state.pos, len(state.tokens) + bool(state.pending)
        matched = rule(state, silent)
        if matched and not silent:
            state.tokens[count].meta["line_offset"] = state.src.count("\n", 0, start)
        return matched

    return positioned


class _LocalMarkdown(MarkdownIt):
    def normalizeLink(self, url: str) -> str:
        # 诊断保留原 destination 的 Unicode/百分号拼写;检查时再解码路径。
        return url


def _parse(text: str) -> list[Token]:
    parser = _LocalMarkdown("commonmark")
    parser.inline.ruler.at("link", _positioned(link))
    parser.inline.ruler.at("image", _positioned(image))
    return parser.parse(text)


def _anchors(tokens: list[Token]) -> set[str]:
    anchors: set[str] = set()
    used: set[str] = set()
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            children = tokens[index + 1].children or []
            text = "".join(
                child.content
                for child in children
                if child.type in {"text", "code_inline", "image"}
            ).lower()
            slug = "".join(
                char
                for char in text
                if char in "-_ " or unicodedata.category(char)[0] not in "PSC"
            ).replace(" ", "-")
            candidate, suffix = slug, 0
            while candidate in used:
                suffix += 1
                candidate = f"{slug}-{suffix}"
            used.add(candidate)
            anchors.add(candidate)
        html_tokens = [token, *(token.children or [])]
        for html in html_tokens:
            if html.type in {"html_inline", "html_block"}:
                anchors.update(
                    match[2]
                    for match in re.finditer(
                        r"<a\s+id=([\"'])(.*?)\1\s*>", html.content
                    )
                )
    return anchors


def check_document_links(root: Path) -> list[LinkProblem]:
    """返回受控诊断;输入/解析失败也视为失败,不以空结果放行。"""
    root = root.resolve()
    problems: list[LinkProblem] = []
    inventory_path = "docs/verification/scope-material-inventory.json"
    try:
        inventory = json.loads((root / inventory_path).read_bytes())
        sources = inventory["classification_rules"]["live_documents"]["exact_paths"]
        if not isinstance(sources, list) or not sources:
            raise ValueError("empty live document selection")
        if not all(isinstance(source, str) and source for source in sources):
            raise ValueError("invalid live document selection")
    except (OSError, ValueError, KeyError, TypeError):
        return [
            LinkProblem(inventory_path, 1, inventory_path, LinkReason.INVALID_INVENTORY)
        ]
    parsed: dict[Path, list[Token]] = {}
    for source in sources:
        try:
            source_path = (root / source).resolve()
            if not source_path.is_relative_to(root):
                raise ValueError("source outside repository")
            tokens = _parse(source_path.read_text(encoding="utf-8"))
            parsed[source_path] = tokens
        except (OSError, ValueError):
            problems.append(LinkProblem(source, 1, source, LinkReason.SOURCE_ERROR))
            continue
        for token in tokens:
            if token.type != "inline":
                continue
            for child in token.children or []:
                target = child.attrGet("href" if child.type == "link_open" else "src")
                if child.type not in {"link_open", "image"} or not isinstance(
                    target, str
                ):
                    continue
                line = (token.map or [0])[0] + 1 + child.meta.get("line_offset", 0)
                try:
                    url = urlsplit(target)
                    if url.scheme or url.netloc:
                        continue
                    path = (
                        root / unquote(url.path).lstrip("/")
                        if url.path.startswith("/")
                        else source_path.parent / unquote(url.path)
                        if url.path
                        else source_path
                    ).resolve()
                    reason: LinkReason | None = None
                    if not path.is_relative_to(root):
                        reason = LinkReason.OUTSIDE_REPOSITORY
                    elif not path.exists():
                        reason = LinkReason.MISSING_TARGET
                    elif url.fragment and path.suffix.lower() == ".md":
                        if path not in parsed:
                            parsed[path] = _parse(path.read_text(encoding="utf-8"))
                        if unquote(url.fragment) not in _anchors(parsed[path]):
                            reason = LinkReason.MISSING_ANCHOR
                    if reason:
                        problems.append(LinkProblem(source, line, target, reason))
                except (OSError, ValueError):
                    problems.append(
                        LinkProblem(source, line, target, LinkReason.TARGET_ERROR)
                    )
    return problems
