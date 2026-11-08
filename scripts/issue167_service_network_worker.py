"""Bounded socket worker; imports and ordinary tests do not execute network."""

from __future__ import annotations

import errno
import os
import socket
import stat
import time
from pathlib import Path
from typing import cast

from scripts import issue167_dns_tls as probe
from scripts import issue167_resolver_worker as local
from scripts import issue167_service_network_case as contract


class TimedOperations(probe.SocketOperations):
    def __init__(self, sha: str, *, clock: probe.Clock = time.monotonic) -> None:
        super().__init__(sha, clock=clock)
        self.timings: list[tuple[float, float]] = []

    def tls(self, host: str, address: str, deadline: float) -> str:
        started = self.clock()
        version = super().tls(host, address, deadline)
        completed = self.clock()
        self.timings.append((started, completed))
        return version


def run_positive(
    operations: TimedOperations, *, deadline: float, clock: probe.Clock = time.monotonic
) -> dict[str, object]:
    result = probe.run_probe(operations, clock=clock, deadline=deadline)
    timings = iter(operations.timings)
    for row in cast(list[dict[str, object]], result["steps"]):
        if row["category"] == "tls_handshake" and row["outcome"] == "observed":
            try:
                started, completed = next(timings)
            except StopIteration:
                result.update(result="unknown", failure_reason="tls_timing_unknown")
                return result
            row.update(started_monotonic=started, completed_monotonic=completed)
    try:
        next(timings)
    except StopIteration:
        pass
    else:
        result.update(result="unknown", failure_reason="tls_timing_unknown")
    if result["result"] == "observed_expected":
        contract.validate_probe(result)
    return result


def denied_attempt(
    run_id: str, sequence: int, *, deadline: float, clock: probe.Clock = time.monotonic
) -> dict[str, object]:
    if type(sequence) is not int or sequence not in {1, 2}:
        raise local.WorkerRejected("deny_sequence_unknown")
    row: dict[str, object] = {
        "run_id": run_id,
        "sequence": sequence,
        "category": "deny_tcp_connect" if sequence == 1 else "deny_udp_A",
        "attempts": 1,
        "result": "unknown",
        "cleanup_complete": False,
    }
    channel = None
    try:
        channel = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM if sequence == 1 else socket.SOCK_DGRAM
        )
        channel.settimeout(probe.remaining(deadline, clock))
        if sequence == 1:
            channel.connect((probe.RESOLVER, 53))
        else:
            question = probe.question(
                probe.HOSTS[0], int.from_bytes(os.urandom(2), "big")
            )
            if channel.sendto(question, (probe.RESOLVER, 53)) != len(question):
                raise local.WorkerRejected("deny_send_unknown")
            channel.settimeout(probe.remaining(deadline, clock))
            channel.recvfrom(probe.MAX_DNS + 1)
        row["result"] = "unexpected_response_or_connect"
    except OSError as error:
        if isinstance(error, TimeoutError) or error.errno in {
            errno.EACCES,
            errno.EPERM,
            errno.ECONNREFUSED,
            errno.EHOSTUNREACH,
            errno.ENETUNREACH,
            errno.ETIMEDOUT,
        }:
            row["result"] = "denied_or_timeout"
    finally:
        if channel is not None:
            try:
                started = clock()
                channel.close()
                row["cleanup_complete"] = clock() - started < 10
            except OSError:
                row["cleanup_complete"] = False
        if row["cleanup_complete"] is not True:
            row["result"] = "unknown"
    return row


def execute(root: Path) -> dict[str, object]:
    case, _, _ = contract.verify_installation(root)
    info = case.worker_root.lstat()
    if (
        os.getuid() != case.uid
        or os.geteuid() != case.uid
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != case.uid
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise local.WorkerRejected("worker_directory_unknown")
    local.reserve(case.worker_root / "worker-started.json", case.run_id)
    deadline = time.monotonic() + case.worker_timeout_s
    result: dict[str, object] = {
        "run_id": case.run_id,
        "result": "unknown",
        "scope": "service_network_metadata",
        "node_pi": False,
        "auth_calls": 0,
        "model_calls": 0,
    }
    try:
        ready = local.own_metadata(case)
        local.publish(case.worker_root / "ready.json", ready)
        denials = []
        for sequence in (1, 2):
            local.wait_gate(
                case.runtime_root / f"gate-{sequence}.json",
                case.run_id,
                sequence,
                deadline,
            )
            row = denied_attempt(
                case.run_id, sequence, deadline=min(deadline, time.monotonic() + 5)
            )
            local.publish(case.worker_root / f"deny-{sequence}.json", row)
            contract.validate_deny(case.run_id, sequence, row)
            denials.append(row)
        local.wait_gate(case.runtime_root / "gate-3.json", case.run_id, 3, deadline)
        profile = contract.read_metadata(root / "profile.json", owner=0)
        assert isinstance(profile, dict)
        operations = TimedOperations(profile["candidate_probe"]["tls_trust"]["sha256"])
        positive = run_positive(operations, deadline=deadline)
        contract.validate_probe(positive)
        result = {
            **ready,
            **result,
            "result": "observed_expected",
            "denials": denials,
            "probe": positive,
        }
        contract.validate_result(case, result)
    except (Exception, KeyboardInterrupt):
        result.update(
            result="unknown", failure_reason="worker_network_observation_unknown"
        )
    local.publish(case.worker_root / "worker-result.json", result)
    if result["result"] == "observed_expected":
        local.wait_gate(case.runtime_root / "gate-4.json", case.run_id, 4, deadline)
    return result


def main() -> int:
    result = execute(Path(__file__).absolute().parent)
    return 0 if result["result"] == "observed_expected" else 1
