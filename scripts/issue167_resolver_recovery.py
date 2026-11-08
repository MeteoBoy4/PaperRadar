"""Fixed, owner-reviewed recovery only; never reruns the original H1 case."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import resource
import stat
import sys
import types
from pathlib import Path
from typing import Protocol

RUN = "c591eb6ad204"
ROOT = Path("/home/paperradar-probes/issue167-" + RUN)
CORE = "cf1c22635aacc842c0cea99cac7c6901a6093981ef2023b31ecd169e77a2f889"
LEDGER = Path("/var/lib/paperradar/probe-runs/issue167-" + RUN + ".json")
LEDGER_SHA = "22d174ef487684a5278d09796ebd495239e7fbb83b3a3b5a86c60c02ab999330"
BINDING_SHA = "96c0998f0d4db4c3a628346e8166cdafd67d9b94e9d57fe25df06d4560a2781c"
UNIT_SHA = "b98de2a517edde5abf450bf10cc7449e9c60e712934dbb0c074cf8ff2c6c9dcb"


class RecoveryRejected(ValueError):
    """Controlled reason, without external exception text."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_record(
    path: Path, *, owner: int = 0, limit: int = 65536, mode: int | None = None
) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as source:
            before = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != owner
                or before.st_nlink != 1
                or before.st_mode & 0o022
                or (mode is not None and stat.S_IMODE(before.st_mode) != mode)
                or before.st_size > limit
            ):
                raise RecoveryRejected("recovery_metadata_unknown")
            raw = source.read(limit + 1)
            after = os.fstat(source.fileno())
        if len(raw) > limit or (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise RecoveryRejected("recovery_metadata_changed")
        return raw
    except OSError:
        raise RecoveryRejected("recovery_metadata_unknown") from None


def protected(path: Path, *, directory: bool = False) -> None:
    for item in (path, *path.parents):
        info = item.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise RecoveryRejected("root_protection_unknown")
    if directory and not stat.S_ISDIR(path.lstat().st_mode):
        raise RecoveryRejected("root_protection_unknown")


class Operations(Protocol):
    def inspect(self) -> None: ...
    def remove_table_if_bound(self) -> None: ...
    def remove_unit(self) -> None: ...
    def verify(self) -> None: ...


def recover(ops: Operations, progress: dict[str, str]) -> dict[str, object]:
    for stage, action in (
        ("inspect", ops.inspect),
        ("table", ops.remove_table_if_bound),
        ("unit", ops.remove_unit),
        ("verify", ops.verify),
    ):
        progress["stage"] = stage
        action()
        progress["last_completed_stage"] = stage
    return {
        "scope": "fixed_resolver_case_recovery_only",
        "run_id": RUN,
        "restoration_result": "project_resources_removed",
        "original_experiment_result": "unknown",
        "original_global_resolver_baseline": "unavailable_not_reconstructed",
        "original_ledger_unchanged": True,
        "code_runtime_retained": True,
        "network_operations": 0,
        "synthetic_reexecs": 0,
        "node_pi": False,
        "no_retry": True,
    }


class RootOperations:
    def __init__(self) -> None:
        if os.geteuid() != 0:
            raise RecoveryRejected("owner_root_required")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        protected(ROOT, directory=True)
        raw = read_record(ROOT / "manifest.json")
        if digest(raw) != CORE:
            raise RecoveryRejected("approved_core_changed")
        manifest = json.loads(raw)
        module_path = ROOT / "issue167_resolver_case.py"
        if digest(read_record(module_path)) != manifest["members"][module_path.name]:
            raise RecoveryRejected("approved_source_changed")
        package = types.ModuleType("scripts")
        package.__path__ = [str(ROOT)]
        sys.modules["scripts"] = package
        self.contract = importlib.import_module("scripts.issue167_resolver_case")
        self.case, tools, _sha = self.contract.verify_installation(ROOT, CORE)
        if self.case.run_id != RUN:
            raise RecoveryRejected("case_identity_changed")
        self.guard = importlib.import_module("scripts.issue167_h1_guardian")
        self.owner = importlib.import_module("scripts.issue167_h1_owner_ops")
        self.phase = importlib.import_module("scripts.issue167_h1_phase")
        self.egress = importlib.import_module("scripts.issue167_service_egress")
        self.plan = self.case.base_plan()
        self.commands = self.guard.Commands(self.plan, tools)
        self.host = self.contract.current_host_context()
        self.profile = self.egress.FrozenEgress.from_profile(
            self.plan,
            read_record(ROOT / "profile.json"),
            self.case.profile_sha256,
            self.host,
        )
        protected(LEDGER)
        raw = read_record(LEDGER, mode=0o600)
        if digest(raw) != LEDGER_SHA:
            raise RecoveryRejected("original_ledger_changed")
        original = json.loads(raw)
        if (
            original["scope"] != "h1_resolver_window_no_network"
            or original["run_id"] != RUN
            or original["result"] != "unknown"
        ):
            raise RecoveryRejected("original_ledger_changed")
        protected(self.case.runtime_root, directory=True)
        raw_binding = read_record(
            self.case.runtime_root / "table-binding.json", limit=8192, mode=0o600
        )
        if digest(raw_binding) != BINDING_SHA:
            raise RecoveryRejected("original_binding_changed")
        self.binding = json.loads(raw_binding)
        if self.binding != original["rules"]["binding"]:
            raise RecoveryRejected("original_binding_changed")
        last = original["rules"]["snapshots"][-1]
        if last["stage"] != "post_stop" or self.egress.verify_state(
            self.profile,
            last["kernel_state"],
            enabled=True,
            host_context=self.host,
            binding=self.binding,
        ) != (0, 0):
            raise RecoveryRejected("original_binding_changed")

    def state(self, *, removed: bool) -> None:
        raw = self.commands._run(
            (
                str(self.commands.tools["systemctl"]),
                "show",
                self.case.unit,
                "--property=LoadState,ActiveState,SubState,MainPID,ControlGroup",
                "--no-pager",
            )
        )
        rows = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
        values = dict(rows)
        expected = {
            "LoadState": "not-found" if removed else "loaded",
            "ActiveState": "inactive",
            "SubState": "dead",
            "MainPID": "0",
            "ControlGroup": "",
        }
        if len(rows) != len(values) or values != expected:
            raise RecoveryRejected("stopped_scope_changed")
        state = self.phase.read_cgroup_state(self.plan, allow_absent=True)
        if state.exists or state.pids:
            raise RecoveryRejected("cgroup_not_absent")

    def inspect(self) -> None:
        protected(self.owner.UNIT_ROOT / self.case.unit)
        if digest(read_record(self.owner.UNIT_ROOT / self.case.unit)) != UNIT_SHA:
            raise RecoveryRejected("unit_bytes_changed")
        if self.owner.check_units(self.plan, self.commands, must_be_absent=False) != {
            self.case.unit
        }:
            raise RecoveryRejected("unit_scope_changed")
        self.state(removed=False)

    def table_present(self) -> bool:
        return bool(
            self.owner.table_present(
                self.plan,
                self.commands._run(
                    (str(self.commands.tools["nft"]), "-j", "list", "tables")
                ),
            )
        )

    def remove_table_if_bound(self) -> None:
        self.inspect()
        if self.table_present():
            counts = self.egress.verify_state(
                self.profile,
                self.commands.snapshot(),
                enabled=True,
                host_context=self.contract.current_host_context(),
                binding=self.binding,
            )
            if counts != (0, 0):
                raise RecoveryRejected("table_counter_changed")
            self.commands.delete()
        if self.table_present():
            raise RecoveryRejected("table_still_present")

    def remove_unit(self) -> None:
        self.inspect()
        if self.table_present():
            raise RecoveryRejected("table_still_present")
        # Already inactive/dead: no reset-failed and no start/stop operation.
        (self.owner.UNIT_ROOT / self.case.unit).unlink()
        self.commands._run((str(self.commands.tools["systemctl"]), "daemon-reload"))

    def verify(self) -> None:
        if self.table_present():
            raise RecoveryRejected("table_still_present")
        self.owner.check_units(self.plan, self.commands, must_be_absent=True)
        self.state(removed=True)
        if digest(read_record(LEDGER, mode=0o600)) != LEDGER_SHA:
            raise RecoveryRejected("original_ledger_changed")
        protected(ROOT, directory=True)
        protected(self.case.runtime_root, directory=True)


def main() -> int:
    progress = {"stage": "bootstrap", "last_completed_stage": "none"}
    try:
        result = recover(RootOperations(), progress)
    except (Exception, KeyboardInterrupt):
        result = {
            "scope": "fixed_resolver_case_recovery_only",
            "run_id": RUN,
            "restoration_result": "unknown",
            "original_experiment_result": "unknown",
            "failure_stage": progress["stage"],
            "last_completed_stage": progress["last_completed_stage"],
            "no_retry": True,
        }
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
