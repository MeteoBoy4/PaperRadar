"""Single-use owner-invoked synthetic duplex-filter validation.

Import is inert. No Pi, application, credentials, DB, or supplier endpoint is
used. Offline tests substitute every host and socket boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import resource
import selectors
import signal
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from scripts import issue167_duplex_filter as filtering
from scripts import issue167_h1_guardian as guardian
from scripts import issue167_h1_phase as cgroups

RUN = "a73d9c02e651"
SCOPE = "synthetic_project_duplex_filter_only"
FRAME_CHANNELS = frozenset({"main_out", "main_in", "control_out", "control_in"})
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
LIMITS: dict[str, Any] = {
    "active_connect_entries": 2,
    "accept_entries": 2,
    "application_send_entries_upper": 12,
    "expected_application_send_entries": 10,
    "wire_tcp_transmissions": "unknown_counter_observation_only",
    "application_retries": 0,
    "node_pi_auth_model_calls": 0,
    "dns_tls_operations": 0,
    "unexpected_connections": "unknown_no_fallback",
    "worker_timeout_s": 75,
    "service_runtime_max_s": 90,
    "owner_timeout_s": 180,
    "command_timeout_s": 8,
    "negative_observation_min_s": 1,
    "negative_gate_budget_ms": 1500,
}


class ProbeRejected(ValueError):
    """Closed experiment reason; never includes external text or payload."""


PROBE_REASONS = frozenset(
    (
        "artifact_member_unknown",
        "artifact_root_unknown",
        "artifact_unknown",
        "artifacts_not_quiescent",
        "baseline_buffer_unknown",
        "baseline_unknown",
        "case_already_consumed",
        "cgroup_not_empty",
        "client_identity_unknown",
        "command_unknown",
        "connection_unknown",
        "control_during_stall_unknown",
        "early_eof_unknown",
        "filter_binding_unknown",
        "filter_ownership_unknown",
        "finished_unknown",
        "fixed_case_unknown",
        "frame_unknown",
        "gate_reference_unknown",
        "gate_unknown",
        "incomplete_frame_unknown",
        "ledger_unknown",
        "member_changed",
        "metadata_directory_unknown",
        "metadata_unknown",
        "negative_direction_missing",
        "negative_duration_unknown",
        "negative_unknown",
        "peer_failed",
        "peer_identity_unknown",
        "peer_privilege_unknown",
        "phase_deadline_unknown",
        "positive_direction_missing",
        "report_unknown",
        "restore_unknown",
        "resume_delivery_unknown",
        "resume_unknown",
        "retry_forbidden",
        "role_deadline_unknown",
        "role_failed",
        "root_changed",
        "scope_already_present",
        "scope_unknown",
        "self_integrity_unknown",
        "stall_payload_arrived_unknown",
        "stop_unknown",
        "table_already_present",
        "table_inventory_unknown",
        "table_not_absent",
        "tool_changed",
        "transport_limit_unknown",
        "transport_short_send_unknown",
        "unexpected_frame",
        "unit_metadata_unknown",
        "unit_not_absent",
        "unit_scope_unknown",
        "worker_exit_unknown",
    )
)


def closed_reason(error: BaseException) -> str:
    allowed = PROBE_REASONS | frozenset(
        {
            "gate_reference_unknown",
            "role_failed",
            "incomplete_frame_unknown",
            "duplex_state_unknown",
            "duplex_scope_unknown",
            "duplex_binding_unknown",
            "duplex_phase_reference_unknown",
            "duplex_transition_unknown",
            "duplex_late_packet",
            "duplex_counter_unknown",
            "duplex_counts_unknown",
            "duplex_reference_chain_unknown",
            "cgroup_identity_unknown",
            "command_failed",
            "command_timeout",
            "command_output_too_large",
        }
    )
    if (
        type(error)
        in {
            ProbeRejected,
            filtering.DuplexRejected,
            guardian.GuardianRejected,
            cgroups.PhaseRejected,
        }
        and len(error.args) == 1
        and type(error.args[0]) is str
        and error.args[0] in allowed
    ):
        return error.args[0]
    return "duplex_operation_unknown"


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact(value: object, expected: object) -> bool:
    try:
        return encoded(value) == encoded(expected)
    except (ValueError, TypeError):
        return False


def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in items:
        if key in result:
            raise ProbeRejected("metadata_unknown")
        result[key] = value
    return result


def read_metadata(path: Path, *, uid: int, limit: int = 32768) -> dict[str, Any]:
    fd = os.open(path, FILE_FLAGS)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != uid
            or before.st_gid != uid
            or before.st_nlink != 1
            or before.st_mode & 0o022
            or before.st_size > limit
        ):
            raise ProbeRejected("metadata_unknown")
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        if (
            len(raw) != before.st_size
            or len(raw) > limit
            or stamp(before) != stamp(after)
        ):
            raise ProbeRejected("metadata_unknown")
        value = json.loads(raw, object_pairs_hook=pairs)
        if type(value) is not dict:
            raise ValueError
        return cast(dict[str, Any], value)
    except (ValueError, UnicodeError):
        raise ProbeRejected("metadata_unknown") from None
    finally:
        os.close(fd)


def stamp(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_uid,
        info.st_gid,
        stat.S_IMODE(info.st_mode),
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def read_role_metadata(
    runtime: Path,
    role: str,
    name: str,
    *,
    expected_root: tuple[int, int],
    expected_directories: Mapping[str, tuple[int, int]],
    root_uid: int = 0,
    uid: int = 1000,
) -> dict[str, Any]:
    """Pin every ancestor before reading a fixed role record; never follow aliases."""
    if (
        role not in {"client", "peer"}
        or name
        not in {
            "ready.json",
            "baseline.json",
            "negative.json",
            "resumed.json",
            "finished.json",
            "failure.json",
        }
        or not runtime.is_absolute()
    ):
        raise ProbeRejected("metadata_directory_unknown")
    fds: list[int] = []
    links: list[tuple[int, str, tuple[int, ...]]] = []
    descriptor = os.open("/", DIR_FLAGS)
    fds.append(descriptor)
    try:
        for part in runtime.parts[1:]:
            info = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                raise ProbeRejected("metadata_directory_unknown")
            parent = descriptor
            descriptor = os.open(part, DIR_FLAGS, dir_fd=parent)
            fds.append(descriptor)
            observed = os.fstat(descriptor)
            if stamp(info)[:6] != stamp(observed)[:6]:
                raise ProbeRejected("metadata_directory_unknown")
            links.append((parent, part, stamp(observed)[:6]))
        root = os.fstat(descriptor)
        if (
            (root.st_dev, root.st_ino) != expected_root
            or root.st_uid != root_uid
            or root.st_gid != root_uid
            or stat.S_IMODE(root.st_mode) != 0o755
        ):
            raise ProbeRejected("metadata_directory_unknown")
        for relative in ("worker", "worker/" + role):
            part = relative.rsplit("/", 1)[-1]
            info = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid != uid
                or info.st_gid != uid
                or stat.S_IMODE(info.st_mode) != 0o700
                or (info.st_dev, info.st_ino) != expected_directories.get(relative)
            ):
                raise ProbeRejected("metadata_directory_unknown")
            parent = descriptor
            descriptor = os.open(part, DIR_FLAGS, dir_fd=parent)
            fds.append(descriptor)
            if stamp(os.fstat(descriptor))[:6] != stamp(info)[:6]:
                raise ProbeRejected("metadata_directory_unknown")
            links.append((parent, part, stamp(info)[:6]))
        before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != uid
            or before.st_gid != uid
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size > 32768
        ):
            raise ProbeRejected("metadata_unknown")
        handle = os.open(name, FILE_FLAGS, dir_fd=descriptor)
        try:
            if stamp(os.fstat(handle)) != stamp(before):
                raise ProbeRejected("metadata_unknown")
            raw = os.read(handle, 32769)
            if (
                len(raw) != before.st_size
                or len(raw) > 32768
                or stamp(os.fstat(handle)) != stamp(before)
            ):
                raise ProbeRejected("metadata_unknown")
        finally:
            os.close(handle)
        for parent, part, expected in links:
            if (
                stamp(os.stat(part, dir_fd=parent, follow_symlinks=False))[:6]
                != expected
            ):
                raise ProbeRejected("metadata_directory_unknown")
        if stamp(os.stat(name, dir_fd=descriptor, follow_symlinks=False)) != stamp(
            before
        ):
            raise ProbeRejected("metadata_unknown")
        value = json.loads(raw, object_pairs_hook=pairs)
        if type(value) is not dict:
            raise ValueError
        return cast(dict[str, Any], value)
    except (ValueError, UnicodeError, OSError) as error:
        if isinstance(error, ProbeRejected):
            raise
        if isinstance(error, FileNotFoundError):
            raise
        raise ProbeRejected("metadata_directory_unknown") from None
    finally:
        for item in reversed(fds):
            os.close(item)


def publish(path: Path, value: object, *, mode: int = 0o600) -> None:
    temporary = path.parent / (".publish-" + path.name)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb", closefd=False) as output:
            os.fchmod(fd, mode)
            output.write(encoded(value))
            output.flush()
            os.fsync(fd)
        os.link(temporary, path, follow_symlinks=False)
    finally:
        os.close(fd)
        temporary.unlink(missing_ok=True)
    parent = os.open(path.parent, DIR_FLAGS)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def open_role_directory(path: Path, *, uid: int = 1000) -> int:
    if not path.is_absolute():
        raise ProbeRejected("metadata_directory_unknown")
    descriptors = [os.open("/", DIR_FLAGS)]
    try:
        for part in path.parts[1:]:
            info = os.stat(part, dir_fd=descriptors[-1], follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                raise ProbeRejected("metadata_directory_unknown")
            descriptor = os.open(part, DIR_FLAGS, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            if stamp(os.fstat(descriptor))[:6] != stamp(info)[:6]:
                raise ProbeRejected("metadata_directory_unknown")
        info = os.fstat(descriptors[-1])
        if (
            info.st_uid != uid
            or info.st_gid != uid
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise ProbeRejected("metadata_directory_unknown")
        result = descriptors.pop()
        return result
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def publish_at(directory_fd: int, name: str, value: object) -> None:
    if Path(name).name != name or name in {".", ".."}:
        raise ProbeRejected("metadata_unknown")
    temporary = ".publish-" + name
    fd = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        with os.fdopen(fd, "wb", closefd=False) as output:
            os.fchmod(fd, 0o600)
            output.write(encoded(value))
            output.flush()
            os.fsync(fd)
        os.link(
            temporary,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
    finally:
        os.close(fd)
        os.unlink(temporary, dir_fd=directory_fd)
    os.fsync(directory_fd)


@dataclass(frozen=True)
class Case:
    run_id: str = RUN

    def __post_init__(self) -> None:
        if self.run_id != RUN:
            raise ProbeRejected("fixed_case_unknown")

    @property
    def plan(self) -> filtering.Plan:
        return filtering.Plan(self.run_id)

    @property
    def code(self) -> Path:
        return Path("/home/paperradar-probes/issue167-" + self.run_id)

    @property
    def runtime(self) -> Path:
        return Path("/run/paperradar-issue167-" + self.run_id)

    @property
    def worker(self) -> Path:
        return self.runtime / "worker"

    @property
    def ledger(self) -> Path:
        return Path("/var/lib/paperradar/probe-runs/issue167-" + self.run_id + ".json")

    @property
    def unit_path(self) -> Path:
        return Path("/etc/systemd/system") / self.plan.unit


def frame(channel: str, sequence: int) -> bytes:
    if (
        channel not in FRAME_CHANNELS
        or type(sequence) is not int
        or not 1 <= sequence <= 3
    ):
        raise ProbeRejected("frame_unknown")
    if channel.startswith("main_") and sequence > 2:
        raise ProbeRejected("frame_unknown")
    return f"{RUN}:{channel}:{sequence}\n".encode("ascii")


class FrameBuffer:
    def __init__(self) -> None:
        self.pending = bytearray()

    def feed(self, raw: bytes) -> list[tuple[str, int]]:
        if (
            type(raw) is not bytes
            or len(raw) > 256
            or len(self.pending) + len(raw) > 256
        ):
            raise ProbeRejected("frame_unknown")
        self.pending.extend(raw)
        result = []
        while b"\n" in self.pending:
            line, _, tail = self.pending.partition(b"\n")
            self.pending[:] = tail
            try:
                run, channel, number = line.decode("ascii").split(":")
                if run != RUN or not number.isascii() or not number.isdigit():
                    raise ValueError
                sequence = int(number)
                if frame(channel, sequence) != line + b"\n":
                    raise ValueError
            except (ValueError, UnicodeError):
                raise ProbeRejected("frame_unknown") from None
            result.append((channel, sequence))
        return result


def validate_report(value: object, *, role: str, stage: str) -> dict[str, Any]:
    expected = {
        "scope": SCOPE,
        "run_id": RUN,
        "role": role,
        "stage": stage,
        "integrity": "complete",
    }
    if role not in {"client", "peer"} or stage not in {
        "ready",
        "baseline",
        "negative",
        "resumed",
        "finished",
    }:
        raise ProbeRejected("report_unknown")
    if (
        type(value) is not dict
        or set(value) != {*expected, "metadata"}
        or not exact({k: value.get(k) for k in expected}, expected)
        or type(value["metadata"]) is not dict
    ):
        raise ProbeRejected("report_unknown")
    fields = {
        "ready": {
            "pid",
            "uid",
            "gid",
            "core_zero",
            "no_new_privs",
            "effective_permitted_inheritable_ambient_empty",
        },
        "baseline": {
            "gate_reference_sha256",
            "main_socket",
            "connect_entries",
            "main_received_A",
            "main_send_entries",
            "control_roundtrip",
            "pending_payload_bytes",
            "accept_entries",
        },
        "negative": {
            "gate_reference_sha256",
            "main_B_send_entries",
            "main_B_received",
            "new_main_payload_bytes_observed",
            "pending_main_payload_bytes",
            "control_roundtrip_during_stall",
            "negative_end_monotonic_ns",
            "negative_started_monotonic_ns",
            "negative_finished_monotonic_ns",
        },
        "resumed": {
            "gate_reference_sha256",
            "main_B_received_without_resend",
            "main_B_read_monotonic_ns",
            "main_application_send_entries",
            "control_roundtrip_after_resume",
            "send_entries",
            "connect_entries",
            "accept_entries",
        },
        "finished": {
            "all_sockets_closed",
            "send_entries",
            "connect_entries",
            "accept_entries",
        },
    }
    metadata = value["metadata"]
    if set(metadata) != fields[stage]:
        raise ProbeRejected("report_unknown")
    for key, item in metadata.items():
        if key == "gate_reference_sha256":
            if (
                type(item) is not str
                or len(item) != 64
                or any(c not in "0123456789abcdef" for c in item)
            ):
                raise ProbeRejected("report_unknown")
        elif key == "main_socket":
            if type(item) is not dict or set(item) != {
                "local_address",
                "local_port",
                "peer_address",
                "peer_port",
                "socket_inode",
            }:
                raise ProbeRejected("report_unknown")
            if any(item[k] != "127.0.0.1" for k in ("local_address", "peer_address")):
                raise ProbeRejected("report_unknown")
            for name in ("local_port", "peer_port", "socket_inode"):
                if type(item[name]) is not int or item[name] <= 0:
                    raise ProbeRejected("report_unknown")
                if item[name] > (65535 if name.endswith("port") else 2**64 - 1):
                    raise ProbeRejected("report_unknown")
        elif key in {
            "core_zero",
            "no_new_privs",
            "effective_permitted_inheritable_ambient_empty",
            "main_received_A",
            "control_roundtrip",
            "main_B_received",
            "control_roundtrip_during_stall",
            "main_B_received_without_resend",
            "control_roundtrip_after_resume",
            "all_sockets_closed",
        }:
            if type(item) is not bool:
                raise ProbeRejected("report_unknown")
        elif type(item) is not int or not 0 <= item < 2**64:
            raise ProbeRejected("report_unknown")
    return cast(dict[str, Any], value)


CORE_NAMES = frozenset(
    {
        "issue167_h1_phase.py",
        "issue167_h1_guardian.py",
        "issue167_duplex_filter.py",
        "issue167_duplex_probe.py",
        "issue167_duplex_cleanup.py",
        "worker-entry.py",
        "probe.service",
    }
)


def installed_manifest(config: dict[str, Any], files: Mapping[str, bytes]) -> bytes:
    if (
        set(files) != CORE_NAMES | {"scope.json"}
        or set(config.get("members", {})) != CORE_NAMES
        or config.get("scope") != SCOPE
        or config.get("run_id") != RUN
        or files["scope.json"] != encoded(config)
        or any(type(raw) is not bytes for raw in files.values())
        or any(digest(files[name]) != config["members"][name] for name in CORE_NAMES)
    ):
        raise ProbeRejected("scope_unknown")
    return encoded(
        {
            "scope": SCOPE,
            "run_id": RUN,
            "members": {name: digest(raw) for name, raw in files.items()},
            "tools": config["tools"],
        }
    )


def host_context() -> dict[str, str]:
    return {
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "kernel": os.uname().release,
        "machine": os.uname().machine,
        "hostname_sha256": digest(os.uname().nodename.encode()),
    }


def self_integrity() -> dict[str, object]:
    selected = {}
    with Path("/proc/self/status").open("rb") as source:
        raw = source.read(16385)
    if len(raw) > 16384:
        raise ProbeRejected("self_integrity_unknown")
    for line in raw.decode("ascii").splitlines():
        key, _, value = line.partition(":")
        if key in {"NoNewPrivs", "CapEff", "CapPrm", "CapInh", "CapAmb"}:
            if key in selected:
                raise ProbeRejected("self_integrity_unknown")
            selected[key] = value.strip()
    if (
        os.getuid() != 1000
        or os.getgid() != 1000
        or resource.getrlimit(resource.RLIMIT_CORE) != (0, 0)
        or set(selected) != {"NoNewPrivs", "CapEff", "CapPrm", "CapInh", "CapAmb"}
        or selected["NoNewPrivs"] != "1"
        or any(int(selected[k], 16) != 0 for k in selected if k != "NoNewPrivs")
    ):
        raise ProbeRejected("self_integrity_unknown")
    return {
        "pid": os.getpid(),
        "uid": 1000,
        "gid": 1000,
        "core_zero": True,
        "no_new_privs": True,
        "effective_permitted_inheritable_ambient_empty": True,
    }


class Transport:
    """Small public frames only; one send call per frame, never retry short writes."""

    def __init__(self) -> None:
        self.sends = 0
        self.received_bytes = 0
        self.received_per_socket: dict[socket.socket, int] = {}
        self.recv_entries = 0
        self.buffers: dict[socket.socket, FrameBuffer] = {}
        self.frames: dict[socket.socket, list[tuple[str, int]]] = {}
        self.eof: set[socket.socket] = set()

    def add(self, sock: socket.socket) -> None:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setblocking(False)
        self.buffers[sock] = FrameBuffer()
        self.frames[sock] = []
        self.received_per_socket[sock] = 0

    def send(self, sock: socket.socket, channel: str, sequence: int) -> None:
        if self.sends >= 8:
            raise ProbeRejected("transport_limit_unknown")
        self.sends += 1
        raw = frame(channel, sequence)
        if sock.send(raw) != len(raw):
            raise ProbeRejected("transport_short_send_unknown")

    def read(self, sock: socket.socket) -> list[tuple[str, int]]:
        self.recv_entries += 1
        if self.recv_entries > 512:
            raise ProbeRejected("transport_limit_unknown")
        raw = sock.recv(256)
        if not raw:
            self.eof.add(sock)
            return []
        self.received_bytes += len(raw)
        self.received_per_socket[sock] += len(raw)
        output = self.buffers[sock].feed(raw)
        self.frames[sock].extend(output)
        return output


class Role:
    def __init__(self, role: str) -> None:
        self.case = Case()
        self.role = role
        self.directory = self.case.worker / role
        self.output_fd = open_role_directory(self.directory)
        self.deadline = time.monotonic() + LIMITS["worker_timeout_s"]
        self.transport = Transport()
        self.stage = "ready"
        self.selector = selectors.DefaultSelector()
        self.main: socket.socket | None = None
        self.control_source: socket.socket | None = None
        self.accepted: list[socket.socket] = []
        self.listener: socket.socket | None = None
        self.accept_count = 0
        self.connect_count = 0
        self.control_replies: set[int] = set()
        self.control_requests: set[int] = set()
        self.main_received: set[int] = set()
        self.main_send_count = 0
        self.main_bytes_at_stall = 0
        self.negative_complete = False
        self.resumption_validated = False
        self.b_read_ns: int | None = None
        self.main_tuple: dict[str, object] | None = None
        self.control_tuple: dict[str, object] | None = None
        self.gate_reference = ""

    def report(self, stage: str, metadata: dict[str, object]) -> None:
        value = {
            "scope": SCOPE,
            "run_id": RUN,
            "role": self.role,
            "stage": stage,
            "integrity": "complete",
            "metadata": metadata,
        }
        validate_report(value, role=self.role, stage=stage)
        publish_at(self.output_fd, stage + ".json", value)

    def gate(self, stage: str) -> dict[str, Any] | None:
        extras = {
            "baseline": set(),
            "stall": {"negative_end_monotonic_ns", "negative_not_before_monotonic_ns"},
            "resume": {"allow_intent_monotonic_ns"},
            "close": set(),
            "exit": set(),
        }
        if type(stage) is not str or stage not in extras:
            raise ProbeRejected("gate_unknown")
        try:
            value = read_metadata(
                self.case.runtime / ("gate-" + stage + ".json"), uid=0
            )
        except FileNotFoundError:
            return None
        if set(value) != {
            "scope",
            "run_id",
            "stage",
            "phase_reference",
            *extras[stage],
        } or not exact(
            {k: value.get(k) for k in ("scope", "run_id", "stage")},
            {"scope": SCOPE, "run_id": RUN, "stage": stage},
        ):
            raise ProbeRejected("gate_unknown")
        if type(value["phase_reference"]) is not dict:
            raise ProbeRejected("gate_unknown")
        expected_sequence = 1 if stage == "baseline" else 2 if stage == "stall" else 3
        if (
            value["phase_reference"].get("phase")
            != ("stall" if stage == "stall" else "allow")
            or type(value["phase_reference"].get("sequence")) is not int
            or value["phase_reference"]["sequence"] != expected_sequence
        ):
            raise ProbeRejected("gate_unknown")
        return value

    def add(self, sock: socket.socket) -> None:
        self.transport.add(sock)
        self.selector.register(sock, selectors.EVENT_READ)

    def pump(self, duration: float = 0.02) -> None:
        if time.monotonic() >= self.deadline:
            raise ProbeRejected("role_deadline_unknown")
        for key, _ in self.selector.select(duration):
            sock = cast(socket.socket, key.fileobj)
            if sock is self.listener:
                if self.accept_count >= 2:
                    raise ProbeRejected("connection_unknown")
                conn, address = sock.accept()
                self.accept_count += 1
                if self.accept_count > 2 or address[0] != self.case.plan.address:
                    conn.close()
                    raise ProbeRejected("connection_unknown")
                self.accepted.append(conn)
                self.add(conn)
                continue
            before = self.transport.received_bytes
            output = self.transport.read(sock)
            if sock in self.transport.eof:
                self.selector.unregister(sock)
                if self.stage != "closing":
                    if (
                        self.stage == "resume"
                        and self.resumption_validated
                        and self.gate("close") is not None
                    ):
                        self.stage = "closing"
                    else:
                        raise ProbeRejected("early_eof_unknown")
                continue
            if (
                sock is self.main
                and self.stage == "stall"
                and self.transport.received_bytes != before
            ):
                raise ProbeRejected("stall_payload_arrived_unknown")
            for channel, sequence in output:
                self.on_frame(sock, channel, sequence)

    def on_frame(self, sock: socket.socket, channel: str, sequence: int) -> None:
        if self.role == "client":
            if (
                sock is not self.main
                or channel != "main_in"
                or sequence in self.main_received
            ):
                raise ProbeRejected("unexpected_frame")
            if (sequence == 1 and self.stage != "baseline") or (
                sequence == 2 and self.stage not in {"resume_pending", "resume"}
            ):
                raise ProbeRejected("unexpected_frame")
            self.main_received.add(sequence)
            if sequence == 2:
                self.b_read_ns = time.monotonic_ns()
            return
        if sock is self.control_source:
            if channel != "control_in" or sequence in self.control_replies:
                raise ProbeRejected("unexpected_frame")
            if sequence not in {1, 2, 3}:
                raise ProbeRejected("unexpected_frame")
            self.control_replies.add(sequence)
            return
        if channel == "control_out":
            expected_stage = {1: "baseline", 2: "stall", 3: "resume"}.get(sequence)
            if sequence in self.control_requests or self.stage != expected_stage:
                raise ProbeRejected("unexpected_frame")
            self.control_requests.add(sequence)
            if self.control_tuple is None:
                if (
                    sequence != 1
                    or self.control_source is None
                    or sock.getpeername() != self.control_source.getsockname()
                ):
                    raise ProbeRejected("connection_unknown")
                self.control_tuple = socket_tuple(sock)
            elif socket_tuple(sock) != self.control_tuple:
                raise ProbeRejected("connection_unknown")
            self.transport.send(sock, "control_in", sequence)
            return
        if channel != "main_out" or sequence in self.main_received:
            raise ProbeRejected("unexpected_frame")
        if self.main is None:
            if sequence != 1 or self.stage != "baseline":
                raise ProbeRejected("connection_unknown")
            self.main = sock
            self.main_tuple = socket_tuple(sock)
        if sock is not self.main:
            raise ProbeRejected("connection_unknown")
        if sequence == 1 and self.stage == "baseline":
            self.main_received.add(1)
            self.transport.send(sock, "main_in", 1)
            self.main_send_count += 1
        elif sequence == 2 and self.stage in {"resume_pending", "resume"}:
            self.main_received.add(2)
            self.b_read_ns = time.monotonic_ns()
        else:
            raise ProbeRejected("unexpected_frame")

    def wait(self, predicate: Callable[[], bool], *, timeout: float = 10) -> None:
        end = min(self.deadline, time.monotonic() + timeout)
        while not predicate():
            if time.monotonic() >= end:
                raise ProbeRejected("phase_deadline_unknown")
            self.pump()

    def wait_gate(self, name: str) -> dict[str, Any]:
        result: dict[str, Any] | None = None

        def ready() -> bool:
            nonlocal result
            result = self.gate(name)
            return result is not None

        self.wait(ready)
        assert result is not None
        return result

    def observe_negative_window(
        self, end_ns: int, not_before_ns: int
    ) -> dict[str, int]:
        started = time.monotonic_ns()
        if (
            type(end_ns) is not int
            or type(not_before_ns) is not int
            or started < not_before_ns
            or end_ns - started
            < int(LIMITS["negative_observation_min_s"]) * 1_000_000_000
            or end_ns - started > 3_000_000_000
        ):
            raise ProbeRejected("negative_duration_unknown")
        while time.monotonic_ns() < end_ns:
            self.pump(0.01)
        self.pump(0)
        finished = time.monotonic_ns()
        if self.main is None:
            raise ProbeRejected("negative_unknown")
        observed_bytes = (
            self.transport.received_per_socket[self.main] - self.main_bytes_at_stall
        )
        if (
            finished < end_ns
            or observed_bytes != 0
            or 2 in self.main_received
            or self.transport.buffers[self.main].pending
        ):
            raise ProbeRejected("stall_payload_arrived_unknown")
        return {
            "negative_started_monotonic_ns": started,
            "negative_finished_monotonic_ns": finished,
            "new_main_payload_bytes_observed": observed_bytes,
        }

    def run(self) -> None:
        identity = self_integrity()
        if self.role == "peer":
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            listener.setblocking(False)
            listener.bind((self.case.plan.address, self.case.plan.port))
            listener.listen(2)
            self.listener = listener
            self.selector.register(listener, selectors.EVENT_READ)
        self.report("ready", identity)
        baseline_gate = self.wait_gate("baseline")
        self.gate_reference = digest(encoded(baseline_gate))
        self.stage = "baseline"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        self.connect_count += 1
        sock.connect((self.case.plan.address, self.case.plan.port))
        self.add(sock)
        if self.role == "client":
            self.main = sock
            self.main_tuple = socket_tuple(sock)
            self.transport.send(sock, "main_out", 1)
            self.main_send_count += 1
            self.wait(lambda: 1 in self.main_received)
        else:
            self.control_source = sock
            self.transport.send(sock, "control_out", 1)
            self.wait(
                lambda: (
                    1 in self.main_received
                    and 1 in self.control_replies
                    and len(self.accepted) == 2
                )
            )
        if (
            self.main is None
            or self.main_tuple is None
            or self.transport.buffers[self.main].pending
        ):
            raise ProbeRejected("baseline_buffer_unknown")
        self.report(
            "baseline",
            {
                "gate_reference_sha256": self.gate_reference,
                "main_socket": self.main_tuple,
                "connect_entries": 1,
                "main_received_A": True,
                "main_send_entries": 1,
                "control_roundtrip": self.role == "peer",
                "pending_payload_bytes": 0,
                "accept_entries": self.accept_count,
            },
        )
        gate = self.wait_gate("stall")
        self.gate_reference = digest(encoded(gate))
        self.stage = "stall"
        end_ns = gate.get("negative_end_monotonic_ns")
        not_before_ns = gate.get("negative_not_before_monotonic_ns")
        if (
            type(end_ns) is not int
            or type(not_before_ns) is not int
            or not time.monotonic_ns() < end_ns <= time.monotonic_ns() + 3_000_000_000
        ):
            raise ProbeRejected("gate_unknown")
        self.main_bytes_at_stall = self.transport.received_per_socket[self.main]
        self.transport.send(
            self.main, "main_out" if self.role == "client" else "main_in", 2
        )
        self.main_send_count += 1
        if self.role == "peer":
            assert self.control_source is not None
            self.transport.send(self.control_source, "control_out", 2)
        observation = self.observe_negative_window(end_ns, not_before_ns)
        if self.role == "peer" and 2 not in self.control_replies:
            raise ProbeRejected("control_during_stall_unknown")
        self.negative_complete = True
        self.stage = "resume_pending"
        self.report(
            "negative",
            {
                "gate_reference_sha256": self.gate_reference,
                "main_B_send_entries": 1,
                "main_B_received": False,
                **observation,
                "pending_main_payload_bytes": 0,
                "control_roundtrip_during_stall": self.role == "peer",
                "negative_end_monotonic_ns": end_ns,
            },
        )
        gate = self.wait_gate("resume")
        self.gate_reference = digest(encoded(gate))
        allow_intent_ns = gate.get("allow_intent_monotonic_ns")
        self.stage = "resume"
        if type(allow_intent_ns) is not int:
            raise ProbeRejected("gate_unknown")
        self.wait(lambda: 2 in self.main_received)
        if self.b_read_ns is None or self.b_read_ns < allow_intent_ns:
            raise ProbeRejected("resume_delivery_unknown")
        if self.role == "peer":
            assert self.control_source is not None
            self.transport.send(self.control_source, "control_out", 3)
            self.wait(lambda: 3 in self.control_replies)
        self.resumption_validated = True
        self.report(
            "resumed",
            {
                "gate_reference_sha256": self.gate_reference,
                "main_B_received_without_resend": True,
                "main_B_read_monotonic_ns": self.b_read_ns,
                "main_application_send_entries": 2,
                "control_roundtrip_after_resume": self.role == "peer",
                "send_entries": self.transport.sends,
                "connect_entries": self.connect_count,
                "accept_entries": self.accept_count,
            },
        )
        self.wait_gate("close")
        self.stage = "closing"
        for active in list(self.transport.buffers):
            active.shutdown(socket.SHUT_WR)
        self.wait(
            lambda: all(s in self.transport.eof for s in self.transport.buffers),
            timeout=5,
        )
        if any(reader.pending for reader in self.transport.buffers.values()):
            raise ProbeRejected("incomplete_frame_unknown")
        for active in self.transport.buffers:
            active.close()
        if self.listener is not None:
            self.selector.unregister(self.listener)
            self.listener.close()
        self.report(
            "finished",
            {
                "all_sockets_closed": True,
                "send_entries": self.transport.sends,
                "connect_entries": self.connect_count,
                "accept_entries": self.accept_count,
            },
        )
        if self.role == "client":
            self.wait_gate("exit")

    def close(self) -> None:
        for sock in self.transport.buffers:
            sock.close()
        if self.listener is not None:
            self.listener.close()
        self.selector.close()
        os.close(self.output_fd)


def socket_tuple(sock: socket.socket) -> dict[str, object]:
    local, remote = sock.getsockname(), sock.getpeername()
    return {
        "local_address": local[0],
        "local_port": local[1],
        "peer_address": remote[0],
        "peer_port": remote[1],
        "socket_inode": os.fstat(sock.fileno()).st_ino,
    }


def worker_main(role: str) -> int:
    if role not in {"client", "peer"}:
        return 1
    operation = Role(role)
    try:
        operation.run()
        return 0
    except BaseException as error:
        with suppress(BaseException):
            publish_at(
                operation.output_fd,
                "failure.json",
                {
                    "scope": SCOPE,
                    "run_id": RUN,
                    "role": role,
                    "integrity": "unknown",
                    "failure_stage": operation.stage,
                    "failure_reason": closed_reason(error),
                },
            )
        return 1
    finally:
        operation.close()


class Operations(Protocol):
    def preflight(self) -> None: ...
    def reserve(self) -> None: ...
    def install(self) -> None: ...
    def start_peer(self) -> dict[str, object]: ...
    def start_client(self) -> dict[str, object]: ...
    def create_filter(self) -> dict[str, object]: ...
    def switch(self, phase: str) -> dict[str, object]: ...
    def gate(self, name: str, extra: dict[str, object] | None = None) -> str: ...
    def reports(self, stage: str) -> dict[str, Any]: ...
    def snapshot(self, label: str) -> dict[str, object]: ...
    def exit(self) -> dict[str, object]: ...
    def restore(self) -> dict[str, object]: ...
    def remove_artifacts(self) -> dict[str, object]: ...
    def write_ledger(self, value: object) -> None: ...
    def close_peer(self) -> None: ...


def validate_baseline(reports: Mapping[str, Any]) -> None:
    if set(reports) != {"client", "peer"}:
        raise ProbeRejected("baseline_unknown")
    client = reports["client"]["metadata"]
    peer = reports["peer"]["metadata"]
    if not exact(
        {
            k: client.get(k)
            for k in (
                "connect_entries",
                "main_received_A",
                "main_send_entries",
                "control_roundtrip",
                "pending_payload_bytes",
                "accept_entries",
            )
        },
        {
            "connect_entries": 1,
            "main_received_A": True,
            "main_send_entries": 1,
            "control_roundtrip": False,
            "pending_payload_bytes": 0,
            "accept_entries": 0,
        },
    ) or not exact(
        {
            k: peer.get(k)
            for k in (
                "connect_entries",
                "main_received_A",
                "main_send_entries",
                "control_roundtrip",
                "pending_payload_bytes",
                "accept_entries",
            )
        },
        {
            "connect_entries": 1,
            "main_received_A": True,
            "main_send_entries": 1,
            "control_roundtrip": True,
            "pending_payload_bytes": 0,
            "accept_entries": 2,
        },
    ):
        raise ProbeRejected("baseline_unknown")
    a, b = client.get("main_socket"), peer.get("main_socket")
    if (
        type(a) is not dict
        or type(b) is not dict
        or set(a) != set(b)
        or set(a)
        != {"local_address", "local_port", "peer_address", "peer_port", "socket_inode"}
    ):
        raise ProbeRejected("connection_unknown")
    if (
        any(
            type(a[k]) is not int or type(b[k]) is not int or a[k] <= 0 or b[k] <= 0
            for k in ("local_port", "peer_port", "socket_inode")
        )
        or any(
            a[k] != "127.0.0.1" or b[k] != "127.0.0.1"
            for k in ("local_address", "peer_address")
        )
        or a["peer_port"] != 46167
        or b["local_port"] != 46167
        or a["local_port"] != b["peer_port"]
        or a["local_port"] == 46167
        or a["socket_inode"] == b["socket_inode"]
    ):
        raise ProbeRejected("connection_unknown")


def run_owner(ops: Operations) -> dict[str, object]:
    result: dict[str, object] = {
        "scope": SCOPE,
        "run_id": RUN,
        "result": "unknown",
        "limits": dict(LIMITS),
        "peer": None,
        "client": None,
        "rules": [],
        "baseline": None,
        "negative": None,
        "resumed": None,
        "exit": None,
        "restoration": None,
        "artifacts": None,
        "installed_manifest_sha256": getattr(ops, "installed_manifest_sha256", None),
    }
    reserved = installed = successful = False
    stage = "preflight"
    try:
        ops.preflight()
        stage = "reserve"
        ops.reserve()
        reserved = True
        stage = "install"
        installed = True
        ops.install()
        stage = "peer"
        result["peer"] = ops.start_peer()
        if not exact(
            result["peer"],
            {
                "uid": 1000,
                "gid": 1000,
                "outside_target_cgroup": True,
                "core_zero": True,
                "no_new_privs": True,
                "integrity": "complete",
            },
        ):
            raise ProbeRejected("peer_identity_unknown")
        stage = "client"
        result["client"] = ops.start_client()
        if not exact(
            result["client"],
            {
                "uid": 1000,
                "gid": 1000,
                "inside_target_cgroup": True,
                "peer_outside_target_cgroup": True,
                "core_zero": True,
                "no_new_privs": True,
                "integrity": "complete",
            },
        ):
            raise ProbeRejected("client_identity_unknown")
        stage = "filter"
        cast(list[Any], result["rules"]).append(ops.create_filter())
        stage = "allow"
        cast(list[Any], result["rules"]).append(ops.switch("allow"))
        baseline_ref = ops.gate("baseline")
        stage = "baseline"
        baseline = ops.reports("baseline")
        validate_baseline(baseline)
        if any(
            row["metadata"]["gate_reference_sha256"] != baseline_ref
            for row in baseline.values()
        ):
            raise ProbeRejected("gate_reference_unknown")
        result["baseline"] = baseline
        cast(list[Any], result["rules"]).append(ops.snapshot("baseline_complete"))
        stage = "stall"
        cast(list[Any], result["rules"]).append(ops.switch("stall"))
        not_before = time.monotonic_ns()
        end = not_before + int(LIMITS["negative_gate_budget_ms"]) * 1_000_000
        negative_ref = ops.gate(
            "stall",
            {
                "negative_end_monotonic_ns": end,
                "negative_not_before_monotonic_ns": not_before,
            },
        )
        stage = "negative"
        negative = ops.reports("negative")
        for role in ("client", "peer"):
            row = negative[role]["metadata"]
            started_ns = row.get("negative_started_monotonic_ns")
            finished_ns = row.get("negative_finished_monotonic_ns")
            if (
                type(started_ns) is not int
                or type(finished_ns) is not int
                or started_ns < not_before
                or started_ns
                + int(LIMITS["negative_observation_min_s"]) * 1_000_000_000
                > end
                or finished_ns < end
            ):
                raise ProbeRejected("negative_duration_unknown")
            if not exact(
                {
                    k: v
                    for k, v in row.items()
                    if k
                    not in {
                        "negative_started_monotonic_ns",
                        "negative_finished_monotonic_ns",
                    }
                },
                {
                    "gate_reference_sha256": negative_ref,
                    "main_B_send_entries": 1,
                    "main_B_received": False,
                    "new_main_payload_bytes_observed": 0,
                    "pending_main_payload_bytes": 0,
                    "control_roundtrip_during_stall": role == "peer",
                    "negative_end_monotonic_ns": end,
                },
            ):
                raise ProbeRejected("negative_unknown")
        result["negative"] = negative
        cast(list[Any], result["rules"]).append(ops.snapshot("negative_complete"))
        stage = "resume"
        intent = time.monotonic_ns()
        cast(list[Any], result["rules"]).append(ops.switch("allow"))
        resumed_ref = ops.gate("resume", {"allow_intent_monotonic_ns": intent})
        stage = "resumed"
        resumed = ops.reports("resumed")
        for role in ("client", "peer"):
            row = resumed[role]["metadata"]
            if (
                row.get("gate_reference_sha256") != resumed_ref
                or not exact(
                    {
                        k: row.get(k)
                        for k in (
                            "main_B_received_without_resend",
                            "main_application_send_entries",
                            "control_roundtrip_after_resume",
                            "connect_entries",
                            "accept_entries",
                        )
                    },
                    {
                        "main_B_received_without_resend": True,
                        "main_application_send_entries": 2,
                        "control_roundtrip_after_resume": role == "peer",
                        "connect_entries": 1,
                        "accept_entries": 0 if role == "client" else 2,
                    },
                )
                or type(row.get("main_B_read_monotonic_ns")) is not int
                or row["main_B_read_monotonic_ns"] < intent
                or type(row.get("send_entries")) is not int
                or row["send_entries"] != (2 if role == "client" else 8)
            ):
                raise ProbeRejected("resume_unknown")
        result["resumed"] = resumed
        ops.gate("close")
        stage = "close"
        ops.reports("finished")
        cast(list[Any], result["rules"]).append(ops.snapshot("before_exit"))
        ops.gate("exit")
        stage = "exit"
        result["exit"] = ops.exit()
        if not exact(
            result["exit"],
            {
                "strict_controller_exit": True,
                "cgroup_empty": True,
                "peer_exit_zero": True,
            },
        ):
            raise ProbeRejected("worker_exit_unknown")
        successful = True
    except BaseException as error:
        result.update(failure_stage=stage, failure_reason=closed_reason(error))
    finally:
        if installed:
            try:
                result["restoration"] = ops.restore()
                if not exact(
                    result["restoration"],
                    {
                        "unit_absent": True,
                        "table_absent": True,
                        "cgroup_empty": True,
                        "peer_reaped": True,
                        "ledger_retained": True,
                    },
                ):
                    raise ProbeRejected("restore_unknown")
            except BaseException:
                successful = False
                result["restoration_error"] = "restoration_unknown"
        if successful:
            try:
                result["artifacts"] = ops.remove_artifacts()
                if not exact(
                    result["artifacts"],
                    {"code_runtime_removed": True, "ledger_retained": True},
                ):
                    raise ProbeRejected("artifact_unknown")
                result["result"] = "observed_expected_and_restored"
            except BaseException:
                result.update(
                    failure_stage="artifacts", failure_reason="artifact_unknown"
                )
        try:
            ops.close_peer()
        except BaseException:
            result.update(result="unknown", peer_close_error="peer_descriptor_unknown")
        if hasattr(ops, "failure_reports"):
            try:
                result["role_failures"] = ops.failure_reports()
            except BaseException:
                result["role_failures"] = {"integrity": "unknown"}
        if reserved:
            try:
                ops.write_ledger(result)
            except BaseException:
                result.update(result="unknown", ledger_error="permanent_result_unknown")
    return result


def render_unit(case: Case, python: str) -> str:
    return f"""[Unit]
