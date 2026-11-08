"""Sealed owner-only removal of one stopped synthetic probe's artifacts."""

from __future__ import annotations

import base64
import json
import os
import re
import resource
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts import issue167_live_artifact_cleanup as boundary

RUN = "d5f2a9017c84"
SCOPE = "fixed_synthetic_exit_retained_artifact_cleanup_only"
UNIT = "paperradar-167-h1net-" + RUN + ".service"
CODE = Path("/home/paperradar-probes/issue167-" + RUN)
RUNTIME = Path("/run/paperradar-issue167-" + RUN)
LEDGER = Path("/var/lib/paperradar/probe-runs/issue167-" + RUN + ".json")
CGROUP = Path("/sys/fs/cgroup/system.slice") / UNIT
LEDGER_SHA = "d4e5d06685fcc927a3d2250c82a7163b7549a08fab725bdec210fa862fc14e1f"
BOUNDARY_SHA = "e0974605d8550fb47916713824449032b3bc43c9e2ee941c4c98fb209bdd2f86"
OLD_SCOPE_SHA = "d9ea0a67f290a868851fb3935223e9904bd0badaa446a645dd2304a6d2c276a9"
OWNER_RECEIPT_SHA = "f2b16800fa8078b675cdc863a98c016160879365c4ef0dd6557043eb3f99b59c"
REASONS = frozenset(
    {
        "root_protection_unknown",
        "record_metadata_unknown",
        "record_size_unknown",
        "record_changed",
        "tree_boundary_unknown",
        "tree_already_open",
        "tree_changed",
        "tree_inventory_changed",
        "runtime_record_unbound",
        "runtime_record_changed",
        "tree_changed_during_removal",
        "artifact_mount_unknown",
        "readonly_command_unknown",
        "mount_metadata_unknown",
        "unit_not_absent",
        "cgroup_not_absent",
        "artifacts_still_present",
        "owner_root_required",
        "fixed_scope_changed",
        "approved_scope_changed",
        "host_binding_changed",
        "approved_tool_changed",
        "interpreter_changed",
        "original_ledger_metadata_changed",
        "original_ledger_changed",
        "original_restoration_unknown",
        "unit_file_not_absent",
        "approved_source_changed",
        "exit_gate_changed",
    }
)


def closed_reason(error: BaseException) -> str:
    if (
        type(error) is boundary.CleanupRejected
        and len(error.args) == 1
        and type(error.args[0]) is str
        and error.args[0] in REASONS
    ):
        return error.args[0]
    return "cleanup_operation_unknown"


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def decode_mount_path(value: str) -> str:
    if "\x00" in value or value.startswith("//"):
        raise boundary.CleanupRejected("mount_metadata_unknown")
    escapes = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}
    result = []
    offset = 0
    while offset < len(value):
        if value[offset] != "\\":
            result.append(value[offset])
            offset += 1
            continue
        token = value[offset + 1 : offset + 4]
        if token not in escapes:
            raise boundary.CleanupRejected("mount_metadata_unknown")
        result.append(escapes[token])
        offset += 4
    decoded = "".join(result)
    if any(part in {".", ".."} for part in decoded.split("/")):
        raise boundary.CleanupRejected("mount_metadata_unknown")
    return decoded


def mount_points(raw: bytes) -> set[Path]:
    if not raw or len(raw) > 1048576:
        raise boundary.CleanupRejected("mount_metadata_unknown")
    points = set()
    try:
        for line in raw.decode("utf-8").splitlines():
            fields = line.split()
            if (
                len(fields) < 10
                or fields.count("-") != 1
                or re.fullmatch(r"0|[1-9][0-9]*", fields[0]) is None
                or re.fullmatch(r"0|[1-9][0-9]*", fields[1]) is None
                or re.fullmatch(r"(?:0|[1-9][0-9]*):(?:0|[1-9][0-9]*)", fields[2])
                is None
            ):
                raise ValueError
            separator = fields.index("-")
            if separator < 6 or len(fields) != separator + 4:
                raise ValueError
            filesystem = fields[separator + 1]
            if not fields[3].startswith("/") and not (
                filesystem == "nsfs"
                and re.fullmatch(r"mnt:\[[1-9][0-9]*\]", fields[3]) is not None
            ):
                raise ValueError
            if fields[3].startswith("/"):
                decode_mount_path(fields[3])
            point = decode_mount_path(fields[4])
            if not point.startswith("/") or ".." in point.split("/"):
                raise ValueError
            points.add(Path(point))
    except (ValueError, UnicodeError):
        raise boundary.CleanupRejected("mount_metadata_unknown") from None
    if not points:
        raise boundary.CleanupRejected("mount_metadata_unknown")
    return points


