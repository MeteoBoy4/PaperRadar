"""已审阅旧runtime的保留式升级,无root模型。"""

import hashlib
from pathlib import Path

import pytest

from tests.site_deployment_support import (
    deployment_sandbox,
    model_intent_preflight,
    run_script,
)


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "payload",
        "payload_format",
        "manifest",
        "source",
        "entry",
        "archive",
        "symlink",
        "extra_file",
        "extra_directory",
        "hardlink",
        "entry_hardlink",
        "policy",
        "member_writable",
        "runtime_new",
        "archive_symlink",
        "member_special_mode",
        "entry_special_mode",
        "policy_mode",
        "cwd_nonempty",
    ],
)
def test_upgrade_only_archives_the_exact_protected_old_runtime(
    tmp_path: Path, change: str
) -> None:
    from paper_radar.live_evidence.deployment import render_upgrade

    root, deploy, _ = deployment_sandbox(tmp_path)
    assert run_script(deploy).returncode == 0
    runtime = root / "usr/libexec/paperradar/live-evidence-runtime"
    old_payload = (runtime / "payload.sha256").read_text().strip()
    old_manifest = hashlib.sha256(
        (runtime / "manifest.sha256").read_bytes()
    ).hexdigest()
    archive = runtime.with_name(runtime.name + ".archive-" + old_payload)
    ledger = root / "var/lib/paperradar/live-evidence"
    (ledger / "ledger.sqlite3").write_bytes(b"history, revocations and budgets")
    if change == "payload":
        (runtime / "payload.sha256").write_text("0" * 64)
    if change == "payload_format":
        (runtime / "payload.sha256").write_text(old_payload + "\n\n")
    if change == "manifest":
        (runtime / "manifest.sha256").write_text("tampered")
    if change == "source":
        (runtime / "wrappers/collect").write_text("changed")
    if change == "entry":
        (runtime.parent / "live-evidence-owner").write_text("changed")
    if change == "archive":
        archive.mkdir()
    if change == "symlink":
        (runtime / "extra").symlink_to(tmp_path)
    if change == "extra_file":
        (runtime / "extra").write_text("unreviewed")
    if change == "extra_directory":
        (runtime / "extra").mkdir()
    if change == "hardlink":
        (tmp_path / "linked").hardlink_to(runtime / "wrappers/collect")
    if change == "entry_hardlink":
        (tmp_path / "linked").hardlink_to(runtime.parent / "live-evidence-owner")
    if change == "policy":
        policy = root / "etc/sudoers.d/paperradar-live-evidence"
        policy.chmod(0o644)
        policy.write_text("changed")
        policy.chmod(0o440)
    if change == "member_writable":
        (runtime / "wrappers/collect").chmod(0o666)
    if change == "runtime_new":
        runtime.with_name(runtime.name + ".new").mkdir()
    if change == "archive_symlink":
        archive.symlink_to(tmp_path)
    if change == "member_special_mode":
        (runtime / "wrappers/collect").chmod(0o4755)
    if change == "entry_special_mode":
        (runtime.parent / "live-evidence-owner").chmod(0o4755)
    if change == "policy_mode":
        (root / "etc/sudoers.d/paperradar-live-evidence").chmod(0o644)
    if change == "cwd_nonempty":
        (root / "srv/pi-cwd/retained").write_bytes(b"user data")
    source = model_intent_preflight(render_upgrade(old_payload, old_manifest))
    for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d", "/srv"):
        source = source.replace(prefix, str(root) + prefix)
    source = source.replace("$(/usr/bin/id -u)", "0")
    source = source.replace('$(/usr/bin/stat -c %u "$current")', "0")
    source = source.replace('[ "$current" != / ]', f'[ "$current" != "{root}" ]')
    script = deploy.with_name("upgrade.sh")
    script.write_text(source)
    script.chmod(0o644)
    result = run_script(script)
    assert result.returncode == (0 if change == "none" else 2), result.stderr.decode()
    assert (
        ledger / "ledger.sqlite3"
    ).read_bytes() == b"history, revocations and budgets"
    if change in {"none", "source_after_password"}:
        assert (archive / "manifest.sha256").is_file()
        assert runtime.is_dir()
    else:
        assert runtime.is_dir()
        expected = {
            "payload": "old_payload_identity",
            "payload_format": "old_payload_identity",
            "manifest": "old_manifest_identity",
            "source": "old_runtime_integrity",
            "entry": "entry_conflict",
            "archive": "archive_exists",
            "symlink": "old_runtime_node",
            "extra_file": "old_runtime_members",
            "extra_directory": "old_runtime_members",
            "hardlink": "old_runtime_hardlink",
            "entry_hardlink": "entry_type",
            "policy": "policy_conflict",
            "member_writable": "protected_mode",
            "runtime_new": "runtime_pending",
            "archive_symlink": "archive_exists",
            "member_special_mode": "old_runtime_mode",
            "entry_special_mode": "entry_mode",
            "policy_mode": "policy_mode",
            "cwd_nonempty": "cwd_not_empty",
        }
        assert f"[{expected[change]}]" in result.stderr.decode()
        if change not in {"archive", "archive_symlink"}:
            assert not archive.exists()


