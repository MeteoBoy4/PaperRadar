"""Generate a fixed-Node diagnostic review bundle; never execute its entry."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts import issue167_node_diag_case as contract
from scripts import issue167_resolver_bundle as original
from scripts import issue167_service_network_bundle as network
from scripts.issue167_h1_auto_bundle import driver_text


def create_bundle(destination: Path, run_id: str, profile_path: Path) -> Path:
    import scripts.issue167_node_diag_supply as supply

    if "." in os.uname().nodename:
        raise ValueError("nss_context_unknown")
    binding = supply.prepare_binding()
    nss = Path("/etc/nsswitch.conf").read_bytes()
    if len(nss) > 16384:
        raise ValueError("nss_context_unknown")
    root = network.create_bundle(destination, run_id, profile_path)
    old = json.loads((root / "plan.json").read_text())
    case = contract.Case(
        *(
            old[k]
            for k in (
                "run_id",
                "uid",
                "gid",
                "profile_sha256",
                "resolver_sha256",
                "apport_sha256",
            )
        )
    )
    for name in ("case", "worker", "owner", "supply"):
        filename = f"issue167_node_diag_{name}.py"
        (root / filename).write_bytes(
            (original.PROJECT / "scripts" / filename).read_bytes()
        )
    (root / "node-binding.json").write_text(
        json.dumps(binding, sort_keys=True, indent=2) + "\n"
    )
    (root / "nss-context.json").write_text(
        json.dumps(
            {
                "nsswitch_sha256": original.digest(nss),
                "hostname_contains_dot": False,
            },
            sort_keys=True,
        )
        + "\n"
    )
    (root / "plan.json").write_text(
        json.dumps(case.to_dict(), sort_keys=True, indent=2) + "\n"
    )
    (root / case.unit).write_text(contract.render_unit(case))
    (root / "network-worker-entry.py").unlink()
    (root / "node-worker-entry.py").write_text(
        network.entry("issue167_node_diag_worker", owner=False)
    )
    (root / "issue167_h1_owner_run.py").write_text(
        network.entry("issue167_node_diag_owner", owner=True)
    )
    (root / "retry-context.json").write_text(
        json.dumps(
            {
                "kind": "new_fixed_node_case_requires_external_approval",
                "previous_cases_retained": True,
                "old_allowances_reused": False,
                "dns_unknown_scope_A_chosen_not_execution_authorization": True,
            },
            sort_keys=True,
        )
        + "\n"
    )
    review = f"""# #167 H1/H2/H3：无秘密固定 Node 诊断，待审未执行

run={run_id}; UID/GID={case.uid}/{case.gid}
unit={case.unit}; table=inet {case.table}
root-owned code={case.install_root}; runtime={case.runtime_root}
permanent=/var/lib/paperradar/probe-runs/issue167-{run_id}.json

所有者只选择了解析预算范围A，尚未批准本包执行。新许可须绑定review-seal.json外部SHA，
先审全部源码、node-binding.json/nss-context.json、manifest、unit和规则；不复用旧余额。

## 具体影响

只安装一个具名项目unit、唯一inet表和本次root-owned代码/runtime/永久单次记录。
原固定cwd=/srv/pi-cwd，UID1000、空cap/ambient、NNP/seccomp、Delegate=no、双零core、
SocketBindDeny=any、AF_INET、IPAddressDeny=any+仅既定pool/router、服务内只读resolver保持。
允许集合仍TCP443至28.0.0.0/8、UDP/TCP53至192.168.44.1；不改全机DNS、router、代理、
core_pattern/Apport或其他程序，不写安装树，不开放模型TCP53，不改变产品启动/协议身份。
无TLS中间人由所有者确认；来源仍为OpenClash fake-ip、原池28.0.0.1/8、sniffer override、
LAN DNS劫持/TCP redirect7892。7892不新增为本机允许项；配置已知变/缺确认即停止。
API/auth共享池不证明分离；不核验上游映射/最终IP/线路、不主张出口身份。
IPv6 not_assessed。

## 固定Node与原安装保护

node-binding.json固定原项目实例/Node实际公开字节、数据库身份/登记投影、root marker、
既有实例锁dev/inode与完整tree-v1。只读窄投影使用stdlib SQLite mode=ro及固定公开列，
不读取业务行、认证或token；它不是完整public use_install/read_state/D5/配置选择重验。
明确标签diagnostic_readonly_original_instance_lock_not_product_use_install。
未来UID1000 worker用O_RDONLY打开原锁inode，LOCK_SH|LOCK_NB，四个Node均pass同一FD，
不复制Node、不另开child锁，不LOCK_UN，仅在子孙退出后close。全树/登记在保护scope两端核对，
不把重hash放入TTL临界段。新JS仅Node builtin、固定源码通过-e，安装树外，无loader/Pi注入。

## 顺序及预算

1. 一个非Landlock固定Node：仅router TCP53 connect一次、无DNS payload，5s。
   成功并close/退出，
   owner检查独立CG归属、完整bound规则及allowed增量；失败停止，不进入负例。
2. 一个原IsolationBoundary固定Node：同TCP53 connect一次，5s，
   必须EACCES/EPERM且close/退出。
   这是Landlock拒绝，应无本表新packet；不要求nft reject增量，不因失败而加端口。
