"""Independent D1: fixed-Node diagnostic metadata, never executes Node/network."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from scripts import issue167_node_diag_case as contract
from scripts import issue167_node_diag_worker as worker


def node_row(mode: str = "lookup_tls") -> dict[str, object]:
    return {
        "category": mode,
        "result": "observed_expected",
        "uid": 1000,
        "core_zero": True,
        "no_new_privs": True,
        "cap_eff_zero": True,
        "cgroup_matches": True,
        "lock_inherited": True,
        "cleanup_complete": True,
        "lookup_calls": 1 if mode == "lookup_tls" else 0,
        "tls_calls": 1 if mode == "lookup_tls" else 0,
        "address": "28.0.5.94" if mode == "lookup_tls" else None,
        "tls_version": "TLSv1.3" if mode == "lookup_tls" else None,
    }


def test_node_metadata_is_closed_and_never_contains_external_text() -> None:
    row = node_row()
    assert (
        contract.validate_node(row, mode="lookup_tls", uid=1000, address="28.0.5.94")
        == row
    )
    row["stderr"] = "synthetic-secret-error"
    with pytest.raises(contract.CaseRejected, match="node_metadata_unknown"):
        contract.validate_node(row, mode="lookup_tls", uid=1000, address="28.0.5.94")


@pytest.mark.parametrize(
    "field,value",
    [
        ("uid", True),
        ("core_zero", False),
        ("no_new_privs", False),
        ("lock_inherited", False),
        ("cleanup_complete", False),
        ("lookup_calls", True),
        ("lookup_calls", 2),
        ("address", "28.0.5.95"),
        ("tls_version", "TLSv1.1"),
        ("cgroup_matches", False),
    ],
)
def test_node_partial_wrong_identity_or_extra_calls_blocks(
    field: str, value: object
) -> None:
    row = node_row()
    row[field] = value
    with pytest.raises(contract.CaseRejected, match="node_metadata_unknown"):
        contract.validate_node(row, mode="lookup_tls", uid=1000, address="28.0.5.94")


@pytest.mark.parametrize("raw", [b"", b"{", b"{}\n{}\n", b"x" * 16385])
def test_bounded_node_output_refuses_partial_multiple_or_excess(raw: bytes) -> None:
    with pytest.raises(contract.CaseRejected, match="node_output_unknown"):
        worker.parse_output(raw)


def test_valid_node_output_keeps_json_only() -> None:
    row = node_row()
    assert worker.parse_output(json.dumps(row).encode() + b"\n") == row


@pytest.mark.parametrize(
    "start,end,expiry",
    [(True, 0.2, 1), (0.1, True, 1), (0.1, 1, 1), (0.2, 0.1, 1), (0.1, 0.2, True)],
)
def test_invalid_or_expired_parent_window_is_unknown(
    start: object, end: object, expiry: object
) -> None:
    with pytest.raises(contract.CaseRejected, match="node_ttl_unknown"):
        contract.validate_window(start, end, expiry, [0.0, 0.05])


def test_case_has_unknown_dns_wire_count_and_no_fake_zero_node() -> None:
    c = contract.Case("b62d4a90e713", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    value = c.to_dict()
    limits = value["network_limits"]
    assert isinstance(limits, dict)
    assert limits["os_dns_queries"] == "unknown"
    assert limits["node_execs"] == 4
    assert "node_pi" not in value and "network_operations" not in value
    assert contract.Case.from_dict(copy.deepcopy(value)).to_dict() == value


class Output:
    def __init__(self) -> None:
        self.closed = False

    def fileno(self) -> int:
        return 10

    def close(self) -> None:
        self.closed = True


class Process:
    def __init__(self, code: int = 0) -> None:
        self.stdout = Output()
        self.returncode: int | None = None
        self.code = code
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float) -> int:
        self.returncode = self.code
        return self.code

    def kill(self) -> None:
        self.killed = True


class Selector:
    def __enter__(self) -> "Selector":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def register(self, *_args: object) -> None:
        pass

    def select(self, _timeout: float) -> list[object]:
        return [object()]


@pytest.mark.parametrize(
    "code,raw,reason",
    [
        (2, b"{}\n", "node_exit_unknown"),
        (0, b"", "node_output_unknown"),
        (0, b"x" * 16385, "node_output_unknown"),
    ],
)
def test_subprocess_failure_never_returns_success_or_raw_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    code: int,
    raw: bytes,
    reason: str,
) -> None:
    child = Process(code)
    captured = {}

    def popen(*args: object, **kwargs: object) -> Process:
        captured.update(kwargs)
        return child

    chunks = iter([raw, b""])
    monkeypatch.setattr("scripts.issue167_node_diag_worker.subprocess.Popen", popen)
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.selectors.DefaultSelector", Selector
    )
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.os.set_blocking", lambda *_: None
    )
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.os.read", lambda *_: next(chunks)
    )
    with pytest.raises(contract.CaseRejected, match=reason):
        worker.run_child(
            ["never-executed-node"],
            cwd=tmp_path,
            pass_fds=(3,),
            preexec=lambda: None,
            deadline=5,
            clock=lambda: 0,
        )
    assert child.stdout.closed
    assert captured["env"] == {} and captured["stderr"] == subprocess.DEVNULL
    assert captured["pass_fds"] == (3,)


def test_timeout_kills_and_reaps_only_new_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    child = Process()

    class EmptySelector(Selector):
        def select(self, _timeout: float) -> list[object]:
            return []

    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.subprocess.Popen",
        lambda *_args, **_kwargs: child,
    )
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.selectors.DefaultSelector", EmptySelector
    )
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.os.set_blocking", lambda *_: None
    )
    with pytest.raises(contract.CaseRejected, match="node_timeout_unknown"):
        worker.run_child(
            ["never-executed-node"],
            cwd=tmp_path,
            pass_fds=(3,),
            preexec=lambda: None,
            deadline=5,
            clock=lambda: 0,
        )
    assert child.killed and child.returncode == 0 and child.stdout.closed


class Stages:
    def __init__(self, fail: int | None = None) -> None:
        self.fail = fail
        self.events: list[str] = []
        self.ledgers: list[dict[str, object]] = []

    def preflight(self) -> None:
        self.events.append("preflight")

    def reserve(self) -> None:
        self.events.append("reserve")

    def install(self) -> None:
        self.events.append("install")

    def start(self) -> None:
        self.events.append("start")

    def ready(self) -> dict[str, object]:
        return {}

    def exercise_rules(self) -> dict[str, object]:
        return {}

    def gate(self, sequence: int) -> None:
        self.events.append(f"gate{sequence}")

    def stage_result(self, sequence: int) -> dict[str, object]:
        self.events.append(f"stage{sequence}")
        if sequence == self.fail:
            raise ValueError("synthetic_internal_text")
        return {}

    def collect(self) -> dict[str, object]:
        return {}

    def wait_exit(self) -> None:
        self.events.append("exit")

    def restore(self) -> dict[str, object]:
        self.events.append("restore")
        return {
            "result": "host_policy_restored",
            "global_resolver_unchanged": True,
            "ledger_retained": True,
            "table_absent": True,
            "unit_absent": True,
        }

    def finish(self) -> dict[str, object]:
        self.events.append("finish")
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        assert isinstance(value, dict)
        self.ledgers.append(copy.deepcopy(value))


@pytest.mark.parametrize("failed", [1, 2, 3, 4])
def test_any_node_stage_failure_blocks_later_nodes_and_keeps_unknown(
    failed: int,
) -> None:
    from scripts import issue167_node_diag_owner as owner

    c = contract.Case("b62d4a90e713", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    ops = Stages(failed)
    result = owner.run_owner(c, ops)
    assert (
        result["result"] == "unknown"
        and result["failure_stage"] == f"node_stage_{failed}"
    )
    assert f"gate{failed + 1}" not in ops.events
    assert "restore" in ops.events and "finish" not in ops.events
    assert ops.ledgers[-1]["result"] == "unknown"
    assert "synthetic_internal_text" not in json.dumps(result)


def stage_row(sequence: int) -> dict[str, object]:
    row = {
        "run_id": "b62d4a90e713",
        "sequence": sequence,
        "node": node_row("tcp53_control" if sequence == 1 else "tcp53_landlock"),
        "child_reaped": True,
        "supply_protection": (
            "diagnostic_readonly_original_instance_lock_not_product_use_install"
        ),
    }
    return row


@pytest.mark.parametrize("sequence,after", [(1, (10, 0)), (2, (11, 0)), (2, (10, 1))])
def test_actual_owner_requires_positive_delta_and_no_landlock_packet(
    sequence: int,
    after: tuple[int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import issue167_node_diag_owner as owner

    ops = owner.LiveOperations.__new__(owner.LiveOperations)
    ops.case = contract.Case("b62d4a90e713", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    ops.previous_counts = (10, 0)
    monkeypatch.setattr(ops, "_wait", lambda _name: stage_row(sequence))
    monkeypatch.setattr(ops, "_verify", lambda _stage=None: after)
    with pytest.raises(ValueError, match="node_packet_evidence_unknown"):
        ops.stage_result(sequence)


def test_static_javascript_has_no_application_or_secret_channel() -> None:
    assert "dns.lookup(host," in worker.JS
    assert "rejectUnauthorized:true" in worker.JS
    assert "minVersion:'TLSv1.2'" in worker.JS
    assert "process.env" not in worker.JS and "http." not in worker.JS
    assert "process.argv.slice(1)" in worker.JS
    assert "family:" not in worker.JS and "ca:" not in worker.JS


def test_nss_drift_after_child_exit_cannot_publish_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    class LocalCase(contract.Case):
        @property
        def worker_root(self) -> Path:
            return tmp_path

    case = LocalCase("b62d4a90e713", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    checks = []

    def check(_root: Path) -> None:
        checks.append("checked")
        if len(checks) > 1:
            raise contract.CaseRejected("nss_context_unknown")

    monkeypatch.setattr(contract, "check_nss", check)
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.local.load_isolation",
        lambda _root: SimpleNamespace(IsolationBoundary=lambda *_args: None),
    )
    monkeypatch.setattr(
        worker, "run_child", lambda *_args, **_kwargs: node_row("tcp53_control")
    )
    lock = tmp_path / "synthetic.lock"
    lock.write_bytes(b"")
    with lock.open("rb") as descriptor:
        handle = SimpleNamespace(
            node=Path("/never-run-node"),
            install=tmp_path,
            pass_fds=(descriptor.fileno(),),
        )
        with pytest.raises(contract.CaseRejected, match="nss_context_unknown"):
            worker.run_stage(case, tmp_path, handle, 1, 10**10)
    assert checks == ["checked", "checked"]


def test_parent_deadline_enforces_tcp_item_in_addition_to_javascript_timer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    class LocalCase(contract.Case):
        @property
        def worker_root(self) -> Path:
            return tmp_path

    case = LocalCase("b62d4a90e713", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    monkeypatch.setattr(contract, "check_nss", lambda _root: None)
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.local.load_isolation",
        lambda _root: SimpleNamespace(IsolationBoundary=lambda *_args: None),
    )
    captured = []

    def child(*_args: object, **kwargs: object) -> dict[str, object]:
        captured.append(kwargs["deadline"])
        return node_row("tcp53_control")

    monkeypatch.setattr(worker, "run_child", child)
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.time.monotonic", lambda: 100.0
    )
    lock = tmp_path / "synthetic.lock"
    lock.write_bytes(b"")
    with lock.open("rb") as descriptor:
        handle = SimpleNamespace(
            node=Path("/never-run-node"),
            install=tmp_path,
            pass_fds=(descriptor.fileno(),),
        )
        worker.run_stage(case, tmp_path, handle, 1, 1000.0)
    assert captured == [105.0]


def test_late_successful_exit_is_still_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    clock = [0.0]
    child = Process()

    def waited(timeout: float) -> int:
        clock[0] = 6.0
        child.returncode = 0
        return 0

    monkeypatch.setattr(child, "wait", waited)
    chunks = iter([json.dumps(node_row("tcp53_control")).encode(), b""])
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.subprocess.Popen", lambda *_a, **_k: child
    )
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.selectors.DefaultSelector", Selector
    )
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.os.set_blocking", lambda *_a: None
    )
    monkeypatch.setattr(
        "scripts.issue167_node_diag_worker.os.read", lambda *_a: next(chunks)
    )
    with pytest.raises(ValueError, match="deadline_unknown"):
        worker.run_child(
            ["never-executed-node"],
            cwd=tmp_path,
            pass_fds=(3,),
            preexec=lambda: None,
            deadline=5.0,
            clock=lambda: clock[0],
        )
