"""执行选择经公共服务原子更新,诊断只读解释窄供给范围。"""

from pathlib import Path

import pytest

from tests.pi_supply_support import inputs, prepare


def test_activate_is_auditable_and_doctor_does_not_grant_business_readiness(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import activate_supply, activation_history, doctor_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    source[3].calls.clear()
    source[4].calls.clear()
    selected = activate_supply(source[0], prepared.supply_id, source[1][:8])
    assert selected.install_id == prepared.install_id
    assert selected.snapshot_id == source[1]
    assert activation_history(source[0]) == (selected,)
    before = source[0].read_bytes()
    report = doctor_supply(source[0], source[1])
    assert report.passed and report.current == selected
    assert "read_contract" in report.configuration_missing
    assert "rpc_compatibility" in report.not_assessed
    assert report.d5 is not None and report.d5.decision == "unknown"
    assert source[0].read_bytes() == before
    assert not source[3].calls and not source[4].calls


def test_all_selected_slots_participate_even_when_prompt_is_placeholder(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.config import compile_config
    from paper_radar.pi_supply import SupplyError, activate_supply, doctor_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    first = activate_supply(source[0], prepared.supply_id, source[1])
    config = tmp_path / "config"
    adapter = config / "adapters/pi-v1.yaml"
    from hashlib import sha256

    from tests.config_adapter_support import SYSTEM_PROMPT_SHA256

    (config / "prompts/pi-system-v2.md").write_bytes(b"...\n")
    (config / "adapters/pi-v2.yaml").write_text(
        adapter.read_text()
        .replace("pi-v1", "pi-v2")
        .replace("1.3.0", "1.4.0")
        .replace("version: v1", "version: v2")
        .replace(SYSTEM_PROMPT_SHA256, sha256(b"...\n").hexdigest())
    )
    settings = config / "settings.yaml"
    settings.write_text(
        settings.read_text().replace("reading: pi-v1", "reading: pi-v2")
    )
    snapshot = compile_config(settings, source[0])
    with pytest.raises(SupplyError, match="adapter_versions_mixed"):
        activate_supply(source[0], prepared.supply_id, snapshot.snapshot_id)
    assert (
        "adapter_versions_mixed"
        in doctor_supply(source[0], snapshot.snapshot_id).blockers
    )
    settings.write_text(
        settings.read_text()
        .replace("screening: pi-v1", "screening: pi-v2")
        .replace("reuse_assessment: pi-v1", "reuse_assessment: pi-v2")
    )
    incompatible = compile_config(settings, source[0])
    with pytest.raises(SupplyError, match="selection_version_mismatch"):
        activate_supply(source[0], prepared.supply_id, incompatible.snapshot_id)
    report = doctor_supply(source[0], incompatible.snapshot_id)
    assert report.current == first
    assert "selection_version_mismatch" in report.blockers


def test_missing_current_then_rebuild_activate_preserves_damaged_history(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import (
        activate_supply,
        activation_history,
        doctor_supply,
        rebuild_supply,
        show_supply,
    )
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    first = activate_supply(source[0], prepared.supply_id, source[1])
    node = show_supply(source[0], prepared.supply_id).installs[0].path / "node/bin/node"
    node.chmod(0o755)
    node.write_bytes(b"bad")
    report = doctor_supply(source[0], source[1])
    assert not report.passed and report.blockers == ("tree_mismatch",)
    rebuilt = rebuild_supply(
        source[0],
        prepared.supply_id,
        tmp_path / "new-root",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    assert doctor_supply(source[0], source[1]).current == first
    second = activate_supply(source[0], prepared.supply_id, source[1])
    assert second.install_id == rebuilt.install_id
    assert activation_history(source[0]) == (first, second)
    report = doctor_supply(source[0], source[1])
    assert report.passed and report.present_count == 2
    assert {item.install_id: item.reason for item in report.instances}[
        first.install_id
    ] == "tree_mismatch"
    assert report.retained_install_ids == (second.install_id, first.install_id)


def test_failed_selection_update_rolls_back_activation_event(tmp_path: Path) -> None:
    import sqlite3

    import pytest

    from paper_radar.pi_supply import (
        SupplyError,
        activate_supply,
        activation_history,
        doctor_supply,
    )

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    first = activate_supply(source[0], prepared.supply_id, source[1])
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "CREATE TRIGGER fail_selection BEFORE UPDATE ON pi_current_selection "
            "BEGIN SELECT RAISE(ABORT, 'SECRET'); END"
        )
    with pytest.raises(SupplyError, match="database_unavailable") as caught:
        activate_supply(source[0], prepared.supply_id, source[1])
    assert "SECRET" not in str(caught.value)
    assert activation_history(source[0]) == (first,)
    assert doctor_supply(source[0], source[1]).current == first


def test_repeated_activation_does_not_expand_retention_and_unactivated_trees_count(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import activate_supply, doctor_supply, rebuild_supply
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    for _ in range(5):
        activate_supply(source[0], prepared.supply_id, source[1])
    report = doctor_supply(source[0], source[1])
    assert report.retained_install_ids == (prepared.install_id,) and report.passed
    for _ in range(4):
        rebuild_supply(
            source[0],
            prepared.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=Run(),
        )
    report = doctor_supply(source[0], source[1])
    assert report.present_count == 5 and report.blockers == ("retention_exceeded",)
    assert (
        report.current is not None and report.current.install_id == prepared.install_id
    )
    assert len(report.acceptance_install_ids) == 1


def test_cli_activation_and_explicit_doctor_scope(tmp_path: Path) -> None:
    from tests.config_test_support import run_cli

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    result = run_cli(
        tmp_path,
        "pi",
        "supply",
        "activate",
        prepared.supply_id,
        "--database",
        str(source[0]),
        "--snapshot",
        source[1][:8],
    )
    assert result.returncode == 0, result.stderr
    result = run_cli(
        tmp_path,
        "doctor",
        "--scope",
        "pi-supply",
        "--database",
        str(source[0]),
        "--snapshot",
        source[1],
    )
    assert result.returncode == 0, result.stderr
    assert "scope=pi-supply result=passed" in result.stdout
    assert (
        "read_contract" in result.stdout
        and "RPC" in result.stdout
        and "unknown" in result.stdout
    )


def test_no_adapter_slot_cannot_activate_and_unselected_slots_are_ignored(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.config import compile_config
    from paper_radar.pi_supply import SupplyError, activate_supply, doctor_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    settings = tmp_path / "config/settings.yaml"
    settings.write_text(settings.read_text().split("adapters:")[0])
    empty = compile_config(settings, source[0])
    with pytest.raises(SupplyError, match="adapter_missing"):
        activate_supply(source[0], prepared.supply_id, empty.snapshot_id)
    assert "adapter_missing" in doctor_supply(source[0], empty.snapshot_id).blockers
    settings.write_text(settings.read_text() + "adapters:\n  screening: pi-v1\n")
    single = compile_config(settings, source[0])
    activate_supply(source[0], prepared.supply_id, single.snapshot_id)
    report = doctor_supply(source[0], single.snapshot_id)
    assert report.passed and report.adapter_unconfigured == (
        "reuse_assessment",
        "reading",
    )


def test_concurrent_activations_publish_one_complete_current_event(
    tmp_path: Path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from paper_radar.pi_supply import activate_supply, activation_history, doctor_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(
                lambda _: activate_supply(source[0], prepared.supply_id, source[1]),
                range(2),
            )
        )
    history = activation_history(source[0])
    assert len(history) == 2 and set(history) == set(results)
    assert doctor_supply(source[0], source[1]).current == history[-1]


def test_supply_activation_install_root_changes_preserve_all_six_projections(
    tmp_path: Path,
) -> None:
    import json

    from paper_radar.config import load_config_snapshot
    from paper_radar.config.projections import project_config
    from paper_radar.pi_supply import activate_supply, prepare_supply, rebuild_supply
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    before = project_config(load_config_snapshot(source[0], source[1]))
    first = prepare(tmp_path, source)
    activate_supply(source[0], first.supply_id, source[1])
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "second-root",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    activate_supply(source[0], first.supply_id, source[1])
    # 只改变执行工具链版本和归档摘要,模型语义仍消费同一快照。
    from tests.pi_supply_support import Download

    download = Download()
    request = json.loads(source[2].read_bytes())
    request["npm_version"] = "10.9.4"
    source[2].write_text(json.dumps(request))

    class NewNpm(Run):
        def run(self, argv: tuple[str, ...], **kwargs: object) -> bytes:
            if argv[-1] == "--version" and "npm-cli.js" in argv[1]:
                return b"10.9.4\n"
            return super().run(argv, **kwargs)  # type: ignore[arg-type]

    second = prepare_supply(
        source[0],
        source[1],
        "screening",
        source[2],
        tmp_path / "third-root",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=download,
        runner=NewNpm(),
    )
    assert second.supply_id != first.supply_id
    activate_supply(source[0], second.supply_id, source[1])
    after = project_config(load_config_snapshot(source[0], source[1]))
    assert len(after.projections) == 6
    assert after == before


def test_profile_and_models_missing_are_disclosed_separately_from_supply(
    tmp_path: Path,
) -> None:
    from paper_radar.config import compile_config
    from paper_radar.pi_supply import activate_supply, doctor_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    settings = tmp_path / "config/settings.yaml"
    settings.write_text(
        settings.read_text()
        .replace("profile: profile-v1\n", "")
        .replace("models: models-v1\n", "")
    )
    snapshot = compile_config(settings, source[0])
    activate_supply(source[0], prepared.supply_id, snapshot.snapshot_id)
    report = doctor_supply(source[0], snapshot.snapshot_id)
    assert report.passed
    assert {"profile", "model:screening", "read_contract"} <= set(
        report.configuration_missing
    )


def test_activation_selects_latest_success_with_ties_and_excludes_bad_newest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_supply import (
        activate_supply,
        rebuild_supply,
        repository,
        show_supply,
    )
    from tests.pi_supply_support import Run

    monkeypatch.setattr(repository, "now", lambda: "2026-10-18T00:00:00+00:00")
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    second = rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    assert (
        activate_supply(source[0], first.supply_id, source[1]).install_id
        == second.install_id
    )
    instance = next(
        item
        for item in show_supply(source[0], first.supply_id).installs
        if item.install_id == second.install_id
    )
    node = instance.path / "node/bin/node"
    node.chmod(0o755)
    node.write_bytes(b"bad")
    assert (
        activate_supply(source[0], first.supply_id, source[1]).install_id
        == first.install_id
    )


def _pause_activation_before_selection(
    database: Path, supply_id: str, snapshot: str, ready: object
) -> None:
    import signal

    from sqlalchemy import Engine, event

    from paper_radar.pi_supply import activate_supply

    @event.listens_for(Engine, "before_cursor_execute")
    def pause(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        many: bool,
    ) -> None:
        if statement.startswith("UPDATE pi_current_selection"):
            ready.set()  # type: ignore[attr-defined]
            signal.pause()

    activate_supply(database, supply_id, snapshot)


def test_killed_activation_after_event_insert_preserves_complete_old_selection(
    tmp_path: Path,
) -> None:
    import multiprocessing

    from paper_radar.pi_supply import activate_supply, activation_history, doctor_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    first = activate_supply(source[0], prepared.supply_id, source[1])
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(
        target=_pause_activation_before_selection,
        args=(source[0], prepared.supply_id, source[1], ready),
    )
    process.start()
    try:
        assert ready.wait(10), "child did not reach the uncommitted activation boundary"
        assert doctor_supply(source[0], source[1]).current == first
        process.kill()
        process.join(10)
        assert process.exitcode == -9
    finally:
        if process.is_alive():
            process.kill()
            process.join(10)
    assert activation_history(source[0]) == (first,)
    assert doctor_supply(source[0], source[1]).current == first
