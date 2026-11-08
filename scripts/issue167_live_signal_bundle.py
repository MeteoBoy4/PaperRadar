"""Prepare the independent E01 review material; never execute it."""

from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import os
import subprocess
import tempfile
from pathlib import Path

from scripts import issue167_live_bundle as previous
from scripts import issue167_live_runtime as runtime
from scripts import issue167_live_signal_case as contract
from scripts import issue167_resolver_bundle as original
from scripts import issue167_service_network_bundle as network
from scripts.issue167_h1_auto_bundle import driver_text
from scripts.issue167_service_egress import (
    FrozenEgress,
    render_activate,
    render_clear,
    render_create,
    render_delete,
)

PROJECT = original.PROJECT
PREPARATION_READY = True
OWNER_FLAGS = (
    "--owner-config-confirmed",
    "--owner-dns-unknown-confirmed",
    "--owner-real-calls-confirmed",
    "--owner-external-sigint-confirmed",
)
SOURCE_PINS = {
    "issue167_live_artifact_cleanup.py": (
        "e0974605d8550fb47916713824449032b3bc43c9e2ee941c4c98fb209bdd2f86",
        (
            "DIR_FLAGS",
            "FILE_FLAGS",
            "CleanupRejected",
            "sha",
            "identity",
            "protected",
            "record",
            "Tree",
            "check_mounts",
        ),
    ),
    "issue167_live_exit_probe.py": (
        "cf3575d53493fd78e44a6197522ceabfb5dd61c7de0346e70a2810123e5190da",
        ("mount_path", "mount_points"),
    ),
}


def cleanup_source(workspace: Path = PROJECT) -> bytes:
    """Generate a core-only module from exact reviewed source segments."""
    parts: list[bytes] = []
    provenance: dict[str, object] = {}
    for filename, (expected, names) in SOURCE_PINS.items():
        raw = (workspace / "scripts" / filename).read_bytes()
        if original.digest(raw) != expected:
            raise ValueError("signal_cleanup_source_changed")
        source = raw.decode("utf-8")
        lines = source.splitlines(keepends=True)
        selected: dict[str, ast.FunctionDef | ast.ClassDef | ast.Assign] = {}
        for node in ast.parse(source).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                selected[node.name] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        selected[target.id] = node
        segments = {}
        for name in names:
            selected_node = selected.get(name)
            if selected_node is None or selected_node.end_lineno is None:
                raise ValueError("signal_cleanup_shape_unknown")
            first = selected_node.lineno
            if isinstance(selected_node, (ast.FunctionDef, ast.ClassDef)):
                first = min([first, *(d.lineno for d in selected_node.decorator_list)])
            chunk = "".join(lines[first - 1 : selected_node.end_lineno]).encode()
            segments[name] = original.digest(chunk)
            parts.append(chunk)
        provenance[filename] = {"sha256": expected, "segments": segments}
    header = b'''"""E01 generated cleanup boundary; reviewed source chunks only."""
from __future__ import annotations
import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
'''
    return (
        header
        + b"\nSOURCE_CHUNKS = "
        + repr(provenance).encode()
        + b"\n\n"
        + b"\n\n".join(parts[:9])
        + b"\n\nProbeRejected = CleanupRejected\n\n"
        + b"\n\n".join(parts[9:])
        + b"\n"
    )


