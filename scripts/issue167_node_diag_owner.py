"""Owner orchestration for a fixed-Node diagnostic, inert on import."""

from __future__ import annotations

import argparse
import json
import re
import resource
import signal
import time
from pathlib import Path
from typing import Protocol, cast

from scripts import issue167_node_diag_case as contract
from scripts import issue167_resolver_owner as base
from scripts import issue167_service_network_owner as network


class LiveOperations(network.LiveOperations):
    def __init__(self, case: contract.Case, manifest_sha: str) -> None:
        base.LiveOperations.__init__(self, case, contract, manifest_sha)
        self.previous_counts = (0, 0)

    def _wait(self, name: str) -> object:
        if name not in {
            "ready.json",
            "worker-result.json",
            *(f"stage-{n}.json" for n in range(1, 5)),
        }:
            raise base.OwnerRejected("metadata_name_unknown")
        while time.monotonic() < self.deadline:
            try:
                return self.contract.read_metadata(
                    self.case.worker_root / name, owner=self.case.uid
                )
            except FileNotFoundError:
                time.sleep(0.05)
        raise base.OwnerRejected("worker_deadline_unknown")

    def exercise_rules(self) -> dict[str, object]:
        value = super().exercise_rules()
        self.activate()
        value["scope"] = "fixed_node_network_and_landlock_diagnostic"
        return value

    def gate(self, sequence: int) -> None:
        if (
            type(sequence) is not int
            or sequence not in {1, 2, 3, 4, 5}
            or self.ready_metadata is None
        ):
            raise base.OwnerRejected("gate_sequence_unknown")
        state = self.commands.unit_state()
        if state.pid != self.ready_metadata["pid"] or self.phase.read_cgroup_state(
            self.plan
        ).pids != {state.pid}:
            raise base.OwnerRejected("worker_cgroup_unknown")
        self._verify()
        self._write(
            self.case.runtime_root / f"gate-{sequence}.json",
            {"run_id": self.case.run_id, "sequence": sequence},
        )

    def stage_result(self, sequence: int) -> dict[str, object]:
        value = contract.validate_stage(
            self.case, sequence, self._wait(f"stage-{sequence}.json")
        )
        before = self.previous_counts
        after = self._verify(f"node_stage_{sequence}")
        if (sequence == 2 and after != before) or (
            sequence != 2 and (after[0] <= before[0] or after[1] != before[1])
        ):
            raise base.OwnerRejected("node_packet_evidence_unknown")
        state = self.commands.unit_state()
        if (
            self.ready_metadata is None
            or state.pid != self.ready_metadata["pid"]
            or self.phase.read_cgroup_state(self.plan).pids != {state.pid}
        ):
            raise base.OwnerRejected("worker_cgroup_unknown")
        return value

    def collect(self) -> dict[str, object]:
        value = base.LiveOperations.collect(self)
        self._verify("diagnostic_complete")
        return value


class Operations(base.Operations, Protocol):
    def stage_result(self, sequence: int) -> dict[str, object]: ...


def run_owner(case: contract.Case, operations: Operations) -> dict[str, object]:
    result: dict[str, object] = {
        "scope": "h1_fixed_node_diagnostic",
        "run_id": case.run_id,
        "result": "unknown",
        "case_binding": case.to_dict(),
        "network_limits": dict(contract.LIMITS),
        "pi_execs": 0,
        "auth_calls": 0,
        "model_calls": 0,
        "worker_ready": None,
        "worker_result": None,
        "rules": None,
        "stages": [],
        "restoration": None,
        "artifacts": None,
        "restoration_stage": None,
        "resolver_check": None,
        "owner_configuration_confirmation_source": (
            "sealed_entry_explicit_owner_flags_external_authorization_required"
        ),
    }
    reserved = installed = successful = False
    stage = "preflight"
    try:
        operations.preflight()
        stage = "reserve"
        operations.reserve()
        reserved = True
        stage = "install"
        installed = True
        operations.install()
        stage = "start"
        operations.start()
        stage = "ready"
        result["worker_ready"] = operations.ready()
        stage = "rules"
        result["rules"] = operations.exercise_rules()
        rows = []
        for sequence in (1, 2, 3, 4):
            stage = f"node_stage_{sequence}"
            operations.gate(sequence)
            rows.append(operations.stage_result(sequence))
        result["stages"] = rows
        stage = "worker_result"
        result["worker_result"] = operations.collect()
        stage = "exit"
        operations.gate(5)
        operations.wait_exit()
        successful = True
    except (Exception, KeyboardInterrupt, SystemExit):
        result.update(failure_stage=stage, failure_reason="owner_operation_unknown")
    finally:
        if installed:
            try:
                with base.cleanup_signals():
                    restoration = operations.restore()
                    if not base.metadata_equal(
                        restoration,
                        {
                            "result": "host_policy_restored",
                            "global_resolver_unchanged": True,
                            "ledger_retained": True,
                            "table_absent": True,
                            "unit_absent": True,
                        },
                    ):
                        raise base.OwnerRejected("restoration_unknown")
                    result["restoration"] = restoration
            except BaseException:
                successful = False
                result["restoration_error"] = "restoration_unknown"
            result["restoration_stage"], result["resolver_check"] = (
                base.restoration_metadata(operations, case.run_id)
            )
        if reserved:
            try:
                operations.write_ledger(result)
            except BaseException:
                successful = False
                result["ledger_error"] = "permanent_result_unknown"
    if successful:
        try:
            with base.cleanup_signals():
                artifacts = operations.finish()
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
            operations.write_ledger(result)
        except BaseException:
            result.update(result="unknown", ledger_error="permanent_result_unknown")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Owner-only fixed Node no-secret diagnostic"
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
        result = run_owner(case, LiveOperations(case, args.expected_manifest_sha))
    except (Exception, KeyboardInterrupt):
        result = {
            "scope": "h1_fixed_node_diagnostic",
            "result": "unknown",
            "failure_reason": "owner_bootstrap_unknown",
        }
    good = (
        case is not None
        and result.get("scope") == "h1_fixed_node_diagnostic"
        and result.get("run_id") == case.run_id
        and result.get("result") == "observed_expected_and_restored"
    )
    envelope = {
        "scope": "h1_owner_automation_only",
        "run_id": case.run_id if case else None,
        "manifest_sha256": args.expected_manifest_sha
        if re.fullmatch("[a-f0-9]{64}", args.expected_manifest_sha)
        else None,
        "owner_result": "observed_expected_and_restored" if good else "unknown",
        "preflight_result": result,
    }
    print(json.dumps(envelope, sort_keys=True))
    return 0 if good else 1
