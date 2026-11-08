"""Prepare the independent no-credential duplex review package; never run it."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts import issue167_duplex_probe as probe
from scripts import issue167_h1_guardian as guard
from scripts.issue167_live_signal_bundle import cleanup_source as cleanup_source

PROJECT = Path(__file__).absolute().parent.parent
MODULE_ORDER = (
    "issue167_h1_phase",
    "issue167_h1_guardian",
    "issue167_duplex_filter",
    "issue167_duplex_cleanup",
    "issue167_duplex_probe",
)
MAX_RESULT_BYTES = 131072
PREPARATION_READY = True


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def worker_entry() -> bytes:
    members = tuple(sorted(probe.CORE_NAMES | {"scope.json"}))
    return f'''"""Bound synthetic role entry. No workspace fallback."""
import hashlib,importlib.abc,importlib.util,json,os,stat,sys,types
from pathlib import Path
ROOT=Path(__file__).absolute().parent
RUN={probe.RUN!r}
SCOPE={probe.SCOPE!r}
MEMBERS={members!r}
MODULES={MODULE_ORDER!r}
def pairs(items):
    result={{}}
    for key,value in items:
        if key in result:raise ValueError('entry_metadata_unknown')
        result[key]=value
    return result
def protected(path,directory=False):
    for part in (path,*path.parents):
        s=part.lstat()
        if (s.st_uid!=0 or s.st_gid!=0 or s.st_mode&0o022
            or stat.S_ISLNK(s.st_mode)):
            raise ValueError('entry_protection_unknown')
    if directory and not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError('entry_protection_unknown')
def read(path,limit=1048576):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        a=os.fstat(fd)
        if (not stat.S_ISREG(a.st_mode) or a.st_uid!=0 or a.st_gid!=0
            or a.st_nlink!=1 or a.st_mode&0o022 or a.st_size>limit):
            raise ValueError('entry_file_unknown')
        raw=os.read(fd,limit+1);b=os.fstat(fd)
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,
                        s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(raw)>limit or stamp(a)!=stamp(b):raise ValueError('entry_file_unknown')
        return raw
    finally:os.close(fd)
class ClosedLoader(importlib.abc.Loader):
    def __init__(self,name,raw):self.name,self.raw=name,raw
    def create_module(self,spec):return None
    def exec_module(self,module):
        module.__file__=str(ROOT/(self.name.rsplit('.',1)[1]+'.py'))
        exec(compile(self.raw,module.__file__,'exec'),module.__dict__)
class ClosedFinder(importlib.abc.MetaPathFinder):
    def __init__(self,sources):self.sources=sources
    def find_spec(self,name,path=None,target=None):
        if name.startswith('scripts.'):
            if name not in self.sources:
                raise ModuleNotFoundError('entry_import_unknown')
            return importlib.util.spec_from_loader(
                name,ClosedLoader(name,self.sources[name]))
        if name=='paper_radar' or name.startswith('paper_radar.'):
            raise ModuleNotFoundError('entry_import_unknown')
        return None
def entry():
    if (len(sys.argv)!=2 or sys.argv[1] not in ('client','peer')
        or os.getuid()!=1000 or os.getgid()!=1000):
        raise ValueError('entry_role_unknown')
    if str(ROOT)!='/home/paperradar-probes/issue167-'+RUN:
        raise ValueError('entry_root_unknown')
    protected(ROOT,True)
    manifest=json.loads(read(ROOT/'manifest.json'),object_pairs_hook=pairs)
    if (set(manifest)!={{'scope','run_id','members','tools'}}
        or manifest['scope']!=SCOPE or manifest['run_id']!=RUN
        or set(manifest['members'])!=set(MEMBERS)
        or set(os.listdir(ROOT))!=set(MEMBERS)|{{'manifest.json'}}):
        raise ValueError('entry_manifest_unknown')
    sources={{}}
    for name in MEMBERS:
        raw=read(ROOT/name)
        if hashlib.sha256(raw).hexdigest()!=manifest['members'][name]:
            raise ValueError('entry_source_unknown')
        if name.endswith('.py') and name!='worker-entry.py':
            sources['scripts.'+name[:-3]]=raw
    python=Path(manifest['tools']['python']['path']);protected(python)
    if (str(Path(sys.executable).resolve())!=str(python)
        or hashlib.sha256(read(python,33554432)).hexdigest()
           !=manifest['tools']['python']['sha256']):
        raise ValueError('entry_python_unknown')
    package=types.ModuleType('scripts');package.__path__=[];sys.modules['scripts']=package
    sys.meta_path.insert(0,ClosedFinder(sources))
    for short in MODULES:__import__('scripts.'+short)
    return sys.modules['scripts.issue167_duplex_probe'].worker_main(sys.argv[1])
try:status=entry()
except BaseException:status=1
raise SystemExit(status)
'''.encode()


def local_result_source(manifest_sha: str, root_manifest_sha: str) -> str:
    return f"""import json,os,stat,sys
