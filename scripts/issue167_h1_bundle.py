"""离线生成H1首轮审阅包;不执行systemd/root/网络/认证/Pi。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def safe_path(path: Path) -> Path:
    resolved = path.resolve()
    if re.fullmatch(r"/[A-Za-z0-9_./-]+", str(resolved)) is None:
        raise ValueError("review_path_invalid")
    return resolved


def create_bundle(
    destination: Path, *, python: Path, uid: int, unit_name: str | None = None
) -> Path:
    destination = safe_path(destination)
    python = safe_path(python)
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError("python_source_invalid")
    if type(uid) is not int or uid <= 0 or uid != os.getuid():
        raise ValueError("nonroot_uid_required")
    if not any(destination.is_relative_to(root) for root in ("/home", "/tmp")):
        raise ValueError("bundle_must_be_nonpackaged_path")
    if (
        unit_name is not None
        and re.fullmatch(r"paperradar-167-preflight-[a-f0-9]{12}\.service", unit_name)
        is None
    ):
        raise ValueError("unit_name_invalid")
    # 新包排他创建,不能覆写旧包/旧回执或借新名清空授权余额。
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    python_copy = destination / "synthetic-python"
    shutil.copyfile(python, python_copy)
    python_copy.chmod(0o700)
    python = python_copy
    results = destination / "results"
    results.mkdir(mode=0o700)
    worker = destination / "worker.py"
    worker.write_bytes((PROJECT / "scripts/issue167_h1_worker.py").read_bytes())
    suffix = hashlib.sha256(str(destination).encode()).hexdigest()[:12]
    unit = unit_name or f"paperradar-167-preflight-{suffix}.service"
    # 首轮不创建mount namespace,保留Apport第三路所检验的namespace条件。
    body = f"""[Unit]
Description=PaperRadar issue 167 synthetic preflight only
[Service]
Type=oneshot
User={uid}
WorkingDirectory=/srv/pi-cwd
ExecStart={python} -I -S -B {worker} --expected-uid {uid} {results / "receipt.json"}
Restart=no
KillMode=control-group
SendSIGKILL=yes
TimeoutStartSec=20s
TimeoutStopSec=5s
LimitCORE=0
NoNewPrivileges=yes
Delegate=no
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=none
IPAddressDeny=any
SocketBindDeny=any
RestrictNamespaces=yes
RestrictRealtime=yes
LockPersonality=yes
StandardOutput=null
StandardError=null
"""
    (destination / unit).write_text(body)
    unit_sha = hashlib.sha256(body.encode()).hexdigest()
    review = f"""# H1首轮:无认证服务预检

本包只供所有者审阅,不自动安装/启动/授权。unit={unit}, uid={uid}。
仅检查service/合成后代core限额、NoNewPrivs和五类socket创建被拒绝。
不调用Pi/Node/认证、不创建连接或做DNS、不会crash、不读凭据或core。
不修改core_pattern、Apport、nft、安装树或产品启动身份。
不启用timer/socket/开机自启。首轮不配置mount namespace,避免把Apport早退当限额证明。

不证明:端点允许正对照、真实TCP/TLS/DNS、精确主机出站、任意后代逃逸、文件白名单、
模型/凭据/参数能力、产品read_evidence。
后续nft phase/真实供给仍另审H1/H2,不得从本轮放行。
仅复制当前Python字节到包内作为合成worker解释器,不改系统Python/固定安装或生产入口。
源码/配置/解释器副本哈希在manifest.json。执行前应确认/srv/pi-cwd仍是原真实空目录,无symlink,
且同名unit不存在;不更改已有cwd权限、不覆盖任何现有unit。

所有者执行前须先明确批准此包。命令只展示在owner-wizard.sh,向导自身不执行root动作。
首轮安装:{destination / unit} -> /etc/systemd/system/{unit}。
运行结果仅写{results / "receipt.json"},已有回执拒绝覆写,失败不自动重跑。
恢复:先stop,核对unit inactive与ControlGroup为空（必要时以可信cgroup事实独立复核）,再删除
本包唯一新增unit文件并daemon-reload;不按前缀删文件/杀进程。保留原失败回执。
若收尾/cgroup事实未知,停止后续轮次,不能只以ControlGroup空字符串证明任意后代已退出。
服务源码以uid={uid}运行,不设置新uid/凭据、不chown业务/安装树。
"""
    (destination / "review.md").write_text(review)
    template = (PROJECT / ".agents/skills/wizard/template.sh").read_text()
    marker = "# STAGES: author this section."
    library = template[: template.index(marker)]
    stages = f"""# STAGES: owner-only commands, never executed by this wizard.
run_wizard() {{
TOTAL_STAGES=4
stage "核对包与授权"
say "先阅读 review.md、manifest.json、unit与worker.py。未明确批准此H1包时不要继续。"
step "确认同名unit不存在、/srv/pi-cwd仍为空且无链接;不要修改原cwd权限。"
say "cd -- {destination} && sha256sum -c members.sha256"
say "test ! -e /etc/systemd/system/{unit} && test ! -L /etc/systemd/system/{unit}"
say "systemctl show {unit} --property=LoadState,FragmentPath,DropInPaths"
step "LoadState须为not-found,FragmentPath与DropInPaths须为空,否则停止且不得覆盖。"
confirm "已审阅并获本轮H1明确批准?" || return 1
stage "所有者安装并启动"
step "在另一个终端由你执行:"
say "sudo systemd-analyze verify {destination / unit}"
say "sudo install -m 0644 -- {destination / unit} /etc/systemd/system/{unit}"
say "sudo systemctl daemon-reload"
say "sudo systemctl start {unit}"
pause "完成后按Enter;失败也不自动重试。"
stage "只核对安全元数据"
say "systemctl show {unit} \
--property=ActiveState,SubState,Result,ControlGroup,LimitCORE,LimitCORESoft"
say "查看 {results / "receipt.json"} 的受控字段;它不是产品准入。"
pause "保留结果,失败保留unknown后停止后续轮次。"
stage "停止与卸载恢复"
say "sudo systemctl stop {unit}"
say "先核对inactive与cgroup为空/后代回收,确认唯一新增unit未被其他配置替换。"
say "sha256sum /etc/systemd/system/{unit}"
say "删除前SHA必须仍为 {unit_sha}"
confirm "已核对回收与精确归属,允许你手动删除本unit?" || return 1
say "sudo rm -- /etc/systemd/system/{unit}"
say "sudo systemctl daemon-reload"
pause "所有者完成恢复后按Enter。"
say "向导只展示步骤,未替你执行sudo。保留回执并告知agent复核。"
}}
run_wizard "$@"; exit
"""
    wizard = destination / "owner-wizard.sh"
    wizard.write_text(library + stages)
    wizard.chmod(0o700)
    members = [path for path in destination.iterdir() if path.is_file()]
    (destination / "members.sha256").write_text(
        "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
            for p in sorted(members)
        )
    )
    members.append(destination / "members.sha256")
    manifest = {
        "scope": "h1_synthetic_preflight_review_only",
        "authorization": "not_granted",
        "unit": unit,
        "uid": uid,
        "members": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in members
        },
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成H1无认证审阅包,不执行宿主操作")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--unit-name")
    args = parser.parse_args()
    print(
        create_bundle(
            args.destination,
            python=Path(sys.executable),
            uid=os.getuid(),
            unit_name=args.unit_name,
        )
    )
