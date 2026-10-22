"""映射受控失败与真实引用链破坏。"""

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"title": {"value": "Title", "locator": "title"}}, "missing_abstract"),
        ({"abstract": screening_fields()["abstract"]}, "missing_title"),
        (screening_fields(truncated=None), "truncation_unknown"),
    ],
)
def test_missing_facts_have_accurate_reasons(
    tmp_path: Path, fields: dict[str, object], reason: str
) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=fields))
    assert saved.status == "retained"
    result = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert result.boundary.reason == result.value.reason == reason
    assert result.boundary.value is result.value.value is None
    assert result.evidence is not None


@pytest.mark.parametrize(
    ("selector", "reason"),
    [
        ({}, "invalid_observation"),
        ({"paper_id": str(uuid4())}, "paper_not_found"),
        ({"version_id": str(uuid4()), "revision_no": 1}, "version_not_found"),
        (
            {"paper_id": "current", "version_id": "version", "revision_no": 1},
            "invalid_observation",
        ),
        ({"paper_id": "current", "revision_no": 1}, "invalid_observation"),
        ({"version_id": "version"}, "invalid_observation"),
        ({"version_id": "version", "revision_no": True}, "invalid_observation"),
        ({"version_id": "version", "revision_no": 0}, "invalid_observation"),
        ({"version_id": "version", "revision_no": 999}, "revision_not_found"),
    ],
)
def test_fact_selectors_are_exclusive_and_precise(
    tmp_path: Path, selector: dict[str, object], reason: str
) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    replaced = {
        key: saved.paper_id
        if value == "current"
        else saved.version_id
        if value == "version"
        else value
        for key, value in selector.items()
    }
    result = service.map_screening_inputs(snapshot_id=snapshot.snapshot_id, **replaced)  # type: ignore[arg-type]
    assert result.boundary.reason == result.value.reason == reason
    assert result.evidence is None


@pytest.mark.parametrize("damage", ["candidate", "owner", "kind", "snapshot"])
def test_registered_but_corrupt_references_are_not_missing(
    tmp_path: Path, damage: str
) -> None:
    settings, database = value_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    service = PaperFacts(database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    with closing(sqlite3.connect(database)) as owner:
        if damage == "candidate":
            owner.execute(
                "UPDATE paper_revision_fields SET candidate_id=?", (str(uuid4()),)
            )
        elif damage == "owner":
            owner.execute("UPDATE paper_versions SET paper_id=?", (str(uuid4()),))
        elif damage == "kind":
            owner.execute("UPDATE artifacts SET kind='pdf'")
        else:
            owner.execute("UPDATE runtime_config_snapshots SET payload_json='{}'")
        owner.commit()
    result = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert result.boundary.reason == result.value.reason == "corrupt_reference"
    assert result.boundary.value is result.value.value is None


def test_snapshot_must_be_registered_in_same_database(tmp_path: Path) -> None:
    settings, database = value_inputs(tmp_path / "first")
    snapshot = compile_config(settings, database)
    _, other_database = value_inputs(tmp_path / "second")
    service = PaperFacts(other_database, tmp_path / "data")
    saved = service.submit(observation(fields=screening_fields()))
    result = service.map_screening_inputs(
        paper_id=saved.paper_id, snapshot_id=snapshot.snapshot_id
    )
    assert result.boundary.reason == result.value.reason == "snapshot_not_found"
    assert result.evidence is not None
