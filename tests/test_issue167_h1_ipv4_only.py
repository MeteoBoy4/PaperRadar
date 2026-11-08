"""Independent D1: IPv4-only H1 candidate; fixtures/mocks, no sockets or host writes."""

import errno
import io
import json
import os
import selectors
import socket
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import pytest

from scripts import issue167_h1_network_worker as worker
from scripts.issue167_h1_network_bundle import create_bundle, units
from scripts.issue167_h1_phase import (
    PhaseRejected,
    Plan,
    render_phase,
    verify_nft_state,
)
from tests.test_issue167_h1_phase import nft_fixture
from tests.test_issue167_h1_phase import plan as sample_plan


def plan() -> Plan:
    return Plan("0123456789ab", 1000, 1000, network_mode="ipv4_only")


def test_ipv4_mode_is_explicitly_bound_and_legacy_shape_stays_unchanged() -> None:
    value = plan().to_dict()
    assert value["network_mode"] == "ipv4_only"
    assert value["addresses"] == ["127.0.0.1"]
    assert Plan.from_dict(json.loads(plan().to_json())) == plan()
    legacy = sample_plan().to_dict()
    assert "network_mode" not in legacy
    assert legacy["addresses"] == ["127.0.0.1", "::1"]
    assert Plan.from_dict(legacy).network_mode == "dual_stack"


@pytest.mark.parametrize("mode", [None, True, 1, "", "ipv6_only", "auto"])
def test_invalid_modes_cannot_create_an_implicit_fallback(mode: object) -> None:
    value = plan().to_dict()
    value["network_mode"] = mode
    with pytest.raises(PhaseRejected, match=r"^plan_network_mode_invalid$"):
        Plan.from_dict(value)


def test_removing_ipv4_mode_or_expanding_addresses_breaks_binding() -> None:
    value = plan().to_dict()
    value.pop("network_mode")
    with pytest.raises(PhaseRejected, match=r"^plan_binding_mismatch$"):
        Plan.from_dict(value)
    value = plan().to_dict()
    value["addresses"] = ["127.0.0.1", "::1"]
    with pytest.raises(PhaseRejected, match=r"^plan_binding_mismatch$"):
        Plan.from_dict(value)


def test_service_family_and_ip_allowlists_enforce_ipv4_only() -> None:
    selected = plan()
    rendered = units(selected)
    assert "RestrictAddressFamilies=AF_INET\n" in rendered[selected.unit]
    assert (
        "RestrictAddressFamilies=AF_UNIX AF_NETLINK AF_INET\n"
        in rendered[selected.guardian_unit]
    )
    for body in rendered.values():
        assert "AF_INET6" not in body
        assert "IPAddressAllow=127.0.0.1/32\n" in body
        assert "::1" not in body
        assert "NoNewPrivileges=yes" in body
        assert "LimitCORE=0" in body


@pytest.mark.parametrize("phase,port", [("a", 38167), ("b", 38169)])
def test_rules_have_no_ipv6_allow_and_keep_inet_default_rejection(
    phase: str, port: int
) -> None:
    rendered = render_phase(plan(), phase)
    assert f"ip daddr 127.0.0.1 tcp dport {port}" in rendered
    assert "ip6" not in rendered and "::1" not in rendered
    assert rendered.count("counter name allowed accept") == 1
    assert "reject with icmpx type admin-prohibited" in rendered


def test_verifier_requires_ipv4_shape_and_rejects_an_ipv6_allow_rule() -> None:
    payload = nft_fixture("a")
    with pytest.raises(PhaseRejected, match=r"^nft_state_unknown$"):
        verify_nft_state(plan(), "a", payload)
    rows = payload["nftables"]
    assert isinstance(rows, list)
    payload["nftables"] = [
        row
        for row in rows
        if not (
            isinstance(row, dict)
            and isinstance(row.get("rule"), dict)
            and row["rule"].get("comment", "").endswith(":ipv6")
        )
    ]
    assert verify_nft_state(plan(), "a", payload) == (4, 7)


def test_phase_budget_distinguishes_socket_checks_from_connection_attempts() -> None:
    selected = plan()
    for phase in ("a", "b"):
        rows = worker.probes(selected, phase)
        assert [item.case for item in rows] == [
            "v6-socket-tcp",
            "v6-socket-udp",
            "v4-current-tcp",
            "v4-other-tcp",
            "v4-blocked-tcp",
            "v4-blocked-udp",
            "v4-dns-udp",
        ]
        checks = [item for item in rows if item.kind == "socket_check"]
        connections = [item for item in rows if item.kind != "socket_check"]
        assert len(checks) == 2 and len(connections) == 5
        assert all(item.port == 0 and item.family == "v6" for item in checks)
        assert all(item.expected == "deny" for item in checks)
        assert all(item.family == "v4" for item in connections)


@pytest.mark.parametrize(
    "number,outcome,category",
    [
        (errno.EPERM, "denied", "permission_denied"),
        (errno.EACCES, "denied", "permission_denied"),
        (errno.EAFNOSUPPORT, "denied", "address_family_unavailable"),
        (errno.EPROTONOSUPPORT, "denied", "address_family_unavailable"),
        (errno.ETIMEDOUT, "unknown", "timed_out"),
        (errno.EINVAL, "unknown", "other"),
        (errno.ECONNREFUSED, "unknown", "connection_refused"),
    ],
)
def test_ipv6_creation_uses_only_closed_errors_and_never_sends(
    monkeypatch: pytest.MonkeyPatch, number: int, outcome: str, category: str
) -> None:
    calls = []

    def denied(family: int, kind: int) -> socket.socket:
        calls.append((family, kind))
        raise OSError(number, "EXTERNAL_PRIVATE_SENTINEL")

    monkeypatch.setattr(socket, "socket", denied)
    probe = worker.probes(plan(), "a")[0]
    result = worker.run_probe(probe)
    assert calls == [(socket.AF_INET6, socket.SOCK_STREAM)]
    assert result["outcome"] == outcome
    assert result["errno_category"] == category
    assert result["kind"] == "socket_check" and result["port"] == 0
    assert "EXTERNAL_PRIVATE_SENTINEL" not in json.dumps(result)


