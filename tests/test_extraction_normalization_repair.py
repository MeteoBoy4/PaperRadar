"""D1:合成 SDK export 到规范正文/证据消费;不加载 SDK 或解析 PDF。"""

from pathlib import Path
from typing import Any

import pytest

from paper_radar.docling_execution.mapping import map_document
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.canonical import CanonicalDocument
from paper_radar.fulltext.normalization import normalize_document, render_reading
from paper_radar.reading.acceptance_v2 import validate_read_output_v2
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from tests.read_support import candidate


class Export:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    def export_to_dict(self) -> dict[str, Any]:
        return self.raw


def item(
    index: int,
    text: str,
    *,
    label: str = "text",
    page: int = 1,
    top: float = 150.0,
    level: int | None = None,
    bottom_left: bool = False,
) -> dict[str, Any]:
    return {
        "self_ref": f"#/texts/{index}",
        "parent": {"$ref": "#/body"},
        "label": label,
        "orig": text,
        "text": text,
        "children": [],
        **({"level": level} if level is not None else {}),
        "prov": [
            {
                "page_no": page,
                "bbox": {
                    "l": 20.0,
                    "t": 800.0 - top if bottom_left else top,
                    "r": 500.0,
                    "b": 780.0 - top if bottom_left else top + 20.0,
                    "coord_origin": "BOTTOMLEFT" if bottom_left else "TOPLEFT",
                },
                "charspan": [0, len(text)],
            }
        ],
    }


def mapped(
    items: list[dict[str, Any]], *, pages: int = 2
) -> tuple[CanonicalDocument, bytes]:
    return map_document(
        Export(
            {
                "pages": {
                    str(page): {
                        "page_no": page,
                        "size": {
                            "width": 600.0,
                            "height": 800.0,
                        },
                    }
                    for page in range(1, pages + 1)
                },
                "body": {
                    "self_ref": "#/body",
                    "children": [{"$ref": node["self_ref"]} for node in items],
                },
                "texts": items,
            }
        ),
        page_count=pages,
        processed_pages=tuple(range(1, pages + 1)),
        has_text_layer=True,
        formula_enabled=False,
    )


@pytest.mark.parametrize("bottom_left", [False, True])
def test_repeated_marginal_banner_with_mixed_labels_is_not_a_section(
    bottom_left: bool,
) -> None:
    text = "Synthetic recurring banner"
    canonical, _ = mapped(
        [
            item(0, text, label="page_header", top=5.0),
            item(
                1,
                text,
                label="section_header",
                level=1,
                page=2,
                top=5.0,
                bottom_left=bottom_left,
            ),
            item(2, "Main scientific prose."),
        ]
    )
    normalized = normalize_document(canonical, version="v2")
    assert [e.evidence_id for e in normalized.evidence] == ["e000004"]
    assert all(block.heading_level is None for block in normalized.reading_blocks)
    assert text.encode() not in render_reading(normalized)
    assert [s.orig for s in normalized.source_blocks][:2] == [text, text]
    # 旧解释器继续重现原语义,不能在同指纹内偷偷修历史。
    assert text.encode() in render_reading(normalize_document(canonical))


@pytest.mark.parametrize(
    ("top", "second_top", "second_page"),
    [
        (150.0, 150.0, 2),
        (5.0, 25.0, 2),
        (5.0, 5.0, 1),
    ],
)
def test_repeated_content_without_matching_cross_page_margin_is_preserved(
    top: float,
    second_top: float,
    second_page: int,
) -> None:
    canonical, _ = mapped(
        [
            item(
                0,
                "Repeated scientific heading",
                label="section_header",
                top=top,
                level=1,
            ),
            item(
                1,
                "Repeated scientific heading",
                label="section_header",
                top=second_top,
                level=2,
                page=second_page,
            ),
        ]
    )
    normalized = normalize_document(canonical, version="v2")
    assert len(normalized.evidence) == 2
    assert all(b.excluded is None for b in normalized.reading_blocks)
    assert [b.heading_level for b in normalized.reading_blocks if b.heading_level] == [
        1,
        2,
    ]


