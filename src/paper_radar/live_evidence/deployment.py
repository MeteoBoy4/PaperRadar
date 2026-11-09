"""非特权构建可审阅的封印包;此模块从不调用sudo或执行部署脚本。"""

from __future__ import annotations

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
[ "$#" -eq 0 ] || exit 2
[ "$(/usr/bin/id -u)" -eq 0 ] || exit 2
[ "$0" = "{STAGING}/{name}.sh" ] || exit 2
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
'''


def render_deploy(payload_sha256: str, plan_id: str = "site-beta") -> str:
    if len(payload_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in payload_sha256
    ):
        raise ValueError("payload_digest_invalid")
    if not re.fullmatch(r"site-beta(?:-[0-9a-f]{12})?", plan_id):
        raise ValueError("plan_id_invalid")
    return (
        _guard("deploy")
        + f"""
protected "$staging/payload.tar"
digest=$(/usr/bin/sha256sum "$staging/payload.tar" | /usr/bin/cut -d ' ' -f 1)
[ "$digest" = '{payload_sha256}' ] || exit 2
# 存在的目标先核信任再触及,不能把普通用户目录chown成信任根。
for path in /usr/libexec /var/lib /etc/sudoers.d /srv; do protected "$path"; done
if [ -e "$runtime" ] || [ -L "$runtime" ]; then protected "$runtime"; fi
for path in $exec_root /var/lib/paperradar $ledger $ledger/inbox /srv/pi-cwd; do
    if [ -e "$path" ] || [ -L "$path" ]; then protected "$path"; fi
done
/usr/bin/install -d -o root -g root -m 0755 $exec_root
[ ! -e $runtime.new ] && [ ! -L $runtime.new ] || exit 2
if [ -e $runtime ]; then
    protected $runtime
    [ "$(/usr/bin/cat $runtime/payload.sha256)" = '{payload_sha256}' ] || exit 2
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
(cd $runtime && /usr/bin/sha256sum --strict -c manifest.sha256 >/dev/null)
/usr/sbin/visudo -cf $runtime/sudoers
/usr/bin/install -d -o root -g root -m 0755 $ledger $ledger/inbox
protected $ledger/inbox
if [ ! -e /srv/pi-cwd ]; then
    /usr/bin/install -d -o root -g root -m 0755 /srv/pi-cwd
    /usr/bin/touch $ledger/cwd-created-by-beta
fi
[ -z "$(/usr/bin/find /srv/pi-cwd -mindepth 1 -maxdepth 1 -print -quit)" ] || exit 2
for entry in collect tighten owner; do
    target=$exec_root/live-evidence-$entry
    if [ -e "$target" ] || [ -L "$target" ]; then
        protected "$target"
        /usr/bin/cmp "$target" "$runtime/wrappers/$entry" || exit 2
    else
        /usr/bin/install -o root -g root -m 0755 "$runtime/wrappers/$entry" "$target"
    fi
done
policy=/etc/sudoers.d/paperradar-live-evidence
if [ -e "$policy" ] || [ -L "$policy" ]; then
    protected "$policy"
    /usr/bin/cmp "$policy" $runtime/sudoers || exit 2
else
    /usr/bin/install -o root -g root -m 0440 $runtime/sudoers "$policy"
fi
$exec_root/live-evidence-collect
# 本次sudo部署命令包含所有者对固定计划/接收的明确授权;不激活。
plan=$ledger/inbox/{plan_id}-plan.json
source=$ledger/inbox/{plan_id}-round-1.json
$exec_root/live-evidence-owner receive --plan "$plan" --source "$source"
"""
    )


def render_uninstall() -> str:
    return (
        _guard("uninstall")
        + """
# 默认只移除本包部署物;账本、inbox回执、失败历史与staging永久保留。
for entry in collect tighten owner; do
    target=$exec_root/live-evidence-$entry
    if [ -e "$target" ] || [ -L "$target" ]; then
        protected "$target"
        /usr/bin/cmp "$target" "$runtime/wrappers/$entry" || exit 2
    fi
done
policy=/etc/sudoers.d/paperradar-live-evidence
if [ -e "$policy" ] || [ -L "$policy" ]; then
    protected "$policy"
    /usr/bin/cmp "$policy" $runtime/sudoers || exit 2
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


def render_review(
    target: Path, digests: dict[str, str], site: SiteConfiguration, plan: ApprovedPlan
) -> str:
    checks = "\n".join(
        f"{digests[name]}  {STAGING}/{name}"
        for name in ("deploy.sh", "uninstall.sh", "payload.tar")
    )
    bootstrap = f"""set -eu
umask 022
stage={STAGING}
protected() {{
  path="$1"
  while :; do
    [ ! -L "$path" ] || exit 2
    [ "$(/usr/bin/stat -c %u "$path")" -eq 0 ] || exit 2
    mode=$(/usr/bin/stat -c %a "$path")
    [ "$((0$mode & 0022))" -eq 0 ] || exit 2
    [ "$path" != / ] || break
    path=$(/usr/bin/dirname "$path")
  done
}}
for path in /var /var/lib /var/lib/paperradar "$stage"; do
  if [ -e "$path" ] || [ -L "$path" ]; then protected "$path"; fi
done
/usr/bin/install -d -o root -g root -m 0755 "$stage"
for name in deploy.sh uninstall.sh payload.tar; do
  [ ! -L "$stage/$name" ] || exit 2
  /usr/bin/install -o root -g root -m 0644 "$1/$name" "$stage/$name"
done
/usr/bin/printf '%s\\n' {shlex.quote(checks)} | /usr/bin/sha256sum -c -
exec /bin/sh "$stage/deploy.sh"
"""
    command = f"sudo /bin/sh -c {shlex.quote(bootstrap)} sh {shlex.quote(str(target))}"
    return f"""# G2 私有封印审阅材料

本目录是当前明确站点的本地审阅包；site.json含必要路径定位，不应贴到公开工单。
build-identity.json记录HEAD、tree、dirty状态、绝对源worktree、Python/lock与冻结源码身份。
迁移前须逐字段比较；最终integration重建后重新审阅其新身份及SHA，不能把feature候选当最终证据。
先审阅deploy.sh、uninstall.sh、payload.tar中的entry.py、wrappers、site.json、plan.json、sudoers、manifest.sha256及冻结源码/依赖。
下列命令只复制字节到root所有staging，复核本文固定摘要，然后从root冻结副本部署；不从仓库或.venv导入/执行root代码。
字节变化必须重新审阅重装；同SHA的幂等重跑沿既有授权。此文生成不是所有者批准。

- 产品uid/gid：{site.product_uid}/{site.product_gid}；当前声明上下文：{site.use_id}。
- 独立站点主张覆盖：{", ".join(site.claim_uses or (site.use_id,))}。
- 计划：{plan.plan_id}；
  UTC窗口：{plan.starts_at.isoformat()} → {plan.ends_at.isoformat()}。
- 认证/模型/网络预算均0，单轮首失败停止；重复采集只刷新观察，不续原verified_at。
- collector_sha256是冻结Python、依赖、源码、entry与wrapper的排序文件摘要清单身份
  （site/plan之前），不是宿主安装的 passed 声明。
- 现场仍需所有者私下确认产品用户无等价root组/能力（含容器管理、任意sudo写入等），
  核对root拥有及产品不可写的完整路径链；不要公开宿主权限细节。
- sudoers仅固定零参数collect与仅收紧tighten；owner入口不在NOPASSWD中。

```text
{checks}
```

审阅通过后，所有者一次执行（部署、β采集、批准固定计划并接收；不激活）：

```sh
{command}
```

命令返回receipt_id，须现场核对回执分项与failure_history。失败时停止，不凭unknown补齐通过。
失败刷新先把当前观察置为mode000，普通产品不能解封；root只读用于受控诊断。
随后按当前安装对已接收的全部用途保守tighten，原回执/原时点不变；mode000本身不表示撤销落账成功。
落账失败返回拒绝并保留tighten-pending；后续仅重放收紧，stopped计划不重试探针。
固定inbox和collector-history.jsonl保留所有已开始采集的结果。
隔离合成检查只接受EACCES/EPERM拒绝，逐项记录outside-read、cwd-write、install-write、
attempt-write与soft/hard零core；Node只执行--version，已降权产品uid。
Apport只采版本/配置身份与core_pattern；不修改全机core策略，不制造真实core。
模型、RPC、IPv4出站及observer仍unknown；β接收/部分激活不会使产品executable=true。

G3由所有者另行操作，不能将本说明当作激活授权。先重采60秒观察，再使用上一步实际receipt_id：

```sh
sudo /usr/libexec/paperradar/live-evidence-collect
owner=/usr/libexec/paperradar/live-evidence-owner
sudo -k "$owner" activate --receipt-id ACTUAL_RECEIPT_ID --use-id {site.use_id}
```

owner入口展示完整脱敏回执并要求输入短ID确认；不能使用占位ID。重采不续原能力时点。
六格站点主张须由所有者逐格选择use-id和显式确认；上例只选当前上下文，不自动激活其他格。
CurrentObservation仅当前low声明上下文；六格只有内容无关站点事实重复独立留痕，模型/RPC/high实际行为均未验。
AUTH_CACHE_BASELINE覆盖credentials全根，包括node-compile-cache、auth.json等全部regular成员与目录stat；没有排除正常缓存写入。
认证helper的HOME/TMPDIR位于credentials，当前Pi入口启用Node compile cache；
正常cache或auth.json刷新会改变基线，准备后拒绝而不领取attempt。
要更新基线须新受信采集计划、重新审阅封印字节并人工激活；当前成功计划重跑只刷新观察，不替换旧回执原基线。
支持连续运行的缓存布局/允许演进保护由Live后继处理，本包不为能运行而放宽成员或字段。


默认卸载（同一已封印脚本；保留账本、回执、失败历史、staging；只删除本部署创建且仍为空的cwd）：

```sh
sudo /bin/sh {STAGING}/uninstall.sh
```

如先前部署中途失败留下runtime.new，只由所有者核对其来源后手动清理该固定目录，再重跑同SHA部署；不自动清理未知目录或回滚历史。
卸载后可重跑同SHA部署恢复，原账本与撤销历史继续有效；清理账本另需所有者显式选择，不属于此脚本。
此包未执行sudo、真实root验证、历史导入、认证、模型、网络或激活；完整离线门禁留后继收口。
"""


def build_deployment(
    target: Path,
    site: SiteConfiguration,
    *,
    starts_at: datetime,
    ends_at: datetime,
    source_root: Path,
) -> dict[str, str]:
    """新目录输出确切review artifacts;窗口与现场身份由所有者入口提供。"""
    if starts_at.tzinfo is None or ends_at.tzinfo is None or starts_at >= ends_at:
        raise ValueError("plan_window_invalid")
    starts_at = starts_at.astimezone(UTC)
    ends_at = ends_at.astimezone(UTC)
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="paperradar-seal-") as temporary:
        frozen = Path(temporary)
        freeze_runtime(frozen, source_root)
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
    (target / "deploy.sh").write_text(render_deploy(payload_digest, plan.plan_id))
    (target / "uninstall.sh").write_text(render_uninstall())

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
    (target / "build-identity.json").write_text(
        json.dumps(identity, sort_keys=True, indent=2) + "\n"
    )
    digests = file_digests(target)
    (target / "REVIEW.md").write_text(render_review(target, digests, site, plan))
    digests = file_digests(target)
    (target / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in digests.items())
    )
    return digests
