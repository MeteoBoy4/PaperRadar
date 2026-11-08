"""E01 owner-side single pidfd delivery seam; import has no host effects."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import resource
import select
import signal
import stat
import time
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from scripts import issue167_live_owner as previous_owner
from scripts import issue167_live_signal_case as contract
from scripts import issue167_resolver_owner as base


@dataclass(frozen=True)
class ControllerIdentity:
    pid: int
    starttime: int
    cgroup_device: int
    cgroup_inode: int

    def __post_init__(self) -> None:
        if (
            type(self.pid) is not int
            or not 1 < self.pid <= 2**31 - 1
            or any(
                type(v) is not int or not 0 < v < 2**64
                for v in (self.starttime, self.cgroup_device, self.cgroup_inode)
            )
        ):
            raise contract.CaseRejected("signal_target_unknown")

    def reference(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_reference(cls, value: object) -> ControllerIdentity:
        if type(value) is not dict or set(value) != {
            "pid",
            "starttime",
            "cgroup_device",
            "cgroup_inode",
        }:
            raise contract.CaseRejected("signal_target_unknown")
        return cls(**value)


def own_controller_starttime(pid: int) -> int:
    """Only stat metadata for the service controller already named by manager."""
    if type(pid) is not int or not 1 < pid <= 2**31 - 1:
        raise contract.CaseRejected("signal_target_unknown")
    with Path(f"/proc/{pid}/stat").open("rb") as source:
        raw = source.read(8193)
    try:
        if len(raw) > 8192 or int(raw.split(b" ", 1)[0]) != pid:
            raise ValueError
        tail = raw.rsplit(b") ", 1)[1].split()
        value = int(tail[19])
        if value <= 0:
            raise ValueError
        return value
    except (ValueError, IndexError):
        raise contract.CaseRejected("signal_target_unknown") from None


class PinnedSender:
    """One immutable controller reference and at most one SIGINT syscall."""

    def __init__(
        self,
        identity: ControllerIdentity,
        verify: Callable[[], ControllerIdentity],
        *,
        opener: Callable[[int], int] = os.pidfd_open,
        closer: Callable[[int], None] = os.close,
        alive: Callable[[int], bool] | None = None,
        sender: Callable[[int, int], None] | None = None,
    ) -> None:
        self.identity = identity
        self.verify = verify
        self.closer = closer
        self.alive = alive or (lambda fd: not select.select([fd], [], [], 0)[0])
        self.sender = sender or (lambda fd, sig: signal.pidfd_send_signal(fd, sig))
        self.fd: int | None = None
        self.attempts = 0
        self.returned = False
        self.not_delivered_exited = False
        self.marker_reference: dict[str, object] | None = None
        try:
            self.fd = opener(identity.pid)
            self.check()
        except BaseException:
            self.close()
            raise

    def check(self) -> None:
        if (
            self.fd is None
            or not self.alive(self.fd)
            or self.verify() != self.identity
            or not self.alive(self.fd)
        ):
            raise contract.CaseRejected("signal_target_unknown")

    def deliver(
        self,
        marker: object,
        *,
        run_id: str,
        fingerprint: str,
        persist_intent: Callable[[dict[str, object]], None],
    ) -> dict[str, object]:
        if self.attempts:
            raise contract.CaseRejected("signal_retry_forbidden")
        reference = contract.validate_marker(
            marker, run_id=run_id, fingerprint=fingerprint
        )
        self.check()
        self.attempts = 1
        self.marker_reference = dict(reference)
        intent = {
            "scope": contract.SCOPE,
            "run_id": run_id,
            "category": "external_sigint_intent",
            "sequence": 1,
            "count": 1,
            "marker_reference": reference,
            "target_reference": self.identity.reference(),
        }
        persist_intent(intent)
        self.check()
        assert self.fd is not None
        try:
            self.sender(self.fd, signal.SIGINT)
        except ProcessLookupError:
            if self.alive(self.fd):
                raise contract.CaseRejected("signal_delivery_unknown") from None
            self.not_delivered_exited = True
        except BaseException:
            raise contract.CaseRejected("signal_delivery_unknown") from None
        else:
            self.returned = True
        return self.receipt()

    def receipt(self) -> dict[str, object]:
        return {
            "category": "external_sigint_delivery",
            "sequence": 1,
            "attempted_count": self.attempts,
            "syscall_returned": self.returned,
            "not_delivered_exited": self.not_delivered_exited,
            "target": "pidfd_bound_controller_only",
            "target_reference": self.identity.reference(),
            "marker_reference": None
            if self.marker_reference is None
            else dict(self.marker_reference),
        }

    def close(self) -> None:
        if self.fd is not None:
            self.closer(self.fd)
            self.fd = None


def reconcile_delivery(
    delivery: object, observed: object, *, normal_complete: bool
) -> str:
    """Missing handler receipt is unknown even when a delivery could have been late."""
    if (
        type(delivery) is not dict
        or type(normal_complete) is not bool
        or set(delivery)
        != {
            "category",
            "sequence",
            "attempted_count",
            "syscall_returned",
            "not_delivered_exited",
            "target",
            "target_reference",
            "marker_reference",
        }
        or type(delivery["sequence"]) is not int
        or delivery["sequence"] != 1
        or type(delivery["attempted_count"]) is not int
        or delivery["attempted_count"] not in {0, 1}
        or type(delivery["syscall_returned"]) is not bool
        or type(delivery["not_delivered_exited"]) is not bool
    ):
        raise contract.CaseRejected("signal_delivery_unknown")
    signal_row = contract.validate_signal(observed)
    ControllerIdentity.from_reference(delivery["target_reference"])
    marker = delivery["marker_reference"]
    if delivery["attempted_count"] == 1:
        if type(marker) is not dict or type(marker.get("fingerprint")) is not str:
            raise contract.CaseRejected("signal_delivery_unknown")
        contract.validate_marker(
            marker, run_id=contract.RUN, fingerprint=marker["fingerprint"]
        )
    elif marker is not None:
        raise contract.CaseRejected("signal_delivery_unknown")
    delivery = {
        k: v
        for k, v in delivery.items()
        if k not in {"target_reference", "marker_reference"}
    }
    if delivery == {
        "category": "external_sigint_delivery",
        "sequence": 1,
        "attempted_count": 1,
        "syscall_returned": True,
        "not_delivered_exited": False,
        "target": "pidfd_bound_controller_only",
    }:
        if signal_row["sigint_received"] != 1:
            raise contract.CaseRejected("signal_delivery_unknown")
        if (
            signal_row["effective_sigint_received"] == 1
            and signal_row["same_keyboard_interrupt_propagated"] is True
            and signal_row["marker_publications"] == 1
            and normal_complete is False
        ):
            return "observed_expected"
        if (
            normal_complete
            and signal_row["late_sigint_received"] == 1
            and signal_row["same_keyboard_interrupt_propagated"] is False
        ):
            return "not_triggered"
        raise contract.CaseRejected("signal_delivery_unknown")
    if (
        normal_complete
        and delivery
        in (
            {
                "category": "external_sigint_delivery",
                "sequence": 1,
                "attempted_count": 0,
                "syscall_returned": False,
                "not_delivered_exited": False,
                "target": "pidfd_bound_controller_only",
            },
            {
                "category": "external_sigint_delivery",
                "sequence": 1,
                "attempted_count": 1,
                "syscall_returned": False,
                "not_delivered_exited": True,
                "target": "pidfd_bound_controller_only",
            },
        )
        and signal_row["sigint_received"] == 0
    ):
        return "not_triggered"
    raise contract.CaseRejected("signal_delivery_unknown")


class LiveOperations(previous_owner.LiveOperations):
    case: Any

    def __init__(self, case: contract.Case, sha: str) -> None:
        base.LiveOperations.__init__(self, case, contract, sha)
        self.previous_counts = (0, 0)
        self.exit_metadata = previous_owner.new_exit_metadata()
        self.sender: PinnedSender | None = None
        self.signal_delivery: dict[str, object] = {
            "category": "external_sigint_delivery",
            "sequence": 1,
            "attempted_count": 0,
            "syscall_returned": False,
            "not_delivered_exited": False,
            "target": "pidfd_bound_controller_only",
        }
        self.started = False

    def _wait(self, name: str) -> object:
        if name not in {
            "ready.json",
            "preflight-result.json",
            "auth-ready-1.json",
            "worker-result.json",
        }:
            raise base.OwnerRejected("metadata_name_unknown")
        deadline = min(
            self.deadline,
            time.monotonic()
            + (360 if name in {"preflight-result.json", "worker-result.json"} else 120),
        )
        while time.monotonic() < deadline:
            try:
                return self.contract.read_metadata(
                    self.case.worker_root / name, owner=self.case.uid
                )
            except FileNotFoundError:
                pass
            try:
                terminal = self.contract.read_metadata(
                    self.case.worker_root / "worker-result.json", owner=self.case.uid
                )
            except FileNotFoundError:
                terminal = None
            if (
                type(terminal) is dict
                and terminal.get("run_id") == self.case.run_id
                and terminal.get("result") == "unknown"
            ):
                raise base.OwnerRejected("worker_terminated_unknown")
            time.sleep(0.02)
        raise base.OwnerRejected("worker_deadline_unknown")

    def ready(self) -> dict[str, object]:
        value = base.LiveOperations.ready(self)
        self.sender = PinnedSender(
            self._controller_identity(), self._controller_identity
        )
        self.signal_delivery = self.sender.receipt()
        return value

    def start(self) -> None:
        if self.started:
            raise base.OwnerRejected("signal_retry_forbidden")
        self.started = True
        super().start()

    def _controller_identity(self) -> ControllerIdentity:
        state = self.commands.unit_state()
        if (
            self.ready_metadata is None
            or state.pid != self.ready_metadata["pid"]
            or state.pid not in self.phase.read_cgroup_state(self.plan).pids
        ):
            raise base.OwnerRejected("signal_target_unknown")
        device, inode = self.guard.read_cgroup_identity(self.plan)
        return ControllerIdentity(
            state.pid, own_controller_starttime(state.pid), device, inode
        )

    def preflight_result(self) -> dict[str, object]:
        value = contract.validate_preflight(self._wait("preflight-result.json"))
        if self._verify("preauthentication_complete") != (0, 0):
            raise base.OwnerRejected("preauthentication_packet_unknown")
        return value

    def auth_ready(self, sequence: int) -> None:
        if sequence != 1 or not base.metadata_equal(
            self._wait("auth-ready-1.json"),
            {
                "run_id": self.case.run_id,
                "sequence": 1,
                "auth_cli_completed": True,
                "logical_refresh_planned": 1,
            },
        ):
            raise base.OwnerRejected("auth_metadata_unknown")
        before = self.previous_counts
        after = self._verify("auth_complete_1")
        if after[0] <= before[0]:
            raise base.OwnerRejected("first_auth_network_evidence_unknown")

    def signal_or_terminal(self) -> dict[str, object]:
        deadline = min(self.deadline, time.monotonic() + 330)
        while time.monotonic() < deadline:
            try:
                terminal = contract.validate_result(
                    self.case,
                    self.contract.read_metadata(
                        self.case.worker_root / "worker-result.json",
                        owner=self.case.uid,
                    ),
                )
            except FileNotFoundError:
                terminal = None
            if terminal is not None:
                if terminal["result"] != "not_triggered":
                    raise base.OwnerRejected("signal_delivery_unknown")
                return dict(self.signal_delivery)
            try:
                marker = contract.validate_marker(
                    self.contract.read_metadata(
                        self.case.worker_root / "signal-ready.json", owner=self.case.uid
                    ),
                    run_id=self.case.run_id,
                    fingerprint=self.case.case_fingerprint,
                )
            except FileNotFoundError:
                time.sleep(0.02)
                continue
            if self.sender is None:
                raise base.OwnerRejected("signal_target_unknown")
            self.contract.verify_installation(self.case.install_root, self.manifest_sha)
            self._verify("before_external_sigint")
            self.signal_delivery = self.sender.deliver(
                marker,
                run_id=self.case.run_id,
                fingerprint=self.case.case_fingerprint,
                persist_intent=lambda value: self._write(
                    self.case.runtime_root / "signal-intent.json", value, 0o600
                ),
            )
            self._verify("after_external_sigint")
            return dict(self.signal_delivery)
        raise base.OwnerRejected("signal_window_unknown")

    def collect(self) -> dict[str, object]:
        value = cast(dict[str, Any], base.LiveOperations.collect(self))
        self._verify("signal_case_complete")
        row = value["case"]
        for phase in ("before", "after"):
            checkpoint = self.contract.read_metadata(
                self.case.worker_root / f"auth-metadata-1-{phase}.json",
                owner=self.case.uid,
                limit=32768,
            )
            if not base.metadata_equal(checkpoint, row["persistent_auth"][phase]):
                self.worker_accepted = False
                raise base.OwnerRejected("signal_auth_observation_unknown")
        checkpoint = self.contract.read_metadata(
            self.case.worker_root / "case-result-1.json", owner=self.case.uid
        )
        if not base.metadata_equal(checkpoint, row):
            self.worker_accepted = False
            raise base.OwnerRejected("worker_aggregate_inconsistent")
        outcome = reconcile_delivery(
            self.signal_delivery,
            row["signal"],
            normal_complete=row["normal_candidate_validated"],
        )
        if outcome != value["result"]:
            self.worker_accepted = False
            raise base.OwnerRejected("signal_delivery_unknown")
        if (
            self.sender is None
            or self.signal_delivery["target_reference"]
            != self.sender.identity.reference()
        ):
            raise base.OwnerRejected("signal_target_unknown")
        reference = self.signal_delivery["marker_reference"]
        if reference is not None:
            contract.validate_marker(
                reference,
                run_id=self.case.run_id,
                fingerprint=self.case.case_fingerprint,
            )
            intent = self.contract.read_metadata(
                self.case.runtime_root / "signal-intent.json", owner=0, limit=4096
            )
            if not base.metadata_equal(
                intent,
                {
                    "scope": contract.SCOPE,
                    "run_id": self.case.run_id,
                    "category": "external_sigint_intent",
                    "sequence": 1,
                    "count": 1,
                    "marker_reference": reference,
                    "target_reference": self.sender.identity.reference(),
                },
            ):
                raise base.OwnerRejected("signal_delivery_unknown")
        return value

    def finish(self) -> dict[str, object]:
        cleanup = importlib.import_module("scripts.issue167_live_signal_cleanup")
        from scripts import issue167_live_ipc as ipc

        if not self.worker_accepted or not self.restoration_accepted:
            raise base.OwnerRejected("unsuccessful_metadata_retained")
        self.contract.verify_installation(self.case.install_root, self.manifest_sha)
        root_uid = os.geteuid()
        self.owner.check_units(self.plan, self.commands, must_be_absent=True)
        if (
            self.phase.read_cgroup_state(self.plan, allow_absent=True).pids
            or self.table_created
            or self.create_uncertain
            or self.owner.table_present(
                self.plan,
                self._run((str(self.commands.tools["nft"]), "-j", "list", "tables")),
            )
        ):
            raise base.OwnerRejected("artifacts_not_quiescent")
        with Path("/proc/self/mountinfo").open("rb") as source:
            cleanup.check_mounts(
                (self.case.runtime_root, self.case.install_root),
                cleanup.mount_points(source.read(1048577)),
            )
        manifest = self.contract.read_metadata(
            self.case.install_root / "manifest.json", owner=0
        )
        assert isinstance(manifest, dict)
        code_names = {"", "manifest.json", *manifest["members"]}
        runtime_names = {
            "",
            "worker",
            "resolver-baseline.json",
            "owner-namespaces.json",
            "table-binding.json",
            "gate-preflight.json",
            "gate-auth-1.json",
            "gate-model-1.json",
            "gate-exit.json",
            "signal-intent.json",
        }
        worker_names = {
            "worker-started.json",
            "ready.json",
            "preflight-result.json",
            "case-1-reserved.json",
            "selection-0.json",
            "selection-1.json",
            "selection-2.json",
            "auth-metadata-1-before.json",
            "auth-metadata-1-after.json",
            "auth-ready-1.json",
            "signal-ready.json",
            "case-result-1.json",
            "worker-result.json",
            "materials",
            "ipc",
        }
        runtime_names.update("worker/" + n for n in worker_names)
        with zipfile.ZipFile(self.case.install_root / "materials.zip") as archive:
            for item in archive.infolist():
                path = Path(item.filename)
                if path.is_absolute() or ".." in path.parts or item.is_dir():
                    raise base.OwnerRejected("signal_materials_unknown")
                relative = "worker/materials/" + item.filename
                runtime_names.add(relative)
                runtime_names.update(
                    str(p)
                    for p in Path(relative).parents
                    if str(p) not in {".", "worker"}
                )
        for category in ipc.CATEGORIES:
            runtime_names.update(
                "worker/ipc/" + category + suffix
                for suffix in (
                    "",
                    "/install",
                    "/install/synthetic-python",
                    "/cwd",
                    "/attempt",
                    "/target-file",
                )
            )

        def inventory(
            root: Path, allowed: set[str], worker_allowed: bool
        ) -> dict[str, list[int]]:
            rows: dict[str, list[int]] = {}
            fds: dict[str, int] = {"": os.open(root, cleanup.DIR_FLAGS)}
            try:
                pending = [""]
                device = os.fstat(fds[""]).st_dev
                while pending:
                    relative = pending.pop()
                    info = os.fstat(fds[relative])
                    rows[relative] = cleanup.identity(info)
                    for name in os.listdir(fds[relative]):
                        child = relative + "/" + name if relative else name
                        if child not in allowed or len(rows) > 512:
                            raise base.OwnerRejected("cleanup_member_unknown")
                        entry = os.stat(
                            name, dir_fd=fds[relative], follow_symlinks=False
                        )
                        uid = (
                            self.case.uid
                            if worker_allowed
                            and (child == "worker" or child.startswith("worker/"))
                            else root_uid
                        )
                        if (
                            entry.st_dev != device
                            or entry.st_uid != uid
                            or entry.st_gid != uid
                            or entry.st_mode & 0o022
                            or stat.S_IMODE(entry.st_mode) & 0o7000
                            or not (
                                stat.S_ISDIR(entry.st_mode)
                                or (stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1)
                            )
                        ):
                            raise base.OwnerRejected("cleanup_boundary_unknown")
                        rows[child] = cleanup.identity(entry)
                        if len(rows) > 512:
                            raise base.OwnerRejected("cleanup_member_unknown")
                        if stat.S_ISDIR(entry.st_mode):
                            fds[child] = os.open(
                                name, cleanup.DIR_FLAGS, dir_fd=fds[relative]
                            )
                            if cleanup.identity(os.fstat(fds[child])) != rows[child]:
                                raise base.OwnerRejected("cleanup_member_unknown")
                            pending.append(child)
                return rows
            finally:
                for fd in fds.values():
                    os.close(fd)

        trees = (
            cleanup.Tree(
                self.case.runtime_root,
                inventory(self.case.runtime_root, runtime_names, True),
                root_uid,
                self.case.uid,
            ),
            cleanup.Tree(
                self.case.install_root,
                inventory(self.case.install_root, code_names, False),
                root_uid,
            ),
        )
        try:
            for tree in trees:
                tree.inspect()
            with Path("/proc/self/mountinfo").open("rb") as source:
                cleanup.check_mounts(
                    (self.case.runtime_root, self.case.install_root),
                    cleanup.mount_points(source.read(1048577)),
                )
            for tree in trees:
                tree.verify()
            self.owner.check_units(self.plan, self.commands, must_be_absent=True)
            if self.phase.read_cgroup_state(
                self.plan, allow_absent=True
            ).pids or self.owner.table_present(
                self.plan,
                self._run((str(self.commands.tools["nft"]), "-j", "list", "tables")),
            ):
                raise base.OwnerRejected("artifacts_not_quiescent")
            for tree in trees:
                tree.remove()
        finally:
            for tree in trees:
                tree.close()
        if any(
            os.path.lexists(p) for p in (self.case.runtime_root, self.case.install_root)
        ):
            raise base.OwnerRejected("artifacts_still_present")
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def close_sender(self) -> None:
        if self.sender is not None:
            self.sender.close()


class Operations(Protocol):
    exit_metadata: dict[str, object]

    def preflight(self) -> None: ...
    def reserve(self) -> None: ...
    def install(self) -> None: ...
    def start(self) -> None: ...
    def ready(self) -> dict[str, object]: ...
    def exercise_rules(self) -> dict[str, object]: ...
    def phase_gate(self, category: str, sequence: int) -> None: ...
    def preflight_result(self) -> dict[str, object]: ...
    def activate(self) -> None: ...
    def auth_ready(self, sequence: int) -> None: ...
    def signal_or_terminal(self) -> dict[str, object]: ...
    def collect(self) -> dict[str, object]: ...
    def wait_exit(self) -> None: ...
    def restore(self) -> dict[str, object]: ...
    def finish(self) -> dict[str, object]: ...
    def write_ledger(self, value: object) -> None: ...
    def database_restoration(self) -> dict[str, object]: ...
    def selection_journal(self) -> dict[str, object]: ...
    def close_sender(self) -> None: ...


def run_owner(case: contract.Case, ops: Operations) -> dict[str, object]:
    result: dict[str, object] = {
        "scope": contract.SCOPE,
        "run_id": case.run_id,
        "result": "unknown",
        "limits": dict(contract.LIMITS),
        "case_binding": case.to_dict(),
        "worker_ready": None,
        "preflight": None,
        "worker_result": None,
        "rules": None,
        "delivery": None,
        "restoration": None,
        "artifacts": None,
        "selection_journal": None,
        "database_selection_restoration": None,
        "exit_diagnostics": None,
        "restoration_stage": None,
        "resolver_check": None,
    }
    reserved = installed = successful = False
    outcome = "unknown"
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
        stage = "ready"
        result["worker_ready"] = ops.ready()
        stage = "rules"
        result["rules"] = ops.exercise_rules()
        stage = "preauthentication"
        ops.phase_gate("preflight", 0)
        result["preflight"] = ops.preflight_result()
        stage = "activate"
        ops.activate()
        stage = "auth"
        ops.phase_gate("auth", 1)
        ops.auth_ready(1)
        stage = "model"
        ops.phase_gate("model", 1)
        stage = "external_sigint"
        result["delivery"] = ops.signal_or_terminal()
        stage = "worker_result"
        result["worker_result"] = ops.collect()
        aggregate = result["worker_result"]
        if type(aggregate) is not dict or not base.metadata_equal(
            aggregate.get("preflight"), result["preflight"]
        ):
            raise base.OwnerRejected("worker_aggregate_inconsistent")
        outcome = aggregate["result"]
        delivery = result["delivery"]
        ready = result["worker_ready"]
        rules = result["rules"]
        if (
            type(delivery) is not dict
            or type(ready) is not dict
            or type(rules) is not dict
        ):
            raise base.OwnerRejected("signal_delivery_unknown")
        target = ControllerIdentity.from_reference(delivery.get("target_reference"))
        binding = rules.get("binding")
        if (
            type(binding) is not dict
            or target.pid != ready.get("pid")
            or target.cgroup_device != binding.get("cgroup_device")
            or target.cgroup_inode != binding.get("cgroup_inode")
        ):
            raise base.OwnerRejected("signal_target_unknown")
        if delivery.get("marker_reference") is not None:
            contract.validate_marker(
                delivery["marker_reference"],
                run_id=case.run_id,
                fingerprint=case.case_fingerprint,
            )
        if (
            reconcile_delivery(
                delivery,
                aggregate["case"]["signal"],
                normal_complete=aggregate["case"]["normal_candidate_validated"],
            )
            != outcome
        ):
            raise base.OwnerRejected("signal_delivery_unknown")
        stage = "exit_gate"
        ops.phase_gate("exit", 7)
        stage = "exit_wait"
        ops.wait_exit()
        successful = True
    except BaseException:
        result.update(failure_stage=stage, failure_reason="signal_owner_unknown")
    finally:
        try:
            result["exit_diagnostics"] = dict(ops.exit_metadata)
        except BaseException:
            successful = False
            result["exit_diagnostics"] = {"integrity": "unknown"}
        if installed:
            try:
                with base.cleanup_signals():
                    restored = ops.restore()
                if not base.metadata_equal(
                    restored,
                    {
                        "result": "host_policy_restored",
                        "global_resolver_unchanged": True,
                        "ledger_retained": True,
                        "table_absent": True,
                        "unit_absent": True,
                    },
                ):
                    raise base.OwnerRejected("restoration_unknown")
                result["restoration"] = restored
            except BaseException:
                successful = False
                result["restoration_error"] = "restoration_unknown"
            result["restoration_stage"], result["resolver_check"] = (
                base.restoration_metadata(ops, case.run_id)
            )
        if reserved:
            try:
                db = ops.database_restoration()
                journal = ops.selection_journal()
                (
                    result["database_selection_restoration"],
                    result["selection_journal"],
                ) = db, journal
                aggregate = result["worker_result"]
                if successful and (
                    not base.metadata_equal(
                        db,
                        {
                            "result": "original_selection_restored",
                            "append_only_history_retained": True,
                            "source": "trusted_worker_public_API_CAS",
                        },
                    )
                    or type(journal) is not dict
                    or journal.get("completeness") != "captured"
                    or type(aggregate) is not dict
                    or not base.metadata_equal(
                        journal.get("entries"), aggregate.get("selection_journal")
                    )
                ):
                    successful = False
                    result["database_evidence_error"] = "live_selection_restore_unknown"
            except BaseException:
                successful = False
                result["database_evidence_error"] = "live_selection_restore_unknown"
            if successful:
                try:
                    with base.cleanup_signals():
                        artifacts = ops.finish()
                    if not base.metadata_equal(
                        artifacts,
                        {
                            "result": "successful_artifacts_removed",
                            "ledger_retained": True,
                        },
                    ):
                        raise base.OwnerRejected("artifact_cleanup_unknown")
                    result["artifacts"] = artifacts
                    result["result"] = outcome + "_and_restored"
                except BaseException:
                    result.update(
                        failure_stage="artifacts",
                        failure_reason="artifact_cleanup_unknown",
                    )
        try:
            ops.close_sender()
        except BaseException:
            result.update(
                result="unknown", sender_close_error="signal_descriptor_close_unknown"
            )
        if reserved:
            try:
                ops.write_ledger(result)
            except BaseException:
                result.update(result="unknown", ledger_error="permanent_result_unknown")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Owner-only single external SIGINT E01"
    )
    parser.add_argument("--expected-manifest-sha", required=True)
    args = parser.parse_args()
    case = None
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        root = Path(__file__).absolute().parent
        loaded, _, _ = contract.verify_installation(root, args.expected_manifest_sha)
        case = cast(contract.Case, loaded)

        def interrupted(_sig: int, _frame: object) -> None:
            raise KeyboardInterrupt

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, interrupted)
        value = run_owner(case, LiveOperations(case, args.expected_manifest_sha))
    except BaseException:
        value = {
            "scope": contract.SCOPE,
            "run_id": case.run_id if case else None,
            "result": "unknown",
            "failure_reason": "owner_bootstrap_unknown",
        }
    outcome = value.get("result")
    good = case is not None and outcome in {
        "observed_expected_and_restored",
        "not_triggered_and_restored",
    }
    envelope = {
        "scope": "h1_owner_automation_only",
        "run_id": case.run_id if case else None,
        "manifest_sha256": args.expected_manifest_sha,
        "owner_result": outcome if good else "unknown",
        "preflight_result": value,
    }
    print(json.dumps(envelope, sort_keys=True))
    return 0 if good else 1
