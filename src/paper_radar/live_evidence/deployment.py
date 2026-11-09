"""非特权构建可审阅的封印包;此模块从不调用sudo或执行部署脚本。"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from paper_radar.live_evidence.collector import SITE_CASES
from paper_radar.live_evidence.receipt import ApprovedPlan, canonical_bytes
from paper_radar.live_evidence.sealed_runtime import RUNTIME_ROOT, SiteConfiguration

STAGING = "/var/lib/paperradar/live-evidence-staging"
EXEC = "/usr/libexec/paperradar"


# 只冻结项目锁定的运行包;主工作树可能另装Docling/dev工具,不得将它们机械装入root闭包。
RUNTIME_PACKAGES = frozenset(
    {
        "_yaml",
        "alembic",
        "annotated_doc",
        "annotated_types",
        "anyio",
        "certifi",
        "greenlet",
        "h11",
        "httpcore",
        "httpx",
        "idna",
        "mako",
        "markdown_it",
        "markupsafe",
        "mdurl",
        "packaging",
        "pydantic",
        "pydantic_core",
        "pygments",
        "rich",
        "shellingham",
        "sqlalchemy",
        "typer",
        "typing_extensions.py",
        "typing_inspection",
        "yaml",
    }
)
RUNTIME_DISTRIBUTIONS = frozenset(
    {
        "alembic",
        "annotated_doc",
        "annotated_types",
        "anyio",
        "certifi",
        "greenlet",
        "h11",
        "httpcore",
        "httpx",
        "idna",
        "mako",
        "markdown_it_py",
        "markupsafe",
        "mdurl",
        "packaging",
        "pydantic",
        "pydantic_core",
        "pygments",
        "pyyaml",
        "rich",
        "shellingham",
        "sqlalchemy",
        "typer",
        "typing_extensions",
        "typing_inspection",
    }
)


def render_sudoers(uid: int) -> str:
    if uid <= 0:
        raise ValueError("collector_product_identity")
    return (
        f'#{uid} ALL=(root) NOPASSWD: NOSETENV: {EXEC}/live-evidence-collect "", '
        f"{EXEC}/live-evidence-tighten *\n"
    )


def _shell_diagnostics(stage: str) -> str:
    # 仅输出固定阶段、对象标签和受控原因;不输出宿主路径或原始输入。
    return f"""stage={stage}
resource=script
reason=command_failed
report_failure() {{
    status=$?
    if [ "$status" -ne 0 ]; then
        format='封印操作拒绝 [%s]；stage=%s resource=%s exit=%s。'
        format="$format"'请停止，由所有者核对既有资源的属主、权限与来源，再审阅续跑方案。\\n'
        /usr/bin/printf "$format" "$reason" "$stage" "$resource" "$status" >&2
    fi
}}
trap report_failure 0
refuse() {{ reason="$1"; exit 2; }}
"""


def _guard(name: str) -> str:
    return f'''#!/bin/sh
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
staging={STAGING}
runtime={RUNTIME_ROOT}
exec_root={EXEC}
ledger=/var/lib/paperradar/live-evidence
{_shell_diagnostics("guard")}[ "$#" -eq 0 ] || refuse arguments_invalid
[ "$(/usr/bin/id -u)" -eq 0 ] || refuse root_required
[ "$0" = "{STAGING}/{name}.sh" ] || refuse execution_location
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
protected "$0"
'''


def render_intent_preflight() -> str:
    """只读支持性预检;不代替实际+a,不修改任何日志或账本。"""
    return """
stage=intent_preflight
resource=intents
[ "$(/usr/bin/uname -s)" = Linux ] || refuse intent_platform_unknown
case "$(/usr/bin/uname -m)" in
    x86_64|aarch64) ;; *) refuse intent_platform_unknown;;
esac
caps=$(/usr/bin/awk '$1 == "CapEff:" {print $2}' /proc/self/status)
case "$caps" in ''|*[!0-9a-fA-F]*) refuse intent_capability_unknown;; esac
[ "$((0x$caps & 512))" -ne 0 ] || refuse intent_capability_missing
intent_target=/var/lib/paperradar
if [ -e /var/lib/paperradar/live-evidence-intents ] ||
   [ -L /var/lib/paperradar/live-evidence-intents ]; then
    intent_target=/var/lib/paperradar/live-evidence-intents
    protected "$intent_target"
    [ -d "$intent_target" ] || refuse intent_log_untrusted
    [ "$(/usr/bin/stat -c %a "$intent_target")" = 755 ] || refuse intent_partial
    intent_file="$intent_target/pending.jsonl"
    if [ -e "$intent_file" ] || [ -L "$intent_file" ]; then
        [ ! -L "$intent_file" ] && [ -f "$intent_file" ] || refuse intent_log_untrusted
        [ "$(/usr/bin/stat -c %u "$intent_file")" -eq 0 ] || refuse intent_log_untrusted
        [ "$(/usr/bin/stat -c %g "$intent_file")" -ne 0 ] || refuse intent_log_untrusted
        [ "$(/usr/bin/stat -c %a "$intent_file")" = 660 ] || refuse intent_log_untrusted
        [ "$(/usr/bin/stat -c %h "$intent_file")" -eq 1 ] || refuse intent_log_untrusted
        [ "$(/usr/bin/stat -c %s "$intent_file")" -lt 8388608 ] ||
            refuse intent_log_full
        attributes=$(/usr/bin/lsattr -d -- "$intent_file" 2>/dev/null |
            /usr/bin/awk '{print $1}')
        case "$attributes" in *i*) refuse intent_log_untrusted;; esac
        case "$attributes" in *a*) ;; *) refuse intent_log_untrusted;; esac
    fi
