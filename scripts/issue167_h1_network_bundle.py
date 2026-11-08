"""Build a sealed H1 synthetic-local review package; never deploy or connect."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from scripts.issue167_h1_phase import Plan, render_create, render_delete, render_phase

PROJECT = Path(__file__).resolve().parents[1]
SOURCES = {
    "issue167_h1_phase.py": "scripts/issue167_h1_phase.py",
    "issue167_h1_guardian.py": "scripts/issue167_h1_guardian.py",
    "issue167_h1_network_worker.py": "scripts/issue167_h1_network_worker.py",
    "issue167_h1_owner_ops.py": "scripts/issue167_h1_owner_ops.py",
    "issue167_observation.py": "scripts/issue167_observation.py",
    "production_isolation.py": "src/paper_radar/pi_execution/isolation.py",
    "production_errors.py": "src/paper_radar/pi_execution/errors.py",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def units(plan: Plan) -> dict[str, str]:
    ipv4_only = plan.network_mode == "ipv4_only"
    ip_allow = "127.0.0.1/32" if ipv4_only else "127.0.0.1/32 ::1/128"
    worker_families = "AF_INET" if ipv4_only else "AF_INET AF_INET6"
    guardian_families = (
        "AF_UNIX AF_NETLINK AF_INET"
        if ipv4_only
        else "AF_UNIX AF_NETLINK AF_INET AF_INET6"
    )
    common = f"""Restart=no
NoNewPrivileges=yes
Delegate=no
RestrictNamespaces=yes
RestrictRealtime=yes
SystemCallArchitectures=native
SystemCallFilter=~bpf io_uring_setup:EPERM io_uring_enter:EPERM io_uring_register:EPERM
KillMode=control-group
SendSIGKILL=yes
TimeoutStopSec=15s
LimitCORE=0
UMask=0077
IPAddressDeny=any
IPAddressAllow={ip_allow}
StandardOutput=null
StandardError=null
"""
    start = f"{plan.install_root}/synthetic-python -I -S -B"
    worker_command = (
        f"{start} {plan.install_root}/issue167_h1_network_worker.py "
        f"--plan {plan.install_root}/plan.json --worker"
    )
    guardian_command = (
        f"{start} {plan.install_root}/issue167_h1_guardian.py "
        f"--plan {plan.install_root}/plan.json"
    )
    worker = f"""[Unit]
Description=PaperRadar 167 synthetic loopback worker
BindsTo={plan.guardian_unit}
After={plan.guardian_unit}
[Service]
Type=exec
User={plan.uid}
Group={plan.gid}
WorkingDirectory=/srv/pi-cwd
ExecStart={worker_command}
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies={worker_families}
RuntimeMaxSec=120s
TimeoutStartSec=15s
{common}"""
    # System service defaults to UID 0. Explicit User=root triggers v259
    # seccomp privilege handling that drops SETUID before exec with empty ambient.
    guardian_caps = (
        "CAP_NET_ADMIN CAP_SETUID CAP_SETGID CAP_KILL CAP_CHOWN CAP_DAC_READ_SEARCH"
    )
    guardian = f"""[Unit]
