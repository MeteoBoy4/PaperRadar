"""核验与历史固定材料重建的公共服务行为。"""

import json
import multiprocessing
import os
import signal
import sqlite3
import sys
from pathlib import Path
from typing import TypedDict

import pytest

from paper_radar.pi_supply import show_supply, verify_supply
from paper_radar.pi_supply.transport import Runner
from tests.pi_supply_support import Download, Run, inputs, prepare


class RebuildOptions(TypedDict):
    data_root: Path
    config_root: Path
    material_root: Path
    downloader: Download
    runner: Runner


def test_verify_appends_checks_to_the_instance_it_actually_checks(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    runner = Run()
    result = verify_supply(source[0], prepared.supply_id, runner=runner)
    assert [(item.install_id, item.passed, item.reason) for item in result] == [
        (prepared.install_id, True, "passed")
    ]
    checks = show_supply(source[0], prepared.supply_id).installs[0].checks
    assert len(checks) == 2
    assert all(check.passed and check.scope == "install_check" for check in checks)
    assert not any("ci" in call[0] for call in runner.calls)


def test_verify_damaged_tree_does_not_execute_and_preserves_success(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    instance = show_supply(source[0], prepared.supply_id).installs[0]
    entry = instance.path / "node/bin/node"
    entry.chmod(0o755)
    entry.write_bytes(b"damaged")
    runner = Run()
    result = verify_supply(source[0], prepared.supply_id, runner=runner)
    assert not result[0].passed and result[0].reason == "tree_mismatch"
    assert not runner.calls
    checks = show_supply(source[0], prepared.supply_id).installs[0].checks
    assert [check.passed for check in checks] == [True, False]


@pytest.mark.parametrize("program", ["node", "npm", "pi"])
def test_verify_explicit_program_probe_failure_is_audited(
    tmp_path: Path, program: str
) -> None:
    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)

    class WrongVersion(Run):
        def run(self, argv: tuple[str, ...], **kwargs: object) -> bytes:
            if argv[-1] == "--version" and (
                (program == "node" and len(argv) == 2)
                or (program == "npm" and "npm-cli.js" in argv[1])
                or (program == "pi" and "dist/cli.js" in argv[1])
            ):
                return b"SECRET-wrong-version"
            return super().run(argv, **kwargs)  # type: ignore[arg-type]

    result = verify_supply(source[0], prepared.supply_id, runner=WrongVersion())
    assert result[0].reason == program + "_version_mismatch"
    assert len(show_supply(source[0], prepared.supply_id).installs[0].checks) == 2


def test_rebuild_uses_frozen_materials_and_preserves_bad_instance(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import rebuild_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    original = show_supply(source[0], prepared.supply_id)
    old_node = original.installs[0].path / "node/bin/node"
    old_node.chmod(0o755)
    old_node.write_bytes(b"damaged old installation")
    source[2].unlink()
    (tmp_path / "evidence.txt").unlink()
    download = source[3]
    download.content = {
        url: raw for url, raw in download.content.items() if url.endswith(".tar.xz")
    }
    download.calls.clear()
    result = rebuild_supply(
        source[0],
        prepared.supply_id,
        tmp_path / "other-install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=download,
        runner=Run(),
    )
    record = show_supply(source[0], prepared.supply_id)
    assert result.supply_id == prepared.supply_id
    assert result.install_id != prepared.install_id
    assert (
        record.manifest == original.manifest and record.materials == original.materials
    )
    assert len(record.installs) == 2
    assert old_node.read_bytes() == b"damaged old installation"
    assert len(download.calls) == 1 and download.calls[0].endswith(".tar.xz")
    results = verify_supply(source[0], prepared.supply_id, runner=Run())
    assert {item.install_id: item.passed for item in results} == {
        prepared.install_id: False,
        result.install_id: True,
    }
    assert all(
        len(instance.checks) == 2
        for instance in show_supply(source[0], prepared.supply_id).installs
    )


def test_failed_rebuild_appends_failure_without_registering_install(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import SupplyError, rebuild_supply

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    source[3].content = {
        url: b"SECRET-bad-archive"
        for url in source[3].content
        if url.endswith(".tar.xz")
    }
    with pytest.raises(SupplyError, match="node_checksum_mismatch"):
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
    record = show_supply(source[0], prepared.supply_id)
    assert len(record.installs) == 1 and len(record.installs[0].checks) == 1
    assert [failure.reason for failure in record.rebuild_failures] == [
        "node_checksum_mismatch"
    ]


def test_available_instances_sort_by_success_not_latest_failure_with_stable_ties(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.pi_supply import available_installs, rebuild_supply, repository

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
    assert [i.install_id for i in available_installs(source[0], first.supply_id)] == [
        second.install_id,
        first.install_id,
    ]

    # 同时间按 check_id 破同;之后的失败不抹去该实例以前的成功。
    class Fail(Run):
        def run(self, argv: tuple[str, ...], **kwargs: object) -> bytes:
            return b"wrong"

    verify_supply(source[0], first.supply_id, runner=Fail())
    assert (
        available_installs(source[0], first.supply_id)[0].install_id
        == second.install_id
    )
    newest = next(
        i
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == second.install_id
    )
    node = newest.path / "node/bin/node"
    node.chmod(0o755)
    node.write_bytes(b"bad")
    assert [i.install_id for i in available_installs(source[0], first.supply_id)] == [
        first.install_id
    ]


def test_rebuild_registration_rollback_and_retry_only_recovers_owned_intent(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import SupplyError, rebuild_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "CREATE TRIGGER reject_install_check BEFORE INSERT ON pi_install_checks "
            "BEGIN SELECT RAISE(ABORT, 'SECRET-db-error'); END"
        )
    kwargs: RebuildOptions = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    with pytest.raises(SupplyError, match="database_unavailable") as caught:
        rebuild_supply(source[0], first.supply_id, tmp_path / "install", **kwargs)
    assert "SECRET" not in str(caught.value)
    record = show_supply(source[0], first.supply_id)
    assert (
        len(record.installs) == 1
        and record.rebuild_failures[0].reason == "database_unavailable"
    )
    pending = next((tmp_path / "install").glob(".pending-rebuild-*.json"))
    intent = json.loads(pending.read_bytes())
    with sqlite3.connect(source[0]) as connection:
        connection.execute("DROP TRIGGER reject_install_check")
    unknown = tmp_path / "install/.staging-unknown"
    unknown.mkdir()
    (unknown / "keep").write_bytes(b"manual handling")
    result = rebuild_supply(source[0], first.supply_id, tmp_path / "install", **kwargs)
    assert result.install_id == intent["install_id"]
    assert not pending.exists()
    assert (unknown / "keep").read_bytes() == b"manual handling"
    assert len(show_supply(source[0], first.supply_id).installs) == 2


@pytest.mark.parametrize(
    "drift,expected",
    [
        ("node", "node_version_mismatch"),
        ("npm", "npm_version_mismatch"),
        ("pi", "pi_version_mismatch"),
        ("lock", "installed_material_changed"),
        ("tree", "tree_mismatch"),
        ("startup", "startup_side_effect"),
    ],
)
def test_rebuild_refuses_frozen_toolchain_lock_and_tree_drift(
    tmp_path: Path,
    drift: str,
    expected: str,
) -> None:
    from paper_radar.pi_supply import SupplyError, rebuild_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    original = show_supply(source[0], first.supply_id)

    class Drift(Run):
        def run(
            self,
            argv: tuple[str, ...],
            *,
            cwd: Path,
            env: dict[str, str],
            timeout: int,
            limit: int,
        ) -> bytes:
            result = super().run(argv, cwd=cwd, env=env, timeout=timeout, limit=limit)
            if argv[-1] == "--version" and (
                (drift == "node" and len(argv) == 2)
                or (drift == "npm" and "npm-cli.js" in argv[1])
                or (drift == "pi" and "dist/cli.js" in argv[1])
            ):
                return b"SECRET-drift"
            if "ci" in argv and drift == "lock":
                (cwd / "package-lock.json").write_bytes(b"drift")
            if "ci" in argv and drift == "tree":
                (cwd / "unexpected").write_bytes(b"drift")
            if argv[-1] == "--help" and drift == "startup":
                (Path(env["PI_CODING_AGENT_SESSION_DIR"]) / "unexpected").write_bytes(
                    b"session"
                )
            return result

    with pytest.raises(SupplyError, match=expected) as caught:
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=Drift(),
        )
    assert "SECRET" not in str(caught.value)
    record = show_supply(source[0], first.supply_id)
    assert record.installs == original.installs and record.manifest == original.manifest
    assert [failure.reason for failure in record.rebuild_failures] == [expected]


def test_verify_platform_probe_failure_is_controlled_and_history_is_queryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.pi_supply import SupplyError, list_supplies

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    monkeypatch.delattr(os, "confstr")
    with pytest.raises(SupplyError, match="platform_mismatch"):
        verify_supply(source[0], first.supply_id, runner=Run())
    assert list_supplies(source[0])[0].supply_id == first.supply_id


def test_failed_failure_audit_preserves_controlled_execution_reason(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import SupplyError, rebuild_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "CREATE TRIGGER reject_failure BEFORE INSERT ON pi_rebuild_failures "
            "BEGIN SELECT RAISE(ABORT, 'SECRET-db-error'); END"
        )
    source[3].content = {
        url: b"bad archive" for url in source[3].content if url.endswith(".tar.xz")
    }
    with pytest.raises(SupplyError, match="failure_record_failed") as caught:
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=Run(),
        )
    assert caught.value.execution_reason == "node_checksum_mismatch"
    assert "SECRET" not in str(caught.value)
    record = show_supply(source[0], first.supply_id)
    assert len(record.installs) == 1 and not record.rebuild_failures


def test_committed_rebuild_reports_cleanup_residual_and_reenters_same_instance(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import rebuild_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    root = tmp_path / "install"

    class ReadOnlyParent(Run):
        def run(self, argv: tuple[str, ...], **kwargs: object) -> bytes:
            result = super().run(argv, **kwargs)  # type: ignore[arg-type]
            if "--help" in argv and ".staging-" not in argv[1]:
                root.chmod(0o500)
            return result

    result = rebuild_supply(
        source[0],
        first.supply_id,
        root,
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=ReadOnlyParent(),
    )
    root.chmod(0o700)
    assert result.residuals
    record = show_supply(source[0], first.supply_id)
    assert len(record.installs) == 2 and not record.rebuild_failures
    again = rebuild_supply(
        source[0],
        first.supply_id,
        root,
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    assert again.install_id == result.install_id and not again.residuals
    assert len(show_supply(source[0], first.supply_id).installs) == 2


def test_sigkill_after_registration_preserves_success_and_retries_same_intent(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import rebuild_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)

    def child_rebuild() -> None:
        def kill_before_unlink(event: str, args: tuple[object, ...]) -> None:
            if event == "os.remove" and ".pending-rebuild-" in str(args[0]):
                os.kill(os.getpid(), signal.SIGKILL)

        sys.addaudithook(kill_before_unlink)
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=Run(),
        )

    child = multiprocessing.get_context("fork").Process(target=child_rebuild)
    child.start()
    child.join(timeout=20)
    assert not child.is_alive() and child.exitcode == -signal.SIGKILL
    record = show_supply(source[0], first.supply_id)
    assert len(record.installs) == 2 and not record.rebuild_failures
    intent = json.loads(
        next((tmp_path / "install").glob(".pending-rebuild-*.json")).read_bytes()
    )
    result = rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    assert result.install_id == intent["install_id"]
    assert len(show_supply(source[0], first.supply_id).installs) == 2


def test_sigkill_after_publication_is_reentrant_without_registering_half_success(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import rebuild_supply

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)

    class KillPublished(Run):
        def run(self, argv: tuple[str, ...], **kwargs: object) -> bytes:
            if (
                len(argv) > 2
                and "dist/cli.js" in argv[1]
                and ".staging-" not in argv[1]
            ):
                os.kill(os.getpid(), signal.SIGKILL)
            return super().run(argv, **kwargs)  # type: ignore[arg-type]

    kwargs: RebuildOptions = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=KillPublished(),
    )
    child = multiprocessing.get_context("fork").Process(
        target=rebuild_supply,
        args=(source[0], first.supply_id, tmp_path / "install"),
        kwargs=kwargs,
    )
    child.start()
    child.join(timeout=20)
    assert not child.is_alive() and child.exitcode == -signal.SIGKILL
    assert len(show_supply(source[0], first.supply_id).installs) == 1
    pending = next((tmp_path / "install").glob(".pending-rebuild-*.json"))
    intent = json.loads(pending.read_bytes())
    residuals = tuple((tmp_path / "install").glob(".staging-*"))
    kwargs["runner"] = Run()
    result = rebuild_supply(source[0], first.supply_id, tmp_path / "install", **kwargs)
    assert result.install_id == intent["install_id"]
    assert all(residual.exists() for residual in residuals)
    assert len(show_supply(source[0], first.supply_id).installs) == 2
