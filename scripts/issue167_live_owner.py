"""Root-only lifecycle and gates; application/DB/token code is never imported."""

from __future__ import annotations

import argparse
import json
import re
import resource
import signal
import time
from pathlib import Path
from typing import Protocol, cast

from scripts import issue167_live_case as contract
from scripts import issue167_resolver_owner as base
from scripts import issue167_service_network_owner as network


def new_exit_metadata() -> dict[str, object]:
    return {
        "gate_checkpoint": "not_started",
        "gate_published": None,
        "wait_checkpoint": "not_started",
        "cgroup_empty": None,
        "manager": None,
        "failure_reason": None,
    }


def _failure_reason(error: BaseException) -> str:
    if isinstance(error, KeyboardInterrupt):
        return "owner_interrupted"
    if isinstance(error, SystemExit):
        return "owner_system_exit"
    if isinstance(error, base.OwnerRejected) and str(error) in {
        "worker_exit_unknown",
        "worker_aggregate_inconsistent",
        "gate_sequence_unknown",
        "worker_cgroup_unknown",
    }:
        return str(error)
    if isinstance(error, OSError):
        return "owner_os_error"
    return "owner_operation_unknown"


def _exit_state(raw: bytes, cgroup: str, expected_pid: object) -> dict[str, object]:
    """Closed projection only; never retain arbitrary manager output or PID/path."""
    try:
        if len(raw) > 8192:
            raise ValueError
        rows = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
        state = dict(rows)
        enums = {
            "ActiveState": {
                "active",
                "inactive",
                "failed",
                "activating",
                "deactivating",
                "reloading",
                "maintenance",
                "refreshing",
            },
            "SubState": {
                "running",
                "exited",
                "dead",
                "failed",
                "start-pre",
                "start",
                "start-post",
                "stop",
                "stop-sigterm",
                "stop-sigkill",
                "stop-post",
                "final-sigterm",
                "final-sigkill",
                "auto-restart",
                "reload",
                "condition",
                "cleaning",
            },
            "Result": {
                "",
                "success",
                "resources",
                "timeout",
                "exit-code",
                "signal",
                "core-dump",
                "watchdog",
                "start-limit-hit",
                "protocol",
                "oom-kill",
                "exec-condition",
                "assert",
                "dependency",
            },
        }
        if len(rows) != len(state) or set(state) != {
            *enums,
            "ExecMainCode",
            "ExecMainStatus",
            "MainPID",
            "ControlGroup",
        }:
            raise ValueError
        if any(state[key] not in allowed for key, allowed in enums.items()):
            raise ValueError
        for key, maximum in (
            ("ExecMainCode", 6),
            ("ExecMainStatus", 255),
            ("MainPID", 2**31 - 1),
        ):
            if (
                re.fullmatch(r"0|[1-9][0-9]{0,9}", state[key]) is None
                or int(state[key]) > maximum
            ):
                raise ValueError
        pid = int(state["MainPID"])
        return {
            **{key: state[key] for key in enums},
            "ExecMainCode": int(state["ExecMainCode"]),
            "ExecMainStatus": int(state["ExecMainStatus"]),
            "main_pid_zero": pid == 0,
            "main_pid_expected": type(expected_pid) is int and pid == expected_pid,
            "control_group_expected": state["ControlGroup"] == cgroup,
            "control_group_empty": state["ControlGroup"] == "",
        }
    except (UnicodeError, ValueError):
        raise base.OwnerRejected("worker_exit_unknown") from None


