"""Independent D1: codecs and mocked I/O only, never DNS/TLS/root execution."""

import hashlib
import json
import os
import resource
import socket
import ssl
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest

from scripts import issue167_dns_tls as probe

PLAN = Path(__file__).parents[1] / "intent/review/issue-167/real-exit-plan-v1.json"


def response(
    host: str = probe.HOSTS[0], *, ttl: int = 30, address: str = "28.0.5.94"
) -> bytes:
    return (
        struct.pack("!6H", 1, 0x8180, 1, 1, 0, 0)
        + probe.question(host, 1)[12:]
        + b"\xc0\x0c"
        + struct.pack("!HHIH", 1, 1, ttl, 4)
        + socket.inet_aton(address)
    )


def test_dns_known_question_and_compressed_single_A() -> None:
    assert (
        probe.question(probe.HOSTS[0], 1).hex()
        == "00010100000100000000000003617069066f70656e616903636f6d0000010001"
    )
    assert probe.parse_answer(response(), probe.HOSTS[0], 1, 5) == probe.DNSResult(
        "28.0.5.94", 30, 5
    )


@pytest.mark.parametrize(
    "field,value",
    [
        (0, 2),
        (1, 0x8380),
        (1, 0x8183),
        (1, 0x0180),
        (1, 0xC180),
        (2, 0),
        (3, 2),
        (4, 1),
        (5, 1),
    ],
)
def test_dns_bad_header_is_unknown(field: int, value: int) -> None:
    raw = response()
    header = list(struct.unpack("!6H", raw[:12]))
    header[field] = value
    with pytest.raises(probe.ProbeRejected, match=r"^dns_shape_unknown$"):
        probe.parse_answer(struct.pack("!6H", *header) + raw[12:], probe.HOSTS[0], 1, 0)


@pytest.mark.parametrize(
    "raw", [b"", response()[:-1], response() + b"extra", b"x" * 4097]
)
def test_dns_truncation_excess_and_trailing_data_are_unknown(raw: bytes) -> None:
    with pytest.raises(probe.ProbeRejected, match=r"^dns_(shape|answer)_unknown$"):
        probe.parse_answer(raw, probe.HOSTS[0], 1, 0)


def test_dns_loop_and_non_ascii_label_refused() -> None:
    raw = response()
    question_offset = len(probe.question(probe.HOSTS[0], 1))
    loop = (
        raw[:question_offset]
        + struct.pack("!H", 0xC000 | question_offset)
        + raw[question_offset + 2 :]
    )
    with pytest.raises(probe.ProbeRejected, match=r"^dns_shape_unknown$"):
        probe.parse_answer(loop, probe.HOSTS[0], 1, 0)
    changed = raw[:13] + b"\xff" + raw[14:]
    with pytest.raises(probe.ProbeRejected, match=r"^dns_shape_unknown$"):
        probe.parse_answer(changed, probe.HOSTS[0], 1, 0)


def test_dns_other_question_cname_zero_ttl_and_pool_escape_refused() -> None:
    with pytest.raises(probe.ProbeRejected, match=r"^dns_question_unknown$"):
        probe.parse_answer(response(probe.HOSTS[1]), probe.HOSTS[0], 1, 0)
    raw = response()
    offset = len(probe.question(probe.HOSTS[0], 1)) + 2
    cname = raw[:offset] + b"\0\5" + raw[offset + 2 :]
    with pytest.raises(probe.ProbeRejected, match=r"^dns_answer_unknown$"):
        probe.parse_answer(cname, probe.HOSTS[0], 1, 0)
    with pytest.raises(probe.ProbeRejected, match=r"^dns_ttl_unknown$"):
        probe.parse_answer(response(ttl=0), probe.HOSTS[0], 1, 0)
    with pytest.raises(probe.ProbeRejected, match=r"^address_outside_pool$"):
        probe.parse_answer(response(address="104.18.0.1"), probe.HOSTS[0], 1, 0)


