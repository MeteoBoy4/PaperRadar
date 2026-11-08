"""Prepare a separately authorized service-network package, never execute it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import issue167_resolver_bundle as base
from scripts import issue167_service_network_case as contract
from scripts.issue167_h1_auto_bundle import driver_text
from scripts.issue167_resolver_case import Case as OriginalCase

# Entry code is stdlib-only until every root-owned member has been checked.
ENTRY = """import hashlib,importlib,json,os,re,stat,sys,types
from pathlib import Path
root=Path(__file__).absolute().parent
if re.fullmatch(r'/home/paperradar-probes/issue167-[a-f0-9]{12}',str(root)) is None:
    raise SystemExit('protected_root_required')
for path in (root,*root.parents):
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:
        raise SystemExit('protected_root_required')
def read(name,limit):
    if re.fullmatch(r'[A-Za-z0-9_.-]+',name) is None or name in {'.','..'}:
        raise SystemExit('member_unknown')
    fd=os.open(root/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022
            or info.st_nlink!=1 or info.st_size>limit):
            raise SystemExit('member_unknown')
        data=stream.read(limit+1)
    if len(data)>limit:
        raise SystemExit('member_unknown')
    return data
def unique(rows):
    value={}
    for key,item in rows:
        if key in value: raise SystemExit('metadata_duplicate')
        value[key]=item
    return value
raw=read('manifest.json',65536)
if __OWNER__:
    if (len(sys.argv)!=3 or sys.argv[1]!='--expected-manifest-sha'
        or hashlib.sha256(raw).hexdigest()!=sys.argv[2]):
        raise SystemExit('approved_manifest_changed')
manifest=json.loads(raw,object_pairs_hook=unique)
if (type(manifest) is not dict or set(manifest)!={'kind','members','tools'}
    or manifest['kind']!='h1_synthetic_local_review'
    or type(manifest['members']) is not dict or len(manifest['members'])>40):
    raise SystemExit('manifest_unknown')
total=len(raw)
for name,sha in manifest['members'].items():
    if (type(name) is not str or type(sha) is not str
        or re.fullmatch('[a-f0-9]{64}',sha) is None):
        raise SystemExit('member_unknown')
    data=read(name,32*1024*1024); total+=len(data)
    if total>64*1024*1024 or hashlib.sha256(data).hexdigest()!=sha:
        raise SystemExit('member_changed')
package=types.ModuleType('scripts');package.__path__=[str(root)]
sys.modules['scripts']=package
module=importlib.import_module('scripts.__MODULE__')
raise SystemExit(module.main())
"""


def entry(module: str, *, owner: bool) -> str:
    return ENTRY.replace("__OWNER__", repr(owner)).replace("__MODULE__", module)


def create_bundle(destination: Path, run_id: str, profile_path: Path) -> Path:
    root = base.create_bundle(destination, run_id, profile_path)
    original = OriginalCase.from_dict(json.loads((root / "plan.json").read_text()))
    case = contract.Case(
        original.run_id,
        original.uid,
        original.gid,
        original.profile_sha256,
        original.resolver_sha256,
        original.apport_sha256,
    )
    (root / "issue167_resolver_owner.py").write_bytes(
        (root / "issue167_h1_owner_run.py").read_bytes()
    )
    for name in ("case", "worker", "owner"):
        filename = f"issue167_service_network_{name}.py"
        (root / filename).write_bytes(
            (base.PROJECT / "scripts" / filename).read_bytes()
        )
    (root / "issue167_dns_tls.py").write_bytes(
        (base.PROJECT / "scripts/issue167_dns_tls.py").read_bytes()
    )
    (root / "plan.json").write_text(
        json.dumps(case.to_dict(), sort_keys=True, indent=2) + "\n"
    )
    (root / case.unit).write_text(contract.render_unit(case))
    (root / "network-worker-entry.py").write_text(
        entry("issue167_service_network_worker", owner=False)
    )
    (root / "issue167_h1_owner_run.py").write_text(
        entry("issue167_service_network_owner", owner=True)
    )
    (root / "retry-context.json").write_text(
        json.dumps(
            {
                "kind": "new_service_network_case_requires_external_approval",
                "previous_cases_retained": True,
                "old_allowances_reused": False,
                "owner_configuration_confirmation": (
                    "external_explicit_entry_flag_required"
                ),
            },
            sort_keys=True,
        )
        + "\n"
    )
    review = f"""# #167 H1/H2/H3：单次项目服务网络验证，待审未执行

run={run_id}; UID/GID={case.uid}/{case.gid}
unit={case.unit}; table=inet {case.table}
root-owned code={case.install_root}; runtime={case.runtime_root}
permanent=/var/lib/paperradar/probe-runs/issue167-{run_id}.json

这是新的单次无凭据网络验证。旧案例、消费和unknown保留，不复用任何旧许可/余额。
先审全部代码、manifest、unit、规则及本说明；授权须绑定review-seal.json的外部SHA。
执行入口必须显式带 --owner-config-confirmed，表示所有者确认下述路由配置仍适用，
它只转录外部声明，不能独立证明路由器配置或执行授权。缺flag在预占与sudo之前拒绝。

## 已冻结范围及精确影响

允许集合仍为应用可见TCP443至28.0.0.0/8及UDP/TCP53至192.168.44.1。
来源仍为所有者已报告OpenClash fake-ip、原池28.0.0.1/8、
sniffer.override-destination=true、
LAN DNS劫持及TCP redirect7892；无TLS中间人由所有者确认。配置已知变化/缺确认即停止。
本机不核验上游映射、不主张线路/最终IP/出口身份；7892不增加为本机允许项。
API/auth共享池不证明两类目标隔离，实际域名由封印worker限制。IPv6 not_assessed、探测0。