fi
options=$(
    /usr/bin/findmnt --raw --noheadings --output VFS-OPTIONS --target "$intent_target"
) || refuse intent_filesystem_unavailable
case ",$options," in *,ro,*) refuse intent_filesystem_readonly;; esac
/usr/bin/lsattr -d -- "$intent_target" >/dev/null 2>&1 ||
    refuse intent_filesystem_unavailable
"""


def render_deploy(
    payload_sha256: str, plan_id: str = "site-beta", *, owner_closure: bool = False
) -> str:
    if len(payload_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in payload_sha256
    ):
        raise ValueError("payload_digest_invalid")
    if not re.fullmatch(r"site-beta(?:-[0-9a-f]{12})?", plan_id):
        raise ValueError("plan_id_invalid")
    return (
        _guard("deploy")
        + render_intent_preflight()
        + f"""
stage=payload_check
resource=payload
protected "$staging/payload.tar"
digest=$(/usr/bin/sha256sum "$staging/payload.tar" | /usr/bin/cut -d ' ' -f 1)
[ "$digest" = '{payload_sha256}' ] || refuse payload_digest
# 存在的目标先核信任再触及,不能把普通用户目录chown成信任根。
stage=preflight
resource=deployment_path
for path in /usr/libexec /var/lib /etc/sudoers.d /srv; do protected "$path"; done
if [ -e "$runtime" ] || [ -L "$runtime" ]; then protected "$runtime"; fi
for path in $exec_root /var/lib/paperradar $ledger $ledger/inbox /srv/pi-cwd; do
    resource=deployment_path
    [ "$path" != /srv/pi-cwd ] || resource=cwd
    if [ -e "$path" ] || [ -L "$path" ]; then protected "$path"; fi
done
stage=runtime_install
resource=runtime
/usr/bin/printf '%s\\n' 'G2 stage=runtime_install'
/usr/bin/install -d -o root -g root -m 0755 $exec_root
[ ! -e $runtime.new ] && [ ! -L $runtime.new ] || refuse runtime_pending
if [ -e $runtime ]; then
    protected $runtime
    [ "$(/usr/bin/cat $runtime/payload.sha256)" = '{payload_sha256}' ] ||
        refuse runtime_identity
else
    /usr/bin/install -d -o root -g root -m 0755 $runtime.new
    cd $runtime.new
    /usr/bin/tar -xf "$staging/payload.tar" --no-same-owner --no-same-permissions
    /usr/bin/chown -R root:root $runtime.new
    /usr/bin/find $runtime.new -type d -exec /usr/bin/chmod 0755 {{}} +
    /usr/bin/find $runtime.new -type f -exec /usr/bin/chmod go-w {{}} +
    /usr/bin/printf '%s\\n' '{payload_sha256}' > $runtime.new/payload.sha256
    /usr/bin/mv $runtime.new $runtime
fi
stage=runtime_verify
(cd $runtime && /usr/bin/sha256sum --strict -c manifest.sha256 >/dev/null)
/usr/sbin/visudo -cf $runtime/sudoers
stage=ledger_prepare
resource=ledger
/usr/bin/install -d -o root -g root -m 0755 $ledger $ledger/inbox
protected $ledger/inbox
stage=intent_prepare
resource=intents
/usr/bin/printf '%s\n' 'G2 stage=intent_prepare'
# 仅owner部署路径,不在NOPASSWD helper中。旧资格先cutover,不读取普通pending。
/bin/sh "$runtime/wrappers/owner" provision-intents
stage=cwd_prepare
resource=cwd
if [ ! -e /srv/pi-cwd ]; then
    /usr/bin/install -d -o root -g root -m 0755 /srv/pi-cwd
    /usr/bin/touch $ledger/cwd-created-by-beta
fi
[ -z "$(/usr/bin/find /srv/pi-cwd -mindepth 1 -maxdepth 1 -print -quit)" ] ||
    refuse cwd_not_empty
stage=entry_install
resource=entry
for entry in collect tighten owner; do
    target=$exec_root/live-evidence-$entry
    if [ -e "$target" ] || [ -L "$target" ]; then
        protected "$target"
        /usr/bin/cmp "$target" "$runtime/wrappers/$entry" || refuse entry_conflict
    else
        /usr/bin/install -o root -g root -m 0755 "$runtime/wrappers/$entry" "$target"
    fi
done
stage=policy
resource=sudoers
policy=/etc/sudoers.d/paperradar-live-evidence
if [ -e "$policy" ] || [ -L "$policy" ]; then
    protected "$policy"
    /usr/bin/cmp "$policy" $runtime/sudoers || refuse policy_conflict
else
    /usr/bin/install -o root -g root -m 0440 $runtime/sudoers "$policy"
fi
stage=collect
resource=collector
/usr/bin/printf '%s\\n' 'G2 stage=collect'
$exec_root/live-evidence-collect
# 本次sudo部署命令包含所有者对固定计划/接收的明确授权;不激活。
plan=$ledger/inbox/{plan_id}-plan.json
source=$ledger/inbox/{plan_id}-round-1.json
stage=receive
resource=receipt
/usr/bin/printf '%s\\n' 'G2 stage=receive'
$exec_root/live-evidence-owner receive --plan "$plan" --source "$source"
"""
        + (
            "\nstage=owner_closure\nresource=owner_closure\n"
            'exec /usr/bin/env -i "$runtime/python/bin/python3" -I -S -B '
            '"$runtime/owner-closure.py"\n'
            if owner_closure
            else ""
        )
    )


def render_upgrade(old_payload_sha256: str, old_manifest_sha256: str) -> str:
    """仅归档明确审阅的旧字节;不删除历史或自动覆盖中断状态。"""
    for digest in (old_payload_sha256, old_manifest_sha256):
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("upgrade_identity_invalid")
    marker_sha256 = hashlib.sha256((old_payload_sha256 + "\n").encode()).hexdigest()
    return (
        _guard("upgrade")
        + render_intent_preflight()
        + f"""