def verify_host(raw: bytes, *, cgroup: Path = CGROUP) -> None:
    try:
        pairs = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
        values = dict(pairs)
        expected = {
            "Id": UNIT,
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "SubState": "dead",
            "MainPID": "0",
            "ControlGroup": "",
            "FragmentPath": "",
            "DropInPaths": "",
            "User": "",
            "Group": "",
        }
        if values != expected or len(pairs) != len(expected):
            raise ValueError
    except (ValueError, UnicodeError):
        raise boundary.CleanupRejected("unit_not_absent") from None
    if os.path.lexists(cgroup):
        raise boundary.CleanupRejected("cgroup_not_absent")


def perform(
    trees: tuple[boundary.Tree, ...],
    verify: Callable[[], None],
    check_records: Callable[[], None],
    progress: dict[str, str],
) -> dict[str, object]:
    try:
        progress["stage"] = "inspect"
        verify()
        for tree in trees:
            tree.inspect()
        progress["stage"] = "recheck"
        verify()
        for tree in trees:
            tree.verify()
        check_records()
        for tree in trees:
            tree.verify()
        progress["stage"] = "remove"
        removed = sum(tree.remove() for tree in trees)
        progress["stage"] = "final_check"
        verify()
        if any(os.path.lexists(tree.path) for tree in trees):
            raise boundary.CleanupRejected("artifacts_still_present")
        return {
            "scope": SCOPE,
            "run_id": RUN,
            "cleanup_result": "code_runtime_removed",
            "original_experiment_result": "unknown",
            "original_ledger_unchanged": True,
            "original_ledger_write_operations": 0,
            "removed_members_including_roots": removed,
            "auth_model_reexecs": 0,
            "synthetic_worker_reexecs": 0,
            "network_operations": 0,
            "database_operations": 0,
            "service_mutations": 0,
            "nft_operations": 0,
            "budget_refund": 0,
        }
    finally:
        for tree in trees:
            tree.close()


