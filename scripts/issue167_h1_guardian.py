"""H1 synthetic root guardian candidate; never invoked by ordinary tests."""

from __future__ import annotations

import argparse
import copy
import ctypes
import errno
import hashlib
import json
import os
import re
import resource
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO, cast


class GuardianRejected(ValueError):
    """Only controlled reasons, never external output or request contents."""


def protected_path(path: Path, *, directory: bool = False) -> None:
    for item in (path, *path.parents):
        info = item.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or (stat.S_ISREG(info.st_mode) and info.st_mode & 0o6000)
        ):
            raise GuardianRejected("unprotected_installation")
    mode = path.lstat().st_mode
    if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
        raise GuardianRejected("unprotected_installation")


def _json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GuardianRejected("metadata_invalid")
        result[key] = value
    return result


def read_json(path: Path, *, owner: int, limit: int = 16384) -> object:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != owner
            or info.st_mode & 0o022
            or info.st_nlink not in {1, 2}
        ):
            raise GuardianRejected("metadata_owner_invalid")
        if info.st_nlink == 2:
            raise FileNotFoundError("metadata_publishing")
        raw = bytearray()
        while len(raw) <= limit:
            chunk = os.read(descriptor, min(4096, limit + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > limit:
            raise GuardianRejected("metadata_too_large")
        try:
            return json.loads(raw, object_pairs_hook=_json_pairs)
        except (UnicodeError, ValueError):
            raise GuardianRejected("metadata_invalid") from None
    finally:
        os.close(descriptor)


def current_host_context() -> dict[str, str]:
    try:
        boot_id = (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        )
        if (
            re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", boot_id)
            is None
        ):
            raise GuardianRejected("host_context_unknown")
        observed = os.uname()
        return {
            "boot_id": boot_id,
            "kernel": observed.release,
            "machine": observed.machine,
            "hostname_sha256": hashlib.sha256(
                observed.nodename.encode("utf-8")
            ).hexdigest(),
        }
    except (OSError, UnicodeError):
        raise GuardianRejected("host_context_unknown") from None


def verify_host_context(value: object) -> None:
    fields = {"boot_id", "kernel", "machine", "hostname_sha256"}
    if (
        type(value) is not dict
        or set(value) != fields
        or any(type(item) is not str or not item for item in value.values())
    ):
        raise GuardianRejected("host_context_unknown")
    if value != current_host_context():
        raise GuardianRejected("host_context_mismatch")


def bootstrap(root: Path) -> dict[str, Path]:
    """Verify root-owned code BEFORE importing a sibling module."""
    if (
        os.geteuid() != 0
        or re.fullmatch(r"/home/paperradar-probes/issue167-[a-f0-9]{12}", str(root))
        is None
    ):
        raise GuardianRejected("root_installation_required")
    protected_path(root, directory=True)
    protected_path(root / "manifest.json")
    value = read_json(root / "manifest.json", owner=0, limit=65536)
    if not isinstance(value, dict) or set(value) != {"kind", "members", "tools"}:
        raise GuardianRejected("manifest_invalid")
    if value["kind"] != "h1_synthetic_local_review":
        raise GuardianRejected("manifest_invalid")
    members = value["members"]
    required = {
        "plan.json",
        "host-context.json",
        "issue167_h1_guardian.py",
        "issue167_h1_phase.py",
        "issue167_h1_network_worker.py",
        "synthetic-python",
    }
    if (
        not isinstance(members, dict)
        or not required <= members.keys()
        or len(members) > 40
    ):
        raise GuardianRejected("manifest_invalid")
    for name, digest in members.items():
        if (
            not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None
            or not isinstance(digest, str)
            or re.fullmatch(r"[a-f0-9]{64}", digest) is None
        ):
            raise GuardianRejected("manifest_invalid")
        member = root / name
        protected_path(member)
        if member.stat().st_size > 32 * 1024 * 1024:
            raise GuardianRejected("member_too_large")
        if hashlib.sha256(member.read_bytes()).hexdigest() != digest:
            raise GuardianRejected("member_changed")
    verify_host_context(read_json(root / "host-context.json", owner=0, limit=4096))
    specs = value["tools"]
    if not isinstance(specs, dict) or set(specs) != {"python", "nft", "systemctl"}:
        raise GuardianRejected("tools_invalid")
    allowed = {
        "python": {root / "synthetic-python"},
        "nft": {Path("/usr/sbin/nft"), Path("/usr/bin/nft")},
        "systemctl": {Path("/usr/bin/systemctl")},
    }
    tools: dict[str, Path] = {}
    for key, spec in specs.items():
        if not isinstance(spec, dict) or set(spec) != {"path", "sha256"}:
            raise GuardianRejected("tools_invalid")
        if not isinstance(spec["path"], str) or Path(spec["path"]) not in allowed[key]:
            raise GuardianRejected("tools_invalid")
        path = Path(spec["path"])
        protected_path(path)
        if (
            not os.access(path, os.X_OK)
            or hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]
        ):
            raise GuardianRejected("tool_changed")
        tools[key] = path
    return tools


# The installed entry point has no working-directory import path under -I.
if __package__ in {None, ""}:
    _root = Path(__file__).absolute().parent
    _tools = bootstrap(_root)
    sys.path.insert(0, str(_root))
    from issue167_h1_phase import (  # type: ignore[import-not-found]
        PhaseRejected,
        Plan,
        load_plan,
        read_cgroup_state,
        render_create,
        render_delete,
        render_phase,
        verify_nft_state,
    )
else:
    from scripts.issue167_h1_phase import (
        PhaseRejected,
        Plan,
        load_plan,
        read_cgroup_state,
        render_create,
        render_delete,
        render_phase,
        verify_nft_state,
    )


@dataclass(frozen=True)
class UnitState:
    pid: int
    cgroup: str


def read_cgroup_identity(plan: Plan) -> tuple[int, int]:
    """Independent live cgroup2 inode identity, limited to this 64-bit host ABI.

    Linux v7.0 nft_socket extracts cgroup_id=kn->id; kernfs_id_ino returns the
    same full id for 64-bit ino_t, and kernfs_get_inode uses it as i_ino.
    No identity is derived from the rule's own numeric right-hand side.
    """
    if os.uname().machine != "x86_64" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise GuardianRejected("cgroup_identity_unknown")
    root = Path("/sys/fs/cgroup")
    for path in (root, *root.parents):
        protected_path(path, directory=True)
    descriptors: list[int] = []
    try:
        descriptor = os.open(
            root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        descriptors.append(descriptor)
        # fstatfs first long is f_type on the explicitly supported x86_64 ABI.
        filesystem = ctypes.create_string_buffer(256)
        fstatfs = ctypes.CDLL(None, use_errno=True).fstatfs
        fstatfs.argtypes = [ctypes.c_int, ctypes.c_void_p]
        fstatfs.restype = ctypes.c_int
        if (
            fstatfs(descriptor, filesystem) != 0
            or ctypes.c_long.from_buffer(filesystem).value != 0x63677270
        ):
            raise GuardianRejected("cgroup_identity_unknown")
        for name in ("system.slice", plan.unit):
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=descriptor,
            )
            descriptors.append(descriptor)
            info = os.fstat(descriptor)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise GuardianRejected("cgroup_identity_unknown")
        info = os.fstat(descriptor)
        if not 0 < info.st_ino < 2**64:
            raise GuardianRejected("cgroup_identity_unknown")
        return info.st_dev, info.st_ino
    except OSError:
        raise GuardianRejected("cgroup_identity_unknown") from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _binding_rows(value: object) -> tuple[dict[str, int], dict[str, object]]:
    """Extract stable handles and the sole scope match, without trusting its ID."""
    try:
        if type(value) is not dict or type(value.get("nftables")) is not list:
            raise ValueError
        handles = {}
        scope: dict[str, object] | None = None
        for row in value["nftables"]:
            if type(row) is not dict or len(row) != 1:
                raise ValueError
            kind, item = next(iter(row.items()))
            if type(item) is not dict:
                raise ValueError
            label = None
            if kind == "table":
                label = "table"
            elif kind == "chain" and item.get("name") in {"out", "phase"}:
                label = "chain_" + str(item["name"])
            elif kind == "counter" and item.get("name") in {"allowed", "rejected"}:
                label = "counter_" + str(item["name"])
            elif kind == "rule" and item.get("chain") == "out":
                label = "scope"
                scope = item["expr"][0]["match"]
                if type(scope) is not dict:
                    raise ValueError
            if label is not None:
                handle = item.get("handle")
                if (
                    type(handle) is not int
                    or not 0 < handle < 2**64
                    or label in handles
                ):
                    raise ValueError
                handles[label] = handle
        if (
            set(handles)
            != {
                "table",
                "chain_out",
                "chain_phase",
                "counter_allowed",
                "counter_rejected",
                "scope",
            }
            or scope is None
        ):
            raise ValueError
        return handles, scope
    except (KeyError, TypeError, ValueError, IndexError):
        raise GuardianRejected("table_binding_unknown") from None


def make_table_binding(
    plan: Plan, payload: object, identity: tuple[int, int]
) -> dict[str, object]:
    # A binding may be created only while the original path check passes.
    verify_nft_state(plan, "deny", payload)
    handles, _scope = _binding_rows(payload)
    device, inode = identity
    if (
        type(device) is not int
        or device < 0
        or type(inode) is not int
        or not 0 < inode < 2**64
    ):
        raise GuardianRejected("table_binding_unknown")
    return {
        "schema": 1,
        "source": "live_cgroup2_inode64",
        "run_id": plan.run_id,
        "plan_sha256": hashlib.sha256(plan.to_json().encode()).hexdigest(),
        "host_context": current_host_context(),
        "cgroup": plan.cgroup,
        "cgroup_device": device,
        "cgroup_inode": inode,
        "handles": handles,
    }


def validate_table_binding(plan: Plan, value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "schema",
        "source",
        "run_id",
        "plan_sha256",
        "host_context",
        "cgroup",
        "cgroup_device",
        "cgroup_inode",
        "handles",
    }:
        raise GuardianRejected("table_binding_unknown")
    if (
        type(value["schema"]) is not int
        or value["schema"] != 1
        or value["source"] != "live_cgroup2_inode64"
        or value["run_id"] != plan.run_id
        or value["plan_sha256"] != hashlib.sha256(plan.to_json().encode()).hexdigest()
        or value["host_context"] != current_host_context()
        or value["cgroup"] != plan.cgroup
        or type(value["cgroup_device"]) is not int
        or value["cgroup_device"] < 0
        or type(value["cgroup_inode"]) is not int
        or not 0 < value["cgroup_inode"] < 2**64
        or type(value["handles"]) is not dict
        or set(value["handles"])
        != {
            "table",
            "chain_out",
            "chain_phase",
            "counter_allowed",
            "counter_rejected",
            "scope",
        }
        or any(
            type(item) is not int or not 0 < item < 2**64
            for item in value["handles"].values()
        )
    ):
        raise GuardianRejected("table_binding_unknown")
    return cast(dict[str, object], value)


def read_table_binding(plan: Plan) -> dict[str, object]:
    path = plan.runtime_root / "table-binding.json"
    protected_path(path)
    info = path.lstat()
    if stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
        raise GuardianRejected("table_binding_unknown")
    return validate_table_binding(plan, read_json(path, owner=0, limit=8192))


def verify_bound_nft_state(
    plan: Plan, phase: str, value: object, binding: object
) -> tuple[int, int]:
    saved = validate_table_binding(plan, binding)
    payload = copy.deepcopy(value)
    handles, scope = _binding_rows(payload)
    if handles != saved["handles"]:
        raise GuardianRejected("table_binding_unknown")
    right = scope.get("right")
    inode = saved["cgroup_inode"]
    if type(right) is str and right == plan.cgroup[1:]:
        pass
    elif (type(right) is int and right == inode) or (
        type(right) is str and right == str(inode)
    ):
        # Only this independently bound uint64 may be translated for the
        # unchanged full structural verifier. Never normalize arbitrary numbers.
        scope["right"] = plan.cgroup[1:]
    else:
        raise GuardianRejected("table_binding_unknown")
    return cast(tuple[int, int], verify_nft_state(plan, phase, payload))


class Commands:
    """Closed command surface: no caller argv, shell, arbitrary table or unit."""

    def __init__(self, plan: Plan, tools: Mapping[str, Path]) -> None:
        self.plan = plan
        self.tools = tools

    def _run(self, argv: tuple[str, ...], data: bytes = b"") -> bytes:
        if len(data) > 4096:
            raise GuardianRejected("command_input_too_large")
        child = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
        output = bytearray()
        try:
            assert child.stdin is not None and child.stdout is not None
            if data:
                child.stdin.write(data)
            child.stdin.close()
            deadline = time.monotonic() + 8
            with selectors.DefaultSelector() as ready:
                ready.register(child.stdout, selectors.EVENT_READ)
                while ready.get_map():
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise GuardianRejected("command_timeout")
                    for key, _ in ready.select(min(left, 0.1)):
                        raw = os.read(key.fd, 4096)
                        if not raw:
                            ready.unregister(key.fd)
                        else:
                            output.extend(raw)
                            if len(output) > 65536:
                                raise GuardianRejected("command_output_too_large")
            if child.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
                raise GuardianRejected("command_failed")
            return bytes(output)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
            for stream in (child.stdin, child.stdout):
                if stream is not None:
                    stream.close()

    def unit_state(self) -> UnitState:
        raw = self._run(
            (
                str(self.tools["systemctl"]),
                "show",
                self.plan.unit,
                "--property=LoadState,ActiveState,SubState,MainPID,ControlGroup,User,Group",
                "--no-pager",
            )
        )
        try:
            rows = [line.split("=", 1) for line in raw.decode("utf-8").splitlines()]
            value = dict(rows)
            if (
                len(value) != len(rows)
                or set(value)
                != {
                    "LoadState",
                    "ActiveState",
                    "SubState",
                    "MainPID",
                    "ControlGroup",
                    "User",
                    "Group",
                }
                or value["LoadState"] != "loaded"
                or value["ActiveState"] != "active"
                or value["SubState"] != "running"
                or value["ControlGroup"] != self.plan.cgroup
                or value["User"] != str(self.plan.uid)
                or value["Group"] != str(self.plan.gid)
            ):
                raise ValueError
            pid = int(value["MainPID"])
            if pid <= 1:
                raise ValueError
        except (UnicodeError, ValueError):
            raise GuardianRejected("unit_identity_unknown") from None
        return UnitState(pid, value["ControlGroup"])

    def stop(self) -> None:
        self._run((str(self.tools["systemctl"]), "stop", self.plan.unit))

    def create(self) -> None:
        raw = self._run((str(self.tools["nft"]), "-j", "list", "tables"))
        try:
            tree = json.loads(raw, object_pairs_hook=_json_pairs)
            tables = [item["table"] for item in tree["nftables"] if "table" in item]
            if any(
                item["family"] == "inet" and item["name"] == self.plan.table
                for item in tables
            ):
                raise GuardianRejected("table_exists")
        except (ValueError, KeyError, TypeError):
            raise GuardianRejected("table_inventory_unknown") from None
        self._run(
            (str(self.tools["nft"]), "-f", "-"), render_create(self.plan).encode()
        )

    def phase(self, phase: str) -> None:
        if phase not in {"deny", "a", "b"}:
            raise GuardianRejected("phase_invalid")
        self._run(
            (str(self.tools["nft"]), "-f", "-"), render_phase(self.plan, phase).encode()
        )

    def counters(self, phase: str) -> tuple[int, int]:
        return cast(
            tuple[int, int], verify_nft_state(self.plan, phase, self.snapshot())
        )

    def snapshot(self) -> object:
        raw = self._run(
            (str(self.tools["nft"]), "-j", "list", "table", "inet", self.plan.table)
        )
        try:
            return json.loads(raw, object_pairs_hook=_json_pairs)
        except (UnicodeError, ValueError):
            raise GuardianRejected("nft_state_unknown") from None

    def bound_counters(self, phase: str, binding: object) -> tuple[int, int]:
        return verify_bound_nft_state(self.plan, phase, self.snapshot(), binding)

    def delete(self) -> None:
        self._run(
            (str(self.tools["nft"]), "-f", "-"), render_delete(self.plan).encode()
        )


class Operations(Protocol):
    def reserve(self) -> None: ...
    def start_peer(self) -> None: ...
    def wait(self, name: str) -> object: ...
    def members(self, pid: int) -> frozenset[int]: ...
    def create(self) -> None: ...
    def counters(self, phase: str) -> tuple[int, int]: ...
    def phase(self, phase: str) -> None: ...
    def gate(self, phase: str) -> None: ...
    def cleanup(self) -> bool: ...


def validate_file_probe(value: object) -> None:
    booleans = {
        "allow_install_read",
        "allow_attempt_write",
        "deny_install_write",
        "deny_cwd_write",
        "deny_business_read",
        "deny_publisher_read",
        "deny_credentials_read",
        "directory_deleted",
        "coverage_complete",
    }
    fields = booleans | {"result", "history", "terminal_regular_files"}
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or any(value[key] is not True for key in booleans)
        or value["result"] != "observed_expected"
        or value["history"] != "observed_mutation"
        or type(value["terminal_regular_files"]) is not int
        or value["terminal_regular_files"] != 1
    ):
        raise GuardianRejected("file_probe_unknown")


