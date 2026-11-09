"""真实封印bootstrap→deploy链的无root模型;仅替换宿主OS边界。"""

import hashlib
import subprocess
from pathlib import Path

from paper_radar.live_evidence.deployment import render_bootstrap, render_owner_workflow
from tests.site_deployment_support import deployment_sandbox


def bootstrap_sandbox(
    tmp_path: Path, *, cwd_uid: int = 0
) -> tuple[Path, Path, list[str]]:
    root, deploy, _ = deployment_sandbox(tmp_path)
    cwd = root / "srv/pi-cwd"
    cwd.mkdir(mode=0o700)
    # 不伪造属主保护结论;在OS边界提供该模型目录的固定uid。
    original = deploy.read_text()
    rewritten = original.replace(
        '        [ "0" -eq 0 ]',
        f'        [ "$(if [ "$current" = "{cwd}" ] && '
        f'[ ! -e "{root / "cwd-owner-changed"}" ]; '
        f'then /usr/bin/printf {cwd_uid}; else /usr/bin/printf 0; fi)" -eq 0 ]',
    )
    assert rewritten != original, "the OS uid model must be installed"
    deploy.write_text(rewritten)
    package = tmp_path / "review"
    package.mkdir()
    for name in ("deploy.sh", "uninstall.sh", "payload.tar"):
        (package / name).write_bytes(deploy.with_name(name).read_bytes())
    return root, package, bootstrap_command(root, package, tmp_path)


def bootstrap_command(
    root: Path, package: Path, tmp_path: Path, *, owner_repair: bool = False
) -> list[str]:
    if owner_repair:
        workflow = model_owner_workflow(root)
        (package / "owner-workflow.sh").write_text(workflow)
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in package.iterdir()
    }
    source = render_bootstrap(hashes, owner_workflow=owner_repair, progress=False)
    source = model_bootstrap(source, root)
    return ["/bin/sh", "-c", source, "sh", str(package)]


def model_bootstrap(source: str, root: Path) -> str:
    for prefix in ("/usr/libexec", "/var", "/etc/sudoers.d", "/srv"):
        source = source.replace(prefix, str(root) + prefix)
    source = source.replace('$(/usr/bin/stat -c %u "$path")', "0")
    source = source.replace('[ "$path" != / ]', f'[ "$path" != "{root}" ]')
    return source.replace(" -o root -g root", "")


def model_owner_workflow(root: Path, *, initial_uid: int = 1000) -> str:
    source = render_owner_workflow(1000, 1000)
    for prefix in ("/usr/libexec", "/var/lib", "/etc/sudoers.d", "/srv"):
        source = source.replace(prefix, str(root) + prefix)
    stat_tool, chown_tool = cwd_model_tools(root, initial_uid=initial_uid)
    source = source.replace("/usr/bin/stat", str(stat_tool))
    source = source.replace(
        '/usr/bin/chown root:root "$cwd"', f'{chown_tool} root:root "$cwd"'
    )
    source = source.replace("$(/usr/bin/id -u)", "0")
    return source.replace('[ "$current" != / ]', f'[ "$current" != "{root}" ]')


def run_bootstrap(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, capture_output=True, timeout=5, check=False)


def cwd_preparation_command(root: Path, *, initial_uid: int = 1000) -> list[str]:
    from paper_radar.live_evidence.deployment import render_cwd_preparation

    source = render_cwd_preparation(1000, 1000)
    source = source.replace("/srv", str(root) + "/srv")
    source = source.replace("$(/usr/bin/id -u)", "0")
    stat_tool, chown_tool = cwd_model_tools(root, initial_uid=initial_uid)
    source = source.replace("/usr/bin/stat", str(stat_tool))
    source = source.replace("/usr/bin/chown", str(chown_tool))
    source = source.replace('[ "$current" != / ]', f'[ "$current" != "{root}" ]')
    return ["/bin/sh", "-c", source]


def cwd_model_tools(root: Path, *, initial_uid: int = 1000) -> tuple[Path, Path]:
    cwd = root / "srv/pi-cwd"
    marker = root / "cwd-owner-changed"
    stat_tool = root / "stat-model"
    stat_tool.write_text(
        '#!/bin/sh\ncase "$2" in %u|%g)\n'
        f'  if [ "$3" = "{cwd}" ] && [ ! -e "{marker}" ]; then\n'
        f"    /usr/bin/printf {initial_uid}\n"
        "  else /usr/bin/printf 0; fi;;\n"
        '  *) exec /usr/bin/stat "$@";;\nesac\n'
    )
    stat_tool.chmod(0o755)
    chown_tool = root / "chown-model"
    chown_tool.write_text(f'#!/bin/sh\n/usr/bin/touch "{marker}"\n')
    chown_tool.chmod(0o755)
    return stat_tool, chown_tool
