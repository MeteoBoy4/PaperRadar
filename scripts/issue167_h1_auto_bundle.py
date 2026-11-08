"""Generate a single-sudo driver, separately sealed from root core."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from scripts.issue167_h1_network_bundle import PROJECT, create_bundle, digest
from scripts.issue167_h1_phase import Plan

OLD_RUN = "6e70b5a31d42"
OLD_MANIFEST = "1fba953291de3c72c4231446601d6c338908d09d89e9bb59c51d7936e41233c6"
OLD_LEDGER = "a8d6c5176b08bcc861fb3b6ddd4d6f9fe9adf5f86ad10151d09b748b44b11c6c"


def driver_text(plan: Plan, core_sha: str, bootstrap: str) -> str:
    # Only sudo itself consumes a password from the terminal. No -S/password variable.
    sudo_invoke = (
        '  if /usr/bin/sudo /usr/bin/python3 -I -S -B - "$owner_source_dir" '
        f"{core_sha} {plan.uid} {plan.gid} "
        "<<'ROOT_BOOTSTRAP' > \"$owner_tmp\""
    )
    result_invoke = (
        '  /usr/bin/python3 -I -S -B - "$owner_source_dir" '
        '"$owner_tmp" "$owner_exit" ' + "<<'LOCAL_RESULT'"
    )
    head = f"""#!/usr/bin/env bash
