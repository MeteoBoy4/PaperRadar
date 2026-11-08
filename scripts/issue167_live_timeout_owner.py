"""Owner-only T1 duplex switch and strict recovery; import has no host effects."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import resource
import signal
import stat
import time
import types
import zipfile
from pathlib import Path
from typing import Any, Protocol, cast

from scripts import issue167_live_owner as previous_owner
from scripts import issue167_live_timeout_case as contract
from scripts import issue167_live_timeout_filter as filtering
from scripts import issue167_resolver_owner as base


def finite(value: object) -> bool:
    return (
        (type(value) is int or type(value) is float)
        and math.isfinite(value)
        and value >= 0
    )


def reconcile_cut(
    delivery: object, observed: object, *, worker_outcome: object, fingerprint: str
) -> str:
    """A timeout is evidence only with a complete timely bidirectional DROP."""
    contract.validate_timeout(observed, run_id=contract.RUN, fingerprint=fingerprint)
    if type(delivery) is not dict or set(delivery) != {
        "category",
        "sequence",
        "attempted_count",
        "completed_count",
        "marker_reference",
        "intent_monotonic",
        "confirmed_monotonic",
        "before_counts",
        "after_counts",
        "target_reference",
    }:
        raise contract.CaseRejected("timeout_switch_unknown")
    if (
        delivery["category"] != "project_duplex_drop"
        or type(delivery["sequence"]) is not int
        or delivery["sequence"] != 1
    ):
        raise contract.CaseRejected("timeout_switch_unknown")
    for name in ("attempted_count", "completed_count"):
        if type(delivery[name]) is not int or delivery[name] not in {0, 1}:
            raise contract.CaseRejected("timeout_switch_unknown")
    if delivery["attempted_count"] != delivery["completed_count"]:
        raise contract.CaseRejected("timeout_switch_unknown")
    assert isinstance(observed, dict)
    if delivery["attempted_count"] == 0:
        if (
            any(
                delivery[k] is not None
                for k in (
                    "marker_reference",
                    "intent_monotonic",
                    "confirmed_monotonic",
                    "before_counts",
                    "after_counts",
                    "target_reference",
                )
            )
            or worker_outcome != "not_triggered"
        ):
            raise contract.CaseRejected("timeout_switch_unknown")
        return "not_triggered"
    marker = contract.validate_marker(
        delivery["marker_reference"], run_id=contract.RUN, fingerprint=fingerprint
    )
    if not base.metadata_equal(marker, observed["marker"]):
        raise contract.CaseRejected("timeout_switch_unknown")
    target = delivery["target_reference"]
    if (
        type(target) is not dict
        or set(target) != {"pid", "starttime", "cgroup_device", "cgroup_inode"}
        or any(type(v) is not int or v <= 0 for v in target.values())
        or target["pid"] <= 1
    ):
        raise contract.CaseRejected("timeout_target_unknown")
    before = filtering.Counts.from_dict(delivery["before_counts"])
    after = filtering.Counts.from_dict(delivery["after_counts"])
    after.require_at_least(before)
    after.require_no_unexpected()
    intent, confirmed = delivery["intent_monotonic"], delivery["confirmed_monotonic"]
    if (
        not finite(intent)
        or not finite(confirmed)
        or not marker["observed_monotonic"] <= intent <= confirmed
    ):
        raise contract.CaseRejected("timeout_switch_unknown")
    if worker_outcome == "not_triggered":
        return "not_triggered"
    if worker_outcome != "observed_expected" or not (
        observed["public_reason"] == "timeout"
        and observed["public_elapsed_seconds"] >= 300
        and observed["public_started_monotonic"] <= intent
        and intent < observed["public_started_monotonic"] + 300
        and confirmed < observed["public_started_monotonic"] + 300
        and confirmed <= observed["public_returned_monotonic"]
        and after.dropped_in > before.dropped_in
        and after.dropped_out > before.dropped_out
        and after.byte_counts[2] > before.byte_counts[2]
        and after.byte_counts[3] > before.byte_counts[3]
    ):
        raise contract.CaseRejected("timeout_condition_unknown")
    return "observed_expected"


def controller_starttime(pid: int) -> int:
    if type(pid) is not int or pid <= 1:
        raise base.OwnerRejected("timeout_target_unknown")
    with Path(f"/proc/{pid}/stat").open("rb") as source:
        raw = source.read(8193)
    try:
        if len(raw) > 8192 or int(raw.split(b" ", 1)[0]) != pid:
            raise ValueError
        result = int(raw.rsplit(b") ", 1)[1].split()[19])
        if result <= 0:
            raise ValueError
        return result
    except (ValueError, IndexError):
        raise base.OwnerRejected("timeout_target_unknown") from None


class LiveOperations(previous_owner.LiveOperations):
    case: Any
    contract: Any

    def __init__(self, case: contract.Case, sha: str) -> None:
        base.LiveOperations.__init__(self, case, contract, sha)
        self.filter_plan = filtering.Plan(case.run_id)
        self.duplex_counts = filtering.Counts()
        self.exit_baseline: filtering.Counts | None = None
        self.current_phase = "deny"
        self.phase_reference: Any = None
        self.phase_references: list[Any] = []
        self.switch_uncertain = False
        self.exit_metadata = previous_owner.new_exit_metadata()
        self.started = False
        self.control_directories: dict[Path, tuple[int, int]] = {}
        self.contract = types.SimpleNamespace(
            **{k: getattr(contract, k) for k in dir(contract) if not k.startswith("__")}
        )
        self.contract.read_metadata = self._read_metadata
        self.delivery: dict[str, Any] = {
            "category": "project_duplex_drop",
            "sequence": 1,
            "attempted_count": 0,
            "completed_count": 0,
            "marker_reference": None,
            "intent_monotonic": None,
            "confirmed_monotonic": None,
            "before_counts": None,
            "after_counts": None,
            "target_reference": None,
        }

    def reserve(self) -> None:
        super().reserve()
        for path in (
            self.case.install_root,
            self.case.runtime_root,
            self.case.worker_root,
        ):
            info = path.lstat()
            self.control_directories[path] = (info.st_dev, info.st_ino)

    def _read_metadata(
        self, path: Path, *, owner: int = 0, limit: int = 131072
    ) -> object:
        """Pin each fixed ancestor and the complete final metadata descriptor."""
        if (
            type(limit) is not int
            or not 0 < limit <= 8 * 1024 * 1024
            or path.parent not in self.control_directories
            or path.name in {"", ".", ".."}
        ):
            raise base.OwnerRejected("metadata_path_unknown")
        descriptors = []
        try:
            fd = os.open(
                "/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            descriptors.append(fd)
            current = Path("/")
            for name in path.parent.parts[1:]:
                fd = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=fd,
                )
                descriptors.append(fd)
                current = current / name
                info = os.fstat(fd)
                expected_uid = self.case.uid if current == self.case.worker_root else 0
                if (
                    info.st_uid != expected_uid
                    or info.st_gid != expected_uid
                    or info.st_mode & 0o022
                ):
                    raise base.OwnerRejected("metadata_ancestor_unknown")
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self.control_directories[path.parent]:
                raise base.OwnerRejected("metadata_ancestor_unknown")
            final = os.open(
                path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=fd,
            )
            descriptors.append(final)
            before = os.fstat(final)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != owner
                or before.st_gid != owner
                or before.st_nlink != 1
                or before.st_mode & 0o022
                or before.st_size > limit
            ):
                raise base.OwnerRejected("metadata_file_unknown")
            chunks = []
            total = 0
            while True:
                chunk = os.read(final, min(65536, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    raise base.OwnerRejected("metadata_size_unknown")
            after = os.fstat(final)

            def fields(x: os.stat_result) -> tuple[int, ...]:
                return (
                    x.st_dev,
                    x.st_ino,
                    x.st_size,
                    x.st_mtime_ns,
                    x.st_ctime_ns,
                    x.st_mode,
                    x.st_uid,
                    x.st_gid,
                    x.st_nlink,
                )

            if total != before.st_size or fields(before) != fields(after):
                raise base.OwnerRejected("metadata_short_or_changed")

            def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
                result = {}
                for key, value in rows:
                    if key in result:
                        raise base.OwnerRejected("metadata_json_unknown")
                    result[key] = value
                return result

            def constant(_value: str) -> Any:
                raise base.OwnerRejected("metadata_json_unknown")

            try:
                return json.loads(
                    b"".join(chunks), object_pairs_hook=pairs, parse_constant=constant
                )
            except (ValueError, UnicodeError):
                raise base.OwnerRejected("metadata_json_unknown") from None
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

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
            if type(terminal) is dict and terminal.get("result") == "unknown":
                raise base.OwnerRejected("worker_terminated_unknown")
            time.sleep(0.02)
        raise base.OwnerRejected("worker_deadline_unknown")

    def start(self) -> None:
        if self.started:
            raise base.OwnerRejected("timeout_retry_forbidden")
        self.started = True
        super().start()

    def _identity(self, *, allow_absent: bool = False) -> None:
        if self.binding is None:
            raise base.OwnerRejected("table_ownership_unknown")
        p = Path("/sys/fs/cgroup") / self.plan.cgroup.lstrip("/")
        try:
            info = p.lstat()
        except FileNotFoundError:
            if allow_absent:
                return
            raise base.OwnerRejected("cgroup_identity_unknown") from None
        assert isinstance(self.binding, dict)
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (
            self.binding["cgroup_device"],
            self.binding["cgroup_inode"],
        ):
            raise base.OwnerRejected("cgroup_identity_unknown")

    def _verify(self, stage: str | None = None) -> Any:
        if self.switch_uncertain:
            raise base.OwnerRejected("timeout_switch_unknown")
        self._identity(allow_absent=stage == "post_stop")
        payload = self._snapshot()
        kwargs = {
            "phase": self.current_phase,
            "host_context": self.contract.current_host_context(),
            "binding": self.binding,
            "phase_reference": self.phase_reference,
            "previous_counts": self.duplex_counts,
        }
        baseline = getattr(self, "exit_baseline", None)
        if baseline is not None:
            kwargs["previous_counts"] = baseline
        verify = (
            filtering.verify_quiescent
            if stage == "post_stop" or baseline is not None
            else filtering.verify_state
        )
        counts = verify(self.filter_plan, payload, **kwargs)
        previous = self.duplex_counts
        self.duplex_counts = counts
        if stage == "before_exit":
            self.exit_baseline = counts
        if stage is not None:
            self.snapshots.append(
                {
                    "stage": stage,
                    "kernel_state": payload,
                    "binding": self.binding,
                    "phase": self.current_phase,
                    "phase_reference": self.phase_reference,
                    "counts": counts.to_dict(),
                    "compared_previous_counts": previous.to_dict(),
                }
            )
        return counts

    def exercise_rules(self) -> dict[str, object]:
        identity = self.guard.read_cgroup_identity(self.plan)
        self.create_uncertain = True
        self._run(
            (str(self.commands.tools["nft"]), "-f", "-"),
            filtering.render_create(self.filter_plan).encode(),
        )
        self.create_uncertain = False
        self.table_created = True
        payload = self._snapshot()
        if self.guard.read_cgroup_identity(self.plan) != identity:
            raise base.OwnerRejected("cgroup_identity_unknown")
        self.binding = filtering.make_binding(
            self.filter_plan, payload, identity, host_context=self.host
        )
        self.phase_reference = self.binding["initial_reference"]
        self.phase_references = [self.phase_reference]
        self._write(self.case.runtime_root / "table-binding.json", self.binding, 0o600)
        if self._verify("created_deny") != filtering.Counts():
            raise base.OwnerRejected("initial_packet_count_unknown")
        return {
            "scope": "project_duplex_input_output",
            "binding": self.binding,
            "snapshots": self.snapshots,
            "phase_references": self.phase_references,
            "counts_semantics": "packet_not_HTTP_or_DNS_query_count",
        }

    def _switch(self, phase: str) -> None:
        self._identity()
        self.switch_uncertain = True
        renderer = (
            filtering.render_allow if phase == "allow" else filtering.render_stall
        )
        self._run(
            (str(self.commands.tools["nft"]), "-f", "-"),
            renderer(self.filter_plan).encode(),
        )
        payload = self._snapshot()
        ref = filtering.capture_phase(
            self.filter_plan,
            payload,
            phase=phase,
            host_context=self.contract.current_host_context(),
            binding=self.binding,
            previous_reference=self.phase_reference,
            previous_counts=self.duplex_counts,
        )
        self.current_phase = phase
        self.phase_reference = ref
        self.phase_references.append(ref)
        self.switch_uncertain = False
        self._verify("transaction_" + phase)

    def activate(self) -> None:
        self._switch("allow")

    def preflight_result(self) -> dict[str, object]:
        result = contract.validate_preflight(self._wait("preflight-result.json"))
        if self._verify("preauthentication_complete") != filtering.Counts():
            raise base.OwnerRejected("preauthentication_packet_unknown")
        return result

    def auth_ready(self, sequence: int) -> None:
        if sequence != 1 or not base.metadata_equal(
            self._wait("auth-ready-1.json"),
            {
                "run_id": self.case.run_id,
                "sequence": 1,
                "auth_cli_completed": True,
                "logical_refresh_plan": contract.AUTH_REFRESH_PLAN,
            },
        ):
            raise base.OwnerRejected("auth_metadata_unknown")
        self._verify("auth_complete_1")

    def _target(self) -> dict[str, int]:
        state = self.commands.unit_state()
        if (
            self.ready_metadata is None
            or state.pid != self.ready_metadata["pid"]
            or state.pid not in self.phase.read_cgroup_state(self.plan).pids
        ):
            raise base.OwnerRejected("timeout_target_unknown")
        self._identity()
        identity = self.guard.read_cgroup_identity(self.plan)
        return {
            "pid": state.pid,
            "starttime": controller_starttime(state.pid),
            "cgroup_device": identity[0],
            "cgroup_inode": identity[1],
        }

    def stall_or_terminal(self) -> dict[str, object]:
        deadline = min(self.deadline, time.monotonic() + 360)
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
                    raise base.OwnerRejected("timeout_switch_unknown")
                return dict(self.delivery)
            try:
                marker = contract.validate_marker(
                    self.contract.read_metadata(
                        self.case.worker_root / "timeout-ready.json",
                        owner=self.case.uid,
                    ),
                    run_id=self.case.run_id,
                    fingerprint=self.case.case_fingerprint,
                )
            except FileNotFoundError:
                time.sleep(0.02)
                continue
            self.contract.verify_installation(self.case.install_root, self.manifest_sha)
            target = self._target()
            before = self._verify("before_duplex_stall")
            intent = time.monotonic()
            self.delivery.update(
                attempted_count=1,
                marker_reference=marker,
                intent_monotonic=intent,
                before_counts=before.to_dict(),
                target_reference=target,
            )
            self._write(
                self.case.runtime_root / "timeout-switch-intent.json",
                {"scope": contract.SCOPE, "run_id": self.case.run_id, **self.delivery},
                0o600,
            )
            if self._target() != target:
                raise base.OwnerRejected("timeout_target_unknown")
            self._switch("stall")
            self.delivery.update(
                completed_count=1,
                confirmed_monotonic=time.monotonic(),
                after_counts=self.duplex_counts.to_dict(),
            )
            return dict(self.delivery)
        raise base.OwnerRejected("timeout_window_unknown")

    def collect(self) -> dict[str, object]:
        value = cast(dict[str, Any], base.LiveOperations.collect(self))
        self._verify("before_exit")
        row = value["case"]
        for phase in ("before", "after"):
            checkpoint = self.contract.read_metadata(
                self.case.worker_root / f"auth-metadata-1-{phase}.json",
                owner=self.case.uid,
                limit=32768,
            )
            if not base.metadata_equal(checkpoint, row["persistent_auth"][phase]):
                raise base.OwnerRejected("timeout_auth_observation_unknown")
        checkpoint = self.contract.read_metadata(
            self.case.worker_root / "case-result-1.json", owner=self.case.uid
        )
        if not base.metadata_equal(checkpoint, row):
            raise base.OwnerRejected("worker_aggregate_inconsistent")
        if self.delivery["completed_count"] == 1:
            self.delivery["after_counts"] = self.duplex_counts.to_dict()
        reconcile_cut(
            self.delivery,
            row["timeout"],
            worker_outcome=value["result"],
            fingerprint=self.case.case_fingerprint,
        )
        filtering.verify_references(
            self.filter_plan,
            self.phase_references,
            host_context=self.host,
            binding=self.binding,
        )
        return value

    def finish(self) -> dict[str, object]:
        cleanup = importlib.import_module("scripts.issue167_live_timeout_cleanup")
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
            "timeout-switch-intent.json",
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
            "timeout-ready.json",
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
                    raise base.OwnerRejected("timeout_materials_unknown")
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


class Operations(Protocol):
    exit_metadata: dict[str, object]
    delivery: dict[str, Any]

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
    def stall_or_terminal(self) -> dict[str, object]: ...
    def collect(self) -> dict[str, object]: ...
    def wait_exit(self) -> None: ...
    def restore(self) -> dict[str, object]: ...
    def finish(self) -> dict[str, object]: ...
    def write_ledger(self, value: object) -> None: ...
    def database_restoration(self) -> dict[str, object]: ...
    def selection_journal(self) -> dict[str, object]: ...


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
        stage = "duplex_stall"
        result["delivery"] = ops.stall_or_terminal()
        stage = "worker_result"
        result["worker_result"] = ops.collect()
        result["delivery"] = dict(ops.delivery)
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
            raise base.OwnerRejected("timeout_switch_unknown")
        target = delivery.get("target_reference")
        if delivery.get("attempted_count") == 1:
            binding = rules.get("binding")
            if (
                type(target) is not dict
                or type(binding) is not dict
                or target.get("pid") != ready.get("pid")
                or target.get("cgroup_device") != binding.get("cgroup_device")
                or target.get("cgroup_inode") != binding.get("cgroup_inode")
            ):
                raise base.OwnerRejected("timeout_target_unknown")
        if (
            reconcile_cut(
                delivery,
                aggregate["case"]["timeout"],
                worker_outcome=outcome,
                fingerprint=case.case_fingerprint,
            )
            != outcome
        ):
            raise base.OwnerRejected("timeout_switch_unknown")
        stage = "exit_gate"
        ops.phase_gate("exit", 7)
        stage = "exit_wait"
        ops.wait_exit()
        successful = True
    except BaseException:
        result.update(failure_stage=stage, failure_reason="timeout_owner_unknown")
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
        if reserved:
            try:
                ops.write_ledger(result)
            except BaseException:
                result.update(result="unknown", ledger_error="permanent_result_unknown")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Owner-only T1 project duplex timeout")
    parser.add_argument("--expected-manifest-sha", required=True)
    args = parser.parse_args()
    case = None
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        loaded, _, _ = contract.verify_installation(
            Path(__file__).absolute().parent, args.expected_manifest_sha
        )
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
    print(
        json.dumps(
            {
                "scope": "h1_owner_automation_only",
                "run_id": case.run_id if case else None,
                "manifest_sha256": args.expected_manifest_sha,
                "owner_result": outcome if good else "unknown",
                "preflight_result": value,
            },
            sort_keys=True,
        )
    )
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
