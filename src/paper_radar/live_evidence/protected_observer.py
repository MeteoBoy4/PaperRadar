"""固定 root 快照来源;只读实际 nft、锚定 cgroup 与封印观察成员。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.observation import (
    CurrentObservation,
    load_refresh_status,
    read_observation_snapshot,
)
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.refresh import record_refresh
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement import (
    TARGET_FILENAME,
    PlacementTarget,
    verify_placement,
)
from paper_radar.pi_execution.site_binding import component_digest

# 部署包按此显式闭包封印;PID、启动时间不属于 observer 身份。
OBSERVER_MEMBERS = (
    "entry.py",
    "site.json",
    "manifest.sha256",
    "payload.sha256",
    "site-packages/paper_radar/live_evidence/sealed_runtime.py",
    "site-packages/paper_radar/pi_execution/site_binding.py",
    "site-packages/paper_radar/live_evidence/protected_observer.py",
    "site-packages/paper_radar/live_evidence/refresh.py",
    "site-packages/paper_radar/live_evidence/observation.py",
    "site-packages/paper_radar/pi_execution/placement.py",
)
REFRESH_HELPER = "/usr/libexec/paperradar/live-evidence-refresh"


def _protected_bytes(ledger: EvidenceLedger, source: Path) -> bytes:
    ledger._protected(source, source=True)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != ledger.trust.owner_uid
            or info.st_mode & 0o022
            or info.st_nlink != 1
            or info.st_size > 4 * 1024 * 1024
        ):
            raise LedgerError("source_untrusted")
        data = stream.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise LedgerError("source_untrusted")
    return data


def observer_identity(root: Path, ledger: EvidenceLedger) -> str:
    """实际受保护观察字节身份;不接受产品自报摘要。"""
    return component_digest(
        {
            name: hashlib.sha256(_protected_bytes(ledger, root / name)).hexdigest()
            for name in OBSERVER_MEMBERS
        }
    )


def read_nft_snapshot() -> dict[str, object]:
    """零参数固定只读命令;输出不上 stdout、不进入历史正文。"""

    def query(argv: tuple[str, ...]) -> tuple[int, dict[str, object]]:
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    env={},
                    timeout=5,
                    check=False,
                )
                if output.tell() > 1024 * 1024:
                    raise LedgerError("observation_unavailable")
                output.seek(0)
                raw = output.read()
                if not raw and result.returncode == 0:
                    raise LedgerError("observation_unavailable")
                value = json.loads(raw) if raw else {"nftables": []}
            except (OSError, ValueError, subprocess.SubprocessError):
                raise LedgerError("observation_unavailable") from None
        if not isinstance(value, dict) or not isinstance(value.get("nftables"), list):
            raise LedgerError("observation_unavailable")
        return result.returncode, value

    result, value = query(
        ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar")
    )
    if result == 0:
        return value
    # 第二个固定只读查询能确认表已丢失;权限/工具/原因不明仍只是临时不可用。
    result, tables = query(("/usr/sbin/nft", "-j", "list", "tables"))
    rows = tables["nftables"]
    if not isinstance(rows, list):
        raise LedgerError("observation_unavailable")
    if result == 0 and not any(
        isinstance(row, dict)
        and isinstance(row.get("table"), dict)
        and row["table"].get("family") == "inet"
        and row["table"].get("name") == "paperradar"
        for row in rows
    ):
        return {"nftables": []}
    raise LedgerError("observation_unavailable")


def stable_nft_snapshot(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: (
                {
                    field: stable_nft_snapshot(content)
                    for field, content in item.items()
                    if field not in {"packets", "bytes"}
                }
                if key == "counter" and isinstance(item, dict)
                else stable_nft_snapshot(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            stable_nft_snapshot(item)
            for item in value
            if not (isinstance(item, dict) and set(item) == {"metainfo"})
        ]
    return value


def egress_identity(snapshot: dict[str, object], target: PlacementTarget) -> str:
    """部署和刷新共用的规范规则/目标身份;计数器数值不是规则身份。"""

    return component_digest(
        {
            "nft": stable_nft_snapshot(snapshot),
            "placement": target.model_dump(mode="json", exclude={"egress_digest"}),
        }
    )


@contextmanager
def protected_collection_lock(ledger: EvidenceLedger) -> Iterator[int]:
    """同一固定 collector.lock 的 root 独占 fd,供封印 collector 组合使用。"""
    ledger._writer()
    ledger._protected(ledger.root)
    lock_path = ledger.root / "collector.lock"
    if lock_path.exists():
        ledger._protected(lock_path)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o644)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LedgerError("observation_unavailable") from None
        yield descriptor
    finally:
        os.close(descriptor)


def refresh_once(
    root: Path, ledger: EvidenceLedger, *, now: datetime | None = None
) -> str:
    """例行模式:不运行 β,不领取计划/预算,不接收或激活证据。"""
    with protected_collection_lock(ledger) as lock_fd:
        return refresh_under_lock(root, ledger, lock_fd=lock_fd, now=now)


def refresh_under_lock(
    root: Path, ledger: EvidenceLedger, *, lock_fd: int, now: datetime | None = None
) -> str:
    """已经持有同一内核锁的封印 collector 调用,避免另开 fd 自锁。"""
    ledger._writer()
    ledger._protected(ledger.root)
    info = os.fstat(lock_fd)
    expected = (ledger.root / "collector.lock").stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != ledger.trust.owner_uid
        or info.st_nlink != 1
        or info.st_mode & 0o022
        or (info.st_dev, info.st_ino) != (expected.st_dev, expected.st_ino)
    ):
        raise LedgerError("source_untrusted")
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    at = now or datetime.now(UTC)
    from paper_radar.live_evidence.sealed_runtime import (
        _read_configuration,
        _reconcile_collector_tightening,
        product_observation,
    )

    _reconcile_collector_tightening(ledger)
    try:
        previous = read_observation_snapshot(ledger, now=at)
        prior_status = load_refresh_status(ledger)
        if (
            prior_status is not None
            and prior_status.result == "available"
            and prior_status.snapshot_sha256
            != hashlib.sha256(canonical_bytes(previous)).hexdigest()
        ):
            raise LedgerError("source_integrity")
        identity = observer_identity(root, ledger)
        site = _read_configuration(root)
        raw = ledger._read_source(ledger.root / "inbox" / TARGET_FILENAME)
        target = PlacementTarget.model_validate_json(raw)
        if canonical_bytes(target) != raw:
            raise LedgerError("source_integrity")
    except (LedgerError, ValueError, OSError):
        return record_refresh(
            ledger, candidate=None, failure="source_untrusted", now=at
        ).result
    if prior_status is not None and prior_status.pending_revocation:
        record_refresh(
            ledger,
            candidate=None,
            failure="source_untrusted"
            if prior_status.result == "source_untrusted"
            else "observation_drift",
            now=at,
            confirmed_components=frozenset(prior_status.changed_components),
            placement_mismatch=prior_status.placement_mismatch,
        )
    # 必须先核实际 cgroup;nft 暂时失败不能遮蔽已确认的目标漂移。
    mismatch = None
    try:
        verify_placement(
            target,
            target.anchor_pid,
            target.anchor_start,
            "paperradar-anchor.service",
        )
    except ExecutionError as error:
        mismatch = error.reason
    incomplete = False
    observed_components = {B.OBSERVER: identity}
    try:
        snapshot = read_nft_snapshot()
        observed_components[B.IPV4_EGRESS] = egress_identity(snapshot, target)
    except LedgerError:
        incomplete = True
    if mismatch is not None:
        observed_components[B.IPV4_EGRESS] = component_digest(
            {"placement": mismatch, "target": target.model_dump(mode="json")}
        )
    try:
        local = product_observation(site, metadata_only=True)
        expected_components = set(B) - {B.IPV4_EGRESS, B.OBSERVER}
        if (
            local.checks != (("metadata", True),)
            or set(local.components) != expected_components
        ):
            incomplete = True
        else:
            observed_components.update(local.components)
    except (OSError, ValueError):
        incomplete = True
    changed = frozenset(
        component
        for component, value in observed_components.items()
        if previous.binding[component] != value
    )
    if (
        observed_components.get(B.IPV4_EGRESS, target.egress_digest)
        != target.egress_digest
    ):
        changed |= {B.IPV4_EGRESS}
    if incomplete:
        return record_refresh(
            ledger,
            candidate=None,
            failure="observation_drift" if changed else "observation_unavailable",
            now=at,
            confirmed_components=changed,
            placement_mismatch=mismatch is not None,
        ).result
    candidate = CurrentObservation(
        observed_at=at,
        binding=observed_components,
        checked_components=tuple(
            component for component in B if component in observed_components
        ),
    )
    return record_refresh(
        ledger,
        candidate=candidate,
        now=at,
        confirmed_components=changed,
        placement_mismatch=mismatch is not None,
    ).result


def request_observation_refresh() -> None:
    """普通消费者的固定零参数特权请求;任何失败都拒绝本次。"""
    started = datetime.now(UTC)
    try:
        result = subprocess.run(
            ("/usr/bin/sudo", "-n", "--", REFRESH_HELPER),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise LedgerError("observation_unavailable") from None
    if result.returncode != 0:
        # 真实漂移在受保护状态中有更精确原因;保留该分类供依赖收紧。
        from paper_radar.live_evidence.observation import load_refresh_status

        status = load_refresh_status(EvidenceLedger())
        if status is not None and status.result in {
            "observation_drift",
            "source_untrusted",
        }:
            raise LedgerError(
                "observation_drift"
                if status.result == "observation_drift"
                else "source_untrusted"
            )
        raise LedgerError("observation_unavailable")
    from paper_radar.live_evidence.observation import (
        load_current_observation,
        load_refresh_status,
    )

    ledger = EvidenceLedger()
    status = load_refresh_status(ledger)
    if status is None or status.recorded_at < started:
        raise LedgerError("observation_unavailable")
    current = load_current_observation(ledger, now=datetime.now(UTC))
    if current.observed_at < started:
        raise LedgerError("observation_unavailable")


def refresh_main(arguments: list[str] | None = None) -> int:
    if list(sys.argv[1:] if arguments is None else arguments):
        return 2
    from paper_radar.live_evidence.sealed_runtime import RUNTIME_ROOT

    try:
        result = refresh_once(RUNTIME_ROOT, EvidenceLedger())
        print(f"观察刷新 result={result}；未接收、未证据激活。")
        return 0 if result == "available" else 2
    except (LedgerError, ValueError, OSError):
        print(
            "观察刷新拒绝 [observation_unavailable]；请核对受保护来源与部署。",
            file=sys.stderr,
        )
        return 2
