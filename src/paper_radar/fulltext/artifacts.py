"""正文生产与持久成员回查公共服务;document 成员只供审计。"""

from typing import Literal

from pydantic import ValidationError

from paper_radar.fulltext.canonical import CanonicalDocument
from paper_radar.fulltext.models import (
    EvidenceMap,
    ExtractionManifest,
    ExtractionStatistics,
    FormulaCoverage,
    FulltextError,
    LoadedExtraction,
    PublishedExtraction,
)
from paper_radar.fulltext.normalization import (
    canonical_json,
    normalize_document,
    render_reading,
    sha256,
)
from paper_radar.fulltext.quality import (
    check_quality,
    reconstruct_context,
    source_is_replayable,
)
from paper_radar.reading.context import ExtractionIdentity, SourceSlice
from paper_radar.storage.artifact_contract import require_sha256
from paper_radar.storage.artifacts import ArtifactStore


class FulltextArtifacts:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def publish(
        self,
        document: CanonicalDocument,
        *,
        extraction_fingerprint: str,
        backend_config_hash: str,
        model_artifacts_hash: str,
        elapsed_seconds: float,
        peak_memory_bytes: int,
        document_json: bytes | None = None,
        warnings: tuple[str, ...] = (),
    ) -> PublishedExtraction:
        for value in (
            extraction_fingerprint,
            backend_config_hash,
            model_artifacts_hash,
        ):
            require_sha256(value)
        evidence_map = normalize_document(document)
        reading = render_reading(evidence_map)
        evidence_bytes = canonical_json(evidence_map.model_dump(mode="json"))
        audit_bytes = (
            document_json
            if document_json is not None
            else canonical_json(document.model_dump(mode="json"))
        )
        identity = ExtractionIdentity(
            extraction_fingerprint, sha256(reading), sha256(evidence_bytes)
        )
        manifest = ExtractionManifest(
            extraction_fingerprint=identity.extraction_fingerprint,
            reading_sha256=identity.reading_sha256,
            evidence_map_sha256=identity.evidence_map_sha256,
            document_sha256=sha256(audit_bytes),
            backend_config_hash=backend_config_hash,
            model_artifacts_hash=model_artifacts_hash,
            elapsed_seconds=elapsed_seconds,
            peak_memory_bytes=peak_memory_bytes,
            warnings=warnings,
        )
        members = {
            "document": audit_bytes,
            "reading": reading,
            "evidence_map": evidence_bytes,
            "manifest": canonical_json(manifest.model_dump(mode="json")),
        }
        quality = check_quality(evidence_map, identity, members)
        record = self.store.publish_artifact(
            "extraction", {role: [raw] for role, raw in members.items()}
        )
        return PublishedExtraction(
            record.artifact_id, identity, quality, statistics(evidence_map, members)
        )

    def load(
        self,
        artifact_id: str,
        *,
        expected_identity: ExtractionIdentity,
        expected_language: Literal["zh", "en"] = "zh",
    ) -> LoadedExtraction:
        members = self.store.read_artifact(artifact_id)
        if set(members) != {"document", "manifest", "reading", "evidence_map"}:
            raise FulltextError("invalid_members")
        try:
            manifest = ExtractionManifest.model_validate_json(members["manifest"])
            evidence_map = EvidenceMap.model_validate_json(members["evidence_map"])
        except (ValidationError, ValueError):
            raise FulltextError("invalid_members") from None
        identity = ExtractionIdentity(
            manifest.extraction_fingerprint,
            sha256(members["reading"]),
            sha256(members["evidence_map"]),
        )
        if (
            identity != expected_identity
            or identity.reading_sha256 != manifest.reading_sha256
            or identity.evidence_map_sha256 != manifest.evidence_map_sha256
            or sha256(members["document"]) != manifest.document_sha256
        ):
            raise FulltextError("identity_mismatch")
        if (
            canonical_json(evidence_map.model_dump(mode="json"))
            != members["evidence_map"]
        ):
            raise FulltextError("invalid_encoding")
        if canonical_json(manifest.model_dump(mode="json")) != members["manifest"]:
            raise FulltextError("invalid_encoding")
        quality = check_quality(evidence_map, identity, members)
        if not quality.passed:
            raise FulltextError("quality_failed", quality)
        context = reconstruct_context(
            evidence_map, identity, expected_language=expected_language
        )
        return LoadedExtraction(
            artifact_id,
            identity,
            context,
            members["reading"],
            quality,
            statistics(evidence_map, members),
        )

    def lookup(
        self, artifact_id: str, identity: ExtractionIdentity, evidence_id: str
    ) -> tuple[SourceSlice, ...]:
        result = self.load(artifact_id, expected_identity=identity).lookup(evidence_id)
        if not result:
            raise FulltextError("unknown_evidence")
        return result


def statistics(
    evidence_map: EvidenceMap, members: dict[str, bytes]
) -> ExtractionStatistics:
    sources = {source.source_id: source for source in evidence_map.source_blocks}
    coverage = []
    for mode in ("display", "inline", "unknown"):
        blocks = [
            block
            for block in evidence_map.reading_blocks
            if block.label == "formula" and block.formula_mode == mode
        ]
        parents = 0
        for block in blocks:
            source = sources.get(block.source_id or "")
            if (
                block.role == "source"
                and source
                and source_is_replayable(
                    source,
                    evidence_map,
                    ExtractionIdentity("statistics", "statistics", "statistics"),
                )
            ):
                parents += 1
        coverage.append(
            FormulaCoverage(mode, len(blocks), parents, len(blocks) - parents)
        )
    return ExtractionStatistics(
        tuple(coverage),
        tuple(sorted((role, len(raw)) for role, raw in members.items())),
    )