def copy_plan(tmp_path: Path) -> Path:
    path = tmp_path / "plan.json"
    path.write_bytes(PLAN.read_bytes())
    path.chmod(0o644)
    return path


def test_actual_frozen_plan_is_loadable(tmp_path: Path) -> None:
    path = copy_plan(tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert probe.load_plan(path, digest)["kind"] == "issue167_real_exit_review_plan"


@pytest.mark.parametrize(
    "change",
    [
        "pool",
        "raw_pool",
        "resolver",
        "budget",
        "step",
        "CA_override",
        "scope",
        "rcode",
        "ttl",
        "bool_deadline",
        "router_mode",
        "redirect",
        "dns_hijack",
        "exit_claim",
        "upstream_claim",
        "role_claim",
    ],
)
def test_semantic_plan_changes_refused_even_with_recomputed_hash(
    tmp_path: Path, change: str
) -> None:
    value = json.loads(PLAN.read_text())
    candidate = value["candidate_probe"]
    if change == "pool":
        value["accepted_policy"]["pool_cidr"] = "28.0.0.0/7"
    elif change == "raw_pool":
        value["owner_report"]["pool_config_raw"] = "28.0.0.0/8"
    elif change == "resolver":
        candidate["resolver"] = "8.8.8.8"
    elif change == "budget":
        candidate["limits"]["dns_queries"] = 5
    elif change == "step":
        candidate["steps"][2]["hostname"] = "other.example"
    elif change == "CA_override":
        candidate["tls_trust"]["environment_CA_override"] = True
    elif change == "scope":
        candidate["root_required"] = True
    elif change == "rcode":
        candidate["dns_acceptance"]["rcode"] = "ANY"
    elif change == "ttl":
        candidate["tls_start_and_finish_before_both_DNS_TTL_expire"] = False
    elif change == "router_mode":
        value["owner_report"]["mode"] = "redir-host"
    elif change == "redirect":
        value["owner_report"]["forwarded_tcp_redirect_port"] = 7893
    elif change == "dns_hijack":
        value["owner_report"]["lan_dns_hijack_transports"] = ["udp"]
    elif change == "exit_claim":
        value["accepted_policy"]["exit_identity_claim"] = True
    elif change == "upstream_claim":
        value["accepted_policy"]["upstream_mapping_verified"] = True
    elif change == "role_claim":
        value["accepted_policy"]["api_auth_separation_claim"] = True
    else:
        candidate["wall_deadline_seconds"] = True
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(value))
    path.chmod(0o644)
    with pytest.raises(probe.ProbeRejected, match=r"^plan_unknown$"):
        probe.load_plan(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_hash_and_duplicate_json_keys_refused(tmp_path: Path) -> None:
    path = copy_plan(tmp_path)
    with pytest.raises(probe.ProbeRejected, match=r"^plan_changed$"):
        probe.load_plan(path, "0" * 64)
    path.write_text('{"kind":1,"kind":2}')
    with pytest.raises(probe.ProbeRejected, match=r"^plan_unknown$"):
        probe.load_plan(path, hashlib.sha256(path.read_bytes()).hexdigest())


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeOperations:
    cleanup_complete = True

    def __init__(self, clock: Clock, failure: str = "") -> None:
        self.clock = clock
        self.failure = failure
        self.calls: list[tuple[str, str]] = []

    def dns(
        self, host: str, transport: Literal["udp", "tcp"], deadline: float
    ) -> probe.DNSResult:
        self.calls.append((host, transport))
        if self.failure == "dns":
            raise RuntimeError("PRIVATE_EXTERNAL_ERROR")
        self.clock.now += 6 if self.failure == "dns_late" else 0.1
        address = "28.0.5.94" if host == probe.HOSTS[0] else "28.0.5.167"
        if self.failure == "disagreement" and transport == "tcp":
            address = "28.0.1.1"
        received = self.clock.now + 1 if self.failure == "future" else self.clock.now
        return probe.DNSResult(
            address, 1 if self.failure == "expired" else 30, received
        )

    def tls(self, host: str, address: str, deadline: float) -> str:
        self.calls.append((host, "tls"))
        self.clock.now += (
            11
            if self.failure == "tls_late"
            else 2
            if self.failure == "expired"
            else 0.1
        )
        if self.failure == "tls":
            raise ssl.SSLError("PRIVATE_TLS_ERROR")
        return "TLSv1.3"


def test_probe_exact_sequence_counts_and_no_acl_claim() -> None:
    clock = Clock()
    operations = FakeOperations(clock)
    value = probe.run_probe(operations, clock=clock)
    assert value["result"] == "observed_expected"
    assert value["dns_operations_entered"] == 4 and value["tls_operations_entered"] == 2
    assert value["OS_ACL_assessed"] is False and value["ipv6"] == "not_assessed"
    assert operations.calls == [
        (host, category) for host in probe.HOSTS for category in ["udp", "tcp", "tls"]
    ]
    assert value["http_requests"] == value["auth_cli"] == value["model_prompts"] == 0


@pytest.mark.parametrize(
    "failure,reason,calls",
    [
        ("dns", "observation_unknown", 1),
        ("dns_late", "deadline_unknown", 1),
        ("future", "dns_ttl_unknown", 1),
        ("disagreement", "dns_disagreement", 2),
        ("tls", "observation_unknown", 3),
        ("tls_late", "deadline_unknown", 3),
        ("expired", "deadline_unknown", 3),
    ],
)
def test_first_unknown_stops_without_retry_or_error_text(
    failure: str, reason: str, calls: int
) -> None:
    clock = Clock()
    operations = FakeOperations(clock, failure)
    value = probe.run_probe(operations, clock=clock)
    assert value["result"] == "unknown" and value["failure_reason"] == reason
    assert len(operations.calls) == calls
    assert "PRIVATE_" not in json.dumps(value)


class SocketStub:
    def __init__(
        self, raw: bytes = b"", peer: tuple[str, int] = (probe.RESOLVER, 53)
    ) -> None:
        self.raw = raw
        self.peer = peer
        self.calls: list[tuple[object, ...]] = []
        self.close_failure = False

    def settimeout(self, value: float) -> None:
        self.calls.append(("timeout", value))

    def sendto(self, value: bytes, target: tuple[str, int]) -> int:
        self.calls.append(("sendto", target))
        return len(value)

    def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
        self.calls.append(("recvfrom", size))
        return self.raw, self.peer

    def connect(self, target: tuple[str, int]) -> None:
        self.calls.append(("connect", target))

    def sendall(self, value: bytes) -> None:
        self.calls.append(("sendall", len(value)))

    def recv(self, count: int) -> bytes:
        part = self.raw[: min(2, count)]
        self.raw = self.raw[len(part) :]
        return part

    def do_handshake(self) -> None:
        self.calls.append(("handshake",))

    def version(self) -> str:
        return "TLSv1.3"

    def close(self) -> None:
        self.calls.append(("close",))
        if self.close_failure:
            raise OSError("PRIVATE_CLOSE_ERROR")


@pytest.mark.parametrize("transport", ["udp", "tcp"])
def test_socket_dns_targets_only_router_no_resolver_or_fallback(
    monkeypatch: pytest.MonkeyPatch, transport: Literal["udp", "tcp"]
) -> None:
    raw = response()
    channel = SocketStub(
        raw if transport == "udp" else struct.pack("!H", len(raw)) + raw
    )
    monkeypatch.setattr(socket, "socket", lambda *_args: channel)
    monkeypatch.setattr(os, "urandom", lambda _n: b"\0\1")
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *_a: pytest.fail("implicit resolver")
    )
    result = probe.SocketOperations("0" * 64, clock=lambda: 0).dns(
        probe.HOSTS[0], transport, 5
    )
    assert result.address == "28.0.5.94"
    assert channel.calls[-1] == ("close",)
    assert (
        ("sendto", (probe.RESOLVER, 53)) in channel.calls
        if transport == "udp"
        else ("connect", (probe.RESOLVER, 53)) in channel.calls
    )


