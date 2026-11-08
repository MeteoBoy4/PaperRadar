"""Prepare the independent T1 review material; never execute it."""

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
from scripts import issue167_live_timeout_case as contract
from scripts import issue167_live_timeout_filter as filtering
from scripts import issue167_resolver_bundle as original
from scripts import issue167_service_network_bundle as network
from scripts.issue167_h1_auto_bundle import driver_text

PROJECT = original.PROJECT
PREPARATION_READY = True
OWNER_FLAGS = (
    "--owner-config-confirmed",
    "--owner-dns-unknown-confirmed",
    "--owner-real-calls-confirmed",
    "--owner-project-duplex-timeout-confirmed",
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
            raise ValueError("timeout_cleanup_source_changed")
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
                raise ValueError("timeout_cleanup_shape_unknown")
            first = selected_node.lineno
            if isinstance(selected_node, (ast.FunctionDef, ast.ClassDef)):
                first = min([first, *(d.lineno for d in selected_node.decorator_list)])
            chunk = "".join(lines[first - 1 : selected_node.end_lineno]).encode()
            segments[name] = original.digest(chunk)
            parts.append(chunk)
        provenance[filename] = {"sha256": expected, "segments": segments}
    header = b'''"""T1 generated cleanup boundary; reviewed source chunks only."""
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
owner=importlib.import_module('scripts.issue167_live_timeout_owner')
worker=importlib.import_module('scripts.issue167_live_timeout_worker')
helper=importlib.import_module('scripts.issue167_live_timeout_cleanup')
assert Path(helper.__file__).resolve()==root/'issue167_live_timeout_cleanup.py'
assert Path(worker.__file__).resolve()==root/'issue167_live_timeout_worker.py'
assert Path(owner.__file__).resolve()==root/'issue167_live_timeout_owner.py'
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
        raise ValueError("timeout_isolated_snapshot_control_unknown")
    value = json.loads(result.stdout)
    if type(value) is not dict:
        raise ValueError("timeout_isolated_snapshot_control_unknown")
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
        raise ValueError("timeout_configuration_unknown")
    with tempfile.TemporaryDirectory(prefix="issue167-t1-materials-") as temporary:
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
                title="Synthetic T1 duplex-timeout estimator example",
                abstract=(
                    "This T1 fictional study compares toy estimators A and B on a "
                    "synthetic sequence for an duplex-timeout protocol test. "
                    "No real dataset or code is supplied."
                ),
                abstract_truncated=False,
            ),
        )
        description = build_call(stage, snapshot, snapshot)
        request = render_request(description)
        if validate_request(request) is not None:
            raise ValueError("timeout_request_unknown")
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
            "kind": "synthetic_T1_value_low_only",
            "configuration_sha256": {
                name: original.digest(raw) for name, raw in sorted(files.items())
            },
            "cases": [
                {
                    "case": "value-low-T1",
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
    files.update({"value-low-T1/" + name: raw for name, raw in cell_files.items()})
    files["manifest.json"] = canonical_json(manifest) + b"\n"
    return files


def specialize_bootstrap(source: str) -> str:
    old = '"issue167_h1_network_worker.py",'
    if source.count(old) != 1:
        raise ValueError("timeout_bootstrap_shape_unknown")
    replacements = (
        "issue167_live_timeout_case.py",
        "issue167_live_timeout_worker.py",
        "issue167_live_timeout_owner.py",
        "issue167_live_timeout_cleanup.py",
        "issue167_live_timeout_filter.py",
    )
    return source.replace(
        old, "\n            ".join(f'"{name}",' for name in replacements), 1
    )


def result_reader(run_id: str, manifest_sha: str) -> str:
    """Bounded T1 reader preserves NT without calling it T1 success."""
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
    if len(raw)>131072 or len(raw)!=before.st_size:raise ValueError()
    def invalid_constant(_):raise ValueError()
    candidate=json.loads(raw,object_pairs_hook=unique,parse_constant=invalid_constant)
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
print(json.dumps({{'owner_result':value['owner_result'],'receipt':str(r/'results/owner-run.json'),'T1_covered':value['owner_result']=='observed_expected_and_restored'}},sort_keys=True))
raise SystemExit(0 if value['owner_result']=='observed_expected_and_restored' else 1)
"""


def specialize_driver(source: str, run_id: str, manifest_sha: str) -> str:
    start, finish = "<<'LOCAL_RESULT'\n", "\nLOCAL_RESULT\n"
    if source.count(start) != 1 or source.count(finish) != 1:
        raise ValueError("timeout_driver_shape_unknown")
    prefix, rest = source.split(start, 1)
    _old, suffix = rest.split(finish, 1)
    result = (
        prefix + start + result_reader(run_id, manifest_sha).rstrip() + finish + suffix
    )
    flags = """if [[ "$#" -ne 4 || "$1" != --owner-config-confirmed ||
      "$2" != --owner-dns-unknown-confirmed ||
      "$3" != --owner-real-calls-confirmed ||
      "$4" != --owner-project-duplex-timeout-confirmed ]]; then
  printf '%s\\n' '需要本次具体H1/H2/H3批准及四项显式确认；默认不执行。' >&2
  exit 2
fi
"""
    if result.count("set -euo pipefail\n") != 1:
        raise ValueError("timeout_driver_shape_unknown")
    return result.replace("set -euo pipefail\n", "set -euo pipefail\n" + flags, 1)


def create_bundle(
    destination: Path, profile_path: Path, *, material_source: Path | None = None
) -> Path:
    if not PREPARATION_READY:
        raise ValueError("timeout_preparation_not_ready")
    from scripts.issue167_node_diag_supply import prepare_binding

    if "." in os.uname().nodename:
        raise ValueError("timeout_site_unknown")
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
        "issue167_live_timeout_case.py",
        "issue167_live_timeout_worker.py",
        "issue167_live_timeout_owner.py",
        "issue167_live_timeout_filter.py",
    ):
        (root / filename).write_bytes((PROJECT / "scripts" / filename).read_bytes())
    (root / "issue167_live_timeout_cleanup.py").write_bytes(generated_cleanup)
    bootstrap = root / "issue167_h1_auto_bootstrap.py"
    bootstrap.write_text(specialize_bootstrap(bootstrap.read_text()))
    context = {
        "kind": "live_t1_preparation_snapshot_activation_time_recheck_required",
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
    (root / "timeout-worker-entry.py").write_text(
        network.entry("issue167_live_timeout_worker", owner=False)
    )
    (root / "issue167_h1_owner_run.py").write_text(
        network.entry("issue167_live_timeout_owner", owner=True)
    )
    frozen = filtering.Plan(case.run_id)
    rules = {
        "create": filtering.render_create(frozen),
        "allow": filtering.render_allow(frozen),
        "stall": filtering.render_stall(frozen),
        "delete": filtering.render_delete(frozen),
    }
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
                "kind": "new_T1_single_case_requires_external_H1_H2_H3",
                "previous_cases_retained": True,
                "old_allowances_reused": False,
                "preparation_not_execution_authorization": True,
            },
            sort_keys=True,
        )
        + "\n"
    )
    (root / "owner-review.md").write_text(
        review_text(root, case)
        + "\n## 完整冻结规则\n\n```json\n"
        + json.dumps(rules, sort_keys=True, indent=2)
        + "\n```\n"
    )
    excluded = {"manifest.json", "owner-wizard.sh", "review-seal.json"}
    names = sorted(
        p.name for p in root.iterdir() if p.is_file() and p.name not in excluded
    )
    if len(names) != 40:
        raise ValueError("timeout_member_count_unknown")
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
    return f"""# #167 T1：单格value/low项目双向DROP，待具体新H1/H2/H3

run={case.run_id}；unit={case.unit}；唯一inet表={case.table}
code={case.install_root}；runtime={case.runtime_root}
永久记录=/var/lib/paperradar/probe-runs/issue167-{case.run_id}.json
仅准备，未预占/执行。最多auth CLI1、prompt/model1、Node2；
应用重试0、信号注入0，不重跑、不加任务、不退款。
模型value/low固定openai/gpt-6.1-sol、prompt_only/provider_default、
chatgpt_subscription，temperature/top_p=null，不扩大材料或effort迫使超时。

## 方法与停止条件

先独立绑定CG/完整双向表，deny下沿原七类IPC control/denial与文件预检；
固定pair entries7、peer operations14；Node2只限auth/model，不是总进程预算，
IPC合成进程沿固定preflight契约，类别不增加。原子allow后单CLI认证。
首个完整解码非空text_delta且同批未terminal/settled/closing时发布一次marker，
不暂停pump，不等待Root，不存正文。Root核本run/controller/CG/完整表后一次nft
事务切INPUT+OUTPUT到stall。只DROP应用可见28.0.0.0/8 TCP443两方向；
DNS仍允许192.168.44.1 UDP/TCP53，意外项目流量独立unknown阻断。
其他宿主流量不涉及，不改router、全机resolver/core或其它服务。
不使用供应商真实IP，不核上游映射/最终IP/线路，不主张出口身份。
无TLS中间人取owner来源；IPv6not_assessed。
本轮不新增DNS/TLS预热探针；Pi内部DNS/QNAME/fallback、redirect和隐藏HTTP
尝试仍unknown，须本次H2认可，与0或1逻辑刷新计划分开。owner须确认冻结pool
仍为当前配置；已知变化或未确认即停止。旧profile中的candidate_probe仅历史
计划，不在本轮执行。

只声明项目诱导双向DROP下实际Pi公共monotonic300秒截止与清理。
期限从公共factory之前开始，DROP不重置，不resume；两方向drop和完整引用
缺一unknown。自然供应商迟延/真实供应商错误不因此登记通过。
早于300秒正常完成、早期连接/已记录SDK错误、缓冲完成为not_triggered，
不补跑。半切换、缺/错参照、观察或后验失败unknown。
只输出category/sequence/count/完整性与必要固定关联，不保留原始流。

## 新H2条件计划

专用认证目录由owner维护，onlyopenai OAuth、订阅scope、无命令型/额外provider。
不沿旧E01的过期时刻或必刷新断言；本CLI条件逻辑刷新0或1并可能联网持久写。
独立模型/刷新HTTP下界0、上界unknown，packet不能当HTTP数。
旧owner确认过store空2bytes/models.json缺失，后续缓存当前内容不由agent预断；
新批次合法新增cache按S记录，未授权读取内容/到期值/长度/哈希。
pre/post仅relative文件集合+mtime/size/inode/ctime，有界nofollow双遍稳定；
marker/root稳定及schema按case约束，不推瞬时全写史或writerPID。
认证失败/超时/轮换未知即停，不回滚auth，不重试；Pi usage缺失不是零成本。

## 收尾与材料

完整公共prepare_launch/use_install/run_call，产品LAUNCH/pi_protocol不改。
service+preexec CORE0、NNP/cap空、cwd/OFD/IPC/S边界保持；
session/guard/terminal/delete均须完整。DB沿实际非空基线CAS追加后恢复原选择，
不初始化/清空/字节回滚。先回收真正子进程、CG空，再完整保存post_stop原始nft、
binding/phase_reference/counts及比较前参照；所有packet+byte与before_exit相等
才撤表/卸unit，完整恢复后清两树，永久单次记录保留。
late packet/恢复失败unknown保留材料，所有者介入仅恢复，不降旧判据。
Root只加载封印标准库闭包，不import可写应用；40member上限不扩，完整规则
随本文manifest覆盖而不另占文件。合成材料23成员经公共链新建fingerprint。
worker720s/service780s/owner900s；auth30s/model300s及原有有界回收。
新D1不扩历史分母/required/正式回执，旧unknown和普通产品缺证据阻断保持。

先审manifest/source/entry/driver及具体规则，获新H1/H2/H3后owner运行：
`bash {root}/owner-wizard.sh {" ".join(OWNER_FLAGS)}`
只在sudo TTY输入一次密码，脚本核查执行，不读取/保存密码。
本包不授权产品激活、真实资料、校准、无人值守或NAS。
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="仅准备T1单格项目双向DROP待审包")
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--profile",
        type=Path,
        default=PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
    )
    args = parser.parse_args()
    print(create_bundle(args.destination, args.profile))
