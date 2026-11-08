"""显式授权入口:两例无秘密native崩溃,仅目录成员/事件元数据,不读core。"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import resource
import selectors
import signal
import struct
import subprocess
import time
from pathlib import Path

DIRECTORIES = (Path("/var/crash"), Path("/var/lib/apport/coredump"))
NONZERO_LIMIT = 64 * 1024 * 1024
_HEADER = struct.Struct("iIII")


def unpack_events(payload: bytes) -> tuple[list[tuple[int, str]], bool]:
    events: list[tuple[int, str]] = []
    complete = True
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < _HEADER.size:
            return events, False
        _, mask, _, size = _HEADER.unpack_from(payload, offset)
        offset += _HEADER.size
        if offset + size > len(payload):
            return events, False
        name = os.fsdecode(payload[offset : offset + size].split(b"\0", 1)[0])
        offset += size
        if mask & (0x4000 | 0x8000 | 0x2000 | 0x800 | 0x400):
            complete = False
        if name and mask & (0x100 | 0x80):
            events.append((mask, name))
    return events, complete


class MembershipWatch:
    def __init__(self, root: Path) -> None:
        libc = ctypes.CDLL(None, use_errno=True)
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise ValueError("watch_unavailable")
        if (
            libc.inotify_add_watch(
                self.fd, os.fsencode(root), 0x100 | 0x80 | 0x400 | 0x800
            )
            < 0
        ):
            os.close(self.fd)
            raise ValueError("watch_unavailable")
        self.events: list[tuple[int, str]] = []
        self.complete = True

    def drain(self) -> None:
        while True:
            try:
                payload = os.read(self.fd, 65536)
            except BlockingIOError:
                return
            if not payload:
                self.complete = False
                return
            events, complete = unpack_events(payload)
            self.events.extend(events)
            self.complete &= complete

    def close(self) -> None:
        os.close(self.fd)


def candidate_name(name: str, executable: Path, pid: int, uid: int) -> bool:
    encoded = str(executable).replace("/", "_").replace(".", "_")
    parts = name.split(".")
    return (
        len(parts) == 6
        and parts[0] == "core"
        and parts[1] == encoded
        and parts[2] == str(uid)
        and parts[4] == str(pid)
    )


def run_case(executable: Path, limit: int) -> dict[str, object]:
    before = {root: set(os.listdir(root)) for root in DIRECTORIES}
    if (
        sum(
            1
            for name in before[DIRECTORIES[1]]
            if len(name.split(".")) > 2 and name.split(".")[2] == str(os.getuid())
        )
        >= 5
    ):
        raise ValueError("old_core_cleanup_risk")
    watches = {root: MembershipWatch(root) for root in DIRECTORIES}

    def limits() -> None:
        resource.setrlimit(resource.RLIMIT_CORE, (limit, limit))
        resource.setrlimit(resource.RLIMIT_AS, (32 * 1024 * 1024, 32 * 1024 * 1024))

    try:
        with subprocess.Popen(
            [str(executable)],
            cwd=executable.parent,
            env={},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            preexec_fn=limits,
            start_new_session=True,
        ) as child:
            assert child.stdout is not None and child.stdin is not None
            with selectors.DefaultSelector() as ready:
                ready.register(child.stdout, selectors.EVENT_READ)
                if not ready.select(5):
                    child.kill()
                    raise ValueError("sample_not_ready")
                frame = os.read(child.stdout.fileno(), 256)
            try:
                pid, uid, soft, hard = map(int, frame.split())
            except ValueError:
                child.kill()
                raise ValueError("sample_metadata_invalid") from None
            if (pid, uid, soft, hard) != (child.pid, os.getuid(), limit, limit):
                child.kill()
                raise ValueError("sample_binding_mismatch")
            child.stdin.write(b"x")
            child.stdin.flush()
            child.stdin.close()
            try:
                exit_code = child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                child.kill()
                raise ValueError("sample_exit_timeout") from None
            # Collector exit is not inferred solely from child.wait().
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                for watch in watches.values():
                    watch.drain()
                time.sleep(0.1)
        after = {root: set(os.listdir(root)) for root in DIRECTORIES}
        for watch in watches.values():
            watch.drain()
        added = {root: after[root] - before[root] for root in DIRECTORIES}
        raw = added[DIRECTORIES[1]]
        attributed = sorted(
            name for name in raw if candidate_name(name, executable, pid, uid)
        )
        event_counts = {str(root): len(watch.events) for root, watch in watches.items()}
        unknown = (
            exit_code != -signal.SIGSEGV
            or not all(w.complete for w in watches.values())
            or any(before[root] - after[root] for root in DIRECTORIES)
            or bool(added[DIRECTORIES[0]])
            or bool(event_counts[str(DIRECTORIES[0])])
            or len(raw) != len(attributed)
        )
        expected = not raw if limit == 0 else len(attributed) == 1
        # Zero must include no transient new member, not merely an empty end state.
        if limit == 0 and any(event_counts.values()):
            unknown = True
        return {
            "limit": limit,
            "hard_limit": hard,
            "uid": uid,
            "pid": pid,
            "exit_code": exit_code,
            "observation_seconds_after_wait": 8,
            "new_members": {str(root): len(added[root]) for root in DIRECTORIES},
            "new_member_events": event_counts,
            "raw_core_members": attributed,
            "observation_complete": all(w.complete for w in watches.values()),
            "result": "observed_expected" if expected and not unknown else "unknown",
        }
    finally:
        for watch in watches.values():
            watch.close()


def run(executable: Path, receipt: Path) -> dict[str, object]:
    executable = executable.resolve(strict=True)
    if (
        not executable.is_relative_to("/home")
        or not executable.is_file()
        or executable.stat().st_uid != os.getuid()
    ):
        raise ValueError("sample_not_owned_home_file")
    if receipt.exists():
        raise ValueError("receipt_exists_no_repeat")
    # Claim BEFORE either crash; failure never grants a retry.
    with receipt.open("x") as output:
        json.dump({"state": "reserved_no_auto_retry"}, output)
        output.flush()
        os.fsync(output.fileno())
    identity = hashlib.sha256(executable.read_bytes()).hexdigest()  # synthetic ELF only
    result: dict[str, object] = {
        "executable_sha256": identity,
        "cases": [],
        "result": "unknown",
    }
    cases = []
    try:
        for limit in (0, NONZERO_LIMIT):
            case = run_case(executable, limit)
            cases.append(case)
            if case["result"] != "observed_expected":
                break
        result["cases"] = cases
        if len(cases) == 2 and all(c["result"] == "observed_expected" for c in cases):
            result["result"] = "paired_observation"
    finally:
        result["cases"] = cases
        receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="仅在明确授权后执行两例无秘密native崩溃"
    )
    parser.add_argument("--run-authorized-pair", action="store_true", required=True)
    parser.add_argument("executable", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.executable, args.receipt), sort_keys=True))
