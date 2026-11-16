"""D1: 合成活文档树的本地链接与锚点公共边界。"""

import json
from pathlib import Path

from scripts.live_document_links import check_document_links


def document_tree(root: Path, text: str) -> None:
    inventory = root / "docs/verification/scope-material-inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(
        json.dumps(
            {"classification_rules": {"live_documents": {"exact_paths": ["README.md"]}}}
        )
    )
    (root / "README.md").write_text(text)


def test_links_report_line_target_and_reason(tmp_path: Path) -> None:
    document_tree(tmp_path, "# 入口\n[`missing`](gone.md)\n[bad](#gone)\n")
    assert [str(problem) for problem in check_document_links(tmp_path)] == [
        "README.md:2 -> gone.md: missing_target",
        "README.md:3 -> #gone: missing_anchor",
    ]


def test_commonmark_links_and_github_anchors(tmp_path: Path) -> None:
    document_tree(
        tmp_path,
        "# 中文、Hello `Code`!\n"
        "# 中文、Hello `Code`!\n"
        "# 中文Hello Code-1\n"
        '<a id="manual"></a>\n'
        "[`label`](#中文hello-code) [duplicate](#中文hello-code-1)\n"
        "[collision](#中文hello-code-1-1) [explicit](#manual)\n"
        "[cross](target%20name.md#章节-v1)\n"
        "![image](asset.bin#not-an-anchor)\n"
        "[Full][ref] [ref][] [ref]\n\n"
        "[ref]: target%20name.md#章节-v1\n"
        "[external](https://invalid.example/nope) [mail](mailto:a@example.test)\n"
        "`[span](missing.md)`\n"
        "````md\n[code](missing.md)\n```\n[still code](missing.md)\n````\n\n"
        "    [indented](missing.md)\n",
    )
    (tmp_path / "target name.md").write_text("章节 V1\n=======\n")
    (tmp_path / "asset.bin").write_bytes(b"image")
    (tmp_path / "unknown.md").write_text("[not scanned](missing.md)")
    assert check_document_links(tmp_path) == []


def test_reference_image_and_multiline_diagnostics(tmp_path: Path) -> None:
    document_tree(
        tmp_path,
        "prefix text\n[one][ref]\n[ref][]\n[ref]\n![pic](missing.png)\n\n"
        "[ref]: gone.md\n",
    )
    assert [str(problem) for problem in check_document_links(tmp_path)] == [
        "README.md:2 -> gone.md: missing_target",
        "README.md:3 -> gone.md: missing_target",
        "README.md:4 -> gone.md: missing_target",
        "README.md:5 -> missing.png: missing_target",
    ]


def test_unicode_diagnostic_preserves_original_destination(tmp_path: Path) -> None:
    document_tree(tmp_path, "text [`标签`](不存在.md#坏锚点)\n")
    assert [str(problem) for problem in check_document_links(tmp_path)] == [
        "README.md:1 -> 不存在.md#坏锚点: missing_target"
    ]


def test_invalid_inventory_and_missing_source_fail_closed(tmp_path: Path) -> None:
    assert check_document_links(tmp_path)[0].reason == "invalid_inventory"
    document_tree(tmp_path, "# Valid\n")
    (tmp_path / "README.md").unlink()
    assert [str(problem) for problem in check_document_links(tmp_path)] == [
        "README.md:1 -> README.md: source_error"
    ]


def test_live_links_never_exempt_local_receipts_or_history_paths(
    tmp_path: Path,
) -> None:
    document_tree(tmp_path, "[receipt](verification-runs/local.json)\n")
    (tmp_path / "history.md").write_text("[old](missing.md)\n")
    assert [str(problem) for problem in check_document_links(tmp_path)] == [
        "README.md:1 -> verification-runs/local.json: missing_target"
    ]


def test_links_outside_root_and_unreadable_markdown_are_diagnosed(
    tmp_path: Path,
) -> None:
    document_tree(tmp_path, "[escape](../outside.md)\n[bad](invalid.md#anchor)\n")
    (tmp_path / "invalid.md").write_bytes(b"\xff")
    assert [problem.reason for problem in check_document_links(tmp_path)] == [
        "outside_repository",
        "target_error",
    ]