def test_unexpected_ipv6_creation_success_is_closed_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class Socket:
        def __init__(self, family: int, kind: int) -> None:
            assert family == socket.AF_INET6 and kind == socket.SOCK_DGRAM

        def close(self) -> None:
            calls.append("closed")

        def connect(self, _address: object) -> None:
            raise AssertionError("socket-only check must not connect")

        def send(self, _body: object) -> None:
            raise AssertionError("socket-only check must not send")

    monkeypatch.setattr(socket, "socket", Socket)
    result = worker.run_probe(worker.probes(plan(), "a")[1])
    assert result["outcome"] == "allowed"
    assert result["errno_category"] == "none"
    assert calls == ["closed"]


def test_socket_close_error_does_not_masquerade_as_creation_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Socket:
        def __init__(self, family: int, kind: int) -> None:
            assert family == socket.AF_INET6 and kind == socket.SOCK_STREAM

        def close(self) -> None:
            raise PermissionError(errno.EPERM, "CLOSE_PRIVATE_SENTINEL")

    monkeypatch.setattr(socket, "socket", Socket)
    result = worker.run_probe(worker.probes(plan(), "a")[0])
    assert result["outcome"] == "unknown"
    assert result["errno_category"] == "other"
    assert "CLOSE_PRIVATE_SENTINEL" not in json.dumps(result)


def test_ipv6_boundary_failure_prevents_all_connection_attempts() -> None:
    calls = []

    def unexpected(probe: worker.Probe) -> worker.ProbeRow:
        calls.append(probe.case)
        return {
            "case": probe.case,
            "kind": probe.kind,
            "family": probe.family,
            "port": probe.port,
            "expected": probe.expected,
            "outcome": "allowed",
            "errno_category": "none",
        }

    rows, complete = worker.run_phase(plan(), "a", perform=unexpected)
    assert not complete and len(rows) == 1
    assert calls == ["v6-socket-tcp"]


def test_peer_inventory_never_creates_a_v6_listener() -> None:
    assert worker.peer_endpoints(plan()) == ((socket.AF_INET, "127.0.0.1"),)
    assert worker.peer_endpoints(sample_plan()) == (
        (socket.AF_INET, "127.0.0.1"),
        (socket.AF_INET6, "::1"),
    )


def test_real_peer_setup_uses_only_two_v4_listeners_with_mocked_sockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class Socket:
        def __init__(self, family: int, kind: int) -> None:
            assert family == socket.AF_INET and kind == socket.SOCK_STREAM
            calls.append(("socket", family, kind))

        def bind(self, address: tuple[str, int]) -> None:
            calls.append(("bind", *address))

        def listen(self, backlog: int) -> None:
            assert backlog == 8

        def setblocking(self, enabled: bool) -> None:
            assert enabled is False

        def close(self) -> None:
            calls.append(("closed",))

    class Selector:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def register(self, channel: Socket, events: int) -> None:
            assert isinstance(channel, Socket) and events == 1

    clock = iter((0.0, 121.0))
    output = io.BytesIO()
    with monkeypatch.context() as patch:
        patch.setattr(socket, "socket", Socket)
        patch.setattr(os, "getuid", lambda: 1000)
        patch.setattr(os, "getgid", lambda: 1000)
        patch.setattr(time, "monotonic", lambda: next(clock))
        patch.setattr(selectors, "DefaultSelector", Selector)
        patch.setattr(sys, "stdout", SimpleNamespace(buffer=output))
        worker.execute_peer(plan())
    assert output.getvalue() == b"READY\n"
    assert calls == [
        ("socket", socket.AF_INET, socket.SOCK_STREAM),
        ("bind", "127.0.0.1", 38167),
        ("socket", socket.AF_INET, socket.SOCK_STREAM),
        ("bind", "127.0.0.1", 38169),
        ("closed",),
        ("closed",),
    ]


def test_generated_review_does_not_retain_dual_stack_budget_or_allowlists(
    tmp_path: Path,
) -> None:
    selected = replace(plan(), uid=os.getuid(), gid=os.getgid())
    root = create_bundle(tmp_path / "ipv4-review", selected)
    value = json.loads((root / "plan.json").read_text())
    assert value["network_mode"] == "ipv4_only"
    assert value["addresses"] == ["127.0.0.1"]
    review = (root / "owner-review.md").read_text()
    assert "network_mode=ipv4_only" in review
    assert "最多10次IPv4连接" in review
    assert "最多4次IPv6创建检查(零报文)" in review
    assert "合计最多20次" not in review
    assert "每阶段最多10次本机连接" not in review
    wizard = (root / "owner-wizard.sh").read_text()
    assert "最多10次IPv4连接/发送与4次IPv6创建(零报文)" in wizard
    assert "20次本机尝试" not in wizard
    for unit in (selected.unit, selected.guardian_unit):
        body = (root / unit).read_text()
        assert "AF_INET6" not in body and "::1" not in body