def main(config: dict[str, Any], original_scope_raw: bytes) -> int:
    progress = {"stage": "initial"}
    try:
        if os.geteuid() != 0 or os.getegid() != 0:
            raise boundary.CleanupRejected("owner_root_required")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if (
            config["scope"] != SCOPE
            or config["run_id"] != RUN
            or config["paths"] != [str(CODE), str(RUNTIME), str(LEDGER)]
            or config["ledger_sha256"] != LEDGER_SHA
            or config["boundary_sha256"] != BOUNDARY_SHA
            or config["original_scope_sha256"] != OLD_SCOPE_SHA
            or config["owner_receipt_sha256"] != OWNER_RECEIPT_SHA
            or boundary.sha(original_scope_raw) != OLD_SCOPE_SHA
            or len(config["code_inventory"]) != 13
            or len(config["runtime_inventory"]) != 5
            or config["ledger_identity"][7] != 999
        ):
            raise boundary.CleanupRejected("fixed_scope_changed")
        original = json.loads(original_scope_raw)
        if (
            original["run_id"] != RUN
            or original["scope"] != "independent_synthetic_supervisor_exit_only"
            or len(original["members"]) != 12
            or config["host"] != original["host"]
            or set(config["code_inventory"]) != {"", *original["members"]}
            or set(config["runtime_inventory"])
            != {
                "",
                "worker",
                "worker/ready.json",
                "worker/terminal.json",
                "gate-exit.json",
            }
        ):
            raise boundary.CleanupRejected("approved_scope_changed")
        host = {
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "kernel": os.uname().release,
            "machine": os.uname().machine,
            "hostname_sha256": boundary.sha(os.uname().nodename.encode()),
        }
        if host != config["host"]:
            raise boundary.CleanupRejected("host_binding_changed")
        for path in (CODE, RUNTIME, LEDGER):
            boundary.protected(path)
        for tool in original["tools"].values():
            path = Path(tool["path"])
            boundary.protected(path)
            if (
                boundary.sha(
                    boundary.record(
                        path, uid=0, mode=stat.S_IMODE(path.lstat().st_mode)
                    )
                )
                != tool["sha256"]
            ):
                raise boundary.CleanupRejected("approved_tool_changed")
        if str(Path(sys.executable).resolve()) != original["tools"]["python"]["path"]:
            raise boundary.CleanupRejected("interpreter_changed")
        trees = (
            boundary.Tree(RUNTIME, config["runtime_inventory"], 0, 1000),
            boundary.Tree(CODE, config["code_inventory"], 0),
        )

        def verify() -> None:
            boundary.protected(LEDGER)
            if boundary.identity(LEDGER.lstat()) != config["ledger_identity"]:
                raise boundary.CleanupRejected("original_ledger_metadata_changed")
            raw = boundary.record(
                LEDGER,
                uid=0,
                mode=0o600,
                limit=4096,
                expected_identity=config["ledger_identity"],
            )
            if boundary.sha(raw) != LEDGER_SHA:
                raise boundary.CleanupRejected("original_ledger_changed")
            value = json.loads(raw)
            if (
                value["run_id"] != RUN
                or value["result"] != "unknown"
                or value["restoration"] != {"unit_absent": True, "cgroup_empty": True}
                or value["exit_diagnostics"] != config["exit_diagnostics"]
            ):
                raise boundary.CleanupRejected("original_restoration_unknown")
            state = boundary.command(
                original["tools"]["systemctl"]["path"],
                [
                    "show",
                    UNIT,
                    "--property=Id,LoadState,ActiveState,SubState,MainPID,ControlGroup,FragmentPath,DropInPaths,User,Group",
                    "--no-pager",
                ],
            )
            verify_host(state)
            for directory in (Path("/etc/systemd/system"), Path("/run/systemd/system")):
                for path in (directory / UNIT, directory / (UNIT + ".d")):
                    if os.path.lexists(path):
                        raise boundary.CleanupRejected("unit_file_not_absent")
            with Path("/proc/self/mountinfo").open("rb") as source:
                points = mount_points(source.read(1048577))
            boundary.check_mounts((CODE, RUNTIME), points)

        def check_records() -> None:
            for name, expected in original["members"].items():
                raw = trees[1].read_metadata(name, uid=0, mode=0o644)
                if boundary.sha(raw) != expected:
                    raise boundary.CleanupRejected("approved_source_changed")
            gate = trees[0].read_metadata("gate-exit.json", uid=0, mode=0o644)
            if gate != encoded({"run_id": RUN, "sequence": 7}):
                raise boundary.CleanupRejected("exit_gate_changed")

        output = perform(trees, verify, check_records, progress)
        status = 0
    except BaseException as error:
        output = {
            "scope": SCOPE,
            "run_id": RUN,
            "cleanup_result": "unknown",
            "original_experiment_result": "unknown",
            "failure_stage": progress["stage"],
            "failure_reason": closed_reason(error),
            "original_ledger_write_operations": 0,
            "auth_model_reexecs": 0,
            "synthetic_worker_reexecs": 0,
            "network_operations": 0,
            "database_operations": 0,
            "service_mutations": 0,
            "nft_operations": 0,
            "budget_refund": 0,
        }
        status = 1
    print(json.dumps(output, sort_keys=True))
    return status


def render_driver(payload: bytes, manifest_sha: str) -> str:
    payload64 = base64.b64encode(payload).decode()
    return f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -ne 0 ]]; then
  printf '%s\\n' '固定仅清理入口不接受参数。' >&2
  exit 2
fi
owner_dir=$(cd -- "$(dirname -- "${{BASH_SOURCE[0]}}")" && pwd -P)
printf '%s\\n' '[H1 仅清理] 保留原unknown/账本；不重验、不启动服务。'
/usr/bin/python3 -I -S -B - "$owner_dir" <<'LOCAL_CHECK'
import hashlib,json,os,stat,sys
from pathlib import Path
r=Path(sys.argv[1]);expected={manifest_sha!r}
def read(name):
    fd=os.open(r/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        s=os.fstat(f.fileno())
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=1000 or s.st_gid!=1000
            or s.st_nlink!=1 or s.st_mode&0o022 or s.st_size>1048576):
            raise SystemExit('local_metadata_unknown')
        raw=f.read(1048577)
        if len(raw)>1048576:raise SystemExit('local_size_unknown')
        return raw
