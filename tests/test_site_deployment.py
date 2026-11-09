from datetime import timedelta
from pathlib import Path

from tests.live_evidence_ledger_support import NOW


def test_sudoers_only_exposes_zero_argument_collector_and_tightening() -> None:
    from paper_radar.live_evidence.deployment import render_sudoers

    policy = render_sudoers(1000)
    assert '/usr/libexec/paperradar/live-evidence-collect ""' in policy
    assert "/usr/libexec/paperradar/live-evidence-tighten *" in policy
    assert "owner" not in policy
    assert "receive" not in policy
    assert "activate" not in policy
    assert "SETENV" not in policy.replace("NOSETENV", "")


def test_deploy_and_uninstall_only_accept_fixed_sealed_location() -> None:
    from paper_radar.live_evidence.deployment import render_deploy, render_uninstall

    deploy = render_deploy("a" * 64)
    uninstall = render_uninstall()
    assert "a" * 64 in deploy
    assert "/usr/sbin/visudo -cf" in deploy
    assert "ledger.sqlite3" not in uninstall
    assert "rm -rf /var/lib/paperradar/live-evidence" not in uninstall
    assert '"$#" -eq 0' in deploy
    assert '"$#" -eq 0' in uninstall
    assert "/var/lib/paperradar/live-evidence-staging/deploy.sh" in deploy


def test_frozen_bundle_executes_with_empty_environment_and_has_no_links(
    tmp_path: Path,
) -> None:
    import subprocess
    import tarfile

    from paper_radar.live_evidence.deployment import build_deployment
    from paper_radar.live_evidence.receipt import ApprovedPlan
    from tests.site_collector_support import site_configuration

    output = tmp_path / "review"
    source_root = Path(__file__).resolve().parents[1]
    hashes = build_deployment(
        output,
        site_configuration(tmp_path),
        starts_at=NOW,
        ends_at=NOW + timedelta(days=7),
        source_root=source_root,
    )
    assert set(hashes) == {
        "payload.tar",
        "approved-plan.json",
        "site.json",
        "deploy.sh",
        "uninstall.sh",
        "REVIEW.md",
        "build-identity.json",
        "owner-workflow.sh",
        "run-g2.sh",
    }
    review = (output / "REVIEW.md").read_text()
    assert str(output / "run-g2.sh") in review
    assert "sudo -k" in (output / "run-g2.sh").read_text()
    assert hashes["deploy.sh"] in review
    assert hashes["uninstall.sh"] in review
    assert "sudo -k" in review
    plan = ApprovedPlan.model_validate_json(
        (output / "approved-plan.json").read_bytes()
    )
    assert plan.max_auth_calls == plan.max_model_calls == plan.max_network_requests == 0
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    with tarfile.open(output / "payload.tar") as archive:
        assert all(
            not member.issym()
            and not member.islnk()
            and not member.name.startswith("/")
            and ".." not in Path(member.name).parts
            for member in archive
        )
        archive.extractall(unpacked, filter="data")
    result = subprocess.run(
        [
            str(unpacked / "python/bin/python3"),
            "-I",
            "-S",
            "-B",
            str(unpacked / "entry.py"),
            "collect",
            "--forbidden",
        ],
        env={"PYTHONPATH": "/tmp/malicious", "PYTHONHOME": "/tmp/malicious"},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2, result.stderr.decode()
    assert result.stderr == b""
    for script in ("deploy.sh", "uninstall.sh"):
        syntax = subprocess.run(
            ["/bin/sh", "-n", str(output / script)], capture_output=True, check=False
        )
        assert syntax.returncode == 0, syntax.stderr.decode()
        # 非root/错误位置不得开始部署;不使用sudo。
        rejected = subprocess.run(
            ["/bin/sh", str(output / script), "--forbidden"],
            capture_output=True,
            check=False,
        )
        assert rejected.returncode == 2


def test_deploy_uninstall_and_restore_are_idempotent_in_rootless_model(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_support import deployment_sandbox, run_script

    root, deploy, uninstall = deployment_sandbox(tmp_path)
    first = run_script(deploy)
    assert first.returncode == 0, first.stderr.decode()
    ledger = root / "var/lib/paperradar/live-evidence"
    (ledger / "ledger.sqlite3").write_bytes(b"retained history")
    (ledger / "inbox/receipt.json").write_bytes(b"retained receipt")
    assert run_script(deploy).returncode == 0
    removed = run_script(uninstall)
    assert removed.returncode == 0, removed.stderr.decode()
    assert (ledger / "ledger.sqlite3").read_bytes() == b"retained history"
    assert (ledger / "inbox/receipt.json").read_bytes() == b"retained receipt"
    assert not (root / "etc/sudoers.d/paperradar-live-evidence").exists()
    assert not (root / "usr/libexec/paperradar/live-evidence-runtime").exists()
    assert not (root / "srv/pi-cwd").exists()
    assert run_script(uninstall).returncode == 0
    assert run_script(deploy).returncode == 0
    assert (ledger / "ledger.sqlite3").read_bytes() == b"retained history"


def test_tampered_package_stops_before_install(tmp_path: Path) -> None:
    from tests.site_deployment_support import deployment_sandbox, run_script

    root, deploy, _ = deployment_sandbox(tmp_path)
    deploy.with_name("payload.tar").write_bytes(b"not the approved artifact")
    assert run_script(deploy).returncode == 2
    assert not (root / "usr/libexec/paperradar").exists()


def test_deploy_refuses_symlink_target_and_leaves_destination_unchanged(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_support import deployment_sandbox, run_script

    root, deploy, _ = deployment_sandbox(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "usr/libexec/paperradar").symlink_to(outside, target_is_directory=True)
    assert run_script(deploy).returncode == 2
    assert not list(outside.iterdir())


def test_deploy_never_chowns_writable_existing_directory_into_trust(
    tmp_path: Path,
) -> None:
    from tests.site_deployment_support import deployment_sandbox, run_script

    root, deploy, _ = deployment_sandbox(tmp_path)
    target = root / "usr/libexec/paperradar"
    target.mkdir(mode=0o777)
    target.chmod(0o777)
    assert run_script(deploy).returncode == 2
    assert target.stat().st_mode & 0o777 == 0o777


def test_sealing_help_has_no_site_or_database_dependency() -> None:
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts/seal_site_evidence.py"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(script), "--help"],
        env={},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "不执行部署" in result.stdout.decode()
    assert result.stderr == b""
