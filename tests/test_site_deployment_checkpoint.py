from pathlib import Path

from tests.site_deployment_checkpoint_support import bootstrap_sandbox, run_bootstrap


def test_three_sha_successes_then_foreign_cwd_reports_actionable_refusal(
    tmp_path: Path,
) -> None:
    root, _, command = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    cwd = root / "srv/pi-cwd"
    before = cwd.stat()
    result = run_bootstrap(command)
    assert result.returncode == 2
    assert len(result.stdout.splitlines()) == 3
    assert all(line.endswith(b": OK") for line in result.stdout.splitlines())
    assert b"[protected_owner]" in result.stderr
    assert b"stage=preflight" in result.stderr
    assert b"resource=cwd" in result.stderr
    assert "所有者" in result.stderr.decode()
    assert str(root).encode() not in result.stderr
    assert cwd.stat() == before
    assert not list(cwd.iterdir())
    assert not (root / "usr/libexec/paperradar").exists()
    assert not (root / "var/lib/paperradar/live-evidence").exists()
    assert not (root / "etc/sudoers.d/paperradar-live-evidence").exists()


def test_explicit_owner_cwd_preparation_preserves_nonempty_directory(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_checkpoint_support import cwd_preparation_command

    root, _, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    cwd = root / "srv/pi-cwd"
    retained = cwd / "retained"
    retained.write_bytes(b"user data")
    before = cwd.stat()
    result = run_bootstrap(cwd_preparation_command(root))
    assert result.returncode == 2
    assert b"[cwd_not_empty]" in result.stderr
    after = cwd.stat()
    assert (
        after.st_ino,
        after.st_uid,
        after.st_gid,
        after.st_mode,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) == (
        before.st_ino,
        before.st_uid,
        before.st_gid,
        before.st_mode,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    assert retained.read_bytes() == b"user data"
    assert not (root / "cwd-owner-changed").exists()


def test_explicit_owner_preparation_refuses_symlink_without_touching_target(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_checkpoint_support import cwd_preparation_command

    root, _, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    cwd = root / "srv/pi-cwd"
    cwd.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    cwd.symlink_to(outside, target_is_directory=True)
    before = outside.stat()
    result = run_bootstrap(cwd_preparation_command(root))
    assert result.returncode == 2
    assert b"[cwd_symlink]" in result.stderr
    assert cwd.is_symlink()
    assert outside.stat() == before
    assert not (root / "cwd-owner-changed").exists()


def test_explicit_owner_preparation_refuses_unexpected_owner(tmp_path: Path) -> None:
    from tests.site_deployment_checkpoint_support import cwd_preparation_command

    root, _, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    cwd = root / "srv/pi-cwd"
    before = cwd.stat()
    result = run_bootstrap(cwd_preparation_command(root, initial_uid=1001))
    assert result.returncode == 2
    assert b"[cwd_state_unexpected]" in result.stderr
    assert cwd.stat() == before
    assert not (root / "cwd-owner-changed").exists()


def test_explicit_owner_preparation_refuses_writable_ancestor(tmp_path: Path) -> None:
    from tests.site_deployment_checkpoint_support import cwd_preparation_command

    root, _, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    (root / "srv").chmod(0o777)
    result = run_bootstrap(cwd_preparation_command(root))
    assert result.returncode == 2
    assert b"[protected_mode]" in result.stderr
    assert (root / "srv").stat().st_mode & 0o777 == 0o777
    assert not (root / "cwd-owner-changed").exists()


def test_sealed_owner_workflow_prepares_empty_cwd_and_runs_original_chain(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_checkpoint_support import bootstrap_command

    root, package, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    command = bootstrap_command(root, package, tmp_path, owner_repair=True)
    first = run_bootstrap(command)
    assert first.returncode == 0, first.stderr.decode()
    assert first.stdout.count(b": OK") == 4
    assert first.stderr == b""
    assert (root / "cwd-owner-changed").is_file()
    assert (root / "srv/pi-cwd").stat().st_mode & 0o777 == 0o755
    assert (root / "usr/libexec/paperradar/live-evidence-owner").is_file()
    assert not (root / "var/lib/paperradar/live-evidence/cwd-created-by-beta").exists()
    assert run_bootstrap(command).returncode == 0
    from tests.site_deployment_support import run_script

    uninstall = root / "var/lib/paperradar/live-evidence-staging/uninstall.sh"
    assert run_script(uninstall).returncode == 0
    assert (root / "srv/pi-cwd").is_dir()


def test_explicit_owner_preparation_refuses_unexpected_mode(tmp_path: Path) -> None:
    from tests.site_deployment_checkpoint_support import cwd_preparation_command

    root, _, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    cwd = root / "srv/pi-cwd"
    cwd.chmod(0o750)
    result = run_bootstrap(cwd_preparation_command(root))
    assert result.returncode == 2
    assert b"[cwd_state_unexpected]" in result.stderr
    assert cwd.stat().st_mode & 0o777 == 0o750
    assert not (root / "cwd-owner-changed").exists()


def test_owner_preparation_preserves_member_racing_into_final_check(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_checkpoint_support import cwd_preparation_command

    root, _, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    command = cwd_preparation_command(root)
    retained = root / "srv/pi-cwd/retained"
    chown = root / "chown-model"
    chown.write_text(chown.read_text() + f'/usr/bin/printf retained > "{retained}"\n')
    result = run_bootstrap(command)
    assert result.returncode == 2
    assert b"[cwd_not_empty]" in result.stderr
    assert retained.read_bytes() == b"retained"
    assert (root / "cwd-owner-changed").is_file()
    assert not (root / "usr/libexec/paperradar").exists()


def test_sealed_owner_workflow_stops_before_deploy_if_cwd_nonempty(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_checkpoint_support import bootstrap_command

    root, package, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    retained = root / "srv/pi-cwd/retained"
    retained.write_bytes(b"user data")
    command = bootstrap_command(root, package, tmp_path, owner_repair=True)
    result = run_bootstrap(command)
    assert result.returncode == 2
    assert b"G2 stage=runtime_install" not in result.stdout
    assert b"[cwd_not_empty]" in result.stderr
    assert b"stage=owner_cwd_prepare" in result.stderr
    assert retained.read_bytes() == b"user data"
    assert not (root / "cwd-owner-changed").exists()
    assert not (root / "usr/libexec/paperradar").exists()


def test_pending_runtime_is_reported_and_preserved_after_three_sha_successes(
    tmp_path: Path,
) -> None:
    root, _, command = bootstrap_sandbox(tmp_path)
    pending = root / "usr/libexec/paperradar/live-evidence-runtime.new"
    pending.mkdir(parents=True)
    pending.parent.chmod(0o755)
    pending.chmod(0o755)
    retained = pending / "retained"
    retained.write_bytes(b"unknown deployment")
    result = run_bootstrap(command)
    assert result.returncode == 2
    assert result.stdout.count(b": OK") == 3
    assert b"[runtime_pending]" in result.stderr
    assert b"stage=runtime_install" in result.stderr
    assert retained.read_bytes() == b"unknown deployment"
    assert not pending.with_suffix("").exists()
    assert not (root / "var/lib/paperradar/live-evidence").exists()
