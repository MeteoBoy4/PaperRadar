"""单入口G2的/tmp shell模型;sudo替身只记录并以当前非特权uid执行。"""

import hashlib
import tarfile
from pathlib import Path

from paper_radar.live_evidence.deployment import file_digests, render_g2_runner
from tests.site_deployment_checkpoint_support import (
    bootstrap_sandbox,
    model_bootstrap,
    model_owner_workflow,
)


def g2_entry_sandbox(
    tmp_path: Path, *, initial_uid: int = 1000, collector_status: int = 0
) -> tuple[Path, Path, Path, Path]:
    root, package, _ = bootstrap_sandbox(tmp_path, cwd_uid=1000)
    payload = tmp_path / "payload"
    events = tmp_path / "events"
    (payload / "wrappers/collect").write_text(
        f'#!/bin/sh\n/usr/bin/printf "collect\\n" >> "{events}"\n'
        f"exit {collector_status}\n"
    )
    (payload / "wrappers/owner").write_text(
        f'#!/bin/sh\n/usr/bin/printf "%s\\n" "$*" >> "{events}"\n'
        '/usr/bin/printf "receipt_id=0123456789abcdef\\n"\n'
    )
    (payload / "manifest.sha256").unlink()
    (payload / "manifest.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in file_digests(payload).items())
    )
    old_digest = hashlib.sha256((package / "payload.tar").read_bytes()).hexdigest()
    with tarfile.open(package / "payload.tar", "w") as archive:
        archive.add(payload, arcname=".")
    new_digest = hashlib.sha256((package / "payload.tar").read_bytes()).hexdigest()
    deploy = package / "deploy.sh"
    deploy.write_text(deploy.read_text().replace(old_digest, new_digest))
    (package / "owner-workflow.sh").write_text(
        model_owner_workflow(root, initial_uid=initial_uid)
    )
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in package.iterdir()
    }
    runner = package / "run-g2.sh"
    source = model_bootstrap(render_g2_runner(hashes), root)
    sudo_log = tmp_path / "sudo-calls"
    sudo_tool = tmp_path / "sudo-model"
    sudo_tool.write_text(
        f'#!/bin/sh\n/usr/bin/printf "%s\\n" "$1" >> "{sudo_log}"\n'
        '[ "$1" = -k ] || exit 99\nshift\nexec "$@"\n'
    )
    sudo_tool.chmod(0o755)
    runner.write_text(source.replace("/usr/bin/sudo", str(sudo_tool)))
    runner.chmod(0o755)
    return root, runner, sudo_log, events
