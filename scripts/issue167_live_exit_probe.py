"""Independent no-network supervisor seam prototype; import is inert.

The only reused live actions are the unmodified phase_gate and wait_exit
methods. Installation/restoration here is a separate, credential-free scope.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import resource
import signal
import stat
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from scripts import issue167_h1_guardian as guard
from scripts import issue167_h1_phase as phase
from scripts import issue167_live_owner as live
from scripts import issue167_resolver_case as metadata
from scripts import issue167_resolver_owner as base

RUN = "d5f2a9017c84"
SCOPE = "independent_synthetic_supervisor_exit_only"
MODULE_ORDER = (
    "issue167_dns_tls",
    "issue167_resolver_case",
    "issue167_service_network_case",
    "issue167_live_case",
    "issue167_resolver_owner",
    "issue167_service_network_owner",
    "issue167_live_owner",
    "issue167_h1_phase",
    "issue167_h1_guardian",
    "issue167_live_exit_probe",
)
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()


class ProbeRejected(ValueError):
    """Closed metadata reason."""


def validate_worker(value: object, run_id: str, phase: str) -> dict[str, Any]:
    expected = {
        "run_id": run_id,
        "phase": phase,
        "count": 1,
        "core_zero": True,
        "no_new_privs": True,
        "caps_zero": True,
    }
    if (
        type(value) is not dict
        or set(value) != {*expected, "pid"}
        or not base.metadata_equal({k: value.get(k) for k in expected}, expected)
        or type(value.get("pid")) is not int
        or not 1 < value["pid"] <= 2**31 - 1
    ):
        raise ProbeRejected("worker_metadata_unknown")
    return cast(dict[str, Any], value)


@dataclass(frozen=True)
class Case:
    run_id: str = RUN

    def __post_init__(self) -> None:
        if self.run_id != RUN:
            raise ProbeRejected("fixed_run_unknown")

    @property
    def plan(self) -> phase.Plan:
        return phase.Plan(self.run_id, 1000, 1000, network_mode="ipv4_only")

    @property
    def unit(self) -> str:
        return self.plan.unit

    @property
    def uid(self) -> int:
        return 1000

    @property
    def runtime_root(self) -> Path:
        return Path("/run/paperradar-issue167-" + self.run_id)

    @property
    def worker_root(self) -> Path:
        return self.runtime_root / "worker"

    @property
    def code_root(self) -> Path:
        return Path("/home/paperradar-probes/issue167-" + self.run_id)

    @property
    def unit_path(self) -> Path:
        return Path("/etc/systemd/system") / self.unit

    @property
    def ledger(self) -> Path:
        return Path("/var/lib/paperradar/probe-runs") / (
            "issue167-" + self.run_id + ".json"
        )


def read_file(path: Path, *, uid: int = 0, limit: int = 1048576) -> bytes:
    fd = os.open(path, FILE_FLAGS)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != uid
            or info.st_gid != uid
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > limit
        ):
            raise ProbeRejected("file_metadata_unknown")
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        if len(raw) > limit or (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ProbeRejected("file_changed")
        return raw
    finally:
        os.close(fd)


def write_new(path: Path, raw: bytes, mode: int = 0o644) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as output:
            output.write(raw)
            output.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def render_unit(case: Case, python: str) -> str:
    return f"""[Unit]
