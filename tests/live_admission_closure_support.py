"""单次owner收口包的无root OS边界模型,不执行真实sudo。"""

import hashlib
from pathlib import Path

from scripts.issue176_closure import build_bundle


def bundle_model(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    host = tmp_path / "host"
    runtime = host / "usr/libexec/paperradar/live-evidence-runtime"
    (runtime / "wrappers").mkdir(parents=True)
    (runtime / "python/bin").mkdir(parents=True)
    (host / "var/lib/paperradar/live-evidence").mkdir(parents=True)
    (host / "etc/sudoers.d").mkdir(parents=True)
    host.chmod(0o755)
    events = tmp_path / "executions"
    for action in ("collect", "owner", "tighten"):
        data = b"#!/bin/sh\nexit 0\n"
        (runtime / "wrappers" / action).write_bytes(data)
        (runtime.parent / f"live-evidence-{action}").write_bytes(data)
        (runtime.parent / f"live-evidence-{action}").chmod(0o755)
    (runtime / "python/bin/python3").write_text(
        f'#!/bin/sh\n/usr/bin/printf executed > "{events}"\n'
    )
    (runtime / "sudoers").write_bytes(b"# offline-model\n")
    policy = host / "etc/sudoers.d/paperradar-live-evidence"
    policy.write_bytes((runtime / "sudoers").read_bytes())
    (runtime / "manifest.sha256").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
            f"{path.relative_to(runtime)}\n"
            for path in sorted(runtime.rglob("*"))
            if path.is_file()
        )
    )
    manifest = hashlib.sha256((runtime / "manifest.sha256").read_bytes()).hexdigest()
    (runtime / "payload.sha256").write_text("a" * 64 + "\n")
    for path in host.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    policy.chmod(0o440)
    (runtime / "python/bin/python3").chmod(0o755)
    for action in ("collect", "owner", "tighten"):
        (runtime.parent / f"live-evidence-{action}").chmod(0o755)
    output = tmp_path / "bundle"
    build_bundle(
        output,
        payload_sha256="a" * 64,
        manifest_sha256=manifest,
        receipt_id="0123456789abcdef",
    )
    source = (output / "run-owner.sh").read_text()
    for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d"):
        source = source.replace(prefix, str(host) + prefix)
    source = source.replace("$(/usr/bin/id -u)", "0")
    source = source.replace('$(/usr/bin/stat -c %u "$current")', "0")
    source = source.replace('[ "$current" != / ]', f'[ "$current" != "{host}" ]')
    source = source.replace(" -o root -g root", "")
    sudo = tmp_path / "sudo-model"
    sudo.write_text('#!/bin/sh\n[ "$1" = -k ] || exit 2\nshift\nexec "$@"\n')
    sudo.chmod(0o755)
    source = source.replace("/usr/bin/sudo", str(sudo))
    runner = output / "run-owner.sh"
    runner.write_text(source)
    return runtime, runner, events, sudo
