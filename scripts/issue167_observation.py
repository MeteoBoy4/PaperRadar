"""Issue 167 offline prototypes; never connected to product admission or credentials."""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import os
import secrets
import stat
import struct
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

# Linux inotify masks. Names are parsed only to skip their bytes, never returned.
_MODIFY = 0x2
_ATTRIB = 0x4
_CLOSE_WRITE = 0x8
_MOVED_FROM = 0x40
_MOVED_TO = 0x80
_CREATE = 0x100
_DELETE = 0x200
_DELETE_SELF = 0x400
_MOVE_SELF = 0x800
_UNMOUNT = 0x2000
_OVERFLOW = 0x4000
_IGNORED = 0x8000
_ISDIR = 0x40000000
_MASK = (
    _MODIFY
    | _ATTRIB
    | _CLOSE_WRITE
    | _MOVED_FROM
    | _MOVED_TO
    | _CREATE
    | _DELETE
    | _DELETE_SELF
    | _MOVE_SELF
    | _UNMOUNT
)
_HEADER = struct.Struct("iIII")


@dataclass(frozen=True)
class FileReceipt:
    history: str
    mutation_events: int
    terminal_regular_files: int | None
    terminal_other_entries: int | None
    terminal_members: tuple[tuple[str, str], ...] | None
    terminal_status: str
    directory_deleted: bool
    reasons: tuple[str, ...]
    cleanup_reasons: tuple[str, ...]


class FileObserver:
    """Observe an existing synthetic tree, without reading any file contents.

    New/moved directories invalidate coverage: adding watches after creation has
    a race. This prototype refuses that gap rather than claiming recursive proof.
    The caller must supply an honest process/reaping window; this is not an
    authority proving cgroup completeness, and only watches the selected tree.
    """

    def __init__(self, root: Path) -> None:
        if not stat.S_ISDIR(root.lstat().st_mode):
            raise ValueError("observer_root_not_directory")
        self.root = root
        self.reasons: set[str] = set()
        self._cleanup_reasons: set[str] = set()
        self._history_snapshot: tuple[int, tuple[str, ...]] | None = None
        self.mutations = 0
        self.started = False
        self.reaped = False
        self.closed = False
        # Random per observation, never persisted; unrelated to any credential.
        self._path_key = secrets.token_bytes(32)
        self._terminal: tuple[int, int, tuple[tuple[str, str], ...]] | None = None
        self._terminal_reason = "terminal_unknown"
        libc = ctypes.CDLL(None, use_errno=True)
        self._libc = libc
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError("observer_init_failed")
        try:
            self._watch(root)
            for parent, dirs, files in os.walk(root, followlinks=False):
                for name in dirs + files:
                    candidate = Path(parent) / name
                    mode = candidate.lstat().st_mode
                    if stat.S_ISLNK(mode):
                        self._problem("initial_symlink")
                    elif stat.S_ISDIR(mode):
                        self._watch(candidate)
        except BaseException:
            self.close()
            raise

    def _problem(self, reason: str) -> None:
        target = (
            self.reasons if self._history_snapshot is None else self._cleanup_reasons
        )
        target.add(reason)

    def _watch(self, path: Path) -> None:
        if self._libc.inotify_add_watch(self.fd, os.fsencode(path), _MASK) < 0:
            raise OSError("observer_watch_failed")

    def launch_started(self) -> None:
        self.drain()
        if self.mutations or self.reasons or self.started:
            self._problem("unclean_start_window")
        self.started = True

    def descendants_reaped(self) -> None:
        self.reaped = True

    def ingest(self, payload: bytes) -> None:
        """Separate decoder seam for synthetic overflow/truncation tests."""
        offset = 0
        while offset < len(payload):
            if len(payload) - offset < _HEADER.size:
                self._problem("truncated_event")
                return
            _, mask, _, length = _HEADER.unpack_from(payload, offset)
            offset += _HEADER.size + length
            if offset > len(payload):
                self._problem("truncated_event")
                return
            if mask & (_OVERFLOW | _UNMOUNT | _IGNORED | _MOVE_SELF):
                self._problem("event_coverage_lost")
            if mask & _ISDIR and mask & (_CREATE | _MOVED_TO):
                self._problem("new_directory_race")
            if mask & (_MODIFY | _ATTRIB | _CLOSE_WRITE | _CREATE | _MOVED_TO):
                self.mutations += 1

    def drain(self) -> None:
        if self.closed:
            self._problem("observer_closed")
            return
        while True:
            try:
                payload = os.read(self.fd, 65536)
            except BlockingIOError:
                return
            except OSError:
                self._problem("observer_read_failed")
                return
            if not payload:
                self._problem("observer_eof")
                return
            self.ingest(payload)

    def snapshot_terminal(self) -> None:
        """Capture after reaping, before cleanup; retain after deletion."""
        self.drain()
        if self._history_snapshot is not None:
            raise ValueError("terminal_snapshot_already_taken")
        if not self.started or not self.reaped:
            self._terminal_reason = "terminal_window_incomplete"
            return
        # Trusted synthetic driver declares all writers gone. Freeze the ended
        # execution window before cleanup can produce normal IN_IGNORED events.
        self._history_snapshot = self.mutations, tuple(sorted(self.reasons))
        regular = other = 0
        members: list[tuple[str, str]] = []
        try:
            if not stat.S_ISDIR(self.root.lstat().st_mode):
                self._terminal_reason = "terminal_root_replaced"
                return
            for parent, dirs, files in os.walk(
                self.root, followlinks=False, onerror=self._scan_error
            ):
                for name in dirs + files:
                    candidate = Path(parent) / name
                    mode = candidate.lstat().st_mode
                    if stat.S_ISREG(mode):
                        kind = "regular"
                        regular += 1
                    elif stat.S_ISDIR(mode):
                        kind = "directory"
                        other += 1
                    else:
                        kind = "other"
                        other += 1
                    relative = os.fsencode(candidate.relative_to(self.root))
                    identity = hmac.new(
                        self._path_key, relative, hashlib.sha256
                    ).hexdigest()
                    members.append((kind, identity))
        except OSError:
            self._terminal_reason = "terminal_scan_failed"
            return
        self._terminal = regular, other, tuple(sorted(members))
        self._terminal_reason = "synthetic_snapshot"

    def receipt(self) -> FileReceipt:
        self.drain()
        if not self.started or not self.reaped:
            self._problem("incomplete_process_window")
        try:
            self.root.lstat()
            deleted = False
        except FileNotFoundError:
            deleted = True
        except OSError:
            self._problem("directory_check_failed")
            deleted = False
        mutations, history_reasons = (
            self._history_snapshot
            if self._history_snapshot is not None
            else (self.mutations, tuple(sorted(self.reasons)))
        )
        history = "observed_mutation" if mutations else "zero_observed"
        if history_reasons:
            history = "unknown"
        regular, other, members = (
            self._terminal if self._terminal is not None else (None, None, None)
        )
        return FileReceipt(
            history,
            mutations,
            regular,
            other,
            members,
            self._terminal_reason,
            deleted,
            history_reasons,
            tuple(sorted(self._cleanup_reasons)),
        )

    def _scan_error(self, error: OSError) -> None:
        raise OSError("terminal_scan_failed")

    def close(self) -> None:
        if not self.closed:
            os.close(self.fd)
            self.closed = True

    def __enter__(self) -> FileObserver:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class Layer(StrEnum):
    PROMPT = "prompt"
    CLI = "cli"
    TLS_CONNECTION = "tls_connection"
    PACKET = "packet"
    MODEL_HTTP = "model_http"
    MODEL_WS_CONNECT = "model_ws_connect"
    MODEL_WS_CREATE = "model_ws_create"
    AUTH_REFRESH_HTTP = "auth_refresh_http"


