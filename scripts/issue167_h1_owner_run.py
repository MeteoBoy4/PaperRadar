"""Root-owned one-shot H1 automation; ordinary import never runs host operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import signal
import stat
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, Protocol, cast


class OwnerRunRejected(ValueError):
    """Only controlled reasons, never external output or exception text."""


class OwnerInterrupted(KeyboardInterrupt):
    """SIGINT/SIGTERM request cleanup without restarting a case."""


def protected_file_bytes(path: Path, *, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_nlink != 1
        ):
            raise OwnerRunRejected("root_metadata_invalid")
        chunks = bytearray()
        while len(chunks) <= limit:
            chunk = os.read(descriptor, min(4096, limit + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
        if len(chunks) > limit:
            raise OwnerRunRejected("root_metadata_too_large")
        return bytes(chunks)
    finally:
        os.close(descriptor)


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    class Parser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise SystemExit("owner_arguments_invalid")

    parser = Parser(description="一次H1自动执行/核查/恢复,密码只由外层sudo接收")
    parser.add_argument("--expected-manifest-sha", required=True)
    args = parser.parse_args(argv)
    if re.fullmatch(r"[a-f0-9]{64}", args.expected_manifest_sha) is None:
        raise SystemExit("owner_manifest_identity_invalid")
    return args


_root: Path
_entry_args: argparse.Namespace
if TYPE_CHECKING:
    from scripts import issue167_h1_owner_ops as owner_ops
    from scripts.issue167_h1_guardian import (
        Commands,
        _json_pairs,
        bootstrap,
        protected_path,
        read_json,
    )
    from scripts.issue167_h1_phase import Plan, load_plan
elif __package__ in {None, ""}:
    _entry_args = arguments()
    _root = Path(__file__).absolute().parent
    if (
        os.geteuid() != 0
        or re.fullmatch(r"/home/paperradar-probes/issue167-[a-f0-9]{12}", str(_root))
        is None
    ):
        raise SystemExit("root_owned_installation_required")
    for _item in (Path(__file__).absolute(), _root, *_root.parents):
        _info = _item.lstat()
        if (
            stat.S_ISLNK(_info.st_mode)
            or _info.st_uid != 0
            or _info.st_mode & (0o022 | 0o6000)
        ):
            raise SystemExit("root_owned_installation_required")
    _manifest = protected_file_bytes(_root / "manifest.json", limit=65536)
    if hashlib.sha256(_manifest).hexdigest() != _entry_args.expected_manifest_sha:
        raise SystemExit("approved_manifest_mismatch")
    sys.path.insert(0, str(_root))
    import issue167_h1_owner_ops as owner_ops
    from issue167_h1_guardian import (
        Commands,
        _json_pairs,
        bootstrap,
        protected_path,
        read_json,
    )
    from issue167_h1_phase import Plan, load_plan
else:
    from scripts import issue167_h1_owner_ops as owner_ops
    from scripts.issue167_h1_guardian import (
        Commands,
        _json_pairs,
        bootstrap,
        protected_path,
        read_json,
    )
    from scripts.issue167_h1_phase import Plan, load_plan

_FAILURE_STAGES = frozenset(
    {
        "reserve",
        "peer_start",
        "worker_ready",
        "identity_file_validation",
        "initial_members",
        "initial_rules",
        "phase_a",
        "phase_b",
        "leftover",
        "cleanup",
        "completed",
    }
)
_FAILURE_REASONS = frozenset(
    {
        "observer_failure",
        "cleanup_unknown",
        "case_already_consumed",
        "worker_identity_unknown",
        "file_probe_unknown",
        "unexpected_descendants",
        "independent_counter_unknown",
        "leftover_metadata_invalid",
        "leftover_observation_unknown",
        "phase_metadata_invalid",
        "phase_observation_unknown",
        "unit_identity_unknown",
        "worker_identity_changed",
        "nft_state_unknown",
        "cgroup_unknown",
        "cgroup_read_unknown",
        "table_exists",
        "table_inventory_unknown",
        "command_failed",
        "command_timeout",
        "command_output_too_large",
        "peer_not_ready",
        "peer_exited",
        "metadata_timeout",
        "metadata_invalid",
        "metadata_owner_invalid",
        "metadata_too_large",
        "phase_invalid",
        "unprotected_installation",
        "host_context_unknown",
        "host_context_mismatch",
        "runtime_metadata_invalid",
        "guardian_metadata_unknown",
        "guardian_runtime_invalid",
        "cgroup_identity_unknown",
        "table_binding_unknown",
    }
)
_CAPABILITIES = frozenset(
    {"chown", "dac_read_search", "kill", "setgid", "setuid", "net_admin"}
)


def guardian_record(
    value: object, *, run_id: str, network_mode: str = "dual_stack"
) -> dict[str, object]:
    if type(network_mode) is not str or network_mode not in {"dual_stack", "ipv4_only"}:
        raise OwnerRunRejected("probe_metadata_invalid")
    minimum_allowed, minimum_rejected = (
        (1, 4) if network_mode == "ipv4_only" else (2, 8)
    )
    required = {
        "scope",
        "run_id",
        "result",
        "phase_counts",
        "leftover_refused",
        "cleanup_complete",
        "auth_calls",
        "model_calls",
        "table_may_remain",
    }
    optional = {
        "failure_reason",
        "failure_stage",
        "os_error_category",
        "guardian_metadata",
    }
    if (
        type(value) is not dict
        or not required <= set(value)
        or not set(value) <= required | optional
        or value["scope"] != "h1_synthetic_local_only"
        or value["run_id"] != run_id
        or type(value["result"]) is not str
        or value["result"] not in {"unknown", "observed_expected"}
    ):
        raise OwnerRunRejected("probe_metadata_invalid")
    for key in ("auth_calls", "model_calls"):
        if type(value[key]) is not int or value[key] != 0:
            raise OwnerRunRejected("probe_metadata_invalid")
    for key in ("leftover_refused", "cleanup_complete", "table_may_remain"):
        if type(value[key]) is not bool:
            raise OwnerRunRejected("probe_metadata_invalid")
    counts = value["phase_counts"]
    if type(counts) is not dict or not set(counts) <= {"a", "b"}:
        raise OwnerRunRejected("probe_metadata_invalid")
    for row in counts.values():
        if (
            type(row) is not dict
            or set(row) != {"allowed_packet_delta", "rejected_packet_delta"}
            or any(
                type(number) is not int or not 0 <= number < 2**64
                for number in row.values()
            )
        ):
            raise OwnerRunRejected("probe_metadata_invalid")
    if "failure_reason" in value and (
        type(value["failure_reason"]) is not str
        or value["failure_reason"] not in _FAILURE_REASONS
    ):
        raise OwnerRunRejected("probe_metadata_invalid")
    if "failure_stage" in value and (
        type(value["failure_stage"]) is not str
        or value["failure_stage"] not in _FAILURE_STAGES
    ):
        raise OwnerRunRejected("probe_metadata_invalid")
    if "os_error_category" in value and (
        type(value["os_error_category"]) is not str
        or value["os_error_category"]
        not in {
            "permission_denied",
            "file_missing",
            "other_os_error",
        }
    ):
        raise OwnerRunRejected("probe_metadata_invalid")
    facts = value.get("guardian_metadata")
    if facts is not None and (
        type(facts) is not dict
        or set(facts) != {"uid_is_root", "core_limits", "no_new_privs", "capabilities"}
        or any(type(facts[key]) is not bool for key in ("uid_is_root", "no_new_privs"))
        or type(facts["core_limits"]) is not list
        or len(facts["core_limits"]) != 2
        or any(
            type(number) is not int or not -1 <= number < 2**63
            for number in facts["core_limits"]
        )
        or type(facts["capabilities"]) is not dict
        or set(facts["capabilities"]) != _CAPABILITIES
        or any(type(enabled) is not bool for enabled in facts["capabilities"].values())
    ):
        raise OwnerRunRejected("probe_metadata_invalid")
    if value["result"] == "observed_expected" and (
        set(counts) != {"a", "b"}
        or value["leftover_refused"] is not True
        or value["cleanup_complete"] is not True
        or value["table_may_remain"] is not False
        or any(
            counts[phase]["allowed_packet_delta"] < minimum_allowed
            or counts[phase]["rejected_packet_delta"] < minimum_rejected
            for phase in ("a", "b")
        )
        or facts is None
        or facts["uid_is_root"] is not True
        or facts["no_new_privs"] is not True
        or facts["core_limits"] != [0, 0]
        or any(enabled is not True for enabled in facts["capabilities"].values())
        or set(value) & {"failure_reason", "failure_stage", "os_error_category"}
    ):
        raise OwnerRunRejected("probe_metadata_invalid")
    return cast(dict[str, object], value)


def validate_retry(root: Path, plan: Plan) -> dict[str, object]:
    value = read_json(root / "retry-context.json", owner=0)
    keys = {
        "kind",
        "predecessor_run_id",
        "predecessor_manifest_sha256",
        "predecessor_ledger_sha256",
        "additional_attempts",
    }
    if (
        type(value) is not dict
        or set(value) != keys
        or value["kind"] != "additional_attempt_after_unknown"
        or type(value["additional_attempts"]) is not int
        or value["additional_attempts"] != 1
        or type(value["predecessor_run_id"]) is not str
        or re.fullmatch(r"[a-f0-9]{12}", value["predecessor_run_id"]) is None
        or value["predecessor_run_id"] == plan.run_id
        or any(
            type(value[key]) is not str
            or re.fullmatch(r"[a-f0-9]{64}", value[key]) is None
            for key in ("predecessor_manifest_sha256", "predecessor_ledger_sha256")
        )
    ):
        raise OwnerRunRejected("retry_context_invalid")
    predecessor = value["predecessor_run_id"]
    ledger = owner_ops.LEDGER_ROOT / f"issue167-{predecessor}.json"
    protected_path(ledger)
    raw = protected_file_bytes(ledger, limit=16384)
    if hashlib.sha256(raw).hexdigest() != value["predecessor_ledger_sha256"]:
        raise OwnerRunRejected("retry_history_mismatch")
    try:
        old = guardian_record(
            json.loads(raw, object_pairs_hook=_json_pairs), run_id=predecessor
        )
    except (ValueError, UnicodeError):
        raise OwnerRunRejected("retry_history_invalid") from None
    if old["result"] != "unknown":
        raise OwnerRunRejected("retry_history_invalid")
    return {
        "predecessor_run_id": predecessor,
        "history_verified": True,
        "predecessor_manifest_sha256": value["predecessor_manifest_sha256"],
        "additional_attempts": 1,
    }


def ledger_record(
    value: object, *, run_id: str, network_mode: str = "dual_stack"
) -> dict[str, object]:
    if type(value) is dict and set(value) == {"run_id", "state"}:
        if value["run_id"] == run_id and value["state"] == "reserved_unknown":
            return cast(dict[str, object], value)
        raise OwnerRunRejected("probe_metadata_invalid")
    return guardian_record(value, run_id=run_id, network_mode=network_mode)


@dataclass(frozen=True)
class Collected:
    guardian: dict[str, object] | None
    ledger: dict[str, object] | None

    @property
    def successful(self) -> bool:
        return (
            self.guardian is not None
            and self.ledger is not None
            and self.guardian == self.ledger
            and self.guardian["result"] == "observed_expected"
        )


class RunnerOperations(Protocol):
    def preflight(self) -> None: ...
    def install(self) -> None: ...
    def verify(self) -> None: ...
    def start(self) -> None: ...
    def wait(self) -> None: ...
    def collect(self) -> Collected: ...
    def restore(self) -> dict[str, object]: ...
    def finish(self) -> dict[str, object]: ...


def owner_metadata(value: object, *, successful_finish: bool) -> dict[str, object]:
    if type(value) is not dict:
        raise OwnerRunRejected("owner_metadata_unknown")
    expected = (
        {"result", "ledger_retained", "auth_calls", "model_calls"}
        if successful_finish
        else {
            "result",
            "ledger_retained",
            "runtime_retained",
            "code_retained",
            "auth_calls",
            "model_calls",
        }
    )
    if (
        set(value) != expected
        or value["result"]
        != (
            "successful_artifacts_removed"
            if successful_finish
            else "host_policy_restored"
        )
        or any(
            type(value[key]) is not int or value[key] != 0
            for key in ("auth_calls", "model_calls")
        )
        or any(
            type(value[key]) is not bool
            for key in expected - {"result", "auth_calls", "model_calls"}
        )
        or (successful_finish and value["ledger_retained"] is not True)
    ):
        raise OwnerRunRejected("owner_metadata_unknown")
    return cast(dict[str, object], value)


def run_owner(
    plan: Plan, operations: RunnerOperations, *, manifest_sha256: str
) -> dict[str, object]:
    if re.fullmatch(r"[a-f0-9]{64}", manifest_sha256) is None:
        raise OwnerRunRejected("approved_manifest_mismatch")
    result: dict[str, object] = {
        "scope": "h1_owner_automation_only",
        "run_id": plan.run_id,
        "manifest_sha256": manifest_sha256,
        "owner_result": "unknown",
        "guardian_result": None,
        "ledger": None,
        "restoration": None,
        "artifacts": None,
    }
    stage = "preflight"
    attempted_install = False
    probe_success = False
    failed = False
    interrupted = False
    try:
        operations.preflight()
        stage = "install"
        attempted_install = True
        operations.install()
        stage = "verify"
        operations.verify()
        stage = "start"
        operations.start()
        stage = "wait"
        operations.wait()
        stage = "collect"
        captured = operations.collect()
        if captured.guardian is not None:
            result["guardian_result"] = guardian_record(
                captured.guardian, run_id=plan.run_id, network_mode=plan.network_mode
            )
        if captured.ledger is not None:
            result["ledger"] = ledger_record(
                captured.ledger, run_id=plan.run_id, network_mode=plan.network_mode
            )
        probe_success = captured.successful
        if not probe_success:
            raise OwnerRunRejected("probe_unknown")
    except (KeyboardInterrupt, SystemExit):
        failed = interrupted = True
        result["failure_stage"] = stage
        result["failure_reason"] = "interrupted"
    except Exception:
        failed = True
        result["failure_stage"] = stage
        result["failure_reason"] = "owner_operation_unknown"
    finally:
        if attempted_install:
            try:
                with cleanup_signal_shield():
                    result["restoration"] = owner_metadata(
                        operations.restore(), successful_finish=False
                    )
            except BaseException:
                failed = True
                result["restoration_error"] = "restoration_unknown"
    if probe_success and not failed and result["restoration"] is not None:
        try:
            result["artifacts"] = owner_metadata(
                operations.finish(), successful_finish=True
            )
            result["owner_result"] = "observed_expected_and_restored"
        except BaseException:
            result["failure_stage"] = "finish"
            result["failure_reason"] = "artifacts_retained_unknown"
    if interrupted:
        result["owner_result"] = "interrupted"
    return result


class LiveRunner:
    def __init__(self, plan: Plan, commands: Commands) -> None:
        self.plan = plan
        self.commands = commands

    def preflight(self) -> None:
        owner_ops.require_no_conflict(self.plan, self.commands)

    def install(self) -> None:
        owner_ops.install(self.plan, self.commands)

    def verify(self) -> None:
        analyze = Path("/usr/bin/systemd-analyze")
        protected_path(analyze)
        self.commands._run(
            (
                str(analyze),
                "verify",
                "--man=no",
                str(self.plan.install_root / self.plan.unit),
                str(self.plan.install_root / self.plan.guardian_unit),
            )
        )
        if owner_ops.check_units(self.plan, self.commands, must_be_absent=False) != {
            self.plan.unit,
            self.plan.guardian_unit,
        }:
            raise OwnerRunRejected("installed_scope_unknown")

    def start(self) -> None:
        for unit in (self.plan.guardian_unit, self.plan.unit):
            self.commands._run((str(self.commands.tools["systemctl"]), "start", unit))

    def state(self, unit: str) -> dict[str, str]:
        if unit not in {self.plan.unit, self.plan.guardian_unit}:
            raise OwnerRunRejected("unit_scope_unknown")
        raw = self.commands._run(
            (
                str(self.commands.tools["systemctl"]),
                "show",
                unit,
                "--property=LoadState,ActiveState,SubState,Result",
                "--no-pager",
            )
        )
        try:
            rows = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
            value = dict(rows)
            if (
                len(rows) != len(value)
                or set(value) != {"LoadState", "ActiveState", "SubState", "Result"}
                or value["LoadState"] != "loaded"
                or value["ActiveState"]
                not in {"active", "inactive", "failed", "activating", "deactivating"}
            ):
                raise ValueError
        except (ValueError, UnicodeError):
            raise OwnerRunRejected("unit_state_unknown") from None
        return value

    def wait(self) -> None:
        deadline = time.monotonic() + 210
        while time.monotonic() < deadline:
            guardian = self.state(self.plan.guardian_unit)
            self.state(self.plan.unit)
            if guardian["ActiveState"] in {"inactive", "failed"}:
                return
            time.sleep(0.1)
        raise OwnerRunRejected("guardian_timeout")

    def collect(self) -> Collected:
        guardian = ledger = None
        # Missing/invalid data is never serialized or promoted.
        with suppress(Exception):
            guardian = guardian_record(
                read_json(self.plan.runtime_root / "guardian-result.json", owner=0),
                run_id=self.plan.run_id,
                network_mode=self.plan.network_mode,
            )
        # Always attempt the independent durable record, even if runtime data is absent.
        with suppress(Exception):
            ledger_path = owner_ops.LEDGER_ROOT / f"issue167-{self.plan.run_id}.json"
            protected_path(ledger_path)
            ledger = ledger_record(
                read_json(ledger_path, owner=0),
                run_id=self.plan.run_id,
                network_mode=self.plan.network_mode,
            )
        return Collected(guardian, ledger)

    def restore(self) -> dict[str, object]:
        return owner_ops.restore(self.plan, self.commands)

    def finish(self) -> dict[str, object]:
        return owner_ops.remove_successful_artifacts(self.plan, self.commands)


@contextmanager
def cleanup_signal_shield() -> Iterator[None]:
    previous = {
        number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        for number in previous:
            signal.signal(number, signal.SIG_IGN)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


@contextmanager
def signal_cleanup() -> Iterator[None]:
    def interrupted(signum: int, frame: object) -> None:
        raise OwnerInterrupted

    previous = {
        number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        for number in previous:
            signal.signal(number, interrupted)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def main() -> int:
    args = _entry_args if __package__ in {None, ""} else arguments()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    root = _root if __package__ in {None, ""} else Path(__file__).absolute().parent
    try:
        tools = bootstrap(root)
        raw = protected_file_bytes(root / "manifest.json", limit=65536)
        if hashlib.sha256(raw).hexdigest() != args.expected_manifest_sha:
            raise OwnerRunRejected("approved_manifest_mismatch")
        plan = load_plan(root / "plan.json")
        if plan.install_root != root:
            raise OwnerRunRejected("plan_root_mismatch")
        retry = validate_retry(root, plan)
        with signal_cleanup():
            result = run_owner(
                plan,
                LiveRunner(plan, Commands(plan, tools)),
                manifest_sha256=args.expected_manifest_sha,
            )
        result["retry_history"] = retry
    except BaseException:
        result = {
            "scope": "h1_owner_automation_only",
            "owner_result": "unknown",
            "failure_stage": "preflight",
            "failure_reason": "preflight_unknown",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["owner_result"] == "observed_expected_and_restored" else 1


if __name__ == "__main__":
    raise SystemExit(main())
