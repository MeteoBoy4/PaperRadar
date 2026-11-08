"""Offline H1 seam: file windows gated by directly read cgroup membership.

This is not admission evidence. A real collector must be protected, bound to its
service, and remain quiescent after the closure gate. Tests use declared fixtures.
The module does not spawn/stop/delete processes or read observed file contents.
"""

from __future__ import annotations

import os
import stat
import struct
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from scripts.issue167_h1_phase import Plan, read_cgroup_state
from scripts.issue167_observation import FileObserver

_CGROUP_ROOT = Path("/sys/fs/cgroup")
_SELF_CGROUP = Path("/proc/self/cgroup")


class WindowRejected(ValueError):
    """Controlled metadata reason, never paths, file names, or exception text."""


@dataclass(frozen=True)
class Membership:
    identity: tuple[int, int]
    pids: frozenset[int]


class TrackedFileObserver(FileObserver):
    """Distinguish expected IN_IGNORED on removal from lost cleanup coverage."""

    def __init__(self, root: Path) -> None:
        self.post_terminal_coverage_lost = False
        super().__init__(root)

    def ingest(self, payload: bytes) -> None:
        if self._history_snapshot is not None:
            offset = 0
            while offset < len(payload):
                if len(payload) - offset < 16:
                    self.post_terminal_coverage_lost = True
                    break
                _wd, mask, _cookie, size = struct.unpack_from("iIII", payload, offset)
                offset += 16 + size
                if offset > len(payload) or mask & (0x4000 | 0x2000 | 0x800):
                    self.post_terminal_coverage_lost = True
        super().ingest(payload)


class CgroupReader:
    """Read own membership and a bounded nofollow subtree; accept no caller JSON.

    A nonstandard root/self file or controller PID is always labeled a synthetic
    fixture. This label is provenance, not a cryptographic source attestation.
    """

    def __init__(
        self,
        plan: Plan,
        *,
        controller_pid: int | None = None,
        cgroup_root: Path = _CGROUP_ROOT,
        self_cgroup: Path = _SELF_CGROUP,
    ) -> None:
        self.plan = plan
        self.controller_pid = os.getpid() if controller_pid is None else controller_pid
        if type(self.controller_pid) is not int or self.controller_pid <= 1:
            raise WindowRejected("controller_identity_unknown")
        self.cgroup_root = cgroup_root
        self.self_cgroup = self_cgroup
        self.source = (
            "kernel_own_cgroup_metadata"
            if cgroup_root == _CGROUP_ROOT
            and self_cgroup == _SELF_CGROUP
            and self.controller_pid == os.getpid()
            else "synthetic_cgroup_fixture"
        )

    def sample(self) -> Membership:
        descriptors: list[int] = []
        try:
            descriptor = os.open(
                self.self_cgroup,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            )
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise WindowRejected("self_cgroup_unknown")
                raw = source.read(16385)
            if raw != f"0::{self.plan.cgroup}\n".encode():
                raise WindowRejected("self_cgroup_unknown")
            for name in (self.cgroup_root, "system.slice", self.plan.unit):
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=descriptors[-1] if descriptors else None,
                )
                descriptors.append(descriptor)
            before = os.fstat(descriptors[-1])
            state = read_cgroup_state(self.plan, cgroup_root=self.cgroup_root)
            after = os.stat(
                self.plan.unit, dir_fd=descriptors[-2], follow_symlinks=False
            )
            identity = (before.st_dev, before.st_ino)
            if (
                not state.exists
                or not stat.S_ISDIR(after.st_mode)
                or identity != (after.st_dev, after.st_ino)
            ):
                raise WindowRejected("cgroup_identity_unknown")
            return Membership(identity, state.pids)
        except WindowRejected:
            raise
        except (OSError, ValueError):
            raise WindowRejected("cgroup_read_unknown") from None
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