Description=PaperRadar 167 bounded synthetic guardian
[Service]
Type=simple
Group=root
WorkingDirectory={plan.install_root}
ExecStart={guardian_command}
CapabilityBoundingSet={guardian_caps}
AmbientCapabilities=
RestrictAddressFamilies={guardian_families}
RuntimeMaxSec=180s
TimeoutStartSec=15s
{common}"""
    return {plan.unit: worker, plan.guardian_unit: guardian}


def create_bundle(destination: Path, plan: Plan, *, python: Path | None = None) -> Path:
    destination = destination.resolve()
    if re.fullmatch(r"/[A-Za-z0-9_./-]+", str(destination)) is None:
        raise ValueError("review_path_invalid")
    if plan.uid != os.getuid() or plan.gid != os.getgid():
        raise ValueError("review_identity_changed")
    # A new review ID never grants an execution allowance.
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    (destination / "results").mkdir(mode=0o700)
    for name, source in SOURCES.items():
        shutil.copyfile(PROJECT / source, destination / name)
    interpreter = (python or Path(sys.executable)).resolve(strict=True)
    shutil.copyfile(interpreter, destination / "synthetic-python")
    (destination / "synthetic-python").chmod(0o755)
    (destination / "plan.json").write_text(plan.to_json())
    uname = os.uname()
    context = {
        "kernel": uname.release,
        "machine": uname.machine,
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "hostname_sha256": hashlib.sha256(uname.nodename.encode("utf-8")).hexdigest(),
    }
    (destination / "host-context.json").write_text(
        json.dumps(context, sort_keys=True) + "\n"
    )
    for name, body in units(plan).items():
        (destination / name).write_text(body)
    for name, body in {
        "create.nft": render_create(plan),
        "phase-a.nft": render_phase(plan, "a"),
        "phase-b.nft": render_phase(plan, "b"),
        "delete.nft": render_delete(plan),
    }.items():
        (destination / name).write_text(body)
    tools = {
        "python": {
            "path": str(plan.install_root / "synthetic-python"),
            "sha256": digest(destination / "synthetic-python"),
        }
    }
    for name, path in (
        ("nft", Path("/usr/sbin/nft")),
        ("systemctl", Path("/usr/bin/systemctl")),
    ):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError("host_tool_missing")
        tools[name] = {"path": str(path), "sha256": digest(path)}
    network_review = f"""仅127.0.0.1与::1,端口A={plan.port_a}、
B={plan.port_b}、blocked={plan.blocked_port}。每阶段最多10次本机连接/单字节发送尝试:
v4/v6当前TCP正例,另一phase/blocked TCP、blocked UDP与UDP53负例。合计最多20次;
本地peer仅固定OK,不读取客户端内容;不解析DNS或发外部请求。UDP53只发合成字节,
不能叫做真实DNS来源验证。IPv6不可用/端口占用/元数据不完整立即unknown,不换目标。
"""
    if plan.network_mode == "ipv4_only":
        network_review = f"""network_mode=ipv4_only,只允许127.0.0.1;
端口A={plan.port_a}、
B={plan.port_b}、blocked={plan.blocked_port}。每阶段先做2次AF_INET6 TCP/UDP socket
创建拒绝检查,只创建/关闭,绝不connect/send;成功创建、timeout或其他不明错误立即unknown。
仅EPERM/EACCES或EAFNOSUPPORT/EPROTONOSUPPORT进入明确拒绝/不可用类别。
随后5次IPv4连接/发送:当前TCP正例、另一phase/blocked TCP、blocked UDP和UDP53负例。
两阶段最多10次IPv4连接/固定单字节发送,另最多4次IPv6创建检查(零报文)。
worker RestrictAddressFamilies=AF_INET,guardian仅AF_UNIX AF_NETLINK AF_INET;
IPAddressAllow仅127.0.0.1/32,peer只建立两个IPv4 TCP listener,nft无IPv6 allow规则。
IPv6不要求双栈可用,但旧IPv6 timeout不改为denied;不把创建检查当packet/HTTP计数。
本地peer仅固定OK,不读客户端内容,不解析DNS或发外部请求;UDP53仅固定字节,
不代表真实DNS验证。IPv4 timeout/端口占用/任何边界或元数据不明仍unknown并停止。
"""
    review = f"""# H1/H3无凭据合成包:待所有者审批,不是生产准入

run_id={plan.run_id}; uid/gid={plan.uid}/{plan.gid}
worker={plan.unit}; guardian={plan.guardian_unit}
nft table=inet {plan.table}; cgroup={plan.cgroup} (level 2)
root-owned code={plan.install_root}
guardian不显式设置User=,采用system service默认UID0,Group=root不变。
这是为避开systemd259.5在显式UID+seccomp+空Ambient时撤CAP_SETUID的源码路径;
不增加Ambient、不移除NNP/seccomp、不改变6项声明cap或实际UID/cap核验。
缺省登录环境变量的设置会随之变化,不能声称所有环境完全等价;当前程序使用绝对路径,
子进程env明确设置,不依赖HOME/LOGNAME/SHELL。此为源码预测,须本次现场验证,不是已通过。
runtime={plan.runtime_root}
永久单次记录=/var/lib/paperradar/probe-runs/issue167-{plan.run_id}.json