stage=upgrade_preflight
resource=deployment_path
protected "$staging/deploy.sh"
for path in "$ledger" "$ledger/inbox" /srv/pi-cwd; do
    protected "$path"
    [ -d "$path" ] || refuse protected_directory
done
resource=cwd
[ "$(/usr/bin/stat -c %a /srv/pi-cwd)" = 755 ] || refuse cwd_state_unexpected
[ -z "$(/usr/bin/find /srv/pi-cwd -mindepth 1 -maxdepth 1 -print -quit)" ] ||
    refuse cwd_not_empty
resource=old_runtime
protected "$runtime"
protected "$runtime/payload.sha256"
protected "$runtime/manifest.sha256"
digest=$(/usr/bin/sha256sum "$runtime/payload.sha256" | /usr/bin/cut -d ' ' -f 1)
[ "$digest" = '{marker_sha256}' ] || refuse old_payload_identity
digest=$(/usr/bin/sha256sum "$runtime/manifest.sha256" | /usr/bin/cut -d ' ' -f 1)
[ "$digest" = '{old_manifest_sha256}' ] || refuse old_manifest_identity
# 完整成员集合须等于原manifest及其目录闭包,不能忽略额外文件/目录。
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
for entry in collect tighten owner; do
    target=$exec_root/live-evidence-$entry
    protected "$target"
    [ -f "$target" ] && [ "$(/usr/bin/stat -c %h "$target")" -eq 1 ] ||
        refuse entry_type
    [ "$(/usr/bin/stat -c %a "$target")" = 755 ] || refuse entry_mode
    /usr/bin/cmp "$target" "$runtime/wrappers/$entry" || refuse entry_conflict
done
policy=/etc/sudoers.d/paperradar-live-evidence
protected "$policy"
[ "$(/usr/bin/stat -c %a "$policy")" = 440 ] || refuse policy_mode
[ -f "$policy" ] && [ "$(/usr/bin/stat -c %h "$policy")" -eq 1 ] || refuse policy_type
/usr/bin/cmp "$policy" "$runtime/sudoers" || refuse policy_conflict
archive="$runtime.archive-{old_payload_sha256}"
[ ! -e "$archive" ] && [ ! -L "$archive" ] || refuse archive_exists
[ ! -e "$runtime.new" ] && [ ! -L "$runtime.new" ] || refuse runtime_pending
stage=upgrade_archive
/usr/bin/mv "$runtime" "$archive"
# 仅移除刚与旧冻结副本逐字节核过的入口/策略;原字节完整留在archive。
for entry in collect tighten owner; do
    /usr/bin/rm "$exec_root/live-evidence-$entry"
done
/usr/bin/rm "$policy"
stage=upgrade_deploy
/bin/sh "$staging/deploy.sh"
message='封印升级完成：旧runtime已归档，新计划已采集接收；G3证据激活未执行。'
/usr/bin/printf '%s\\n' "$message"
"""
    )


def render_uninstall() -> str:
    return (
        _guard("uninstall")
        + """
stage=uninstall
resource=entry
# 默认只移除本包部署物;账本、inbox回执、失败历史与staging永久保留。
for entry in collect tighten owner; do
    target=$exec_root/live-evidence-$entry
    if [ -e "$target" ] || [ -L "$target" ]; then
        protected "$target"
        /usr/bin/cmp "$target" "$runtime/wrappers/$entry" || refuse entry_conflict
    fi
done
stage=policy
resource=sudoers
policy=/etc/sudoers.d/paperradar-live-evidence
if [ -e "$policy" ] || [ -L "$policy" ]; then
    protected "$policy"
    /usr/bin/cmp "$policy" $runtime/sudoers || refuse policy_conflict
    /usr/bin/rm "$policy"
fi
for entry in collect tighten owner; do
    /usr/bin/rm -f $exec_root/live-evidence-$entry
done
if [ -e $ledger/cwd-created-by-beta ]; then
    protected $ledger/cwd-created-by-beta
    if [ -e /srv/pi-cwd ]; then
        protected /srv/pi-cwd
        /usr/bin/rmdir /srv/pi-cwd
    fi
    /usr/bin/rm $ledger/cwd-created-by-beta
fi
if [ -e $runtime ]; then
    protected $runtime
    /usr/bin/rm -rf $runtime
fi
/usr/bin/printf '%s\\n' '已卸载部署物；账本、回执、失败历史与staging保留。'
"""
    )


def _wrapper(action: str) -> bytes:
    # 环境和cwd固定; -I -S禁用PYTHONPATH/user-site/.pth/sitecustomize。
    return f"""#!/bin/sh
