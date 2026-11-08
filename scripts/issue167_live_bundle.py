"""Prepare a six-cell review package; never installs or executes that package."""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path

from scripts import issue167_live_case as contract
from scripts import issue167_live_runtime as runtime
from scripts import issue167_resolver_bundle as original
from scripts import issue167_service_network_bundle as network
from scripts.issue167_h1_auto_bundle import driver_text

SOURCES = (
    "issue167_live_case.py",
    "issue167_live_worker.py",
    "issue167_live_owner.py",
    "issue167_live_runtime.py",
    "issue167_live_resources.py",
    "issue167_live_ipc.py",
    "issue167_session_observation.py",
    "issue167_service_network_case.py",
    "issue167_service_network_owner.py",
    "issue167_dns_tls.py",
)

# The owner selected classified session observation and declared the auth input.
# Keep generation closed until the new backend and integration have been reviewed.
PREPARATION_READY = True


def material_files(source: Path) -> dict[str, bytes]:
    raw = (source / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    if manifest != json.loads(
        (
            original.PROJECT / "intent/review/issue-167/synthetic-manifest.json"
        ).read_bytes()
    ):
        raise ValueError("synthetic_manifest_changed")
    expected = dict(manifest["configuration_sha256"])
    expected.update({"source/" + n: h for n, h in manifest["source_sha256"].items()})
    for cell in manifest["cases"]:
        expected.update({cell["case"] + "/" + n: h for n, h in cell["sha256"].items()})
    if len(expected) != 65 or {
        (c["consumer"], c["thinking"]) for c in manifest["cases"]
    } != {
        (consumer, level)
        for consumer in ("boundary", "value", "read")
        for level in ("low", "high")
    }:
        raise ValueError("synthetic_members_unknown")
    result = {"manifest.json": raw}
    for name, h in expected.items():
        data = runtime.read_file(source / name, 4 * 1024 * 1024)
        if original.digest(data) != h:
            raise ValueError("synthetic_member_changed")
        result[name] = data
    return result


def write_materials(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as out:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100600 << 16
            out.writestr(info, data)


def specialize_bootstrap(source: str) -> str:
    old = '"issue167_h1_network_worker.py",'
    if source.count(old) != 1:
        raise ValueError("live_bootstrap_shape_unknown")
    # Keep the shared source/default and every previously executed package
    # unchanged. This package uses the same verified copy boundary for its own
    # required worker and still retains the generic forty-member limit.
    return source.replace(old, '"issue167_live_worker.py",', 1)


def create_bundle(destination: Path, run_id: str, profile_path: Path) -> Path:
    if not PREPARATION_READY:
        raise ValueError("live_preparation_not_ready")
    from scripts.issue167_node_diag_supply import prepare_binding

    if "." in os.uname().nodename:
        raise ValueError("live_site_unknown")
    app = runtime.prepare_binding()
    supply = prepare_binding()
    materials = material_files(original.PROJECT / ".scratch/issue-167/synthetic")
    nss = runtime.read_file(Path("/etc/nsswitch.conf"), 16384)
    root = original.create_bundle(destination, run_id, profile_path)
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
    (root / "issue167_resolver_owner.py").write_bytes(
        (root / "issue167_h1_owner_run.py").read_bytes()
    )
    (root / "issue167_h1_network_worker.py").unlink()
    bootstrap_path = root / "issue167_h1_auto_bootstrap.py"
    bootstrap_path.write_text(specialize_bootstrap(bootstrap_path.read_text()))
    for name in SOURCES:
        (root / name).write_bytes((original.PROJECT / "scripts" / name).read_bytes())
    context = {
        "kind": "live_six_public_bindings",
        "supply": supply,
        "synthetic_manifest_sha256": original.digest(materials["manifest.json"]),
        "nsswitch_sha256": original.digest(nss),
        "hostname_contains_dot": False,
        "application_runtime": app,
        "auth_input_declaration": dict(contract.AUTH_INPUT_DECLARATION),
        "observation_choice": "S",
    }
    (root / "live-context.json").write_text(
        json.dumps(context, sort_keys=True, indent=2) + "\n"
    )
    write_materials(root / "materials.zip", materials)
    (root / "plan.json").write_text(
        json.dumps(case.to_dict(), sort_keys=True, indent=2) + "\n"
    )
    (root / case.unit).write_text(contract.render_unit(case))
    (root / "live-worker-entry.py").write_text(
        network.entry("issue167_live_worker", owner=False)
    )
    (root / "issue167_h1_owner_run.py").write_text(
        network.entry("issue167_live_owner", owner=True)
    )
    (root / "retry-context.json").write_text(
        json.dumps(
            {
                "kind": "new_six_cell_batch_requires_external_approval",
                "previous_cases_retained": True,
                "old_allowances_reused": False,
                "preparation_not_execution_authorization": True,
            },
            sort_keys=True,
        )
        + "\n"
    )
    (root / "owner-review.md").write_text(review_text(root, case))
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
        "".join(f"{original.digest((root / n).read_bytes())}  {n}\n" for n in names)
    )
    names.append("members.sha256")
    if len(names) > 40:
        raise ValueError("member_count_unknown")
    previous = json.loads((root / "manifest.json").read_text())
    manifest = {
        "kind": "h1_synthetic_local_review",
        "members": {n: original.digest((root / n).read_bytes()) for n in names},
        "tools": previous["tools"],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    sha = original.digest((root / "manifest.json").read_bytes())
    text = driver_text(
        case.base_plan(), sha, (root / "issue167_h1_auto_bootstrap.py").read_text()
    )
    flags = """if [[ "$#" -ne 3 || "$1" != --owner-config-confirmed ||
      "$2" != --owner-dns-unknown-confirmed ||
      "$3" != --owner-real-calls-confirmed ]]; then
  printf '%s\\n' '需要外部单次H1/H2/H3授权和三项显式确认；默认不执行。' >&2
  exit 2
fi
"""
    text = text.replace("set -euo pipefail\n", "set -euo pipefail\n" + flags, 1)
    (root / "owner-wizard.sh").write_text(text)
    (root / "owner-wizard.sh").chmod(0o700)
    (root / "review-seal.json").write_text(
        json.dumps(
            {
                "kind": "h1_owner_auto_review",
                "run_id": run_id,
                "manifest_sha256": sha,
                "driver_sha256": original.digest(text.encode()),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    for n in names:
        (root / n).chmod(0o755 if n == "synthetic-python" else 0o644)
    return root


def review_text(root: Path, case: contract.Case) -> str:
    return f"""# #167 H1/H2/H3：真实公共启动链的六格合成正常批次，待审未执行

run={case.run_id}; uid/gid={case.uid}/{case.gid}
unit={case.unit}; table=inet {case.table}
root-owned code={case.install_root}; runtime={case.runtime_root}
permanent=/var/lib/paperradar/probe-runs/issue167-{case.run_id}.json

本包未获执行许可。请审全部源码、runtime绑定、live-context、65成员合成材料zip、unit/规则。
新H1/H2/H3须绑定review-seal.json外部SHA；旧批准/预算不授予新调用，失败unknown不退款/重发。

## 具体差异与隐私边界

只新增上述一个unit/独占项目表及本次代码/runtime/永久预占，不改全机core/DNS、router、代理、
其他服务、安装树或产品启动/协议身份。冻结允许集仍TCP443至28.0.0.0/8及UDP/TCP53至
192.168.44.1；AF_INET、仅现有pool/router、cap/ambient空、NNP/seccomp、Delegate=no、
服务LimitCORE=0与公共子进程preexec软硬零core、只读服务resolver、
固定/srv/pi-cwd保持。
来源仍为所有者OpenClash fake-ip、原池28.0.0.1/8、sniffer override、LAN DNS劫持及TCP
redirect7892；配置变/缺确认停止。API/auth共享池不证明分离；无TLS中间人由所有者陈述，
本机不核验上游映射/最终IP/线路或主张出口身份。IPv6网络连接0/not_assessed。

Root仅stdlib安全验证/复制封印字节、服务生命周期和规则，不root import工作区应用。
UID1000受信controller导入SHA绑定的原应用源码/解释器/标准库与必要依赖，逐成员核验、
禁止unbound imports与旧pyc，前后及各格核对。模型LL不增加运行库/业务根读取权限。
待认证目录为封印项目根下 .scratch/exp-2/credentials/。
只在本地H2材料引用，不入回执。
该目录已由所有者在会话确认并负责维护；所有者只读结构声明：仅openai OAuth，scopes含
chatgpt.tokens.use.direct，非api_key，无额外provider/命令型key；models.json缺失，models-store为空
对象，node-compile-cache已存在。此为所有者输入声明，agent未读取凭据内容、长度/哈希或派生值，
不独立复核其结构。程序仅固定路径lstat检查权限/类型及models.json仍缺失，不新增凭据reader。
持久认证目录由公共auth CLI合法初始化/更新auth.json、models-store及编译缓存，
可能有两个存储锁目录。它与模型临时agent分别记录；认证目录只保留前后metadata checkpoint，
history not_assessed、
persistent_not_deleted，不套用模型session零写，不删/移动/回滚既有缓存或auth.json。
token只走原匿名pipe→Python私有memory→原模型env，不经unit属性/manager/runtime文件，
不存任何完整流，路径/token不写回执或普通日志。

## 本批会改变的项目实验DB

六格新audit snapshot必须真实登记，不能替换为旧ID。未来worker通过公共compile_config将
已封印low/high配置写入原实验供给库，再逐格公共activate_supply选择相应snapshot。完整
公共prepare_launch/use_install验证供给材料/D5/配置/整树并传原OFD给auth/model；不使用
此前Node诊断窄投影代替它。所有DB写仅在新许可后，本轮AFK未写真实库。
启动前冻结原选择fulltuple；公共commit_activation事务内加controller局部expected-old CAS
守卫，检查原ID/supply/install/snapshot/root后才调用原_select_activation；冲突整笔回滚。
格间和auth→model门闩后重查，本批每个已确认返回选择原子fsync到私有保护控制journal。
私有control保留恢复所需真实root_path；worker-result/Rootledger/stdout仅投影root_path_identity，
不把用户名/原路径带进执行回执，Root先验raw control再投影与worker export交叉比较。
结束用同样公共API/CAS恢复原逻辑选择，追加历史保留、不字节回滚、不删新snapshots或旧历史。
外部选择漂移/commit不明不盲回滚，DB恢复未知使整例unknown，即使网络/unit已恢复也不通过。
SIGTERM/SIGINT由worker受控收尾；SIGKILL/创建或commit不明不能保证自动DB恢复，保留journal。

## 认证前及六格顺序

认证前同服务检查cwd祖先/NSS/当前uid默认unpackaged配置absence、原隔离能力与零core。
新包只读精确核当前core_pattern仍是已声明Apport pipe并传%c；
固定主handler/fileutils/report三项sourceSHA。controller与固定Node路径须在/home非打包范围，实际unit为system.slice。
当前pattern是本轮明确绑定，不声称旧C对照保存过其全字节；既有limit0/非0paired事实保留，
不重跑崩溃、不改宿主。配置/source漂移一律unknown阻断，长期doctor仍属后续工程。
七组同uid自建无秘密Python target/peer正负对照，7targets/
14peers/14probes，ptrace/readv/writev/pidfd/proc/signal只操作本批marker，不读真实进程或凭据；
正例不成立/不支持/cleanup未知即停，不加权限。只对自身一个小空树做inotify初始化/封口/
删除核查，不调配额。真实每个AttemptResources仍须在modelPopen前arm，缺观察阻断。

固定6格：boundary-low/high、value-low/high、read-low/high，唯一模型元组openai/
gpt-6.1-sol/prompt_only/provider_default/chatgpt_subscription，temperature/top_p=null。
仅65成员已封印虚构Profile、摘要/手制正文/evidence，不外发真实资料。各格先永久预占，
auth-go后公共prepare_launch；刷新成功且只剩controller时auth-ready，root核完整规则/CG
后给model-go，才公共run_call。仅原Popen/preexec/argv/env/OFD，resource adapter只观察。
按所有者已选S分别登记三类文件事实：模型session/unknown写入的所声明边界全窗口必须
完整且session零写；固定源码已知的agent auth/models空存储、proper-lockfile锁目录、
自身TMPDIR下Node编译缓存另分类。模型三个exact锁目录为auth.json.lock、models-store.json.lock、
settings.json.lock，不通配其它lock。原公共RPC的set_auto_retry/compaction(false)会通过
SettingsManager非session重写settings；不能跳过这两个命令。它单列control_settings事件下界，
只允许同一inode/owner/mode/nlink下的公开SETTINGS_JSON严格同语义重写（格式/mtime可变）。
初始、封口、删前再次解析这一公开非秘密设置参考，拒重复key/NaN/未知字段/型别或值变化；
不读取auth/model store或编译缓存内容，不将此控制写误记session，也不放宽实际设置约束。
缓存与锁内部全写历史明确not_assessed；边界事件只记
observed inotify lower bound，不填成精确write数或整个attempt零写。
完整终态按类别/type/count
记录；未知路径、缺watch、溢出、跨边界move、symlink/special/别名或任何session写都unknown停止。
可信CG封口后才原rmtree，删除生命周期显式授权，再独立absent与cleanup完整性；不以终态
替代历史。新scope为classified_session_observation，
不冒用旧window_complete或产品正式证据。

## 预算、停止、回执

每格auth CLI上限1、显式prompt1、model exec1；本批各6，Node exec上限12，无应用重试/
fallback。必须一并批准首CLI的联网刷新：所有者报告auth.json expires单位毫秒，access已于
2026-11-06 18:42过期（未提供时区，本包不换算/不读原值）；若未被其它actor更新，下一CLI
计划触发1次logical refresh并联网，绝非离线前置。后5个CLI是否再次刷新unknown，不能假定0。
首auth完成还需本表allowed packet增量，但packet不当作HTTP计数；独立HTTP发送源缺失，
实际refresh HTTP仍下界0+unknown。默认redirect/隐藏重试不被虚构为一次wire请求。
refresh开始后有独立持久化rotated token窗口；
父auth强停时rotation/persistence可能unknown。
任何首auth失败/超时/坏shape/CG或规则异常停止后续模型/格，
不自动重试或回滚auth.json。
auth30s、RPC/model300s、cleanup10s；worker2520s、unit2580s、owner2700s，stop
最多60s并留root70s监督，不保证任意kernel阻塞可抢占。父等待识别worker终结，不空等45分钟。
实际model HTTP/refresh均只给无独立发送源的下界0+unknown。
透明方法参考无秘密Node诊断，但此前A不授予本轮auth/Pi余额或未知范围许可；
本轮OS内部DNS/QNAME/fallback未知须随新H2明确批准。
token以Pi报告usage为权威，缺失或0为unknown，不当零消耗并停止后续。
每格严格RPC及公共业务validator（Read v2 attempt1），不保存原候选/headers/body/token/
stderr/完整session/第三方异常原文。仅分类/count/完整性、prompt完整写、ACK与agent_start
独立序号、Pi token用量、三类文件事实、CG/供给/恢复安全metadata进入回执。
正常六格不证明参数效力、alias/订阅限额、故障、真实供应商错误、H5或产品激活；不接
read_evidence，不采用新启动身份/loader，不为精确计数重跑EXP-2，不扩大历史分母/required。

## 恢复及入口

原scope核对→stop→CG空→独立binding完整验表→删本表/卸unit/reload，永久ledger与DB
journal保留；resolver在启动前持久root0600基线，恢复核前后SHA。失败保留受控材料，
成功才精确清本code/runtime。未知attempt树不归档/读内容，不把残留误说已删。
本轮保持严格post-stop规则判据：普通失败若出现late unexpected reject等，即使CG已空，
后验仍可能拒绝并保留本表/unit待审；不能声称所有普通失败都自动清理。此时须所有者
审阅原范围仅恢复，不降规则判据、不flush全局、不自动重跑；失败code/runtime/journal保留。
Root只由所有者审阅执行，唯一sudo由TTY读取密码；不sudo-S、不脚本读取/保存密码。
三个flag只转录本次外部执行许可、配置适用性及本轮auth/Pi内部DNS未知接受，不自证授权；
此前A没有本轮余额，S及所有者输入声明已确定但不代替实际执行批准；
缺任意一个在预占/sudo前拒绝。本次仍须明确批准真实认证/联网refresh和模型prompt以及DB副作用，
此前S/输入裁定不代替执行许可。

获批后运行：
`bash {root}/owner-wizard.sh`
参数：`--owner-config-confirmed --owner-dns-unknown-confirmed`
和 `--owner-real-calls-confirmed`
任何失败请勿重跑。内部配置、绑定/回执与相关SHA只留本地，不发GitHub。
"""


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="只准备六格真实调用审阅包，默认不执行")
    p.add_argument("destination", type=Path)
    p.add_argument("--run-id", required=True)
    p.add_argument(
        "--profile",
        type=Path,
        default=original.PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
    )
    a = p.parse_args()
    print(create_bundle(a.destination, a.run_id, a.profile))