def reconcile_done(plan: Plan, phase: str, value: object) -> None:
    if phase not in {"a", "b"}:
        raise GuardianRejected("phase_invalid")
    if not isinstance(value, dict) or set(value) != {"run_id", "phase", "cases"}:
        raise GuardianRejected("phase_metadata_invalid")
    if value["run_id"] != plan.run_id or value["phase"] != phase:
        raise GuardianRejected("phase_metadata_invalid")
    rows = value["cases"]
    current = plan.port_a if phase == "a" else plan.port_b
    other = plan.port_b if phase == "a" else plan.port_a
    expected = [
        (f"{family}-{kind}", transport, family, port, outcome)
        for kind, transport, port, outcome in (
            ("current-tcp", "tcp", current, "allow"),
            ("other-tcp", "tcp", other, "deny"),
            ("blocked-tcp", "tcp", plan.blocked_port, "deny"),
            ("blocked-udp", "udp", plan.blocked_port, "deny"),
            ("dns-udp", "udp", 53, "deny"),
        )
        for family in (("v4",) if plan.network_mode == "ipv4_only" else ("v4", "v6"))
    ]
    if plan.network_mode == "ipv4_only":
        expected = [
            ("v6-socket-tcp", "socket_check", "v6", 0, "deny"),
            ("v6-socket-udp", "socket_check", "v6", 0, "deny"),
            *expected,
        ]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise GuardianRejected("phase_metadata_invalid")
    for row, (case, transport, family, port, outcome) in zip(
        rows, expected, strict=True
    ):
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "case",
                "kind",
                "family",
                "port",
                "expected",
                "outcome",
                "errno_category",
            }
            or type(row["port"]) is not int
            or (row["case"], row["kind"], row["family"], row["port"], row["expected"])
            != (case, transport, family, port, outcome)
        ):
            raise GuardianRejected("phase_metadata_invalid")
        if (
            outcome == "allow"
            and (row["outcome"] != "allowed" or row["errno_category"] != "none")
        ) or (
            outcome == "deny"
            and (
                row["outcome"] != "denied"
                or row["errno_category"]
                not in (
                    {"permission_denied", "address_family_unavailable"}
                    if transport == "socket_check"
                    else {"permission_denied", "admin_unreachable"}
                )
            )
        ):
            raise GuardianRejected("phase_observation_unknown")


