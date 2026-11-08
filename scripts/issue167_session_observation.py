"""S observer: complete assessed session guards, unassessed cache interiors.

Only the parent-created public control-settings JSON is read. Credential and
cache bodies are never read. Cache paths are a fixed-source classification, not
a content-safety assertion. Event counts are lower bounds; the full history of
compile-cache/lock interiors is never claimed.
"""

from __future__ import annotations

import ctypes
import json
import os
import stat
import struct
from collections import Counter
from contextlib import ExitStack, suppress
from pathlib import Path
from typing import cast

from scripts.issue167_fork_observation import CgroupReader, Membership

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
_MUTATION = _MODIFY | _ATTRIB | _CLOSE_WRITE | _CREATE | _DELETE
_MASK = _MUTATION | _MOVED_FROM | _MOVED_TO | _DELETE_SELF | _MOVE_SELF | _UNMOUNT
_HEADER = struct.Struct("iIII")
_CATEGORIES = (
    "baseline",
    "auth_store",
    "model_store",
    "store_lock",
    "compile_cache",
    "session",
    "unknown",
)
_STORES = {"agent/auth.json": "auth_store", "agent/models-store.json": "model_store"}
_LOCKS = {
    "agent/auth.json.lock",
    "agent/models-store.json.lock",
    "agent/settings.json.lock",
}
_BASE_DIRS = {"home", "tmp", "agent"}
_SETTING = "agent/settings.json"
_CACHE = "tmp/node-compile-cache"
MAX_ENTRIES = 100000
MAX_EVENTS = 100000
_PUBLIC_SETTINGS = {
    "cacheWarming": "off",
    "compaction": {"enabled": False},
    "defaultProjectTrust": "never",
    "enableInstallTelemetry": False,
    "retry": {"enabled": False, "provider": {"maxRetries": 0}},
}
_NON_SESSION_EVENTS = (
    "auth_store",
    "model_store",
    "store_lock",
    "compile_cache",
    "control_settings",
)


class SessionObservationRejected(ValueError):
    """Closed reasons only, without names, paths, contents or OS exception text."""


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_uid,
        info.st_gid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _settings_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_uid,
        info.st_gid,
    )


