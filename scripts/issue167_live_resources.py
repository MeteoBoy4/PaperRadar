"""Experimental public-launch resource observation, inert until explicitly entered.

This controller-local adapter does not change model arguments, environment,
pre-exec isolation, pipe termination, or inherited installation descriptors.
It is not product admission or a new product launch-policy identity.
"""

from __future__ import annotations

import copy
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Protocol, cast

from paper_radar.pi_execution import launcher
from paper_radar.pi_execution.resources import (
    SETTINGS_JSON,
    AttemptResources,
    ExecutionRoots,
)
from scripts.issue167_fork_observation import CgroupReader, ForkObservation
from scripts.issue167_session_observation import (
    ClassifiedSessionObservation,
    SessionObservationRejected,
    missing_receipt,
)

_LEASE = threading.Lock()


class _LauncherModule(Protocol):
    AttemptResources: type[AttemptResources]


_LAUNCHER = cast(_LauncherModule, launcher)


class ResourceObservationRejected(ValueError):
    """Closed metadata category; never include paths or external exception text."""


@dataclass
class _Attempt:
    sequence: int
    resource: AttemptResources
    window: ForkObservation | ClassifiedSessionObservation | None = None
    receipt: dict[str, object] | None = None
    finished: bool = False
    failed: bool = False