set -eu
runtime={RUNTIME_ROOT}
cd $runtime
/usr/bin/sha256sum --strict -c manifest.sha256 >/dev/null
set -- $runtime/entry.py {action} "$@"
exec /usr/bin/env -i $runtime/python/bin/python3 -I -S -B "$@"
""".encode()


def freeze_runtime(target: Path, source_root: Path) -> None:
    """只在非特权构建期复制;不执行复制品,不保留软链/.pth/bytecode。"""
    if os.geteuid() == 0:
        raise ValueError("build_requires_unprivileged_user")
    python = target / "python"
    (python / "bin").mkdir(parents=True)
    shutil.copy2(Path(sys.executable).resolve(), python / "bin/python3")
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    shutil.copytree(
        sysconfig.get_path("stdlib"),
        python / "lib" / version,
        ignore=shutil.ignore_patterns(
            "__pycache__", "site-packages", "dist-packages", "test", "tests"
        ),
    )
    packages = target / "site-packages"
    packages.mkdir()
    original = Path(sysconfig.get_path("purelib"))
    for item in original.iterdir():
        distribution = (
            item.name.split("-", 1)[0] if item.name.endswith(".dist-info") else None
        )
        if (
            item.name not in RUNTIME_PACKAGES
            and distribution not in RUNTIME_DISTRIBUTIONS
        ):
            continue
        if item.is_dir():
            shutil.copytree(
                item,
                packages / item.name,
                ignore=shutil.ignore_patterns("__pycache__", "tests", "test"),
            )
        elif item.is_file():
            shutil.copy2(item, packages / item.name)
    shutil.copytree(
        source_root / "src/paper_radar",
        packages / "paper_radar",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    # _yaml扩展可缺省,PyYAML提供纯Python路径;_distutils_hack不执行。
    (target / "entry.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "root = Path(__file__).parent\n"
        "sys.path.insert(0, str(root / 'site-packages'))\n"
        "from paper_radar.live_evidence.sealed_runtime import runtime_main\n"
        "raise SystemExit(runtime_main())\n"
    )
    (target / "wrappers").mkdir()
    for name, action in (
        ("collect", "collect"),
        ("tighten", "tighten"),
        ("owner", "owner"),
    ):
        path = target / "wrappers" / name
        path.write_bytes(_wrapper(action))
        path.chmod(0o755)


def file_digests(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("runtime_symlink_forbidden")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def render_cwd_preparation(product_uid: int, product_gid: int) -> str:
    """仅生成供owner另行审阅的固定空cwd预配;普通deploy不调用。"""
    if product_uid <= 0 or product_gid <= 0:
        raise ValueError("collector_product_identity")
    return f"""set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
{_shell_diagnostics("owner_cwd_prepare")}resource=cwd
[ "$(/usr/bin/id -u)" -eq 0 ] || refuse root_required
current=/srv
while :; do
    [ ! -L "$current" ] || refuse protected_symlink
    [ -d "$current" ] || refuse protected_directory
    [ "$(/usr/bin/stat -c %u "$current")" -eq 0 ] || refuse protected_owner
    mode=$(/usr/bin/stat -c %a "$current")
    [ "$((0$mode & 0022))" -eq 0 ] || refuse protected_mode
    [ "$current" != / ] || break
    current=$(/usr/bin/dirname "$current")
done
cwd=/srv/pi-cwd
[ ! -L "$cwd" ] || refuse cwd_symlink
[ -d "$cwd" ] || refuse cwd_directory
owner=$(/usr/bin/stat -c %u "$cwd")
group=$(/usr/bin/stat -c %g "$cwd")
mode=$(/usr/bin/stat -c %a "$cwd")
# 只接受审阅的产品目录状态,或本命令已经完成的root:root0755状态。
if [ "$owner:$group:$mode" = '{product_uid}:{product_gid}:700' ]; then
    entries=$(/usr/bin/find "$cwd" -mindepth 1 -maxdepth 1 -print -quit) ||
    refuse cwd_unreadable
    [ -z "$entries" ] || refuse cwd_not_empty
    /usr/bin/chown root:root "$cwd"
    /usr/bin/chmod 0755 "$cwd"
elif [ "$owner:$group:$mode" != '0:0:755' ]; then
    refuse cwd_state_unexpected
fi
# 先改变属主封闭产品写入,再复核;竞态留下的成员一律保留并拒绝续跑。
[ ! -L "$cwd" ] || refuse cwd_symlink
owner=$(/usr/bin/stat -c %u "$cwd")
group=$(/usr/bin/stat -c %g "$cwd")
mode=$(/usr/bin/stat -c %a "$cwd")
[ "$owner:$group:$mode" = '0:0:755' ] || refuse cwd_state_unexpected
entries=$(/usr/bin/find "$cwd" -mindepth 1 -maxdepth 1 -print -quit) ||
    refuse cwd_unreadable
