"""Fixed Node builtin-only diagnostic; execution requires a separately approved unit."""

from __future__ import annotations

import ctypes
import json
import os
import selectors
import stat
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, cast

from scripts import issue167_dns_tls as probe
from scripts import issue167_node_diag_case as contract
from scripts import issue167_resolver_worker as local
from scripts.issue167_resolver_case import pairs


class NodeHandle(Protocol):
    @property
    def node(self) -> Path: ...
    @property
    def install(self) -> Path: ...
    @property
    def pass_fds(self) -> tuple[int, ...]: ...


JS = r"""'use strict';
const fs=require('node:fs'),net=require('node:net');
const dns=require('node:dns'),tls=require('node:tls');
const [mode,host,expected,timeout,lockfd,device,inode,cgroup]=process.argv.slice(1);
let socket=null,done=false,outcome='unknown';
let lookupCalls=0,tlsCalls=0,address=null,version=null;
let timer;
function identity(){
 const status=fs.readFileSync('/proc/self/status','utf8');
 const limits=fs.readFileSync('/proc/self/limits','utf8');
 const core=limits.match(/^Max core file size\s+(\S+)\s+(\S+)/m);
 const lock=fs.fstatSync(Number(lockfd));
 return {uid:process.getuid(),core_zero:!!core&&core[1]==='0'&&core[2]==='0',
 no_new_privs:/^NoNewPrivs:\s+1$/m.test(status),cap_eff_zero:/^CapEff:\s+0+$/m.test(status),
 cgroup_matches:fs.readFileSync('/proc/self/cgroup','utf8')==='0::'+cgroup+'\n',
 lock_inherited:String(lock.dev)===device&&String(lock.ino)===inode};
}
function finish(clean){
 if(done)return;done=true;clearTimeout(timer);
 try{process.stdout.write(JSON.stringify({...identity(),category:mode,result:outcome,
 cleanup_complete:clean,lookup_calls:lookupCalls,tls_calls:tlsCalls,address:address,
 tls_version:version})+'\n');}catch{process.exitCode=1;}
}
function close(){if(socket)socket.destroy();else finish(true);}
timer=setTimeout(()=>{outcome='unknown';close();},Number(timeout));
function attach(channel){socket=channel;channel.once('close',()=>finish(true));}
try{
 if(mode==='tcp53_control'||mode==='tcp53_landlock'){
  const channel=net.connect({host:'192.168.44.1',port:53});attach(channel);
  channel.once('connect',()=>{outcome=mode==='tcp53_control'?'observed_expected':'unknown';close();});
  channel.once('error',(error)=>{
   const denied=mode==='tcp53_landlock'&&['EACCES','EPERM'].includes(error.code);
   outcome=denied?'observed_expected':'unknown';close();
  });
 }else if(mode==='lookup_tls'&&['api.openai.com','auth.openai.com'].includes(host)){
  lookupCalls=1;dns.lookup(host,(error,ip,family)=>{
   if(done)return;if(error||family!==4||ip!==expected){close();return;}
   address=ip;tlsCalls=1;
   const channel=tls.connect({host:ip,port:443,servername:host,
    rejectUnauthorized:true,minVersion:'TLSv1.2'});attach(channel);
   channel.once('secureConnect',()=>{
    version=channel.getProtocol();
    const valid=channel.authorized&&['TLSv1.2','TLSv1.3'].includes(version);
    outcome=valid?'observed_expected':'unknown';close();
   });
   channel.once('error',()=>{outcome='unknown';close();});
  });
 }else{close();}
}catch{outcome='unknown';close();}
"""


def parse_output(raw: bytes) -> dict[str, object]:
    if not raw or len(raw) > 16384 or raw.count(b"\n") > 1:
        raise contract.CaseRejected("node_output_unknown")
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise contract.CaseRejected("node_output_unknown") from None
    if type(value) is not dict:
        raise contract.CaseRejected("node_output_unknown")
    return cast(dict[str, object], value)


def _control() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        raise contract.CaseRejected("node_preexec_unknown")


def run_child(
    argv: list[str],
    *,
    cwd: Path,
    pass_fds: tuple[int, ...],
    preexec: Callable[[], object],
    deadline: float,
    clock: probe.Clock = time.monotonic,
) -> dict[str, object]:
    child = subprocess.Popen(
        argv,
        cwd=cwd,
        env={},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        pass_fds=pass_fds,
        preexec_fn=preexec,
    )
    raw = bytearray()
    try:
        assert child.stdout is not None
        os.set_blocking(child.stdout.fileno(), False)
        with selectors.DefaultSelector() as ready:
            ready.register(child.stdout, selectors.EVENT_READ)
            while True:
                events = ready.select(probe.remaining(deadline, clock))
                if not events:
                    raise contract.CaseRejected("node_timeout_unknown")
                chunk = os.read(child.stdout.fileno(), 16385 - len(raw))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > 16384:
                    raise contract.CaseRejected("node_output_unknown")
        child.wait(timeout=probe.remaining(deadline, clock))
        if child.returncode != 0:
            raise contract.CaseRejected("node_exit_unknown")
        probe.remaining(deadline, clock)
        return parse_output(bytes(raw))
    finally:
        if child.poll() is None:
            child.kill()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                raise contract.CaseRejected("node_reap_unknown") from None
        if child.stdout is not None:
            child.stdout.close()


