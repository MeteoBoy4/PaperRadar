"""Closed metadata contract for a no-network resolver/window H1 case.

Only standard-library imports are used before installation verification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from scripts.issue167_h1_phase import Plan


class CaseRejected(ValueError):
    """Controlled reason only."""


def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in rows:
        if key in value:
            raise CaseRejected("metadata_duplicate")
        value[key] = item
    return value


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Case:
    run_id: str
    uid: int
    gid: int
    profile_sha256: str
    resolver_sha256: str
    apport_sha256: str
    worker_timeout_s: int = 40
    owner_timeout_s: int = 90

    def __post_init__(self) -> None:
        if (
            type(self.run_id) is not str
            or re.fullmatch(r"[a-f0-9]{12}", self.run_id) is None
        ):
            raise CaseRejected("case_identity_unknown")
        if any(type(v) is not int or not 0 < v < 2**31 for v in (self.uid, self.gid)):
            raise CaseRejected("case_identity_unknown")
        if any(
            type(v) is not str or re.fullmatch(r"[a-f0-9]{64}", v) is None
            for v in (self.profile_sha256, self.resolver_sha256, self.apport_sha256)
        ):
            raise CaseRejected("case_digest_unknown")
        if (
            type(self.worker_timeout_s) is not int
            or self.worker_timeout_s != 40
            or type(self.owner_timeout_s) is not int
            or self.owner_timeout_s != 90
        ):
            raise CaseRejected("case_deadline_unknown")

    @property
    def install_root(self) -> Path:
        return Path(f"/home/paperradar-probes/issue167-{self.run_id}")

    @property
    def runtime_root(self) -> Path:
        return Path(f"/run/paperradar-issue167-{self.run_id}")

    @property
    def worker_root(self) -> Path:
        return self.runtime_root / "worker"

    @property
    def unit(self) -> str:
        return f"paperradar-167-h1net-{self.run_id}.service"

    @property
    def table(self) -> str:
        return f"paperradar167_{self.run_id}"

    def base_plan(self) -> Plan:
        from scripts.issue167_h1_phase import Plan

        return Plan(self.run_id, self.uid, self.gid, network_mode="ipv4_only")

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "h1_resolver_window_preflight",
            "run_id": self.run_id,
            "uid": self.uid,
            "gid": self.gid,
            "install_root": str(self.install_root),
            "runtime_root": str(self.runtime_root),
            "unit": self.unit,
            "table": self.table,
            "profile_sha256": self.profile_sha256,
            "resolver_sha256": self.resolver_sha256,
            "apport_sha256": self.apport_sha256,
            "worker_timeout_s": self.worker_timeout_s,
            "owner_timeout_s": self.owner_timeout_s,
            "network_operations": 0,
            "node_pi": False,
            "auth_calls": 0,
            "model_calls": 0,
            "synthetic_auth_execs": 1,
            "synthetic_model_execs": 1,
            "authorization": "not_granted",
        }

    @classmethod
    def from_dict(cls, value: object) -> Case:
        if type(value) is not dict:
            raise CaseRejected("case_shape_unknown")
        try:
            case = cls(
                **{
                    key: value[key]
                    for key in (
                        "run_id",
                        "uid",
                        "gid",
                        "profile_sha256",
                        "resolver_sha256",
                        "apport_sha256",
                        "worker_timeout_s",
                        "owner_timeout_s",
                    )
                }
            )
            if json.dumps(value, sort_keys=True) != json.dumps(
                case.to_dict(), sort_keys=True
            ):
                raise CaseRejected("case_binding_unknown")
            return case
        except (KeyError, TypeError):
            raise CaseRejected("case_shape_unknown") from None


def protected(path: Path, *, directory: bool = False) -> None:
    for item in (path, *path.parents):
        info = item.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise CaseRejected("protected_installation_required")
    info = path.lstat()
    valid = (
        stat.S_ISDIR(info.st_mode)
        if directory
        else (stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    )
    if not valid:
        raise CaseRejected("protected_installation_required")


def read_metadata(path: Path, *, owner: int, limit: int = 65536) -> object:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if stat.S_ISREG(info.st_mode) and info.st_uid == owner and info.st_nlink == 2:
            raise FileNotFoundError("metadata_publishing")
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != owner
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > limit
        ):
            raise CaseRejected("metadata_unknown")
        raw = source.read(limit + 1)
        if len(raw) > limit:
            raise CaseRejected("metadata_unknown")
    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (UnicodeError, ValueError, RecursionError):
        raise CaseRejected("metadata_unknown") from None


def load_case(path: Path, *, owner: int = 0) -> Case:
    return Case.from_dict(read_metadata(path, owner=owner))


def current_host_context() -> dict[str, str]:
    return {
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "kernel": os.uname().release,
        "machine": os.uname().machine,
        "hostname_sha256": digest(os.uname().nodename.encode()),
    }


def render_unit(case: Case) -> str:
    root = case.install_root
    return f"""[Unit]