@pytest.mark.parametrize("label", ["text", "caption"])
def test_inline_symbol_duplication_is_restricted_without_rewriting_source(
    tmp_path: Path,
    label: str,
) -> None:
    text = "The coefficients XZ XZ and qr qr control the response."
    canonical, raw = mapped([item(0, text, label=label)])
    database = tmp_path / "db"
    upgrade_database(database)
    service = FulltextArtifacts(ArtifactStore(database, tmp_path / "data"))
    saved = service.publish(
        canonical,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=0.0,
        peak_memory_bytes=0,
        document_json=raw,
        normalization_version="v2",
    )
    loaded = service.load(saved.artifact_id, expected_identity=saved.identity)
    (source,) = loaded.context.replay()
    assert source.unreliable
    assert source.text == text and source.kind == "text"
    assert (
        source.provenance.page_no,
        source.provenance.bbox,
        source.provenance.start,
        source.provenance.end,
    ) == (1, (20.0, 150.0, 500.0, 170.0), 0, len(text))
    assert text.encode() in loaded.reading
    reference = {
        "statement": "该处说明了系数。",
        "evidence": [{"evidence_id": source.evidence_id}],
    }
    result = validate_read_output_v2(
        candidate(research_value_reason=reference, reuse_feasibility_reason=reference),
        loaded.context,
        attempt_ordinal=1,
    )
    assert [(d.location, d.reason.value) for d in result.diagnostics] == [
        ("$.research_value_reason.statement", "restricted_source_reference"),
        ("$.reuse_feasibility_reason.statement", "restricted_source_reference"),
    ]
    assert all(w.origin == "program" for w in result.warnings)
    assert not normalize_document(canonical).source_blocks[0].unreliable


@pytest.mark.parametrize(
    "text",
    [
        "The model XZ and XZ agree; qr is a coefficient.",
        "This is a very very useful method.",
        "They had had a discussion; go go is a natural repetition.",
        "Normal scientific symbols α β γ and cp remain available.",
        "A larger token token remains ordinary prose.",
        "Alphabetic words like shells shells stay unchanged.",
    ],
)
def test_normal_scientific_text_and_repeated_words_remain_reliable(text: str) -> None:
    canonical, _ = mapped([item(0, text)])
    normalized = normalize_document(canonical, version="v2")
    assert normalized.source_blocks[0].orig == text
    assert not normalized.source_blocks[0].unreliable
    assert len(normalized.evidence) == 1


@pytest.mark.parametrize("token", ["AB", "xz", "zt", "Q", "IL", "fc", "TL", "cp"])
def test_adjacent_short_symbol_candidates_are_flagged_without_deduplication(
    token: str,
) -> None:
    text = f"The response depends on {token} {token}."
    canonical, _ = mapped([item(0, text)])
    normalized = normalize_document(canonical, version="v2")
    source = normalized.source_blocks[0]
    assert source.orig == text and source.text == text
    assert source.unreliable
    assert len(normalized.evidence) == 1


def test_terminal_independent_backmatter_headings_share_top_level() -> None:
    headings = [
        ("1 Introduction", 1),
        ("1.1 Observations", 2),
        ("2 Methods", 1),
        ("2.1 Instrumentation", 2),
        ("Data Availability", 1),
        ("Competing Interests", 2),
        ("Acknowledgements", 3),
        ("Bibliography", 1),
    ]
    canonical, _ = mapped(
        [
            item(
                index, text, label="section_header", level=level, top=100.0 + index * 25
            )
            for index, (text, level) in enumerate(headings)
        ]
    )
    normalized = normalize_document(canonical, version="v2")
    assert [b.heading_level for b in normalized.reading_blocks if b.heading_level] == [
        1,
        2,
        1,
        2,
        1,
        1,
        1,
        1,
    ]
    assert [
        b.heading_level
        for b in normalize_document(canonical).reading_blocks
        if b.heading_level
    ] == [1, 2, 1, 2, 1, 2, 3, 1]


@pytest.mark.parametrize(
    ("headings", "levels"),
    [
        (
            ["Methods", "Data Availability", "Competing Interests", "Results"],
            [1, 1, 2, 1],
        ),
        (
            [
                "Methods",
                "2.1 Data Availability",
                "2.1.1 Competing Interests",
                "References",
            ],
            [1, 2, 3, 1],
        ),
        (
            ["Methods", "Data Availability", "Unclassified Supplement", "References"],
            [1, 1, 2, 3],
        ),
        (
            ["Methods", "Instrumentation", "Data Availability", "Competing Interests"],
            [1, 2, 2, 3],
        ),
    ],
)
def test_backmatter_requires_terminal_classifiable_unumbered_group_with_anchor(
    headings: list[str],
    levels: list[int],
) -> None:
    canonical, _ = mapped(
        [
            item(index, text, label="section_header", level=level)
            for index, (text, level) in enumerate(zip(headings, levels, strict=True))
        ]
    )
    normalized = normalize_document(canonical, version="v2")
    assert [
        b.heading_level for b in normalized.reading_blocks if b.heading_level
    ] == levels


def test_explicit_parent_heading_relationship_is_not_flattened() -> None:
    canonical, _ = mapped(
        [
            item(0, "Methods", label="section_header", level=1),
            item(1, "Data Availability", label="section_header", level=1),
            item(2, "Competing Interests", label="section_header", level=2),
        ]
    )
    blocks = list(canonical.blocks)
    blocks[-1] = blocks[-1].model_copy(update={"parent_ref": blocks[-2].ref})
    normalized = normalize_document(
        canonical.model_copy(update={"blocks": tuple(blocks)}), version="v2"
    )
    assert [b.heading_level for b in normalized.reading_blocks if b.heading_level] == [
        1,
        1,
        2,
    ]