[ -z "$entries" ] || refuse cwd_not_empty
"""


G2_ROOT_FILES = ("deploy.sh", "uninstall.sh", "owner-workflow.sh", "payload.tar")


def render_owner_workflow(product_uid: int, product_gid: int) -> str:
    return (
        _guard("owner-workflow")
        + "/usr/bin/printf '%s\\n' 'G2 stage=owner_cwd_prepare'\n"
        + render_cwd_preparation(product_uid, product_gid)
        + f'''
stage=deploy
resource=deployment
/usr/bin/printf '%s\\n' 'G2 stage=deploy'
/bin/sh "{STAGING}/deploy.sh"
/usr/bin/printf '%s\\n' 'G2完成：部署、β采集与接收已返回成功；G3证据激活未执行。'
'''
    )


def render_bootstrap(
    digests: dict[str, str],
    *,
    sealed_files: dict[str, bytes],
    owner_workflow: bool = True,
    progress: bool = True,
    upgrade: bool = False,
    interactive: bool = False,
) -> str:
    names = (
        G2_ROOT_FILES
        if owner_workflow
        else ("deploy.sh", "uninstall.sh", "payload.tar")
    )
    if upgrade:
        names = (*names, "upgrade.sh")
    frozen = []
    for name in names:
        data = sealed_files[name]
        if hashlib.sha256(data).hexdigest() != digests[name]:
            raise ValueError("sealed_source_digest")
        encoded = base64.encodebytes(data).decode("ascii")
        frozen.append(
            f"/usr/bin/base64 --decode > \"$staging/{name}\" <<'FROZEN_BYTES'\n"
            + encoded
            + "FROZEN_BYTES\n"
        )
    frozen_bytes = "".join(frozen)
    checks = "\n".join(f"{digests[name]}  {STAGING}/{name}" for name in names)
    entry = "upgrade" if upgrade else "owner-workflow" if owner_workflow else "deploy"
    announce = "/usr/bin/printf '%s\\n' 'G2 stage=root_copy'\n" if progress else ""
    return f"""set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
{_shell_diagnostics("bootstrap")}staging={STAGING}
{announce}protected() {{
  path="$1"
  while :; do
    [ ! -L "$path" ] || refuse protected_symlink
    [ "$(/usr/bin/stat -c %u "$path")" -eq 0 ] || refuse protected_owner
    mode=$(/usr/bin/stat -c %a "$path")
    [ "$((0$mode & 0022))" -eq 0 ] || refuse protected_mode
    [ "$path" != / ] || break
    path=$(/usr/bin/dirname "$path")
  done
}}
for path in /var /var/lib /var/lib/paperradar "$staging"; do
  if [ -e "$path" ] || [ -L "$path" ]; then protected "$path"; fi
done
/usr/bin/install -d -o root -g root -m 0755 "$staging"
for name in {" ".join(names)}; do
  [ ! -L "$staging/$name" ] || refuse protected_symlink
  if [ -e "$staging/$name" ]; then
    protected "$staging/$name"
    [ -f "$staging/$name" ] || refuse protected_type
    [ "$(/usr/bin/stat -c %h "$staging/$name")" -eq 1 ] || refuse protected_hardlink
  fi
done
# 字节已冻结在入口的stdin脚本中;root从不打开产品可换链来源。
{frozen_bytes}
stage=root_hash
resource=sealed_files
/usr/bin/printf '%s\\n' {shlex.quote(checks)} | /usr/bin/sha256sum -c -
exec /bin/sh "$staging/{entry}.sh"{" </dev/tty" if interactive else ""}
"""


def render_g2_runner(
    digests: dict[str, str],
    *,
    sealed_files: dict[str, bytes],
    upgrade: bool = False,
    owner_closure: bool = False,
) -> str:
    names = (*G2_ROOT_FILES, "upgrade.sh") if upgrade else G2_ROOT_FILES
    checks = "\n".join(f"{digests[name]}  {name}" for name in names)
    bootstrap = render_bootstrap(
        digests, sealed_files=sealed_files, upgrade=upgrade, interactive=owner_closure
    )
    announcement = (
        "封印升级：只请求一次sudo密码，核旧身份并归档后部署；不执行G3。"
        if upgrade
        else "G2：只请求一次sudo密码，自动预配空cwd并部署；不执行G3。"
    )
    if owner_closure:
        announcement = (
            "集成所有者流程：一次sudo密码，cutover后新证据需本人手动确认；不自动激活。"
        )
    return f"""#!/bin/sh
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
{_shell_diagnostics("package_check")}[ "$#" -eq 0 ] || refuse arguments_invalid
[ "$(/usr/bin/id -u)" -ne 0 ] || refuse unprivileged_entry_required
package=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")" && /usr/bin/pwd -P)
/usr/bin/printf '%s\\n' 'G2 stage=package_check'
(cd "$package" &&
    /usr/bin/printf '%s\\n' {shlex.quote(checks)} | /usr/bin/sha256sum -c -)
/usr/bin/printf '%s\\n' {shlex.quote(announcement)}
# heredoc经stdin传输冻结字节,大payload不进入exec argv（单参数上限）。
exec /usr/bin/sudo -k /bin/sh -s <<'FROZEN_BOOTSTRAP'
{bootstrap}FROZEN_BOOTSTRAP
"""


def render_review(
    target: Path, digests: dict[str, str], site: SiteConfiguration, plan: ApprovedPlan
) -> str:
    checks = "\n".join(
        f"{digests[name]}  {name}" for name in ("run-g2.sh", *G2_ROOT_FILES)
    )
    return f"""# G2 私有封印审阅材料

本目录含当前站点私有路径，请勿贴到公开工单。
build-identity.json记录源HEAD/tree/dirty、绝对worktree、Python/lock、源码与payload身份。
最终主树重建后核对身份与新SHA；旧包批准不能迁移，生成本说明不是所有者批准。
先审阅run-g2.sh、owner-workflow.sh、deploy.sh、uninstall.sh和payload中的entry/wrappers、
site/plan、sudoers、manifest.sha256、冻结Python/依赖/源码。所有字节变化均重新审阅。

- 产品uid/gid：{site.product_uid}/{site.product_gid}；声明上下文：{site.use_id}。
- 独立主张：{", ".join(site.claim_uses or (site.use_id,))}。
- 计划：{plan.plan_id}；
  UTC窗口：{plan.starts_at.isoformat()} → {plan.ends_at.isoformat()}。
