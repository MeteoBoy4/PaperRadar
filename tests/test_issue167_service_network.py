"""Independent D1, pure mocks: service-network budgets and trust boundaries."""

from __future__ import annotations

import copy
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from scripts import issue167_resolver_case as old
from scripts import issue167_resolver_owner as base_owner
from scripts import issue167_service_network_case as case
from scripts import issue167_service_network_owner as owner
from scripts import issue167_service_network_worker as worker


def example_case() -> case.Case:
    return case.Case("f287c9ad630e", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)


def example_probe() -> dict[str, object]:
    rows = []
    for offset, role in ((0, "api"), (3, "auth")):
        for i, transport in enumerate(("udp", "tcp")):
            rows.append(
                {
                    "sequence": offset + i + 1,
                    "role": role,
                    "category": "dns_A",
                    "transport": transport,
                    "outcome": "observed",
                    "address": "28.0.5.94",
                    "ttl": 1,
                    "received_monotonic": 10.0 + i * 0.1,
                }
            )
        rows.append(
            {
                "sequence": offset + 3,
                "role": role,
                "category": "tls_handshake",
                "outcome": "observed",
                "address": "28.0.5.94",
                "tls_version": "TLSv1.3",
                "chain_checked": True,
                "hostname_checked": True,
                "dns_expiry_monotonic": 11.0,
                "started_monotonic": 10.2,
                "completed_monotonic": 10.3,
            }
        )
    return {
        "scope": "ordinary_user_predeployment_metadata_only",
        "result": "observed_expected",
        "OS_ACL_assessed": False,
        "ipv6": "not_assessed",
        "exit_identity_claim": False,
        "counts_semantics": "entered_bounded_operation_not_wire_count",
        "dns_operations_entered": 4,
        "tls_operations_entered": 2,
        "http_requests": 0,
        "auth_cli": 0,
        "model_prompts": 0,
        "cleanup_complete": True,
        "steps": rows,
    }


