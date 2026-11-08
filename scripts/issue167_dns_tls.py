"""#167 predeployment metadata probe; import/help are inert, execution needs approval.

This utility cannot verify external authorization or router configuration. The CLI
confirmation only records a caller's statement. It neither installs nor tests ACLs.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import os
import re
import resource
import socket
import ssl
import stat
import struct
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

HOSTS = ("api.openai.com", "auth.openai.com")
RESOLVER = "192.168.44.1"
POOL = ipaddress.IPv4Network("28.0.0.0/8")
CA_FILE = Path("/etc/ssl/certs/ca-certificates.crt")
MAX_DNS = 4096
Clock = Callable[[], float]


class ProbeRejected(ValueError):
    """Only controlled reasons; never serialize external exception text."""


def remaining(deadline: float, clock: Clock) -> float:
    value = deadline - clock()
    if not math.isfinite(value) or value <= 0:
        raise ProbeRejected("deadline_unknown")
    return value


def hostname(host: str) -> None:
    if host not in HOSTS:
        raise ProbeRejected("hostname_unknown")


def pool_address(value: str) -> str:
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        raise ProbeRejected("address_unknown") from None
    if address not in POOL:
        raise ProbeRejected("address_outside_pool")
    return str(address)


def question(host: str, transaction: int) -> bytes:
    hostname(host)
    if type(transaction) is not int or not 0 <= transaction <= 65535:
        raise ProbeRejected("transaction_unknown")
    labels = b"".join(
        bytes([len(label)]) + label.encode("ascii") for label in host.split(".")
    )
    return struct.pack("!6H", transaction, 0x0100, 1, 0, 0, 0) + labels + b"\0\0\1\0\1"


def _name(raw: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    cursor = offset
    end: int | None = None
    seen: set[int] = set()
    for _ in range(128):
        if cursor < 12 or cursor >= len(raw) or cursor in seen:
            raise ProbeRejected("dns_shape_unknown")
        seen.add(cursor)
        size = raw[cursor]
        if size & 0xC0 == 0xC0:
            if cursor + 1 >= len(raw):
                raise ProbeRejected("dns_shape_unknown")
            pointer = ((size & 63) << 8) | raw[cursor + 1]
            if not 12 <= pointer < cursor:
                raise ProbeRejected("dns_shape_unknown")
            if end is None:
                end = cursor + 2
            cursor = pointer
            continue
        if size & 0xC0:
            raise ProbeRejected("dns_shape_unknown")
        cursor += 1
        if size == 0:
            name = ".".join(labels).lower()
            if len(name) > 253:
                raise ProbeRejected("dns_shape_unknown")
            return name, cursor if end is None else end
        if size > 63 or cursor + size > len(raw):
            raise ProbeRejected("dns_shape_unknown")
        try:
            label = raw[cursor : cursor + size].decode("ascii")
        except UnicodeError:
            raise ProbeRejected("dns_shape_unknown") from None
        if re.fullmatch(r"[A-Za-z0-9-]+", label) is None:
            raise ProbeRejected("dns_shape_unknown")
        labels.append(label)
        cursor += size
    raise ProbeRejected("dns_shape_unknown")


@dataclass(frozen=True)
class DNSResult:
    address: str
    ttl: int
    received: float

    @property
    def expires(self) -> float:
        return self.received + self.ttl


def parse_answer(raw: bytes, host: str, transaction: int, received: float) -> DNSResult:
    hostname(host)
    if not 12 <= len(raw) <= MAX_DNS or not math.isfinite(received):
        raise ProbeRejected("dns_shape_unknown")
    identifier, flags, qd, an, ns, ar = struct.unpack("!6H", raw[:12])
    if (
        identifier != transaction
        or not flags & 0x8000
        or flags & 0x7800
        or flags & 0x0200
        or flags & 0x0040
        or flags & 15
        or (qd, an, ns, ar) != (1, 1, 0, 0)
    ):
        raise ProbeRejected("dns_shape_unknown")
    name, cursor = _name(raw, 12)
    if name != host or cursor + 4 > len(raw) or raw[cursor : cursor + 4] != b"\0\1\0\1":
        raise ProbeRejected("dns_question_unknown")
    name, cursor = _name(raw, cursor + 4)
    if name != host or cursor + 10 > len(raw):
        raise ProbeRejected("dns_answer_unknown")
    kind, dns_class, ttl, length = struct.unpack("!HHIH", raw[cursor : cursor + 10])
    cursor += 10
    if (kind, dns_class, length) != (1, 1, 4) or cursor + 4 != len(raw):
        raise ProbeRejected("dns_answer_unknown")
    if ttl == 0:
        raise ProbeRejected("dns_ttl_unknown")
    return DNSResult(
        pool_address(str(ipaddress.IPv4Address(raw[cursor:]))), ttl, received
    )


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ProbeRejected("plan_unknown")
        value[key] = item
    return value


def _same(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def load_plan(path: Path, expected_sha: str) -> dict[str, object]:
    if re.fullmatch(r"[a-f0-9]{64}", expected_sha) is None:
        raise ProbeRejected("plan_unknown")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o022:
            raise ProbeRejected("plan_unknown")
        raw = source.read(65537)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ProbeRejected("plan_changed")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs)
        if type(value) is not dict:
            raise ProbeRejected("plan_unknown")
        report = value["owner_report"]
        policy = value["accepted_policy"]
        probe = value["candidate_probe"]
        required_allow = [
            {
                "family": "ipv4",
                "transport": "tcp",
                "destination": "28.0.0.0/8",
                "ports": [443],
            },
            {
                "family": "ipv4",
                "transport": "udp",
                "destination": RESOLVER,
                "ports": [53],
            },
            {
                "family": "ipv4",
                "transport": "tcp",
                "destination": RESOLVER,
                "ports": [53],
            },
        ]
        if (
            report["router"] != RESOLVER
            or report["pool_config_raw"] != "28.0.0.1/8"
            or report["mode"] != "fake-ip"
            or report["software"] != "OpenClash"
            or not _same(report["forwarded_tcp_redirect_port"], 7892)
            or not _same(report["lan_dns_hijack_transports"], ["tcp", "udp"])
            or report["dns_hijack_target"] != "router"
            or report["sniffer_override_destination"] is not True
            or report["tls_intermediary_absent"] is not True
            or policy["pool_cidr"] != str(POOL)
            or policy["ipv6"] != "not_assessed"
            or policy["exit_identity_claim"] is not False
            or policy["upstream_mapping_verified"] is not False
            or policy["api_auth_separation_claim"] is not False
            or policy["reported_A_is_allowlist"] is not False
            or policy["configuration_installed"] is not False
            or not _same(policy["allow"], required_allow)
            or probe["resolver"] != RESOLVER
            or not _same(probe["resolver_port"], 53)
        ):
            raise ProbeRejected("plan_unknown")
        limits = {
            "dns_queries": 4,
            "dns_udp_sends": 2,
            "dns_tcp_connections": 2,
            "tls_tcp_connections": 2,
            "tls_handshakes": 2,
            "http_requests": 0,
            "auth_cli": 0,
            "model_prompts": 0,
            "implicit_dns_queries": 0,
            "retries": 0,
            "fallbacks": 0,
            "ipv6_probes": 0,
        }
        if not _same(probe["limits"], limits):
            raise ProbeRejected("plan_unknown")
        trust = probe["tls_trust"]
        if (
            trust["ca_bundle"] != str(CA_FILE)
            or re.fullmatch(r"[a-f0-9]{64}", trust["sha256"]) is None
            or trust["environment_CA_override"] is not False
            or trust["client_certificate"] is not False
            or trust["client_private_key"] is not False
            or probe["scope"] != "ordinary_user_predeployment_metadata_only"
            or probe["root_required"] is not False
            or probe["deploys_allow_rules"] is not False
            or probe["host_configuration_changes"] is not False
            or probe["router_configuration_changes"] is not False
            or probe["collector_cannot_prove_os_acl"] is not True
            or probe["tls_uses_no_system_resolver"] is not True
            or probe["tls_deadline_includes_tcp"] is not True
            or probe["tls_start_and_finish_before_both_DNS_TTL_expire"] is not True
        ):
            raise ProbeRejected("plan_unknown")
        dns_acceptance = {
            "UDP_TCP_must_agree": True,
            "all_A_in_frozen_pool": True,
            "cname": "unknown_stop",
            "max_response_bytes": 4096,
            "positive_TTL": True,
            "qclass": "IN",
            "qtype": "A",
            "question_match": True,
            "rcode": "NOERROR",
            "single_A_only": True,
            "source_resolver_match": True,
            "transaction_match": True,
            "truncation": "unknown_stop",
        }
        if not _same(probe["dns_acceptance"], dns_acceptance):
            raise ProbeRejected("plan_unknown")
        steps: list[dict[str, object]] = []
        for host in HOSTS:
            for transport in ("udp", "tcp"):
                steps.append(
                    {
                        "category": "dns_A",
                        "deadline_seconds": 5,
                        "hostname": host,
                        "query_limit": 1,
                        "sequence": len(steps) + 1,
                        "transport": transport,
                    }
                )
            steps.append(
                {
                    "address_source": "same_run_UDP_TCP_agreed_single_A",
                    "category": "tls_handshake",
                    "certificate_chain_check": True,
                    "connect_limit": 1,
                    "deadline_seconds": 10,
                    "handshake_limit": 1,
                    "hostname": host,
                    "hostname_check": True,
                    "minimum_tls": "1.2",
                    "port": 443,
                    "sequence": len(steps) + 1,
                    "sni": host,
                    "transport": "tcp",
                }
            )
        if not _same(probe["steps"], steps):
            raise ProbeRejected("plan_unknown")
        if not _same(probe["wall_deadline_seconds"], 45) or not _same(
            probe["cleanup_deadline_seconds"], 10
        ):
            raise ProbeRejected("plan_unknown")
        return value
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ProbeRejected("plan_unknown") from None


class Operations(Protocol):
    @property
    def cleanup_complete(self) -> bool: ...

    def dns(
        self, host: str, transport: Literal["udp", "tcp"], deadline: float
    ) -> DNSResult: ...
    def tls(self, host: str, address: str, deadline: float) -> str: ...


class SocketOperations:
    def __init__(self, ca_sha256: str, *, clock: Clock = time.monotonic) -> None:
        self.ca_sha256 = ca_sha256
        self.clock = clock
        self.cleanup_complete = True

    def _close(self, channel: socket.socket) -> None:
        primary_failure = sys.exc_info()[0] is not None
        start = self.clock()
        try:
            channel.close()
            if self.clock() - start >= 10:
                raise ProbeRejected("cleanup_unknown")
        except BaseException:
            self.cleanup_complete = False
            if not primary_failure:
                raise ProbeRejected("cleanup_unknown") from None

    @contextmanager
    def _socket(self, kind: int) -> Iterator[socket.socket]:
        channel = socket.socket(socket.AF_INET, kind)
        try:
            yield channel
        finally:
            self._close(channel)

    def _read(self, channel: socket.socket, count: int, deadline: float) -> bytes:
        result = bytearray()
        while len(result) < count:
            channel.settimeout(remaining(deadline, self.clock))
            part = channel.recv(count - len(result))
            if not part:
                raise ProbeRejected("dns_truncated")
            result.extend(part)
        return bytes(result)

    def dns(
        self, host: str, transport: Literal["udp", "tcp"], deadline: float
    ) -> DNSResult:
        if transport not in {"udp", "tcp"}:
            raise ProbeRejected("transport_unknown")
        transaction = int.from_bytes(os.urandom(2), "big")
        query = question(host, transaction)
        kind = socket.SOCK_DGRAM if transport == "udp" else socket.SOCK_STREAM
        with self._socket(kind) as channel:
            channel.settimeout(remaining(deadline, self.clock))
            if transport == "udp":
                if channel.sendto(query, (RESOLVER, 53)) != len(query):
                    raise ProbeRejected("dns_send_unknown")
                channel.settimeout(remaining(deadline, self.clock))
                raw, peer = channel.recvfrom(MAX_DNS + 1)
                if peer != (RESOLVER, 53):
                    raise ProbeRejected("dns_peer_unknown")
            else:
                channel.connect((RESOLVER, 53))
                channel.settimeout(remaining(deadline, self.clock))
                channel.sendall(struct.pack("!H", len(query)) + query)
                length = struct.unpack("!H", self._read(channel, 2, deadline))[0]
                if not 12 <= length <= MAX_DNS:
                    raise ProbeRejected("dns_shape_unknown")
                raw = self._read(channel, length, deadline)
            received = self.clock()
            remaining(deadline, self.clock)
            result = parse_answer(raw, host, transaction, received)
        return result

    def _context(self) -> ssl.SSLContext:
        descriptor = os.open(CA_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            before = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_mode & 0o022
            ):
                raise ProbeRejected("ca_unknown")
            raw = source.read(2 * 1024 * 1024 + 1)
            after = os.fstat(source.fileno())
        if (
            len(raw) > 2 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != self.ca_sha256
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or b"PRIVATE KEY" in raw
        ):
            raise ProbeRejected("ca_changed")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cadata=raw.decode("ascii"))
        return context

    def tls(self, host: str, address: str, deadline: float) -> str:
        hostname(host)
        address = pool_address(address)
        context = self._context()
        channel: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            channel.settimeout(remaining(deadline, self.clock))
            channel.connect((address, 443))
            channel = context.wrap_socket(
                channel, server_hostname=host, do_handshake_on_connect=False
            )
            channel.settimeout(remaining(deadline, self.clock))
            channel.do_handshake()
            remaining(deadline, self.clock)
            version = channel.version()
            if version not in {"TLSv1.2", "TLSv1.3"}:
                raise ProbeRejected("tls_version_unknown")
            return version
        finally:
            self._close(channel)


def run_probe(
    operations: Operations,
    *,
    clock: Clock = time.monotonic,
    deadline: float | None = None,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    result: dict[str, object] = {
        "scope": "ordinary_user_predeployment_metadata_only",
        "result": "unknown",
        "OS_ACL_assessed": False,
        "ipv6": "not_assessed",
        "exit_identity_claim": False,
        "counts_semantics": "entered_bounded_operation_not_wire_count",
        "dns_operations_entered": 0,
        "tls_operations_entered": 0,
        "http_requests": 0,
        "auth_cli": 0,
        "model_prompts": 0,
        "steps": rows,
    }
    wall = min(clock() + 45, deadline) if deadline is not None else clock() + 45
    sequence = 0
    dns_count = tls_count = 0
    try:
        for role, host in zip(("api", "auth"), HOSTS, strict=True):
            answers = []
            for transport in ("udp", "tcp"):
                sequence += 1
                row: dict[str, object] = {
                    "sequence": sequence,
                    "role": role,
                    "category": "dns_A",
                    "transport": transport,
                    "outcome": "unknown",
                }
                rows.append(row)
                remaining(wall, clock)
                dns_count += 1
                result["dns_operations_entered"] = dns_count
                operation_deadline = min(wall, clock() + 5)
                answer = operations.dns(host, transport, operation_deadline)
                remaining(operation_deadline, clock)
                pool_address(answer.address)
                if (
                    type(answer.ttl) is not int
                    or answer.ttl <= 0
                    or not math.isfinite(answer.received)
                    or answer.received > clock()
                ):
                    raise ProbeRejected("dns_ttl_unknown")
                remaining(wall, clock)
                answers.append(answer)
                row.update(
                    {
                        "outcome": "observed",
                        "address": answer.address,
                        "ttl": answer.ttl,
                        "received_monotonic": answer.received,
                    }
                )
            if answers[0].address != answers[1].address:
                raise ProbeRejected("dns_disagreement")
            expiry = min(answer.expires for answer in answers)
            sequence += 1
            row = {
                "sequence": sequence,
                "role": role,
                "category": "tls_handshake",
                "outcome": "unknown",
            }
            rows.append(row)
            remaining(expiry, clock)
            remaining(wall, clock)
            tls_count += 1
            result["tls_operations_entered"] = tls_count
            operation_deadline = min(wall, expiry, clock() + 10)
            version = operations.tls(host, answers[0].address, operation_deadline)
            remaining(operation_deadline, clock)
            remaining(expiry, clock)
            remaining(wall, clock)
            if version not in {"TLSv1.2", "TLSv1.3"}:
                raise ProbeRejected("tls_version_unknown")
            row.update(
                {
                    "outcome": "observed",
                    "tls_version": version,
                    "chain_checked": True,
                    "hostname_checked": True,
                    "address": answers[0].address,
                    "dns_expiry_monotonic": expiry,
                }
            )
        if not operations.cleanup_complete:
            raise ProbeRejected("cleanup_unknown")
        result["result"] = "observed_expected"
    except (Exception, KeyboardInterrupt) as error:
        allowed = {
            "deadline_unknown",
            "hostname_unknown",
            "transaction_unknown",
            "address_unknown",
            "address_outside_pool",
            "dns_shape_unknown",
            "dns_question_unknown",
            "dns_answer_unknown",
            "dns_ttl_unknown",
            "dns_truncated",
            "dns_send_unknown",
            "dns_peer_unknown",
            "dns_disagreement",
            "transport_unknown",
            "ca_unknown",
            "ca_changed",
            "tls_version_unknown",
            "cleanup_unknown",
        }
        reason = (
            error.args[0]
            if isinstance(error, ProbeRejected) and len(error.args) == 1
            else None
        )
        result["failure_reason"] = (
            reason
            if isinstance(reason, str) and reason in allowed
            else "observation_unknown"
        )
    result["cleanup_complete"] = operations.cleanup_complete
    return result


def _write(
    directory: int,
    name: str,
    value: object,
    *,
    deadline: float | None = None,
    clock: Clock = time.monotonic,
) -> None:
    if deadline is not None:
        remaining(deadline, clock)
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory,
    )
    with os.fdopen(descriptor, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(value, output, sort_keys=True, separators=(",", ":"))
        output.write("\n")
        output.flush()
        if deadline is not None:
            remaining(deadline, clock)
        os.fsync(output.fileno())
        if deadline is not None:
            remaining(deadline, clock)
    os.fsync(directory)
    if deadline is not None:
        remaining(deadline, clock)


def execute(
    plan_path: Path,
    expected_sha: str,
    state_dir: Path,
    *,
    owner_config_confirmed: bool,
    clock: Clock = time.monotonic,
) -> dict[str, object]:
    started = clock()
    deadline = started + 45
    if os.getuid() == 0 or os.geteuid() == 0:
        raise ProbeRejected("ordinary_user_required")
    if owner_config_confirmed is not True:
        raise ProbeRejected("external_owner_confirmation_required")
    plan = load_plan(plan_path, expected_sha)
    remaining(deadline, clock)
    directory = os.open(state_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ProbeRejected("state_directory_unknown")
        try:
            os.stat("result.json", dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ProbeRejected("case_already_consumed")
        _write(
            directory,
            "execution-started.json",
            {
                "scope": "ordinary_user_predeployment_metadata_only",
                "state": "reserved_unknown",
                "plan_sha256": expected_sha,
            },
            deadline=deadline,
            clock=clock,
        )
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
            raise ProbeRejected("core_limit_unknown")
        probe = cast(dict[str, object], plan["candidate_probe"])
        trust = cast(dict[str, object], probe["tls_trust"])
        result = run_probe(
            SocketOperations(cast(str, trust["sha256"]), clock=clock),
            clock=clock,
            deadline=deadline,
        )
        if result["result"] == "observed_expected":
            remaining(deadline, clock)
        finalization_deadline = min(clock() + 10, started + 55)
        result.update(
            {
                "plan_sha256": expected_sha,
                "owner_configuration_confirmation_source": (
                    "caller_statement_external_authorization_required"
                ),
                "router_configuration_independently_verified": False,
                "completion_requires_successful_process_exit": True,
            }
        )
        _write(
            directory,
            "result.json",
            result,
            deadline=finalization_deadline,
            clock=clock,
        )
        remaining(finalization_deadline, clock)
        return result
    finally:
        os.close(directory)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="仅显式授权后执行普通用户DNS/TLS元数据探针;不部署规则、不认证或请求模型"
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--expected-plan-sha")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument(
        "--owner-config-confirmed",
        action="store_true",
        help="仅转录外部授权时所有者配置确认;flag不能自证权限",
    )
    args = parser.parse_args(argv)
    if (
        not args.execute
        or not args.plan
        or not args.expected_plan_sha
        or not args.state_dir
    ):
        parser.error("需要--execute、计划/SHA与独立0700状态目录;默认不执行")
    try:
        result = execute(
            args.plan,
            args.expected_plan_sha,
            args.state_dir,
            owner_config_confirmed=args.owner_config_confirmed,
        )
    except (Exception, KeyboardInterrupt):
        result = {
            "scope": "ordinary_user_predeployment_metadata_only",
            "result": "unknown",
            "failure_reason": "execution_incomplete",
            "no_retry": True,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "observed_expected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
