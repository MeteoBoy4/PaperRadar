"""Independent D1: trusted IPv4 plan reconciliation, with mocks only."""

from copy import deepcopy
from typing import cast

import pytest

from scripts import issue167_h1_guardian as guardian
from scripts import issue167_h1_owner_run as runner
from scripts.issue167_h1_phase import Plan
from tests.test_issue167_h1_guardian import FakeOps


def plan() -> Plan:
    return Plan("123456abcdef", 1000, 1000, network_mode="ipv4_only")


def done(phase: str) -> dict[str, object]:
    current, other = (38167, 38169) if phase == "a" else (38169, 38167)
    rows = []
    for kind in ("tcp", "udp"):
        rows.append(
            {
                "case": "v6-socket-" + kind,
                "kind": "socket_check",
                "family": "v6",
                "port": 0,
                "expected": "deny",
                "outcome": "denied",
                "errno_category": "permission_denied",
            }
        )
    for case, kind, port, expected in (
        ("v4-current-tcp", "tcp", current, "allow"),
        ("v4-other-tcp", "tcp", other, "deny"),
        ("v4-blocked-tcp", "tcp", 38168, "deny"),
        ("v4-blocked-udp", "udp", 38168, "deny"),
        ("v4-dns-udp", "udp", 53, "deny"),
    ):
        rows.append(
            {
                "case": case,
                "kind": kind,
                "family": "v4",
                "port": port,
                "expected": expected,
                "outcome": "allowed" if expected == "allow" else "denied",
                "errno_category": "none"
                if expected == "allow"
                else "admin_unreachable",
            }
        )
    return {"run_id": plan().run_id, "phase": phase, "cases": rows}


def test_ipv4_mode_requires_two_creation_checks_and_five_network_rows() -> None:
    for phase in ("a", "b"):
        guardian.reconcile_done(plan(), phase, done(phase))


@pytest.mark.parametrize("category", ["timed_out", "other", "admin_unreachable"])
def test_ipv6_timeout_or_network_error_is_not_creation_denial(category: str) -> None:
    value = done("a")
    rows = cast(list[dict[str, object]], value["cases"])
    rows[0]["errno_category"] = category
    with pytest.raises(guardian.GuardianRejected, match=r"^phase_observation_unknown$"):
        guardian.reconcile_done(plan(), "a", value)


def test_missing_creation_check_stays_unknown() -> None:
    value = done("a")
    cast(list[dict[str, object]], value["cases"]).pop(0)
    with pytest.raises(guardian.GuardianRejected, match=r"^phase_metadata_invalid$"):
        guardian.reconcile_done(plan(), "a", value)


class IPv4Ops(FakeOps):
    def wait(self, name: str) -> object:
        if name in {"a-done.json", "b-done.json"}:
            self.events.append(name)
            return done(name[0])
        return super().wait(name)

    def counters(self, phase: str) -> tuple[int, int]:
        self.events.append("counter:" + phase)
        count = self.counter_reads.get(phase, 0)
        self.counter_reads[phase] = count + 1
        return (0, 0) if count == 0 else (1, 4)


def test_packet_reference_excludes_ipv6_socket_creation_rows() -> None:
    operations = IPv4Ops()
    result = guardian.run_guardian(plan(), operations)
    assert result["result"] == "observed_expected"
    assert result["phase_counts"] == {
        phase: {"allowed_packet_delta": 1, "rejected_packet_delta": 4}
        for phase in ("a", "b")
    }
    assert result["cleanup_complete"] is True


def success_record() -> dict[str, object]:
    return {
        **guardian.run_guardian(plan(), IPv4Ops()),
        "table_may_remain": False,
        "guardian_metadata": {
            "uid_is_root": True,
            "core_limits": [0, 0],
            "no_new_privs": True,
            "capabilities": {
                name: True
                for name in (
                    "chown",
                    "dac_read_search",
                    "kill",
                    "setgid",
                    "setuid",
                    "net_admin",
                )
            },
        },
    }


def test_owner_collector_uses_trusted_plan_mode() -> None:
    value = success_record()
    assert (
        runner.guardian_record(value, run_id=plan().run_id, network_mode="ipv4_only")
        == value
    )
    assert (
        runner.ledger_record(value, run_id=plan().run_id, network_mode="ipv4_only")
        == value
    )
    with pytest.raises(runner.OwnerRunRejected, match=r"^probe_metadata_invalid$"):
        runner.guardian_record(value, run_id=plan().run_id)
    untrusted = deepcopy(value)
    untrusted["network_mode"] = "ipv4_only"
    with pytest.raises(runner.OwnerRunRejected, match=r"^probe_metadata_invalid$"):
        runner.guardian_record(untrusted, run_id=plan().run_id)
