from pathlib import Path

import pytest

from tests.site_deployment_checkpoint_support import run_bootstrap
from tests.site_g2_entry_support import g2_entry_sandbox


def test_g2_entry_is_single_sudo_without_interactive_activation() -> None:
    from paper_radar.live_evidence.deployment import render_g2_runner

    source = render_g2_runner(
        {
            name: "a" * 64
            for name in (
                "deploy.sh",
                "uninstall.sh",
                "owner-workflow.sh",
                "payload.tar",
            )
        }
    )
    assert source.count("/usr/bin/sudo ") == 1
    assert "/usr/bin/sudo -k " in source
    assert " read " not in source
    assert " activate " not in source
    assert "package_check" in source


def test_single_user_entry_runs_sealed_workflow_and_reports_receipt_without_g3(
    tmp_path: Path,
) -> None:
    root, runner, sudo_log, events = g2_entry_sandbox(tmp_path)
    result = run_bootstrap([str(runner)])
    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr == b""
    assert sudo_log.read_text() == "-k\n"
    assert events.read_text().splitlines()[0] == "collect"
    assert events.read_text().splitlines()[1].startswith("receive --plan ")
    assert len(events.read_text().splitlines()) == 2
    assert b"receipt_id=0123456789abcdef" in result.stdout
    assert "G3证据激活未执行" in result.stdout.decode()
    for stage in (
        b"package_check",
        b"root_copy",
        b"owner_cwd_prepare",
        b"runtime_install",
        b"collect",
        b"receive",
    ):
        assert b"G2 stage=" + stage in result.stdout
    assert (root / "cwd-owner-changed").is_file()
    assert (
        root / "var/lib/paperradar/live-evidence-staging/owner-workflow.sh"
    ).is_file()


def test_tampered_owner_workflow_stops_before_sudo_and_cwd_change(
    tmp_path: Path,
) -> None:
    root, runner, sudo_log, events = g2_entry_sandbox(tmp_path)
    runner.with_name("owner-workflow.sh").write_text("exit 0\n")
    result = run_bootstrap([str(runner)])
    assert result.returncode != 0
    assert not sudo_log.exists()
    assert not events.exists()
    assert not (root / "cwd-owner-changed").exists()


@pytest.mark.parametrize("state", ["nonempty", "symlink", "owner", "ancestor"])
def test_single_entry_refuses_unsafe_cwd_before_deploy_or_collect(
    tmp_path: Path, state: str
) -> None:
    root, runner, sudo_log, events = g2_entry_sandbox(
        tmp_path, initial_uid=1001 if state == "owner" else 1000
    )
    cwd = root / "srv/pi-cwd"
    if state == "nonempty":
        (cwd / "retained").write_bytes(b"user data")
    elif state == "symlink":
        cwd.rmdir()
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        cwd.symlink_to(outside, target_is_directory=True)
    elif state == "ancestor":
        (root / "srv").chmod(0o777)
    result = run_bootstrap([str(runner)])
    expected = {
        "nonempty": "cwd_not_empty",
        "symlink": "cwd_symlink",
        "owner": "cwd_state_unexpected",
        "ancestor": "protected_mode",
    }
    assert result.returncode == 2
    assert f"[{expected[state]}]".encode() in result.stderr
    assert sudo_log.read_text() == "-k\n"
    assert not events.exists()
    assert not (root / "cwd-owner-changed").exists()
    assert not (root / "usr/libexec/paperradar").exists()
    if state == "nonempty":
        assert (cwd / "retained").read_bytes() == b"user data"
    elif state == "symlink":
        assert cwd.is_symlink()


def test_collector_failure_stops_before_receive_and_success_summary(
    tmp_path: Path,
) -> None:
    _, runner, sudo_log, events = g2_entry_sandbox(tmp_path, collector_status=2)
    result = run_bootstrap([str(runner)])
    assert result.returncode == 2
    assert sudo_log.read_text() == "-k\n"
    assert events.read_text() == "collect\n"
    assert b"stage=collect" in result.stderr
    assert b"receipt_id=" not in result.stdout
    assert "G2完成" not in result.stdout.decode()


def test_root_rechecks_workflow_hash_after_user_check(tmp_path: Path) -> None:
    root, runner, sudo_log, events = g2_entry_sandbox(tmp_path)
    sudo_tool = tmp_path / "sudo-model"
    source = sudo_tool.read_text()
    source = source.replace(
        'exec "$@"',
        f'/usr/bin/printf tampered > "{runner.with_name("owner-workflow.sh")}"\n'
        'exec "$@"',
    )
    sudo_tool.write_text(source)
    result = run_bootstrap([str(runner)])
    assert result.returncode != 0
    assert sudo_log.read_text() == "-k\n"
    assert not events.exists()
    assert not (root / "cwd-owner-changed").exists()
