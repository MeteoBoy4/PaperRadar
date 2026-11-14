"""B-E12 仅合成 PDF 与持久正文的公开 CLI 准备。"""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from paper_radar.body import BodyService
from paper_radar.fulltext.canonical import CanonicalDocument
from paper_radar.reading.context import ExtractionIdentity
from tests.experiment_extract_support import ExtractFixture, executor, extract_fixture
from tests.test_experiment_candidates_cli import FeedFixture, invoke


def synthetic_pdf(rotation: int = 0) -> bytes:
    content = (
        b"1 0 0 rg 40 780 480 30 re f\n"
        b"0 0 0 rg BT /F1 12 Tf 50 795 Td (Results) Tj ET\n"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 650 850] "
            f"/CropBox [20 30 620 830] /Rotate {rotation} "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ).encode(),
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    raw = b"%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(raw)
    raw += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    raw += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    raw += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{start}\n%%EOF\n"
    ).encode()
    return raw + b"% synthetic padding\n" * 40


@dataclass
class LayoutFixture:
    extraction: ExtractFixture
    identity: ExtractionIdentity

    def args(self, command: str) -> list[str]:
        return [
            command,
            self.extraction.prepared.paper_id,
            "--root",
            str(self.extraction.root.root),
            "--fingerprint",
            self.identity.extraction_fingerprint,
            "--reading-sha256",
            self.identity.reading_sha256,
            "--evidence-map-sha256",
            self.identity.evidence_map_sha256,
        ]

    def review(
        self,
        *,
        passed: bool = True,
        request: str = "review",
        note: str = "",
        command: str = "layout-review",
    ) -> dict[str, object]:
        checks = [
            "--body-boundary",
            "true",
            "--reading-order",
            "true",
            "--sections",
            "true",
            "--headers-footers",
            "true",
            "--provenance",
            "true",
            "--restricted-content",
            str(passed).lower(),
        ]
        result = invoke(
            *self.args(command),
            "--reviewer",
            "owner",
            "--recorder",
            "agent",
            "--request-id",
            request,
            "--note",
            note,
            *checks,
        )
        assert result.exit_code == 0, result.output
        payload: dict[str, object] = json.loads(result.stdout)
        return payload


def layout_fixture(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    rotation: int = 0,
    origin: str = "top_left",
    canonical: CanonicalDocument | None = None,
) -> LayoutFixture:
    from paper_radar.docling_execution.models import WorkerResponse
    from tests.test_experiment_pdf_cli import attach
    from tests.test_fulltext_artifacts import document

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    attached = attach(
        prepared.prepared,
        tmp_path,
        request="renderable-pdf",
        raw=synthetic_pdf(rotation),
    )
    assert attached.exit_code == 0, attached.output
    canonical = canonical or document()
    if origin == "bottom_left":
        blocks = tuple(
            block.model_copy(
                update={
                    "provenance": tuple(
                        p.model_copy(
                            update={
                                "origin": "bottom_left",
                                "bbox": (
                                    p.bbox[0],
                                    800.0 - p.bbox[3],
                                    p.bbox[2],
                                    800.0 - p.bbox[1],
                                ),
                            }
                        )
                        for p in block.provenance
                    )
                }
            )
            for block in canonical.blocks
        )
        canonical = canonical.model_copy(update={"blocks": blocks})
    executor(
        monkeypatch,
        WorkerResponse(document=canonical, document_json="{}", peak_memory_bytes=4096),
    )
    extracted = prepared.extract()
    assert extracted.exit_code == 0, extracted.output
    body = BodyService(prepared.root.database, prepared.root.data_root)
    identity = body.current_body(prepared.prepared.paper_id).identity
    assert identity is not None
    return LayoutFixture(prepared, identity)