class LiveOperations(network.LiveOperations):
    def __init__(self, case: contract.Case, sha: str) -> None:
        base.LiveOperations.__init__(self, case, contract, sha)
        self.previous_counts = (0, 0)
        self.exit_metadata = new_exit_metadata()

    def _wait(self, name: str) -> object:
        if name not in {
            "ready.json",
            "preflight-result.json",
            "worker-result.json",
            *(f"auth-ready-{n}.json" for n in range(1, 7)),
            *(f"case-result-{n}.json" for n in range(1, 7)),
        }:
            raise base.OwnerRejected("metadata_name_unknown")
        allowance = (
            120
            if name == "ready.json" or name.startswith("auth-ready")
            else 360
            if name == "preflight-result.json" or name.startswith("case-result")
            else 90
        )
        deadline = min(self.deadline, time.monotonic() + allowance)
        next_manager = 0.0
        while time.monotonic() < deadline:
            try:
                return self.contract.read_metadata(
                    self.case.worker_root / name, owner=self.case.uid
                )
            except FileNotFoundError:
                pass
            if name != "worker-result.json":
                try:
                    terminal = self.contract.read_metadata(
                        self.case.worker_root / "worker-result.json",
                        owner=self.case.uid,
                    )
                except FileNotFoundError:
                    terminal = None
                if (
                    type(terminal) is dict
                    and terminal.get("run_id") == self.case.run_id
                    and terminal.get("result") == "unknown"
                ):
                    raise base.OwnerRejected("worker_terminated_unknown")
            if time.monotonic() >= next_manager:
                raw = self._systemctl(
                    "show",
                    self.case.unit,
                    "--property=ActiveState,SubState,MainPID",
                    "--no-pager",
                )
                try:
                    state = dict(
                        line.split("=", 1) for line in raw.decode("ascii").splitlines()
                    )
                    if set(state) != {"ActiveState", "SubState", "MainPID"}:
                        raise ValueError
                    if state["MainPID"] == "0" and (
                        state["ActiveState"] in {"inactive", "failed"}
                        or state["SubState"] == "exited"
                    ):
                        raise base.OwnerRejected("worker_terminated_unknown")
                except (ValueError, UnicodeError):
                    raise base.OwnerRejected("worker_state_unknown") from None
                next_manager = time.monotonic() + 1
            time.sleep(0.05)
        raise base.OwnerRejected("worker_deadline_unknown")

    def _systemctl(self, *args: str) -> bytes:
        if args != ("stop", self.case.unit):
            return super()._systemctl(*args)
        super()._systemctl("stop", "--no-block", self.case.unit)
        deadline = time.monotonic() + 70
        while time.monotonic() < deadline:
            try:
                self._stopped_unit_state()
                return b""
            except base.OwnerRejected:
                time.sleep(0.1)
        raise base.OwnerRejected("worker_stop_unknown")

    def selection_journal(self) -> dict[str, object]:
        rows = []
        try:
            for sequence in range(8):
                try:
                    value = self.contract.read_metadata(
                        self.case.worker_root / f"selection-{sequence}.json",
                        owner=self.case.uid,
                    )
                except FileNotFoundError:
                    break
                rows.append(
                    contract.project_journal_entry(
                        sequence, value, run_id=self.case.run_id
                    )
                )
            return {
                "source": "trusted_worker_control_journal_receipt_projection",
                "entries": rows,
                "completeness": "captured",
            }
        except (OSError, ValueError):
            return {
                "source": "trusted_worker_control_journal_receipt_projection",
                "entries": rows,
                "completeness": "unknown",
            }

    def database_restoration(self) -> dict[str, object]:
        expected = {
            "result": "original_selection_restored",
            "append_only_history_retained": True,
        }
        try:
            value = self.contract.read_metadata(
                self.case.worker_root / "worker-result.json", owner=self.case.uid
            )
            if (
                type(value) is dict
                and value.get("run_id") == self.case.run_id
                and base.metadata_equal(value.get("selection_restoration"), expected)
            ):
                return {**expected, "source": "trusted_worker_public_API_CAS"}
        except (OSError, ValueError):
            pass
        return {"result": "unknown", "source": "trusted_worker_public_API_CAS"}

    def phase_gate(self, category: str, sequence: int) -> None:
        if (
            category not in {"preflight", "auth", "model", "exit"}
            or type(sequence) is not int
            or (category in {"auth", "model"} and not 1 <= sequence <= 6)
            or (category == "preflight" and sequence != 0)
            or (category == "exit" and sequence != 7)
            or self.ready_metadata is None
        ):
            raise base.OwnerRejected("gate_sequence_unknown")
        state = self.commands.unit_state()
        if state.pid != self.ready_metadata["pid"] or self.phase.read_cgroup_state(
            self.plan
        ).pids != {state.pid}:
            raise base.OwnerRejected("worker_cgroup_unknown")
        self._verify()
        name = (
            f"gate-{category}-{sequence}.json"
            if category in {"auth", "model"}
            else f"gate-{category}.json"
        )
        path = self.case.runtime_root / name
        value = {"run_id": self.case.run_id, "sequence": sequence}
        if category != "exit":
            self._write(path, value)
            return
        self.exit_metadata["gate_checkpoint"] = "write_intent"
        try:
            self._write(path, value)
        except (Exception, KeyboardInterrupt, SystemExit):
            # Publication may precede a failing directory fsync. A matching
            # control file establishes publication only, never durability.
            try:
                published = self.contract.read_metadata(path, owner=0)
                self.exit_metadata["gate_published"] = (
                    True if base.metadata_equal(published, value) else None
                )
            except FileNotFoundError:
                self.exit_metadata["gate_published"] = False
            except (Exception, KeyboardInterrupt, SystemExit):
                self.exit_metadata["gate_published"] = None
            raise
        self.exit_metadata.update(gate_checkpoint="write_complete", gate_published=True)

    def wait_exit(self) -> None:
        # Same terminal predicate as base.LiveOperations.wait_exit. Diagnostics
        # add no alternative path to success, including when observation fails.
        self.exit_metadata["wait_checkpoint"] = "waiting"
        try:
            while time.monotonic() < self.deadline:
                self.exit_metadata["cgroup_empty"] = None
                empty = not self.phase.read_cgroup_state(
                    self.plan, allow_absent=True
                ).pids
                self.exit_metadata["cgroup_empty"] = empty
                if empty:
                    self.exit_metadata["manager"] = None
                    raw = self._systemctl(
                        "show",
                        self.case.unit,
                        "--property=ActiveState,SubState,Result,ExecMainCode,ExecMainStatus,MainPID,ControlGroup",
                        "--no-pager",
                    )
                    try:
                        state = _exit_state(
                            raw,
                            self.plan.cgroup,
                            self.ready_metadata.get("pid")
                            if self.ready_metadata
                            else None,
                        )
                    except base.OwnerRejected:
                        self.exit_metadata["failure_reason"] = (
                            "manager_metadata_unknown"
                        )
                        raise
                    self.exit_metadata["manager"] = state
                    if (
                        state["ActiveState"] == "active"
                        and state["SubState"] == "exited"
                        and state["Result"] == "success"
                        and state["ExecMainCode"] == 1
                        and state["ExecMainStatus"] == 0
                        and state["main_pid_zero"] is True
                        and (
                            state["control_group_expected"] is True
                            or state["control_group_empty"] is True
                        )
                    ):
                        self.exit_metadata["wait_checkpoint"] = "complete"
                        return
                    if (
                        state["ActiveState"] in {"failed", "inactive"}
                        or state["SubState"] == "exited"
                        or state["Result"] not in {"success", ""}
                    ):
                        raise base.OwnerRejected("worker_exit_unknown")
                time.sleep(0.05)
            raise base.OwnerRejected("worker_exit_unknown")
        except (Exception, KeyboardInterrupt, SystemExit) as error:
            if self.exit_metadata["failure_reason"] is None:
                self.exit_metadata["failure_reason"] = _failure_reason(error)
            raise

    def preflight_result(self) -> dict[str, object]:
        value = contract.validate_preflight(self._wait("preflight-result.json"))
        if self._verify("preauthentication_complete") != (0, 0):
            raise base.OwnerRejected("preauthentication_packet_unknown")
        return value

    def auth_ready(self, sequence: int) -> None:
        expected = {
            "run_id": self.case.run_id,
            "sequence": sequence,
            "auth_cli_completed": True,
            "first_network_refresh_planned": sequence == 1,
        }
        value = self._wait(f"auth-ready-{sequence}.json")
        if not base.metadata_equal(value, expected):
            raise base.OwnerRejected("auth_metadata_unknown")
        before = self.previous_counts
        after = self._verify(f"auth_complete_{sequence}")
        if sequence == 1 and after[0] <= before[0]:
            # This is packet evidence of the planned network phase, never an
            # independently measured refresh HTTP count.
            raise base.OwnerRejected("first_auth_network_evidence_unknown")

    def cell_result(self, sequence: int) -> dict[str, object]:
        value = contract.validate_cell(
            sequence,
            self._wait(f"case-result-{sequence}.json"),
            run_id=self.case.run_id,
        )
        self._verify(f"model_complete_{sequence}")
        return value

    def collect(self) -> dict[str, object]:
        value = base.LiveOperations.collect(self)
        self._verify("batch_complete")
        return value