Description=PaperRadar 167 independent synthetic supervisor exit
[Service]
Type=exec
RemainAfterExit=yes
User=1000
Group=1000
ExecStart={python} -I -S -B {case.code_root}/worker.py
WorkingDirectory={case.worker_root}
Environment=PATH=/usr/bin:/bin
Environment=PYTHONNOUSERSITE=1
UMask=0077
Restart=no
KillMode=control-group
TimeoutStartSec=10
TimeoutStopSec=8
RuntimeMaxSec=60
LimitCORE=0
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=none
IPAddressDeny=any
SocketBindDeny=any
SystemCallFilter=~@network-io
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={case.worker_root}
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ProtectClock=yes
RestrictSUIDSGID=yes
LockPersonality=yes
StandardInput=null
StandardOutput=null
StandardError=null
"""


def worker_source(case: Case) -> bytes:
    # This is public synthetic code only; no socket import or content reader.
    return f'''"""One synthetic worker; no credential/application/network access."""
import json,os,resource,stat,time
from pathlib import Path
root=Path({str(case.runtime_root)!r})
run={case.run_id!r}
def publish(name,value):
    tmp=root/'worker'/('.tmp-'+name)
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(value,f,sort_keys=True);f.write('\\n');f.flush();os.fsync(f.fileno())
    os.link(tmp,root/'worker'/name,follow_symlinks=False);tmp.unlink()
    fd=os.open(root/'worker',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
def main():
    if os.getuid()!=1000 or os.getgid()!=1000:raise ValueError()
    core=resource.getrlimit(resource.RLIMIT_CORE)==(0,0)
    with Path('/proc/self/status').open('rb') as f:raw=f.read(16385)
    if len(raw)>16384:raise ValueError()
    selected={{}}
    for line in raw.decode('ascii').splitlines():
        key,_,value=line.partition(':')
        if key in {{'NoNewPrivs','CapEff','CapPrm','CapInh','CapBnd','CapAmb'}}:
            if key in selected:raise ValueError()
            selected[key]=value.strip()
    nnp=selected.get('NoNewPrivs')=='1'
    keys={{'NoNewPrivs','CapEff','CapPrm','CapInh','CapBnd','CapAmb'}}
    caps=set(selected)==keys and all(
        int(selected[k],16)==0 for k in selected if k!='NoNewPrivs')
    if not(core and nnp and caps):raise ValueError()
    base={{'run_id':run,'count':1,'pid':os.getpid(),'core_zero':core,'no_new_privs':nnp,'caps_zero':caps}}
    publish('ready.json',dict(base,phase='ready'))
    publish('terminal.json',dict(base,phase='terminal'))
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        try:
            fd=os.open(root/'gate-exit.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        except FileNotFoundError:
            time.sleep(.05);continue
        with os.fdopen(fd,'rb') as f:
            s=os.fstat(f.fileno())
            if s.st_nlink==2:
                time.sleep(.05);continue
            if (not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_gid!=0
                or s.st_nlink!=1 or stat.S_IMODE(s.st_mode)!=0o644
                or s.st_size>4096):raise ValueError()
            raw=f.read(4097)
        pairs=[]
        def exact(items):
            result={{}}
            for key,value in items:
                if key in result:raise ValueError()
                result[key]=value
            return result
        value=json.loads(raw,object_pairs_hook=exact)
        if (set(value)!={{'run_id','sequence'}} or value['run_id']!=run
            or type(value['sequence']) is not int or value['sequence']!=7):
            raise ValueError()
        return 0
    return 1
try:status=main()
except BaseException:status=1
raise SystemExit(status)
'''.encode()


class Seam(live.LiveOperations):
    """Uses original methods; only the no-nft verification adapter is different."""

    def __init__(self, operations: HostOperations) -> None:
        self.host = operations
        self.case = cast(Any, operations.case)
        self.plan = operations.plan
        self.commands = operations.commands
        self.phase = phase
        self.contract = metadata
        self.ready_metadata = None
        self.exit_metadata = live.new_exit_metadata()
        self.deadline = time.monotonic() + 60

    def _verify(self, stage: str | None = None) -> tuple[int, int]:
        self.host.verify_scope()
        return (0, 0)  # No packet observation/claim exists in this scope.

    def _systemctl(self, *args: str) -> bytes:
        if args != (
            "show",
            self.case.unit,
            "--property=ActiveState,SubState,Result,ExecMainCode,ExecMainStatus,MainPID,ControlGroup",
            "--no-pager",
        ):
            raise ProbeRejected("command_scope_unknown")
        return cast(bytes, self.host.systemctl(*args))


class Operations(Protocol):
    seam: Any

    def preflight(self) -> None: ...
    def reserve(self) -> None: ...
    def install(self) -> None: ...
    def start(self) -> None: ...
    def checkpoint(self, name: str) -> dict[str, object]: ...
    def restore(self) -> dict[str, object]: ...
    def remove_artifacts(self) -> dict[str, object]: ...
    def write_ledger(self, value: object) -> None: ...


def cleanup_failure_reason(error: BaseException) -> str:
    """Closed projection; never expose arbitrary exception text or paths."""
    if isinstance(error, KeyboardInterrupt):
        return "cleanup_interrupted"
    if isinstance(error, SystemExit):
        return "cleanup_system_exit"
    if isinstance(error, OSError):
        return "cleanup_os_error"
    if (
        type(error) is ProbeRejected
        and len(error.args) == 1
        and type(error.args[0]) is str
        and error.args[0]
        in {
            "artifact_cleanup_unknown",
            "artifact_mount_unknown",
            "cgroup_not_empty",
            "cleanup_boundary_unknown",
            "cleanup_member_changed",
            "cleanup_member_unknown",
            "cleanup_root_changed",
            "mount_metadata_unknown",
            "reset_unknown",
            "restoration_unknown",
            "stop_unknown",
            "unit_metadata_unknown",
            "unit_not_absent",
            "unit_scope_unknown",
        }
    ):
        return error.args[0]
    return "cleanup_operation_unknown"


def run_probe(ops: Operations) -> dict[str, object]:
    cleanup: dict[str, object] = {
        "unit_restoration": "not_started",
        "artifacts": "not_started",
        "failure_stage": None,
        "failure_reason": None,
    }
    result: dict[str, object] = {
        "scope": SCOPE,
        "run_id": RUN,
        "result": "unknown",
        "synthetic_worker_starts_upper": 1,
        "auth_model_calls": 0,
        "network_operations": 0,
        "database_operations": 0,
        "nft_operations": 0,
        "old_result_changed": False,
        "exit_diagnostics": None,
        "restoration": None,
        "artifacts": None,
        "cleanup_diagnostics": cleanup,
    }
    reserved = installed = passed = False
    stage = "preflight"
    try:
        ops.preflight()
        stage = "reserve"
        ops.reserve()
        reserved = True
        stage = "install"
        installed = True
        ops.install()
        stage = "start"
        ops.start()
        for name in ("ready", "terminal"):
            stage = name
            result[name] = ops.checkpoint(name)
        stage = "exit_gate"
        ops.seam.phase_gate("exit", 7)
        stage = "exit_wait"
        ops.seam.wait_exit()
        passed = True
    except BaseException as error:
        result.update(failure_stage=stage, failure_reason=live._failure_reason(error))
    finally:
        try:
            diagnostic = dict(ops.seam.exit_metadata)
            if (
                stage in {"exit_gate", "exit_wait"}
                and diagnostic.get("failure_reason") is None
            ):
                diagnostic["failure_reason"] = result.get("failure_reason")
            result["exit_diagnostics"] = diagnostic
        except BaseException:
            passed = False
            result["diagnostic_error"] = "exit_metadata_unknown"
        if installed:
            cleanup_stage = "unit_restoration"
            cleanup["unit_restoration"] = "checking"
            try:
                with base.cleanup_signals():
                    restored = ops.restore()
                    if not base.metadata_equal(
                        restored, {"unit_absent": True, "cgroup_empty": True}
                    ):
                        raise ProbeRejected("restoration_unknown")
                    result["restoration"] = restored
                    cleanup["unit_restoration"] = "complete"
                    cleanup_stage = "artifacts"
                    cleanup["artifacts"] = "checking"
                    result["artifacts"] = ops.remove_artifacts()
                    if not base.metadata_equal(
                        result["artifacts"],
                        {"code_runtime_removed": True, "ledger_retained": True},
                    ):
                        raise ProbeRejected("artifact_cleanup_unknown")
                    cleanup["artifacts"] = "complete"
                    cleanup_stage = "signal_scope"
            except BaseException as error:
                passed = False
                # Retain the old aggregate field for existing receipt readers.
                # The new projection distinguishes unit restoration from files.
                result["restoration_error"] = "restoration_unknown"
                reason = cleanup_failure_reason(error)
                cleanup.update(failure_stage=cleanup_stage, failure_reason=reason)
                if cleanup_stage == "unit_restoration":
                    cleanup["unit_restoration"] = "unknown"
                elif cleanup_stage == "artifacts":
                    cleanup["artifacts"] = "unknown"
                    result["artifact_error"] = reason
        if passed:
            result["result"] = "observed_expected_and_restored"
        if reserved:
            try:
                ops.write_ledger(result)
            except BaseException:
                result.update(result="unknown", ledger_error="permanent_result_unknown")
    return result


class HostOperations:
    def __init__(self, config: dict[str, Any], files: Mapping[str, bytes]) -> None:
        self.config = config
        self.files = files
        self.case = Case()
        self.plan = self.case.plan
        self.commands = guard.Commands(
            self.plan, {k: Path(v["path"]) for k, v in config["tools"].items()}
        )
        self.seam = Seam(self)
        self.anchor: Any = None
        self.created: dict[Path, tuple[int, int]] = {}
        self.unit_created = False
        self.started = False

    def systemctl(self, *args: str) -> bytes:
        return self.commands._run((str(self.commands.tools["systemctl"]), *args))

    def manager(self) -> dict[str, str]:
        raw = self.systemctl(
            "show",
            self.case.unit,
            "--property=Id,LoadState,ActiveState,SubState,MainPID,ControlGroup,FragmentPath,DropInPaths,User,Group",
            "--no-pager",
        )
        try:
            rows = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
            state = dict(rows)
            if (
                len(rows) != len(state)
                or set(state)
                != {
                    "Id",
                    "LoadState",
                    "ActiveState",
                    "SubState",
                    "MainPID",
                    "ControlGroup",
                    "FragmentPath",
                    "DropInPaths",
                    "User",
                    "Group",
                }
                or state["Id"] != self.case.unit
            ):
                raise ValueError
        except (ValueError, UnicodeError):
            raise ProbeRejected("unit_metadata_unknown") from None
        return state

    def check_unit(self, *, absent: bool = False) -> dict[str, str]:
        for path in (
            Path("/run/systemd/system") / self.case.unit,
            Path(str(self.case.unit_path) + ".d"),
            Path("/run/systemd/system") / (self.case.unit + ".d"),
        ):
            if os.path.lexists(path):
                raise ProbeRejected("unit_scope_unknown")
        state = self.manager()
        if absent:
            if os.path.lexists(self.case.unit_path) or state != {
                "Id": self.case.unit,
                "LoadState": "not-found",
                "ActiveState": "inactive",
                "SubState": "dead",
                "MainPID": "0",
                "ControlGroup": "",
                "FragmentPath": "",
                "DropInPaths": "",
                "User": "",
                "Group": "",
            }:
                raise ProbeRejected("unit_not_absent")
        else:
            guard.protected_path(self.case.unit_path)
            if (
                read_file(self.case.unit_path) != self.files["probe.service"]
                or any(
                    state[key] != expected
                    for key, expected in {
                        "LoadState": "loaded",
                        "FragmentPath": str(self.case.unit_path),
                        "DropInPaths": "",
                        "User": "1000",
                        "Group": "1000",
                    }.items()
                )
                or state["ControlGroup"] not in {"", self.plan.cgroup}
            ):
                raise ProbeRejected("unit_scope_unknown")
        return state

    def preflight(self) -> None:
        if os.geteuid() != 0 or self.config["run_id"] != RUN:
            raise ProbeRejected("owner_identity_unknown")
        if self.config["host"] != metadata.current_host_context():
            raise ProbeRejected("host_binding_unknown")
        if set(self.files) != set(self.config["members"]):
            raise ProbeRejected("member_scope_unknown")
        for name, raw in self.files.items():
            if (
                Path(name).name != name
                or name in {".", ".."}
                or digest(raw) != self.config["members"][name]
            ):
                raise ProbeRejected("member_changed")
        if self.files["probe.service"].decode() != render_unit(
            self.case, self.config["tools"]["python"]["path"]
        ):
            raise ProbeRejected("unit_bytes_unknown")
        for tool in self.config["tools"].values():
            path = Path(tool["path"])
            guard.protected_path(path)
            if digest(read_file(path, limit=33554432)) != tool["sha256"]:
                raise ProbeRejected("tool_changed")
        if (
            str(Path(sys.executable).resolve())
            != self.config["tools"]["python"]["path"]
        ):
            raise ProbeRejected("interpreter_changed")
        for path in (self.case.code_root, self.case.runtime_root, self.case.ledger):
            if os.path.lexists(path):
                raise ProbeRejected("already_consumed_or_present")
        self.check_unit(absent=True)
        if phase.read_cgroup_state(self.plan, allow_absent=True).exists:
            raise ProbeRejected("cgroup_present")

    def reserve(self) -> None:
        for path in (self.case.ledger.parent.parent, self.case.ledger.parent):
            if not os.path.lexists(path):
                path.mkdir(mode=0o755)
            guard.protected_path(path, directory=True)
        self.anchor = guard.claim_anchor(self.case.ledger, RUN)

    def install(self) -> None:
        parent = self.case.code_root.parent
        if not os.path.lexists(parent):
            parent.mkdir(mode=0o755)
        guard.protected_path(parent, directory=True)
        for path in (self.case.code_root, self.case.runtime_root):
            guard.protected_path(path.parent, directory=True)
            path.mkdir(mode=0o755)
            path.chmod(0o755)
            info = path.lstat()
            self.created[path] = (info.st_dev, info.st_ino)
        self.case.worker_root.mkdir(mode=0o700)
        os.chown(self.case.worker_root, 1000, 1000)
        for name, raw in self.files.items():
            write_new(self.case.code_root / name, raw)
        guard.protected_path(self.case.unit_path.parent, directory=True)
        write_new(self.case.unit_path, self.files["probe.service"])
        self.unit_created = True
        self.systemctl("daemon-reload")

    def verify_scope(self) -> None:
        self.check_unit()
        for root, expected in self.created.items():
            guard.protected_path(root, directory=True)
            info = root.lstat()
            if (info.st_dev, info.st_ino) != expected:
                raise ProbeRejected("root_identity_unknown")
        if set(os.listdir(self.case.code_root)) != set(self.files):
            raise ProbeRejected("code_members_unknown")
        for name, expected in self.config["members"].items():
            if digest(read_file(self.case.code_root / name)) != expected:
                raise ProbeRejected("code_changed")
        worker = self.case.worker_root.lstat()
        if (
            not stat.S_ISDIR(worker.st_mode)
            or worker.st_uid != 1000
            or worker.st_gid != 1000
            or stat.S_IMODE(worker.st_mode) != 0o700
        ):
            raise ProbeRejected("worker_root_unknown")

    def start(self) -> None:
        if self.started:
            raise ProbeRejected("restart_forbidden")
        self.started = True
        self.systemctl("start", self.case.unit)
        self.seam.deadline = time.monotonic() + 60

    def checkpoint(self, name: str) -> dict[str, object]:
        if name not in {"ready", "terminal"}:
            raise ProbeRejected("worker_metadata_unknown")
        self.verify_scope()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                value = validate_worker(
                    metadata.read_metadata(
                        self.case.worker_root / (name + ".json"), owner=1000, limit=4096
                    ),
                    RUN,
                    name,
                )
                break
            except FileNotFoundError:
                time.sleep(0.05)
        else:
            raise ProbeRejected("worker_deadline_unknown")
        self.verify_scope()
        state = self.commands.unit_state()
        if value["pid"] != state.pid or phase.read_cgroup_state(self.plan).pids != {
            state.pid
        }:
            raise ProbeRejected("worker_identity_unknown")
        if name == "ready":
            self.seam.ready_metadata = {"pid": state.pid}
        elif self.seam.ready_metadata != {"pid": state.pid}:
            raise ProbeRejected("worker_identity_unknown")
        return {
            "count": 1,
            "integrity": "complete",
            "core_zero": True,
            "no_new_privs": True,
            "caps_zero": True,
        }

    def restore(self) -> dict[str, object]:
        if self.unit_created:
            self.check_unit()
            self.systemctl("stop", "--no-block", self.case.unit)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                state = self.check_unit()
                empty = not phase.read_cgroup_state(self.plan, allow_absent=True).pids
                if (
                    empty
                    and state["MainPID"] == "0"
                    and (state["ActiveState"], state["SubState"])
                    in {("inactive", "dead"), ("failed", "failed")}
                ):
                    break
                time.sleep(0.05)
            else:
                raise ProbeRejected("stop_unknown")
            if state["ActiveState"] == "failed":
                self.systemctl("reset-failed", self.case.unit)
                state = self.check_unit()
                if (state["ActiveState"], state["SubState"], state["MainPID"]) != (
                    "inactive",
                    "dead",
                    "0",
                ):
                    raise ProbeRejected("reset_unknown")
            self.check_unit()
            self.case.unit_path.unlink()
            self.systemctl("daemon-reload")
        self.check_unit(absent=True)
        if phase.read_cgroup_state(self.plan, allow_absent=True).pids:
            raise ProbeRejected("cgroup_not_empty")
        return {"unit_absent": True, "cgroup_empty": True}

    def remove_artifacts(self) -> dict[str, object]:
        self.check_unit(absent=True)
        for root, expected in self.created.items():
            info = root.lstat()
            if (info.st_dev, info.st_ino) != expected:
                raise ProbeRejected("cleanup_root_changed")
        remove_flat_tree(
            self.case.runtime_root,
            {
                "worker": (1000, True),
                "gate-exit.json": (0, False),
                **{
                    f"worker/{name}": (1000, False)
                    for name in (
                        "ready.json",
                        "terminal.json",
                        ".tmp-ready.json",
                        ".tmp-terminal.json",
                    )
                },
            },
            self.created.get(self.case.runtime_root),
        )
        remove_flat_tree(
            self.case.code_root,
            {name: (0, False) for name in self.files},
            self.created.get(self.case.code_root),
        )
        return {"code_runtime_removed": True, "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        if self.anchor is None:
            raise ProbeRejected("ledger_missing")
        info = os.fstat(self.anchor.fileno())
        linked = self.case.ledger.lstat()
        if (
            (info.st_dev, info.st_ino) != (linked.st_dev, linked.st_ino)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ProbeRejected("ledger_changed")
        self.anchor.seek(0)
        self.anchor.truncate()
        self.anchor.write(encoded(value).decode())
        self.anchor.flush()
        os.fsync(self.anchor.fileno())


def mount_path(value: str) -> Path:
    """Decode only kernel mountinfo escapes, once, for an absolute path."""
    escapes = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}
    if re.search(r"\\(?!040|011|012|134)", value) or "\x00" in value:
        raise ValueError
    decoded = re.sub(r"\\(040|011|012|134)", lambda m: escapes[m[1]], value)
    if (
        not decoded.startswith("/")
        or decoded.startswith("//")
        or any(part in {".", ".."} for part in decoded.split("/"))
    ):
        raise ValueError
    return Path(decoded)


def mount_points(raw: bytes) -> set[Path]:
    if not raw or len(raw) > 1048576:
        raise ProbeRejected("mount_metadata_unknown")
    points = set()
    try:
        for line in raw.decode("utf-8").splitlines():
            fields = line.split()
            if (
                len(fields) < 10
                or fields.count("-") != 1
                or re.fullmatch(r"[0-9]+", fields[0]) is None
                or re.fullmatch(r"[0-9]+", fields[1]) is None
                or re.fullmatch(r"[0-9]+:[0-9]+", fields[2]) is None
            ):
                raise ValueError
            separator = fields.index("-")
            if separator < 6 or len(fields) != separator + 4:
                raise ValueError
            root = fields[3]
            if root.startswith("/"):
                mount_path(root)
            elif not (
                fields[separator + 1] == "nsfs"
                and re.fullmatch(r"mnt:\[[1-9][0-9]*\]", root) is not None
            ):
                # This probe supports only the non-path form observed locally.
                # A namespace root is descriptive; field five remains the target.
                raise ValueError
            points.add(mount_path(fields[4]))
    except (ValueError, UnicodeError):
        raise ProbeRejected("mount_metadata_unknown") from None
    if not points:
        raise ProbeRejected("mount_metadata_unknown")
    return points


def remove_flat_tree(
    root: Path,
    allowed: dict[str, tuple[int, bool]],
    expected: tuple[int, int] | None,
    *,
    root_uid: int = 0,
) -> None:
    if not os.path.lexists(root) and expected is None:
        return
    fd = os.open(root, DIR_FLAGS)
    fds = {"": fd}
    seen: dict[str, os.stat_result] = {}
    try:
        top = os.fstat(fd)
        if (
            expected is None
            or (top.st_dev, top.st_ino) != expected
            or top.st_uid != root_uid
            or top.st_gid != root_uid
            or stat.S_IMODE(top.st_mode) != 0o755
        ):
            raise ProbeRejected("cleanup_root_changed")
        with Path("/proc/self/mountinfo").open("rb") as source:
            points = mount_points(source.read(1048577))
        if any(point.is_relative_to(root) for point in points):
            raise ProbeRejected("artifact_mount_unknown")
        for parent in ("", "worker"):
            if parent not in fds:
                continue
            for name in os.listdir(fds[parent]):
                relative = parent + "/" + name if parent else name
                if relative not in allowed:
                    raise ProbeRejected("cleanup_member_unknown")
                uid, directory = allowed[relative]
                info = os.stat(name, dir_fd=fds[parent], follow_symlinks=False)
                if (
                    info.st_dev != top.st_dev
                    or info.st_uid != uid
                    or info.st_gid != uid
                    or info.st_mode & 0o022
                    or stat.S_IMODE(info.st_mode) & 0o7000
                    or not (
                        stat.S_ISDIR(info.st_mode)
                        if directory
                        else stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    )
                ):
                    raise ProbeRejected("cleanup_boundary_unknown")
                seen[relative] = info
                if directory:
                    nested = os.open(name, DIR_FLAGS, dir_fd=fds[parent])
                    fds[relative] = nested
                    if (os.fstat(nested).st_dev, os.fstat(nested).st_ino) != (
                        info.st_dev,
                        info.st_ino,
                    ):
                        raise ProbeRejected("cleanup_member_changed")
        for relative, before in seen.items():
            parent, _, name = relative.rpartition("/")
            after = os.stat(name, dir_fd=fds[parent], follow_symlinks=False)
            if (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_uid,
                before.st_gid,
                before.st_nlink,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_uid,
                after.st_gid,
                after.st_nlink,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ProbeRejected("cleanup_member_changed")
        for relative in sorted(seen, key=lambda value: (-value.count("/"), value)):
            parent, _, name = relative.rpartition("/")
            before = seen[relative]
            after = os.stat(name, dir_fd=fds[parent], follow_symlinks=False)
            if (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_uid,
                before.st_gid,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_uid,
                after.st_gid,
            ):
                raise ProbeRejected("cleanup_member_changed")
            if stat.S_ISDIR(before.st_mode):
                os.rmdir(name, dir_fd=fds[parent])
            else:
                os.unlink(name, dir_fd=fds[parent])
        after = root.lstat()
        if (after.st_dev, after.st_ino) != expected:
            raise ProbeRejected("cleanup_root_changed")
        root.rmdir()
    finally:
        for descriptor in fds.values():
            os.close(descriptor)


def root_main(config: dict[str, Any], files: Mapping[str, bytes]) -> int:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(
            sig, lambda _sig, _frame: (_ for _ in ()).throw(KeyboardInterrupt())
        )
    ops = HostOperations(config, files)
    result = run_probe(ops)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "observed_expected_and_restored" else 1


def render_driver(
    config: dict[str, Any], files: Mapping[str, bytes], manifest_sha: str
) -> str:
    payload = encoded(
        {
            "config": config,
            "files": {
                name: base64.b64encode(raw).decode() for name, raw in files.items()
            },
        }
    )
    payload64 = base64.b64encode(payload).decode()
    return f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -ne 0 ]]; then
  printf '%s\\n' '固定监督验证入口不接受参数。' >&2
  exit 2
fi
owner_dir=$(cd -- "$(dirname -- "${{BASH_SOURCE[0]}}")" && pwd -P)
printf '%s\\n' '[H1 合成监督收尾] 单次worker；无认证/模型/网络/数据库；原unknown不变。'
/usr/bin/python3 -I -S -B - "$owner_dir" <<'LOCAL_CHECK'
import hashlib,json,os,stat,sys
from pathlib import Path
r=Path(sys.argv[1]); expected={manifest_sha!r}
def read(name):
    fd=os.open(r/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        s=os.fstat(f.fileno())
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=1000 or s.st_gid!=1000
            or s.st_nlink!=1 or s.st_mode&0o022 or s.st_size>2097152):
            raise SystemExit('local_metadata_unknown')
        raw=f.read(2097153)
        if len(raw)>2097152:raise SystemExit('local_size_unknown')
        return raw
if os.getuid()!=1000 or os.getgid()!=1000:raise SystemExit('owner_identity_unknown')
for d in (r,r/'results'):
    s=d.lstat()
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=1000 or s.st_gid!=1000
        or stat.S_IMODE(s.st_mode)!=0o700):
        raise SystemExit('local_directory_unknown')
raw=read('manifest.json')
if hashlib.sha256(raw).hexdigest()!=expected:raise SystemExit('manifest_changed')
m=json.loads(raw);seal=json.loads(read('review-seal.json'))
expected_seal={{'scope':{SCOPE!r},'run_id':{RUN!r},
    'manifest_sha256':expected,
    'driver_sha256':hashlib.sha256(read('owner-run.sh')).hexdigest()}}
if seal!=expected_seal:raise SystemExit('review_seal_changed')
for name,want in m['members'].items():
    if (Path(name).name!=name or name in {{'.','..'}}
        or hashlib.sha256(read(name)).hexdigest()!=want):
        raise SystemExit('member_changed')
if os.path.lexists(r/'results/owner-run.json'):
    raise SystemExit('result_already_present')
fd=os.open(r/'results/execution-started.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:
    json.dump({{'scope':{SCOPE!r},'run_id':{RUN!r},'state':'reserved_unknown','manifest_sha256':expected}},f,sort_keys=True)
    f.write('\\n');f.flush();os.fsync(f.fileno())
LOCAL_CHECK
owner_output=$(mktemp "$owner_dir/results/.owner-output-XXXXXX")
owner_status=0
printf '%s\\n' '[H1] 只在sudo终端提示输入密码；脚本负责安装、单次启动、核验和恢复。'
if /usr/bin/sudo /usr/bin/python3 -I -S -B - <<'ROOT_LITERAL' > "$owner_output"
import base64,hashlib,json,sys,types
try:
    payload=base64.b64decode({payload64!r},validate=True)
    if hashlib.sha256(payload).hexdigest()!={digest(payload)!r}:raise ValueError()
    decoded=json.loads(payload);config=decoded['config']
    files={{name:base64.b64decode(value,validate=True)
        for name,value in decoded['files'].items()}}
    if set(files)!=set(config['members']):raise ValueError()
    for name,raw in files.items():
        if hashlib.sha256(raw).hexdigest()!=config['members'][name]:raise ValueError()
    package=types.ModuleType('scripts');package.__path__=[];sys.modules['scripts']=package
    for short in {MODULE_ORDER!r}:
        name='scripts.'+short;module=types.ModuleType(name);module.__file__='<sealed:'+short+'>';module.__package__='scripts'
        sys.modules[name]=module;setattr(package,short,module)
        exec(compile(files[short+'.py'],module.__file__,'exec'),module.__dict__)
    status=sys.modules['scripts.issue167_live_exit_probe'].root_main(config,files)
except BaseException:
    print(json.dumps({{'scope':{SCOPE!r},'run_id':{RUN!r},'result':'unknown','failure_reason':'owner_bootstrap_unknown','auth_model_calls':0,'network_operations':0,'old_result_changed':False}},sort_keys=True))
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
    if len(raw)>16384:raise ValueError()
    value=json.loads(raw)
    if (value['scope']!={SCOPE!r} or value['run_id']!={RUN!r}
        or value['auth_model_calls']!=0 or value['network_operations']!=0
        or value['old_result_changed'] is not False
        or (status==0 and value['result']!='observed_expected_and_restored')
        or (status!=0 and value['result']!='unknown')):raise ValueError()
except BaseException:
    value={{'scope':{SCOPE!r},'run_id':{RUN!r},'result':'unknown','failure_reason':'owner_output_unknown','auth_model_calls':0,'network_operations':0,'old_result_changed':False}}
value['owner_exit_status']=status
fd=os.open(r/'results/owner-run.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:
    json.dump(value,f,sort_keys=True);f.write('\\n');f.flush();os.fsync(f.fileno())
output.unlink()
print('监督验证结果：'+value['result']+'；旧批次仍unknown；回执已保存。')
if value['result']!='observed_expected_and_restored':raise SystemExit(1)
LOCAL_RECEIPT
exit "$owner_status"
"""


