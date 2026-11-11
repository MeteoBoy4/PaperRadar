"""新Live封印外层入口;root只执行stdin冻结并核验过的归档字节。"""

# 冻结shell和审阅文本保留完整命令行,便于逐字审阅。
# ruff: noqa: E501

import base64
from pathlib import Path

from paper_radar.live_evidence.sealed_runtime import RUNTIME_ROOT


def wrapper(action: str) -> bytes:
    if action not in {"collect", "tighten", "owner", "refresh", "collect-models"}:
        raise ValueError("wrapper_action")
    zero = (
        '[ "$#" -eq 0 ] || exit 2\n'
        if action in {"collect", "refresh", "collect-models"}
        else ""
    )
    return f"""#!/bin/sh
set -eu
{zero}runtime={RUNTIME_ROOT}
cd "$runtime"
/usr/bin/sha256sum --strict -c manifest.sha256 >/dev/null
exec /usr/bin/env -i "$runtime/python/bin/python3" -I -S -B "$runtime/entry.py" {action} "$@"
""".encode()


def render_runner(
    payload: bytes, payload_sha: str, manifest_sha: str, *, files: int, directories: int
) -> str:
    encoded = base64.encodebytes(payload).decode("ascii")
    return f"""#!/bin/sh
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
[ "$#" -le 1 ] || exit 2
action=${{1-install}}
case "$action" in install|uninstall|recover) ;; *) exit 2;; esac
[ "$(/usr/bin/id -u)" -ne 0 ] || exit 2
package=$(CDPATH= cd -- "$(/usr/bin/dirname -- "$0")" && /usr/bin/pwd -P)
actual=$(/usr/bin/sha256sum "$package/payload.tar" | /usr/bin/cut -d ' ' -f 1)
[ "$actual" = '{payload_sha}' ] || exit 2
# 密码边界前只读用户包;root只接收本入口内嵌的精确字节。
exec /usr/bin/sudo -k /bin/sh -s -- "$action" <<'LIVE_FROZEN_BOOTSTRAP'
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022
case "$1" in install|uninstall|recover) action=$1;; *) exit 2;; esac
[ "$(/usr/bin/id -u)" -eq 0 ] || exit 2
refuse() {{ /usr/bin/printf 'Live封印入口拒绝 [%s]；保留现场，请所有者核对身份与恢复步骤。\\n' "$1" >&2; exit 2; }}
protected() {{
    current=$1
    while :; do
        [ ! -L "$current" ] || refuse protected_symlink
        [ "$(/usr/bin/stat -c %u "$current")" -eq 0 ] || refuse protected_owner
        mode=$(/usr/bin/stat -c %a "$current")
        [ "$((0$mode & 0022))" -eq 0 ] || refuse protected_mode
        [ "$current" != / ] || break
        current=$(/usr/bin/dirname "$current")
    done
}}
base=/var/lib/paperradar/live-bundles
for directory in /var /var/lib /var/lib/paperradar "$base"; do
    if [ -e "$directory" ] || [ -L "$directory" ]; then protected "$directory"; fi
done
/usr/bin/install -d -o root -g root -m 0755 "$base"
stage="$base/{payload_sha}"
if [ ! -e "$stage" ] && [ ! -L "$stage" ]; then
    [ ! -e "$stage.new" ] && [ ! -L "$stage.new" ] || refuse staging_partial
    /usr/bin/install -d -o root -g root -m 0755 "$stage.new" "$stage.new/runtime"
    /usr/bin/base64 --decode > "$stage.new/payload.tar" <<'LIVE_ARCHIVE_BYTES'
{encoded}LIVE_ARCHIVE_BYTES
    actual=$(/usr/bin/sha256sum "$stage.new/payload.tar" | /usr/bin/cut -d ' ' -f 1)
    [ "$actual" = '{payload_sha}' ] || refuse archive_identity
    /usr/bin/tar -xf "$stage.new/payload.tar" -C "$stage.new/runtime" --no-same-owner --no-same-permissions
    /usr/bin/printf '%s\\n' '{payload_sha}' > "$stage.new/runtime/payload.sha256"
    /usr/bin/mv "$stage.new" "$stage"
fi
protected "$stage"
[ -d "$stage/runtime" ] && [ ! -L "$stage/runtime" ] || refuse staging_type
for member in "$stage/payload.tar" "$stage/runtime/manifest.sha256" "$stage/runtime/payload.sha256"; do
    protected "$member"
    [ -f "$member" ] && [ "$(( $(/usr/bin/stat -c %h "$member") ))" -eq 1 ] || refuse staging_type
done
bad=$(/usr/bin/find "$stage/runtime" \\( -type l -o ! -user root -o -perm /022 -o \\( -type f ! -links 1 \\) -o \\( ! -type f ! -type d \\) \\) -print -quit)
[ -z "$bad" ] || refuse staging_protection
actual=$(/usr/bin/sha256sum "$stage/payload.tar" | /usr/bin/cut -d ' ' -f 1)
[ "$actual" = '{payload_sha}' ] || refuse archive_identity
actual=$(/usr/bin/sha256sum "$stage/runtime/manifest.sha256" | /usr/bin/cut -d ' ' -f 1)
[ "$actual" = '{manifest_sha}' ] || refuse manifest_identity
[ "$(/usr/bin/cat "$stage/runtime/payload.sha256")" = '{payload_sha}' ] || refuse payload_identity
[ "$(/usr/bin/find "$stage/runtime" -type f | /usr/bin/wc -l)" -eq {files + 2} ] || refuse inventory
[ "$(/usr/bin/find "$stage/runtime" -mindepth 1 -type d | /usr/bin/wc -l)" -eq {directories} ] || refuse inventory
bad=$(/usr/bin/find "$stage/runtime" \\( -type l -o ! -user root -o -perm /022 -o \\( -type f ! -links 1 \\) -o \\( ! -type f ! -type d \\) \\) -print -quit)
[ -z "$bad" ] || refuse staging_protection
(cd "$stage/runtime" && /usr/bin/sha256sum --strict -c manifest.sha256 >/dev/null)
exec /usr/bin/env -i "$stage/runtime/python/bin/python3" -I -S -B "$stage/runtime/install-live.py" "$action"
LIVE_FROZEN_BOOTSTRAP
"""


