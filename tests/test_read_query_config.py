"""D1 只读Read投影比较与提交顺序。"""

from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from paper_radar.config import compile_config
from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadTasks
from tests.config_projection_support import new_yaml_version
from tests.pi_rpc_source_support import NOW
from tests.read_queries_support import changed_profile, successful
from tests.read_tasks_support import ready, valid_candidate


@pytest.mark.parametrize("reference", [None, "invalid", "0" * 64, "not-ready"])
def test_unknown_reference_never_enters_old_list(
    tmp_path: Path, reference: str | None
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    result = successful(tasks, data, extraction.fingerprint, "read")
    if reference == "not-ready":
        settings = yaml.safe_load(data.settings.read_text())
        settings.pop("read")
        data.settings.write_text(yaml.safe_dump(settings))
        reference = compile_config(data.settings, data.database).snapshot_id
    query = ReadQueries(data.database, data.data_root)
    assert (
        query.analysis(result.analysis_id, snapshot_id=reference).config_status
        == "unknown"
    )
    assert query.old_configurations((data.paper_id,), snapshot_id=reference) == ()


def test_explicit_new_snapshot_only_labels_old_and_does_not_read_settings(
    tmp_path: Path,
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    result = successful(tasks, data, extraction.fingerprint, "read")
    snapshot = changed_profile(data)
    data.settings.unlink()
    query = ReadQueries(data.database, data.data_root)
    current = query.current(data.paper_id, snapshot_id=snapshot)
    assert current.state == "available"
    assert current.analyses[0].config_status == "old"
    assert current.analyses[0].changed_components == ("profile",)
    assert (
        query.analysis(result.analysis_id, snapshot_id=data.snapshot_id).config_status
        == "current"
    )
    old = query.old_configurations((data.paper_id, data.paper_id), snapshot_id=snapshot)
    assert len(old) == 1 and old[0].analysis_id == result.analysis_id
    assert query.old_configurations(snapshot_id=snapshot) == old
    assert set(asdict(old[0])) == {
        "paper_id",
        "analysis_id",
        "output_language",
        "changed_components",
    }
    assert "PRIVATE NEW PROFILE" not in str(asdict(old[0]))
    assert len(tasks.history(data.paper_id)) == 1
    assert tasks.task(result.task_id).remaining_attempts == 1


@pytest.mark.parametrize(
    "change", ["profile", "model", "prompt", "adapter", "screening", "version-only"]
)
def test_comparison_uses_only_read_semantics(tmp_path: Path, change: str) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    result = successful(tasks, data, extraction.fingerprint, "read")
    if change == "profile":
        reference = changed_profile(data)
    else:
        if change in {"model", "screening"}:
            slot = "reading" if change == "model" else "screening"
            new_yaml_version(
                data.settings, "models", lambda c: c[slot].update(model="changed-model")
            )
        elif change == "adapter":
            new_yaml_version(
                data.settings,
                "adapters.reading",
                lambda c: c.update(thinking_level="high"),
            )
        elif change == "version-only":
            new_yaml_version(data.settings, "read", lambda _: None)
        else:
            prompt = data.settings.parents[1] / "prompts/reading/v2.md"
            prompt.write_text("PRIVATE NEW PROMPT\n")
            settings = yaml.safe_load(data.settings.read_text())
            settings["prompts"]["reading"] = "v2"
            data.settings.write_text(yaml.safe_dump(settings))
        reference = compile_config(data.settings, data.database).snapshot_id
    view = ReadQueries(data.database, data.data_root).analysis(
        result.analysis_id, snapshot_id=reference
    )
    expected = (change,) if change in {"profile", "model", "prompt", "adapter"} else ()
    assert view.changed_components == expected
    assert view.config_status == ("old" if expected else "current")
    assert view.body_status == "current"


def test_latest_success_uses_commit_order_and_idempotent_replay_does_not_replace(
    tmp_path: Path,
) -> None:
    data, _, extraction = ready(tmp_path)
    clock = [NOW]
    tasks = ReadTasks(data.database, data.data_root, clock=lambda: clock[0])
    first_task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="a",
    )
    first_handle = tasks.claim(first_task.task_id)
    first = tasks.submit_test(first_handle, valid_candidate())
    new_snapshot = changed_profile(data)
    clock[0] -= timedelta(seconds=1)
    second_task = tasks.register(
        data.paper_id,
        snapshot_id=new_snapshot,
        extraction_fingerprint=extraction.fingerprint,
        request_id="b",
    )
    query = ReadQueries(data.database, data.data_root)
    tasks.fail(tasks.claim(second_task.task_id), "timeout")
    assert query.current(data.paper_id).analyses[0].analysis_id == first.analysis_id
    # 不同任务的时钟回拨与attempt序号都不能替代提交序。
    handle = tasks.claim(second_task.task_id)
    second = tasks.submit_test(handle, valid_candidate())
    english = successful(tasks, data, extraction.fingerprint, "en", language="en")
    query = ReadQueries(data.database, data.data_root)
    assert [
        (v.output_language, v.analysis_id)
        for v in query.current(data.paper_id).analyses
    ] == [("en", english.analysis_id), ("zh", second.analysis_id)]
    returned = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="a-replay",
    )
    assert returned.task_id == first.task_id
    assert (
        tasks.submit_test(first_handle, valid_candidate()).analysis_id
        == first.analysis_id
    )
    assert (
        tasks.submit_test(handle, valid_candidate()).analysis_id == second.analysis_id
    )
    assert query.current(data.paper_id).analyses[1].analysis_id == second.analysis_id
    latest = query.current(data.paper_id, snapshot_id=data.snapshot_id).analyses[1]
    assert latest.config_status == "old" and latest.changed_components == ("profile",)
    assert [a.analysis_id for a in query.history(data.paper_id)] == [
        first.analysis_id,
        second.analysis_id,
        english.analysis_id,
    ]
    assert (
        query.analysis(first.analysis_id, snapshot_id=data.snapshot_id).config_status
        == "current"
    )
    assert len(tasks.history(data.paper_id)) == 3


def test_unverifiable_snapshot_does_not_trust_its_id_or_projection(
    tmp_path: Path,
) -> None:
    import sqlite3

    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    result = successful(tasks, data, extraction.fingerprint, "read")
    reference = changed_profile(data)
    with sqlite3.connect(data.database) as connection:
        connection.execute(
            "UPDATE runtime_config_snapshots SET payload_json='{}' WHERE snapshot_id=?",
            (reference,),
        )
    query = ReadQueries(data.database, data.data_root)
    assert (
        query.analysis(result.analysis_id, snapshot_id=reference).config_status
        == "unknown"
    )
    assert query.old_configurations((data.paper_id,), snapshot_id=reference) == ()