Description=PaperRadar 167 synthetic project duplex filter
[Service]
Type=exec
RemainAfterExit=yes
User=1000
Group=1000
ExecStart={python} -I -S -B {case.code}/worker-entry.py client
WorkingDirectory={case.worker}/client
Environment=PATH=/usr/bin:/bin
UMask=0077
Restart=no
KillMode=control-group
SendSIGKILL=yes
TimeoutStartSec=10s
TimeoutStopSec=8s
RuntimeMaxSec=90s
LimitCORE=0
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictAddressFamilies=AF_INET
IPAddressDeny=any
IPAddressAllow=127.0.0.1/32
SocketBindDeny=any
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={case.worker}/client
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
RestrictSUIDSGID=yes
LockPersonality=yes
StandardInput=null
StandardOutput=null
StandardError=null
"""


def peer_limits() -> None:
    """Only used by the future root owner before its own unprivileged child exec."""
    import ctypes

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    library = ctypes.CDLL(None, use_errno=True)
    if library.prctl(38, 1, 0, 0, 0) != 0:
        raise ProbeRejected("peer_privilege_unknown")


class PinnedArtifactTree:
    """Closed layout inspected through held directory FDs, including root parent."""

    def __init__(
        self,
        root: Path,
        layout: Mapping[str, tuple[int, bool, int]],
        expected_root: tuple[int, int],
        directory_identities: Mapping[str, tuple[int, int]],
        *,
        root_uid: int = 0,
    ) -> None:
        self.root = root
        self.layout = layout
        self.expected_root = expected_root
        self.directory_identities = directory_identities
        self.root_uid = root_uid
        self.fds: dict[str, int] = {}
        self.all_fds: list[int] = []
        self.links: list[tuple[int, str, tuple[int, ...]]] = []
        self.expected: dict[str, tuple[int, ...]] = {}
        self.parent_fd = -1

    def inspect(self) -> None:
        if self.fds or not self.root.is_absolute():
            raise ProbeRejected("artifact_root_unknown")
        fd = os.open("/", DIR_FLAGS)
        self.all_fds.append(fd)
        try:
            for part in self.root.parts[1:]:
                info = os.stat(part, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    raise ProbeRejected("artifact_root_unknown")
                parent_fd = fd
                fd = os.open(part, DIR_FLAGS, dir_fd=parent_fd)
                self.all_fds.append(fd)
                if stamp(os.fstat(fd))[:6] != stamp(info)[:6]:
                    raise ProbeRejected("artifact_root_unknown")
                self.links.append((parent_fd, part, stamp(info)[:6]))
                self.parent_fd = parent_fd
            root_info = os.fstat(fd)
            if (
                (root_info.st_dev, root_info.st_ino) != self.expected_root
                or root_info.st_uid != self.root_uid
                or root_info.st_gid != self.root_uid
                or stat.S_IMODE(root_info.st_mode) != 0o755
            ):
                raise ProbeRejected("artifact_root_unknown")
            self.fds[""] = fd
            self.expected[""] = stamp(root_info)
            pending = [""]
            while pending:
                parent = pending.pop()
                handle = self.fds[parent]
                children = {
                    p.rsplit("/", 1)[-1]
                    for p in self.layout
                    if p.rpartition("/")[0] == parent
                }
                names = os.listdir(handle)
                if set(names) != children or len(names) != len(children):
                    # No unknown child is stat'ed or traversed.
                    raise ProbeRejected("artifact_member_unknown")
                for name in sorted(names):
                    relative = parent + "/" + name if parent else name
                    uid, directory, mode = self.layout[relative]
                    info = os.stat(name, dir_fd=handle, follow_symlinks=False)
                    if (
                        info.st_dev != root_info.st_dev
                        or info.st_uid != uid
                        or info.st_gid != uid
                        or stat.S_IMODE(info.st_mode) != mode
                        or not (
                            stat.S_ISDIR(info.st_mode)
                            if directory
                            else stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                        )
                    ):
                        raise ProbeRejected("artifact_member_unknown")
                    self.expected[relative] = stamp(info)
                    if directory:
                        if (info.st_dev, info.st_ino) != self.directory_identities.get(
                            relative
                        ):
                            raise ProbeRejected("artifact_member_unknown")
                        nested = os.open(name, DIR_FLAGS, dir_fd=handle)
                        self.all_fds.append(nested)
                        if stamp(os.fstat(nested)) != stamp(info):
                            raise ProbeRejected("artifact_member_unknown")
                        self.fds[relative] = nested
                        pending.append(relative)
            if set(self.expected) != {"", *self.layout}:
                raise ProbeRejected("artifact_member_unknown")
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self) -> None:
        for link_parent, name, expected in self.links:
            if (
                stamp(os.stat(name, dir_fd=link_parent, follow_symlinks=False))[:6]
                != expected
            ):
                raise ProbeRejected("artifact_root_unknown")
        for relative, expected in self.expected.items():
            if relative:
                parent, _, name = relative.rpartition("/")
                info = os.stat(name, dir_fd=self.fds[parent], follow_symlinks=False)
            else:
                info = os.fstat(self.fds[""])
            if stamp(info) != expected:
                raise ProbeRejected("artifact_member_unknown")
        for parent, fd in self.fds.items():
            children = {
                p.rsplit("/", 1)[-1]
                for p in self.layout
                if p.rpartition("/")[0] == parent
            }
            if set(os.listdir(fd)) != children:
                raise ProbeRejected("artifact_member_unknown")

    def remove(self) -> int:
        self.verify()
        removed = 0
        for relative in sorted(self.layout, key=lambda p: (-p.count("/"), p)):
            parent, _, name = relative.rpartition("/")
            fd = self.fds[parent]
            expected = self.expected[relative]
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stamp(info)[:6] != expected[:6] or (
                not stat.S_ISDIR(info.st_mode) and stamp(info) != expected
            ):
                raise ProbeRejected("artifact_member_unknown")
            if stat.S_ISDIR(info.st_mode):
                os.rmdir(name, dir_fd=fd)
            else:
                os.unlink(name, dir_fd=fd)
            removed += 1
        observed = os.stat(self.root.name, dir_fd=self.parent_fd, follow_symlinks=False)
        if stamp(observed)[:6] != self.expected[""][:6]:
            raise ProbeRejected("artifact_root_unknown")
        os.rmdir(self.root.name, dir_fd=self.parent_fd)
        return removed + 1

    def close(self) -> None:
        for fd in reversed(self.all_fds):
            os.close(fd)
        self.all_fds.clear()
        self.fds.clear()


class HostOperations:
    def __init__(
        self, config: dict[str, Any], files: Mapping[str, bytes], cleanup: Any
    ) -> None:
        self.config = config
        self.files = files
        self.cleanup = cleanup
        self.installed_manifest_sha256 = digest(installed_manifest(config, files))
        self.case = Case()
        self.plan = self.case.plan
        self.commands = guardian.Commands(
            cast(Any, self.plan),
            {n: Path(t["path"]) for n, t in config["tools"].items()},
        )
        self.peer: subprocess.Popen[bytes] | None = None
        self.peer_fd: int | None = None
        self.client_pid: int | None = None
        self.anchor: Any = None
        self.created: dict[Path, tuple[int, int]] = {}
        self.worker_identities: dict[str, tuple[int, int]] = {}
        self.unit_created = False
        self.unit_attempted = False
        self.table_created = False
        self.create_uncertain = False
        self.binding: dict[str, Any] | None = None
        self.phase_reference: dict[str, Any] | None = None
        self.phase_references: list[dict[str, Any]] = []
        self.current_phase = "deny"
        self.counts = filtering.Counts()
        self.stall_start_counts = filtering.Counts()
        self.deadline = time.monotonic() + 180

    def systemctl(self, *args: str) -> bytes:
        allowed = {
            ("daemon-reload",),
            ("start", self.plan.unit),
            ("stop", "--no-block", self.plan.unit),
            ("reset-failed", self.plan.unit),
            (
                "show",
                self.plan.unit,
                "--property=Id,LoadState,ActiveState,SubState,MainPID,ControlGroup,FragmentPath,DropInPaths,User,Group",
                "--no-pager",
            ),
        }
        if args not in allowed:
            raise ProbeRejected("command_unknown")
        return self.commands._run((str(self.commands.tools["systemctl"]), *args))

    def nft(self, *args: str, data: bytes = b"") -> bytes:
        if args not in {
            ("-j", "list", "tables"),
            ("-j", "list", "table", "inet", self.plan.table),
            ("-f", "-"),
        }:
            raise ProbeRejected("command_unknown")
        return self.commands._run((str(self.commands.tools["nft"]), *args), data)

    def manager(self, *, absent: bool = False) -> dict[str, str]:
        raw = self.systemctl(
            "show",
            self.plan.unit,
            "--property=Id,LoadState,ActiveState,SubState,MainPID,ControlGroup,FragmentPath,DropInPaths,User,Group",
            "--no-pager",
        )
        try:
            items = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
            state = dict(items)
            if (
                len(items) != len(state)
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
                or state["Id"] != self.plan.unit
            ):
                raise ValueError
        except (ValueError, UnicodeError):
            raise ProbeRejected("unit_metadata_unknown") from None
        for p in (
            Path("/run/systemd/system") / self.plan.unit,
            Path("/run/systemd/system") / (self.plan.unit + ".d"),
            Path(str(self.case.unit_path) + ".d"),
        ):
            if os.path.lexists(p):
                raise ProbeRejected("unit_scope_unknown")
        if absent:
            if os.path.lexists(self.case.unit_path) or not exact(
                state,
                {
                    "Id": self.plan.unit,
                    "LoadState": "not-found",
                    "ActiveState": "inactive",
                    "SubState": "dead",
                    "MainPID": "0",
                    "ControlGroup": "",
                    "FragmentPath": "",
                    "DropInPaths": "",
                    "User": "",
                    "Group": "",
                },
            ):
                raise ProbeRejected("unit_not_absent")
        else:
            self.cleanup.protected(self.case.unit_path)
            if (
                self.cleanup.record(self.case.unit_path, uid=0, mode=0o644)
                != self.files["probe.service"]
                or any(
                    state[k] != v
                    for k, v in {
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

    def cg(self, *, absent: bool = False) -> Any:
        return cgroups.read_cgroup_state(cast(Any, self.plan), allow_absent=absent)

    def table_present(self) -> bool:
        try:
            raw = json.loads(self.nft("-j", "list", "tables"), object_pairs_hook=pairs)
            rows = raw["nftables"]
            if type(rows) is not list:
                raise ValueError
            found = False
            for row in rows:
                if type(row) is not dict or len(row) != 1:
                    raise ValueError
                if "metainfo" in row:
                    continue
                table = row["table"]
                if (
                    type(table) is not dict
                    or type(table.get("name")) is not str
                    or type(table.get("family")) is not str
                ):
                    raise ValueError
                if table["family"] == "inet" and table["name"] == self.plan.table:
                    if found:
                        raise ValueError
                    found = True
            return found
        except (ValueError, KeyError, TypeError):
            raise ProbeRejected("table_inventory_unknown") from None

    def preflight(self) -> None:
        if (
            os.geteuid() != 0
            or os.getegid() != 0
            or self.config["scope"] != SCOPE
            or self.config["run_id"] != RUN
            or self.config["host"] != host_context()
            or self.config["limits"] != LIMITS
        ):
            raise ProbeRejected("scope_unknown")
        installed_manifest(self.config, self.files)
        for value in self.config["tools"].values():
            p = Path(value["path"])
            self.cleanup.protected(p)
            if (
                digest(
                    self.cleanup.record(p, uid=0, mode=stat.S_IMODE(p.lstat().st_mode))
                )
                != value["sha256"]
            ):
                raise ProbeRejected("tool_changed")
        if str(Path(sys.executable).resolve()) != self.config["tools"]["python"][
            "path"
        ] or self.files["probe.service"].decode() != render_unit(
            self.case, self.config["tools"]["python"]["path"]
        ):
            raise ProbeRejected("tool_changed")
        for p in (self.case.code, self.case.runtime, self.case.ledger):
            if os.path.lexists(p):
                raise ProbeRejected("case_already_consumed")
        self.manager(absent=True)
        if self.cg(absent=True).exists or self.table_present():
            raise ProbeRejected("scope_already_present")
        for p in (
            self.case.code.parent,
            self.case.runtime.parent,
            self.case.unit_path.parent,
        ):
            self.cleanup.protected(p)

    def reserve(self) -> None:
        for p in (self.case.ledger.parent.parent, self.case.ledger.parent):
            if not os.path.lexists(p):
                p.mkdir(mode=0o755)
            self.cleanup.protected(p)
        self.anchor = guardian.claim_anchor(self.case.ledger, RUN)

    def install(self) -> None:
        for p in (self.case.code, self.case.runtime):
            self.cleanup.protected(p.parent)
            p.mkdir(mode=0o755)
            p.chmod(0o755)
            info = p.lstat()
            self.created[p] = (info.st_dev, info.st_ino)
        for p in (
            self.case.worker,
            self.case.worker / "client",
            self.case.worker / "peer",
        ):
            p.mkdir(mode=0o700)
            os.chown(p, 1000, 1000)
            info = p.lstat()
            self.worker_identities[str(p.relative_to(self.case.runtime))] = (
                info.st_dev,
                info.st_ino,
            )
        for name, raw in {
            **self.files,
            "manifest.json": installed_manifest(self.config, self.files),
        }.items():
            fd = os.open(
                self.case.code / name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o644,
            )
            try:
                os.fchmod(fd, 0o644)
                with os.fdopen(fd, "wb", closefd=False) as output:
                    output.write(raw)
                    output.flush()
                    os.fsync(fd)
            finally:
                os.close(fd)
        self.cleanup.protected(self.case.unit_path.parent)
        self.unit_attempted = True
        fd = os.open(
            self.case.unit_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
        )
        try:
            os.fchmod(fd, 0o644)
            with os.fdopen(fd, "wb", closefd=False) as output:
                output.write(self.files["probe.service"])
                output.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        self.unit_created = True
        self.systemctl("daemon-reload")
        self.verify_scope()

    def verify_scope(self) -> None:
        self.manager()
        for root, expected in self.created.items():
            self.cleanup.protected(root)
            info = root.lstat()
            if (info.st_dev, info.st_ino) != expected:
                raise ProbeRejected("root_changed")
        expected_files = {
            **self.files,
            "manifest.json": installed_manifest(self.config, self.files),
        }
        if set(os.listdir(self.case.code)) != set(expected_files):
            raise ProbeRejected("member_changed")
        for name, expected_raw in expected_files.items():
            if (
                self.cleanup.record(self.case.code / name, uid=0, mode=0o644)
                != expected_raw
            ):
                raise ProbeRejected("member_changed")

    def read_role(self, role: str, stage: str) -> dict[str, Any]:
        end = min(self.deadline, time.monotonic() + 12)
        while time.monotonic() < end:
            try:
                return validate_report(
                    read_role_metadata(
                        self.case.runtime,
                        role,
                        stage + ".json",
                        expected_root=self.created[self.case.runtime],
                        expected_directories=self.worker_identities,
                    ),
                    role=role,
                    stage=stage,
                )
            except FileNotFoundError:
                pass
            try:
                failure = read_role_metadata(
                    self.case.runtime,
                    role,
                    "failure.json",
                    expected_root=self.created[self.case.runtime],
                    expected_directories=self.worker_identities,
                )
            except FileNotFoundError:
                failure = None
            if failure is not None:
                raise ProbeRejected("role_failed")
            if self.peer is not None and self.peer.poll() not in {None, 0}:
                raise ProbeRejected("peer_failed")
            time.sleep(0.02)
        raise ProbeRejected("role_deadline_unknown")

    def start_peer(self) -> dict[str, object]:
        if self.peer is not None:
            raise ProbeRejected("retry_forbidden")
        self.peer = subprocess.Popen(
            [
                self.config["tools"]["python"]["path"],
                "-I",
                "-S",
                "-B",
                str(self.case.code / "worker-entry.py"),
                "peer",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=self.case.worker / "peer",
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
                "HOME": str(self.case.worker / "peer"),
                "TMPDIR": str(self.case.worker / "peer"),
            },
            user=1000,
            group=1000,
            extra_groups=(),
            preexec_fn=peer_limits,
            start_new_session=True,
        )
        self.peer_fd = os.pidfd_open(self.peer.pid)
        row = self.read_role("peer", "ready")["metadata"]
        if row.get("pid") != self.peer.pid or not exact(
            {k: row[k] for k in row if k != "pid"},
            {
                "uid": 1000,
                "gid": 1000,
                "core_zero": True,
                "no_new_privs": True,
                "effective_permitted_inheritable_ambient_empty": True,
            },
        ):
            raise ProbeRejected("peer_identity_unknown")
        return {
            "uid": 1000,
            "gid": 1000,
            "outside_target_cgroup": True,
            "core_zero": True,
            "no_new_privs": True,
            "integrity": "complete",
        }

    def start_client(self) -> dict[str, object]:
        if self.client_pid is not None:
            raise ProbeRejected("retry_forbidden")
        self.systemctl("start", self.plan.unit)
        row = self.read_role("client", "ready")["metadata"]
        state = self.commands.unit_state()
        group = self.cg()
        if (
            row.get("pid") != state.pid
            or group.pids != {state.pid}
            or self.peer is None
            or self.peer.pid in group.pids
            or not exact(
                {k: row[k] for k in row if k != "pid"},
                {
                    "uid": 1000,
                    "gid": 1000,
                    "core_zero": True,
                    "no_new_privs": True,
                    "effective_permitted_inheritable_ambient_empty": True,
                },
            )
        ):
            raise ProbeRejected("client_identity_unknown")
        self.client_pid = state.pid
        return {
            "uid": 1000,
            "gid": 1000,
            "inside_target_cgroup": True,
            "peer_outside_target_cgroup": True,
            "core_zero": True,
            "no_new_privs": True,
            "integrity": "complete",
        }

    def raw_table(self) -> bytes:
        return self.nft("-j", "list", "table", "inet", self.plan.table)

    def check_cgroup_identity(self, *, allow_absent: bool = False) -> None:
        if self.binding is None:
            raise ProbeRejected("filter_binding_unknown")
        state = self.cg(absent=allow_absent)
        if not state.exists:
            if allow_absent:
                return
            raise ProbeRejected("client_identity_unknown")
        if guardian.read_cgroup_identity(cast(Any, self.plan)) != (
            self.binding["cgroup_device"],
            self.binding["cgroup_inode"],
        ):
            raise ProbeRejected("client_identity_unknown")

    def create_filter(self) -> dict[str, object]:
        self.verify_scope()
        identity = guardian.read_cgroup_identity(cast(Any, self.plan))
        if self.table_present():
            raise ProbeRejected("table_already_present")
        self.create_uncertain = True
        self.nft("-f", "-", data=filtering.render_create(self.plan).encode())
        self.table_created = True
        self.create_uncertain = False
        raw = self.raw_table()
        self.binding = filtering.make_binding(
            self.plan, raw, identity, host_context=self.config["host"]
        )
        self.phase_reference = self.binding["initial_reference"]
        self.phase_references = [self.phase_reference]
        self.counts = filtering.verify_state(
            self.plan,
            raw,
            phase="deny",
            host_context=self.config["host"],
            binding=self.binding,
            phase_reference=self.phase_reference,
            previous_counts=filtering.Counts(),
        )
        return self.observation("created_deny", raw)

    def observation(self, label: str, raw: bytes) -> dict[str, object]:
        return {
            "stage": label,
            "phase": self.current_phase,
            "binding": self.binding,
            "phase_reference": self.phase_reference,
            "counts": self.counts.to_dict(),
            "kernel_state": json.loads(raw, object_pairs_hook=pairs),
        }

    def switch(self, phase: str) -> dict[str, object]:
        if type(phase) is not str or phase not in {"allow", "stall"}:
            raise ProbeRejected("gate_unknown")
        if self.binding is None or self.phase_reference is None:
            raise ProbeRejected("filter_binding_unknown")
        self.verify_scope()
        self.check_cgroup_identity()
        if (
            self.client_pid is None
            or self.client_pid not in self.cg().pids
            or self.peer is None
            or self.peer.pid in self.cg().pids
        ):
            raise ProbeRejected("client_identity_unknown")
        self.nft(
            "-f",
            "-",
            data=(
                filtering.render_allow(self.plan)
                if phase == "allow"
                else filtering.render_stall(self.plan)
            ).encode(),
        )
        raw = self.raw_table()
        reference = filtering.capture_phase(
            self.plan,
            raw,
            phase=phase,
            host_context=self.config["host"],
            binding=self.binding,
            previous_reference=self.phase_reference,
            previous_counts=self.counts,
        )
        self.phase_reference = reference
        self.phase_references.append(reference)
        self.current_phase = phase
        self.counts = filtering.verify_state(
            self.plan,
            raw,
            phase=phase,
            host_context=self.config["host"],
            binding=self.binding,
            phase_reference=reference,
            previous_counts=self.counts,
        )
        if phase == "stall":
            self.stall_start_counts = self.counts
        return self.observation("transaction_" + phase, raw)

    def gate(self, name: str, extra: dict[str, object] | None = None) -> str:
        if name not in {"baseline", "stall", "resume", "close", "exit"}:
            raise ProbeRejected("gate_unknown")
        expected_extra = {
            "baseline": set(),
            "stall": {"negative_end_monotonic_ns", "negative_not_before_monotonic_ns"},
            "resume": {"allow_intent_monotonic_ns"},
            "close": set(),
            "exit": set(),
        }[name]
        if extra is not None and (
            type(extra) is not dict or set(extra) != expected_extra
        ):
            raise ProbeRejected("gate_unknown")
        if extra is None and expected_extra:
            raise ProbeRejected("gate_unknown")
        if any(type(v) is not int or v <= 0 for v in (extra or {}).values()):
            raise ProbeRejected("gate_unknown")
        value = {
            "scope": SCOPE,
            "run_id": RUN,
            "stage": name,
            "phase_reference": self.phase_reference,
            **(extra or {}),
        }
        publish(self.case.runtime / ("gate-" + name + ".json"), value, mode=0o644)
        return digest(encoded(value))

    def reports(self, stage: str) -> dict[str, Any]:
        reports = {role: self.read_role(role, stage) for role in ("client", "peer")}
        if stage == "finished":
            for role, row in reports.items():
                if not exact(
                    row["metadata"],
                    {
                        "all_sockets_closed": True,
                        "send_entries": 2 if role == "client" else 8,
                        "connect_entries": 1,
                        "accept_entries": 0 if role == "client" else 2,
                    },
                ):
                    raise ProbeRejected("finished_unknown")
            if self.peer is None or self.peer.wait(timeout=5) != 0:
                raise ProbeRejected("peer_failed")
        return reports

    def snapshot(self, label: str) -> dict[str, object]:
        if self.binding is None or self.phase_reference is None:
            raise ProbeRejected("filter_binding_unknown")
        self.check_cgroup_identity()
        raw = self.raw_table()
        self.counts = filtering.verify_state(
            self.plan,
            raw,
            phase=self.current_phase,
            host_context=self.config["host"],
            binding=self.binding,
            phase_reference=self.phase_reference,
            previous_counts=self.counts,
        )
        if label == "baseline_complete" and (
            self.counts.allowed_in == 0 or self.counts.allowed_out == 0
        ):
            raise ProbeRejected("positive_direction_missing")
        if label == "negative_complete" and (
            self.counts.dropped_in <= self.stall_start_counts.dropped_in
            or self.counts.dropped_out <= self.stall_start_counts.dropped_out
        ):
            raise ProbeRejected("negative_direction_missing")
        return self.observation(label, raw)

    def exit(self) -> dict[str, object]:
        if self.binding is None:
            raise ProbeRejected("filter_binding_unknown")
        filtering.verify_references(
            self.plan,
            self.phase_references,
            host_context=self.config["host"],
            binding=self.binding,
        )
        end = min(self.deadline, time.monotonic() + 12)
        while time.monotonic() < end:
            if not self.cg(absent=True).pids:
                raw = self.commands._run(
                    (
                        str(self.commands.tools["systemctl"]),
                        "show",
                        self.plan.unit,
                        "--property=ActiveState,SubState,Result,ExecMainCode,ExecMainStatus,MainPID,ControlGroup",
                        "--no-pager",
                    )
                )
                try:
                    rows = [
                        line.split("=", 1) for line in raw.decode("ascii").splitlines()
                    ]
                    state = dict(rows)
                    if len(rows) != len(state) or set(state) != {
                        "ActiveState",
                        "SubState",
                        "Result",
                        "ExecMainCode",
                        "ExecMainStatus",
                        "MainPID",
                        "ControlGroup",
                    }:
                        raise ValueError
                except (ValueError, UnicodeError):
                    raise ProbeRejected("worker_exit_unknown") from None
                if (
                    state["ActiveState"] == "active"
                    and state["SubState"] == "exited"
                    and state["Result"] == "success"
                    and state["ExecMainCode"] == "1"
                    and state["ExecMainStatus"] == "0"
                    and state["MainPID"] == "0"
                    and state["ControlGroup"] in {"", self.plan.cgroup}
                ):
                    return {
                        "strict_controller_exit": True,
                        "cgroup_empty": True,
                        "peer_exit_zero": True,
                    }
                if (
                    state["ActiveState"] in {"failed", "inactive"}
                    or state["SubState"] == "exited"
                ):
                    raise ProbeRejected("worker_exit_unknown")
            time.sleep(0.02)
        raise ProbeRejected("worker_exit_unknown")

    def restore(self) -> dict[str, object]:
        if self.unit_created:
            self.manager()
            self.systemctl("stop", "--no-block", self.plan.unit)
            end = time.monotonic() + 15
            while time.monotonic() < end:
                state = self.manager()
                if (
                    not self.cg(absent=True).pids
                    and state["MainPID"] == "0"
                    and (state["ActiveState"], state["SubState"])
                    in {("inactive", "dead"), ("failed", "failed")}
                ):
                    break
                time.sleep(0.02)
            else:
                raise ProbeRejected("stop_unknown")
        if self.cg(absent=True).pids:
            raise ProbeRejected("cgroup_not_empty")
        self.close_peer()
        if self.table_present():
            if (
                not self.table_created
                or self.create_uncertain
                or self.binding is None
                or self.phase_reference is None
            ):
                raise ProbeRejected("filter_ownership_unknown")
            self.check_cgroup_identity(allow_absent=True)
            raw = self.raw_table()
            filtering.verify_quiescent(
                self.plan,
                raw,
                phase=self.current_phase,
                host_context=self.config["host"],
                binding=self.binding,
                phase_reference=self.phase_reference,
                previous_counts=self.counts,
            )
            self.nft("-f", "-", data=filtering.render_delete(self.plan).encode())
            self.table_created = False
        if self.table_present():
            raise ProbeRejected("table_not_absent")
        if self.unit_created:
            state = self.manager()
            if state["ActiveState"] == "failed":
                self.systemctl("reset-failed", self.plan.unit)
            self.manager()
            self.case.unit_path.unlink()
            self.systemctl("daemon-reload")
        self.manager(absent=True)
        if self.cg(absent=True).pids:
            raise ProbeRejected("cgroup_not_empty")
        return {
            "unit_absent": True,
            "table_absent": True,
            "cgroup_empty": True,
            "peer_reaped": True,
            "ledger_retained": True,
        }

    def mountinfo(self) -> bytes:
        with Path("/proc/self/mountinfo").open("rb") as source:
            return source.read(1048577)

    def remove_artifacts(self) -> dict[str, object]:
        self.manager(absent=True)
        if (
            self.table_present()
            or self.cg(absent=True).pids
            or (self.peer is not None and self.peer.poll() is None)
        ):
            raise ProbeRejected("artifacts_not_quiescent")
        self.cleanup.check_mounts(
            (self.case.code, self.case.runtime),
            self.cleanup.mount_points(self.mountinfo()),
        )

        runtime_layout = {
            "worker": (1000, True, 0o700),
            "worker/client": (1000, True, 0o700),
            "worker/peer": (1000, True, 0o700),
            **{
                "gate-" + name + ".json": (0, False, 0o644)
                for name in ("baseline", "stall", "resume", "close", "exit")
            },
            **{
                f"worker/{role}/{stage}.json": (1000, False, 0o600)
                for role in ("client", "peer")
                for stage in ("ready", "baseline", "negative", "resumed", "finished")
            },
        }
        code_layout = {
            name: (0, False, 0o644) for name in {*self.files, "manifest.json"}
        }
        trees = [
            PinnedArtifactTree(
                self.case.runtime,
                runtime_layout,
                self.created[self.case.runtime],
                self.worker_identities,
            ),
            PinnedArtifactTree(
                self.case.code, code_layout, self.created[self.case.code], {}
            ),
        ]
        try:
            for tree in trees:
                tree.inspect()
            # No deletion until both closed trees passed and all pins rechecked.
            for tree in trees:
                tree.verify()
            for tree in trees:
                tree.remove()
        finally:
            for tree in trees:
                tree.close()
        return {"code_runtime_removed": True, "ledger_retained": True}

    def close_peer(self) -> None:
        if self.peer is not None and self.peer.poll() is None:
            if self.peer_fd is None:
                raise ProbeRejected("peer_identity_unknown")
            signal.pidfd_send_signal(self.peer_fd, signal.SIGTERM)
            try:
                self.peer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                signal.pidfd_send_signal(self.peer_fd, signal.SIGKILL)
                self.peer.wait(timeout=2)
        if self.peer_fd is not None:
            os.close(self.peer_fd)
            self.peer_fd = None

    def failure_reports(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for role in ("client", "peer"):
            try:
                value = read_role_metadata(
                    self.case.runtime,
                    role,
                    "failure.json",
                    expected_root=self.created[self.case.runtime],
                    expected_directories=self.worker_identities,
                )
            except FileNotFoundError:
                continue
            if (
                set(value)
                != {
                    "scope",
                    "run_id",
                    "role",
                    "integrity",
                    "failure_stage",
                    "failure_reason",
                }
                or value["scope"] != SCOPE
                or value["run_id"] != RUN
                or value["role"] != role
                or value["integrity"] != "unknown"
                or value["failure_stage"]
                not in {
                    "ready",
                    "baseline",
                    "stall",
                    "resume_pending",
                    "resume",
                    "closing",
                }
                or value["failure_reason"]
                not in PROBE_REASONS | {"duplex_operation_unknown"}
            ):
                raise ProbeRejected("metadata_unknown")
            result[role] = value
        return result

    def write_ledger(self, value: object) -> None:
        if self.anchor is None:
            raise ProbeRejected("ledger_unknown")
        before = os.fstat(self.anchor.fileno())
        linked = self.case.ledger.lstat()
        if (
            (before.st_dev, before.st_ino) != (linked.st_dev, linked.st_ino)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
        ):
            raise ProbeRejected("ledger_unknown")
        self.anchor.seek(0)
        self.anchor.truncate()
        self.anchor.write(encoded(value).decode())
        self.anchor.flush()
        os.fsync(self.anchor.fileno())


def owner_main(config: dict[str, Any], files: Mapping[str, bytes], cleanup: Any) -> int:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    ops = HostOperations(config, files, cleanup)
    result = run_owner(ops)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "observed_expected_and_restored" else 1
