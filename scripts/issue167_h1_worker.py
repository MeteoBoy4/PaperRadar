"""H1首轮无认证worker:仅同进程/合成后代元数据与socket创建拒绝。"""

from __future__ import annotations

import argparse
import errno
import json
import os
import resource
import socket
import subprocess
import sys
from contextlib import suppress
from pathlib import Path


def socket_denials() -> dict[str, str]:
    outcomes = {}
    for label, family, kind in (
        ("ipv4_tcp", socket.AF_INET, socket.SOCK_STREAM),
        ("ipv6_tcp", socket.AF_INET6, socket.SOCK_STREAM),
        ("unix", socket.AF_UNIX, socket.SOCK_STREAM),
        ("ipv4_udp", socket.AF_INET, socket.SOCK_DGRAM),
        ("ipv6_udp", socket.AF_INET6, socket.SOCK_DGRAM),
    ):
        try:
            with socket.socket(family, kind):
                outcomes[label] = "unexpected_allowed"
        except OSError as error:
            outcomes[label] = (
                "denied"
                if error.errno in {errno.EPERM, errno.EACCES, errno.EAFNOSUPPORT}
                else "unknown"
            )
    return outcomes


def collect(*, expected_uid: int | None = None) -> dict[str, object]:
    status = Path("/proc/self/status").read_text()
    no_new_privs = next(
        (
            line.split(":", 1)[1].strip()
            for line in status.splitlines()
            if line.startswith("NoNewPrivs:")
        ),
        None,
    )
    # 固定合成子进程,不读配置/凭据/env,不crash、不联网、不运行Pi。
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            (
                "import json,os,resource;"
                "print(json.dumps([os.getuid(),"
                "list(resource.getrlimit(resource.RLIMIT_CORE))]))"
            ),
        ],
        env={},
        capture_output=True,
        timeout=5,
        check=False,
    )
    child_observed = None
    if child.returncode == 0 and len(child.stdout) <= 256:
        with suppress(ValueError):
            child_observed = json.loads(child.stdout)
    denials = socket_denials()
    core = list(resource.getrlimit(resource.RLIMIT_CORE))
    passed = (
        expected_uid == os.getuid()
        and type(expected_uid) is int
        and core == [0, 0]
        and no_new_privs == "1"
        and child_observed == [os.getuid(), [0, 0]]
        and set(denials.values()) == {"denied"}
        and os.getcwd() == "/srv/pi-cwd"
    )
    return {
        "scope": "synthetic_service_preflight_only",
        "uid": os.getuid(),
        "core_limits": core,
        "no_new_privs": no_new_privs == "1",
        "child_metadata": child_observed,
        "socket_creation": denials,
        "cwd_matches": os.getcwd() == "/srv/pi-cwd",
        "result": "observed_expected" if passed else "unknown",
        "auth_calls": 0,
        "model_calls": 0,
    }


def run_once(receipt: Path, *, expected_uid: int | None = None) -> dict[str, object]:
    descriptor = os.open(receipt, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    result: dict[str, object] = {
        "scope": "synthetic_service_preflight_only",
        "result": "reserved_unknown",
        "auth_calls": 0,
        "model_calls": 0,
    }
    with os.fdopen(descriptor, "w+") as output:
        json.dump(result, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
        try:
            result = collect(expected_uid=expected_uid)
        finally:
            output.seek(0)
            output.truncate()
            json.dump(result, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="无认证H1服务元数据,不会运行Pi或联网")
    parser.add_argument("--expected-uid", type=int, required=True)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    result = run_once(args.receipt, expected_uid=args.expected_uid)
    raise SystemExit(0 if result["result"] == "observed_expected" else 1)
