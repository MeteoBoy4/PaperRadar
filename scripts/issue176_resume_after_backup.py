#!/usr/bin/env python3
"""非特权构建after-backup单次owner续行包;不读取真实root或业务DB。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shlex
from pathlib import Path
from typing import Any

if not __package__:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.issue176_resume_after_backup_workflow import validate_inputs

RUNTIME = "/usr/libexec/paperradar/live-evidence-runtime"
STAGING = "/var/lib/paperradar/live-evidence-resume"


def build_bundle(output: Path, inputs: dict[str, Any]) -> None:
    if os.geteuid() == 0:
        raise ValueError("resume_build_requires_unprivileged_user")
    validate_inputs(inputs)
    payload_sha256 = inputs["payload_sha256"]
    manifest_sha256 = inputs["manifest_sha256"]
    workflow = (
        Path(__file__)
        .with_name("issue176_resume_after_backup_workflow.py")
        .read_bytes()
    )
    configuration = (json.dumps(inputs, sort_keys=True, indent=2) + "\n").encode()
    stage = STAGING + "-" + hashlib.sha256(workflow + configuration).hexdigest()[:16]
    uninstall = f"""#!/bin/sh
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
[ "$(/usr/bin/id -u)" -eq 0 ] || exit 2
stage={stage}
archive="$stage.archive"
protected() {{
 current="$1"
 while :; do
  [ ! -L "$current" ] || exit 2
  [ "$(/usr/bin/stat -c %u "$current")" -eq 0 ] || exit 2
  mode=$(/usr/bin/stat -c %a "$current")
  [ "$((0$mode & 0022))" -eq 0 ] || exit 2
  [ "$current" != / ] || break
  current=$(/usr/bin/dirname "$current")
 done
}}
protected "$0"
protected "$stage"
[ ! -e "$archive" ] && [ ! -L "$archive" ] || exit 2
# 仅原样归档本新恢复工具;不触碰runtime/账本/phase/backup/log/预算。
/usr/bin/mv "$stage" "$archive"
/usr/bin/printf '%s\n' '新恢复工具已归档；全部原部署与业务事实保持。'
""".encode()
    blobs = (
        ("workflow.py", workflow),
        ("config.json", configuration),
        ("uninstall.sh", uninstall),
    )
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in blobs}
    checks = "\n".join(f"{digest}  {name}" for name, digest in hashes.items())
    root_checks = "\n".join(
        f"{digest}  {stage}/{name}" for name, digest in hashes.items()
    )
    marker = hashlib.sha256((payload_sha256 + "\n").encode()).hexdigest()
    frozen_bytes = "\n".join(
        f"/usr/bin/printf '%s' '{base64.b64encode(data).decode()}' | "
        + f'/usr/bin/base64 --decode > "$staging/{name}"'
        for name, data in blobs
    )
    root = f"""set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