def run_stage(
    case: contract.Case, root: Path, handle: NodeHandle, sequence: int, deadline: float
) -> dict[str, object]:
    contract.check_nss(root)
    node = handle.node
    install = handle.install
    fds = handle.pass_fds
    if len(fds) != 1:
        raise contract.CaseRejected("node_supply_unknown")
    lock = os.fstat(fds[0])
    tree = case.worker_root / f"node-{sequence}"
    tree.mkdir(mode=0o700)
    boundary = local.load_isolation(root).IsolationBoundary(
        install, Path("/srv/pi-cwd"), tree, None
    )
    host = probe.HOSTS[sequence - 3] if sequence in {3, 4} else ""
    refs = []
    expected = ""
    if sequence in {3, 4}:
        profile = contract.read_metadata(root / "profile.json", owner=0)
        assert isinstance(profile, dict)
        ops = probe.SocketOperations(profile["candidate_probe"]["tls_trust"]["sha256"])
        transports: tuple[Literal["udp"], Literal["tcp"]] = ("udp", "tcp")
        answers = [
            ops.dns(host, transport, min(deadline, time.monotonic() + 5))
            for transport in transports
        ]
        if answers[0].address != answers[1].address or not ops.cleanup_complete:
            raise contract.CaseRejected("node_reference_unknown")
        expected = answers[0].address
        refs = [
            {
                "transport": transport,
                "address": answer.address,
                "ttl": answer.ttl,
                "received_monotonic": answer.received,
            }
            for transport, answer in zip(("udp", "tcp"), answers, strict=True)
        ]
        deadline = min(deadline, min(a.expires for a in answers))
    mode = (
        "tcp53_control"
        if sequence == 1
        else "tcp53_landlock"
        if sequence == 2
        else "lookup_tls"
    )
    started = time.monotonic()
    deadline = min(deadline, started + (10 if sequence in {3, 4} else 5))
    timeout_ms = max(
        1,
        int(
            min(
                probe.remaining(deadline, time.monotonic),
                10 if sequence in {3, 4} else 5,
            )
            * 1000
        ),
    )
    argv = [
        str(node),
        "-e",
        JS,
        mode,
        host,
        expected,
        str(timeout_ms),
        str(fds[0]),
        str(lock.st_dev),
        str(lock.st_ino),
        case.base_plan().cgroup,
    ]
    value = run_child(
        argv,
        cwd=Path("/srv/pi-cwd"),
        pass_fds=fds,
        preexec=_control if sequence == 1 else boundary,
        deadline=deadline,
    )
    ended = time.monotonic()
    contract.check_nss(root)
    contract.validate_node(value, mode=mode, uid=case.uid, address=expected or None)
    result: dict[str, object] = {
        "run_id": case.run_id,
        "sequence": sequence,
        "node": value,
        "child_reaped": True,
        "supply_protection": (
            "diagnostic_readonly_original_instance_lock_not_product_use_install"
        ),
    }
    if refs:
        result.update(
            reference=refs, started_monotonic=started, completed_monotonic=ended
        )
    contract.validate_stage(case, sequence, result)
    return result


def execute(root: Path) -> dict[str, object]:
    import scripts.issue167_node_diag_supply as supply

    loaded, _, _ = contract.verify_installation(root)
    case = cast(contract.Case, loaded)
    info = case.worker_root.lstat()
    if (
        os.getuid() != case.uid
        or os.geteuid() != case.uid
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != case.uid
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise contract.CaseRejected("worker_identity_unknown")
    local.reserve(case.worker_root / "worker-started.json", case.run_id)
    deadline = time.monotonic() + case.worker_timeout_s
    result: dict[str, object] = {
        "run_id": case.run_id,
        "scope": "fixed_node_no_secret_diagnostic",
        "result": "unknown",
        "pi_execs": 0,
        "auth_calls": 0,
        "model_calls": 0,
        "limits": dict(contract.LIMITS),
    }
    try:
        binding = supply.load_binding(root / "node-binding.json")
        with supply.supply_use(binding) as handle:
            ready = local.own_metadata(case)
            local.publish(case.worker_root / "ready.json", ready)
            rows = []
            for sequence in (1, 2, 3, 4):
                local.wait_gate(
                    case.runtime_root / f"gate-{sequence}.json",
                    case.run_id,
                    sequence,
                    deadline,
                )
                row = run_stage(case, root, handle, sequence, deadline)
                rows.append(row)
                local.publish(case.worker_root / f"stage-{sequence}.json", row)
            result = {**ready, **result, "result": "observed_expected", "stages": rows}
            contract.validate_result(case, result)
            local.publish(case.worker_root / "worker-result.json", result)
            local.wait_gate(case.runtime_root / "gate-5.json", case.run_id, 5, deadline)
            return result
    except (Exception, KeyboardInterrupt):
        result.update(result="unknown", failure_reason="node_diagnostic_unknown")
    local.publish(case.worker_root / "worker-result.json", result)
    return result


def main() -> int:
    return (
        0
        if execute(Path(__file__).absolute().parent)["result"] == "observed_expected"
        else 1
    )
