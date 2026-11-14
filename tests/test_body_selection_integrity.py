"""D1: 选择不得把旧冻结样本伪绑到后续 metadata 修订。"""

import sqlite3
from pathlib import Path

import pytest

from paper_radar.body import BodyService
from paper_radar.body.models import BodyError
from paper_radar.body.repository import transaction
from paper_radar.body.selection import BodySelections
from paper_radar.papers import PaperFacts
from tests.body_selection_support import choose, second_body
from tests.experiment_layout_support import layout_fixture
from tests.exposure_support import backup
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def test_rehashed_selection_cannot_forge_frozen_sample_revision_or_pass_backup(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    assert choose(fixture).exit_code == 0
    (original,) = BodySelections(root.database, root.data_root).history()
    papers = PaperFacts(root.database, root.data_root)
    current = papers.show(fixture.extraction.prepared.paper_id)
    assert (
        papers.correct(
            dict(
                version_id=current.version_id,
                request_id="revision",
                actor="owner",
                reason="synthetic correction",
                fields={
                    "title": {"value": "Corrected title", "locator": "manual/title"}
                },
            )
        ).status
        == "retained"
    )
    forged = original.model_copy(update={"revision_no": original.revision_no + 1})
    with sqlite3.connect(root.database) as connection:
        connection.execute("DROP TRIGGER body_selections_no_update")
        connection.execute(
            "UPDATE body_selections SET revision_no=?, request_hash=?",
            (forged.revision_no, forged.request_digest()),
        )
    with pytest.raises(BodyError) as error:
        BodySelections(root.database, root.data_root).history()
    assert error.value.reason == "corrupt_reference"
    rejected = backup(root, tmp_path / "backups")
    assert rejected.exit_code == 2 and "registration_invalid" in rejected.output


def test_new_success_does_not_change_selected_body_in_shared_connection(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    paper = fixture.extraction.prepared.paper_id
    body = BodyService(root.database, root.data_root)
    old = fixture.identity
    assert choose(fixture).exit_code == 0
    selections = BodySelections(root.database, root.data_root).history()
    new = second_body(fixture)
    assert new != old
    assert body.current_body(paper).identity == old
    with transaction(root.database) as connection:
        assert body.current_body_in_connection(connection, paper).identity == old
    assert BodySelections(root.database, root.data_root).history() == selections
    fixture.identity = new
    assert choose(fixture, request="explicit-new").exit_code == 0
    assert body.current_body(paper).identity == new