class ForkObservation:
    """Watch one already-created tree; close only after no child writers remain.

    The trusted controller remains alive in the group and must not start another
    writer between the gate and snapshot/deletion. A stopped controller, process
    group wait, or a self-reported descendants_reaped flag cannot satisfy this API.
    This lifecycle is for a disposable per-attempt/model tree. A persistent auth
    directory has a different policy and is not automatically watched or deleted.
    """

    def __init__(
        self,
        root: Path,
        reader: CgroupReader,
        *,
        observer_factory: Callable[[Path], FileObserver] | None = None,
    ) -> None:
        self._event_source = (
            "inotify" if observer_factory is None else "synthetic_event_backend"
        )
        try:
            self._observer = (observer_factory or TrackedFileObserver)(root)
        except (OSError, ValueError):
            raise WindowRejected("file_observer_unavailable") from None
        self._reader = reader
        self._identity: tuple[int, int] | None = None
        self._started = False
        self._sealed = False
        self._deleted_checked = False
        self._problems: set[str] = set()

    def _gate(self) -> Membership:
        try:
            sample = self._reader.sample()
            if sample.pids != {self._reader.controller_pid}:
                raise WindowRejected("writers_not_quiescent")
            if self._identity is not None and sample.identity != self._identity:
                raise WindowRejected("cgroup_identity_unknown")
            return sample
        except WindowRejected as error:
            self._problems.add(str(error))
            raise

    def start(self) -> None:
        if self._started:
            self._problems.add("window_sequence_unknown")
            raise WindowRejected("window_sequence_unknown")
        self._identity = self._gate().identity
        self._observer.launch_started()
        if self._observer.reasons:
            self._problems.add("file_window_unknown")
            raise WindowRejected("file_window_unknown")
        self._started = True

    def seal_terminal(self) -> None:
        if not self._started or self._sealed:
            self._problems.add("window_sequence_unknown")
            raise WindowRejected("window_sequence_unknown")
        first = self._gate()
        second = self._gate()
        if first != second:
            self._problems.add("cgroup_identity_unknown")
            raise WindowRejected("cgroup_identity_unknown")
        self._observer.descendants_reaped()
        self._observer.snapshot_terminal()
        self._sealed = True

    def check_deleted(self) -> None:
        if not self._sealed or self._deleted_checked:
            self._problems.add("window_sequence_unknown")
            raise WindowRejected("window_sequence_unknown")
        self._gate()
        try:
            self._observer.root.lstat()
        except FileNotFoundError:
            pass
        except OSError:
            self._problems.add("directory_check_unknown")
            raise WindowRejected("directory_check_unknown") from None
        else:
            self._problems.add("deletion_unknown")
            raise WindowRejected("deletion_unknown")
        self._gate()
        self._deleted_checked = True

    def receipt(self) -> dict[str, object]:
        if self._started:
            # Keep prior facts separate; a failed gate makes result unknown.
            with suppress(WindowRejected):
                self._gate()
        receipt = self._observer.receipt()
        reasons = set(self._problems) | set(receipt.reasons)
        if not (self._started and self._sealed and self._deleted_checked):
            reasons.add("complete_lifecycle_missing")
        if receipt.terminal_status != "synthetic_snapshot":
            reasons.add("terminal_unknown")
        if not receipt.directory_deleted:
            reasons.add("deletion_unknown")
        # Normal IN_IGNORED after deliberate tree removal does not erase a
        # previously sealed history. Other cleanup observation failures do.
        if set(receipt.cleanup_reasons) - {"event_coverage_lost"} or (
            "event_coverage_lost" in receipt.cleanup_reasons
            and (
                not isinstance(self._observer, TrackedFileObserver)
                or self._observer.post_terminal_coverage_lost
            )
        ):
            reasons.add("cleanup_observation_unknown")
        post_terminal_mutations = (
            self._observer.mutations - receipt.mutation_events if self._sealed else None
        )
        if post_terminal_mutations:
            reasons.add("cleanup_mutation_unknown")
        return {
            "scope": "fork_observation_prototype",
            "source": self._reader.source,
            "event_source": self._event_source,
            "run_id": self._reader.plan.run_id,
            "result": "unknown" if reasons else "window_complete",
            "history": receipt.history,
            "mutation_events": receipt.mutation_events,
            "terminal_status": receipt.terminal_status,
            "terminal_regular_files": receipt.terminal_regular_files,
            "terminal_other_entries": receipt.terminal_other_entries,
            "directory_deleted": receipt.directory_deleted,
            "post_terminal_mutation_events": post_terminal_mutations,
            "reasons": sorted(reasons),
        }

    def close(self) -> None:
        self._observer.close()

    def __enter__(self) -> ForkObservation:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