- 单轮、首失败停，认证/模型/网络预算均0；不自动激活，β模型/RPC/IPv4/observer仍unknown。
- 所有者仍须私下确认产品用户无等价root组/能力/任意sudo通道；宿主细节不公开。
- sudoers仅固定零参数collect与仅收紧tighten；owner放宽入口不在NOPASSWD中。

```text
{checks}
```

审阅通过后，只运行下面一个普通用户入口，输入一次sudo密码，其他步骤由脚本执行。
没有额外read确认、手动chown或复制命令；不要再单独运行旧G2命令。

```sh
{shlex.quote(str(target / "run-g2.sh"))}
```

run-g2先核包内四件固定SHA，再一次sudo -k从入口内嵌精确字节冻结到root所有staging，
复核同四SHA；
大payload经stdin脚本传输而非exec参数；root不打开用户可换链来源，
只从root冻结owner-workflow执行，不从repo、.venv、PYTHONPATH或用户环境运行代码。
owner-workflow先校验自身位置/保护链，再显式预配固定/srv/pi-cwd，随后调用原deploy/collect/receive。
固定cwd仅接受{site.product_uid}:{site.product_gid}:0700无链接空目录，或已预配root:root0755空目录；
完整祖先须root所有且组/其他不可写。其他属主、组、模式、链接、非空或不安全祖先均拒绝。
经此次明确审阅，由冻结workflow执行chown root:root/chmod0755，复核保护与空目录后才继续。
后检出现竞态成员则保留全部数据并停止，不删除、移动、读取成员内容或自动回滚属主。
普通deploy不接管用户目录；owner预配cwd默认卸载保留。不会重装Pi或改写EXP2业务库。

脚本持续输出stage与结果；receive返回实际receipt_id，成功末行明确“G3证据激活未执行”。
SHA OK只证明对应复制校验，不是部署/采集/接收终态。
拒绝给出受控原因、固定stage/resource与退出码。
任何失败安全停止；runtime.new不自动删除，不同payload的既有runtime不覆盖，须owner核对旧部署再处理。
账本/回执/计划/失败历史/stopped/撤销/预算均保留；新包不自动重放已停止计划或恢复旧激活。
本次owner流程仅G2，不接受自由参数。只有成功终态和receipt_id才表示G2推进；仍不等于产品可执行。

G3由所有者另行逐格操作，不由本脚本执行。使用实际receipt_id，重采60秒当前观察后短ID确认：

```sh
sudo /usr/libexec/paperradar/live-evidence-collect
owner=/usr/libexec/paperradar/live-evidence-owner
sudo -k "$owner" activate --receipt-id ACTUAL_RECEIPT_ID --use-id {site.use_id}
```

当前观察不续原verified_at；六格分别选择与确认，高档模型实际行为没有因此被核验。
AUTH_CACHE_BASELINE包含credentials全根及node-compile-cache全部stat；正常写入会漂移并拒绝。
新基线须新受信计划、重新审阅封印和人工激活；不静默排除成员或刷新旧回执原时点。
失败刷新封闭mode000当前观察并先持久收紧旧用途；落账失败保留待收紧，stopped计划不重试探针。

默认卸载使用同一封印副本，保留账本、回执、失败历史、staging和owner预配cwd：

```sh
sudo /bin/sh {STAGING}/uninstall.sh
```

本包生成未执行真实sudo、部署/collector/receive、认证/模型/网络或证据激活；完整门禁留后继。
"""


def render_upgrade_review(
    target: Path,
    digests: dict[str, str],
    site: SiteConfiguration,
    plan: ApprovedPlan,
    upgrade_from: tuple[str, str],
) -> str:
    checks = "".join(f"{digest}  {name}\n" for name, digest in digests.items())
    return f"""# 所有者封印升级审阅

这是新的root字节批准，旧G2批准不迁移。本目录含私有站点路径，请勿公开。
请完整审阅run-upgrade.sh、upgrade.sh、deploy.sh、owner-workflow.sh、uninstall.sh、
payload中的Python/依赖/源码、entry/wrappers、site/plan/sudoers/manifest和SHA256SUMS。
build-identity.json绑定本次HEAD/tree/dirty、Python/lock/source/payload及旧身份。

- 旧payload必须为{upgrade_from[0]}。
- 旧manifest.sha256文件的SHA256必须为{upgrade_from[1]}。
- 完整保护链、文件/目录集合、每个旧文件哈希、属主、权限、无链接/硬链均核验，
  三个旧入口和sudoers也分别校验。
- 旧runtime原样移动到同级live-evidence-runtime.archive-旧payloadSHA；不覆盖已有归档。
- 只移除已与旧冻结副本核过的入口/sudoers，原字节仍留在归档中，再执行新冻结deploy。
- 不改变cwd属主，不重装Pi，不compile或写EXP2业务库。保留ledger/inbox/旧回执/计划、
  撤销、stopped、失败历史及预算；新collector/plan不复活旧资格。
- 未知/篡改/不完整状态拒绝，中断不自动回滚、删除归档或重试。
  升级成功后再次运行同包也安全拒绝；
  owner先核现场再决定恢复，不得盲删runtime或归档。普通deploy仍拒不同payload。
- sudoers仍只允许固定零参数collect和收紧tighten；owner放宽入口不在NOPASSWD中。
  所有者仍须确认产品用户没有等价root组/能力/任意sudo通道。