def _settings_canonical(raw: bytes) -> bytes:
    def unique(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def invalid_constant(_value: str) -> object:
        raise ValueError

    if type(raw) is not bytes or len(raw) > 16384:
        raise ValueError
    value = json.loads(
        raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant
    )
    if type(value) is not dict:
        raise ValueError
    # Canonical serialization retains bool/int/float distinctions; dict equality
    # would let False == 0 and silently weaken the fixed public controls.
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _inventory() -> dict[str, dict[str, int]]:
    return {key: {"regular": 0, "directory": 0, "other": 0} for key in _CATEGORIES}


def missing_receipt(reader: CgroupReader) -> dict[str, object]:
    return {
        "scope": "classified_session_observation",
        "run_id": reader.plan.run_id,
        "source": reader.source,
        "event_source": "unknown",
        "result": "unknown",
        "session_history": "unknown",
        "session_mutation_events": 0,
        "session_integrity": "unknown",
        "guard_integrity": "unknown",
        "unknown_mutation_events": 0,
        "settings_semantics": False,
        "known_non_session_history": "not_assessed",
        "non_session_event_lower_bounds": {key: 0 for key in _NON_SESSION_EVENTS},
        "event_count_semantics": "observed_inotify_records_lower_bound_not_write_count",
        "terminal_status": "unknown",
        "terminal_inventory": None,
        "terminal_integrity": "unknown",
        "directory_deleted": False,
        "cleanup_integrity": "unknown",
        "post_terminal_write_events": 0,
        "reasons": ["complete_lifecycle_missing"],
    }


class ClassifiedSessionObservation:
    """Pre-arm fixed guards only; never promise recursive cache-event coverage.

    Every path outside the fixed non-session boundaries is assessed at a guard
    ancestor. Creating a session/unknown directory already violates the zero-
    write condition, so no late-added recursive watch is used as proof. Cache
    interiors are explicitly unassessed from the beginning; terminal enumeration
    still includes them and rejects aliases/special or unknown entries.
    """

    def __init__(
        self,
        root: Path,
        reader: CgroupReader,
        *,
        expected_settings: bytes | None = None,
    ) -> None:
        if os.getuid() == 0 or os.geteuid() == 0:
            raise SessionObservationRejected("ordinary_observer_required")
        if expected_settings is None:
            raise SessionObservationRejected("public_settings_reference_missing")
        try:
            self._reference = _settings_canonical(expected_settings)
            known = json.dumps(
                _PUBLIC_SETTINGS, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
            if self._reference != known:
                raise ValueError
        except (ValueError, UnicodeError, RecursionError, OverflowError):
            raise SessionObservationRejected(
                "public_settings_reference_unknown"
            ) from None
        self.root, self.reader = root, reader
        self.fd = -1
        self._paths: dict[Path, int] = {}
        self._watches: dict[int, tuple[Path, bool]] = {}
        self._anchors: dict[Path, tuple[int, int]] = {}
        self._settings: tuple[int, ...] | None = None
        self._settings_semantics = False
        self._identity: tuple[int, int] | None = None
        self._started = self._sealed = self._deleted = self._closed = False
        self._delete_authorized = False
        self._self_deleted: set[int] = set()
        self._events = 0
        self._reasons: set[str] = set()
        self._guard_reasons: set[str] = set()
        self._cleanup_reasons: set[str] = set()
        self._counts: Counter[str] = Counter()
        self._session = self._unknown = self._post = 0
        self._terminal: dict[str, dict[str, int]] | None = None
        self._terminal_ok = False
        self._libc = ctypes.CDLL(None, use_errno=True)
        try:
            self._initial_baseline()
            self.fd = self._libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
            if self.fd < 0:
                raise OSError
            for path in (
                root,
                *(root / name for name in sorted(_BASE_DIRS)),
                root / _SETTING,
            ):
                info = path.lstat()
                descriptor = self._libc.inotify_add_watch(
                    self.fd, os.fsencode(path), _MASK
                )
                if descriptor < 0 or descriptor in self._watches:
                    raise OSError
                self._paths[path] = descriptor
                self._watches[descriptor] = path, stat.S_ISREG(info.st_mode)
                self._anchors[path] = info.st_dev, info.st_ino
            self._settings = _settings_identity((root / _SETTING).lstat())
            self._initial_baseline()
            self._verify_settings()
            if not self._settings_semantics:
                raise ValueError
        except (OSError, ValueError):
            self.close()
            raise SessionObservationRejected("session_observer_unavailable") from None

    def _initial_baseline(self) -> None:
        if (
            self.root.is_symlink()
            or not self.root.is_dir()
            or self.root.lstat().st_uid != os.getuid()
        ):
            raise ValueError
        expected = {*_BASE_DIRS, _SETTING}
        actual: set[str] = set()
        for parent, dirs, files in os.walk(self.root, followlinks=False):
            for name in dirs + files:
                p = Path(parent) / name
                relative = p.relative_to(self.root).as_posix()
                info = p.lstat()
                if relative not in expected or info.st_uid != os.getuid():
                    raise ValueError
                if relative in _BASE_DIRS:
                    if not stat.S_ISDIR(info.st_mode):
                        raise ValueError
                elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError
                actual.add(relative)
        if actual != expected:
            raise ValueError

    def _problem(self, reason: str, *, guard: bool = False) -> None:
        self._reasons.add(reason)
        if guard:
            self._guard_reasons.add(reason)
        if self._sealed:
            self._cleanup_reasons.add(reason)

    def _gate(self) -> Membership:
        try:
            state = self.reader.sample()
            if state.pids != {self.reader.controller_pid}:
                raise SessionObservationRejected("writers_not_quiescent")
            if self._identity is not None and self._identity != state.identity:
                raise SessionObservationRejected("cgroup_identity_unknown")
            return state
        except Exception as error:
            reason = (
                error.args[0]
                if isinstance(error, SessionObservationRejected)
                else "cgroup_read_unknown"
            )
            self._problem(cast(str, reason), guard=True)
            raise SessionObservationRejected(cast(str, reason)) from None

    def _check_anchors(self) -> None:
        try:
            for path, identity in self._anchors.items():
                info = path.lstat()
                if (info.st_dev, info.st_ino) != identity or stat.S_ISLNK(info.st_mode):
                    raise OSError
            if self._settings != _settings_identity((self.root / _SETTING).lstat()):
                self._problem("baseline_changed", guard=True)
        except OSError:
            self._problem("assessed_anchor_changed", guard=True)
        self._verify_settings()

    def _verify_settings(self) -> None:
        """Check this public file at boundaries, never claim per-write body history."""
        self._settings_semantics = False
        if self._guard_reasons:
            return
        try:
            directory_flags = (
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            with ExitStack() as handles:
                root_fd = os.open(self.root, directory_flags)
                handles.callback(os.close, root_fd)
                root_info = os.fstat(root_fd)
                if (root_info.st_dev, root_info.st_ino) != self._anchors[self.root]:
                    raise ValueError
                agent_fd = os.open("agent", directory_flags, dir_fd=root_fd)
                handles.callback(os.close, agent_fd)
                agent_info = os.fstat(agent_fd)
                if (agent_info.st_dev, agent_info.st_ino) != self._anchors[
                    self.root / "agent"
                ]:
                    raise ValueError
                fd = os.open(
                    "settings.json",
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=agent_fd,
                )
                source = handles.enter_context(os.fdopen(fd, "rb"))
                before = os.fstat(source.fileno())
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_uid != os.getuid()
                    or _settings_identity(before) != self._settings
                ):
                    raise ValueError
                raw = source.read(16385)
                if _stamp(before) != _stamp(os.fstat(source.fileno())):
                    raise ValueError
            if _settings_canonical(raw) != self._reference:
                raise ValueError
            self._settings_semantics = True
        except (OSError, ValueError, UnicodeError, RecursionError, OverflowError):
            self._problem("public_settings_semantics_unknown", guard=True)

    def start(self) -> None:
        if self._started or self._closed:
            self._problem("window_sequence_unknown", guard=True)
            raise SessionObservationRejected("window_sequence_unknown")
        self._identity = self._gate().identity
        self.drain()
        self._check_anchors()
        if self._counts or self._session or self._unknown or self._reasons:
            self._problem("unclean_start_window", guard=True)
            raise SessionObservationRejected("session_observation_unknown")
        self._started = True

    @staticmethod
    def _category(relative: str) -> str:
        if relative in _BASE_DIRS or relative == _SETTING or relative == "":
            return "baseline"
        if relative in _STORES:
            return _STORES[relative]
        if relative in _LOCKS:
            return "store_lock"
        if relative == _CACHE or relative.startswith(_CACHE + "/"):
            return "compile_cache"
        if relative == "agent/sessions" or relative.startswith("agent/sessions/"):
            return "session"
        return "unknown"

    def ingest(self, payload: bytes) -> None:
        offset = 0
        while offset < len(payload):
            if self._events >= MAX_EVENTS:
                self._problem("event_record_limit_unknown", guard=True)
                return
            if len(payload) - offset < _HEADER.size:
                self._problem("truncated_event", guard=True)
                return
            wd, mask, _cookie, length = _HEADER.unpack_from(payload, offset)
            self._events += 1
            offset += _HEADER.size
            if length > 4096 or offset + length > len(payload):
                self._problem("truncated_event", guard=True)
                return
            raw = payload[offset : offset + length].split(b"\0", 1)[0]
            offset += length
            if not mask or mask & ~(_MASK | _OVERFLOW | _IGNORED | _ISDIR):
                self._problem("event_mask_unknown", guard=True)
            if mask & (_OVERFLOW | _UNMOUNT | _MOVE_SELF):
                self._problem("event_coverage_lost", guard=True)
            watch = self._watches.get(wd)
            if watch is None:
                self._problem("watch_identity_unknown", guard=True)
                continue
            path, file_watch = watch
            if raw:
                if file_watch or b"/" in raw or raw in {b".", b".."}:
                    self._problem("event_name_unknown", guard=True)
                    continue
                path = path / os.fsdecode(raw)
            relative = path.relative_to(self.root).as_posix()
            if relative == ".":
                relative = ""
            category = self._category(relative)
            if mask & (_MOVED_FROM | _MOVED_TO):
                self._problem("cross_boundary_move", guard=True)
                self._unknown += 1
            if self._sealed:
                if mask & _DELETE_SELF:
                    try:
                        path.lstat()
                    except FileNotFoundError:
                        gone = True
                    except OSError:
                        gone = False
                    else:
                        gone = False
                    if self._delete_authorized and gone:
                        self._self_deleted.add(wd)
                    else:
                        self._problem("unexpected_watch_deletion", guard=True)
                if mask & _IGNORED and (
                    not self._delete_authorized or wd not in self._self_deleted
                ):
                    self._problem("assessed_watch_lost", guard=True)
                # File-unlink emits ATTRIB/DELETE_SELF/IGNORED on its inode
                # watch. These are cleanup metadata, never content-write proof.
                if mask & (_CREATE | _MODIFY | _CLOSE_WRITE | _MOVED_FROM | _MOVED_TO):
                    self._post += 1
                    self._problem("post_terminal_write", guard=True)
                continue
            if mask & (_IGNORED | _DELETE_SELF):
                self._problem("assessed_watch_lost", guard=True)
            if not mask & _MUTATION:
                continue
            if category == "session":
                self._session += 1
                self._problem("session_write_observed")
            elif relative == _SETTING:
                if mask & (_CREATE | _DELETE | _ATTRIB):
                    self._unknown += 1
                    self._problem("public_settings_identity_event", guard=True)
                elif mask & (_MODIFY | _CLOSE_WRITE):
                    self._counts["control_settings"] += 1
            elif category in {"baseline", "unknown"}:
                self._unknown += 1
                self._problem("unclassified_or_baseline_write", guard=True)
            else:
                self._counts[category] += 1
                expected_dir = category in {"store_lock", "compile_cache"}
                if mask & _CREATE and bool(mask & _ISDIR) != expected_dir:
                    self._problem("cache_boundary_type_unknown", guard=True)
                if mask & _DELETE and category != "store_lock":
                    self._problem("cache_boundary_removed", guard=True)

    def drain(self) -> None:
        if self._closed:
            if not (self._sealed and self._deleted):
                self._problem("observer_closed", guard=True)
            return
        while True:
            if "event_record_limit_unknown" in self._reasons:
                return
            try:
                raw = os.read(self.fd, 65536)
            except BlockingIOError:
                return
            except OSError:
                self._problem("observer_read_failed", guard=True)
                return
            if not raw:
                self._problem("observer_eof", guard=True)
                return
            self.ingest(raw)

    def _scan_terminal(self) -> None:
        counts = _inventory()
        seen_dirs: set[tuple[int, int]] = set()
        entries = 0
        pending: list[tuple[int, str]] = []
        try:
            root_fd = os.open(
                self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            pending = [(root_fd, "")]
            root_device = os.fstat(root_fd).st_dev
            while pending:
                descriptor, prefix = pending.pop()
                try:
                    before = os.fstat(descriptor)
                    if (
                        before.st_dev,
                        before.st_ino,
                    ) in seen_dirs or before.st_dev != root_device:
                        raise ValueError
                    seen_dirs.add((before.st_dev, before.st_ino))
                    with os.scandir(descriptor) as children:
                        for child in children:
                            entries += 1
                            if entries > MAX_ENTRIES:
                                raise ValueError
                            relative = (
                                prefix + "/" + child.name if prefix else child.name
                            )
                            info = child.stat(follow_symlinks=False)
                            category = self._category(relative)
                            kind = (
                                "directory"
                                if stat.S_ISDIR(info.st_mode)
                                else "regular"
                                if stat.S_ISREG(info.st_mode)
                                else "other"
                            )
                            counts[category][kind] += 1
                            if (
                                info.st_uid != os.getuid()
                                or info.st_dev != root_device
                                or category in {"session", "unknown"}
                                or kind == "other"
                                or (kind == "regular" and info.st_nlink != 1)
                                or (
                                    category in {"auth_store", "model_store"}
                                    and kind != "regular"
                                )
                                or (category == "store_lock" and kind != "directory")
                                or (relative == _CACHE and kind != "directory")
                            ):
                                raise ValueError
                            if kind == "directory":
                                child_fd = os.open(
                                    child.name,
                                    os.O_RDONLY
                                    | os.O_DIRECTORY
                                    | os.O_NOFOLLOW
                                    | os.O_CLOEXEC,
                                    dir_fd=descriptor,
                                )
                                current = os.fstat(child_fd)
                                if (current.st_dev, current.st_ino) != (
                                    info.st_dev,
                                    info.st_ino,
                                ):
                                    os.close(child_fd)
                                    raise ValueError
                                pending.append((child_fd, relative))
                    if _stamp(before) != _stamp(os.fstat(descriptor)):
                        raise ValueError
                finally:
                    os.close(descriptor)
            if counts["baseline"] != {"regular": 1, "directory": 3, "other": 0}:
                raise ValueError
            self._terminal_ok = True
        except (OSError, ValueError):
            self._problem("terminal_inventory_unknown", guard=True)
        finally:
            for descriptor, _prefix in pending:
                os.close(descriptor)
            self._terminal = counts

    def seal_terminal(self) -> None:
        if not self._started or self._sealed:
            self._problem("window_sequence_unknown", guard=True)
            raise SessionObservationRejected("window_sequence_unknown")
        first, second = self._gate(), self._gate()
        if first != second:
            self._problem("cgroup_identity_unknown", guard=True)
            raise SessionObservationRejected("cgroup_identity_unknown")
        self.drain()
        self._check_anchors()
        self._scan_terminal()
        self.drain()
        self._sealed = True

    def ready_for_delete(self) -> None:
        self.drain()
        self._gate()
        self._check_anchors()
        if not self._sealed or not self._terminal_ok or self._reasons:
            raise SessionObservationRejected("session_observation_unknown")
        self._delete_authorized = True

    def check_deleted(self) -> None:
        if not self._sealed or self._deleted:
            raise SessionObservationRejected("window_sequence_unknown")
        self._gate()
        try:
            self.root.lstat()
        except FileNotFoundError:
            self._deleted = True
        except OSError:
            self._problem("directory_check_unknown", guard=True)
        else:
            self._problem("deletion_unknown", guard=True)
        self._gate()
        self.drain()

    def receipt(self) -> dict[str, object]:
        if self._started:
            with suppress(SessionObservationRejected):
                self._gate()
        self.drain()
        row = missing_receipt(self.reader)
        reasons = set(self._reasons)
        if not (self._started and self._sealed and self._deleted):
            reasons.add("complete_lifecycle_missing")
        guard = "unknown" if self._guard_reasons or not self._started else "complete"
        row.update(
            event_source="inotify",
            result="unknown" if reasons else "session_window_complete",
            session_history="unknown"
            if guard == "unknown"
            else "observed_mutation"
            if self._session
            else "zero_observed",
            session_mutation_events=self._session,
            session_integrity=guard,
            guard_integrity=guard,
            unknown_mutation_events=self._unknown,
            settings_semantics=self._settings_semantics,
            non_session_event_lower_bounds={
                key: self._counts[key] for key in _NON_SESSION_EVENTS
            },
            terminal_status="classified_snapshot" if self._terminal_ok else "unknown",
            terminal_inventory=self._terminal,
            terminal_integrity="complete" if self._terminal_ok else "unknown",
            directory_deleted=self._deleted,
            cleanup_integrity="complete"
            if self._deleted and not self._cleanup_reasons
            else "unknown",
            post_terminal_write_events=self._post,
            reasons=sorted(reasons),
        )
        return row

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self.fd >= 0:
                try:
                    os.close(self.fd)
                except OSError:
                    self._problem("observer_close_unknown", guard=True)
                    raise

    def __enter__(self) -> ClassifiedSessionObservation:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
