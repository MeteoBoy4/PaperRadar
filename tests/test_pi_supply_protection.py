"""公共安装句柄的真实本地锁边界,不依赖 Node/Pi。"""

from pathlib import Path

import pytest

from paper_radar.pi_supply import activate_supply
from tests.pi_supply_support import inputs, prepare


def test_shared_users_block_exclusive_collection_until_last_close(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import exclusive_install, probe_install, use_install

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    with use_install(source[0], source[1]) as first:
        assert first.install_id == prepared.install_id
        assert first.node.is_absolute() and first.pi.is_absolute()
        with use_install(source[0], source[1]) as second:
            assert first.pass_fds != second.pass_fds
            assert (
                probe_install(source[0], prepared.supply_id, first.install_id).state
                == "in_flight"
            )
        assert (
            probe_install(source[0], prepared.supply_id, first.install_id).state
            == "in_flight"
        )
    assert (
        probe_install(source[0], prepared.supply_id, first.install_id).state == "idle"
    )
    with exclusive_install(source[0], prepared.supply_id, first.install_id):
        assert (
            probe_install(source[0], prepared.supply_id, first.install_id).state
            == "in_flight"
        )


def test_activation_verify_and_doctor_share_the_use_boundary(tmp_path: Path) -> None:
    import pytest

    from paper_radar.pi_supply import (
        SupplyError,
        doctor_supply,
        exclusive_install,
        probe_install,
        use_install,
        verify_supply,
    )

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    root = tmp_path / "install"
    # 历史实例/外部损坏的缺锁现场;doctor 本身不得初始化。
    (root / ".locks" / f"{prepared.install_id}.lock").unlink()
    (root / ".locks").rmdir()
    before = sorted(path.relative_to(root) for path in root.rglob("*"))
    report = doctor_supply(source[0], source[1])
    assert report.instances[0].protection_state == "unknown"
    assert "protection_unknown" in report.instances[0].protection
    assert sorted(path.relative_to(root) for path in root.rglob("*")) == before
    activate_supply(source[0], prepared.supply_id, source[1])
    with exclusive_install(source[0], prepared.supply_id, prepared.install_id):
        with pytest.raises(SupplyError, match=r"install_unavailable|install_busy"):
            activate_supply(source[0], prepared.supply_id, source[1])
        with (
            pytest.raises(SupplyError, match="install_busy"),
            use_install(source[0], source[1]),
        ):
            pytest.fail("exclusive collector must exclude new users")
        checks = verify_supply(source[0], prepared.supply_id, runner=source[4])
        assert not checks[0].passed and checks[0].reason == "install_busy"
    with use_install(source[0], source[1]):
        report = doctor_supply(source[0], source[1])
        assert report.instances[0].protection_state == "in_flight"
        assert "in_flight" in report.instances[0].protection
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )


def test_normal_parent_close_keeps_live_child_protected(tmp_path: Path) -> None:
    import os
    import select

    from paper_radar.pi_supply import probe_install
    from tests.pi_supply_process_support import inherited_child, received

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    with inherited_child(source[0], source[1]) as (
        parent,
        child,
        release,
        request,
        closed,
    ):
        death = os.pidfd_open(child)
        try:
            os.write(request, b"C")
            assert received(closed) == b"C"
            assert (
                probe_install(source[0], prepared.supply_id, prepared.install_id).state
                == "in_flight"
            )
            os.write(release, b"X")
            assert select.select([death], [], [], 10)[0]
            assert parent.wait(timeout=10) == 0
        finally:
            os.close(death)
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )


def test_killed_parent_does_not_release_live_child_protection(tmp_path: Path) -> None:
    import os
    import select

    from paper_radar.pi_supply import probe_install
    from tests.pi_supply_process_support import inherited_child

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    with inherited_child(source[0], source[1]) as (parent, child, release, _, _):
        death = os.pidfd_open(child)
        try:
            parent.kill()
            assert parent.wait(timeout=10) < 0
            assert (
                probe_install(source[0], prepared.supply_id, prepared.install_id).state
                == "in_flight"
            )
            os.write(release, b"X")
            assert select.select([death], [], [], 10)[0]
        finally:
            os.close(death)
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )


