"""One fixed H1 recovery exception; requires separate owner approval before use.

Import is inert. This is not a general numeric-cgroup normalization or a probe.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import resource
import stat
import sys
from pathlib import Path
from typing import Protocol

RUN_ID = "a840c6d21e97"
ROOT = Path("/home/paperradar-probes/issue167-" + RUN_ID)
MANIFEST_SHA = "64fa5e6b65119a0d60eee1f57565c41675887e4ebd7d4f266bfeaaf4c606fba7"
GUARDIAN_SHA = "11a99d5e9ef6b43f93226aa098dc5bc4973642f7457c8a341f63b5ee811077f2"
TABLE_SHA = "9721daafa30c44f0e4837f8c4b5694f1fdd99feaceac62df4fe8b37f67df5b9d"
RESULT_SHA = "5a4678ce2f82c6b208b3f9ecea15f2697b892ec2fb05c0c5737c23a326b9e5b7"
LEDGER_ROOT = Path("/var/lib/paperradar/probe-runs")
LEDGER = LEDGER_ROOT / ("issue167-" + RUN_ID + ".json")
RESERVATION = LEDGER_ROOT / ("issue167-" + RUN_ID + "-recovery-v1.json")


class RecoveryRejected(ValueError):
    """Controlled metadata failure, without external exception text."""


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def require_table(value: object) -> None:
    # Pins EVERYTHING: handles, numeric string 844648, counters, rules, metainfo.
    # Owner must explicitly accept that its historical path binding is unknown.
    if digest(value) != TABLE_SHA:
        raise RecoveryRejected("recovery_snapshot_changed")


class Operations(Protocol):
    def preflight(self) -> None: ...
    def reserve(self) -> None: ...
    def table(self) -> object: ...
    def delete_table(self) -> None: ...
    def remove_units(self) -> None: ...
    def verify_restored(self) -> None: ...


def recover(
    operations: Operations, progress: dict[str, str] | None = None
) -> dict[str, object]:
    """Never retry or call a probe; any failure leaves a consumed reservation."""
    state = progress if progress is not None else {}
    for stage, action in (
        ("preflight", operations.preflight),
        ("snapshot", lambda: require_table(operations.table())),
        ("reserve", operations.reserve),
        # Recheck scope and exact snapshot immediately before mutation.
        ("pre_mutation_scope", operations.preflight),
        ("pre_mutation_snapshot", lambda: require_table(operations.table())),
        ("delete_table", operations.delete_table),
        ("remove_units", operations.remove_units),
        ("verify_restored", operations.verify_restored),
    ):
        state["stage"] = stage
        action()
        state["last_completed_stage"] = stage
    return {
        "scope": "h1_fixed_recovery_exception_only",
        "run_id": RUN_ID,
        "restoration_result": "host_policy_restored",
        "experiment_result": "unknown",
        "original_numeric_binding": "unknown_owner_exception",
        "ledger_runtime_code_retained": True,
        "probe_attempts": 0,
        "auth_calls": 0,
        "model_calls": 0,
    }


def protected(path: Path, *, directory: bool = False) -> None:
    for item in (path, *path.parents):
        info = item.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise RecoveryRejected("protected_root_required")
    info = path.lstat()
    if directory:
        valid = stat.S_ISDIR(info.st_mode)
    else:
        valid = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    if not valid:
        raise RecoveryRejected("protected_root_required")


class RootOperations:
    def __init__(self) -> None:
        if os.geteuid() != 0:
            raise RecoveryRejected("owner_root_required")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        protected(ROOT, directory=True)
        # Verify before importing original, protected root-owned code.
        for name, expected in (
            ("manifest.json", MANIFEST_SHA),
            ("issue167_h1_guardian.py", GUARDIAN_SHA),
        ):
            path = ROOT / name
            protected(path)
            if path.stat().st_size > 65536:
                raise RecoveryRejected("bootstrap_too_large")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RecoveryRejected("bootstrap_changed")
        sys.path.insert(0, str(ROOT))
        self.guard = importlib.import_module("issue167_h1_guardian")
        # guardian imports phase only after full original manifest/host/tool check.
        self.phase = importlib.import_module("issue167_h1_phase")
        self.owner = importlib.import_module("issue167_h1_owner_ops")
        self.plan = self.phase.load_plan(ROOT / "plan.json")
        if self.plan.run_id != RUN_ID or self.plan.install_root != ROOT:
            raise RecoveryRejected("run_changed")
        self.commands = self.guard.Commands(self.plan, self.guard.bootstrap(ROOT))
        protected(LEDGER_ROOT, directory=True)
        protected(LEDGER)
        self.ledger_sha = hashlib.sha256(LEDGER.read_bytes()).hexdigest()

    def unit_states(self, *, restored: bool) -> None:
        for unit in (self.plan.unit, self.plan.guardian_unit):
            raw = self.commands._run(
                (
                    str(self.commands.tools["systemctl"]),
                    "show",
                    unit,
                    "--property=ActiveState,SubState,MainPID,ControlGroup",
                    "--no-pager",
                )
            )
            rows = [line.split("=", 1) for line in raw.decode().splitlines()]
            values = dict(rows)
            if (
                len(rows) != len(values)
                or set(values) != {"ActiveState", "SubState", "MainPID", "ControlGroup"}
                or values["MainPID"] != "0"
                or values["ControlGroup"] != ""
                or (values["ActiveState"], values["SubState"])
                not in (
                    {("inactive", "dead")}
                    if restored
                    else {("inactive", "dead"), ("failed", "failed")}
                )
            ):
                raise RecoveryRejected("unit_not_stopped")
        target = self.owner.GuardianTarget(
            self.plan.run_id,
            self.plan.uid,
            self.plan.gid,
            self.plan.port_a,
            self.plan.port_b,
            self.plan.blocked_port,
            self.plan.timeout_s,
        )
        for plan in (self.plan, target):
            state = self.phase.read_cgroup_state(plan, allow_absent=True)
            if state.exists or state.pids:
                raise RecoveryRejected("cgroup_not_absent")

    def preflight(self) -> None:
        loaded = self.owner.check_units(self.plan, self.commands, must_be_absent=False)
        if loaded != {self.plan.unit, self.plan.guardian_unit}:
            raise RecoveryRejected("installed_scope_changed")
        self.unit_states(restored=False)
        protected(self.plan.runtime_root, directory=True)
        for path in (self.plan.runtime_root / "guardian-result.json", LEDGER):
            protected(path)
            if digest(self.guard.read_json(path, owner=0)) != RESULT_SHA:
                raise RecoveryRejected("root_attestation_changed")
        go = self.plan.runtime_root / "go-a.json"
        protected(go)
        if digest(self.guard.read_json(go, owner=0)) != digest(
            {"phase": "a", "run_id": RUN_ID, "sequence": 1}
        ):
            raise RecoveryRejected("root_gate_changed")
        if hashlib.sha256(LEDGER.read_bytes()).hexdigest() != self.ledger_sha:
            raise RecoveryRejected("ledger_changed")

    def reserve(self) -> None:
        # O_EXCL makes this exact recovery attempt single use, including failures.
        descriptor = os.open(
            RESERVATION, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(
                json.dumps(
                    {
                        "run_id": RUN_ID,
                        "state": "reserved_unknown",
                        "scope": "h1_fixed_recovery_exception_only",
                        "table_sha256": TABLE_SHA,
                        "ledger_sha256": self.ledger_sha,
                    },
                    sort_keys=True,
                ).encode()
                + b"\n"
            )
            output.flush()
            os.fsync(output.fileno())
        parent = os.open(LEDGER_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)

    def table(self) -> object:
        return self.owner.decoded_json(
            self.commands._run(
                (
                    str(self.commands.tools["nft"]),
                    "-j",
                    "list",
                    "table",
                    "inet",
                    self.plan.table,
                )
            )
        )

    def delete_table(self) -> None:
        # Original delete.nft names only inet paperradar167_a840c6d21e97.
        self.commands.delete()

    def remove_units(self) -> None:
        # Do not unlink either unit unless deletion is independently observed.
        self.require_table_absent()
        self.owner.check_units(self.plan, self.commands, must_be_absent=False)
        self.unit_states(restored=False)
        # Clear only these loaded failed units before removing their fragments.
        self.commands._run(
            (
                str(self.commands.tools["systemctl"]),
                "reset-failed",
                self.plan.unit,
                self.plan.guardian_unit,
            )
        )
        for unit in (self.plan.unit, self.plan.guardian_unit):
            (self.owner.UNIT_ROOT / unit).unlink()
        self.commands._run((str(self.commands.tools["systemctl"]), "daemon-reload"))

    def require_table_absent(self) -> None:
        if self.owner.table_present(
            self.plan,
            self.commands._run(
                (str(self.commands.tools["nft"]), "-j", "list", "tables")
            ),
        ):
            raise RecoveryRejected("table_still_present")

    def verify_restored(self) -> None:
        self.require_table_absent()
        self.owner.check_units(self.plan, self.commands, must_be_absent=True)
        self.unit_states(restored=True)
        protected(LEDGER)
        if hashlib.sha256(LEDGER.read_bytes()).hexdigest() != self.ledger_sha:
            raise RecoveryRejected("ledger_changed")
        protected(ROOT, directory=True)
        protected(self.plan.runtime_root, directory=True)


def main() -> int:
    progress = {"stage": "bootstrap", "last_completed_stage": "none"}
    try:
        result = recover(RootOperations(), progress)
    except (Exception, KeyboardInterrupt):
        print(
            json.dumps(
                {
                    "scope": "h1_fixed_recovery_exception_only",
                    "run_id": RUN_ID,
                    "restoration_result": "unknown",
                    "experiment_result": "unknown",
                    "failure_reason": "fixed_recovery_incomplete",
                    "failure_stage": progress["stage"],
                    "last_completed_stage": progress["last_completed_stage"],
                    "no_retry": True,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
