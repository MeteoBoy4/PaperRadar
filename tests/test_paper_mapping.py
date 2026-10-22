"""正式事实映射:真实公共登记、配置编译和历史重建。"""

from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from tests.config_test_support import value_inputs
from tests.test_paper_service import observation


def screening_fields(
    title: str = "Title", abstract: str = "Abstract", truncated: bool | None = False
) -> dict[str, object]:
    return {
        "title": {"value": title, "locator": "title"},
        "abstract": {
            "value": {
                "text": abstract,
                "is_truncated": truncated,
                "rule": "fixture-v1",
            },
            "locator": "abstract",
        },
    }


def test_public_mapping_builds_two_inputs_with_complete_evidence(
    tmp_path: Path,
) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    assert saved.paper_id and saved.version_id
    result = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert result.format_version == 1
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.evidence is not None
    assert (
        result.evidence.paper_id,
        result.evidence.version_id,
        result.evidence.revision_no,
    ) == (saved.paper_id, saved.version_id, 1)
    assert result.evidence.fields["title"].candidate_id
    assert result.evidence.selection is not None
    for stage in (result.boundary, result.value):
        assert stage.reason is None and stage.value is not None
        assert stage.snapshot_id == snapshot.snapshot_id
        assert stage.evidence == result.evidence
        assert b'"title":"Title"' in stage.value.payload_bytes
        assert saved.paper_id.encode() not in stage.value.payload_bytes
        assert snapshot.snapshot_id.encode() not in stage.value.payload_bytes


def test_invalid_snapshot_reference_never_echoes_untrusted_text(tmp_path: Path) -> None:
    result = PaperFacts(tmp_path / "absent.sqlite").map_screening_inputs(
        paper_id="private-title-sentinel", snapshot_id="private-prompt-sentinel"
    )
    assert result.boundary.reason == "snapshot_not_found"
    assert result.value.value is None
    assert "private" not in repr(result)
    assert not list(tmp_path.iterdir())


def test_stage_readiness_is_independent(tmp_path: Path) -> None:
    settings, database = value_inputs(tmp_path)
    # Boundary 不就绪, value 仍具有完整材料。
    settings.write_text(settings.read_text().replace("  boundary: v1\n", ""))
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    result = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert result.boundary.reason == "config_not_ready"
    assert result.value.reason is None and result.value.value is not None


def test_boundary_ready_does_not_require_value_topics(tmp_path: Path) -> None:
    from tests.config_test_support import boundary_inputs

    settings, database = boundary_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    result = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert result.boundary.value is not None
    assert result.value.reason == "config_not_ready"


def test_complete_reinterpretation_preserves_old_mapping(tmp_path: Path) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    assert saved.paper_id and saved.version_id
    old = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    no_abstract = service.submit(
        observation(
            parser_version=2, fields={"title": {"value": "Title", "locator": "title"}}
        )
    )
    assert no_abstract.status == "retained"
    current = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert current.boundary.reason == current.value.reason == "missing_abstract"
    rebuilt = service.map_screening_inputs(
        version_id=saved.version_id, revision_no=1, snapshot_id=snapshot.snapshot_id
    )
    assert rebuilt.boundary.value == old.boundary.value
    assert rebuilt.value.value == old.value.value
    changed = service.submit(
        observation(parser_version=3, fields=screening_fields(abstract="New abstract"))
    )
    assert changed.status == "retained"
    current = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert old.value.value and current.value.value
    assert old.value.value.fingerprint != current.value.value.fingerprint
    # Explicit historical snapshot never consults selector files.
    settings.unlink()
    assert (
        service.map_screening_inputs(
            version_id=saved.version_id, revision_no=1, snapshot_id=snapshot.snapshot_id
        )
        == rebuilt
    )