def isolated_snapshot_control(root: Path) -> dict[str, object]:
    """Load only prepared modules and inspect an unrelated synthetic tree."""
    program = r"""import builtins,importlib,io,json,os,sys,tempfile,types
from pathlib import Path
root=Path(sys.argv[1]).resolve()
package=types.ModuleType('scripts');package.__path__=[str(root)]
sys.modules['scripts']=package
owner=importlib.import_module('scripts.issue167_live_signal_owner')
worker=importlib.import_module('scripts.issue167_live_signal_worker')
helper=importlib.import_module('scripts.issue167_live_signal_cleanup')
assert Path(helper.__file__).resolve()==root/'issue167_live_signal_cleanup.py'
assert Path(worker.__file__).resolve()==root/'issue167_live_signal_worker.py'
assert Path(owner.__file__).resolve()==root/'issue167_live_signal_owner.py'
assert not any(n=='paper_radar' or n.startswith('paper_radar.') for n in sys.modules)
with tempfile.TemporaryDirectory(prefix='issue167-sealed-snapshot-') as temporary:
    directory=Path(temporary)/'synthetic'
    directory.mkdir(mode=0o700)
    for name in ('auth.json','models-store.json','exp2-installation-id'):
        p=directory/name;p.write_bytes(b'public synthetic sentinel');p.chmod(0o600)
    (directory/'node-compile-cache').mkdir(mode=0o700)
    (directory/'node-compile-cache/v').mkdir(mode=0o700)
    p=directory/'node-compile-cache/v/cache';p.write_bytes(b'public sentinel')
    p.chmod(0o600)
    real_os_open,real_io_open,real_builtin_open=os.open,io.open,builtins.open
    attempted_regular=[]
    def directory_open(path,flags,*args,**kwargs):
        if not flags&os.O_DIRECTORY:
            attempted_regular.append(True)
            raise AssertionError('regular_file_open_not_allowed')
        return real_os_open(path,flags,*args,**kwargs)
    def metadata_only(file,*args,**kwargs):
        if not isinstance(file,(str,bytes,os.PathLike)):
            raise AssertionError('unexpected_open_descriptor')
        if os.fsdecode(file)!='/proc/self/mountinfo':
            attempted_regular.append(True)
            raise AssertionError('regular_content_read_not_allowed')
        return real_io_open(file,*args,**kwargs)
    try:
        os.open=directory_open;io.open=metadata_only;builtins.open=metadata_only
        value=worker.credential_snapshot(directory,os.getuid(),os.getgid(),
                                         run_id=worker.contract.RUN,phase='before')
    finally:
        os.open=real_os_open;io.open=real_io_open;builtins.open=real_builtin_open
    snapshot=value['snapshot']
    assert snapshot['node_count']==7 and snapshot['integrity']=='complete'
    assert set(snapshot['nodes'])=={'.','auth.json','models-store.json',
                                  'exp2-installation-id','node-compile-cache',
                                  'node-compile-cache/v','node-compile-cache/v/cache'}
    assert all(set(x)=={'inode','size','mtime_ns','ctime_ns'}
               for x in snapshot['nodes'].values())
    assert not attempted_regular and snapshot['regular_contents_read'] is False
print(json.dumps({'scope':'isolated_sealed_module_synthetic_snapshot_control',
                  'main_calls':0,'application_imports':0,'snapshot_nodes':7,
                  'integrity':'complete','regular_credential_contents_opened':0,
                  'helper_source':'same_prepared_copy_only'},sort_keys=True))
"""
    result = subprocess.run(
        ["/usr/bin/python3", "-I", "-S", "-B", "-", str(root.resolve())],
        input=program.encode(),
        cwd="/tmp",
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        capture_output=True,
        check=False,
        timeout=15,
    )
    if result.returncode or result.stderr or len(result.stdout) > 4096:
        raise ValueError("signal_isolated_snapshot_control_unknown")
    value = json.loads(result.stdout)
    if type(value) is not dict:
        raise ValueError("signal_isolated_snapshot_control_unknown")
    return value