本包与H1-0不同,须新H1/H3具体批准后才由所有者执行root步骤。审批须绑定本manifest
完整SHA与全部代码/规则/单元字节。包内authorization=not_granted不能自证许可。改ID/端口/
代码不能自动追加预算。已有case锚点/目录/同名unit/表或配置冲突一律拒绝,不覆盖、不重试。

范围:单worker直接fork,root guardian外部串行切本包独占nft phase;保留原拓扑,无Delegate、
跨unit token/OFD桥、loader或生产启动身份改动。{network_review}

ready前用复制的生产Boundary源码进行合成文件正负例、短暂创建删除的inotify历史、清理前
终态集合与删除独立事实;Pythonstdlib额外读授权只是合成fixture,不扩大生产Node白名单。
B后故意留下不同session的固定子进程,guardian必须拒再切phase,stop整unit,确认递归cgroup
空后才验表并撤规则;创建不明/表漂移保留,不能先卸规则留下活进程。guardian失败通过BindsTo
停止worker。counter只是该窗口aggregate packet下界/参照,不是HTTP次数或每次调用精确因果。

root权限:两个具体unit的安装/停止/卸载、唯一inet table及本包phase、精确runtime/code目录,
以及永久root单次记录。guard cap为NET_ADMIN/SETUID/SETGID/KILL/CHOWN/DAC_READ_SEARCH;
代码root-owned不可普通用户写,先验manifest/工具/host后才导入同目录模块。不读凭据、
业务DB、真实文件/进程内存、core/report、environ或完整外部流;不运行Pi/Node/模型或崩溃。
不修改core_pattern、Apport/whoopsie、系统DNS/代理、其他表或服务;不用mount namespace
硬化改变所依赖的Apport路径。root/普通用户当前core限额均由服务LimitCORE=0设置。

安装仅复制到本包root-owned/home根,不存在时才创建;不要把workspace脚本直接sudo运行。
先复核源/已安装manifest SHA均等审批消息,root-installed helper install只装unit,不启动。
启动按guardian→worker,不额外start/restart。Case失败/未知不退款,永久记录保留。

恢复先核对unit字节/manager/drop-in,停止两个精确unit、确认两个递归cgroup都空,再验表删除。
单位/表归属未知不自动作用于陌生对象,保留元数据/规则供所有者处理。restore保留runtime/code
与永久记录;仅成功且ledger与root结果一致、unit/table已消失、无额外挂载时finish才移除本包
runtime/code,永久单次记录及项目公共空父目录不删除。失败metadata不自动删除。

不证明:真正Pi/Node/认证、provider端点/TLS/日期模型/参数、真实session零写历史或任意
恶意进程逃逸。这些仍需后续适用证据与H2/H3,不能借本轮放行。没有完整离线门禁/产品激活。
执行前先读owner-wizard.sh每一root命令;向导只展示,不会替所有者执行sudo。
"""
    (destination / "owner-review.md").write_text(review)
    members = [p for p in destination.iterdir() if p.is_file()]
    # Wizard is generated last, its source is sealed too; no circular self-digest.
    stages = wizard_stages(
        destination, plan, [p.name for p in members] + ["owner-wizard.sh"]
    )
    template = (PROJECT / ".agents/skills/wizard/template.sh").read_text()
    library = template[: template.index("# STAGES: author this section.")]
    (destination / "owner-wizard.sh").write_text(library + stages)
    (destination / "owner-wizard.sh").chmod(0o700)
    members.append(destination / "owner-wizard.sh")
    (destination / "members.sha256").write_text(
        "".join(f"{digest(p)}  {p.name}\n" for p in sorted(members))
    )
    members.append(destination / "members.sha256")
    manifest = {
        "kind": "h1_synthetic_local_review",
        "members": {p.name: digest(p) for p in sorted(members)},
        "tools": tools,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    return destination


def wizard_stages(source: Path, plan: Plan, members: list[str]) -> str:
    root = plan.install_root
    py = root / "synthetic-python"
    helper = root / "issue167_h1_owner_ops.py"
    verify = (
        "sudo systemd-analyze verify --man=no "
        f"{root}/{plan.unit} {root}/{plan.guardian_unit}"
    )
    copy_result = (
        f"cp -- {plan.runtime_root}/guardian-result.json "
        f"{source}/results/guardian-result.json"
    )
    copy_ledger = (
        "sudo cat /var/lib/paperradar/probe-runs/"
        f"issue167-{plan.run_id}.json > {source}/results/ledger.json"
    )
    show_both = (
        f"systemctl show {plan.unit} {plan.guardian_unit} "
        "--property=LoadState,ActiveState,ControlGroup,FragmentPath"
    )
    approval_budget = (
        "最多10次IPv4连接/发送与4次IPv6创建(零报文)"
        if plan.network_mode == "ipv4_only"
        else "20次本机尝试"
    )
    stages = f"""# STAGES: owner-only commands, no automatic root actions.
