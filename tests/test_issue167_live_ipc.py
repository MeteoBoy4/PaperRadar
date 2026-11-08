"""独立D1:无秘密IPC矩阵的闭集、正负控制和失败清理;本模块仅mock。"""

import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from scripts import issue167_live_ipc as ipc


class Pair:
    def __init__(self, category: str, owner: "Operations") -> None:
        self.category = category
        self.owner = owner

    def probe(self, isolated: bool, deadline: float) -> dict[str, object]:
        self.owner.calls.append((self.category, isolated))
        if self.owner.throw == (self.category, isolated):
            raise ValueError("uncontrolled-synthetic-exception")
        value: dict[str, object] = {
            "result": "denied" if isolated else "allowed",
            "errno_category": "permission" if isolated else "none",
            "verified": True,
            "peer_reaped": True,
        }
        value.update(self.owner.changed.get((self.category, isolated), {}))
        return value

    def close(self, deadline: float) -> bool:
        self.owner.closed.append(self.category)
        return self.category != self.owner.bad_close


class Operations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []
        self.closed: list[str] = []
        self.changed: dict[tuple[str, bool], dict[str, object]] = {}
        self.throw: tuple[str, bool] | None = None
        self.bad_close: str | None = None

    def open(self, category: str, deadline: float) -> Pair:
        return Pair(category, self)


def run(ops: Operations) -> dict[str, Any]:
    return ipc.run_ipc_preflight(
        Path("/tmp/synthetic-ipc-unused"), 100, operations=ops, clock=lambda: 1
    )


def test_all_categories_require_control_then_denial_and_cleanup() -> None:
    ops = Operations()
    receipt = run(ops)
    assert receipt["result"] == "observed_expected"
    assert receipt["integrity"] == "complete"
    assert receipt["pair_entries"] == 7
    assert receipt["peer_operations_entered"] == 14
    assert ops.calls == [
        (category, isolated)
        for category in ipc.CATEGORIES
        for isolated in (False, True)
    ]
    assert ops.closed == list(ipc.CATEGORIES)
    assert all(row["cleanup_complete"] is True for row in receipt["steps"])
    assert set(receipt) == ipc.RECEIPT_FIELDS


@pytest.mark.parametrize("result", ["denied", "unknown"])
def test_positive_control_failure_never_runs_landlock_peer(result: str) -> None:
    ops = Operations()
    ops.changed[(ipc.CATEGORIES[0], False)] = {"result": result}
    receipt = run(ops)
    assert receipt["result"] == "unknown"
    assert receipt["failure_reason"] == "positive_control_unknown"
    assert ops.calls == [(ipc.CATEGORIES[0], False)]
    assert ops.closed == [ipc.CATEGORIES[0]]


def test_unsupported_control_is_unknown_with_a_closed_reason() -> None:
    ops = Operations()
    ops.changed[(ipc.CATEGORIES[0], False)] = {
        "result": "unknown",
        "verified": False,
        "errno_category": "unsupported",
    }
    receipt = run(ops)
    assert receipt["failure_reason"] == "positive_control_unknown"
    assert receipt["steps"][0]["control_errno_category"] == "unsupported"
    assert ops.calls == [(ipc.CATEGORIES[0], False)]


@pytest.mark.parametrize("result", ["allowed", "unknown"])
def test_negative_must_be_observed_permission_denial(result: str) -> None:
    ops = Operations()
    ops.changed[(ipc.CATEGORIES[0], True)] = {"result": result}
    receipt = run(ops)
    assert receipt["result"] == "unknown"
    assert receipt["failure_reason"] == "isolation_denial_unknown"
    assert len(ops.calls) == 2
    assert ops.closed == [ipc.CATEGORIES[0]]


@pytest.mark.parametrize(
    "change",
    [
        {"raw": "forbidden"},
        {"peer_reaped": False},
        {"verified": False},
        {"verified": 1},
        {"errno_category": "raw-synthetic-error"},
    ],
)
def test_partial_or_uncontrolled_metadata_fails_closed(
    change: dict[str, object],
) -> None:
    ops = Operations()
    ops.changed[(ipc.CATEGORIES[0], False)] = change
    receipt = run(ops)
    assert receipt["result"] == "unknown"
    assert receipt["failure_reason"] == "peer_metadata_unknown"
    assert "forbidden" not in str(receipt)
    assert "raw-synthetic-error" not in str(receipt)
    assert ops.closed == [ipc.CATEGORIES[0]]


def test_exception_is_closed_and_target_is_still_cleaned() -> None:
    ops = Operations()
    ops.throw = (ipc.CATEGORIES[0], False)
    receipt = run(ops)
    assert receipt["failure_reason"] == "ipc_observation_unknown"
    assert "uncontrolled" not in str(receipt)
    assert ops.closed == [ipc.CATEGORIES[0]]