def test_wrong_udp_source_stops_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SocketStub(response(), ("8.8.8.8", 53))
    monkeypatch.setattr(socket, "socket", lambda *_args: channel)
    with pytest.raises(probe.ProbeRejected, match=r"^dns_peer_unknown$"):
        probe.SocketOperations("0" * 64, clock=lambda: 0).dns(probe.HOSTS[0], "udp", 5)
    assert channel.calls[-1] == ("close",)


def test_tls_literal_address_SNI_and_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SocketStub()
    secure = SocketStub()
    wrapped = []
    monkeypatch.setattr(socket, "socket", lambda *_args: channel)
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *_a: pytest.fail("implicit resolver")
    )

    def wrap(raw: object, **kwargs: object) -> SocketStub:
        assert raw is channel
        wrapped.append(kwargs)
        return secure

    operations = probe.SocketOperations("0" * 64, clock=lambda: 0)
    monkeypatch.setattr(
        operations,
        "_context",
        lambda: cast(ssl.SSLContext, SimpleNamespace(wrap_socket=wrap)),
    )
    assert operations.tls(probe.HOSTS[0], "28.0.5.94", 10) == "TLSv1.3"
    assert ("connect", ("28.0.5.94", 443)) in channel.calls
    assert wrapped == [
        {"server_hostname": probe.HOSTS[0], "do_handshake_on_connect": False}
    ]
    assert secure.calls[-1] == ("close",)
    assert not any(c[0] in {"sendall", "sendto"} for c in channel.calls + secure.calls)