from pathlib import Path
ROOT=Path(sys.argv[1]);OUTPUT=Path(sys.argv[2]);STATUS=int(sys.argv[3])
def pairs(items):
    result={{}}
    for key,value in items:
        if key in result:raise ValueError()
        result[key]=value
    return result
def same(a,b):
    return (json.dumps(a,sort_keys=True,allow_nan=False)
            ==json.dumps(b,sort_keys=True,allow_nan=False))
def constant(_):raise ValueError()
try:
    fd=os.open(OUTPUT,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        a=os.fstat(fd)
        if (not stat.S_ISREG(a.st_mode) or a.st_uid!=1000 or a.st_gid!=1000
            or a.st_nlink!=1 or stat.S_IMODE(a.st_mode)!=0o600
            or a.st_size>{MAX_RESULT_BYTES}):raise ValueError()
        with os.fdopen(fd,'rb',closefd=False) as source:
            raw=source.read({MAX_RESULT_BYTES + 1})
        b=os.fstat(fd)
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,
                        s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(raw)>{MAX_RESULT_BYTES} or stamp(a)!=stamp(b):raise ValueError()
    finally:os.close(fd)
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)
    if (type(value) is not dict or value.get('scope')!={probe.SCOPE!r}
        or value.get('run_id')!={probe.RUN!r}
        or not same(value.get('limits'),{probe.LIMITS!r})
        or value.get('installed_manifest_sha256')!={root_manifest_sha!r}):
        raise ValueError()
    if value.get('result')=='observed_expected_and_restored':
        restored={{'unit_absent':True,'table_absent':True,'cgroup_empty':True,
                  'peer_reaped':True,'ledger_retained':True}}
        removed={{'code_runtime_removed':True,'ledger_retained':True}}
        if (STATUS!=0 or not same(value.get('restoration'),restored)
            or not same(value.get('artifacts'),removed)):raise ValueError()
    elif value.get('result')=='unknown':
        if STATUS==0:raise ValueError()
    else:raise ValueError()
except BaseException:
    value={{'scope':{probe.SCOPE!r},'run_id':{probe.RUN!r},'result':'unknown','failure_reason':'owner_output_unknown','limits':{probe.LIMITS!r},'installed_manifest_sha256':{root_manifest_sha!r}}}