class LaunchResourceObservation:
    """One exclusive adapter scope in an otherwise trusted, isolated controller.

    Normal scope exit requires every created resource to have completed its
    window. Exceptional exit closes observation FDs but never deletes a tree
    whose child-writer gate or observed window is incomplete.
    """

    def __init__(
        self, reader: CgroupReader, *, synthetic: bool = False, classified: bool = False
    ) -> None:
        if (
            type(reader) is not CgroupReader
            or type(synthetic) is not bool
            or type(classified) is not bool
        ):
            raise ResourceObservationRejected("resource_authority_unknown")
        if not synthetic and (
            reader.source != "kernel_own_cgroup_metadata"
            or reader.cgroup_root != Path("/sys/fs/cgroup")
            or reader.self_cgroup != Path("/proc/self/cgroup")
            or reader.controller_pid != os.getpid()
        ):
            raise ResourceObservationRejected("resource_authority_unknown")
        self.reader = reader
        self.synthetic = synthetic
        self.classified = classified
        self._attempts: list[_Attempt] = []
        self._active = False
        self._entered = False
        self._thread: int | None = None
        self._factory: type[AttemptResources] | None = None
        self._problem: str | None = None

    def _missing(self, attempt: _Attempt) -> dict[str, object]:
        deleted = False
        root = getattr(attempt.resource, "root", None)
        if isinstance(root, Path):
            try:
                root.lstat()
            except FileNotFoundError:
                deleted = True
            except OSError:
                pass
        if self.classified:
            receipt = missing_receipt(self.reader)
            receipt["directory_deleted"] = deleted
            return receipt
        return {
            "scope": "fork_observation_prototype",
            "source": self.reader.source,
            "event_source": "unknown",
            "run_id": self.reader.plan.run_id,
            "result": "unknown",
            "history": "unknown",
            "mutation_events": None,
            "terminal_status": "terminal_unknown",
            "terminal_regular_files": None,
            "terminal_other_entries": None,
            "directory_deleted": deleted,
            "post_terminal_mutation_events": None,
            "reasons": ["resource_lifecycle_incomplete"],
        }

    def _snapshot(self, attempt: _Attempt) -> None:
        if attempt.window is None:
            attempt.receipt = self._missing(attempt)
            return
        try:
            attempt.receipt = attempt.window.receipt()
        except Exception:
            attempt.receipt = self._missing(attempt)

    @property
    def receipts(self) -> tuple[dict[str, object], ...]:
        # Reading status while a child is active must not call receipt(): doing
        # so would falsely mark the still-open backend process window incomplete.
        rows = []
        for attempt in self._attempts:
            row = copy.deepcopy(attempt.receipt or self._missing(attempt))
            row.update(category="attempt_files", sequence=attempt.sequence)
            if self._problem is not None:
                row["result"] = "unknown"
                row["reasons"] = sorted(
                    set(cast(list[str], row["reasons"])) | {self._problem}
                )
            rows.append(row)
        return tuple(rows)

    def assert_complete(self) -> None:
        if self._problem is not None:
            raise ResourceObservationRejected(self._problem)
        if not self._attempts:
            raise ResourceObservationRejected("resource_observation_missing")
        if any(not attempt.finished for attempt in self._attempts):
            raise ResourceObservationRejected("resource_observation_incomplete")
        expected = "session_window_complete" if self.classified else "window_complete"
        if any(row["result"] != expected for row in self.receipts):
            raise ResourceObservationRejected("resource_window_unknown")

    def _before_delete(
        self, window: ForkObservation | ClassifiedSessionObservation
    ) -> None:
        if isinstance(window, ClassifiedSessionObservation):
            try:
                window.ready_for_delete()
            except SessionObservationRejected:
                raise ResourceObservationRejected("resource_window_unknown") from None
            return
        row = window.receipt()
        reasons = row["reasons"]
        if (
            type(reasons) is not list
            or set(reasons) - {"complete_lifecycle_missing", "deletion_unknown"}
            or row["history"] not in {"zero_observed", "observed_mutation"}
            or row["terminal_status"] != "synthetic_snapshot"
            or row["directory_deleted"] is not False
            or type(row["post_terminal_mutation_events"]) is not int
            or row["post_terminal_mutation_events"] != 0
            or any(
                type(row[key]) is not int or cast(int, row[key]) < 0
                for key in ("terminal_regular_files", "terminal_other_entries")
            )
            or (
                not self.synthetic
                and (
                    row["source"] != "kernel_own_cgroup_metadata"
                    or row["event_source"] != "inotify"
                )
            )
        ):
            raise ResourceObservationRejected("resource_window_unknown")

    def __enter__(self) -> LaunchResourceObservation:
        if not _LEASE.acquire(blocking=False):
            raise ResourceObservationRejected("resource_adapter_busy")
        try:
            if self._entered:
                raise ResourceObservationRejected("resource_adapter_reused")
            if _LAUNCHER.AttemptResources is not AttemptResources:
                raise ResourceObservationRejected("resource_factory_binding_unknown")
            self._entered = self._active = True
            self._thread = threading.get_ident()
            owner = self

            class ObservedResources(AttemptResources):
                def __init__(self, roots: ExecutionRoots, proxy: str | None) -> None:
                    if not owner._active or threading.get_ident() != owner._thread:
                        raise ResourceObservationRejected(
                            "resource_adapter_thread_unknown"
                        )
                    if any(not a.finished for a in owner._attempts):
                        raise ResourceObservationRejected(
                            "resource_adapter_attempt_overlap"
                        )
                    attempt = _Attempt(len(owner._attempts) + 1, self)
                    self._observation = attempt
                    owner._attempts.append(attempt)
                    try:
                        super().__init__(roots, proxy)
                    except BaseException:
                        attempt.failed = True
                        owner._snapshot(attempt)
                        raise
                    try:
                        attempt.window = (
                            ClassifiedSessionObservation(
                                self.root, owner.reader, expected_settings=SETTINGS_JSON
                            )
                            if owner.classified
                            else ForkObservation(self.root, owner.reader)
                        )
                        attempt.window.start()
                    except BaseException:
                        attempt.failed = True
                        # Constructor has not returned: model Popen cannot yet
                        # have happened. This is only the newly-owned base tree.
                        try:
                            AttemptResources.close(self)
                        finally:
                            owner._snapshot(attempt)
                            if attempt.window is not None:
                                attempt.window.close()
                        raise

                def close(self) -> None:
                    attempt = self._observation
                    if attempt.finished:
                        return
                    if attempt.window is None:
                        # The base constructor may virtually call close before
                        # its own initialization has completed.
                        if hasattr(self, "root"):
                            AttemptResources.close(self)
                        return
                    if attempt.failed:
                        raise ResourceObservationRejected("resource_window_unknown")
                    try:
                        attempt.window.seal_terminal()
                        owner._before_delete(attempt.window)
                        AttemptResources.close(self)
                        attempt.window.check_deleted()
                        owner._snapshot(attempt)
                        expected = (
                            "session_window_complete"
                            if owner.classified
                            else "window_complete"
                        )
                        if (
                            attempt.receipt is None
                            or attempt.receipt["result"] != expected
                        ):
                            raise ResourceObservationRejected("resource_window_unknown")
                        attempt.finished = True
                    except BaseException:
                        attempt.failed = True
                        owner._snapshot(attempt)
                        raise
                    finally:
                        try:
                            attempt.window.close()
                        except BaseException as error:
                            attempt.failed = True
                            attempt.finished = False
                            if attempt.receipt is None:
                                attempt.receipt = owner._missing(attempt)
                            attempt.receipt["result"] = "unknown"
                            attempt.receipt["reasons"] = sorted(
                                set(cast(list[str], attempt.receipt["reasons"]))
                                | {"resource_observer_close_unknown"}
                            )
                            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                                raise
                            raise ResourceObservationRejected(
                                "resource_observer_close_unknown"
                            ) from None

            self._factory = ObservedResources
            _LAUNCHER.AttemptResources = ObservedResources
            return self
        except BaseException:
            self._active = False
            _LEASE.release()
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                self.assert_complete()
        finally:
            try:
                if _LAUNCHER.AttemptResources is not self._factory:
                    self._problem = "resource_factory_binding_unknown"
                _LAUNCHER.AttemptResources = AttemptResources
                for attempt in self._attempts:
                    if attempt.receipt is None:
                        self._snapshot(attempt)
                    if attempt.window is not None:
                        try:
                            attempt.window.close()
                        except OSError:
                            self._problem = "resource_observer_close_unknown"
            except BaseException:
                self._problem = "resource_cleanup_interrupted"
                raise
            finally:
                # An interruption in observer cleanup must not leave a global
                # factory lease held. It remains a failed/unknown attempt.
                self._active = False
                _LEASE.release()
        if exc_type is None and self._problem is not None:
            raise ResourceObservationRejected(self._problem)


def observe_launch_resources(
    reader: CgroupReader, *, synthetic: bool = False, classified: bool = False
) -> LaunchResourceObservation:
    """Acquire the process-local experimental hook; construction alone is inert."""
    return LaunchResourceObservation(reader, synthetic=synthetic, classified=classified)