新计划{plan.plan_id}，窗口{plan.starts_at.isoformat()} → {plan.ends_at.isoformat()}；
独立主张{", ".join(site.claim_uses or (site.use_id,))}；
单轮/首失败停/认证模型网络预算全0。
新runtime来自本次root冻结副本，执行会采集并接收新的实际回执，绝不自动激活。
旧回执仍保留旧原时点，不假称旧回执已由新代码核验。模型/RPC/IPv4/observer仍unknown。

完整审阅上述新字节后，只运行下面普通用户入口并输入一次sudo密码；其余复制/核验/升级/采集/接收由脚本完成：

```sh
{shlex.quote(str(target / "run-upgrade.sh"))}
```

入口先核包内固定SHA，再一次sudo -k复制到root所有staging并复核，只从root冻结upgrade运行。
不从repo/.venv导入或执行root代码，不调用旧runtime代码。只有升级成功终态及新receipt_id才表示本步完成。

G3仍由所有者另行执行。采用上一步实际返回的新receipt_id，完整审阅并本人手动输入短ID：

```sh
sudo /usr/libexec/paperradar/live-evidence-collect
owner=/usr/libexec/paperradar/live-evidence-owner
sudo -k "$owner" activate --receipt-id ACTUAL_RECEIPT_ID --use-id {site.use_id}
```

手动确认后固定collector真实刷新观察，同一绑定、覆盖与审核内容才写入；阅读可以超过60秒，
当前观察TTL仍60秒，刷新不续原verified_at或期限。事实改变/撤销/到期/时钟回退仍拒绝。
credentials全根含node-compile-cache全部stat，无正常写入例外；不得删除必要项或把unknown当通过。
默认新uninstall保留归档、账本/回执/计划/失败/stopped/撤销历史。G3与完整门禁仍未由离线包完成。
本包生成未执行真实sudo/collect/receive/revoke/activate、认证、模型或网络。

```text
{checks}```
"""


def render_integrated_review(
    target: Path,
    digests: dict[str, str],
    site: SiteConfiguration,
    plan: ApprovedPlan,
    upgrade_from: tuple[str, str] | None,
) -> str:
    runner = "run-upgrade.sh" if upgrade_from else "run-g2.sh"
    return f"""# 所有者cutover与收口集成审阅包（尚未执行）

审阅全部脚本、入口内嵌字节和payload中的冻结Python/依赖/源码/owner-closure.py/json、site/plan/manifest/sudoers。
旧runtime要求{upgrade_from or "新部署"}，只核后原样归档；
未知/部分状态拒绝，不盲删或自动回滚。
先暂停业务及其他准入写入，确认本产品uid无等价root权限。仅本人审阅确切字节后运行：

`{shlex.quote(str(target / runner))}`

唯一sudo密码边界后root只执行内嵌冻结字节，不打开用户可换链来源。
先核/准备固定root只追加日志；首次cutover使全部旧激活失效并永久撤销旧回执六格，保历史/原verified_at/预算。
日志0660/root:产品gid、目录0755、FS_APPEND_FL；缺失/未知/不支持/满/损坏均拒绝，不清空轮转或恢复旧文件。
新计划{plan.plan_id}窗口{plan.starts_at.isoformat()} → {plan.ends_at.isoformat()}；
六格独立主张、单轮首失败停、认证/模型/网络全0。
只按本次新计划唯一受信回执继续，不重启旧stopped计划，不拿旧v3证明新策略。
本人完整审阅并手输实际短ID激活boundary-low，再本人确认临时value-low；不自动传入或生成确认。
备份后fork降至产品uid，实际验证删除/截断/覆盖/替换/硬链/清旗标均EACCES或EPERM。
仅该子进程设置NNP使固定sudo helper不可提权，正式request_revocation持久追加本格意图，
必须观察helper失败；新进程共享投影须拒绝。
随后root固定helper撤销value-low，合并恢复备份核旧活全部失效、日志拒绝保留；最后本人重新审阅/手输ID激活boundary-low。
每次激活前/确认后真实刷新60秒观察，不能续原verified_at。最终非空站点分项active+qualified才写root安全回执。
业务库仅必要预算ID/代际/计数只读元数据，拒sidecar，不读payload/auth/cache正文，不compile/重装Pi。
每阶段root检查点持久保留；任何失败停止，不自动清理、回滚或授予。NNP仅子进程，不改变root/sudoers配置。
收口包只作当前现场OS和生命周期验证；模型/RPC/IPv4/observer缺口仍阻断，不表示Live/B完成。
默认卸载保留账本/回执/原runtime归档/日志/失败/停止/预算；新权限字节仍P5本人审阅执行。