Description=PaperRadar 167 no-network resolver/window preflight
[Service]
Type=exec
RemainAfterExit=yes
User={case.uid}
Group={case.gid}
WorkingDirectory=/srv/pi-cwd
ExecStart={root}/synthetic-python -I -S -B {root}/issue167_resolver_worker.py
BindReadOnlyPaths={root}/resolv.conf:/etc/resolv.conf
Restart=no
KillMode=control-group
SendSIGKILL=yes
RuntimeMaxSec=50s
TimeoutStartSec=15s
TimeoutStopSec=10s
LimitCORE=0
UMask=0077
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
Delegate=no
RestrictNamespaces=yes
RestrictAddressFamilies=none
IPAddressDeny=any
SocketBindDeny=any
RestrictRealtime=yes
SystemCallArchitectures=native
SystemCallFilter=~bpf io_uring_setup:EPERM io_uring_enter:EPERM io_uring_register:EPERM
StandardOutput=null
StandardError=null
"""


def verify_installation(
    root: Path,
    expected_sha: str | None = None,
    *,
    case_loader: Callable[[Path], Case] = load_case,
) -> tuple[Case, dict[str, Path], str]:
    if (
        re.fullmatch(r"/home/paperradar-probes/issue167-[a-f0-9]{12}", str(root))
        is None
    ):
        raise CaseRejected("installation_root_unknown")
    protected(root, directory=True)
    protected(root / "manifest.json")
    raw = (root / "manifest.json").read_bytes()
    actual_sha = digest(raw)
    if len(raw) > 65536 or (expected_sha is not None and actual_sha != expected_sha):
        raise CaseRejected("manifest_changed")
    manifest = read_metadata(root / "manifest.json", owner=0)
    if type(manifest) is not dict or set(manifest) != {"kind", "members", "tools"}:
        raise CaseRejected("manifest_unknown")
    if manifest["kind"] != "h1_synthetic_local_review":
        raise CaseRejected("manifest_unknown")
    members = manifest["members"]
    if type(members) is not dict or len(members) > 40:
        raise CaseRejected("manifest_unknown")
    required = {
        "plan.json",
        "profile.json",
        "resolv.conf",
        "host-context.json",
        "synthetic-python",
        "issue167_resolver_case.py",
        "issue167_resolver_worker.py",
        "issue167_resolver_child.py",
        "issue167_h1_owner_run.py",
        "issue167_h1_phase.py",
        "issue167_h1_guardian.py",
        "issue167_h1_owner_ops.py",
        "issue167_service_egress.py",
        "issue167_fork_observation.py",
        "issue167_observation.py",
        "production_isolation.py",
        "production_errors.py",
    }
    if not required <= set(members):
        raise CaseRejected("manifest_unknown")
    total = len(raw)
    for name, expected in members.items():
        if (
            type(name) is not str
            or re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None
            or name in {".", ".."}
            or type(expected) is not str
            or re.fullmatch(r"[a-f0-9]{64}", expected) is None
        ):
            raise CaseRejected("manifest_unknown")
        path = root / name
        protected(path)
        if path.stat().st_size > 32 * 1024 * 1024:
            raise CaseRejected("member_size_unknown")
        member = path.read_bytes()
        total += len(member)
        if total > 64 * 1024 * 1024 or digest(member) != expected:
            raise CaseRejected("member_changed")
    case = case_loader(root / "plan.json")
    if case.install_root != root:
        raise CaseRejected("case_binding_unknown")
    if read_metadata(root / "host-context.json", owner=0) != current_host_context():
        raise CaseRejected("host_changed")
    profile = read_metadata(root / "profile.json", owner=0)
    if (
        type(profile) is not dict
        or digest((root / "profile.json").read_bytes()) != case.profile_sha256
    ):
        raise CaseRejected("profile_changed")
    try:
        router = profile["owner_report"]["router"]
        resolver = f"nameserver {router}\n".encode()
    except (KeyError, TypeError):
        raise CaseRejected("profile_changed") from None
    if (
        digest(resolver) != case.resolver_sha256
        or (root / "resolv.conf").read_bytes() != resolver
    ):
        raise CaseRejected("resolver_changed")
    apport = Path("/usr/share/apport/apport")
    protected(apport)
    if (
        apport.stat().st_size > 1024 * 1024
        or digest(apport.read_bytes()) != case.apport_sha256
    ):
        raise CaseRejected("collector_changed")
    specs = manifest["tools"]
    allowed = {
        "python": root / "synthetic-python",
        "nft": Path("/usr/sbin/nft"),
        "systemctl": Path("/usr/bin/systemctl"),
        "systemd_analyze": Path("/usr/bin/systemd-analyze"),
    }
    if type(specs) is not dict or set(specs) != set(allowed):
        raise CaseRejected("tools_unknown")
    tools: dict[str, Path] = {}
    for key, path in allowed.items():
        spec = specs[key]
        if (
            type(spec) is not dict
            or set(spec) != {"path", "sha256"}
            or spec["path"] != str(path)
        ):
            raise CaseRejected("tools_unknown")
        protected(path)
        if not os.access(path, os.X_OK) or digest(path.read_bytes()) != spec["sha256"]:
            raise CaseRejected("tool_changed")
        tools[key] = path
    return case, tools, actual_sha


READY_FIELDS = {
    "run_id",
    "pid",
    "uid",
    "core_limits",
    "no_new_privs",
    "cap_eff_zero",
    "cgroup_matches",
    "resolver_sha256",
    "mount_namespace",
    "pid_namespace",
}
CHAIN_FIELDS = {
    "auth_marker_transferred",
    "model_marker_received",
    "auth_fd_inherited",
    "model_fd_inherited",
    "shared_offset",
    "exclusive_denied_while_child_alive",
    "exclusive_allowed_after_exit",
    "child_core_zero",
    "child_cgroup_matches",
    "child_resolver_matches",
    "child_no_new_privs",
    "separate_session",
}


def validate_ready(case: Case, value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != READY_FIELDS:
        raise CaseRejected("worker_identity_unknown")
    if (
        value["run_id"] != case.run_id
        or type(value["pid"]) is not int
        or value["pid"] <= 1
        or type(value["uid"]) is not int
        or value["uid"] != case.uid
        or json.dumps(value["core_limits"]) != "[0, 0]"
        or any(
            value[key] is not True
            for key in ("no_new_privs", "cap_eff_zero", "cgroup_matches")
        )
        or value["resolver_sha256"] != case.resolver_sha256
        or type(value["mount_namespace"]) is not str
        or re.fullmatch(r"mnt:\[[0-9]+\]", value["mount_namespace"]) is None
        or type(value["pid_namespace"]) is not str
        or re.fullmatch(r"pid:\[[0-9]+\]", value["pid_namespace"]) is None
    ):
        raise CaseRejected("worker_identity_unknown")
    return cast(dict[str, object], value)


def validate_result(case: Case, value: object) -> dict[str, object]:
    required = READY_FIELDS | {
        "result",
        "window",
        "synthetic_chain",
        "network_operations",
        "node_pi",
        "auth_calls",
        "model_calls",
        "synthetic_auth_execs",
        "synthetic_model_execs",
    }
    if type(value) is not dict or set(value) != required:
        raise CaseRejected("worker_result_unknown")
    validate_ready(case, {key: value[key] for key in READY_FIELDS})
    if (
        value["result"] != "observed_expected"
        or value["node_pi"] is not False
        or any(
            type(value[k]) is not int or value[k] != 1
            for k in ("synthetic_auth_execs", "synthetic_model_execs")
        )
        or any(
            type(value[k]) is not int or value[k] != 0
            for k in ("network_operations", "auth_calls", "model_calls")
        )
        or type(value["synthetic_chain"]) is not dict
        or set(value["synthetic_chain"]) != CHAIN_FIELDS
        or any(item is not True for item in value["synthetic_chain"].values())
    ):
        raise CaseRejected("worker_result_unknown")
    window = value["window"]
    if (
        type(window) is not dict
        or set(window)
        != {
            "scope",
            "source",
            "event_source",
            "run_id",
            "result",
            "history",
            "mutation_events",
            "terminal_status",
            "terminal_regular_files",
            "terminal_other_entries",
            "directory_deleted",
            "post_terminal_mutation_events",
            "reasons",
        }
        or window.get("scope") != "fork_observation_prototype"
        or window.get("source") != "kernel_own_cgroup_metadata"
        or window.get("event_source") != "inotify"
        or window.get("run_id") != case.run_id
        or window.get("result") != "window_complete"
        or window.get("history") != "observed_mutation"
        or type(window.get("mutation_events")) is not int
        or window["mutation_events"] < 1
        or window.get("terminal_status") != "synthetic_snapshot"
        or type(window.get("terminal_regular_files")) is not int
        or window["terminal_regular_files"] != 1
        or type(window.get("terminal_other_entries")) is not int
        or window["terminal_other_entries"] != 1
        or window.get("directory_deleted") is not True
        or type(window.get("post_terminal_mutation_events")) is not int
        or window["post_terminal_mutation_events"] != 0
        or window.get("reasons") != []
    ):
        raise CaseRejected("window_unknown")
    return cast(dict[str, object], value)