def material_files(source: Path) -> dict[str, bytes]:
    """Rebuild one synthetic value/low input through the public compiler."""
    from paper_radar.config import StageName, compile_config, upgrade_database
    from paper_radar.fulltext.normalization import canonical_json
    from paper_radar.llm import build_call, render_request
    from paper_radar.llm.rpc import validate_request
    from paper_radar.screening.validation import validate_output
    from paper_radar.stage_inputs import ScreeningFacts, build_stage_input
    from scripts.issue167_materials import expected_output

    seed = previous.material_files(source)
    files = {
        name: raw
        for name, raw in seed.items()
        if name.startswith(("config/", "prompts/", "contracts/"))
        and name
        not in {"config/settings-high.yaml", "config/adapters/issue167-high-v1.yaml"}
    }
    if len(files) != 17:
        raise ValueError("signal_configuration_unknown")
    with tempfile.TemporaryDirectory(prefix="issue167-e01-materials-") as temporary:
        root = Path(temporary)
        for name, raw in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        database = root / "synthetic.sqlite3"
        upgrade_database(database)
        snapshot = compile_config(root / "config/settings-low.yaml", database)
        stage = build_stage_input(
            snapshot,
            StageName.VALUE,
            ScreeningFacts(
                title="Synthetic E01 external-interruption estimator example",
                abstract=(
                    "This E01 fictional study compares toy estimators A and B on a "
                    "synthetic sequence for an external-interruption protocol test. "
                    "No real dataset or code is supplied."
                ),
                abstract_truncated=False,
            ),
        )
        description = build_call(stage, snapshot, snapshot)
        request = render_request(description)
        if validate_request(request) is not None:
            raise ValueError("signal_request_unknown")
        candidate = canonical_json(expected_output(StageName.VALUE))
        validate_output(
            "value_prediction",
            candidate,
            stage.value_prediction_context(snapshot, original_title_is_zh=False),
        )
        descriptor = {
            key: value.decode("utf-8") if isinstance(value, bytes) else value
            for key, value in dataclasses.asdict(description).items()
        }
        cell_files = {
            "stage-input.json": stage.payload_bytes,
            "system.txt": description.system_prompt,
            "user.txt": request,
            "description.json": canonical_json(descriptor),
            "expected-valid-output.json": candidate,
        }
        manifest = {
            "kind": "synthetic_E01_value_low_only",
            "configuration_sha256": {
                name: original.digest(raw) for name, raw in sorted(files.items())
            },
            "cases": [
                {
                    "case": "value-low-E01",
                    "consumer": "value",
                    "thinking": "low",
                    "snapshot_id": snapshot.snapshot_id,
                    "fingerprint": stage.fingerprint,
                    "sha256": {
                        name: original.digest(raw)
                        for name, raw in sorted(cell_files.items())
                    },
                }
            ],
        }
    files.update({"value-low-E01/" + name: raw for name, raw in cell_files.items()})
    files["manifest.json"] = canonical_json(manifest) + b"\n"
    return files


def specialize_bootstrap(source: str) -> str:
    old = '"issue167_h1_network_worker.py",'
    if source.count(old) != 1:
        raise ValueError("signal_bootstrap_shape_unknown")
    replacements = (
        "issue167_live_signal_case.py",
        "issue167_live_signal_worker.py",
        "issue167_live_signal_owner.py",
        "issue167_live_signal_cleanup.py",
    )
    return source.replace(
        old, "\n            ".join(f'"{name}",' for name in replacements), 1
    )


def result_reader(run_id: str, manifest_sha: str) -> str:
    """Bounded E01 reader preserves NT without calling it E01 success."""
    return f"""import json,os,stat,sys
from pathlib import Path
r,p,code=Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3])
def unique(rows):
    result={{}}
    for key,value in rows:
        if key in result:raise ValueError()
        result[key]=value
    return result
value={{'owner_result':'unknown','failure_stage':'owner_output_unknown','exit_code':code}}
try:
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid()
            or before.st_gid!=os.getgid() or before.st_nlink!=1
            or before.st_mode&0o022 or before.st_size>131072):raise ValueError()
        raw=stream.read(131073)
        after=os.fstat(stream.fileno())
        if (before.st_dev,before.st_ino,before.st_size,
            before.st_mtime_ns,before.st_ctime_ns)!=(
            after.st_dev,after.st_ino,after.st_size,
            after.st_mtime_ns,after.st_ctime_ns):raise ValueError()
    if len(raw)>131072:raise ValueError()
    candidate=json.loads(raw,object_pairs_hook=unique)
    if (type(candidate) is not dict
        or set(candidate)!={{'scope','run_id','manifest_sha256',
                           'owner_result','preflight_result'}}
        or candidate['scope']!='h1_owner_automation_only'
        or candidate['run_id']!={run_id!r}
        or candidate['manifest_sha256']!={manifest_sha!r}
        or candidate['owner_result'] not in {{'observed_expected_and_restored',
                                            'not_triggered_and_restored','unknown'}}
        or type(candidate['preflight_result']) is not dict
        or candidate['preflight_result'].get('scope')!={contract.SCOPE!r}
        or candidate['preflight_result'].get('result')!=candidate['owner_result']
        or ((candidate['owner_result']=='unknown') != (code!=0))):
        raise ValueError()
    value=candidate
except (OSError,ValueError,TypeError):pass
fd=os.open(r/'results/owner-run.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as out:
    json.dump(value,out,sort_keys=True,indent=2);out.write('\\n');out.flush();os.fsync(out.fileno())
p.unlink(missing_ok=True)
print(json.dumps({{'owner_result':value['owner_result'],'receipt':str(r/'results/owner-run.json'),'E01_covered':value['owner_result']=='observed_expected_and_restored'}},sort_keys=True))
raise SystemExit(0 if value['owner_result']=='observed_expected_and_restored' else 1)
"""


