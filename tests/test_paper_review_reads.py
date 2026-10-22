"""审查补齐的读取、参数和当前版本说明公共回归。"""

import sqlite3
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.errors import StorageError
from tests.config_test_support import run_cli


@pytest.mark.parametrize("operation", ["trace", "show", "revision", "validate_all"])
@pytest.mark.parametrize(
    "state,reason",
    [
        ("missing", "database_missing"),
        ("uninitialized", "database_uninitialized"),
        ("old", "upgrade_required"),
    ],
)
def test_read_preserves_storage_environment_reason(
    tmp_path: Path, state: str, reason: str, operation: str
) -> None:
    database = tmp_path / "facts.sqlite"
    if state != "missing":
        with sqlite3.connect(database) as connection:
            if state == "old":
                connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
                connection.execute(
                    "INSERT INTO alembic_version VALUES ('a601_paper_facts')"
                )
    service = PaperFacts(database)
    with pytest.raises(StorageError) as caught:
        if operation == "revision":
            service.revision("id", 1)
        elif operation == "validate_all":
            service.validate_all()
        else:
            getattr(service, operation)("id")
    assert caught.value.reason == reason
    assert "db upgrade" in str(caught.value)
    assert database.exists() == (state != "missing")


def test_missing_database_cli_gives_storage_guidance(tmp_path: Path) -> None:
    database = tmp_path / "absent.sqlite"
    result = run_cli(tmp_path, "paper", "show", "id", "--database", str(database))
    assert result.returncode == 1
    assert "[database_missing]" in result.stderr
    assert "db upgrade" in result.stderr
    assert not database.exists()


def test_verify_without_data_root_is_parameter_error_before_database_io(
    tmp_path: Path,
) -> None:
    database = tmp_path / "absent.sqlite"
    result = run_cli(
        tmp_path,
        "paper",
        "trace",
        "PRIVATE-ID",
        "--database",
        str(database),
        "--verify-source-bytes",
    )
    assert result.returncode == 2
    assert "--verify-source-bytes 需要 --data-root" in result.stderr
    assert "PRIVATE" not in result.stdout + result.stderr
    assert not database.exists()


def test_service_verify_without_data_root_reports_invalid_parameter(
    tmp_path: Path,
) -> None:
    from paper_radar.papers.errors import PaperError
    from paper_radar.storage.database import upgrade_database
    from tests.test_paper_service import observation

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    result = PaperFacts(database, tmp_path / "data").submit(observation())
    assert result.paper_id
    with pytest.raises(PaperError) as caught:
        PaperFacts(database).trace(result.paper_id, verify_source_bytes=True)
    assert caught.value.reason == "invalid_observation"
    assert caught.value.path == "data_root"


@pytest.mark.parametrize("upgrade", [False, True])
def test_show_text_includes_current_version_selection(
    tmp_path: Path, upgrade: bool
) -> None:
    from paper_radar.storage.database import upgrade_database
    from tests.test_paper_service import observation
    from tests.test_version_relations import relation

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    pre = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            relations=relation(),
        )
    )
    assert pre.paper_id
    if upgrade:
        service.submit(observation(doi="10.1/journal"))
    selection = service.show(pre.paper_id).selection
    assert selection
    assert selection.reason == ("journal_upgrade" if upgrade else "initial")
    result = run_cli(
        tmp_path, "paper", "show", pre.paper_id, "--database", str(database)
    )
    assert result.returncode == 0, result.stderr
    assert "当前版本选择：" in result.stdout
    for expected in (selection.reason, selection.selected_at, selection.selection_id):
        assert expected in result.stdout


def test_existing_cross_paper_relation_hints_on_plain_metadata_and_replays_receipt(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.database import upgrade_database
    from tests.test_paper_service import observation
    from tests.test_version_relations import relation

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    service.submit(observation(doi="10.1/journal"))
    service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            relations=relation(),
            payload=b"relation",
        )
    )
    metadata = observation(
        doi="10.1/pre",
        version_kind="preprint",
        payload=b"volume",
        fields={"volume": {"value": "42", "locator": "volume"}},
    )
    result = service.submit(metadata)
    assert (result.status, result.reason) == ("retained", "requires_merge")
    assert pre.paper_id
    trace = service.trace(pre.paper_id)
    assert len(trace.relations) == 1
    assert len(trace.relations[0].assertions) == 1
    assert service.submit(metadata) == result
    assert service.trace(pre.paper_id) == trace
    service.validate_all()
