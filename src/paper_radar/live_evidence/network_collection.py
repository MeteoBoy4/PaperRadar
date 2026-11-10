"""四个固定 IPv4 负对照;counter/来源归属由 root 判断。"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field

from paper_radar.live_evidence.receipt import WireModel
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.pi_execution.placement import PlacementTarget


class NetworkOutcome(WireModel):
    attempted: bool = Field(strict=True)
    response: bool = Field(strict=True)


def negative_rule_handle(snapshot: dict[str, Any], comment: str) -> int | None:
    matches = [
        item["rule"].get("handle")
        for item in snapshot.get("nftables", [])
        if "rule" in item
        and item["rule"].get("comment") == comment
        and item["rule"].get("family") == "inet"
        and item["rule"].get("table") == "paperradar"
    ]
    return (
        matches[0]
        if len(matches) == 1 and type(matches[0]) is int and matches[0] > 0
        else None
    )


def _counter(snapshot: dict[str, Any], handle: int) -> tuple[int, int] | None:
    matches = [
        item["rule"]
        for item in snapshot.get("nftables", [])
        if "rule" in item
        and item["rule"].get("handle") == handle
        and item["rule"].get("family") == "inet"
        and item["rule"].get("table") == "paperradar"
    ]
    if len(matches) != 1:
        return None
    expressions = matches[0].get("expr", [])
    if not any("drop" in value or "reject" in value for value in expressions):
        return None
    counters = [value["counter"] for value in expressions if "counter" in value]
    if len(counters) != 1 or any(
        type(counters[0].get(key)) is not int or counters[0][key] < 0
        for key in ("packets", "bytes")
    ):
        return None
    return counters[0]["packets"], counters[0]["bytes"]


def _other_counters(snapshot: dict[str, Any], handle: int) -> list[object]:
    return [
        expression["counter"]
        for item in snapshot.get("nftables", [])
        if "rule" in item and item["rule"].get("handle") != handle
        for expression in item["rule"].get("expr", [])
        if "counter" in expression
    ]


def verify_counter_change(
    before: dict[str, Any], after: dict[str, Any], *, handle: int, attributable: bool
) -> bool:
    from paper_radar.live_evidence.protected_observer import stable_nft_snapshot

    first, last = _counter(before, handle), _counter(after, handle)
    return bool(
        attributable
        and first is not None
        and last is not None
        and stable_nft_snapshot(before) == stable_nft_snapshot(after)
        and _other_counters(before, handle) == _other_counters(after, handle)
        and last[0] - first[0] == 1
        and last[1] > first[1]
    )


def exclusive_probe(target: PlacementTarget, pid: int, start: int, unit: str) -> bool:
    """相同项目子树只有锚定进程和已核固定probe;并发污染保持unknown。"""
    from paper_radar.pi_execution.placement import verify_placement

    try:
        verify_placement(target, pid, start, unit)
        from paper_radar.pi_execution.placement import _CGROUP_ROOT

        directory = _CGROUP_ROOT / target.ancestors[0].path.lstrip("/")
        pids: set[int] = set()
        for source in directory.rglob("cgroup.procs"):
            pids.update(int(value) for value in source.read_text().split())
        return pids == {pid, target.anchor_pid}
    except (OSError, ValueError):
        return False


def execute_negative(
    root: Path, site: SiteConfiguration, case_id: str, exchange: Callable[..., None]
) -> NetworkOutcome:
    import os
    import sys

    from paper_radar.live_evidence import network_probe
    from paper_radar.llm.dispatch import DispatchDenied
    from paper_radar.pi_execution.placement import PlacedProcess
    from paper_radar.pi_execution.process import adopt_process

    if os.getuid() != site.product_uid or os.getgid() != site.product_gid:
        raise DispatchDenied("permission_failed")
    placement = PlacedProcess()
    session = None
    try:
        child = placement.execute(
            (sys.executable, "-I", str(Path(network_probe.__file__))),
            env={},
            cwd=Path("/srv/pi-cwd"),
            install=site.install_path,
            attempt=None,
            proxy_port=None,
            pass_fds=(),
            before_release=lambda: exchange(
                "network", placement.pid, placement.start, placement.unit
            ),
        )
        session = adopt_process(child)
        placement.handoff()
        from time import monotonic

        deadline = monotonic() + 3
        pending = (case_id + "\n").encode()
        output = bytearray()
        while monotonic() < deadline:
            event = session.pump(pending, 0.05)
            pending = pending[event.written :]
            output.extend(event.stdout)
            if len(output) > 1024 or event.stderr_bytes:
                raise ValueError("collector_result_invalid")
            if not pending:
                session.close_stdin()
            if event.stdout_eof and event.stderr_eof and event.exit_code is not None:
                if event.exit_code != 0:
                    raise ValueError("collector_result_invalid")
                return NetworkOutcome.model_validate_json(bytes(output))
        raise ValueError("collector_child_timeout")
    except DispatchDenied:
        return NetworkOutcome(attempted=False, response=False)
    finally:
        if session is not None:
            session.terminate(2)
        placement.close()


def idle_probe_scope(target: PlacementTarget) -> bool:
    from paper_radar.pi_execution.placement import _CGROUP_ROOT, verify_placement

    try:
        verify_placement(
            target, target.anchor_pid, target.anchor_start, "paperradar-anchor.service"
        )
        directory = _CGROUP_ROOT / target.ancestors[0].path.lstrip("/")
        pids = {
            int(value)
            for source in directory.rglob("cgroup.procs")
            for value in source.read_text().split()
        }
        return pids == {target.anchor_pid}
    except (OSError, ValueError):
        return False