def test_owner_observed_backmatter_roles_are_a_supported_general_group() -> None:
    canonical, _ = mapped(
        [
            item(index, text, label="section_header", level=level)
            for index, (text, level) in enumerate(
                [
                    ("Methods", 1),
                    ("Availability Statement", 1),
                    ("Conflict of Interest", 2),
                    ("Acknowledgments", 3),
                    ("References", 1),
                ]
            )
        ]
    )
    normalized = normalize_document(canonical, version="v2")
    assert [b.heading_level for b in normalized.reading_blocks if b.heading_level] == [
        1,
        1,
        1,
        1,
        1,
    ]


def test_long_paragraph_with_only_one_unformatted_duplicate_is_restricted() -> None:
    text = (
        "This synthetic paragraph describes a model and its independent observations. "
        "We compare several windows and preserve the original "
        "order of the measurements. "
        "The uncertainty analysis considers the calibration, "
        "sampling and instrument response. "
        "One parameter qr qr appears once in this otherwise "
        "ordinary scientific paragraph. "
        "The remaining discussion provides qualitative "
        "context without further repetitions."
    )
    canonical, _ = mapped([item(0, text)])
    source = normalize_document(canonical, version="v2").source_blocks[0]
    assert source.unreliable and source.orig == text


def test_v1_and_v2_artifacts_restore_without_sdk_or_source_root(tmp_path: Path) -> None:
    import json
    import os
    import subprocess
    import sys
    from dataclasses import asdict

    from paper_radar.backup import create_backup, restore_backup

    original = tmp_path / "original"
    original.mkdir()
    database = original / "db"
    upgrade_database(database)
    store = ArtifactStore(database, original / "data")
    service = FulltextArtifacts(store)
    canonical, raw = mapped([item(0, "The coefficient qr qr requires review.")])
    references: list[dict[str, Any]] = []
    for version in ("v1", "v2"):
        published = service.publish(
            canonical,
            extraction_fingerprint=("a" if version == "v1" else "b") * 64,
            backend_config_hash="c" * 64,
            model_artifacts_hash="d" * 64,
            elapsed_seconds=0.0,
            peak_memory_bytes=0,
            document_json=raw,
            normalization_version="v1" if version == "v1" else "v2",
        )
        references.append(
            {
                "version": version,
                "artifact": published.artifact_id,
                "identity": asdict(published.identity),
            }
        )
    before = {
        entry["artifact"]: store.read_artifact(entry["artifact"])
        for entry in references
    }
    backup = create_backup(database, original / "data", tmp_path / "backups")
    original.rename(tmp_path / "unavailable-original")
    restored = restore_backup(backup.batch_dir, tmp_path / "restored").target_dir
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys, json
from pathlib import Path
def guard(event, args):
    denied = {'docling', 'docling_core', 'torch', 'transformers',
              'docling_parse', 'pypdfium2'}
    if event == 'import' and args[0].split('.')[0] in denied:
        raise AssertionError('SDK import forbidden')
    if event == 'socket.__new__':
        raise AssertionError('Network forbidden')
sys.addaudithook(guard)
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.reading.context import ExtractionIdentity
root = Path(sys.argv[1])
service = FulltextArtifacts(ArtifactStore(root/'database.sqlite3', root))
for reference in json.loads(sys.argv[2]):
    identity = ExtractionIdentity(**reference['identity'])
    loaded = service.load(reference['artifact'], expected_identity=identity)
    (source,) = loaded.context.replay()
    assert source.text == 'The coefficient qr qr requires review.'
    assert source.unreliable is (reference['version'] == 'v2')
    assert source.provenance.page_no == 1
    assert source.provenance.bbox == (20.,150.,500.,170.)
    assert source.provenance.start == 0 and source.provenance.end == 38
print('v1 and v2 replayed without SDK')
""",
            str(restored),
            json.dumps(references),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "v1 and v2 replayed without SDK"
    recovered = ArtifactStore(restored / "database.sqlite3", restored)
    assert {
        artifact: recovered.read_artifact(artifact) for artifact in before
    } == before


@pytest.mark.parametrize(
    "text",
    [
        "I I speak with hesitation.",
        "NO NO is an ordinary repeated word.",
        "BY BY is repeated in an uppercase label.",
    ],
)
def test_common_short_words_are_not_restricted_by_capitalization(text: str) -> None:
    canonical, _ = mapped([item(0, text)])
    assert not normalize_document(canonical, version="v2").source_blocks[0].unreliable


def test_identical_text_at_opposite_page_margins_is_not_a_repeated_banner() -> None:
    canonical, _ = mapped(
        [
            item(0, "Repeated text in different positions", top=5.0),
            item(1, "Repeated text in different positions", page=2, top=775.0),
        ]
    )
    normalized = normalize_document(canonical, version="v2")
    assert len(normalized.evidence) == 2
    assert all(block.excluded is None for block in normalized.reading_blocks)