class Phase(StrEnum):
    FOREGROUND = "foreground"
    WARMUP = "warmup"
    RETRY = "retry"


@dataclass(frozen=True)
class RequestEvent:
    layer: Layer
    sequence: int
    phase: Phase


class RequestReceipt(TypedDict):
    status: str
    counts: dict[str, int]
    phases: dict[str, int]
    reasons: tuple[str, ...]


class RequestLedger:
    """Synthetic peer instrumentation, not a TLS decoder or Pi hook.

    An independent peer's expected counts detect losses. Without that reference,
    unseen requests cannot be inferred. No URL, headers, body or token is accepted.
    """

    def __init__(self, available: frozenset[Layer]) -> None:
        self.available = available
        self.events: set[RequestEvent] = set()
        self.seen: set[tuple[Layer, int]] = set()
        self.reasons: set[str] = set()

    def record(self, event: RequestEvent) -> None:
        if (
            type(event.layer) is not Layer
            or type(event.phase) is not Phase
            or type(event.sequence) is not int
            or event.sequence < 1
        ):
            self.reasons.add("invalid_event")
            return
        key = event.layer, event.sequence
        if key in self.seen:
            self.reasons.add("duplicate_event")
            return
        self.seen.add(key)
        self.events.add(event)

    def observation_failed(self) -> None:
        self.reasons.add("observer_failed")

    def reconcile(self, expected: dict[Layer, int]) -> RequestReceipt:
        counts = Counter(event.layer for event in self.events)
        phases = Counter((event.layer, event.phase) for event in self.events)
        reasons = set(self.reasons)
        for layer in Layer:
            if layer not in self.available:
                reasons.add("layer_unobservable")
            if layer not in expected:
                reasons.add("independent_reference_missing")
            elif type(expected[layer]) is not int or expected[layer] < 0:
                reasons.add("invalid_reference")
            elif counts[layer] != expected[layer]:
                reasons.add("independent_count_mismatch")
            sequences = sorted(n for item, n in self.seen if item == layer)
            if sequences != list(range(1, len(sequences) + 1)):
                reasons.add("sequence_gap")
        return {
            "status": "unknown" if reasons else "synthetic_reconciled",
            "counts": {layer.value: counts[layer] for layer in self.available},
            "phases": {
                f"{layer.value}:{phase.value}": phases[layer, phase]
                for layer in self.available
                for phase in Phase
            },
            "reasons": tuple(sorted(reasons)),
        }