set -euo pipefail
run_owner_auto() {{
  local owner_source_dir
  owner_source_dir=$(cd -- "$(dirname -- "${{BASH_SOURCE[0]}}")" && pwd -P)
  printf '%s\\n' '[H1] 核对封印并预占本地执行；本脚本不读取或保存密码。'
  /usr/bin/python3 -I -S -B - "$owner_source_dir" <<'LOCAL_CHECK'
import os,json,hashlib,stat
from pathlib import Path
import sys
r=Path(sys.argv[1]); expected={core_sha!r}
if os.getuid()!={plan.uid} or os.getgid()!={plan.gid}:
    raise SystemExit('owner_identity_mismatch')
seal=json.loads((r/'review-seal.json').read_text())
if (set(seal)!={{'kind','run_id','manifest_sha256','driver_sha256'}}
    or seal['kind']!='h1_owner_auto_review'
    or seal['run_id']!={plan.run_id!r}):
    raise SystemExit('review_seal_invalid')
if (seal['manifest_sha256']!=expected
    or hashlib.sha256((r/'manifest.json').read_bytes()).hexdigest()!=expected):
    raise SystemExit('manifest_changed')
if (hashlib.sha256((r/'owner-wizard.sh').read_bytes()).hexdigest()
    !=seal['driver_sha256']):
    raise SystemExit('driver_changed')
if (r/'results/owner-run.json').exists() or (r/'results/owner-run.json').is_symlink():
    raise SystemExit('result_already_present')
fd=os.open(r/'results/execution-started.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as out:
    json.dump({{'state':'reserved_unknown','run_id':{plan.run_id!r},'manifest_sha256':expected}},out)
    out.flush();os.fsync(out.fileno())
LOCAL_CHECK
  local owner_tmp owner_exit
  owner_tmp=$(mktemp "$owner_source_dir/results/.owner-output-XXXXXX")
  owner_exit=0
  printf '%s\\n' '[H1] 以下只有sudo可能请求终端密码；不会自动补跑。'
{sudo_invoke}
"""
    tail = """ROOT_BOOTSTRAP
  then
    owner_exit=0
  else
    owner_exit=$?
  fi
__RESULT_INVOKE__
import json,os,sys
from pathlib import Path
r,p,code=Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3])
value={'owner_result':'unknown','failure_stage':'sudo_or_bootstrap','exit_code':code}
try:
    with p.open('rb') as inp: raw=inp.read(131073)
    if len(raw)<=131072:
        candidate=json.loads(raw)
        if (type(candidate) is dict and candidate.get('owner_result')
            in {'unknown','observed_expected_and_restored','interrupted'}):
            value=candidate
except (OSError,ValueError):
    pass
if value.get('owner_result')=='observed_expected_and_restored':
    if code!=0:
        value={**value,'owner_result':'interrupted' if code==130 else 'unknown',
               'failure_stage':'owner_exit','exit_code':code}
    elif (value.get('scope')!='h1_owner_automation_only'
          or value.get('run_id')!=__EXPECTED_RUN__
          or value.get('manifest_sha256')!=__EXPECTED_CORE__):
        value={**value,'owner_result':'unknown','failure_stage':'owner_identity'}
fd=os.open(r/'results/owner-run.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as out:
    json.dump(value,out,sort_keys=True,indent=2);out.write('\\n');out.flush();os.fsync(out.fileno())
p.unlink(missing_ok=True)
print(json.dumps({'owner_result':value['owner_result'],'receipt':str(r/'results/owner-run.json')},sort_keys=True))
raise SystemExit(0 if value['owner_result']=='observed_expected_and_restored' else 1)
LOCAL_RESULT
}
run_owner_auto "$@"
"""
    return (
        head
        + bootstrap.rstrip()
        + "\n"
        + tail.replace("__RESULT_INVOKE__", result_invoke)
        .replace("__EXPECTED_RUN__", repr(plan.run_id))
        .replace("__EXPECTED_CORE__", repr(core_sha))
    )


def create_auto_bundle(
    destination: Path, plan: Plan, *, predecessor: dict[str, object] | None = None
) -> Path:
    previous = OLD_RUN if predecessor is None else predecessor.get("predecessor_run_id")
    if plan.run_id == previous:
        raise ValueError("old_case_cannot_be_reused")
    root = create_bundle(destination, plan)
    manifest = json.loads((root / "manifest.json").read_text())
    (root / "owner-wizard.sh").unlink()
    manifest["members"].pop("owner-wizard.sh")
    for name in ("issue167_h1_owner_run.py", "issue167_h1_auto_bootstrap.py"):
        (root / name).write_bytes((PROJECT / "scripts" / name).read_bytes())
    retry = {
        "kind": "additional_attempt_after_unknown",
        "predecessor_run_id": OLD_RUN,
        "predecessor_manifest_sha256": OLD_MANIFEST,
        "predecessor_ledger_sha256": OLD_LEDGER,
        "additional_attempts": 1,
    }
    if predecessor is not None:
        retry = predecessor
    if (
        set(retry)
        != {
            "kind",
            "predecessor_run_id",
            "predecessor_manifest_sha256",
            "predecessor_ledger_sha256",
            "additional_attempts",
        }
        or retry["kind"] != "additional_attempt_after_unknown"
        or type(retry["additional_attempts"]) is not int
        or retry["additional_attempts"] != 1
        or type(retry["predecessor_run_id"]) is not str
        or re.fullmatch(r"[a-f0-9]{12}", str(retry["predecessor_run_id"])) is None
        or any(
            type(retry[key]) is not str
            or re.fullmatch(r"[a-f0-9]{64}", str(retry[key])) is None
            for key in ("predecessor_manifest_sha256", "predecessor_ledger_sha256")
        )
    ):
        raise ValueError("retry_context_invalid")
    (root / "retry-context.json").write_text(json.dumps(retry, sort_keys=True) + "\n")
    review = (root / "owner-review.md").read_text()
    review += """

## 本修订的自动执行与额外尝试边界

旧run已失败unknown、永久账本保留，不退还/重命名它。retry-context链接其清单和账本。
本包需绑定review-seal.json的新H1/H3额外一次授权；不是旧H1-0或旧失败run的补跑。
修复：runtime新目录显式fchmod0755不受UMask0077影响；worker等待root原子runtime-ready
完成标记后才检查其私有目录；root捕获闭集failure_stage/os_error和自身选定权限metadata。
原root cap、端口、unit角色、产品启动身份和计数终局不扩大。具体网络模式、创建检查与
连接/发送上限以前文封印计划为准;IPv4-only不是旧dual-stack结果的重写或预算退款。

本修订不使用旧手动向导。你启动owner-wizard.sh后只需在sudo的终端提示输入密码；
脚本不read/保存/记录密码，不用sudo -S或密码环境变量。唯一一次sudo运行字面bootstrap:
先fd-relative/no-follow/UID/nlink/大小/SHA验证全部用户源字节，再安装root-owned副本,
随后exec封印root runner自动核对、安装、一次启动、等待、采集和恢复。
不会sudo执行workspace文件。
密码错误/中断/失败也保留本地execution-started与受控unknown结果，不自动重试。
未知/失败不finish删除材料；SIGKILL/不可验证归属不能保证自动恢复，保留证据供owner处置。

## 停止后规则身份的独立绑定修复

在live精确cgroup2路径打开并独立fstat读取dev/inode,前后核对不变;仅支持本机x86_64
64位ABI且fstatfs确认cgroup2。Linux v7.0官方源码中nft socket cgroup ID与该inode同源,
这是源码依据与mock验证,尚不冒称本次宿主链路现场通过。原严格路径验表通过后、任何go前,
新增root0600原子runtime/table-binding.json,绑定boot/kernel/plan/cgroup dev-inode及
table/scope/chain/counter稳定handles。该文件由本次root创建,不是从当前表自报数字推定。
后续切phase/计数和停止后的恢复均验绑定与完整原规则;只允许保存的精确数字ID转换供原
严格verifier检查。缺绑定只允许原严格path核查,numeric仍unknown;坏绑定/handle/host漂移
不能降级。未增加cap、外部端点、mount namespace或其他宿主策略。
完整成功并核对后finish会按原边界移除本run runtime/code（含该binding）,永久单次账本保留;
失败保留材料。创建中断/绑定尚未完成/未知规则仍可能需要所有者仅恢复裁决,不能保证任意
中断都自动恢复。旧run的数字身份例外仅用于它的恢复,不能成为本包的默认放宽。

core manifest不含driver/review-seal或其间接hash引用，driver内嵌core SHA；外部review-seal
绑定core+driver SHA。可写seal自检只发现意外损坏，不代表软件验证了外部批准或产品通过。
旧手动说明仅为范围/恢复设计依据；实际命令由自动root runner的固定闭集路径执行。
"""
    (root / "owner-review.md").write_text(review)
    core_names = set(manifest["members"]) | {
        "issue167_h1_owner_run.py",
        "issue167_h1_auto_bootstrap.py",
        "retry-context.json",
    }
    core_names.discard("members.sha256")
    (root / "members.sha256").write_text(
        "".join(f"{digest(root / name)}  {name}\n" for name in sorted(core_names))
    )
    core_names.add("members.sha256")
    manifest["members"] = {name: digest(root / name) for name in sorted(core_names)}
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    for member in [*manifest["members"], "manifest.json"]:
        (root / member).chmod(0o755 if member == "synthetic-python" else 0o644)
    core_sha = digest(root / "manifest.json")
    driver = root / "owner-wizard.sh"
    driver.write_text(
        driver_text(
            plan, core_sha, (root / "issue167_h1_auto_bootstrap.py").read_text()
        )
    )
    driver.chmod(0o700)
    seal = {
        "kind": "h1_owner_auto_review",
        "run_id": plan.run_id,
        "manifest_sha256": core_sha,
        "driver_sha256": digest(driver),
    }
    (root / "review-seal.json").write_text(
        json.dumps(seal, sort_keys=True, indent=2) + "\n"
    )
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="仅生成只需sudo密码的额外尝试待审包,不执行"
    )
    parser.add_argument("destination", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--network-mode", choices=("dual_stack", "ipv4_only"), default="dual_stack"
    )
    parser.add_argument("--retry-context", type=Path)
    args = parser.parse_args()
    print(
        create_auto_bundle(
            args.destination,
            Plan(args.run_id, os.getuid(), os.getgid(), network_mode=args.network_mode),
            predecessor=json.loads(args.retry_context.read_text())
            if args.retry_context
            else None,
        )
    )