def review_text(
    target: Path,
    payload_sha: str,
    manifest_sha: str,
    start: str,
    end: str,
    pending: bool,
) -> str:
    return f"""# Live 私有封印审阅包

本目录含私有站点路径；不得公开、提交或附到回执。所有者批准的是本次归档和入口确切字节；
重新压缩、更改窗口/计划/成员/脚本均需重新审阅。包级payload SHA256：{payload_sha}；
成员清单文件SHA256：{manifest_sha}。SHA256SUMS覆盖外层入口及归档，归档内manifest.sha256列全部成员。

UTC共同窗口：{start} → {end}。{"精确日期与网络适用性未确认：安装入口在变更前拒绝，现场gate保持。" if pending else "窗口与网络适用性来源已绑定；仍须所有者审阅本次确切字节。"}
六格目标在部署后72小时内完成；子窗口不得超出共同窗口。七份v2计划属于live-177，累计认证+网络40、模型40；
根侧预占不退款，安全失败首停/同类连续三轮/累计六失败轮停止，换计划/升级不重置。
严格β仍使用独立v1单轮计划和旧失败语义。manifest v2固定三批外部执行：A=boundary-low，B=boundary-high，C=value-low及剩余三格。
A后返回；B/C首格必须分别有本次真实refresh+原提交且模型成功，否则持久unknown停止，不能借续跑寻找事件。
批间不留轮/锁/持密进程；所有者自行选择共同窗口内时点，不探测expiry、不自动等待/补跑/延窗。
正常提前刷新满足ADR-0063；供应商真实到期始终unknown。部署epoch固定72h六格目标，仅披露，不改变授权。
不能把三次调用、cache stat变化或成功模型响应当刷新证明。固定Node认证入口只在产品uid运行，正式与collector共用；root只接白名单。

按顺序审阅：

1. manifest.sha256、deployment.json、site.json、source-identity.json、source-vectors/、完整Python/stdlib/依赖/源码、auth_helper.mjs（公开入口/静态API摘要）、auth_metadata.py、normal_auth_refresh.py与entry.py/install-live.py。
2. resources/paperradar.slice、paperradar-anchor.service、resolv.conf和live_host.py规则生成/验证代码。
   仅inet paperradar，真实slice层级与独立kernfs dev/inode，四固定comment+counter；允许28.0.0.0/8 TCP443、192.168.44.1 UDP/TCP53；其他项目出站drop。
   不改全机resolver、上游路由、sysctl、host capability或常驻root服务。scope逐调用wrapper把core软硬置0，anchor LimitCORE=0。
3. network-owner-confirmation.json（每计划适用确认原文与七plan_ids）、plan.json、plans/七计划、model-manifest.json、materials/六格完整纯编译合成材料。
4. wrappers/零参数collect/refresh/model-collect与精确sudoers；owner与tighten不放宽派发权限。
5. legacy升级身份只作候选，实际root入口逐字核旧payload/manifest、完整成员与三个入口/sudoers后原样归档。
   本地候选版本不代表实际已部署；任一不符拒绝，不覆盖已有归档。保留旧runtime、账本、intents、原回执、撤销、失败/stopped、额度和新状态journal。
6. deployment.json若有cache_migration，先核metadata预期。停止产品业务/其他认证/collector后，在产品uid子进程中以RENAME_NOREPLACE将旧cache迁到凭据根同级辅助归档。
   仅lstat比较，不列cache目录或读正文；不删、不复制、不覆盖未知目标；同FS迁移失败即保留并停止。

所有者审阅精确SHA后，唯一sudo密码入口：

```sh
{target / "run-live.sh"} install
```

安装只初始化/批准封印计划与保护资源，不运行认证/模型、receive或激活。
manager必须running且linger=yes；degraded、unit用户遮蔽/dropin、CG重建、resolver/规则漂移拒绝；不reset-failed。
实际CG身份与egress摘要部署后写受保护target，不伪冻进归档；observer身份不含PID，并避免payload hash自循环。
存在未知资源、archive冲突、部分复制、中断无法识别或历史失信时拒绝，保留现场；不可盲删.new/journal/archive。
同SHA已安装重跑只核字节与当前目标，不重跑联网/模型或初始化谱系；已卸载只允许显式recover重新建立目标，旧撤销不复活。

部署完成后按批准窗口由普通产品会话调用固定零参数入口：先严格β，核受保护source七案例完整passed，再两次独立refresh。
首个placeholder→真实观察保留observation_drift与依赖收紧；第二次同事实才available。不得清撤销/换plan绕过。

```sh
sudo /usr/libexec/paperradar/live-evidence-collect
sudo /usr/libexec/paperradar/live-evidence-refresh
sudo /usr/libexec/paperradar/live-evidence-refresh
sudo /usr/libexec/paperradar/live-evidence-model-collect
```

模型collector首次先四出站负对照，再执行A；后两次由所有者在选定时点独立调用同一零参数入口执行B、C（不是自动连续调用）。核每次normal_refresh/next_batch/stopped及受保护事件来源后再决定下一次。collector只写inbox/历史；root不运行Pi，持密auth/model均产品uid。
任何不符合预期的失败立即按受保护状态停下；成功终态也不等于产品可执行。owner另行receive与逐格明确激活，不用--owner-closure。

卸载/恢复仍调用同一已审副本并输入sudo密码：

```sh
{target / "run-live.sh"} uninstall
{target / "run-live.sh"} recover
```

卸载先使观察不可读、关闭派发入口，再停止项目slice并核无活进程后移除本包精确规则/unit/resolver/入口/runtime；
历史/账本/额度/intents/归档/stopped全部保留。恢复重核manager/资源/实际新CG与规则，不恢复旧激活或清历史。
新当前绑定与原strictβ来源不符时模型仍拒绝，需要新的审阅计划/包取得新站点来源，不能改写旧回执。
重启后/run及CG改变导致暂不可执行；需所有者显式同SHA恢复，不能自动自愈或从旧观察续期。
本包仅本地构建，真实OS/隔离/userns/ptrace/Apport分支/core对照/网络/认证/模型/receive/激活均未验证。
"""