```text
{"".join(f"{digest}  {name}\n" for name, digest in digests.items())}```
"""


def build_deployment(
    target: Path,
    site: SiteConfiguration,
    *,
    starts_at: datetime,
    ends_at: datetime,
    source_root: Path,
    upgrade_from: tuple[str, str] | None = None,
    owner_closure: bool = False,
) -> dict[str, str]:
    """新目录输出确切review artifacts;窗口与现场身份由所有者入口提供。"""
    if starts_at.tzinfo is None or ends_at.tzinfo is None or starts_at >= ends_at:
        raise ValueError("plan_window_invalid")
    if upgrade_from is not None:
        render_upgrade(*upgrade_from)
    if owner_closure and set(site.claim_uses or (site.use_id,)) != {
        "boundary-low",
        "boundary-high",
        "value-low",
        "value-high",
        "read-low",
        "read-high",
    }:
        raise ValueError("closure_claim_uses")
    starts_at = starts_at.astimezone(UTC)
    ends_at = ends_at.astimezone(UTC)
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="paperradar-seal-") as temporary:
        frozen = Path(temporary)
        freeze_runtime(frozen, source_root)
        if owner_closure:
            (frozen / "owner-closure.py").write_bytes(
                (source_root / "scripts/issue176_closure_workflow.py").read_bytes()
            )
        collector_digest = hashlib.sha256(
            json.dumps(
                file_digests(frozen), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        plan_key = hashlib.sha256(
            canonical_bytes(site)
            + collector_digest.encode()
            + starts_at.isoformat().encode()
            + ends_at.isoformat().encode()
        ).hexdigest()[:12]
        plan = ApprovedPlan(
            format_version="v1",
            plan_id=f"site-beta-{plan_key}",
            kind="site_beta",
            collector_sha256=collector_digest,
            cases=SITE_CASES,
            starts_at=starts_at,
            ends_at=ends_at,
            max_auth_calls=0,
            max_model_calls=0,
            max_network_requests=0,
            max_rounds=1,
            stop_on_first_failure=True,
        )
        if owner_closure:
            (frozen / "owner-closure.json").write_text(
                json.dumps(
                    {
                        "plan_id": plan.plan_id,
                        "drill_use": "value-low",
                        "final_use": "boundary-low",
                        "admission_policy": "pi-admission-v4",
                        "initial_activation": "required",
                        "protected_log_probe": "required",
                        "run_name": "closure-" + plan_key,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        (frozen / "plan.json").write_bytes(canonical_bytes(plan))
        (frozen / "site.json").write_bytes(canonical_bytes(site))
        (frozen / "sudoers").write_text(render_sudoers(site.product_uid))
        digests = file_digests(frozen)
        (frozen / "manifest.sha256").write_text(
            "".join(f"{digest}  {name}\n" for name, digest in digests.items())
        )
        # 无软链/设备/绝对路径;所有成员显式排序,owner与mtime规范化。
        with tarfile.open(target / "payload.tar", "w") as archive:
            for path in sorted(frozen.rglob("*")):
                info = archive.gettarinfo(
                    str(path), path.relative_to(frozen).as_posix()
                )
                info.uid = info.gid = info.mtime = 0
                info.mode = 0o755 if path.is_dir() or info.mode & 0o111 else 0o644
                info.uname = info.gname = "root"
                if path.is_file():
                    with path.open("rb") as source:
                        archive.addfile(info, source)
                else:
                    archive.addfile(info)
        (target / "approved-plan.json").write_bytes(canonical_bytes(plan))
        (target / "site.json").write_bytes(canonical_bytes(site))
    payload_digest = hashlib.sha256((target / "payload.tar").read_bytes()).hexdigest()
    (target / "deploy.sh").write_text(
        render_deploy(payload_digest, plan.plan_id, owner_closure=owner_closure)
    )
    (target / "uninstall.sh").write_text(render_uninstall())
    owner_workflow = render_owner_workflow(site.product_uid, site.product_gid)
    if owner_closure:
        owner_workflow = owner_workflow.replace(
            "G2完成：部署、β采集与接收已返回成功；G3证据激活未执行。",
            "所有者集成收口流程返回成功；以root安全回执为准。",
        )
    (target / "owner-workflow.sh").write_text(owner_workflow)
    if upgrade_from is not None:
        upgrade_script = render_upgrade(*upgrade_from)
        if owner_closure:
            upgrade_script = upgrade_script.replace(
                "G3证据激活未执行", "所有者集成收口结果以root安全回执为准"
            )
        (target / "upgrade.sh").write_text(upgrade_script)
    runner = "run-upgrade.sh" if upgrade_from is not None else "run-g2.sh"
    (target / runner).write_text(
        render_g2_runner(
            file_digests(target),
            sealed_files={
                name: (target / name).read_bytes()
                for name in (
                    (*G2_ROOT_FILES, "upgrade.sh") if upgrade_from else G2_ROOT_FILES
                )
            },
            upgrade=upgrade_from is not None,
            owner_closure=owner_closure,
        )
    )
    (target / runner).chmod(0o755)

    def git_identity(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(source_root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    identity = {
        "format_version": 1,
        "source_worktree": str(source_root.resolve()),
        "git_head": git_identity("rev-parse", "HEAD"),
        "git_tree": git_identity("rev-parse", "HEAD^{tree}"),
        "git_status": git_identity("status", "--porcelain", "--untracked-files=normal"),
        "source_python_sha256": {
            name: digest
            for name, digest in file_digests(source_root / "src/paper_radar").items()
            if name.endswith(".py")
        },
        "uv_lock_sha256": hashlib.sha256(
            (source_root / "uv.lock").read_bytes()
        ).hexdigest(),
        "python_executable_sha256": hashlib.sha256(
            Path(sys.executable).resolve().read_bytes()
        ).hexdigest(),
        "collector_sha256": collector_digest,
        "payload_sha256": payload_digest,
    }
    if upgrade_from is not None:
        identity["upgrade_from"] = {
            "payload_sha256": upgrade_from[0],
            "manifest_sha256": upgrade_from[1],
        }
    (target / "build-identity.json").write_text(
        json.dumps(identity, sort_keys=True, indent=2) + "\n"
    )
    digests = file_digests(target)
    review_text = (
        render_review(target, digests, site, plan)
        if upgrade_from is None
        else render_upgrade_review(target, digests, site, plan, upgrade_from)
    )
    if owner_closure:
        review_text = render_integrated_review(
            target, digests, site, plan, upgrade_from
        )
    (target / "REVIEW.md").write_text(review_text)
    digests = file_digests(target)
    (target / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in digests.items())
    )
    return digests