class Operations(Protocol):
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
    def cell_result(self, sequence: int) -> dict[str, object]: ...
    def collect(self) -> dict[str, object]: ...
    def wait_exit(self) -> None: ...
    def restore(self) -> dict[str, object]: ...
    def finish(self) -> dict[str, object]: ...
    def write_ledger(self, value: object) -> None: ...
    def selection_journal(self) -> dict[str, object]: ...
    def database_restoration(self) -> dict[str, object]: ...


def run_owner(case: contract.Case, ops: Operations) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    result: dict[str, object] = {
        "scope": "h1_live_six_batch",
        "run_id": case.run_id,
        "result": "unknown",
        "case_binding": case.to_dict(),
        "limits": dict(contract.LIMITS),
        "worker_ready": None,
        "preflight": None,
        "worker_result": None,
        "rules": None,
        "cases": rows,
        "restoration": None,
        "artifacts": None,
        "restoration_stage": None,
        "resolver_check": None,
        "exit_diagnostics": None,
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
        stage = "start"
        ops.start()
        stage = "ready"
        result["worker_ready"] = ops.ready()
        stage = "rules"
        result["rules"] = ops.exercise_rules()
        stage = "preauthentication"
        ops.phase_gate("preflight", 0)
        result["preflight"] = ops.preflight_result()
        stage = "activate_network"
        ops.activate()
        for sequence in range(1, 7):
            stage = f"auth_{sequence}"
            ops.phase_gate("auth", sequence)
            ops.auth_ready(sequence)
            stage = f"model_{sequence}"
            ops.phase_gate("model", sequence)
            rows.append(ops.cell_result(sequence))
        stage = "worker_result"
        result["worker_result"] = ops.collect()
        aggregate = result["worker_result"]
        if (
            type(aggregate) is not dict
            or not base.metadata_equal(aggregate.get("cases"), rows)
            or not base.metadata_equal(aggregate.get("preflight"), result["preflight"])
        ):
            raise base.OwnerRejected("worker_aggregate_inconsistent")
        stage = "exit_gate"
        ops.phase_gate("exit", 7)
        stage = "exit_wait"
        ops.wait_exit()
        successful = True
    except (Exception, KeyboardInterrupt, SystemExit) as error:
        result.update(failure_stage=stage, failure_reason=_failure_reason(error))
    finally:
        if isinstance(ops, LiveOperations):
            diagnostic = getattr(ops, "exit_metadata", None)
            if type(diagnostic) is dict:
                if (
                    stage in {"exit_gate", "exit_wait"}
                    and diagnostic.get("failure_reason") is None
                ):
                    diagnostic["failure_reason"] = result.get("failure_reason")
                result["exit_diagnostics"] = dict(diagnostic)
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
                result["database_selection_restoration"] = ops.database_restoration()
            except BaseException:
                result["database_selection_restoration"] = {"result": "unknown"}
            try:
                result["selection_journal"] = ops.selection_journal()
            except BaseException:
                result["selection_journal"] = {"completeness": "unknown"}
            if successful:
                expected_db = {
                    "result": "original_selection_restored",
                    "append_only_history_retained": True,
                    "source": "trusted_worker_public_API_CAS",
                }
                journal = result.get("selection_journal")
                worker = result.get("worker_result")
                if (
                    not base.metadata_equal(
                        result.get("database_selection_restoration"), expected_db
                    )
                    or type(journal) is not dict
                    or journal.get("completeness") != "captured"
                    or type(worker) is not dict
                    or not base.metadata_equal(
                        journal.get("entries"), worker.get("selection_journal")
                    )
                ):
                    successful = False
                    result["database_evidence_error"] = "live_selection_restore_unknown"
            try:
                ops.write_ledger(result)
            except BaseException:
                successful = False
                result["ledger_error"] = "permanent_result_unknown"
    if successful:
        try:
            with base.cleanup_signals():
                artifacts = ops.finish()
                if not base.metadata_equal(
                    artifacts,
                    {"result": "successful_artifacts_removed", "ledger_retained": True},
                ):
                    raise base.OwnerRejected("artifact_cleanup_unknown")
                result["artifacts"] = artifacts
            result["result"] = "observed_expected_and_restored"
        except BaseException:
            result.update(
                failure_stage="finish", failure_reason="artifact_cleanup_unknown"
            )
        try:
            ops.write_ledger(result)
        except BaseException:
            result.update(result="unknown", ledger_error="permanent_result_unknown")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Owner-only six-cell controlled Pi batch")
    p.add_argument("--expected-manifest-sha", required=True)
    args = p.parse_args()
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
    except (Exception, KeyboardInterrupt):
        value = {
            "scope": "h1_live_six_batch",
            "result": "unknown",
            "failure_reason": "owner_bootstrap_unknown",
        }
    good = (
        case is not None
        and value.get("scope") == "h1_live_six_batch"
        and value.get("run_id") == case.run_id
        and value.get("result") == "observed_expected_and_restored"
    )
    output = {
        "scope": "h1_owner_automation_only",
        "run_id": case.run_id if case else None,
        "manifest_sha256": args.expected_manifest_sha,
        "owner_result": "observed_expected_and_restored" if good else "unknown",
        "preflight_result": value,
    }
    print(json.dumps(output, sort_keys=True))
    return 0 if good else 1