def specialize_driver(source: str, run_id: str, manifest_sha: str) -> str:
    start, finish = "<<'LOCAL_RESULT'\n", "\nLOCAL_RESULT\n"
    if source.count(start) != 1 or source.count(finish) != 1:
        raise ValueError("signal_driver_shape_unknown")
    prefix, rest = source.split(start, 1)
    _old, suffix = rest.split(finish, 1)
    result = (
        prefix + start + result_reader(run_id, manifest_sha).rstrip() + finish + suffix
    )
    flags = """if [[ "$#" -ne 4 || "$1" != --owner-config-confirmed ||
      "$2" != --owner-dns-unknown-confirmed ||
      "$3" != --owner-real-calls-confirmed ||
      "$4" != --owner-external-sigint-confirmed ]]; then
  printf '%s\\n' '需要本次具体H1/H2/H3批准及四项显式确认；默认不执行。' >&2
  exit 2
fi
"""
    if result.count("set -euo pipefail\n") != 1:
        raise ValueError("signal_driver_shape_unknown")
    return result.replace("set -euo pipefail\n", "set -euo pipefail\n" + flags, 1)


def create_bundle(
    destination: Path, profile_path: Path, *, material_source: Path | None = None
) -> Path:
    if not PREPARATION_READY:
        raise ValueError("signal_preparation_not_ready")
    from scripts.issue167_node_diag_supply import prepare_binding

    if "." in os.uname().nodename:
        raise ValueError("signal_site_unknown")
    app, supply = runtime.prepare_binding(), prepare_binding()
    materials = material_files(
        PROJECT / ".scratch/issue-167/synthetic"
        if material_source is None
        else material_source
    )
    synthetic_manifest = json.loads(materials["manifest.json"])
    generated_cleanup = cleanup_source()
    nss = runtime.read_file(Path("/etc/nsswitch.conf"), 16384)
    root = original.create_bundle(destination, contract.RUN, profile_path)
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
        ),
        case_fingerprint=synthetic_manifest["cases"][0]["fingerprint"],
    )
    (root / "issue167_resolver_owner.py").write_bytes(
        (root / "issue167_h1_owner_run.py").read_bytes()
    )
    (root / "issue167_h1_network_worker.py").unlink()
    for filename in (
        *previous.SOURCES,
        "issue167_live_signal_case.py",
        "issue167_live_signal_worker.py",
        "issue167_live_signal_owner.py",
    ):
        (root / filename).write_bytes((PROJECT / "scripts" / filename).read_bytes())
    (root / "issue167_live_signal_cleanup.py").write_bytes(generated_cleanup)
    bootstrap = root / "issue167_h1_auto_bootstrap.py"
    bootstrap.write_text(specialize_bootstrap(bootstrap.read_text()))
    context = {
        "kind": "live_e01_preparation_snapshot_activation_time_recheck_required",
        "supply": supply,
        "synthetic_manifest_sha256": original.digest(materials["manifest.json"]),
        "nsswitch_sha256": original.digest(nss),
        "hostname_contains_dot": False,
        "application_runtime": app,
        "auth_input_declaration": dict(contract.AUTH_INPUT_REQUIREMENTS),
        "observation_choice": "S",
    }
    (root / "live-context.json").write_text(
        json.dumps(context, sort_keys=True, indent=2) + "\n"
    )
    previous.write_materials(root / "materials.zip", materials)
    (root / "plan.json").write_text(
        json.dumps(case.to_dict(), sort_keys=True, indent=2) + "\n"
    )
    (root / case.unit).write_text(contract.render_unit(case))
    (root / "signal-worker-entry.py").write_text(
        network.entry("issue167_live_signal_worker", owner=False)
    )
    (root / "issue167_h1_owner_run.py").write_text(
        network.entry("issue167_live_signal_owner", owner=True)
    )
    profile = FrozenEgress.from_profile(
        case.base_plan(),
        (root / "profile.json").read_bytes(),
        case.profile_sha256,
        json.loads((root / "host-context.json").read_text()),
    )
    rules = {
        "create": render_create(profile),
        "activate": render_activate(profile),
        "clear": render_clear(profile),
        "delete": render_delete(profile),
    }
    (root / "review-rules.json").write_text(
        json.dumps(rules, sort_keys=True, indent=2) + "\n"
    )
    for filename in (
        "create.nft",
        "activate.nft",
        "clear.nft",
        "delete.nft",
        "members.sha256",
    ):
        (root / filename).unlink()
    (root / "retry-context.json").write_text(
        json.dumps(
            {
                "kind": "new_E01_single_case_requires_external_H1_H2_H3",
                "previous_cases_retained": True,
                "old_allowances_reused": False,
                "preparation_not_execution_authorization": True,
            },
            sort_keys=True,
        )
        + "\n"
    )
    (root / "owner-review.md").write_text(review_text(root, case))
    excluded = {"manifest.json", "owner-wizard.sh", "review-seal.json"}
    names = sorted(
        p.name for p in root.iterdir() if p.is_file() and p.name not in excluded
    )
    if len(names) != 40:
        raise ValueError("signal_member_count_unknown")
    old_manifest = json.loads((root / "manifest.json").read_text())
    manifest = {
        "kind": "h1_synthetic_local_review",
        "members": {
            name: original.digest((root / name).read_bytes()) for name in names
        },
        "tools": old_manifest["tools"],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    )
    sha = original.digest((root / "manifest.json").read_bytes())
    driver = specialize_driver(
        driver_text(case.base_plan(), sha, bootstrap.read_text()), case.run_id, sha
    )
    (root / "owner-wizard.sh").write_text(driver)
    (root / "owner-wizard.sh").chmod(0o700)
    seal = {
        "kind": "h1_owner_auto_review",
        "run_id": case.run_id,
        "manifest_sha256": sha,
        "driver_sha256": original.digest(driver.encode()),
    }
    (root / "review-seal.json").write_text(
        json.dumps(seal, sort_keys=True, indent=2) + "\n"
    )
    for name in names:
        (root / name).chmod(0o755 if name == "synthetic-python" else 0o644)
    return root