refuse() {{
 /usr/bin/printf 'owner-resume refused stage=bootstrap reason=%s\\n' "$1" >&2
 exit 2
}}
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
/usr/bin/printf '%s\\n' 'owner-resume stage=verify_runtime'
protected "$runtime"
protected /var/lib/paperradar
[ ! -e "$staging" ] && [ ! -L "$staging" ] || refuse resume_already_staged
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
/usr/bin/printf '%s\\n' 'owner-resume stage=freeze_new_payload'
/usr/bin/install -d -o root -g root -m 0755 "$staging"
# root不读取产品可写路径,从已审runner内嵌精确字节冻结,避免复制期间换链读取root文件。
{frozen_bytes}
/usr/bin/printf '%s\\n' {shlex.quote(root_checks)} | /usr/bin/sha256sum -c -
cd "$runtime"
exec /usr/bin/env -i "$runtime/python/bin/python3" -I -S -B "$staging/workflow.py"
"""
    if len(root.encode()) > 96 * 1024:
        raise ValueError("resume_bootstrap_too_large")
    runner = f"""#!/bin/sh
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
refuse() {{
 /usr/bin/printf 'owner-resume refused stage=user_preflight reason=%s\n' "$1" >&2
 exit 2
}}
[ "$#" -eq 0 ] || refuse arguments_invalid
[ "$(/usr/bin/id -u)" -ne 0 ] || refuse unprivileged_entry_required
# 本入口显式经典sudo,不改全局alternatives/sudoers/runtime。
[ ! -L /usr/bin/sudo.ws ] && [ -f /usr/bin/sudo.ws ] || refuse classic_sudo_type
[ "$(/usr/bin/stat -c %u /usr/bin/sudo.ws)" -eq 0 ] || refuse classic_sudo_owner
[ "$(/usr/bin/stat -c %h /usr/bin/sudo.ws)" -eq 1 ] || refuse classic_sudo_hardlink
[ "$(/usr/bin/stat -c %a /usr/bin/sudo.ws)" = 4755 ] || refuse classic_sudo_mode
[ -t 0 ] || refuse interactive_tty_required
package=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")" && /usr/bin/pwd -P)
(cd "$package" &&
 /usr/bin/printf '%s\n' {shlex.quote(checks)} | /usr/bin/sha256sum -c -)
exec /usr/bin/sudo.ws -k -- /bin/sh -c {shlex.quote(root)}
"""
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    for name, data in blobs:
        (output / name).write_bytes(data)
    (output / "run-resume.sh").write_text(runner)
    (output / "run-resume.sh").chmod(0o700)
    hashes["run-resume.sh"] = hashlib.sha256(runner.encode()).hexdigest()
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items())
    )
    (output / "REVIEW.md").write_text(
        "# 仅before-revoke backup后续行的owner新包（尚未执行）\n\n"
        "输入JSON只是约束,不是grant权威；完整审阅全部新脚本/config/内嵌字节/SHA256SUMS。\n"
        "先停止业务与其他准入写入；仅新包入口一次sudo.ws密码，stdin必须正常TTY，root只从内嵌字节冻结。\n"
        "精确核原runtime/payload/manifest/入口/sudoers/owner代码与原config，旧39/v4字节不改。\n"
        "原phase必须exact4只读文件及backup SHA一致；\n"
        "plan/RID/两组原active集合/无pending或revoke/有效窗口/预算/锁均复核。\n"
        "只作用域设tempfile.tempdir=/var/tmp（root:root1777且同device/mount）；\n"
        "执行原冻结v4 probe，finally恢复。\n"
        "所有EACCES/EPERM和NNP helper失败断言保持，EXDEV绝不算合格；\n"
        "不放开日志任何祖先，不删旧文件。\n"
        "只继续probe→root revoke→原backup restore；\n"
        "最后boundary本人完整审阅/手输ID一次。\n"
        "不重前两次激活/backup/cutover/receive，不compile/重装/认证/模型/网络，预算ID/代际/attempt前后完整比较。\n"
        "失败给stage/reason并保新失败检查点，不自动清理或授予；不要盲重跑。\n"
        "uninstall.sh仅把本工具root冻结目录原样归档，不删除或修改旧runtime/4文件/backup/log/ledger/budget。\n"
        f"\n执行入口：`{output / 'run-resume.sh'}`\n"
        f"卸载仅owner另行选择：`sudo.ws /bin/sh {stage}/uninstall.sh`\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="构建待审after-backup续行包,不执行sudo或读取真实root。"
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        required=True,
        help="主代理提供的只读约束元数据JSON,不含secret。",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="尚不存在的私有待审输出目录。"
    )
    args = parser.parse_args()
    try:
        build_bundle(args.output, json.loads(args.inputs.read_bytes()))
    except (OSError, ValueError):
        parser.exit(
            2, "续行包构建拒绝 [resume_inputs_invalid]；核对精确约束与新输出目录。\n"
        )
    print("新恢复包已生成；未执行root或改变任何现场事实，请owner审阅确切SHA后执行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
