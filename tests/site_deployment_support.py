"""封印脚本的无root文件系统模型;不构成真实OS权限证明。"""

import hashlib
import subprocess
import tarfile
from pathlib import Path

from paper_radar.live_evidence.deployment import (
    file_digests,
    render_deploy,
    render_uninstall,
)


def deployment_sandbox(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "host"
    root.mkdir(mode=0o755)
    for name in (
        "usr/libexec",
        "var/lib/paperradar/live-evidence-staging",
        "etc/sudoers.d",
        "srv",
    ):
        (root / name).mkdir(parents=True, mode=0o755)
    staging = root / "var/lib/paperradar/live-evidence-staging"
    payload = tmp_path / "payload"
    (payload / "wrappers").mkdir(parents=True, mode=0o755)
    for name in ("collect", "tighten", "owner"):
        (payload / "wrappers" / name).write_text("#!/bin/sh\nexit 0\n")
    (payload / "sudoers").write_text("# synthetic-only\n")
    (payload / "manifest.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in file_digests(payload).items())
    )
    with tarfile.open(staging / "payload.tar", "w") as archive:
        archive.add(payload, arcname=".")
    digest = hashlib.sha256((staging / "payload.tar").read_bytes()).hexdigest()
    for name, source in (
        ("deploy", render_deploy(digest)),
        ("uninstall", render_uninstall()),
    ):
        for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d", "/srv"):
            source = source.replace(prefix, str(root) + prefix)
        source = source.replace("$(/usr/bin/id -u)", "0")
        source = source.replace('$(/usr/bin/stat -c %u "$current")', "0")
        source = source.replace('[ "$current" != / ]', f'[ "$current" != "{root}" ]')
        source = source.replace(" -o root -g root", "")
        source = source.replace("/usr/bin/chown", "/usr/bin/true")
        source = source.replace("/usr/sbin/visudo", "/usr/bin/true")
        (staging / f"{name}.sh").write_text(source)
    for path in root.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    return root, staging / "deploy.sh", staging / "uninstall.sh"


def run_script(script: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["/bin/sh", str(script)], capture_output=True, check=False)
