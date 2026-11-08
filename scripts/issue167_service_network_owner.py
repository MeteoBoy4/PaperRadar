"""Owner-only service-network orchestration; no action occurs on import."""

from __future__ import annotations

import argparse
import json
import re
import resource
import signal
import time
from pathlib import Path
from typing import cast

from scripts import issue167_resolver_owner as base
from scripts import issue167_service_network_case as contract


class LiveOperations(base.LiveOperations):
    def __init__(self, case: contract.Case, manifest_sha: str) -> None:
        super().__init__(case, contract, manifest_sha)
        self.previous_counts = (0, 0)

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
        if any(
            current < previous
            for current, previous in zip(counts, self.previous_counts, strict=True)
        ):
            raise base.OwnerRejected("packet_counter_decreased")
        if (self.enabled and counts[1] != self.previous_counts[1]) or (
            not self.enabled and counts[0] != self.previous_counts[0]
        ):
            raise base.OwnerRejected("phase_packet_evidence_unknown")
        self.previous_counts = counts
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
            raise base.OwnerRejected("cgroup_identity_unknown")
        self.binding = self.egress.make_binding(
            self.profile, payload, identity, host_context=self.host
        )
        self._write(self.case.runtime_root / "table-binding.json", self.binding, 0o600)
        if self._verify("created_deny") != (0, 0):
            raise base.OwnerRejected("initial_packet_count_unknown")
        return {
            "scope": "service_network_rule_and_representative_flow",
            "binding": self.binding,
            "snapshots": self.snapshots,
            "counts_semantics": "packet_not_HTTP_or_DNS_query_count",
        }

    def _wait(self, name: str) -> object:
        if name not in {
            "ready.json",
            "worker-result.json",
            "deny-1.json",
            "deny-2.json",
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

    def gate(self, sequence: int) -> None:
        if (
            type(sequence) is not int
            or sequence not in {1, 2, 3, 4}
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

    def deny_result(self, sequence: int) -> dict[str, object]:
        value = contract.validate_deny(
            self.case.run_id, sequence, self._wait(f"deny-{sequence}.json")
        )
        before = self.previous_counts
        after = self._verify(f"deny_{sequence}")
        if before[0] != after[0] or after[1] <= before[1]:
            raise base.OwnerRejected("deny_packet_evidence_unknown")
        return value

    def activate(self) -> None:
        self._run(
            (str(self.commands.tools["nft"]), "-f", "-"),
            self.egress.render_activate(self.profile).encode(),
        )
        self.enabled = True
        self._verify("activated")

    def collect(self) -> dict[str, object]:
        before = self.previous_counts
        value = super().collect()
        after = self.previous_counts
        if after[0] <= before[0] or after[1] != before[1]:
            self.worker_accepted = False
            raise base.OwnerRejected("allow_packet_evidence_unknown")
        self._verify("positive_complete")
        return value


def run_owner(case: contract.Case, operations: LiveOperations) -> dict[str, object]:
    result: dict[str, object] = {
        "scope": "h1_service_network_preflight",
        "run_id": case.run_id,
        "result": "unknown",
        "case_binding": case.to_dict(),
        "network_limits": contract.LIMITS,
        "node_pi": False,
        "auth_calls": 0,
        "model_calls": 0,
        "worker_ready": None,
        "worker_result": None,
        "rules": None,
        "denials": [],
        "restoration": None,
        "artifacts": None,
        "restoration_stage": None,
        "resolver_check": None,
        "owner_configuration_confirmation_source": (
            "sealed_entry_explicit_owner_flag_external_authorization_required"
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
        denials = []
        for sequence in (1, 2):
            stage = f"deny_{sequence}"
            operations.gate(sequence)
            denials.append(operations.deny_result(sequence))
        result["denials"] = denials
        stage = "activate"
        operations.activate()
        stage = "positive"
        operations.gate(3)
        result["worker_result"] = operations.collect()
        stage = "exit"
        operations.gate(4)
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


def owner_envelope(
    case: contract.Case | None, sha: str, result: dict[str, object]
) -> dict[str, object]:
    good = (
        case is not None
        and result.get("scope") == "h1_service_network_preflight"
        and result.get("run_id") == case.run_id
        and result.get("result") == "observed_expected_and_restored"
    )
    return {
        "scope": "h1_owner_automation_only",
        "run_id": case.run_id if case else None,
        "manifest_sha256": sha if re.fullmatch("[a-f0-9]{64}", sha) else None,
        "owner_result": "observed_expected_and_restored" if good else "unknown",
        "preflight_result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Owner-only bounded service DNS/TLS case"
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
            "scope": "h1_service_network_preflight",
            "result": "unknown",
            "failure_reason": "owner_bootstrap_unknown",
        }
    envelope = owner_envelope(case, args.expected_manifest_sha, result)
    print(json.dumps(envelope, sort_keys=True))
    return 0 if envelope["owner_result"] == "observed_expected_and_restored" else 1