def test_fact_changes_only_affect_semantic_inputs(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields(" T\r\nx ", " A\r\nb ")))
    assert saved.paper_id and saved.version_id
    original = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert original.value.value and original.boundary.value and original.evidence
    fingerprints = (
        original.boundary.value.fingerprint,
        original.value.value.fingerprint,
    )
    updates = [
        {
            **screening_fields("T\nx", "A\nb"),
            "volume": {"value": "42", "locator": "volume"},
        },
        screening_fields("T\nx", "A\nb"),
        screening_fields("T\nx", "A  b"),
        screening_fields("T\nx", "A  b", True),
    ]
    for index, fields in enumerate(updates):
        service.submit(
            observation(
                payload=f"new-{index}".encode(),
                observed_at=datetime(2026, 2, index + 1, tzinfo=UTC),
                fields=fields,
            )
        )
        mapped = service.map_screening_inputs(
            paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
        )
        assert mapped.boundary.value and mapped.value.value and mapped.evidence
        pair = (mapped.boundary.value.fingerprint, mapped.value.value.fingerprint)
        if index < 2:
            assert pair == fingerprints
            assert (
                mapped.evidence.fields["title"].acquisition_id
                != original.evidence.fields["title"].acquisition_id
            )
        else:
            assert all(
                before != after
                for before, after in zip(fingerprints, pair, strict=True)
            )
        fingerprints = pair
    corrected = service.correct(
        {
            "version_id": saved.version_id,
            "request_id": "manual-mapping",
            "actor": "researcher",
            "reason": "correct title",
            "fields": {"title": {"value": "T\nx", "locator": "manual.title"}},
        }
    )
    assert corrected.status == "retained"
    same = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert same.boundary.value and same.value.value and same.evidence
    assert (
        same.boundary.value.fingerprint,
        same.value.value.fingerprint,
    ) == fingerprints
    assert same.evidence.fields["title"].source_kind == "manual"
    different = service.submit(
        observation(doi="10.1234/other", fields=screening_fields("T\nx", "A  b", True))
    )
    other = service.map_screening_inputs(
        paper_id=different.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert other.boundary.value and other.value.value
    assert (
        other.boundary.value.fingerprint,
        other.value.value.fingerprint,
    ) == fingerprints


def test_source_arbitration_changes_evidence_without_changing_inputs(
    tmp_path: Path,
) -> None:
    from tests.feed_support import item

    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    feed = service.register_feed("https://feed.example/rss")
    first = service.submit(
        item(feed.feed_id, doi="10.1234/abc", fields=screening_fields())
    )
    assert first.paper_id and first.version_id
    fingerprints = []
    for source in ("feed", "registry", "publisher", "manual"):
        if source == "registry":
            result = service.submit(
                observation(
                    source_kind=source,
                    provider="crossref",
                    query_key="10.1234/abc",
                    target_paper_id=first.paper_id,
                    target_version_id=first.version_id,
                    fields=screening_fields(),
                )
            )
        elif source == "publisher":
            result = service.submit(observation(fields=screening_fields()))
        elif source == "manual":
            result = service.correct(
                {
                    "version_id": first.version_id,
                    "request_id": "same-facts",
                    "actor": "researcher",
                    "reason": "verified",
                    "fields": screening_fields(),
                }
            )
        else:
            result = first
        assert result.status == "retained"
        mapped = service.map_screening_inputs(
            paper_id=first.paper_id, snapshot_id=snapshot.snapshot_id
        )
        assert mapped.boundary.value and mapped.value.value and mapped.evidence
        assert mapped.evidence.fields["title"].source_kind == source
        fingerprints.append(
            (mapped.boundary.value.fingerprint, mapped.value.value.fingerprint)
        )
    assert len(set(fingerprints)) == 1
    changed = service.correct(
        {
            "version_id": first.version_id,
            "request_id": "new-facts",
            "actor": "researcher",
            "reason": "correct text",
            "fields": screening_fields(abstract="Corrected abstract"),
        }
    )
    assert changed.status == "retained"
    mapped = service.map_screening_inputs(
        paper_id=first.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert mapped.boundary.value and mapped.value.value
    assert mapped.boundary.value.fingerprint != fingerprints[0][0]
    assert mapped.value.value.fingerprint != fingerprints[0][1]


def test_read_only_config_changes_preserve_both_inputs_and_old_snapshot(
    tmp_path: Path,
) -> None:
    from tests.config_projection_support import full_inputs, new_yaml_version

    settings, database = full_inputs(tmp_path)
    original = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    before = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=original.snapshot_id
    )
    new_yaml_version(
        settings,
        "models",
        lambda value: value["reading"].update(model="new-read-model"),
    )
    newer = compile_config(settings, database)
    assert original.snapshot_id != newer.snapshot_id
    after = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=newer.snapshot_id
    )
    assert before.boundary.value == after.boundary.value
    assert before.value.value == after.value.value
    assert before.evidence != after.evidence
    assert (
        service.map_screening_inputs(
            paper_id=saved.paper_id, snapshot_id=original.snapshot_id
        )
        == before
    )


def test_complete_reinterpretation_falls_back_to_other_source_with_history(
    tmp_path: Path,
) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    assert saved.version_id and saved.paper_id
    lower = service.submit(
        observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1234/abc",
            target_paper_id=saved.paper_id,
            target_version_id=saved.version_id,
            fields=screening_fields(),
        )
    )
    assert lower.status == "retained"
    before = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert before.evidence and before.value.value
    updated = service.submit(
        observation(parser_version=2, fields={"title": screening_fields()["title"]})
    )
    assert updated.status == "retained"
    after = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert after.evidence and after.value.value
    assert after.evidence.revision_no > before.evidence.revision_no
    assert after.evidence.fields["abstract"].source_kind == "registry"
    assert before.evidence.fields["abstract"].source_kind == "publisher"
    assert after.value.value.fingerprint == before.value.value.fingerprint
    assert after.boundary.value == before.boundary.value
    assert (
        service.map_screening_inputs(
            version_id=saved.version_id,
            revision_no=before.evidence.revision_no,
            snapshot_id=snapshot.snapshot_id,
        )
        == before
    )


def test_topics_change_only_value_projection(tmp_path: Path) -> None:
    from tests.config_projection_support import full_inputs, new_yaml_version

    settings, database = full_inputs(tmp_path)
    original = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    before = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=original.snapshot_id
    )
    new_yaml_version(
        settings,
        "topics",
        lambda value: value["topics"][0].update(description="new research focus"),
    )
    newer = compile_config(settings, database)
    after = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=newer.snapshot_id
    )
    assert before.boundary.value == after.boundary.value
    assert before.value.value and after.value.value
    assert before.value.value.fingerprint != after.value.value.fingerprint