def review_text(root: Path, case: contract.Case) -> str:
    return f"""# #167 E01：单格value/low外部SIGINT，待新H1/H2/H3

run={case.run_id}; uid/gid={case.uid}/{case.gid}
unit={case.unit}；独占inet表={case.table}
代码={case.install_root}
runtime={case.runtime_root}
永久记录=/var/lib/paperradar/probe-runs/issue167-{case.run_id}.json
本包只准备，未预占/消费；原unknown、账本、消耗保持。
失败不退款/重发，本材料不构成产品准入。

## 单次调用与外部信号

value/low仅1格，最多1auth CLI、1prompt、1model exec。
Node最多2、外部SIGINT最多1。
模型为openai/gpt-6.1-sol，prompt_only/provider_default，
chatgpt_subscription，temperature/top_p=null。
完整public prepare_launch/use_install/run_call及原OFD保持；
模型argv/env、产品LAUNCH与pi_protocol不变。
root先pin controller pidfd/starttime/unit/CG，发送前再核，
SIGINT只发该controller，不向unit/进程组发送。
marker要求已解码prompt fullwrite、ACK started、agent_start，
且未观察settled/closing，发布一次，不暂停pump。
它不证明RPC内核已消费ACK或供应商已收到请求。
实验handler仅MODEL_CALL记录并抛同一真正KI，
不宣称普通产品CLI覆盖。
正常早结束/明确迟到为not_triggered；
缺发送接收参照或观察失败unknown，均不补跑。
不要求中断后的Node退出0；必须public terminate、完整S、
CG回收、原选择恢复及controller严格退出。
not_triggered_and_restored完整保留且不是E01通过；
其进程可正常收尾，向导以非0提醒未覆盖。

## 当前认证与元数据

使用owner维护目录及本次新声明：onlyopenai OAuth，
scope含chatgpt.tokens.use.direct，无额外provider/命令型输入。
models.json缺失，models-store仍空2bytes/0成员，
cache顶目录旧mtime；不得预称六格后已有非空cache写回。
当前access再次过期，计划1logical refresh联网/持久写，
不能作为离线前置。HTTP下界0/上界unknown，
不能把packet或计划数当HTTP1。
07:13更新由owner时间窗/结构/排外声明关联e93，
非旧回执直证，不指CLI序号、不重复加算。
最新精确补证（owner报告，非读取凭据重算）：
execution-started=2026-11-08 07:12:59.589，
auth.json mtime=07:13:14.872，目录mtime=07:14:50.056，
owner-run=07:15:22.569，同批DB写入=07:15:21.17；
窗口内owner未手换、未其它位置登录/刷新、未其它Pi用此目录。
此组合把更新关联到e93批次；不指定CLI或HTTP1，
也不据目录mtime冒称捕获了具体rename事件。
Case中的分钟精度为原报告摘要投影，以本段精确补证为准。
owner报告access expiry=2026-11-08 08:10:14且再次过期；
下一CLI仍计划一次logical refresh及联网持久写入。
auth完整退出/持久化后验前不arm；
刷新失败/超时/轮换未知停止，不回滚auth.json或重试。
credentials pre/post仅relative集合与mtime/size/inode/ctime；
仅metadata sampler、Root及agent不读内容或token派生值。
本轮真实auth CLI按H2会读取并可能更新秘密，
并非“整轮零秘密”；marker内容不被sampler读取。
top四名+root封闭，cache有界递归、nofollow双遍稳定；
缺参照/越界/alias/special或采集中不稳定变化unknown并停止。
pre到post的合法auth/cache delta本身不算失败：
根inode和marker四项stat不得变，auth inode可正常原子替换；
cache合法delta在本轮真实记录为已知非session变化。
快照只证明前后delta，不是瞬时全写史或writerPID；
persistent不删除，history仍not_assessed。
未来实际新增缓存写才按S登记。Pi usage缺失/total0为未知，
不当零成本或已停止供应商计算。

## 隔离和恢复

仅新增本unit/本表及本次代码/runtime/永久记录；
不改router、全机resolver/core、其它程序或固定安装树。
应用可见允许仍28.0.0.0/8 TCP443，
192.168.44.1 UDP/TCP53；池变停止，IPv6not_assessed。
无TLS中间人仍取owner来源；本机不核上游映射/最终IP/线路，
不主张出口身份，不新增DNS/TLS预热探针。
Pi内部DNS/QNAME/fallback仍unknown，需本轮H2认可。
NNP/cap空、service+preexec CORE0、IPC预检、cwd/S保持。
session/guard/终态/独立删除须完整；
未知路径/丢watch/overflow/alias阻断。
已知非session为下界，缓存内部history不外推。
Root只stdlib载入封印root-owned字节，
不import可写应用。
准备只有公共registry RO投影和code绑定；
执行重新完整use_install，不以诊断投影替代。
实验库非空，public compile/CAS选择并恢复实际原baseline；
追加历史保留，不初始化/清空/字节回滚。
CG空及独立完整表binding后才撤表、卸unit/reload；
DB恢复分别核，未知不finish。
完整恢复后才清两树，单次记录保留；
部分安装/归属/清理失败可能留本unit/表/树，
须owner仅恢复，不自动重验。

## 材料与入口

generic cap40未增：4份nft合入review-rules.json，
与实际renderer逐字核对；manifest覆盖来源，
冗余members.sha256移除，新增3signal及1chunk cleanup模块。
cleanup只含已审Tree/record与strict mount parser，
不带旧main/perform/RUN路径。
单格zip23成员经公共输入链重建新fingerprint，无六格执行循环。
先审40成员、两entry、runtime/context、23材料、
unit/4规则、driver与seal，自检不代替本轮外部H1/H2/H3。
worker720s、service780s、owner900s；
auth30s、model300s及原有有界回收，失败不补。
获具体批准后运行：
`bash {root}/owner-wizard.sh {" ".join(OWNER_FLAGS)}`
只输入一次sudo TTY密码；脚本核查执行，不读取/保存密码。
新D1不扩历史分母/required/正式回执，产品缺证据仍阻断。
配置/绑定/回执只留本地；不授正式校准、真实资料或无人值守资格。
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="仅准备E01单格外部SIGINT待审包")
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--profile",
        type=Path,
        default=PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
    )
    args = parser.parse_args()
    print(create_bundle(args.destination, args.profile))