3. API：父Python显式UDP/TCP A参考各1（各5s），必须strict single A、同IP、正TTL、池内。
   随后一个原Landlock Node默认dns.lookup调用1，无family/RES_OPTIONS/LOCALDOMAIN改写；
   结果必须为匹配参考的IPv4，再对该IPv4 TLS443一次、SNI/hostname为api.openai.com。
4. AUTH：同上，固定auth.openai.com，新的参考/Node会话，不复用旧TTL。

共Node exec4、lookup调用2、显式参考DNS4（UDP2/TCP2）、Node TLS连接/握手2、TCP53
正例/隔离负例各1；HTTP/auth CLI/model prompt/Pi/IPv6网络连接/崩溃0。
无应用重试/备用域名。
OS内部A/AAAA/NSS/重试次数、wire QNAME及TCPfallback尝试unknown，A只接受此诊断未知；
绝不声称总DNS查询<=2/6，AAAA查询不当作IPv6网络连接验收。若lookup走TCP53失败即unknown。
Node默认lookup只返回一个地址；IPv6或非参考地址均停止，不挑选备用地址。此诊断不等同
Pi/Undici原connector的全部family/autoselection行为，不作为产品接线或启动身份依据。

每域名Node查址+TLS整个父before/after区间须在同轮两份参考最早TTL截止前；Node本段最多10s
且受TTL更短截止，过期不补查。Node TLS默认根信任来自固定Node构建，env为空，无CA覆盖，
rejectUnauthorized=true、hostname/SNI、最低TLS1.2，无client key/cert。
它与前轮Python TLS探针的封印系统CA不同；本轮父Python只做DNS参考、不TLS。
仅握手后destroy并观察close，不发HTTP、不保存证书/原错误/流。
Node只筛选自身status/limits/cgroup与继承FD元数据，
输出closed categories/counts/booleans。
stdout最多16384 bytes、单JSON、父绝对截止、非0/残留/坏元数据均unknown，不保存stderr。
worker100s、unit110s、owner150s及有界命令/恢复；不承诺任意kernel阻塞绝对可抢占。

## 恢复和入口

沿v3持久root0600 resolver before/after基线、closed恢复阶段、scope-before-stop、CG空后
独立binding完整核表再删，精确unlink本unit/reload；永久记录保留、成功才清理本code/runtime。
源码/归属/绑定漂移或创建不明保留unknown/材料；SIGKILL不能保证自动恢复，无退款或重试。
root动作只由所有者审阅执行。字面bootstrap先验证所有源/工具/host，复制root-owned副本后exec；
不root导入workspace源码，不读取或保存密码，只有sudo通过TTY取一次密码。

获批且冻结配置/本次A未知范围仍适用后运行：
`bash {root}/owner-wizard.sh --owner-config-confirmed --owner-dns-unknown-confirmed`
两个flag缺任意一个，均在本地预占/sudo前拒绝；flag只转录所有者外部声明，不自证许可。
失败不要再跑，告知agent。旧unknown/账本/消耗不改，不扩历史分母/required或产品回执。
真实Pi、认证/模型、供应商能力/故障、H5与产品激活仍未获许可。内部配置/回执及相关哈希
只留本地，不发GitHub。本文件和生成包本身不授权任何现场动作。
"""
    (root / "owner-review.md").write_text(review)
    excluded = {
        "manifest.json",
        "owner-wizard.sh",
        "review-seal.json",
        "members.sha256",
    }
    names = sorted(
        p.name for p in root.iterdir() if p.is_file() and p.name not in excluded
    )
    (root / "members.sha256").write_text(
        "".join(
            f"{original.digest((root / name).read_bytes())}  {name}\n" for name in names
        )
    )
    names.append("members.sha256")
    old_manifest = json.loads((root / "manifest.json").read_text())
    manifest = {
        "kind": "h1_synthetic_local_review",
        "members": {
            name: original.digest((root / name).read_bytes()) for name in names
        },
        "tools": old_manifest["tools"],
    }
    if len(names) > 40:
        raise ValueError("member_count_unknown")
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    sha = original.digest((root / "manifest.json").read_bytes())
    text = driver_text(
        case.base_plan(), sha, (root / "issue167_h1_auto_bootstrap.py").read_text()
    )
    flags = """if [[ "$#" -ne 2 || "$1" != --owner-config-confirmed ||
      "$2" != --owner-dns-unknown-confirmed ]]; then
  printf '%s\\n' '需要外部授权及显式配置/解析未知范围确认：' \
    '--owner-config-confirmed --owner-dns-unknown-confirmed' >&2
  exit 2
fi
"""
    text = text.replace("set -euo pipefail\n", "set -euo pipefail\n" + flags, 1)
    (root / "owner-wizard.sh").write_text(text)
    (root / "owner-wizard.sh").chmod(0o700)
    seal = {
        "kind": "h1_owner_auto_review",
        "run_id": run_id,
        "manifest_sha256": sha,
        "driver_sha256": original.digest(text.encode()),
    }
    (root / "review-seal.json").write_text(
        json.dumps(seal, sort_keys=True, indent=2) + "\n"
    )
    for name in names:
        (root / name).chmod(0o755 if name == "synthetic-python" else 0o644)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="只准备固定Node无秘密诊断审阅包，不执行"
    )
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--profile",
        type=Path,
        default=original.PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
    )
    args = parser.parse_args()
    print(create_bundle(args.destination, args.run_id, args.profile))
