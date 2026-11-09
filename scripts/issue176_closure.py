#!/usr/bin/env python3
"""生成单次所有者收口审阅包;构建不读站点、不部署、不执行sudo。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shlex
from pathlib import Path

RUNTIME = "/usr/libexec/paperradar/live-evidence-runtime"
STAGING = "/var/lib/paperradar/live-evidence-closure"


def build_bundle(
    output: Path, *, payload_sha256: str, manifest_sha256: str, receipt_id: str
) -> None:
    if any(
        not re.fullmatch("[0-9a-f]{64}", digest)
        for digest in (payload_sha256, manifest_sha256)
    ) or not re.fullmatch("[0-9a-f]{16}", receipt_id):
        raise ValueError("closure_identity_invalid")
    workflow = Path(__file__).with_name("issue176_closure_workflow.py").read_bytes()
    config = {
        "payload_sha256": payload_sha256,
        "manifest_sha256": manifest_sha256,
        "receipt_id": receipt_id,
        "drill_use": "value-low",
        "final_use": "boundary-low",
        "run_name": "closure-"
        + hashlib.sha256(
            workflow
            + payload_sha256.encode()
            + manifest_sha256.encode()
            + receipt_id.encode()
        ).hexdigest()[:16],
    }
    configuration = (json.dumps(config, sort_keys=True, indent=2) + "\n").encode()
    hashes = {
        "workflow.py": hashlib.sha256(workflow).hexdigest(),
        "config.json": hashlib.sha256(configuration).hexdigest(),
    }
    stage = STAGING + "-" + config["run_name"]
    checks = "\n".join(f"{digest}  {name}" for name, digest in hashes.items())
    root_checks = "\n".join(
        f"{digest}  {stage}/{name}" for name, digest in hashes.items()
    )
    marker = hashlib.sha256((payload_sha256 + "\n").encode()).hexdigest()
    frozen_bytes = "\n".join(
        f"/usr/bin/printf '%s' '{base64.b64encode(data).decode()}' | "
        f'/usr/bin/base64 --decode > "$staging/{name}"'
        for name, data in (("workflow.py", workflow), ("config.json", configuration))
    )
    root = f"""set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
refuse() {{ /usr/bin/printf 'closure refused [%s]\\n' "$1" >&2; exit 2; }}
[ "$(/usr/bin/id -u)" -eq 0 ] || refuse root_required
runtime={RUNTIME}
staging={stage}
protected() {{
 current="$1"
 while :; do
  [ ! -L "$current" ] || refuse protected_symlink
  [ "$(/usr/bin/stat -c %u "$current")" -eq 0 ] || refuse protected_owner
  mode=$(/usr/bin/stat -c %a "$current")
  [ "$((0$mode & 0022))" -eq 0 ] || refuse protected_mode
  [ "$current" != / ] || break
  current=$(/usr/bin/dirname "$current")
 done
}}
protected "$runtime"
protected /var/lib/paperradar
[ ! -e "$staging" ] && [ ! -L "$staging" ] || refuse closure_already_staged
digest=$(/usr/bin/sha256sum "$runtime/payload.sha256" | /usr/bin/cut -d ' ' -f 1)
[ "$digest" = '{marker}' ] || refuse old_payload_identity
digest=$(/usr/bin/sha256sum "$runtime/manifest.sha256" | /usr/bin/cut -d ' ' -f 1)
[ "$digest" = '{manifest_sha256}' ] || refuse old_manifest_identity
invalid=$(/usr/bin/find "$runtime" ! '(' -type f -o -type d ')' -print -quit)
[ -z "$invalid" ] || refuse old_runtime_node
expected=$(/usr/bin/awk '
 {{path=substr($0,67); print "f " path;
   while (sub("/[^/]+$", "", path)) print "d " path}}
 END {{print "d "; print "f manifest.sha256"; print "f payload.sha256"}}
 ' "$runtime/manifest.sha256" | LC_ALL=C /usr/bin/sort -u)
actual=$(cd "$runtime" &&
 /usr/bin/find . -printf '%y %P\\n' | LC_ALL=C /usr/bin/sort -u)
[ "$expected" = "$actual" ] || refuse old_runtime_members
members=$(/usr/bin/find "$runtime" -print)
while IFS= read -r member; do
 protected "$member"
 member_mode=$(/usr/bin/stat -c %a "$member")
 case "$member_mode" in 644|755) ;; *) refuse old_runtime_mode;; esac
 if [ -d "$member" ]; then
  [ "$member_mode" = 755 ] || refuse old_runtime_mode
 fi
 if [ -f "$member" ]; then
  [ "$(/usr/bin/stat -c %h "$member")" -eq 1 ] || refuse old_runtime_hardlink
 fi