def test_upgrade_bundle_binds_old_identity_and_publishes_one_reviewed_entry(
    tmp_path: Path,
) -> None:
    import json
    import subprocess
    from datetime import timedelta

    from paper_radar.live_evidence.deployment import build_deployment
    from tests.live_evidence_ledger_support import NOW
    from tests.site_collector_support import site_configuration

    target = tmp_path / "review"
    hashes = build_deployment(
        target,
        site_configuration(tmp_path),
        starts_at=NOW,
        ends_at=NOW + timedelta(days=7),
        source_root=Path(__file__).resolve().parents[1],
        upgrade_from=("a" * 64, "b" * 64),
    )
    assert "run-upgrade.sh" in hashes and "upgrade.sh" in hashes
    assert "run-g2.sh" not in hashes
    runner = (target / "run-upgrade.sh").read_text()
    assert runner.count("/usr/bin/sudo ") == 1
    assert " activate " not in runner and " read " not in runner
    for name in ("upgrade.sh", "deploy.sh", "payload.tar"):
        assert hashes[name] in runner
    assert "exec /bin/sh" in runner and "upgrade.sh" in runner
    identity = json.loads((target / "build-identity.json").read_bytes())
    assert identity["upgrade_from"] == {
        "payload_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
    }
    review = (target / "REVIEW.md").read_text()
    assert str(target / "run-upgrade.sh") in review
    assert "G3仍由所有者另行执行" in review
    assert "a" * 64 in review and "b" * 64 in review
    for name in ("run-upgrade.sh", "upgrade.sh", "deploy.sh"):
        result = subprocess.run(
            ["/bin/sh", "-n", str(target / name)], capture_output=True, check=False
        )
        assert result.returncode == 0, result.stderr.decode()