def test_use_keeps_original_entries_after_new_activation(tmp_path: Path) -> None:
    from paper_radar.pi_supply import rebuild_supply, use_install

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    activate_supply(source[0], first.supply_id, source[1])
    with use_install(source[0], source[1]) as old:
        rebuilt = rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "second-root",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
        activate_supply(source[0], first.supply_id, source[1])
        with use_install(source[0], source[1]) as new:
            assert old.install_id == first.install_id
            assert new.install_id == rebuilt.install_id
            assert old.node != new.node and old.pi != new.pi
            assert (
                old.node
                == tmp_path
                / "install"
                / first.supply_id
                / first.install_id
                / "node/bin/node"
            )


def test_bad_tree_and_wrong_snapshot_do_not_leave_a_protection_holder(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.config import compile_config
    from paper_radar.pi_supply import SupplyError, probe_install, use_install

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    adapter = tmp_path / "config/adapters/pi-v1.yaml"
    (adapter.parent / "pi-v2.yaml").write_text(
        adapter.read_text()
        .replace("pi-v1", "pi-v2")
        .replace("1.3.0", "1.4.0")
        .replace("version: v1", "version: v2")
    )
    (tmp_path / "config/prompts/pi-system-v2.md").write_bytes(
        (tmp_path / "config/prompts/pi-system-v1.md").read_bytes()
    )
    settings = tmp_path / "config/settings.yaml"
    settings.write_text(settings.read_text().replace(": pi-v1", ": pi-v2"))
    wrong = compile_config(settings, source[0])
    with (
        pytest.raises(SupplyError, match="selection_version_mismatch"),
        use_install(source[0], wrong.snapshot_id),
    ):
        pytest.fail("incompatible snapshot must not receive a handle")
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )
    node = (
        tmp_path
        / "install"
        / prepared.supply_id
        / prepared.install_id
        / "node/bin/node"
    )
    node.chmod(0o755)
    node.write_bytes(b"broken")
    with (
        pytest.raises(SupplyError, match="tree_mismatch"),
        use_install(source[0], source[1]),
    ):
        pytest.fail("corrupt tree must not receive a handle")
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )


def test_unsafe_or_missing_lock_observation_is_read_only_and_conservative(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.pi_supply import SupplyError, exclusive_install, probe_install

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    (tmp_path / "install/.locks" / f"{prepared.install_id}.lock").unlink()
    (tmp_path / "install/.locks").rmdir()
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "unknown"
    )
    assert not (tmp_path / "install/.locks").exists()
    with (
        pytest.raises(SupplyError, match="protection_unknown"),
        exclusive_install(source[0], prepared.supply_id, prepared.install_id),
    ):
        pytest.fail("absent lock is not evidence of no user")
    activate_supply(source[0], prepared.supply_id, source[1])
    lock = tmp_path / "install/.locks" / f"{prepared.install_id}.lock"
    lock.unlink()
    secret = tmp_path / "secret"
    secret.write_bytes(b"secret")
    lock.symlink_to(secret)
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "unknown"
    )
    assert secret.read_bytes() == b"secret"