done <<MEMBERS
$members
MEMBERS
(cd "$runtime" && /usr/bin/sha256sum --strict -c manifest.sha256 >/dev/null) ||
 refuse old_runtime_integrity
for entry in collect owner tighten; do
 protected /usr/libexec/paperradar/live-evidence-$entry
 /usr/bin/cmp /usr/libexec/paperradar/live-evidence-$entry \
  "$runtime/wrappers/$entry" || refuse entry_conflict
done
policy=/etc/sudoers.d/paperradar-live-evidence
protected "$policy"
[ "$(/usr/bin/stat -c %a "$policy")" = 440 ] || refuse policy_mode
[ -f "$policy" ] && [ "$(/usr/bin/stat -c %h "$policy")" -eq 1 ] ||
 refuse policy_type
/usr/bin/cmp "$policy" "$runtime/sudoers" || refuse policy_conflict
/usr/bin/install -d -o root -g root -m 0755 "$staging"
# root不读取产品可写路径,从已审runner内嵌精确字节冻结,避免复制期间换链读取root文件。
{frozen_bytes}
/usr/bin/printf '%s\\n' {shlex.quote(root_checks)} | /usr/bin/sha256sum -c -
cd "$runtime"
exec /usr/bin/env -i "$runtime/python/bin/python3" -I -S -B "$staging/workflow.py"
"""
    runner = f"""#!/bin/sh
set -eu
[ "$#" -eq 0 ] || exit 2
package=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")" && /usr/bin/pwd -P)
(cd "$package" &&
 /usr/bin/printf '%s\\n' {shlex.quote(checks)} | /usr/bin/sha256sum -c -)
exec /usr/bin/sudo -k /bin/sh -c {shlex.quote(root)} sh "$package"
"""
    output.mkdir(parents=True, mode=0o700)
    (output / "workflow.py").write_bytes(workflow)
    (output / "config.json").write_bytes(configuration)
    (output / "run-owner.sh").write_text(runner)
    (output / "run-owner.sh").chmod(0o700)
    hashes["run-owner.sh"] = hashlib.sha256(runner.encode()).hexdigest()
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items())
    )
    (output / "REVIEW.md").write_text(
        "# 所有者单次收口审阅包（尚未执行）\n\n"
        "先暂停业务任务与其他准入写入，审阅本包全部字节和SHA256SUMS。\n"
        "run-owner.sh只申请一次sudo密码；root先核部署runtime完整成员及摘要，再从已审入口内嵌字节冻结本包；root不读产品可写来源。\n"
        "仅新进程生命周期重读；不会重启主机、服务或改变部署runtime/sudoers。\n"
        "初始只允许boundary-low非空active、value-low未激活且未撤销。\n"
        "本人完整审阅并手输短ID激活value-low→备份账本→helper不可逆撤销value-low→"
        "新进程复核→合并恢复备份（全部激活失效）→新进程复核→本人重新审阅并手输短ID激活boundary-low。\n"
        "每次激活前/确认后均由固定collector真实刷新观察；失败安全停，不假fresh、不续verified_at。\n"
        "成功必须最终原boundary-low全部非空分项active，value-low仍撤销，业务预算标识/计数未变。\n"
        "备份、每阶段只读快照和安全回执保存在root账本下唯一closure目录；不删除或覆盖历史。\n"
        "任一步中断不自动回滚/清理/授予；恢复后若尚未最终激活，保持阻断并由本人另行重审激活。\n"
        "本脚本无认证/模型/网络；原计划窗口、stopped、撤销与预算不刷新。\n"
        "安全回执含原主张、激活事件时刻、绑定摘要、用途、登记与期限依据；仅root来源为权威。\n"
        "模型/RPC/IPv4/observer仍缺失，不把部分active写成可执行或Live完成。\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="构建待审单次收口包，不执行sudo或读取真实站点。"
    )
    parser.add_argument(
        "--payload-sha256", required=True, help="已部署runtime payload SHA256。"
    )
    parser.add_argument(
        "--manifest-sha256", required=True, help="已部署manifest文件SHA256。"
    )
    parser.add_argument(
        "--receipt-id", required=True, help="owner明确选择的已接收回执短ID。"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="尚不存在的私有审阅目录。"
    )
    args = parser.parse_args()
    try:
        build_bundle(
            args.output,
            payload_sha256=args.payload_sha256,
            manifest_sha256=args.manifest_sha256,
            receipt_id=args.receipt_id,
        )
    except (ValueError, OSError):
        parser.exit(
            2, "收口构建拒绝 [closure_identity_invalid]；请核对精确身份和新输出目录。\n"
        )
    print("待审包已生成；没有部署、sudo、采集、撤销、恢复或证据激活。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