value['manifest_sha256']={manifest_sha!r};value['owner_exit_status']=STATUS
fd=os.open(ROOT/'results/owner-run.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as output:
    json.dump(value,output,sort_keys=True,allow_nan=False)
    output.write('\\n');output.flush();os.fsync(output.fileno())
print('合成双向机制：'+value['result']+'；无模型调用；回执已保存。')
if value['result']!='observed_expected_and_restored':raise SystemExit(1)
"""


def render_driver(
    config: dict[str, Any], files: dict[str, bytes], manifest_sha: str
) -> bytes:
    root_manifest = probe.installed_manifest(config, files)
    payload = encoded(
        {
            "config": config,
            "files": {n: base64.b64encode(v).decode() for n, v in files.items()},
            "root_manifest": base64.b64encode(root_manifest).decode(),
        }
    )
    parts = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'if [[ "$#" -ne 1 || "$1" != --owner-duplex-synthetic-confirmed ]]; then',
        "  printf '%s\\n' '仅在本包单次H1获批后使用指定确认参数。' >&2",
        "  exit 2",
        "fi",
        'owner_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)',
        "printf '%s\\n' '[H1 T1合成双向机制] 核验封印→预占→自有角色/规则→核对→恢复。'",
        "/usr/bin/python3 -I -S -B - \"$owner_dir\" <<'LOCAL_CHECK'",
        local_check_source(manifest_sha),
        "LOCAL_CHECK",
        'owner_output=$(mktemp "$owner_dir/results/.owner-output-XXXXXX")',
        "owner_status=0",
        "printf '%s\\n' '[H1] 只在sudo终端输入密码；无认证/模型，不自动重试。'",
        "if /usr/bin/sudo /usr/bin/python3 -I -S -B - "
        "<<'ROOT_LITERAL' > \"$owner_output\"",
        root_literal(payload, digest(root_manifest)),
        "ROOT_LITERAL",
        "then owner_status=0",
        "else owner_status=$?",
        "fi",
        '/usr/bin/python3 -I -S -B - "$owner_dir" "$owner_output" "$owner_status" '
        "<<'LOCAL_RESULT'",
        local_result_source(manifest_sha, digest(root_manifest)),
        "LOCAL_RESULT",
        'rm -- "$owner_output"',
        'exit "$owner_status"',
        "",
    ]
    return "\n".join(parts).encode()


def local_check_source(manifest_sha: str) -> str:
    members = tuple(
        sorted(
            {
                *probe.CORE_NAMES,
                "scope.json",
                "installed-manifest.json",
                "owner-review.md",
            }
        )
    )
    return f"""import hashlib,json,os,stat,sys
from pathlib import Path
r=Path(sys.argv[1]);expected={manifest_sha!r}
def pairs(items):
    d={{}}
    for k,v in items:
        if k in d:raise SystemExit('local_metadata_unknown')
        d[k]=v
    return d
def read(name):
    fd=os.open(r/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if (not stat.S_ISREG(a.st_mode) or a.st_uid!=1000 or a.st_gid!=1000
            or a.st_nlink!=1 or a.st_mode&0o022 or a.st_size>2097152):
            raise SystemExit('local_metadata_unknown')
        with os.fdopen(fd,'rb',closefd=False) as source:raw=source.read(2097153)
        b=os.fstat(fd)
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,
                        s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(raw)>2097152 or stamp(a)!=stamp(b):
            raise SystemExit('local_metadata_unknown')
        return raw
    finally:os.close(fd)
if os.getuid()!=1000 or os.getgid()!=1000:raise SystemExit('owner_identity_unknown')
for p in (r,r/'results'):
    s=p.lstat()
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=1000 or s.st_gid!=1000
        or stat.S_IMODE(s.st_mode)!=0o700):raise SystemExit('local_directory_unknown')
raw=read('manifest.json')
if hashlib.sha256(raw).hexdigest()!=expected:raise SystemExit('manifest_changed')
m=json.loads(raw,object_pairs_hook=pairs)
seal=json.loads(read('review-seal.json'),object_pairs_hook=pairs)
expected_seal={{'scope':{probe.SCOPE!r},'run_id':{probe.RUN!r},
               'manifest_sha256':expected,
               'driver_sha256':hashlib.sha256(read('owner-wizard.sh')).hexdigest()}}
if seal!=expected_seal:raise SystemExit('seal_changed')
if (set(m)!={{'scope','run_id','members','root_manifest_sha256'}}
    or m['scope']!={probe.SCOPE!r} or m['run_id']!={probe.RUN!r}
    or set(m['members'])!=set({members!r})):raise SystemExit('member_scope_unknown')
for n,w in m['members'].items():
    if (Path(n).name!=n or n in {{'.','..'}}
        or hashlib.sha256(read(n)).hexdigest()!=w):raise SystemExit('member_changed')
if (m['root_manifest_sha256']!=
    hashlib.sha256(read('installed-manifest.json')).hexdigest()):
    raise SystemExit('installed_manifest_changed')
if os.path.lexists(r/'results/owner-run.json'):
    raise SystemExit('result_already_present')
fd=os.open(r/'results/execution-started.json',
           os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:
    json.dump({{'scope':{probe.SCOPE!r},'run_id':{probe.RUN!r},
               'state':'reserved_unknown','manifest_sha256':expected}},f,sort_keys=True)
    f.write('\\n');f.flush();os.fsync(f.fileno())
"""


def root_literal(payload: bytes, root_manifest_sha: str) -> str:
    return f"""import base64,hashlib,json,sys,types
try:
    raw=base64.b64decode({base64.b64encode(payload).decode()!r},validate=True)
    if hashlib.sha256(raw).hexdigest()!={digest(payload)!r}:raise ValueError()
    payload=json.loads(raw);config=payload['config']
    files={{n:base64.b64decode(v,validate=True)
           for n,v in payload['files'].items()}}
    if set(files)!={{*config['members'],'scope.json'}}:raise ValueError()
    for n,w in config['members'].items():
        if hashlib.sha256(files[n]).hexdigest()!=w:raise ValueError()
    package=types.ModuleType('scripts');package.__path__=[];sys.modules['scripts']=package
    for short in {MODULE_ORDER!r}:
        name='scripts.'+short;module=types.ModuleType(name)
        module.__file__='<sealed:'+short+'>';module.__package__='scripts'
        sys.modules[name]=module;setattr(package,short,module)
        exec(compile(files[short+'.py'],module.__file__,'exec'),module.__dict__)
    owner=sys.modules['scripts.issue167_duplex_probe']
    cleanup=sys.modules['scripts.issue167_duplex_cleanup']
    if (owner.installed_manifest(config,files)!=
        base64.b64decode(payload['root_manifest'],validate=True)):raise ValueError()
    status=owner.owner_main(config,files,cleanup)
except BaseException:
    print(json.dumps({{'scope':{probe.SCOPE!r},'run_id':{probe.RUN!r},
        'result':'unknown','failure_reason':'owner_bootstrap_unknown',
        'limits':{probe.LIMITS!r},
        'installed_manifest_sha256':{root_manifest_sha!r}}},sort_keys=True));status=1
sys.exit(status)
"""


def build_package(destination: Path, workspace: Path) -> dict[str, str]:
    if not PREPARATION_READY:
        raise ValueError("duplex_preparation_not_ready")
    if destination.exists() or destination.is_symlink():
        raise ValueError("duplex_destination_present")
    case = probe.Case()
    tools = prepare_tools()
    files = {
        short + ".py": (workspace / "scripts" / (short + ".py")).read_bytes()
        for short in MODULE_ORDER
        if short != "issue167_duplex_cleanup"
    }
    files["issue167_duplex_cleanup.py"] = cleanup_source(workspace)
    files["worker-entry.py"] = worker_entry()
    files["probe.service"] = probe.render_unit(case, tools["python"]["path"]).encode()
    if set(files) != probe.CORE_NAMES:
        raise ValueError("duplex_member_scope_unknown")
    config = {
        "scope": probe.SCOPE,
        "run_id": probe.RUN,
        "host": probe.host_context(),
        "members": {n: digest(raw) for n, raw in files.items()},
        "tools": tools,
        "limits": dict(probe.LIMITS),
    }
    files["scope.json"] = encoded(config)
    root_manifest = probe.installed_manifest(config, files)
    artifacts = {
        **files,
        "installed-manifest.json": root_manifest,
        "owner-review.md": review_text(destination).encode(),
    }
    manifest = encoded(
        {
            "scope": probe.SCOPE,
            "run_id": probe.RUN,
            "members": {n: digest(raw) for n, raw in artifacts.items()},
            "root_manifest_sha256": digest(root_manifest),
        }
    )
    driver = render_driver(config, files, digest(manifest))
    seal = encoded(
        {
            "scope": probe.SCOPE,
            "run_id": probe.RUN,
            "manifest_sha256": digest(manifest),
            "driver_sha256": digest(driver),
        }
    )
    destination.mkdir(mode=0o700)
    (destination / "results").mkdir(mode=0o700)
    for n, raw in {
        **artifacts,
        "manifest.json": manifest,
        "owner-wizard.sh": driver,
        "review-seal.json": seal,
    }.items():
        with (destination / n).open("xb") as output:
            output.write(raw)
        (destination / n).chmod(0o700 if n == "owner-wizard.sh" else 0o600)
    return {
        "review_seal_sha256": digest(seal),
        "manifest_sha256": digest(manifest),
        "driver_sha256": digest(driver),
        "installed_manifest_sha256": digest(root_manifest),
    }


def prepare_tools() -> dict[str, dict[str, str]]:
    tools = {}
    for name, literal in {
        "python": "/usr/bin/python3",
        "systemctl": "/usr/bin/systemctl",
        "nft": "/usr/sbin/nft",
        "systemd_analyze": "/usr/bin/systemd-analyze",
    }.items():
        path = Path(literal).resolve(strict=True)
        guard.protected_path(path)
        tools[name] = {"path": str(path), "sha256": digest(path.read_bytes())}
    return tools


def worker_load_control(root: Path) -> dict[str, Any]:
    """Exercise real entry checks on sealed copies; only worker_main is removed."""
    program = r"""import ast,json,os,shutil,socket,sqlite3,signal,stat
import subprocess,sys,tempfile,types
from pathlib import Path
source_root=Path(sys.argv[1]).resolve()
installed=json.loads((source_root/'installed-manifest.json').read_bytes())
scope=json.loads((source_root/'scope.json').read_bytes())
logical='/home/paperradar-probes/issue167-'+scope['run_id']
allowed=set(installed['members'])|{'manifest.json'}
python=Path(scope['tools']['python']['path'])
tree=ast.parse((source_root/'worker-entry.py').read_bytes())
removed=0
for node in ast.walk(tree):
    if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
        and node.func.attr=='worker_main'):
        node.func=ast.Name(id='main_removed',ctx=ast.Load());removed+=1
assert removed==1
active=[];main_calls=[];opened=[];fds={}
def forbidden(*args,**kwargs):
    active.append(True);raise AssertionError('active_operation_blocked')
def main_removed(*args,**kwargs):return 0
def synthetic(info):
    names=('st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink','st_size',
           'st_mtime_ns','st_ctime_ns')
    fields={n:getattr(info,n) for n in names}
    fields.update(st_uid=0,st_gid=0)
    return types.SimpleNamespace(**fields)
real_open,real_close,real_fstat=os.open,os.close,os.fstat
real_listdir,real_lstat=os.listdir,Path.lstat
ancestors=set(str(p) for p in Path(logical).parents)
ancestors.update(str(p) for p in python.parents)
ancestors.add(str(python))
with tempfile.TemporaryDirectory(prefix='issue167-duplex-entry-control-') as temp:
    copy_root=Path(temp)
    for name in installed['members']:
        shutil.copyfile(source_root/name,copy_root/name)
        (copy_root/name).chmod(0o644)
    shutil.copyfile(source_root/'installed-manifest.json',copy_root/'manifest.json')
    (copy_root/'manifest.json').chmod(0o644)
    def mapped(path):
        text=os.fsdecode(path)
        if text==logical:return copy_root
        if text.startswith(logical+'/'):
            name=text[len(logical)+1:]
            if name not in allowed:raise AssertionError('entry_unknown_path')
            return copy_root/name
        if text==str(python):return python
        raise AssertionError('entry_unknown_path')
    def opened_file(path,flags,*args,**kwargs):
        target=mapped(path)
        assert flags&os.O_WRONLY==0 and flags&os.O_RDWR==0
        handle=real_open(target,flags,*args,**kwargs)
        fds[handle]=True;opened.append(str(path));return handle
    def closed_file(handle):
        fds.pop(handle,None);return real_close(handle)
    def stat_file(handle):
        value=real_fstat(handle)
        return synthetic(value) if handle in fds else value
    def lstat_path(path,*args,**kwargs):
        text=str(path)
        if text in ancestors:
            if text==str(python):return synthetic(real_lstat(python))
            return types.SimpleNamespace(st_uid=0,st_gid=0,
                                         st_mode=stat.S_IFDIR|0o755)
        if text==logical or text.startswith(logical+'/'):
            return synthetic(real_lstat(mapped(path)))
        return real_lstat(path,*args,**kwargs)
    def listed(path):
        if str(path)==logical:return real_listdir(copy_root)
        return real_listdir(path)
    try:
        os.open=opened_file;os.close=closed_file;os.fstat=stat_file
        Path.lstat=lstat_path;os.listdir=listed
        subprocess.Popen=forbidden;socket.socket=forbidden
        sqlite3.connect=forbidden;signal.pidfd_send_signal=forbidden
        os.kill=forbidden;os.killpg=forbidden
        sys.argv=[logical+'/worker-entry.py','client']
        namespace={'__name__':'__main__','__file__':sys.argv[0],
                   'main_removed':main_removed}
        try:exec(compile(ast.fix_missing_locations(tree),'entry-control','exec'),namespace)
        except SystemExit as error:assert error.code==0
        assert not active and not fds
        assert len(opened)==10
        assert len([n for n in sys.modules if n.startswith('scripts.')])==5
        assert not any(n=='paper_radar' or n.startswith('paper_radar.')
                       for n in sys.modules)
    finally:
        os.open=real_open;os.close=real_close;os.fstat=real_fstat
        Path.lstat=real_lstat;os.listdir=real_listdir
print(json.dumps({'scope':'sealed_worker_entry_load_only',
                  'worker_main_calls':0,'removed_main_calls':removed,
                  'root_source_modules':5,'sealed_or_python_reads':len(opened),
                  'active_operations':len(active),'workspace_fallback':False,
                  'synthetic_permission_and_prefix_mapping':True},sort_keys=True))
"""
    result = subprocess.run(
        ["/usr/bin/python3", "-I", "-S", "-B", "-", str(root.resolve())],
        input=program.encode(),
        capture_output=True,
        check=False,
        timeout=15,
        cwd="/tmp",
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if result.returncode or result.stderr or len(result.stdout) > 4096:
        raise ValueError("duplex_worker_load_control_unknown")
    value = json.loads(result.stdout)
    if type(value) is not dict:
        raise ValueError("duplex_worker_load_control_unknown")
    return value


def review_text(destination: Path) -> str:
    case = probe.Case()
    return f"""# #167 T1双向过滤无凭据合成验证：待具体H1，尚未执行

run={probe.RUN}；unit={case.plan.unit}；唯一inet表={case.plan.table}
代码={case.code}；runtime={case.runtime}；永久单次记录={case.ledger}

本包仅准备项目INPUT+OUTPUT机制，不运行Pi/Node、认证/刷新/模型，
不读凭据/cache/业务DB或安装锁；不授权后续真实Pi300秒。
K2保持不另备E02，旧unknown/消耗/回归用例保留。

## 所有者将执行

核本机/工具/完整来源及目标缺失，预占永久单次记录；
安装本次root-owned代码与具名单元，派生installed manifest。
启动一个CG外owned UID1000 peer和一个UID1000 client unit。
peer只在127.0.0.1:46167监听，主连接与同UID CG外control连接
共2个active connect/2 accept；application send最多12（预期10），
无应用重试/端口fallback，不沿旧余额。
TCP重传次数是unknown传输层，不是应用重发。

allow双向A到达→一次事务切换INPUT+OUTPUT stall→两端各send唯一B一次，
持续有界recv（新增payload须0）、两方向drop counter各增，
CG外control在stall中双向成功→实验phase resume allow后同B到达，
不app重发。实验resume不是最终host恢复，不能用它容忍late packet。

独立CG dev/inode、table/chain/counter/rule引用及完整快照逐阶段核验；
单边切换、未知归属、额外规则、计数回退、错误数据/时序或观察失败
均unknown，不换UID/放宽地址/停读数据假装挂起。
INPUT socket/cgroup效果本轮尚未实测，不能拿旧OUTPUT当覆盖；
loopback高端口结果不自动证明真实TCP443/Pi/供应商挂起。

最终清目标CG/停owned peer，再严格post_stop计数稳定和fullbinding，
才撤本表/本unit并清两树，永久记录保留。
late packet/恢复失败unknown留材料，所有者仅恢复；不为回收放宽判据。
删除中途失败可能留下部分树，不自动重验/退款。

worker75秒/service90秒/owner180秒，命令各8秒，
negative observation受控绝对时点；详细额度见scope.json。
只影响精确项目CG；其它流量policy accept，控制仅证明本例同UID不同CG。
不改全机/router/DNS/core或其它单元，不使用供应商IP，
无外部DNS/TLS，IPv6not_assessed。

## 材料与root边界

新scope core7＋scope.json部署8files，Root另生成installed manifest；
外层manifest审10成员（部署8＋installed-manifest.json＋本review），
避免config自hash循环。5个标准库模块闭包，root字面stdin先核SHA再load，
不Root import工作区应用。worker entry逐成员核root保护/完整hash，
仅closed scripts sources和系统Python-I-S-B，没有workspace fallback。
generated cleanup只含已审Tree/record/strict mount parser chunks，
不带旧main/perform/旧RUN路径。
本scope实际回收使用probe.PinnedArtifactTree：逐祖先FD固定，
先核封闭名字集合再stat/descend，两树全验后才删；
不调用旧通用Tree.inspect扫描陌生目录。

H1批准后由所有者运行：
`bash {destination}/owner-wizard.sh --owner-duplex-synthetic-confirmed`

只在sudo终端输入一次密码，脚本核验执行，不读取/保存密码。真实规则/连接尚未执行，准备自检不授执行许可。后续真实Pi300秒/网络挂起仍另冻结并批准H1/H2/H3；自然供应商迟延/错误不得由本合成验证记通过，产品准入仍阻断。
"""
