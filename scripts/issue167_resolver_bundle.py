"""Prepare a new owner-reviewed, no-network H1 resolver/window package only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from scripts.issue167_h1_auto_bundle import driver_text
from scripts.issue167_resolver_case import Case, current_host_context, render_unit
from scripts.issue167_service_egress import FrozenEgress

PROJECT = Path(__file__).resolve().parents[1]
APPORT_SHA = "e8b57da9924d461fee6d3b392dc184697bc14d2eb8d717c05e1cbf0bd376041e"
SOURCES = {
    "issue167_resolver_case.py": "scripts/issue167_resolver_case.py",
    "issue167_h1_owner_run.py": "scripts/issue167_resolver_owner.py",
    "issue167_resolver_worker.py": "scripts/issue167_resolver_worker.py",
    "issue167_resolver_child.py": "scripts/issue167_resolver_child.py",
    "issue167_service_egress.py": "scripts/issue167_service_egress.py",
    "issue167_fork_observation.py": "scripts/issue167_fork_observation.py",
    "issue167_observation.py": "scripts/issue167_observation.py",
    "issue167_h1_phase.py": "scripts/issue167_h1_phase.py",
    "issue167_h1_guardian.py": "scripts/issue167_h1_guardian.py",
    "issue167_h1_owner_ops.py": "scripts/issue167_h1_owner_ops.py",
    "issue167_h1_network_worker.py": "scripts/issue167_h1_network_worker.py",
    "issue167_h1_auto_bootstrap.py": "scripts/issue167_h1_auto_bootstrap.py",
    "production_isolation.py": "src/paper_radar/pi_execution/isolation.py",
    "production_errors.py": "src/paper_radar/pi_execution/errors.py",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def create_bundle(destination: Path, run_id: str, profile_path: Path) -> Path:
    destination = destination.resolve()
    if re.fullmatch(r"/[A-Za-z0-9_./-]+", str(destination)) is None:
        raise ValueError("review_path_unknown")
    raw = profile_path.read_bytes()
    if len(raw) > 65536 or os.getuid() == 0:
        raise ValueError("review_source_unknown")
    source = Path("/usr/share/apport/apport").read_bytes()
    if digest(source) != APPORT_SHA:
        raise ValueError("collector_source_changed")
    # Validate policy before allocating a package; the base Plan is identity only.
    provisional = Case(
        run_id, os.getuid(), os.getgid(), digest(raw), "0" * 64, APPORT_SHA
    )
    host = current_host_context()
    profile = FrozenEgress.from_profile(provisional.base_plan(), raw, digest(raw), host)
    resolver = f"nameserver {profile.resolver}\n".encode()
    case = Case(
        run_id, os.getuid(), os.getgid(), digest(raw), digest(resolver), APPORT_SHA
    )
    interpreter = Path(sys.executable).resolve(strict=True)
    tools = {
        "python": {
            "path": str(case.install_root / "synthetic-python"),
            "sha256": digest(interpreter.read_bytes()),
        }
    }
    for name, path in {
        "nft": Path("/usr/sbin/nft"),
        "systemctl": Path("/usr/bin/systemctl"),
        "systemd_analyze": Path("/usr/bin/systemd-analyze"),
    }.items():
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError("host_tool_missing")
        tools[name] = {"path": str(path), "sha256": digest(path.read_bytes())}
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    destination.chmod(0o700)
    (destination / "results").mkdir(mode=0o700)
    for name, source_path in SOURCES.items():
        shutil.copyfile(PROJECT / source_path, destination / name)
    shutil.copyfile(interpreter, destination / "synthetic-python")
    (destination / "synthetic-python").chmod(0o755)
    (destination / "plan.json").write_text(
        json.dumps(case.to_dict(), sort_keys=True, indent=2) + "\n"
    )
    (destination / "profile.json").write_bytes(raw)
    (destination / "resolv.conf").write_bytes(resolver)
    (destination / "host-context.json").write_text(
        json.dumps(host, sort_keys=True) + "\n"
    )
    # Required by the reused generic copy bootstrap, not consumed as retry funding.
    (destination / "retry-context.json").write_text(
        json.dumps(
            {
                "kind": "new_no_network_case_requires_external_approval",
                "previous_cases_retained": True,
                "old_allowances_reused": False,
            },
            sort_keys=True,
        )
        + "\n"
    )
    (destination / case.unit).write_text(render_unit(case))
    from scripts.issue167_service_egress import (
        render_activate,
        render_clear,
        render_create,
        render_delete,
    )

    for name, contents in {
        "create.nft": render_create(profile),
        "activate.nft": render_activate(profile),
        "clear.nft": render_clear(profile),
        "delete.nft": render_delete(profile),
    }.items():
        (destination / name).write_text(contents)
    review = f"""# #167 H1/H3：无网络 resolver/window 新案例，待所有者审批

run={case.run_id}; uid/gid={case.uid}/{case.gid}
unit={case.unit}; table=inet {case.table}
root-owned code={case.install_root}; runtime={case.runtime_root}
permanent=/var/lib/paperradar/probe-runs/issue167-{case.run_id}.json

这是一项新的单次无秘密验证，不复用旧root/网络/EXP-2许可、余额或失败历史。
先审全部源码、plan/profile、unit、规则与bootstrap，再批准绑定review-seal.json的外部SHA。
本地可写seal自检不构成外部授权或产品通过。

## 精确影响与动作