def test_target_cleanup_failure_blocks_all_later_pairs() -> None:
    ops = Operations()
    ops.bad_close = ipc.CATEGORIES[0]
    receipt = run(ops)
    assert receipt["failure_reason"] == "ipc_cleanup_unknown"
    assert receipt["steps"][0]["cleanup_complete"] is False
    assert len(ops.calls) == 2


def test_expired_parent_deadline_starts_no_process() -> None:
    ops = Operations()
    receipt = ipc.run_ipc_preflight(
        Path("/tmp/unused"), 1, operations=ops, clock=lambda: 2
    )
    assert receipt["failure_reason"] == "ipc_deadline_unknown"
    assert ops.calls == []


@pytest.mark.parametrize("raw", [b"", b"{", b"{}\n{}\n", b"x" * 4097])
def test_bounded_json_parser_rejects_partial_multiple_and_excess(raw: bytes) -> None:
    with pytest.raises(ipc.IpcRejected, match="ipc_metadata_unknown"):
        ipc.parse_json(raw)


def test_parser_rejects_duplicate_fields() -> None:
    with pytest.raises(ipc.IpcRejected, match="ipc_metadata_unknown"):
        ipc.parse_json(b'{"result":"allowed","result":"denied"}\n')


def test_probe_source_scope_does_not_include_external_targets_or_node() -> None:
    assert "socket" not in ipc.TARGET
    assert "getenv" not in ipc.TARGET + ipc.PEER
    assert "environ" not in ipc.TARGET + ipc.PEER
    assert "node" not in ipc.TARGET + ipc.PEER
    assert "os.kill(pid, signal.SIGUSR1)" in ipc.PEER


def test_embedded_target_and_peer_are_parseable_without_execution() -> None:
    compile(ipc.TARGET, "synthetic-target", "exec")
    compile(ipc.PEER, "synthetic-peer", "exec")


def test_peer_reader_checks_eof_instead_of_accepting_a_first_line() -> None:
    read, write = os.pipe()
    try:
        os.write(write, b'{"result":"allowed"}\n{"raw":"extra"}\n')
        os.close(write)
        write = -1
        with os.fdopen(read, "rb") as stream:
            child = cast(subprocess.Popen[bytes], SimpleNamespace(stdout=stream))
            with pytest.raises(ipc.IpcRejected, match="ipc_metadata_unknown"):
                ipc._peer_json(child, time.monotonic() + 1, time.monotonic)
    finally:
        if write >= 0:
            os.close(write)


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize(
    "category,broken_reply",
    [
        ("process_vm_writev", "reset"),
        ("process_vm_writev", "state"),
        ("signal", "signal_state"),
    ],
)
def test_kernel_target_numeric_flags_cannot_be_accepted_as_booleans(
    monkeypatch: pytest.MonkeyPatch,
    isolated: bool,
    category: str,
    broken_reply: str,
) -> None:
    def stream() -> SimpleNamespace:
        return SimpleNamespace(fileno=lambda: 123456, close=lambda: None)

    child = SimpleNamespace(
        stdin=stream(),
        stdout=stream(),
        returncode=0,
        poll=lambda: 0,
        wait=lambda timeout=None: 0,
    )
    pair = object.__new__(ipc.KernelPair)
    pair.category = category
    pair.clock = lambda: 1
    pair.target = cast(subprocess.Popen[bytes], SimpleNamespace(poll=lambda: None))
    pair.python = Path("/tmp/not-executed-python")
    pair.install = pair.cwd = pair.attempt = Path("/tmp/not-accessed")
    pair.factory = lambda *_: lambda: None
    pair.metadata = {"pid": 123456, "address": 123456, "length": 24, "fd": 4}

    def command(name: str, _deadline: float) -> dict[str, object]:
        values: dict[str, dict[str, object]] = {
            "reset": {"reset": True},
            "state": {
                "original": isolated,
                "written": not isolated,
                "signal_received": False,
            },
            "signal_state": {"signal_received": not isolated},
        }
        row = values[name]
        if name == broken_reply:
            return {key: int(cast(bool, value)) for key, value in row.items()}
        return row

    monkeypatch.setattr(pair, "_command", command)
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_kw: child)
    monkeypatch.setattr(os, "write", lambda _fd, raw: len(raw))
    monkeypatch.setattr(
        ipc,
        "_peer_json",
        lambda *_a: {
            "result": "denied" if isolated else "allowed",
            "errno_category": "permission" if isolated else "none",
            "verified": True,
        },
    )
    if broken_reply == "reset":
        with pytest.raises(ipc.IpcRejected, match="ipc_target_unknown"):
            pair.probe(isolated, 100)
    else:
        observation = ipc.validate_observation(pair.probe(isolated, 100))
        assert observation["result"] == "unknown"
        assert observation["verified"] is False