def build_package(destination: Path, workspace: Path) -> dict[str, str]:
    case = Case()
    tools = {}
    for name, literal in {
        "python": "/usr/bin/python3",
        "systemctl": "/usr/bin/systemctl",
        "systemd_analyze": "/usr/bin/systemd-analyze",
    }.items():
        path = Path(literal).resolve(strict=True)
        guard.protected_path(path)
        tools[name] = {
            "path": str(path),
            "sha256": digest(read_file(path, limit=33554432)),
        }
    files = {
        name + ".py": (workspace / "scripts" / (name + ".py")).read_bytes()
        for name in MODULE_ORDER
    }
    files["worker.py"] = worker_source(case)
    files["probe.service"] = render_unit(case, tools["python"]["path"]).encode()
    config = {
        "scope": SCOPE,
        "run_id": RUN,
        "host": metadata.current_host_context(),
        "tools": tools,
        "members": {name: digest(raw) for name, raw in files.items()},
        "limits": {
            "synthetic_worker_starts": 1,
            "exit_gate_publications": 1,
            "auth_model_calls": 0,
            "network_operations": 0,
            "database_operations": 0,
            "nft_operations": 0,
            "worker_timeout_s": 40,
            "service_runtime_max_s": 60,
            "seam_deadline_s": 60,
        },
    }
    review = f"""# #167 独立无秘密监督收尾：待新H1，尚未执行

本包只取得当前监督接缝的未来现场结论，不补写旧e93批次；旧unknown、消耗和认证目录保持。

## 所有者将执行的动作

1. 核对本包完整成员/工具与本机绑定，确认专用unit、代码/runtime、永久ledger均缺失。
2. 原子预占永久 `{case.ledger}`
   （root:root 0600，不退款、不重试）；新增代码 `{case.code_root}`
   与控制目录 `{case.runtime_root}`（root:root 0755），
   其worker子目录uid/gid1000 0700。
3. 仅安装 `{case.unit_path}`；daemon-reload后只start一次
   `{case.unit}`。UID1000标准库合成worker检查自身core hard/soft0、
   NoNewPrivileges和五个cap集合为0，只输出ready/terminal受控metadata，
   不读凭据、日志或其它进程环境。
4. root只驱动当前issue167_live_owner.LiveOperations的原phase_gate('exit',7)
   与wait_exit，原resolver_owner._write、guardian.Commands.unit_state、
   phase.read_cgroup_state均复用。新适配_verify只核本scope代码/unit/CG，
   不调用nft，不冒充原全链规则验证。unit保持Type=exec和RemainAfterExit=yes，
   成功仍须原严格active/exited/success/ExecMainCode1/Status0/MainPID0和CG空，
   不用卸载后的默认Result自证。
5. 成败均尝试精确验证本unit后stop --no-block，等待CG空及停态；
   仅本unit若failed才reset-failed，复核后unlink本unit、daemon-reload并确认缺失；
   只删除本次精确的代码/runtime两树，永久ledger留存。陌生成员、身份变化、
   挂载/alias或恢复未知即停止，保留unknown/必要材料，不重跑；
   部分删除失败仍可留下部分树。
   部分安装（例如unit发布后fsync失败）可能保留这个具名单元和code/runtime；
   归属核验不全时不自动删除，须后续所有者仅恢复，不获得重验预算。

## 范围和预算

单次synthetic worker1、exit gate7一次；worker等待40秒、service运行最多60秒、
接缝60秒，manager命令各8秒，清理另有15秒停态窗口。
无Node/Pi、认证、刷新、模型、DB、真实锁、socket探针、DNS/TLS/连接/发送、
nft或resolver操作，无安装树写入、崩溃或宿主全机策略改动。
服务限制socket syscalls/地址族、IP及bind；本轮不探测网络，
不把配置等同网络现场通过。

root通过单次sudo的封印字面stdin执行，完整10个stdlib脚本模块先核SHA后
预载于空scripts package；不从可写工作区import应用，
未纳入旧40成员或2284 runtime闭包。代码目录12个普通文件
（10模块、worker、unit副本），另有实际unit；runtime仅固定worker控制文件
和root exit gate。原凭据/业务目录完全不访问。输出只保留受控状态/类别/次数/完整性，
不保存任意stderr、异常原文或真实PID/CG路径。

## 审阅后入口

`bash {destination}/owner-run.sh`。
仅在sudo终端提示输入一次密码；脚本负责全部命令及核验，不读取/保存密码。
参数不接受、任何已预占或结果均拒绝，授权或密码失败也不自动重试。
先看manifest.json、scope.json、全部源码与unit、owner-run.sh，
再核review-seal.json。新D1独立，不进历史分母/required/正式回执。
本包/绑定/回执只留本地。
"""
    destination.mkdir(mode=0o700)
    (destination / "results").mkdir(mode=0o700)
    artifacts = {**files, "scope.json": encoded(config), "review.md": review.encode()}
    manifest = encoded(
        {
            "scope": SCOPE,
            "run_id": RUN,
            "members": {name: digest(raw) for name, raw in artifacts.items()},
        }
    )
    for name, raw in {**artifacts, "manifest.json": manifest}.items():
        write_new(destination / name, raw, 0o600)
    driver = render_driver(config, files, digest(manifest)).encode()
    write_new(destination / "owner-run.sh", driver, 0o700)
    seal = encoded(
        {
            "scope": SCOPE,
            "run_id": RUN,
            "manifest_sha256": digest(manifest),
            "driver_sha256": digest(driver),
        }
    )
    write_new(destination / "review-seal.json", seal, 0o600)
    return {
        "review_seal_sha256": digest(seal),
        "manifest_sha256": digest(manifest),
        "driver_sha256": digest(driver),
    }