_REASONS = frozenset(
    {
        "worker_identity_unknown",
        "file_probe_unknown",
        "unexpected_descendants",
        "independent_counter_unknown",
        "leftover_metadata_invalid",
        "leftover_observation_unknown",
        "phase_metadata_invalid",
        "phase_observation_unknown",
        "unit_identity_unknown",
        "worker_identity_changed",
        "nft_state_unknown",
        "cgroup_unknown",
        "cgroup_read_unknown",
        "table_exists",
        "table_inventory_unknown",
        "command_failed",
        "command_timeout",
        "command_output_too_large",
        "peer_not_ready",
        "peer_exited",
        "metadata_timeout",
        "metadata_invalid",
        "metadata_owner_invalid",
        "metadata_too_large",
        "phase_invalid",
        "unprotected_installation",
        "host_context_unknown",
        "host_context_mismatch",
        "runtime_metadata_invalid",
        "guardian_metadata_unknown",
        "guardian_runtime_invalid",
        "cgroup_identity_unknown",
        "table_binding_unknown",
    }
)


def failure_reason(error: Exception) -> str:
    if isinstance(error, FileExistsError):
        return "case_already_consumed"
    if isinstance(error, (GuardianRejected, PhaseRejected)) and len(error.args) == 1:
        reason = error.args[0]
        if type(reason) is str and reason in _REASONS:
            return reason
    return "observer_failure"