唯一一次sudo：密码只由sudo TTY读取，不用sudo-S、不在脚本/变量/文件存密码。
literal stdin bootstrap先nofollow/NONBLOCK/owner/nlink/大小/SHA验证全部源字节，再排他
复制到root-owned /home根并exec已封印owner代码；不以root运行workspace文件。
临时owner是sudo授权的root管理进程，不声称受旧六cap guardian约束；无常驻root service。
worker UID/GID固定、cap/ambient空、NNP/seccomp/Delegate=no和双层零core保持。

安装1个具名unit及本次root代码/runtime/resolv.conf；该unit仅将本次受保护文件以
BindReadOnlyPaths绑定到自己的/etc/resolv.conf。不写全机resolver，不改router/代理/
core_pattern/Apport/安装树或其他程序；前后只读核对全机resolver SHA，外部变化即unknown，
不替别人回滚。RemainAfterExit=yes仅保留退出状态，root确认ExecMainCode1/Status0、CG空
之后显式stop/unlink/reload，正常成功不留下该unit。

worker限制为RestrictAddressFamilies=none、IPAddressDeny=any和SocketBindDeny=any。
不创建socket；nft按精确cgroup执行deny→activate→clear→activate，空CG后bound核表删除。
只核对实际kernel规则结构/独立CG身份，packet counter必须0；不做允许/拒绝流量对照，
不借规则字节声称出站流量已验。新private profile中的candidate_probe是历史前置元数据
计划，不会执行；本案例DNS/TLS/HTTP/真实auth/model/Pi/Node/IPv6探测与崩溃全部0。

只执行synthetic Python auth1/model1，非Node/Pi：固定非秘密marker仅匿名输出管道→父内存→
model显式env，回执只boolean，不保存marker/完整argv/env；原FD以pass_fds继承，核共享
offset、父close后独立EX拒绝、子退出后EX允许。model使用复制的production LL源码并额外
允许Python stdlib，仅此合成fixture，不改产品权限或identity，不冒充生产prepare_launch。
同CG不同session子进程退出后才seal终态→删除model树→独立deleted；实际inotify/CG
缺失、后代/漂移/overflow/窗口丢失均unknown；不调系统watch配额。

## namespace/core与证明范围

源collector SHA={case.apport_sha256}。Apport is_same_ns含/system.slice例外，不能因新mnt
inode不同推断提前ignore；保留原RLimitCore零路径。当前仅实际namespace/cgroup、
readonly resolver、core00等metadata与已绑定源码适用性说明，不运行Apport或crash，不声称
完整core持久化重新通过；未重查用户unpackaged配置、未授真实凭据。
namespace对比来源是root-caller，不伪称真实handler。产品LAUNCH_POLICY_VERSION/
pi_protocol/read_evidence均不变；真实Node/Pi、DNS兼容/内层TCP53、认证/模型及H5仍待。

## 停止、恢复与回执

root永久O_EXCL锚点先于案例动作，worker也预占；任何失败/unknown不退款、不自动重试。
本修订在服务安装/启动前原子保存root0600全局resolver基线，恢复时读回同run/SHA后再
比较当前SHA；before/after来源与受控恢复子阶段保留到ledger。inactive/dead不做reset-failed，
仅failed态才重置并复核，不把未加载视为必须重跑。旧失败记录不回填成通过。
原子门闩/ready/result有界等待；source、unit/drop-in/manager或table归属不明则保留待审，
不停止陌生对象、不flush全局。root中断进入受控恢复；SIGKILL/创建不明不能保证恢复。
先核unit字节并stop，CG空且独立binding/完整表状态相符后才delete本表，再卸unit/reload。
成功才精确删除本次runtime/code并保留永久ledger，失败保留受控材料；不删任何旧case。

保留worker的受控明细、5个已验本表kernel快照、independent binding及namespace来源，
不读凭据/真实进程environ/core/日志或模型流。具体内部配置与回执只留本地，不发GitHub。
worker内部40s、unit RuntimeMaxSec50s、owner等待90s及有界命令/回收；不重复start/restart。

## 入口

批准后由所有者在项目根目录运行：
`bash {destination}/owner-wizard.sh`
只向sudo输入一次密码，其余安装/唯一启动/核查/恢复由脚本执行。失败不要再跑，告知agent。
默认生成文件不授予执行许可；这个包不提供产品准入、激活或完整Live资格。
"""
    (destination / "owner-review.md").write_text(review)
    names = sorted(path.name for path in destination.iterdir() if path.is_file())
    (destination / "members.sha256").write_text(
        "".join(
            f"{digest((destination / name).read_bytes())}  {name}\n" for name in names
        )
    )
    names.append("members.sha256")
    for name in names:
        (destination / name).chmod(0o755 if name == "synthetic-python" else 0o644)
    manifest = {
        "kind": "h1_synthetic_local_review",
        "members": {name: digest((destination / name).read_bytes()) for name in names},
        "tools": tools,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    (destination / "manifest.json").chmod(0o644)
    core_sha = digest((destination / "manifest.json").read_bytes())
    driver = destination / "owner-wizard.sh"
    driver.write_text(
        driver_text(
            case.base_plan(),
            core_sha,
            (destination / "issue167_h1_auto_bootstrap.py").read_text(),
        )
    )
    driver.chmod(0o700)
    seal = {
        "kind": "h1_owner_auto_review",
        "run_id": run_id,
        "manifest_sha256": core_sha,
        "driver_sha256": digest(driver.read_bytes()),
    }
    (destination / "review-seal.json").write_text(
        json.dumps(seal, sort_keys=True, indent=2) + "\n"
    )
    (destination / "review-seal.json").chmod(0o644)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="仅准备无网络H1 resolver/window待审包")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--profile",
        type=Path,
        default=PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
    )
    args = parser.parse_args()
    print(create_bundle(args.destination, args.run_id, args.profile))