@pytest.mark.parametrize(
    "change",
    ["none", "user_tamper", "source_after_password", "old_changed", "collector_failed"],
)
def test_one_upgrade_entry_checks_copies_archives_deploys_and_never_activates(
    tmp_path: Path, change: str
) -> None:
    import tarfile

    from paper_radar.live_evidence.deployment import (
        file_digests,
        render_g2_runner,
        render_upgrade,
    )
    from tests.site_deployment_checkpoint_support import model_bootstrap, run_bootstrap
    from tests.site_g2_entry_support import g2_entry_sandbox

    root, old_runner, sudo_log, events = g2_entry_sandbox(tmp_path)
    first = run_bootstrap([str(old_runner)])
    assert first.returncode == 0, first.stderr.decode()
    runtime = root / "usr/libexec/paperradar/live-evidence-runtime"
    old_digest = (runtime / "payload.sha256").read_text().strip()
    old_manifest = hashlib.sha256(
        (runtime / "manifest.sha256").read_bytes()
    ).hexdigest()
    archive = runtime.with_name(runtime.name + ".archive-" + old_digest)
    ledger = root / "var/lib/paperradar/live-evidence"
    retained = {
        "ledger.sqlite3": b"revocation and budget history",
        "inbox/old.json": b"old receipt, original verification time",
        "old-plan.stopped": b"stopped forever",
        "collector-history.jsonl": b"old failure history",
    }
    for name, data in retained.items():
        (ledger / name).write_bytes(data)
    events.unlink()
    sudo_log.unlink()
    payload = tmp_path / "payload"
    (payload / "wrappers/collect").write_text(
        f'#!/bin/sh\n/usr/bin/printf "new-collect\\n" >> "{events}"\n'
        f"exit {2 if change == 'collector_failed' else 0}\n"
    )
    (payload / "wrappers/owner").write_text(
        '#!/bin/sh\n[ "$1" != provision-intents ] || exit 0\n'
        f'/usr/bin/printf "%s\\n" "$*" >> "{events}"\n'
        '/usr/bin/printf "receipt_id=fedcba9876543210\\n"\n'
    )
    (payload / "manifest.sha256").unlink()
    (payload / "manifest.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in file_digests(payload).items())
    )
    package = old_runner.parent
    with tarfile.open(package / "payload.tar", "w") as tar:
        tar.add(payload, arcname=".")
    new_digest = hashlib.sha256((package / "payload.tar").read_bytes()).hexdigest()
    assert new_digest != old_digest
    deploy = package / "deploy.sh"
    deploy.write_text(deploy.read_text().replace(old_digest, new_digest))
    upgrade = model_intent_preflight(render_upgrade(old_digest, old_manifest))
    for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d", "/srv"):
        upgrade = upgrade.replace(prefix, str(root) + prefix)
    upgrade = upgrade.replace("$(/usr/bin/id -u)", "0")
    upgrade = upgrade.replace('$(/usr/bin/stat -c %u "$current")', "0")
    upgrade = upgrade.replace('[ "$current" != / ]', f'[ "$current" != "{root}" ]')
    (package / "upgrade.sh").write_text(upgrade)
    (package / "upgrade.sh").chmod(0o644)
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in package.iterdir()
    }
    runner_source = model_bootstrap(
        render_g2_runner(
            hashes,
            sealed_files={p.name: p.read_bytes() for p in package.iterdir()},
            upgrade=True,
        ),
        root,
    )
    runner = package / "run-upgrade.sh"
    runner.write_text(
        runner_source.replace("/usr/bin/sudo", str(tmp_path / "sudo-model"))
    )
    runner.chmod(0o755)
    if change == "user_tamper":
        (package / "upgrade.sh").write_text("tampered\n")
    if change == "source_after_password":
        sudo_tool = tmp_path / "sudo-model"
        sudo_tool.write_text(
            sudo_tool.read_text().replace(
                'exec "$@"',
                f'/usr/bin/printf tampered > "{package / "upgrade.sh"}"\nexec "$@"',
            )
        )
    if change == "old_changed":
        (runtime / "wrappers/collect").write_text("changed\n")
    result = run_bootstrap([str(runner)])
    for name, data in retained.items():
        assert (ledger / name).read_bytes() == data
    if change == "user_tamper":
        assert result.returncode != 0 and not sudo_log.exists()
    else:
        assert sudo_log.read_text() == "-k\n"
    if change in {"none", "source_after_password", "collector_failed"}:
        assert archive.is_dir() and runtime.is_dir()
        assert (runtime / "payload.sha256").read_text().strip() == new_digest
        assert events.read_text().splitlines()[0] == "new-collect"
        if change in {"none", "source_after_password"}:
            assert result.returncode == 0, result.stderr.decode()
            assert events.read_text().splitlines()[1].startswith("receive --plan ")
            assert len(events.read_text().splitlines()) == 2
            assert b"receipt_id=fedcba9876543210" in result.stdout
            assert "G3证据激活未执行" in result.stdout.decode()
            if change == "source_after_password":
                (package / "upgrade.sh").write_text(upgrade)
            second = run_bootstrap([str(runner)])
            assert second.returncode == 2
            assert b"[old_payload_identity]" in second.stderr
            assert len(events.read_text().splitlines()) == 2
        else:
            assert result.returncode == 2
            assert events.read_text() == "new-collect\n"
            assert "封印升级完成" not in result.stdout.decode()
    else:
        assert result.returncode != 0 and not archive.exists() and not events.exists()


def test_upgrade_requires_both_old_digests_before_reading_site(tmp_path: Path) -> None:
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts/seal_site_evidence.py"
    output = tmp_path / "review"
    result = subprocess.run(
        [
            str(Path(sys.executable)),
            "-I",
            "-S",
            "-B",
            str(script),
            "--site",
            str(tmp_path / "unread-site.json"),
            "--starts-at",
            "2026-11-09T03:57:37+00:00",
            "--ends-at",
            "2026-11-16T03:57:37+00:00",
            "--output",
            str(output),
            "--upgrade-from-payload",
            "a" * 64,
        ],
        env={},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "升级必须同时提供旧payload与manifest SHA256" in result.stderr.decode()
    assert not output.exists()
