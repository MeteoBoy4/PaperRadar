"""Fixed no-network Python peer for the H1 resolver/window case.

The marker is public synthetic data. No token, argv, environment, observed file
content, or external exception is emitted by the model role.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import stat
import sys
from pathlib import Path

MARKER = "issue167-public-nonsecret-resolver-fixture"


def metadata(fd: int, cgroup: str, resolver_sha: str) -> dict[str, bool]:
    info = os.fstat(fd)
    with Path("/proc/self/status").open("rb") as source:
        raw = source.read(16385)
    if len(raw) > 16384:
        raise ValueError("self_metadata_unknown")
    selected = {}
    for line in raw.decode("ascii").splitlines():
        key, _, value = line.partition(":")
        if key == "NoNewPrivs":
            selected[key] = value.strip()
    with Path("/etc/resolv.conf").open("rb") as source:
        resolver = source.read(4097)
    with Path("/proc/self/cgroup").open("rb") as source:
        own_cgroup = source.read(16385)
    return {
        "fd_inherited": stat.S_ISREG(info.st_mode),
        "core_zero": resource.getrlimit(resource.RLIMIT_CORE) == (0, 0),
        "cgroup_matches": own_cgroup == f"0::{cgroup}\n".encode(),
        "resolver_matches": len(resolver) <= 4096
        and hashlib.sha256(resolver).hexdigest() == resolver_sha,
        "no_new_privs": selected.get("NoNewPrivs") == "1",
        "separate_session": os.getsid(0) != os.getsid(os.getppid()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="固定无网络合成Python子进程")
    parser.add_argument("--role", choices=("auth", "model"), required=True)
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--resolver-sha", required=True)
    parser.add_argument("--tree", type=Path)
    args = parser.parse_args()
    try:
        value = metadata(args.fd, args.cgroup, args.resolver_sha)
        if args.role == "auth":
            # Only the parent's anonymous pipe receives this public fixture.
            print(json.dumps({"marker": MARKER, "metadata": value}), flush=True)
            return 0
        if args.tree is None or os.lseek(args.fd, 0, os.SEEK_CUR) != 17:
            raise ValueError("model_setup_unknown")
        os.lseek(args.fd, 23, os.SEEK_SET)
        value["marker_received"] = os.environ.get("OPENAI_API_KEY") == MARKER
        print(json.dumps({"stage": "ready", "metadata": value}), flush=True)
        if sys.stdin.buffer.readline(4) != b"GO\n":
            raise ValueError("model_gate_unknown")
        transient = args.tree / "agent" / "transient"
        with transient.open("xb") as output:
            output.write(b"fixed-nonsecret-file")
        transient.unlink()
        print(json.dumps({"stage": "done", "mutation_complete": True}), flush=True)
        return 0
    except (Exception, KeyboardInterrupt):
        # Do not print the error, marker, input, paths, or environment.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
