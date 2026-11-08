"""Owner-executed no-network H1 resolver/window case. Import is inert."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import resource
import shutil
import signal
import stat
import sys
import tempfile
import time
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TextIO, cast

if TYPE_CHECKING:
    from scripts.issue167_resolver_case import Case


class OwnerRejected(ValueError):
    """Closed metadata reason, no external exception text."""


def metadata_equal(value: object, expected: object) -> bool:
    return json.dumps(value, sort_keys=True) == json.dumps(expected, sort_keys=True)


_RESTORATION_STAGES = frozenset(
    {
        "unit_scope_before_stop",
        "stop_unit",
        "cgroup_empty",
        "table_inventory",
        "table_verify",
        "table_delete",
        "table_absent",
        "unit_scope",
        "unit_state",
        "reset_failed",
        "reset_state",
        "unit_scope_final",
        "unit_unlink",
        "daemon_reload",
        "unit_absent",
        "resolver_baseline",
        "global_resolver_compare",
        "complete",
    }
)


def restoration_metadata(operations: object, run_id: str) -> tuple[str | None, object]:
    """Keep only closed diagnostics produced by the prospective owner code."""
    try:
        stage = getattr(operations, "restoration_stage", None)
        check = getattr(operations, "resolver_check", None)
    except Exception:
        return None, None
    if type(stage) is not str or stage not in _RESTORATION_STAGES:
        stage = None
    if (
        type(check) is not dict
        or set(check)
        != {"run_id", "before_sha256", "after_sha256", "comparison", "source"}
        or check.get("run_id") != run_id
        or check.get("source") != "root_baseline_file_and_post_restore_read"
        or any(
            type(check.get(k)) is not str
            or re.fullmatch(r"[a-f0-9]{64}", check[k]) is None
            for k in ("before_sha256", "after_sha256")
        )
        or check.get("comparison")
        != (
            "same"
            if check.get("before_sha256") == check.get("after_sha256")
            else "changed"
        )
    ):
        check = None
    return stage, check


class Operations(Protocol):
    def preflight(self) -> None: ...
    def reserve(self) -> None: ...
    def install(self) -> None: ...
    def start(self) -> None: ...
    def ready(self) -> dict[str, object]: ...
    def exercise_rules(self) -> dict[str, object]: ...
    def gate(self, sequence: int) -> None: ...
    def collect(self) -> dict[str, object]: ...
    def wait_exit(self) -> None: ...
    def restore(self) -> dict[str, object]: ...
    def finish(self) -> dict[str, object]: ...
    def write_ledger(self, value: object) -> None: ...


def run_owner(case: Case, operations: Operations) -> dict[str, object]:
    result: dict[str, object] = {
        "scope": "h1_resolver_window_no_network",
        "run_id": case.run_id,
        "result": "unknown",
        "worker_ready": None,
        "worker_result": None,
        "rules": None,
        "restoration": None,
        "artifacts": None,
        "network_operations": 0,
        "node_pi": False,
        "auth_calls": 0,
        "model_calls": 0,
        "case_binding": case.to_dict(),
        "restoration_stage": None,
        "resolver_check": None,
    }
    reserved = install_attempted = successful = False
    stage = "preflight"
    try:
        operations.preflight()
        stage = "reserve"
        operations.reserve()
        reserved = True
        stage = "install"
        install_attempted = True
        operations.install()
        stage = "start"
        operations.start()
        stage = "ready"
        result["worker_ready"] = operations.ready()
        stage = "rules"
        result["rules"] = operations.exercise_rules()
        stage = "gate_run"
        operations.gate(1)
        stage = "worker_result"
        result["worker_result"] = operations.collect()
        stage = "gate_exit"
        operations.gate(2)
        stage = "worker_exit"
        operations.wait_exit()
        successful = True
    except (KeyboardInterrupt, SystemExit):
        result.update(failure_stage=stage, failure_reason="owner_interrupted")
    except Exception:
        result.update(failure_stage=stage, failure_reason="owner_operation_unknown")
    finally:
        if install_attempted:
            try:
                with cleanup_signals():
                    restored = operations.restore()
                    if not metadata_equal(
                        restored,
                        {
                            "result": "host_policy_restored",
                            "global_resolver_unchanged": True,
                            "ledger_retained": True,
                            "table_absent": True,
                            "unit_absent": True,
                        },
                    ):
                        raise OwnerRejected("restoration_unknown")
                    result["restoration"] = restored
            except BaseException:
                successful = False
                result["restoration_error"] = "restoration_unknown"
            result["restoration_stage"], result["resolver_check"] = (
                restoration_metadata(operations, case.run_id)
            )
        if reserved:
            try:
                operations.write_ledger(result)
            except BaseException:
                successful = False
                result["ledger_error"] = "permanent_result_unknown"
    if successful:
        try:
            with cleanup_signals():
                artifacts = operations.finish()
                if not metadata_equal(
                    artifacts,
                    {
                        "result": "successful_artifacts_removed",
                        "ledger_retained": True,
                    },
                ):
                    raise OwnerRejected("artifact_cleanup_unknown")
                result["artifacts"] = artifacts
            result["result"] = "observed_expected_and_restored"
        except BaseException:
            result.update(
                failure_stage="finish", failure_reason="artifact_cleanup_unknown"
            )
        try:
            operations.write_ledger(result)
        except BaseException:
            result.update(result="unknown", ledger_error="permanent_result_unknown")
    return result


@contextmanager
def cleanup_signals() -> Iterator[None]:
    old = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for sig in old:
            signal.signal(sig, signal.SIG_IGN)
        yield
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


def bootstrap_entry(root: Path, expected: str) -> types.ModuleType:
    # Before importing any sibling, verify the entry parent and Case module using
    # only stdlib. The Case verifier then checks every member/tool/host binding.
    if os.geteuid() != 0:
        raise OwnerRejected("owner_root_required")
    for path in (root, *root.parents):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise OwnerRejected("root_installation_required")

    def read_entry(path: Path, limit: int) -> bytes:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != 0
                or info.st_nlink != 1
                or info.st_mode & 0o022
                or info.st_size > limit
            ):
                raise OwnerRejected("root_member_unknown")
            raw = source.read(limit + 1)
            if len(raw) > limit:
                raise OwnerRejected("root_member_unknown")
            return raw

    raw = read_entry(root / "manifest.json", 65536)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected:
        raise OwnerRejected("approved_manifest_changed")
    manifest = json.loads(raw)
    path = root / "issue167_resolver_case.py"
    if (
        hashlib.sha256(read_entry(path, 65536)).hexdigest()
        != manifest["members"][path.name]
    ):
        raise OwnerRejected("case_module_changed")
    package = types.ModuleType("scripts")
    package.__path__ = [str(root)]
    sys.modules["scripts"] = package
    contract = importlib.import_module("scripts.issue167_resolver_case")
    contract.verify_installation(root, expected)
    return contract


class LiveOperations:
    """No caller argv or arbitrary unit/table/path surface."""

    def __init__(
        self, case: Case, contract: types.ModuleType, manifest_sha: str
    ) -> None:
        self.case = case
        self.contract = contract
        self.manifest_sha = manifest_sha
        _case, tools, _sha = contract.verify_installation(
            case.install_root, manifest_sha
        )
        self.guard = importlib.import_module("scripts.issue167_h1_guardian")
        self.phase = importlib.import_module("scripts.issue167_h1_phase")
        self.owner = importlib.import_module("scripts.issue167_h1_owner_ops")
        self.egress = importlib.import_module("scripts.issue167_service_egress")
        self.plan = case.base_plan()
        self.commands = self.guard.Commands(self.plan, tools)
        self.host = contract.current_host_context()
        self.profile = self.egress.FrozenEgress.from_profile(
            self.plan,
            (case.install_root / "profile.json").read_bytes(),
            case.profile_sha256,
            self.host,
        )
        self.deadline = time.monotonic() + case.owner_timeout_s
        self.anchor: TextIO | None = None
        self.binding: object | None = None
        self.table_created = False
        self.create_uncertain = False
        self.enabled = False
        self.unit_owned = False
        self.global_resolver_sha: str | None = None
        self.restoration_stage: str | None = None
        self.resolver_check: dict[str, object] | None = None
        self.root_namespaces = {
            name: os.readlink(f"/proc/self/ns/{name}") for name in ("mnt", "pid")
        }
        self.ready_metadata: dict[str, object] | None = None
        self.worker_accepted = False
        self.restoration_accepted = False
        self.snapshots: list[dict[str, object]] = []

    def _run(self, argv: tuple[str, ...], data: bytes = b"") -> bytes:
        return cast(bytes, self.commands._run(argv, data))

    def _systemctl(self, *args: str) -> bytes:
        return self._run((str(self.commands.tools["systemctl"]), *args))

    def _resolver_digest(self) -> str:
        # Read only the fixed public host resolver; never write/restore it.
        fd = os.open("/etc/resolv.conf", os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise OwnerRejected("host_resolver_unknown")
            raw = source.read(16385)
            after = os.fstat(source.fileno())
        if len(raw) > 16384 or (
            before.st_dev,
            before.st_ino,
            before.st_mtime_ns,
            before.st_size,
        ) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size):
            raise OwnerRejected("host_resolver_unknown")
        return hashlib.sha256(raw).hexdigest()

    def preflight(self) -> None:
        self.contract.verify_installation(self.case.install_root, self.manifest_sha)
        unit = self.case.install_root / self.case.unit
        if unit.read_text() != self.contract.render_unit(self.case):
            raise OwnerRejected("unit_bytes_unknown")
        self.owner.check_units(self.plan, self.commands, must_be_absent=True)
        if self.case.runtime_root.exists() or self.case.runtime_root.is_symlink():
            raise OwnerRejected("runtime_already_present")
        ledger = self.owner.LEDGER_ROOT / f"issue167-{self.case.run_id}.json"
        if not self.owner.absent(ledger):
            raise OwnerRejected("case_already_consumed")
        if self.owner.table_present(
            self.plan,
            self._run((str(self.commands.tools["nft"]), "-j", "list", "tables")),
        ):
            raise OwnerRejected("table_already_present")
        self._run(
            (
                str(self.commands.tools["systemd_analyze"]),
                "verify",
                "--man=no",
                str(unit),
            )
        )
        self.global_resolver_sha = self._resolver_digest()

    def _write(self, path: Path, value: object, mode: int = 0o644) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w") as output:
                os.fchmod(output.fileno(), mode)
                json.dump(value, output, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, path, follow_symlinks=False)
        finally:
            Path(temporary).unlink(missing_ok=True)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def reserve(self) -> None:
        baseline = self._resolver_baseline_record()
        for directory in (self.owner.LEDGER_ROOT.parent, self.owner.LEDGER_ROOT):
            if self.owner.absent(directory):
                directory.mkdir(mode=0o755)
                directory.chmod(0o755)
            self.guard.protected_path(directory, directory=True)
        self.anchor = self.guard.claim_anchor(
            self.owner.LEDGER_ROOT / f"issue167-{self.case.run_id}.json",
            self.case.run_id,
        )
        self.case.runtime_root.mkdir(mode=0o700, exist_ok=False)
        self.case.runtime_root.chmod(0o755)
        self._write(self.case.runtime_root / "resolver-baseline.json", baseline, 0o600)
        self.case.worker_root.mkdir(mode=0o700)
        os.chown(self.case.worker_root, self.case.uid, self.case.gid)
        self.case.worker_root.chmod(0o700)
        self._write(
            self.case.runtime_root / "owner-namespaces.json",
            {"run_id": self.case.run_id, **self.root_namespaces},
        )

    def install(self) -> None:
        self.owner.check_units(self.plan, self.commands, must_be_absent=True)
        source = self.case.install_root / self.case.unit
        self.guard.protected_path(source)
        target = self.owner.UNIT_ROOT / self.case.unit
        fd = os.open(
            target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644
        )
        self.unit_owned = True
        with os.fdopen(fd, "wb") as output:
            output.write(source.read_bytes())
            output.flush()
            os.fsync(output.fileno())
        self._systemctl("daemon-reload")
        if self.owner.check_units(self.plan, self.commands, must_be_absent=False) != {
            self.case.unit
        }:
            raise OwnerRejected("unit_scope_unknown")

    def start(self) -> None:
        self._systemctl("start", self.case.unit)

    def _wait(self, name: str) -> object:
        if name not in {"ready.json", "worker-result.json"}:
            raise OwnerRejected("metadata_name_unknown")
        while time.monotonic() < self.deadline:
            try:
                return self.contract.read_metadata(
                    self.case.worker_root / name, owner=self.case.uid
                )
            except FileNotFoundError:
                time.sleep(0.05)
        raise OwnerRejected("worker_deadline_unknown")

    def ready(self) -> dict[str, object]:
        metadata = cast(
            dict[str, object],
            self.contract.validate_ready(self.case, self._wait("ready.json")),
        )
        state = self.commands.unit_state()
        if state.pid != metadata["pid"] or self.phase.read_cgroup_state(
            self.plan
        ).pids != {state.pid}:
            raise OwnerRejected("worker_cgroup_unknown")
        if (
            metadata["mount_namespace"] == self.root_namespaces["mnt"]
            or metadata["pid_namespace"] != self.root_namespaces["pid"]
        ):
            raise OwnerRejected("worker_namespace_unknown")
        self.ready_metadata = metadata
        return metadata

    def _snapshot(self) -> object:
        return self.commands.snapshot()

    def _verify(self, stage: str | None = None) -> tuple[int, int]:
        payload = self._snapshot()
        counts = cast(
            tuple[int, int],
            self.egress.verify_state(
                self.profile,
                payload,
                enabled=self.enabled,
                host_context=self.contract.current_host_context(),
                binding=self.binding,
            ),
        )
        if counts != (0, 0):
            raise OwnerRejected("unexpected_packet_count")
        if stage is not None:
            self.snapshots.append({"stage": stage, "kernel_state": payload})
        return counts

    def exercise_rules(self) -> dict[str, object]:
        identity = self.guard.read_cgroup_identity(self.plan)
        self.create_uncertain = True
        self._run(
            (str(self.commands.tools["nft"]), "-f", "-"),
            self.egress.render_create(self.profile).encode(),
        )
        self.create_uncertain = False
        self.table_created = True
        payload = self._snapshot()
        self.egress.verify_state(
            self.profile, payload, enabled=False, host_context=self.host
        )
        if self.guard.read_cgroup_identity(self.plan) != identity:
            raise OwnerRejected("cgroup_identity_unknown")
        self.binding = self.egress.make_binding(
            self.profile, payload, identity, host_context=self.host
        )
        self._write(self.case.runtime_root / "table-binding.json", self.binding, 0o600)
        self._verify("created_deny")
        for enabled, stage in (
            (True, "activated"),
            (False, "cleared"),
            (True, "reactivated"),
        ):
            renderer = (
                self.egress.render_activate if enabled else self.egress.render_clear
            )
            self._run(
                (str(self.commands.tools["nft"]), "-f", "-"),
                renderer(self.profile).encode(),
            )
            self.enabled = enabled
            self._verify(stage)
        return {
            "scope": "kernel_rule_structure_no_traffic",
            "switches": 3,
            "allowed_packets": 0,
            "rejected_packets": 0,
            "independent_cgroup_identity_bound": True,
            "binding": self.binding,
            "snapshots": self.snapshots,
            "namespace_context": {
                "source": "root_caller_self_and_bound_worker_self",
                "root_caller": self.root_namespaces,
                "worker": {
                    "mnt": self.ready_metadata["mount_namespace"]
                    if self.ready_metadata
                    else None,
                    "pid": self.ready_metadata["pid_namespace"]
                    if self.ready_metadata
                    else None,
                },
                "system_slice_prefix_bound": self.plan.cgroup.startswith(
                    "/system.slice/"
                ),
                "apport_source_sha256": self.case.apport_sha256,
                "collector_invoked": False,
                "new_crashes": 0,
            },
        }

    def gate(self, sequence: int) -> None:
        if sequence not in {1, 2}:
            raise OwnerRejected("gate_sequence_unknown")
        if self.ready_metadata is None:
            raise OwnerRejected("worker_identity_unknown")
        state = self.commands.unit_state()
        if state.pid != self.ready_metadata["pid"] or self.phase.read_cgroup_state(
            self.plan
        ).pids != {state.pid}:
            raise OwnerRejected("worker_cgroup_unknown")
        self._verify()
        self._write(
            self.case.runtime_root
            / ("gate-run.json" if sequence == 1 else "gate-exit.json"),
            {"run_id": self.case.run_id, "sequence": sequence},
        )

    def collect(self) -> dict[str, object]:
        value = cast(
            dict[str, object],
            self.contract.validate_result(self.case, self._wait("worker-result.json")),
        )
        if self.ready_metadata is None or any(
            value[key] != previous for key, previous in self.ready_metadata.items()
        ):
            raise OwnerRejected("worker_identity_changed")
        self._verify()
        self.worker_accepted = True
        return value

    def wait_exit(self) -> None:
        while time.monotonic() < self.deadline:
            if not self.phase.read_cgroup_state(self.plan, allow_absent=True).pids:
                raw = self._systemctl(
                    "show",
                    self.case.unit,
                    "--property=ActiveState,SubState,Result,ExecMainCode,ExecMainStatus,MainPID,ControlGroup",
                    "--no-pager",
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
                    if {k: v for k, v in state.items() if k != "ControlGroup"} == {
                        "ActiveState": "active",
                        "SubState": "exited",
                        "Result": "success",
                        "ExecMainCode": "1",
                        "ExecMainStatus": "0",
                        "MainPID": "0",
                    } and state["ControlGroup"] in {"", self.plan.cgroup}:
                        return
                    if (
                        state["ActiveState"] in {"failed", "inactive"}
                        or state["SubState"] == "exited"
                        or state["Result"]
                        not in {
                            "success",
                            "",
                        }
                    ):
                        raise OwnerRejected("worker_exit_unknown")
                except (UnicodeError, ValueError):
                    raise OwnerRejected("worker_exit_unknown") from None
            time.sleep(0.05)
        raise OwnerRejected("worker_exit_unknown")

    def _resolver_baseline_record(self) -> dict[str, object]:
        if (
            type(self.global_resolver_sha) is not str
            or re.fullmatch(r"[a-f0-9]{64}", self.global_resolver_sha) is None
        ):
            raise OwnerRejected("resolver_baseline_unknown")
        return {"run_id": self.case.run_id, "sha256": self.global_resolver_sha}

    def _stopped_unit_state(self) -> str:
        raw = self._systemctl(
            "show",
            self.case.unit,
            "--property=ActiveState,SubState,MainPID,ControlGroup",
            "--no-pager",
        )
        try:
            rows = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
            state = dict(rows)
            if (
                len(rows) != len(state)
                or set(state) != {"ActiveState", "SubState", "MainPID", "ControlGroup"}
                or state["MainPID"] != "0"
                or state["ControlGroup"] not in {"", self.plan.cgroup}
                or (state["ActiveState"], state["SubState"])
                not in {("inactive", "dead"), ("failed", "failed")}
            ):
                raise ValueError
        except (ValueError, UnicodeError):
            raise OwnerRejected("unit_stopped_state_unknown") from None
        if self.phase.read_cgroup_state(self.plan, allow_absent=True).pids:
            raise OwnerRejected("cgroup_not_empty")
        return str(state["ActiveState"])

    def restore(self) -> dict[str, object]:
        self.resolver_check = None
        self.restoration_stage = "unit_scope_before_stop"
        loaded = self.owner.check_units(self.plan, self.commands, must_be_absent=False)
        if loaded - {self.case.unit}:
            raise OwnerRejected("foreign_unit_scope")
        if self.case.unit in loaded:
            self.restoration_stage = "stop_unit"
            self._systemctl("stop", self.case.unit)
        self.restoration_stage = "cgroup_empty"
        if self.phase.read_cgroup_state(self.plan, allow_absent=True).pids:
            raise OwnerRejected("cgroup_not_empty")
        self.restoration_stage = "table_inventory"
        present = self.owner.table_present(
            self.plan,
            self._run((str(self.commands.tools["nft"]), "-j", "list", "tables")),
        )
        if present:
            if not self.table_created or self.create_uncertain or self.binding is None:
                raise OwnerRejected("table_ownership_unknown")
            self.restoration_stage = "table_verify"
            self._verify("post_stop")
            self.restoration_stage = "table_delete"
            self.commands.delete()
            self.table_created = False
        self.restoration_stage = "table_absent"
        if self.owner.table_present(
            self.plan,
            self._run((str(self.commands.tools["nft"]), "-j", "list", "tables")),
        ):
            raise OwnerRejected("table_still_present")
        self.restoration_stage = "unit_scope"
        self.owner.check_units(self.plan, self.commands, must_be_absent=False)
        if self.unit_owned:
            self.restoration_stage = "unit_state"
            if self._stopped_unit_state() == "failed":
                self.restoration_stage = "reset_failed"
                self._systemctl("reset-failed", self.case.unit)
                self.restoration_stage = "reset_state"
                if self._stopped_unit_state() != "inactive":
                    raise OwnerRejected("unit_reset_unknown")
            self.restoration_stage = "unit_scope_final"
            self.owner.check_units(self.plan, self.commands, must_be_absent=False)
            self.restoration_stage = "unit_unlink"
            (self.owner.UNIT_ROOT / self.case.unit).unlink()
            self.restoration_stage = "daemon_reload"
            self._systemctl("daemon-reload")
        self.restoration_stage = "unit_absent"
        self.owner.check_units(self.plan, self.commands, must_be_absent=True)
        self.restoration_stage = "resolver_baseline"
        expected_baseline = self._resolver_baseline_record()
        baseline_path = self.case.runtime_root / "resolver-baseline.json"
        try:
            info = baseline_path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise OwnerRejected("resolver_baseline_unknown")
            baseline = self.contract.read_metadata(baseline_path, owner=0, limit=1024)
        except (OSError, ValueError):
            raise OwnerRejected("resolver_baseline_unknown") from None
        if not metadata_equal(baseline, expected_baseline):
            raise OwnerRejected("resolver_baseline_unknown")
        self.restoration_stage = "global_resolver_compare"
        after_sha = self._resolver_digest()
        if (
            type(after_sha) is not str
            or re.fullmatch(r"[a-f0-9]{64}", after_sha) is None
        ):
            raise OwnerRejected("host_resolver_unknown")
        self.resolver_check = {
            "run_id": self.case.run_id,
            "before_sha256": self.global_resolver_sha,
            "after_sha256": after_sha,
            "comparison": "same"
            if self.global_resolver_sha == after_sha
            else "changed",
            "source": "root_baseline_file_and_post_restore_read",
        }
        if self.global_resolver_sha != after_sha:
            raise OwnerRejected("host_resolver_changed")
        self.restoration_accepted = True
        self.restoration_stage = "complete"
        return {
            "result": "host_policy_restored",
            "global_resolver_unchanged": True,
            "ledger_retained": True,
            "table_absent": True,
            "unit_absent": True,
        }

    def finish(self) -> dict[str, object]:
        if not self.worker_accepted or not self.restoration_accepted:
            raise OwnerRejected("unsuccessful_metadata_retained")
        self.owner.check_units(self.plan, self.commands, must_be_absent=True)
        if (
            self.phase.read_cgroup_state(self.plan, allow_absent=True).pids
            or self.table_created
            or self.create_uncertain
        ):
            raise OwnerRejected("artifacts_not_quiescent")
        if self.owner.table_present(
            self.plan,
            self._run((str(self.commands.tools["nft"]), "-j", "list", "tables")),
        ):
            raise OwnerRejected("table_still_present")
        if not shutil.rmtree.avoids_symlink_attacks:
            raise OwnerRejected("safe_removal_unavailable")
        points = self.owner.mountpoints(Path("/proc/self/mountinfo").read_text())
        for root in (self.case.runtime_root, self.case.install_root):
            self.guard.protected_path(root, directory=True)
            if any(point.is_relative_to(root) for point in points):
                raise OwnerRejected("artifact_mount_unknown")
        for root in (self.case.runtime_root, self.case.install_root):
            shutil.rmtree(root)
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        if self.anchor is None:
            raise OwnerRejected("permanent_anchor_missing")
        self.anchor.seek(0)
        self.anchor.truncate()
        json.dump(value, self.anchor, sort_keys=True)
        self.anchor.write("\n")
        self.anchor.flush()
        os.fsync(self.anchor.fileno())


def owner_envelope(
    case: Case | None, manifest_sha: str, inner: dict[str, object]
) -> dict[str, object]:
    success = (
        case is not None
        and inner.get("scope") == "h1_resolver_window_no_network"
        and inner.get("run_id") == case.run_id
        and inner.get("result") == "observed_expected_and_restored"
    )
    return {
        "scope": "h1_owner_automation_only",
        "run_id": case.run_id if case is not None else None,
        "manifest_sha256": manifest_sha
        if re.fullmatch(r"[a-f0-9]{64}", manifest_sha)
        else None,
        "owner_result": "observed_expected_and_restored" if success else "unknown",
        "preflight_result": inner,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Owner-only no-network H1 case")
    parser.add_argument("--expected-manifest-sha", required=True)
    args = parser.parse_args()
    case: Case | None = None
    try:
        root = Path(__file__).absolute().parent
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        contract = bootstrap_entry(root, args.expected_manifest_sha)
        case = contract.load_case(root / "plan.json")
        operations = LiveOperations(case, contract, args.expected_manifest_sha)

        def interrupted(_signum: int, _frame: object) -> None:
            raise KeyboardInterrupt

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, interrupted)
        result = run_owner(case, operations)
    except (Exception, KeyboardInterrupt):
        result = {
            "scope": "h1_resolver_window_no_network",
            "result": "unknown",
            "failure_reason": "owner_bootstrap_unknown",
        }
    envelope = owner_envelope(case, args.expected_manifest_sha, result)
    print(json.dumps(envelope, sort_keys=True))
    return 0 if envelope["owner_result"] == "observed_expected_and_restored" else 1


if __name__ == "__main__":
    raise SystemExit(main())