def test_ca_uses_same_verified_bytes_without_environment_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = b"PUBLIC_CA_FIXTURE"
    path = tmp_path / "ca.pem"
    path.write_bytes(raw)
    path.chmod(0o644)
    monkeypatch.setattr(probe, "CA_FILE", path)
    recorded = []
    context = SimpleNamespace(load_verify_locations=lambda **kw: recorded.append(kw))
    monkeypatch.setattr(ssl, "SSLContext", lambda protocol: context)
    operations = probe.SocketOperations(hashlib.sha256(raw).hexdigest())
    assert operations._context() is cast(ssl.SSLContext, context)
    assert recorded == [{"cadata": raw.decode()}]
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    path.write_bytes(b"CHANGED")
    with pytest.raises(probe.ProbeRejected, match=r"^ca_changed$"):
        operations._context()


def test_cleanup_failure_does_not_overwrite_primary_failure() -> None:
    operations = probe.SocketOperations("0" * 64, clock=lambda: 0)
    channel = SocketStub()
    channel.close_failure = True
    with pytest.raises(probe.ProbeRejected, match=r"^dns_peer_unknown$"):
        try:
            raise probe.ProbeRejected("dns_peer_unknown")
        finally:
            operations._close(cast(socket.socket, channel))
    assert operations.cleanup_complete is False


def test_close_keyboard_interrupt_is_incomplete_and_primary_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = probe.SocketOperations("0" * 64, clock=lambda: 0)
    channel = SocketStub()

    def interrupted() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(channel, "close", interrupted)
    with pytest.raises(probe.ProbeRejected, match=r"^cleanup_unknown$"):
        operations._close(cast(socket.socket, channel))
    assert operations.cleanup_complete is False
    with pytest.raises(probe.ProbeRejected, match=r"^dns_peer_unknown$"):
        try:
            raise probe.ProbeRejected("dns_peer_unknown")
        finally:
            operations._close(cast(socket.socket, channel))


