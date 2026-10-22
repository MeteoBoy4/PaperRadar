"""同材料完整重新解释的公共声明与版本门禁。"""

from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.test_paper_service import observation


@pytest.mark.parametrize("declaration", [None, "partial", "economical"])
def test_complete_interpretation_declaration_is_required(
    tmp_path: Path, declaration: str | None
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    request = observation()
    if declaration is None:
        request.pop("interpretation", None)
    else:
        request["interpretation"] = declaration
    result = PaperFacts(database, tmp_path / "data").submit(request)
    assert (result.status, result.reason) == ("rejected", "invalid_observation")


@pytest.mark.parametrize(
    "change", ["downgrade", "same_version_fields", "same_version_locator"]
)
def test_material_interpretation_cannot_downgrade_or_change_without_new_parser(
    tmp_path: Path, change: str
) -> None:
    from datetime import UTC, datetime

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    original = observation()
    first = service.submit(original)
    upgraded = observation(
        parser_version=2,
        observed_at=datetime(2026, 1, 2, tzinfo=UTC),
        fields={"title": {"value": "Version two", "locator": "title"}},
    )
    assert service.submit(upgraded).status == "retained"
    assert first.paper_id
    before = service.trace(first.paper_id)
    changed = {**upgraded, "observed_at": datetime(2026, 1, 3, tzinfo=UTC)}
    if change == "downgrade":
        changed = {**original, "observed_at": datetime(2026, 1, 3, tzinfo=UTC)}
    elif change == "same_version_fields":
        changed["fields"] = {
            "title": {"value": "Changed without version", "locator": "title"}
        }
    else:
        changed["fields"] = {
            "title": {"value": "Version two", "locator": "other-locator"}
        }
    result = service.submit(changed)
    assert (result.status, result.reason) == ("rejected", "invalid_observation")
    assert service.submit(original) == first
    assert service.trace(first.paper_id) == before


@pytest.mark.parametrize("replacement", ["missing_abstract", "new_abstract"])
def test_complete_reparse_preserves_old_revision_input_and_replaces_current_material(
    tmp_path: Path, replacement: str
) -> None:
    from datetime import UTC, datetime

    from paper_radar.config import StageName, compile_config
    from paper_radar.papers import AbstractValue
    from paper_radar.stage_inputs import ScreeningFacts, build_stage_input
    from tests.config_projection_support import full_inputs

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    original_fields: dict[str, object] = {
        "title": {"value": "Original title", "locator": "title"},
        "abstract": {
            "value": {
                "text": "Original abstract",
                "is_truncated": False,
                "rule": "fixture-v1",
            },
            "locator": "abstract",
        },
    }
    first = service.submit(observation(fields=original_fields))
    assert first.paper_id
    old_revision = service.trace(first.paper_id).revisions[0]
    old_input = build_stage_input(
        snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(
            title="Original title",
            abstract="Original abstract",
            abstract_truncated=False,
        ),
    )
    changed_fields = {"title": original_fields["title"]}
    if replacement == "new_abstract":
        changed_fields["abstract"] = {
            "value": {
                "text": "Reparsed abstract",
                "is_truncated": False,
                "rule": "fixture-v2",
            },
            "locator": "abstract",
        }
    result = service.submit(
        observation(
            parser_version=2,
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields=changed_fields,
        )
    )
    assert result.status == "retained"
    trace = service.trace(first.paper_id, verify_source_bytes=True)
    assert trace.current.revision_no == 2
    assert trace.revisions[0] == old_revision
    old_title, old_abstract = (
        trace.revisions[0].fields["title"].value,
        trace.revisions[0].fields["abstract"].value,
    )
    assert isinstance(old_title, str) and isinstance(old_abstract, AbstractValue)
    assert old_abstract.is_truncated is False
    rebuilt = build_stage_input(
        snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(
            title=old_title,
            abstract=old_abstract.text,
            abstract_truncated=old_abstract.is_truncated,
        ),
    )
    assert rebuilt.fingerprint == old_input.fingerprint
    if replacement == "missing_abstract":
        assert "abstract" not in trace.current.fields
    else:
        current_abstract = trace.current.fields["abstract"].value
        assert isinstance(current_abstract, AbstractValue)
        assert current_abstract.text == "Reparsed abstract"
        changed_input = build_stage_input(
            snapshot,
            StageName.BOUNDARY,
            ScreeningFacts(
                title=old_title,
                abstract=current_abstract.text,
                abstract_truncated=False,
            ),
        )
        assert changed_input.fingerprint != old_input.fingerprint


def test_different_material_missing_field_still_keeps_prior_candidate(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    first = service.submit(
        observation(
            fields={
                "title": {"value": "Title", "locator": "title"},
                "journal": {"value": "Journal", "locator": "journal"},
            }
        )
    )
    assert first.paper_id
    changed = service.submit(
        observation(
            payload=b"different material",
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"title": {"value": "New title", "locator": "title"}},
        )
    )
    assert changed.status == "retained"
    assert service.show(first.paper_id).fields["journal"].value == "Journal"


def test_empty_higher_parser_is_not_retained_and_does_not_clear_current_revision(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    original = observation()
    first = service.submit(original)
    assert first.paper_id
    old = service.show(first.paper_id)
    empty = observation(
        parser_version=2, observed_at=datetime(2026, 1, 2, tzinfo=UTC), fields={}
    )
    result = service.submit(empty)
    assert (result.status, result.reason) == ("not_retained", "not_retained")
    assert service.show(first.paper_id) == old
    assert len(service.trace(first.paper_id).revisions) == 1
    assert service.submit(empty) == result
    assert service.submit(original) == first
    downgrade = service.submit(
        observation(observed_at=datetime(2026, 1, 3, tzinfo=UTC))
    )
    assert downgrade.reason == "invalid_observation"