def test_exclusive_boundary_returns_actual_hash_for_safe_damaged_tree(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import exclusive_install, show_supply
    from paper_radar.pi_supply.filesystem import tree_hash

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    record = show_supply(source[0], prepared.supply_id)
    node = record.installs[0].path / "node/bin/node"
    node.chmod(0o755)
    node.write_bytes(b"damaged but safely located")
    actual = tree_hash(record.installs[0].path)
    with exclusive_install(
        source[0], prepared.supply_id, prepared.install_id
    ) as handle:
        assert actual != record.manifest.expected_tree
        assert handle.recheck(source[0]) == actual


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("failure", "process_failed"),
        ("timeout", "process_timeout"),
        ("cancel", "operation_interrupted"),
    ],
)
def test_actual_verify_failure_timeout_and_cancel_release_protection(
    tmp_path: Path,
    action: str,
    expected: str,
) -> None:
    import os
    import select
    import signal

    from paper_radar.pi_supply import probe_install, show_supply
    from tests.pi_supply_process_support import checking_process

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    with checking_process(
        source[0], prepared.supply_id, 1 if action == "timeout" else 30
    ) as (parent, child, release):
        death = os.pidfd_open(child)
        try:
            assert (
                probe_install(source[0], prepared.supply_id, prepared.install_id).state
                == "in_flight"
            )
            if action == "failure":
                os.write(release, b"X")
            elif action == "cancel":
                parent.send_signal(signal.SIGINT)
            stdout, stderr = parent.communicate(timeout=10)
            assert parent.returncode == 0 and not stderr
            assert stdout.strip() == expected.encode()
            assert select.select([death], [], [], 10)[0]
        finally:
            os.close(death)
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )
    assert (
        show_supply(source[0], prepared.supply_id).installs[0].checks[-1].reason
        == expected
    )


def test_independent_processes_keep_protection_until_both_children_exit(
    tmp_path: Path,
) -> None:
    import os
    import select

    from paper_radar.pi_supply import probe_install
    from tests.pi_supply_process_support import inherited_child, received

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    with (
        inherited_child(source[0], source[1]) as one,
        inherited_child(source[0], source[1]) as two,
    ):
        for parent, child, release, request, closed in (one, two):
            death = os.pidfd_open(child)
            try:
                assert (
                    probe_install(
                        source[0], prepared.supply_id, prepared.install_id
                    ).state
                    == "in_flight"
                )
                os.write(request, b"C")
                assert received(closed) == b"C"
                os.write(release, b"X")
                assert select.select([death], [], [], 10)[0]
                assert parent.wait(timeout=10) == 0
            finally:
                os.close(death)
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )


def test_doctor_keeps_in_flight_install_outside_retention_window(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import doctor_supply, rebuild_supply, use_install

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    activate_supply(source[0], first.supply_id, source[1])
    with use_install(source[0], source[1]):
        for index in range(4):
            rebuild_supply(
                source[0],
                first.supply_id,
                tmp_path / f"root-{index}",
                data_root=tmp_path / "data",
                config_root=tmp_path / "config",
                material_root=tmp_path / "materials",
                downloader=source[3],
                runner=source[4],
            )
            activate_supply(source[0], first.supply_id, source[1])
        report = doctor_supply(source[0], source[1])
        old = next(
            item for item in report.instances if item.install_id == first.install_id
        )
        assert first.install_id not in report.retained_install_ids
        assert old.protection_state == "in_flight" and "in_flight" in old.protection
        assert "retention_exceeded" in report.blockers and report.present_count == 5


def test_historical_queries_do_not_require_platform_flock(tmp_path: Path) -> None:
    import subprocess
    import sys

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    code = """
import sys
from pathlib import Path
sys.modules['fcntl'] = None
from paper_radar.pi_supply import list_supplies, show_supply
assert list_supplies(Path(sys.argv[1]))[0].supply_id == sys.argv[2]
assert show_supply(Path(sys.argv[1]), sys.argv[2]).manifest.pi_version == '1.3.0'
"""
    result = subprocess.run(
        (sys.executable, "-c", code, str(source[0]), prepared.supply_id),
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0 and not result.stdout and not result.stderr


def test_new_never_activated_install_has_initialized_observable_protection(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import exclusive_install, probe_install

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    assert (
        probe_install(source[0], prepared.supply_id, prepared.install_id).state
        == "idle"
    )
    with exclusive_install(source[0], prepared.supply_id, prepared.install_id):
        assert (
            probe_install(source[0], prepared.supply_id, prepared.install_id).state
            == "in_flight"
        )