def run_guardian(plan: Plan, ops: Operations) -> dict[str, object]:
    result: dict[str, object] = {
        "scope": "h1_synthetic_local_only",
        "run_id": plan.run_id,
        "result": "unknown",
        "phase_counts": {},
        "leftover_refused": False,
        "cleanup_complete": False,
        "auth_calls": 0,
        "model_calls": 0,
    }
    successful = False
    reserved = False
    stage = "reserve"
    try:
        ops.reserve()
        reserved = True
        stage = "peer_start"
        ops.start_peer()
        stage = "worker_ready"
        ready = ops.wait("ready.json")
        if (
            not isinstance(ready, dict)
            or set(ready)
            != {
                "run_id",
                "pid",
                "uid",
                "file_probe",
                "core_limits",
                "no_new_privs",
                "cap_eff_zero",
                "cgroup_matches",
            }
            or type(ready["core_limits"]) is not list
            or len(ready["core_limits"]) != 2
            or any(
                type(value) is not int or value != 0 for value in ready["core_limits"]
            )
            or any(
                ready[key] is not True
                for key in ("no_new_privs", "cap_eff_zero", "cgroup_matches")
            )
            or ready["run_id"] != plan.run_id
            or type(ready["uid"]) is not int
            or ready["uid"] != plan.uid
            or type(ready["pid"]) is not int
            or ready["pid"] <= 1
        ):
            raise GuardianRejected("worker_identity_unknown")
        stage = "identity_file_validation"
        validate_file_probe(ready["file_probe"])
        pid = ready["pid"]
        stage = "initial_members"
        if ops.members(pid) != {pid}:
            raise GuardianRejected("unexpected_descendants")
        stage = "initial_rules"
        ops.create()
        ops.counters("deny")
        counts: dict[str, dict[str, int]] = {}
        result["phase_counts"] = counts
        for phase in ("a", "b"):
            stage = f"phase_{phase}"
            if ops.members(pid) != {pid}:
                raise GuardianRejected("unexpected_descendants")
            ops.phase(phase)
            before = ops.counters(phase)
            ops.gate(phase)
            done = ops.wait(f"{phase}-done.json")
            reconcile_done(plan, phase, done)
            after = ops.counters(phase)
            allowed, rejected = after[0] - before[0], after[1] - before[1]
            minimum_allowed, minimum_rejected = (
                (1, 4) if plan.network_mode == "ipv4_only" else (2, 8)
            )
            if allowed < minimum_allowed or rejected < minimum_rejected:
                raise GuardianRejected("independent_counter_unknown")
            counts[phase] = {
                "allowed_packet_delta": allowed,
                "rejected_packet_delta": rejected,
            }
        result["phase_counts"] = counts
        stage = "leftover"
        leftover = ops.wait("leftover-ready.json")
        if (
            not isinstance(leftover, dict)
            or set(leftover) != {"run_id", "controller_pid", "child_pid"}
            or leftover["run_id"] != plan.run_id
            or type(leftover["controller_pid"]) is not int
            or leftover["controller_pid"] != pid
            or type(leftover["child_pid"]) is not int
            or leftover["child_pid"] <= 1
            or leftover["child_pid"] == pid
        ):
            raise GuardianRejected("leftover_metadata_invalid")
        members = ops.members(pid)
        if members != {pid, leftover["child_pid"]}:
            raise GuardianRejected("leftover_observation_unknown")
        # Deliberately DO NOT switch: a remaining descendant forbids another phase.
        result["leftover_refused"] = True
        successful = True
    except Exception as error:
        result["failure_reason"] = failure_reason(error)
        result["failure_stage"] = stage
        if isinstance(error, OSError):
            result["os_error_category"] = (
                "permission_denied"
                if error.errno in {errno.EPERM, errno.EACCES}
                else "file_missing"
                if error.errno == errno.ENOENT
                else "other_os_error"
            )
    finally:
        if reserved:
            result["cleanup_complete"] = ops.cleanup()
    if successful and result["cleanup_complete"] is not True:
        result["failure_reason"] = "cleanup_unknown"
    if successful and result["cleanup_complete"] is True:
        result["result"] = "observed_expected"
    return result


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def claim_anchor(path: Path, run_id: str) -> TextIO:
    protected_path(path.parent, directory=True)
    descriptor = os.open(
        path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    output = os.fdopen(descriptor, "w+")
    try:
        json.dump({"run_id": run_id, "state": "reserved_unknown"}, output)
        output.flush()
        os.fsync(output.fileno())
        _sync_directory(path.parent)
    except BaseException:
        output.close()
        raise
    return output


def guardian_runtime_metadata() -> dict[str, object]:
    # Only selected self metadata; never environ/cmdline or another process.
    with Path("/proc/self/status").open("rb") as source:
        raw = source.read(16385)
    if len(raw) > 16384:
        raise GuardianRejected("guardian_metadata_unknown")
    selected: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        key, _, value = line.partition(":")
        if key in {"CapEff", "NoNewPrivs", "Uid"}:
            if key in selected:
                raise GuardianRejected("guardian_metadata_unknown")
            selected[key] = value.strip()
    if set(selected) != {"CapEff", "NoNewPrivs", "Uid"}:
        raise GuardianRejected("guardian_metadata_unknown")
    if re.fullmatch(r"[0-9a-fA-F]{16}", selected["CapEff"]) is None:
        raise GuardianRejected("guardian_metadata_unknown")
    caps = int(selected["CapEff"], 16)
    uid = tuple(int(value) for value in selected["Uid"].split())
    bits = {
        "chown": 0,
        "dac_read_search": 2,
        "kill": 5,
        "setgid": 6,
        "setuid": 7,
        "net_admin": 12,
    }
    return {
        "uid_is_root": os.geteuid() == 0 and uid == (0, 0, 0, 0),
        "core_limits": list(resource.getrlimit(resource.RLIMIT_CORE)),
        "no_new_privs": selected["NoNewPrivs"] == "1",
        "capabilities": {name: bool(caps & (1 << bit)) for name, bit in bits.items()},
    }


class LiveOperations:
    def __init__(self, plan: Plan, commands: Commands) -> None:
        self.plan = plan
        self.commands = commands
        self.deadline = time.monotonic() + plan.timeout_s
        self.peer: subprocess.Popen[bytes] | None = None
        self.runtime_owned = False
        self.table_created = False
        self.create_uncertain = False
        self.current_phase = "deny"
        self.anchor: TextIO | None = None
        self.guardian_metadata: dict[str, object] | None = None
        self.table_binding: dict[str, object] | None = None

    def _write(self, path: Path, value: object, mode: int = 0o644) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".publish-", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w") as output:
                os.fchmod(output.fileno(), mode)
                json.dump(value, output, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, path, follow_symlinks=False)
        finally:
            temporary.unlink(missing_ok=True)
        _sync_directory(path.parent)

    def reserve(self) -> None:
        self.anchor = claim_anchor(
            Path("/var/lib/paperradar/probe-runs")
            / f"issue167-{self.plan.run_id}.json",
            self.plan.run_id,
        )
        self.plan.runtime_root.mkdir(mode=0o700, exist_ok=False)
        descriptor = os.open(
            self.plan.runtime_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            # Service UMask=0077 must not remove the worker's traversal rights.
            os.fchmod(descriptor, 0o755)
            if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o755:
                raise GuardianRejected("runtime_metadata_invalid")
        finally:
            os.close(descriptor)
        protected_path(self.plan.runtime_root, directory=True)
        self.runtime_owned = True
        self._write(
            self.plan.runtime_root / "started.json",
            {"run_id": self.plan.run_id, "state": "reserved_unknown"},
        )
        worker = self.plan.runtime_root / "worker"
        worker.mkdir(mode=0o700)
        os.chown(worker, self.plan.uid, self.plan.gid)
        self._write(
            self.plan.runtime_root / "runtime-ready.json",
            {"run_id": self.plan.run_id, "state": "runtime_ready"},
        )

    def start_peer(self) -> None:
        self.guardian_metadata = guardian_runtime_metadata()
        self._write(
            self.plan.runtime_root / "guardian-runtime.json", self.guardian_metadata
        )
        facts = self.guardian_metadata
        capabilities = facts["capabilities"]
        if (
            facts["uid_is_root"] is not True
            or facts["no_new_privs"] is not True
            or facts["core_limits"] != [0, 0]
            or type(capabilities) is not dict
            or not all(value is True for value in capabilities.values())
        ):
            raise GuardianRejected("guardian_runtime_invalid")
        self.peer = subprocess.Popen(
            [
                str(self.commands.tools["python"]),
                "-I",
                "-S",
                "-B",
                str(self.plan.install_root / "issue167_h1_network_worker.py"),
                "--plan",
                str(self.plan.install_root / "plan.json"),
                "--peer",
            ],
            user=self.plan.uid,
            group=self.plan.gid,
            extra_groups=[],
            env={},
            cwd=self.plan.install_root,
            stdout=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        assert self.peer.stdout is not None
        with selectors.DefaultSelector() as ready:
            ready.register(self.peer.stdout, selectors.EVENT_READ)
            if (
                not ready.select(10)
                or os.read(self.peer.stdout.fileno(), 64) != b"READY\n"
            ):
                raise GuardianRejected("peer_not_ready")

    def wait(self, name: str) -> object:
        if name not in {
            "ready.json",
            "a-done.json",
            "b-done.json",
            "leftover-ready.json",
        }:
            raise GuardianRejected("metadata_name_invalid")
        path = self.plan.runtime_root / "worker" / name
        while time.monotonic() < self.deadline:
            if self.peer is not None and self.peer.poll() is not None:
                raise GuardianRejected("peer_exited")
            try:
                return read_json(path, owner=self.plan.uid)
            except FileNotFoundError:
                time.sleep(0.05)
        raise GuardianRejected("metadata_timeout")

    def members(self, pid: int) -> frozenset[int]:
        state = self.commands.unit_state()
        if state.pid != pid:
            raise GuardianRejected("worker_identity_changed")
        return cast(frozenset[int], read_cgroup_state(self.plan).pids)

    def create(self) -> None:
        identity = read_cgroup_identity(self.plan)
        self.create_uncertain = True
        self.commands.create()
        self.create_uncertain = False
        self.table_created = True
        payload = self.commands.snapshot()
        verify_nft_state(self.plan, "deny", payload)
        if read_cgroup_identity(self.plan) != identity:
            raise GuardianRejected("cgroup_identity_unknown")
        self.table_binding = make_table_binding(self.plan, payload, identity)
        self._write(
            self.plan.runtime_root / "table-binding.json", self.table_binding, 0o600
        )

    def counters(self, phase: str) -> tuple[int, int]:
        if self.table_binding is not None:
            return self.commands.bound_counters(phase, self.table_binding)
        return self.commands.counters(phase)

    def phase(self, phase: str) -> None:
        self.counters(self.current_phase)
        self.commands.phase(phase)
        self.current_phase = phase
        self.counters(phase)

    def gate(self, phase: str) -> None:
        if phase not in {"a", "b"}:
            raise GuardianRejected("phase_invalid")
        self._write(
            self.plan.runtime_root / f"go-{phase}.json",
            {
                "run_id": self.plan.run_id,
                "phase": phase,
                "sequence": 1 if phase == "a" else 2,
            },
        )

    def cleanup(self) -> bool:
        empty = False
        try:
            with suppress(GuardianRejected):
                self.commands.stop()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                state = read_cgroup_state(self.plan, allow_absent=True)
                if not state.pids:
                    empty = True
                    break
                time.sleep(0.05)
            if not empty or self.create_uncertain:
                return False  # Leave rules intact: owner must recover this state.
            if self.table_created:
                if self.table_binding is None:
                    self.commands.counters(self.current_phase)
                else:
                    self.commands.bound_counters(self.current_phase, self.table_binding)
                self.commands.delete()
                self.table_created = False
            return True
        except Exception:
            return False
        finally:
            if self.peer is not None:
                if self.peer.poll() is None:
                    os.killpg(self.peer.pid, signal.SIGTERM)
                    try:
                        self.peer.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(self.peer.pid, signal.SIGKILL)
                        self.peer.wait(timeout=2)
                if self.peer.stdout is not None:
                    self.peer.stdout.close()

    def write_result(self, result: object) -> None:
        if isinstance(result, dict):
            result = {
                **result,
                "table_may_remain": self.table_created or self.create_uncertain,
                **(
                    {"guardian_metadata": self.guardian_metadata}
                    if self.guardian_metadata is not None
                    else {}
                ),
            }
        if self.anchor is None:
            return
        try:
            self.anchor.seek(0)
            self.anchor.truncate()
            json.dump(result, self.anchor, sort_keys=True)
            self.anchor.write("\n")
            self.anchor.flush()
            os.fsync(self.anchor.fileno())
            if self.runtime_owned:
                self._write(self.plan.runtime_root / "guardian-result.json", result)
        finally:
            self.anchor.close()
            self.anchor = None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="H1 root-owned guardian; owner approval required"
    )
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    if args.plan != _root / "plan.json":
        raise GuardianRejected("plan_path_invalid")
    plan = load_plan(args.plan)
    if plan.install_root != _root:
        raise GuardianRejected("plan_root_mismatch")
    if (
        Path("/proc/self/cgroup").read_text().strip()
        != f"0::/system.slice/{plan.guardian_unit}"
    ):
        raise GuardianRejected("guardian_service_required")
    ops = LiveOperations(plan, Commands(plan, _tools))
    result = run_guardian(plan, ops)
    ops.write_result(result)
    return 0 if result["result"] == "observed_expected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