if os.getuid()!=1000 or os.getgid()!=1000:raise SystemExit('owner_identity_unknown')
for d in (r,r/'results'):
    s=d.lstat()
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=1000 or s.st_gid!=1000
        or stat.S_IMODE(s.st_mode)!=0o700):raise SystemExit('local_directory_unknown')
raw=read('manifest.json')
if hashlib.sha256(raw).hexdigest()!=expected:raise SystemExit('manifest_changed')
m=json.loads(raw);seal=json.loads(read('review-seal.json'))
if seal!={{'scope':{SCOPE!r},'run_id':{RUN!r},'manifest_sha256':expected,
          'driver_sha256':hashlib.sha256(read('owner-cleanup.sh')).hexdigest()}}:
    raise SystemExit('review_seal_changed')
members={{'boundary.py','cleanup.py','scope.json','original-scope.json','review.md'}}
if set(m['members'])!=members:
    raise SystemExit('member_scope_unknown')
for name,want in m['members'].items():
    if hashlib.sha256(read(name)).hexdigest()!=want:raise SystemExit('member_changed')
if os.path.lexists(r/'results/owner-cleanup.json'):
    raise SystemExit('result_already_present')
fd=os.open(r/'results/execution-started.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:
    json.dump({{'scope':{SCOPE!r},'run_id':{RUN!r},'state':'reserved_unknown','manifest_sha256':expected}},f,sort_keys=True)
    f.write('\\n');f.flush();os.fsync(f.fileno())
LOCAL_CHECK
owner_output=$(mktemp "$owner_dir/results/.owner-output-XXXXXX")
owner_status=0
printf '%s\\n' '[H1] 仅sudo可能请求终端密码；脚本负责核验及删除两树。'
if /usr/bin/sudo /usr/bin/python3 -I -S -B - <<'ROOT_LITERAL' > "$owner_output"
import base64,hashlib,json,sys,types
try:
    payload=base64.b64decode({payload64!r},validate=True)
    if hashlib.sha256(payload).hexdigest()!={boundary.sha(payload)!r}:raise ValueError()
    value=json.loads(payload)
    boundary_raw=base64.b64decode(value['boundary'],validate=True)
    source_raw=base64.b64decode(value['source'],validate=True)
    scope_raw=base64.b64decode(value['original_scope'],validate=True)
    if (hashlib.sha256(boundary_raw).hexdigest()!=value['config']['boundary_sha256']
        or hashlib.sha256(source_raw).hexdigest()!=value['source_sha256']
        or hashlib.sha256(scope_raw).hexdigest()!=
           value['config']['original_scope_sha256']):raise ValueError()
    package=types.ModuleType('scripts');package.__path__=[];sys.modules['scripts']=package
    for short,raw in [('issue167_live_artifact_cleanup',boundary_raw),
                      ('issue167_live_exit_artifact_cleanup',source_raw)]:
        name='scripts.'+short;module=types.ModuleType(name)
        module.__file__='<sealed:'+short+'>';module.__package__='scripts'
        sys.modules[name]=module;setattr(package,short,module)
        exec(compile(raw,module.__file__,'exec'),module.__dict__)
    status=sys.modules['scripts.issue167_live_exit_artifact_cleanup'].main(value['config'],scope_raw)
except BaseException:
    print(json.dumps({{'scope':{SCOPE!r},'run_id':{RUN!r},'cleanup_result':'unknown',
        'original_experiment_result':'unknown','failure_reason':'bootstrap_unknown',
        'auth_model_reexecs':0,'synthetic_worker_reexecs':0,'network_operations':0,
        'database_operations':0,'service_mutations':0,'nft_operations':0,'budget_refund':0}},sort_keys=True))
    status=1
sys.exit(status)
ROOT_LITERAL
then
  owner_status=0
else
  owner_status=$?
fi
/usr/bin/python3 -I -S -B - \\
  "$owner_dir" "$owner_output" "$owner_status" <<'LOCAL_RECEIPT'
import json,os,sys
from pathlib import Path
r=Path(sys.argv[1]);output=Path(sys.argv[2]);status=int(sys.argv[3])
try:
    raw=output.read_bytes()
    if len(raw)>4096:raise ValueError()
    value=json.loads(raw)
    if (value['scope']!={SCOPE!r} or value['run_id']!={RUN!r}
        or value['original_experiment_result']!='unknown'
        or any(type(value[k]) is not int or value[k]!=0 for k in
               ['auth_model_reexecs','synthetic_worker_reexecs','network_operations',
                'database_operations','service_mutations','nft_operations','budget_refund'])
        or (status==0 and value['cleanup_result']!='code_runtime_removed')
        or (status!=0 and value['cleanup_result']!='unknown')):raise ValueError()
except BaseException:
    value={{'scope':{SCOPE!r},'run_id':{RUN!r},'cleanup_result':'unknown',
        'original_experiment_result':'unknown','failure_reason':'owner_output_unknown',
        'auth_model_reexecs':0,'synthetic_worker_reexecs':0,'network_operations':0,
        'database_operations':0,'service_mutations':0,'nft_operations':0,'budget_refund':0}}
value['owner_exit_status']=status
fd=os.open(r/'results/owner-cleanup.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:
    json.dump(value,f,sort_keys=True);f.write('\\n');f.flush();os.fsync(f.fileno())
output.unlink()
print('清理结果：'+value['cleanup_result']+'；原实验仍unknown；回执已保存。')
if value['cleanup_result']!='code_runtime_removed':raise SystemExit(1)
LOCAL_RECEIPT
exit "$owner_status"
"""


def build_package(destination: Path, workspace: Path) -> dict[str, str]:
    metadata = json.loads((destination / "host-metadata.json").read_bytes())
    destination.chmod(0o700)
    old = workspace / ".scratch/issue-167/live-exit-probe-v1"
    old_scope_raw = (old / "scope.json").read_bytes()
    old_scope = json.loads(old_scope_raw)
    public_receipt_raw = (old / "results/owner-run.json").read_bytes()
    original_result = json.loads(public_receipt_raw)
    if original_result.pop("owner_exit_status") != 1:
        raise boundary.CleanupRejected("original_owner_status_unknown")
    ledger_raw = encoded(original_result)
    if (
        boundary.sha(old_scope_raw) != OLD_SCOPE_SHA
        or boundary.sha(public_receipt_raw) != OWNER_RECEIPT_SHA
        or len(ledger_raw) != 999
        or boundary.sha(ledger_raw) != LEDGER_SHA
        or len(metadata["code_inventory"]) != 13
        or len(metadata["runtime_inventory"]) != 5
        or metadata["ledger_identity"][7] != 999
    ):
        raise boundary.CleanupRejected("preparation_reference_unknown")
    boundary_raw = (
        workspace / "scripts/issue167_live_artifact_cleanup.py"
    ).read_bytes()
    source_raw = (
        workspace / "scripts/issue167_live_exit_artifact_cleanup.py"
    ).read_bytes()
    if boundary.sha(boundary_raw) != BOUNDARY_SHA:
        raise boundary.CleanupRejected("boundary_source_changed")
    config = {
        "scope": SCOPE,
        "run_id": RUN,
        "paths": [str(CODE), str(RUNTIME), str(LEDGER)],
        "ledger_sha256": LEDGER_SHA,
        "boundary_sha256": BOUNDARY_SHA,
        "original_scope_sha256": OLD_SCOPE_SHA,
        "owner_receipt_sha256": OWNER_RECEIPT_SHA,
        "host": old_scope["host"],
        "exit_diagnostics": original_result["exit_diagnostics"],
        "code_inventory": metadata["code_inventory"],
        "runtime_inventory": metadata["runtime_inventory"],
        "ledger_identity": metadata["ledger_identity"],
    }
    review = f"""# #167 d5仅清理保留目录：待新H1，尚未执行

原run={RUN}仍unknown；门闩写入/严格退出及unit、CG恢复有据，artifact清理未完成。
新包不重验、不改原结果、不退款。仅删除两棵精确树，预计18节点（code13+runtime5）：
- `{CODE}`：root:root0755，dev/inode及12文件完整metadata绑定见scope。
- `{RUNTIME}`：root:root0755，仅root gate与UID1000 worker/ready/terminal。
永久 `{LEDGER}` 为root:root0600、999bytes；
原dev/inode/mtime/ctime与SHA始终核对，绝不写或删。
其预期SHA从公开owner结果去掉仅本地owner_exit_status后按原编码派生；agent未读取root账本正文。

## 所有者动作与边界

单次sudo字面stdin先核固定两模块/本机/原scope12源码及工具；完整两树pin后，
仅按固定源码和gate预期读取这些公开记录，read前核已打开FD完整身份；其它runtime内容只看metadata。
只读systemctl show具名unit，必须not-found/inactive/dead/MainPID0，
CG/fragment/dropin/user/group为空，
unit文件/dropin和本CG目录均须缺失。不做start/stop/reset/reload、nft/resolver、DB或任何重跑。
全部目标先经过两阶段host/ledger/mount/inventory验证，
再FD-relative unlink/rmdir，最后复核两树absent及原账本不变。

mountinfo有界1MiB、非空/完整行和严格转义；第4root只接受绝对路径，或本机当前实际观察到的
`fstype=nsfs`且`mnt:[正十进制inode]`。其它未知namespace或非路径形态仍unknown。
ASCII结构数字、NUL、dot components及双斜杠开头均严格核验，畸形观测不参与删除。
第5mountpoint始终严格解码且absolute，两树下面的任何mount仍拒绝；不会忽略mount观察失败。
这是本次受限清理规则，不自动扩展成所有namespace的通用支持，也不改宿主挂载。

新root代码仅用先核SHA的字面stdin加载两个标准库模块，不从可写工作区import应用；
旧helper只复用Tree/protected/record/check_mounts/command，绝不调用旧main/perform或其e93/nft路径。
原scope、公开回执、新两树的metadata和所有绑定只留本地。

无Pi/Node、凭据、日志/core/environ、网络、认证/模型、合成worker、实验库或额外额度操作。
原ledger/回执/旧unknown不变。删除中途失败可能留下部分树，报unknown且不自动重试；没有回滚或自动补验。
本包未执行；新D1仅/tmp/mock，不扩历史分母/required/正式回执。

## 审阅后入口

先审manifest.json、scope.json、original-scope.json、全部两模块和owner-cleanup.sh，核review-seal。
获新H1后运行 `bash {destination}/owner-cleanup.sh`，只在sudo终端输入一次密码。
入口原子预占本地execution-started，一次失败也不自动重试；输出只存受控清理类别/计数/完整性，
结果到results/owner-cleanup.json。root动作由所有者审阅执行。
"""
    artifacts = {
        "boundary.py": boundary_raw,
        "cleanup.py": source_raw,
        "scope.json": encoded(config),
        "original-scope.json": old_scope_raw,
        "review.md": review.encode(),
    }
    results = destination / "results"
    results.mkdir(mode=0o700)
    (destination / "host-metadata.json").rename(results / "host-metadata.json")
    for name, raw in artifacts.items():
        with (destination / name).open("xb") as output:
            output.write(raw)
        (destination / name).chmod(0o600)
    manifest = encoded(
        {
            "scope": SCOPE,
            "run_id": RUN,
            "members": {name: boundary.sha(raw) for name, raw in artifacts.items()},
        }
    )
    with (destination / "manifest.json").open("xb") as output:
        output.write(manifest)
    (destination / "manifest.json").chmod(0o600)
    payload = encoded(
        {
            "boundary": base64.b64encode(boundary_raw).decode(),
            "source": base64.b64encode(source_raw).decode(),
            "source_sha256": boundary.sha(source_raw),
            "original_scope": base64.b64encode(old_scope_raw).decode(),
            "config": config,
        }
    )
    driver = render_driver(payload, boundary.sha(manifest)).encode()
    with (destination / "owner-cleanup.sh").open("xb") as output:
        output.write(driver)
    (destination / "owner-cleanup.sh").chmod(0o700)
    seal = encoded(
        {
            "scope": SCOPE,
            "run_id": RUN,
            "manifest_sha256": boundary.sha(manifest),
            "driver_sha256": boundary.sha(driver),
        }
    )
    with (destination / "review-seal.json").open("xb") as output:
        output.write(seal)
    (destination / "review-seal.json").chmod(0o600)
    return {
        "review_seal_sha256": boundary.sha(seal),
        "manifest_sha256": boundary.sha(manifest),
        "driver_sha256": boundary.sha(driver),
    }