run_wizard() {{
TOTAL_STAGES=6
stage "审批与源字节核对"
say "本包须另获H1/H3批准,不沿用H1-0或旧EXP-2许可。先读owner-review.md及所有root代码。"
say "cd -- {source} && sha256sum -c members.sha256"
say "sha256sum {source}/manifest.json"
step "manifest SHA须与本轮审批消息完全一致,否则停止。root步骤均由你另开终端执行。"
confirm "已获得绑定此包SHA与{approval_budget}的明确批准?" || return 1
stage "创建受保护代码根并复制"
say "test ! -L /home/paperradar-probes"
say "若公共父目录不存在,仅创建它: sudo mkdir -m 0755 -- /home/paperradar-probes"
say "stat -c '%u %a %F' /home /home/paperradar-probes"
step "父链须root所有且不允许组/其他写;冲突不chmod、不覆盖,直接停止。"
say "sudo mkdir -m 0755 -- {root}"
"""
    for name in [*members, "members.sha256", "manifest.json"]:
        mode = "0755" if name == "synthetic-python" else "0644"
        stages += (
            f'say "sudo install -o 0 -g 0 -m {mode} -- {source / name} {root / name}"\n'
        )
    stages += f"""say "sudo sha256sum {root}/manifest.json"
say "cd -- {root} && sha256sum -c members.sha256"
step "重新核对同一批准SHA;校验不一致时不要执行任何root脚本。"
pause "源与root-installed字节核对完成后按Enter。"
stage "安装两个精确unit,尚不运行"
say "sudo {py} -I -S -B {helper} install"
say "{verify}"
step "任一步失败都不start/restart,转恢复;不得新ID重试。"
pause "安装和只读语法检查完成后按Enter。"
stage "唯一一次合成本机运行"
say "sudo systemctl start {plan.guardian_unit}"
say "sudo systemctl start {plan.unit}"
step "最多等待180秒,不重复启动;本包root guardian会串行两phase与遗留后代负例。"
say "systemctl show {plan.guardian_unit} --property=ActiveState,SubState,Result"
say "{copy_result}"
say "{copy_ledger}"
pause "保留结果;unknown/失败不改写passed,不重发。"
stage "先停止并核对空cgroup再撤规则与unit"
say "sudo {py} -I -S -B {helper} restore > {source}/results/restoration.json"
step "归属/完整性/回收未知时停止,保留规则和metadata,告知agent;不要手工flush全局规则。"
say "{show_both}"
pause "恢复命令完成后按Enter。"
stage "仅成功时清理本包文件,保留永久单次记录"
say "确认结果成功且已复制;未知/失败时不执行finish,保留材料。"
confirm "是否已确认observed_expected、cleanup_complete与ledger一致?" || return 1
say "sudo {py} -I -S -B {helper} finish > {source}/results/artifacts.json"
step "永久记录留/var/lib/paperradar/probe-runs,不删除或用新名字清预算。"
say "向导没有替你执行命令。完成后告知agent只读复核。"
}}
run_wizard "$@"; exit
"""
    return stages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="仅生成未授权的H1合成本机审阅包")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--network-mode", choices=("dual_stack", "ipv4_only"), default="dual_stack"
    )
    args = parser.parse_args()
    print(
        create_bundle(
            args.destination,
            Plan(args.run_id, os.getuid(), os.getgid(), network_mode=args.network_mode),
        )
    )