只安装上述一个具名unit/项目独占表及本次受保护代码/runtime/resolver文件。
服务仅BindReadOnlyPaths本次nameserver文件到自己的/etc/resolv.conf，不改全机resolver；
安装启动前root0600原子保存全机resolver基线，恢复读回同run并比较前后SHA，漂移unknown。
无router、宿主全局出站、core_pattern、Apport、安装树或其他服务配置变更。
可信Python worker AF_INET、IPAddressDeny=any且只Allow现有池/router；cap/ambient空、
NNP/seccomp/Delegate=no、零core、SocketBindDeny=any、固定/srv/pi-cwd保持。
未运行Node/Pi、模型Landlock或生产prepare_launch，不声称Node默认lookup或内层TCP53已兼容。

## 顺序、预算与停止

1. 初始完整deny：TCP connect至router53一次，5s，无DNS payload；成功连接即unknown停止。
2. 仍deny：UDP A api.openai.com一次send/最多一次recv，5s；若规则失效可能发至router，
   已计入DNS预算；有任何响应即unknown停止。
每次socket已关闭且worker静默等待新gate后，root独立读取完整bound规则快照，
要求allowed不增、rejected增加；仅超时/errno不证明拒绝。任一步失败不activate、不追加尝试。
3. 单次activate完整冻结允许集合并核表；执行api UDP A/TCP A/TLS，再auth UDP A/TCP A/TLS。
每DNS操作5s，每TLS含TCP最多10s，组件总45s；单A、UDP/TCP一致、正TTL、池内、无CNAME/TC。
两次TLS均在同轮两份DNS最早TTL失效前开始并完成，保存开始/完成单调时间以独立复核。
只用封印公共CA，证书链/hostname校验，无client key/cert/环境CA覆盖，不发送HTTP。
active完整快照须allowed增、无意外reject；counter单调、稳定handles和独立CG绑定不变。

合计上限：DNS查询5（UDP3/TCP2），UDP send3，router TCP连接尝试3，TLS TCP连接/握手2。
这些是有界操作/连接尝试上限，非wire packet/query计数；内核重传不冒充应用重试。
HTTP/auth CLI/model prompt/Pi/Node/IPv6探测/新崩溃均0；
无重试、fallback、AAAA、额外域名。
worker70s、unit RuntimeMaxSec80s、owner120s及有界命令/恢复；不承诺任意kernel阻塞硬截止。

## 单次执行、恢复和证明边界

只有sudo本身从TTY读取一次密码，不读/存密码、不sudo-S、不root执行可写workspace脚本。
字面bootstrap先验证全部来源、成员/工具/host/SHA，再排他复制到root-owned目录并exec。
root/worker均先单次预占，失败/unknown不退款、不换ID重试。所有root动作由所有者执行。
源码/单位drop-in/归属不明即停止保留；先核unit归属再stop、CG空后按独立binding完整验表才删，
只unlink本unit/reload；inactive/dead不reset，failed才reset并复核。恢复子阶段与resolver
before/after保留永久ledger，成功才精确移除本code/runtime。SIGKILL/创建不明不保证自动恢复。

组件仍保留ordinary_user_predeployment_metadata_only/OS_ACL_assessed=false原语义；
新owner另列实际服务规则与代表性TCP/UDP对照，不修改组件原scope冒充全覆盖。
该轮不覆盖任意地址/协议、Node/Pi DNS或模型内层网络、真实凭据/认证/模型、完整core重验、
全渠道文件写入、供应商能力、H5或产品激活；不改变产品策略身份或历史覆盖/分母。
只保存受控metadata、完整本表规则快照、必要绑定及TLS/DNS窗口，不读日志/真实environ/凭据/core。
内部配置、回执及相关哈希只留本地，不发GitHub。

## 获批后入口

`bash {root}/owner-wizard.sh --owner-config-confirmed`
只输入sudo密码。任何失败不要再跑，告知agent；本文件和生成包本身不授予执行许可。
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
            f"{base.digest((root / name).read_bytes())}  {name}\n" for name in names
        )
    )
    names.append("members.sha256")
    old = json.loads((root / "manifest.json").read_text())
    manifest = {
        "kind": "h1_synthetic_local_review",
        "members": {name: base.digest((root / name).read_bytes()) for name in names},
        "tools": old["tools"],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    sha = base.digest((root / "manifest.json").read_bytes())
    text = driver_text(
        case.base_plan(), sha, (root / "issue167_h1_auto_bootstrap.py").read_text()
    )
    flag = """if [[ "$#" -ne 1 || "$1" != --owner-config-confirmed ]]; then
  printf '%s\\n' '需要外部授权及所有者配置适用性确认：--owner-config-confirmed' >&2
  exit 2
fi
"""
    text = text.replace("set -euo pipefail\n", "set -euo pipefail\n" + flag, 1)
    (root / "owner-wizard.sh").write_text(text)
    (root / "owner-wizard.sh").chmod(0o700)
    seal = {
        "kind": "h1_owner_auto_review",
        "run_id": run_id,
        "manifest_sha256": sha,
        "driver_sha256": base.digest((root / "owner-wizard.sh").read_bytes()),
    }
    (root / "review-seal.json").write_text(
        json.dumps(seal, sort_keys=True, indent=2) + "\n"
    )
    for name in names:
        (root / name).chmod(0o755 if name == "synthetic-python" else 0o644)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="只准备新的服务网络待审包，不执行")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--profile",
        type=Path,
        default=base.PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
    )
    args = parser.parse_args()
    print(create_bundle(args.destination, args.run_id, args.profile))