def test_execute_persistent_reservation_precedes_io_and_prevents_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    clock = Clock()
    operations = FakeOperations(clock)
    monkeypatch.setattr(probe, "SocketOperations", lambda _sha, **_kw: operations)
    monkeypatch.setattr(
        probe,
        "run_probe",
        lambda ops, **_kw: {"result": "unknown", "failure_reason": "fixture_unknown"},
    )
    monkeypatch.setattr(resource, "setrlimit", lambda *_args: None)
    monkeypatch.setattr(resource, "getrlimit", lambda *_args: (0, 0))
    plan = copy_plan(tmp_path)
    sha = hashlib.sha256(plan.read_bytes()).hexdigest()
    result = probe.execute(plan, sha, state, owner_config_confirmed=True)
    assert result["result"] == "unknown"
    marker = state / "execution-started.json"
    assert marker.stat().st_mode & 0o777 == 0o600
    previous = marker.read_bytes()
    with pytest.raises(probe.ProbeRejected, match=r"^case_already_consumed$"):
        probe.execute(plan, sha, state, owner_config_confirmed=True)
    assert marker.read_bytes() == previous and operations.calls == []


def test_root_missing_confirmation_help_and_default_never_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(socket, "socket", lambda *_args: pytest.fail("network"))
    sha = hashlib.sha256(PLAN.read_bytes()).hexdigest()
    with pytest.raises(
        probe.ProbeRejected, match=r"^external_owner_confirmation_required$"
    ):
        probe.execute(PLAN, sha, tmp_path, owner_config_confirmed=False)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(probe.ProbeRejected, match=r"^ordinary_user_required$"):
        probe.execute(PLAN, sha, tmp_path, owner_config_confirmed=True)
    with pytest.raises(SystemExit) as help_exit:
        probe.main(["--help"])
    assert help_exit.value.code == 0
    with pytest.raises(SystemExit) as default_exit:
        probe.main([])
    assert default_exit.value.code == 2
    assert "自证" in capsys.readouterr().out


def test_passed_in_deadline_is_not_reset_by_network_loop() -> None:
    clock = Clock()
    clock.now = 40
    operations = FakeOperations(clock, "dns_late")
    value = probe.run_probe(operations, clock=clock, deadline=45)
    assert value["result"] == "unknown"
    assert value["failure_reason"] == "deadline_unknown"
    assert operations.calls == [(probe.HOSTS[0], "udp")]


def test_execute_includes_plan_loading_in_absolute_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    plan = copy_plan(tmp_path)
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    clock = Clock()
    original = probe.load_plan

    def slow_load(path: Path, sha: str) -> dict[str, object]:
        value = original(path, sha)
        clock.now = 46
        return value

    monkeypatch.setattr(probe, "load_plan", slow_load)
    monkeypatch.setattr(socket, "socket", lambda *_args: pytest.fail("network"))
    with pytest.raises(probe.ProbeRejected, match=r"^deadline_unknown$"):
        probe.execute(plan, digest, state, owner_config_confirmed=True, clock=clock)
    assert list(state.iterdir()) == []


def test_late_final_fsync_cannot_return_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    plan = copy_plan(tmp_path)
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    clock = Clock()
    operations = FakeOperations(clock)
    monkeypatch.setattr(probe, "SocketOperations", lambda _sha, **_kw: operations)
    monkeypatch.setattr(
        probe, "run_probe", lambda _ops, **_kw: {"result": "observed_expected"}
    )
    monkeypatch.setattr(resource, "setrlimit", lambda *_args: None)
    monkeypatch.setattr(resource, "getrlimit", lambda *_args: (0, 0))
    calls = 0

    def fsync(_fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            clock.now = 56

    monkeypatch.setattr(os, "fsync", fsync)
    with pytest.raises(probe.ProbeRejected, match=r"^deadline_unknown$"):
        probe.execute(plan, digest, state, owner_config_confirmed=True, clock=clock)
    assert (state / "execution-started.json").exists()
    value = json.loads((state / "result.json").read_text())
    assert value["completion_requires_successful_process_exit"] is True
