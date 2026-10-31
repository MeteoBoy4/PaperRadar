"""仅检查已分类活文档指向冻结证据/history/台账的相对 Markdown 链接。"""

import json
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]


def evidence_links_exist(root: Path) -> None:
    inventory = json.loads(
        (root / "docs/verification/scope-material-inventory.json").read_bytes()
    )
    evidence = {
        row["path"]
        for row in [*inventory["bindings"], *inventory["unbound_materials"]]
        if row["category"] in {"evidence", "coverage", "historical_evidence_disclosure"}
    }
    broken = []
    for source in inventory["classification_rules"]["live_documents"]["exact_paths"]:
        text: str = (root / source).read_text()
        # 去掉 fenced code, 保留换行使断链位置仍对应原文。
        fences = re.compile(r"(?ms)^ *(`{3,}|~{3,})[^\n]*\n.*?^ *\1[^\n]*$")
        text = fences.sub(lambda m: "\n" * m[0].count("\n"), text)
        text = re.sub(r"`[^`\n]*`", lambda m: " " * len(m[0]), text)
        references = dict(re.findall(r"(?m)^ {0,3}\[([^\]]+)\]:\s*<?([^\s>]+)>?", text))
        links = [
            (m.start(), m[1])
            for m in re.finditer(
                r"!?\[[^\]\n]*\]\(\s*<?([^\s)>]+)>?(?:\s+[^)]*)?\)", text
            )
        ]
        for match in re.finditer(r"\[([^\]\n]+)\]\[([^\]\n]*)\]", text):
            label = match[2] or match[1]
            if label in references:
                links.append((match.start(), references[label]))
        for match in re.finditer(r"(?<!\])\[([^\]\n]+)\](?![(:\[])", text):
            if match[1] in references:
                links.append((match.start(), references[match[1]]))
        for offset, target in links:
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                continue
            relative = posixpath.normpath(
                posixpath.join(posixpath.dirname(source), unquote(url.path))
            )
            if relative not in evidence and not relative.startswith(
                ("docs/verification/", "verification-runs/", "intent/review/")
            ):
                continue
            if not (root / relative).is_file():
                broken.append(
                    f"{source}:{text.count(chr(10), 0, offset) + 1} -> {target}"
                )
    assert not broken, "冻结依据相对链接不存在：\n" + "\n".join(broken)


def test_live_document_evidence_links_exist() -> None:
    evidence_links_exist(ROOT)


def test_broken_relative_evidence_link_identifies_source_and_target(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "docs/verification"
    directory.mkdir(parents=True)
    (directory / "scope-material-inventory.json").write_text(
        json.dumps(
            {
                "bindings": [],
                "unbound_materials": [],
                "classification_rules": {
                    "live_documents": {"exact_paths": ["README.md"]}
                },
            }
        )
    )
    (tmp_path / "README.md").write_text(
        "[missing](docs/verification/missing-history.md#unchecked)\n"
    )
    with pytest.raises(
        AssertionError,
        match=r"README.md:1 -> docs/verification/missing-history.md#unchecked",
    ):
        evidence_links_exist(tmp_path)


def test_shortcut_reference_evidence_link_is_checked(tmp_path: Path) -> None:
    directory = tmp_path / "docs/verification"
    directory.mkdir(parents=True)
    (directory / "scope-material-inventory.json").write_text(
        json.dumps(
            {
                "bindings": [],
                "unbound_materials": [],
                "classification_rules": {
                    "live_documents": {"exact_paths": ["README.md"]}
                },
            }
        )
    )
    (tmp_path / "README.md").write_text(
        "[history]\n\n[history]: docs/verification/missing.md\n"
    )
    with pytest.raises(
        AssertionError, match=r"README.md:1 -> docs/verification/missing.md"
    ):
        evidence_links_exist(tmp_path)


def test_link_scope_excludes_external_anchors_other_targets_and_unknown_sources(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "docs/verification"
    directory.mkdir(parents=True)
    (directory / "history with spaces.md").write_text("frozen proof")
    (directory / "scope-material-inventory.json").write_text(
        json.dumps(
            {
                "bindings": [],
                "unbound_materials": [],
                "classification_rules": {
                    "live_documents": {"exact_paths": ["README.md"]}
                },
            }
        )
    )
    (tmp_path / "README.md").write_text(
        "[existing](docs/verification/history%20with%20spaces.md#unchecked-anchor)\n"
        "[reference][history]\n\n"
        "[history]: docs/verification/history%20with%20spaces.md\n"
        "[outside](https://invalid.example/docs/verification/missing.md)\n"
        "[issue](https://github.com/example/repo/issues/1#issuecomment-1)\n"
        "[anchor](#missing) [unrelated](docs/contracts/missing.md)\n"
        "`[code](docs/verification/code-missing.md)`\n"
        "```md\n[example](docs/verification/example-missing.md)\n```\n"
    )
    (tmp_path / "unknown.md").write_text("[ignored](docs/verification/missing.md)")
    evidence_links_exist(tmp_path)