def test_network_case_does_not_pollute_old_zero_network_contract() -> None:
    current = example_case()
    assert case.Case.from_dict(current.to_dict()) == current
    previous = old.Case(current.run_id, 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    assert previous.to_dict()["network_operations"] == 0
    assert "network_operations" not in current.to_dict()
    assert current.to_dict()["network_limits"] == case.LIMITS
    with pytest.raises(old.CaseRejected, match=r"^case_deadline_unknown$"):
        old.Case.from_dict(current.to_dict())


def test_unit_changes_only_network_worker_deadline_and_existing_scope() -> None:
    unit = case.render_unit(example_case())
    assert "RestrictAddressFamilies=AF_INET\n" in unit
    assert "IPAddressAllow=28.0.0.0/8 192.168.44.1/32\n" in unit
    for text in (
        "SocketBindDeny=any",
        "LimitCORE=0",
        "Delegate=no",
        "CapabilityBoundingSet=\n",
        "BindReadOnlyPaths=",
        "WorkingDirectory=/srv/pi-cwd",
    ):
        assert text in unit


def test_good_probe_has_actual_both_ttl_timestamps() -> None:
    value = example_probe()
    assert case.validate_probe(value) == value


@pytest.mark.parametrize(
    "key,value",
    [
        ("extra_raw", "secret"),
        ("dns_operations_entered", True),
        ("dns_operations_entered", 5),
        ("tls_operations_entered", 3),
        ("http_requests", 1),
        ("cleanup_complete", False),
        ("OS_ACL_assessed", True),
        ("counts_semantics", "packet_count"),
    ],
)
def test_probe_top_metadata_refuses_unknown_or_changed_fields(
    key: str, value: object
) -> None:
    result = example_probe()
    result[key] = value
    with pytest.raises(old.CaseRejected, match=r"^network_probe_unknown$"):
        case.validate_probe(result)


@pytest.mark.parametrize(
    "key,value",
    [
        ("completed_monotonic", 11.0),
        ("started_monotonic", True),
        ("completed_monotonic", float("nan")),
        ("started_monotonic", 9.0),
        ("dns_expiry_monotonic", 12.0),
    ],
)
def test_ttl_incomplete_or_expired_timing_blocks(key: str, value: object) -> None:
    result = example_probe()
    rows = cast(list[dict[str, object]], result["steps"])
    rows[2][key] = value
    with pytest.raises(old.CaseRejected, match=r"^tls_timing_unknown$"):
        case.validate_probe(result)


class FakeSocket:
    def __init__(self, *, close_fail: bool = False, connect_ok: bool = False) -> None:
        self.close_fail = close_fail
        self.connect_ok = connect_ok
        self.sent = 0
        self.closed = False

    def settimeout(self, _value: float) -> None:
        pass

    def connect(self, _peer: object) -> None:
        if not self.connect_ok:
            raise PermissionError(13, "synthetic")

    def sendto(self, data: bytes, _peer: object) -> int:
        self.sent += 1
        return len(data)

    def recvfrom(self, _size: int) -> object:
        raise TimeoutError

    def close(self) -> None:
        if self.close_fail:
            raise PermissionError(13, "synthetic-close")
        self.closed = True

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_close_error_cannot_masquerade_as_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = FakeSocket(close_fail=True)
    monkeypatch.setattr("socket.socket", lambda *_: channel)
    value = worker.denied_attempt("f287c9ad630e", 1, deadline=5, clock=lambda: 0)
    assert value["result"] == "unknown"
    assert value["cleanup_complete"] is False


@pytest.mark.parametrize("sequence", [1, 2])
def test_deny_is_single_attempt_and_closes_before_publication(
    sequence: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    channel = FakeSocket()
    monkeypatch.setattr("socket.socket", lambda *_: channel)
    value = worker.denied_attempt("f287c9ad630e", sequence, deadline=5, clock=lambda: 0)
    case.validate_deny("f287c9ad630e", sequence, value)
    assert channel.sent == (1 if sequence == 2 else 0)
    assert channel.closed


def test_unexpected_tcp_connect_is_never_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = FakeSocket(connect_ok=True)
    monkeypatch.setattr("socket.socket", lambda *_: channel)
    value = worker.denied_attempt("f287c9ad630e", 1, deadline=5, clock=lambda: 0)
    with pytest.raises(old.CaseRejected, match=r"^deny_observation_unknown$"):
        case.validate_deny("f287c9ad630e", 1, value)


def fake_operations(
    *, enabled: bool, before: tuple[int, int], after: tuple[int, int]
) -> owner.LiveOperations:
    op = object.__new__(owner.LiveOperations)
    op.enabled = enabled
    op.previous_counts = before
    op.profile = object()
    op.binding = object()
    op.contract = cast(ModuleType, SimpleNamespace(current_host_context=lambda: {}))
    op.egress = cast(ModuleType, SimpleNamespace(verify_state=lambda *_a, **_kw: after))
    op.snapshots = []
    op._snapshot = lambda: {}  # type: ignore[method-assign]
    return op


@pytest.mark.parametrize(
    "enabled,before,after,reason",
    [
        (True, (10, 2), (11, 3), "phase_packet_evidence_unknown"),
        (False, (0, 0), (1, 1), "phase_packet_evidence_unknown"),
        (True, (10, 2), (9, 2), "packet_counter_decreased"),
    ],
)
def test_late_phase_counter_fault_also_blocks_restoration(
    enabled: bool, before: tuple[int, int], after: tuple[int, int], reason: str
) -> None:
    op = fake_operations(enabled=enabled, before=before, after=after)
    with pytest.raises(base_owner.OwnerRejected, match=r"^" + reason + "$"):
        op._verify("post_stop")


class Orchestration:
    def __init__(self, fail: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail = fail
        self.restoration_stage = "complete"
        self.resolver_check = {
            "run_id": example_case().run_id,
            "before_sha256": "a" * 64,
            "after_sha256": "a" * 64,
            "comparison": "same",
            "source": "root_baseline_file_and_post_restore_read",
        }

    def step(self, name: str) -> dict[str, object]:
        self.calls.append(name)
        if self.fail == name:
            raise ValueError("synthetic")
        return {}

    def preflight(self) -> None:
        self.step("preflight")

    def reserve(self) -> None:
        self.step("reserve")

    def install(self) -> None:
        self.step("install")

    def start(self) -> None:
        self.step("start")

    def ready(self) -> dict[str, object]:
        return self.step("ready")

    def exercise_rules(self) -> dict[str, object]:
        return self.step("rules")

    def gate(self, i: int) -> None:
        self.step(f"gate{i}")

    def deny_result(self, i: int) -> dict[str, object]:
        return self.step(f"deny{i}")

    def activate(self) -> None:
        self.step("activate")

    def collect(self) -> dict[str, object]:
        return self.step("collect")

    def wait_exit(self) -> None:
        self.step("exit")

    def restore(self) -> dict[str, object]:
        self.step("restore")
        return {
            "result": "host_policy_restored",
            "global_resolver_unchanged": True,
            "ledger_retained": True,
            "table_absent": True,
            "unit_absent": True,
        }

    def finish(self) -> dict[str, object]:
        self.step("finish")
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def write_ledger(self, _value: object) -> None:
        self.step("ledger")


@pytest.mark.parametrize(
    "fail", ["deny1", "deny2", "rules", "activate", "collect", "restore"]
)
def test_any_failed_stage_stops_later_work_and_preserves_unknown(fail: str) -> None:
    op = Orchestration(fail)
    result = owner.run_owner(example_case(), cast(owner.LiveOperations, op))
    assert result["result"] == "unknown"
    if fail in {"deny1", "deny2", "rules"}:
        assert "activate" not in op.calls
    assert "finish" not in op.calls
    assert "ledger" in op.calls
    assert "network_operations" not in result


def test_orchestration_retains_new_network_scope_and_permanent_evidence() -> None:
    op = Orchestration()
    result = owner.run_owner(example_case(), cast(owner.LiveOperations, op))
    assert result["result"] == "observed_expected_and_restored"
    assert result["scope"] == "h1_service_network_preflight"
    assert op.calls.count("ledger") == 2
    assert result["resolver_check"] == op.resolver_check
    assert (
        owner.owner_envelope(example_case(), "a" * 64, result)["owner_result"]
        == "observed_expected_and_restored"
    )
    previous = copy.deepcopy(result)
    previous["scope"] = "h1_resolver_window_no_network"
    assert (
        owner.owner_envelope(example_case(), "a" * 64, previous)["owner_result"]
        == "unknown"
    )


def test_boolean_expiry_cannot_compare_equal_to_one_second() -> None:
    value = example_probe()
    rows = cast(list[dict[str, object]], value["steps"])
    rows[0]["received_monotonic"] = 0.0
    rows[1]["received_monotonic"] = 0.0
    rows[2].update(
        started_monotonic=0.1, completed_monotonic=0.2, dns_expiry_monotonic=True
    )
    with pytest.raises(old.CaseRejected, match=r"^tls_timing_unknown$"):
        case.validate_probe(value)


def deny_row(sequence: int) -> dict[str, object]:
    return {
        "run_id": example_case().run_id,
        "sequence": sequence,
        "category": "deny_tcp_connect" if sequence == 1 else "deny_udp_A",
        "attempts": 1,
        "result": "denied_or_timeout",
        "cleanup_complete": True,
    }


def test_worker_denied_without_independent_packet_delta_is_unknown() -> None:
    op = fake_operations(enabled=False, before=(0, 0), after=(0, 0))
    op.case = example_case()
    op._wait = lambda name: deny_row(1)  # type: ignore[method-assign]
    with pytest.raises(
        base_owner.OwnerRejected, match=r"^deny_packet_evidence_unknown$"
    ):
        op.deny_result(1)


def test_positive_probe_without_allowed_packet_delta_is_unknown() -> None:
    current = example_case()
    ready = {
        "run_id": current.run_id,
        "pid": 12345,
        "uid": 1000,
        "core_limits": [0, 0],
        "no_new_privs": True,
        "cap_eff_zero": True,
        "cgroup_matches": True,
        "resolver_sha256": current.resolver_sha256,
        "mount_namespace": "mnt:[12]",
        "pid_namespace": "pid:[13]",
    }
    result = {
        **ready,
        "result": "observed_expected",
        "scope": "service_network_metadata",
        "node_pi": False,
        "auth_calls": 0,
        "model_calls": 0,
        "denials": [deny_row(1), deny_row(2)],
        "probe": example_probe(),
    }
    op = fake_operations(enabled=True, before=(0, 2), after=(0, 2))
    op.case = current
    op.ready_metadata = ready
    op.contract = case
    op._wait = lambda name: result  # type: ignore[method-assign]
    op.worker_accepted = False
    with pytest.raises(
        base_owner.OwnerRejected, match=r"^allow_packet_evidence_unknown$"
    ):
        op.collect()
    assert op.worker_accepted is False
