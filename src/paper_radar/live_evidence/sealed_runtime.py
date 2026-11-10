"""固定封印入口;root 只执行冻结代码,现场读操作在产品 uid 子进程内。"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import resource
import select
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from paper_radar.live_evidence.collector import (
    SITE_CASES,
    SiteObservation,
    build_site_receipt,
)
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    Digest,
    UseId,
    WireModel,
    canonical_bytes,
)
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.current_binding import local_binding_components
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import IsolationBoundary
from paper_radar.pi_execution.resources import (
    ExecutionRoots,
    check_credentials_directory,
    check_cwd,
    proxy_port,
)
from paper_radar.pi_supply import SupplyError
from paper_radar.pi_supply.protection import acquire_install

RUNTIME_ROOT = Path("/usr/libexec/paperradar/live-evidence-runtime")


class SiteConfiguration(WireModel):
    product_uid: int = Field(gt=0, strict=True)
    product_gid: int = Field(gt=0, strict=True)
    database: Path
    snapshot_id: Digest
    install_path: Path
    claim_uses: tuple[UseId, ...] = ()
    credentials_dir: Path = Field(repr=False)
    roots: ExecutionRoots
    binding: EvidenceBinding
    use_id: UseId

    @model_validator(mode="after")
    def valid_site(self) -> Self:
        paths = (
            self.database,
            self.install_path,
            self.credentials_dir,
            self.roots.data_root,
            self.roots.config_root,
            self.roots.material_root,
            self.roots.install_root,
        )
        if any(not path.is_absolute() or ".." in path.parts for path in paths):
            raise ValueError("collector_path_invalid")
        if (
            self.install_path
            != self.roots.install_root
            / self.binding.supply_id
            / self.binding.install_id
        ):
            raise ValueError("collector_install_path_invalid")
        if len(set(self.claim_uses)) != len(self.claim_uses):
            raise ValueError("collector_use_duplicate")
        if self.use_id.rsplit("-", 1)[1] != self.binding.thinking_level:
            raise ValueError("collector_use_mismatch")
        return self


def _denied(operation: Callable[[], object]) -> bool:
    try:
        operation()
    except OSError as error:
        return error.errno in {errno.EACCES, errno.EPERM}
    return False


def _anonymous_write(directory: Path) -> None:
    # 无名字临时inode;即使隔离失效,关闭fd后也不遗留文件。
    descriptor = os.open(directory, os.O_TMPFILE | os.O_RDWR, 0o600)
    os.close(descriptor)


def isolation_probe(
    install: Path, *, proxy: str | None
) -> tuple[tuple[str, bool], ...]:
    """产品uid合成fork;只读/写合成文件,不触碰任何秘密内容或网络。"""
    cwd = check_cwd()
    with tempfile.TemporaryDirectory(prefix="paperradar-beta-") as temporary:
        root = Path(temporary)
        outside = root / "synthetic-outside"
        outside.write_bytes(b"synthetic\n")
        attempt = root / "attempt"
        attempt.mkdir()
        # 先证明合成外部文件在DAC下可读,再验证Landlock拒绝。
        if outside.read_bytes() != b"synthetic\n":
            return (("outside-read-denied", False),)
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            result: list[tuple[str, bool]] = []
            name = "outside-read-denied"
            try:
                IsolationBoundary(install, cwd, attempt, proxy_port(proxy))()
                for name, path in (
                    ("outside-read-denied", outside),
                    ("cwd-write-denied", cwd),
                    ("install-write-denied", install),
                ):
                    if name == "outside-read-denied":
                        passed = _denied(path.read_bytes)
                    else:
                        passed = _denied(partial(_anonymous_write, path))
                    result.append((name, passed))
                    if not passed:
                        break
                if len(result) == 3 and all(passed for _, passed in result):
                    name = "attempt-write-allowed"
                    (attempt / "allowed").write_bytes(b"synthetic")
                    result.append((name, True))
                    name = "core-zero"
                    result.append(
                        (
                            name,
                            resource.getrlimit(resource.RLIMIT_CORE) == (0, 0),
                        )
                    )
            except Exception:
                # 不输出异常文本、路径或数据;父进程只接收有限标准。
                if not result or all(passed for _, passed in result):
                    result.append((name, False))
            try:
                os.write(write_fd, json.dumps(result).encode())
            finally:
                os._exit(0)
        os.close(write_fd)
        try:
            with os.fdopen(read_fd, "rb") as source:
                raw = source.read(4096)
            _, status = os.waitpid(pid, 0)
            if status != 0:
                return (("outside-read-denied", False),)
            value = json.loads(raw)
            return tuple((str(name), passed is True) for name, passed in value)
        except (ValueError, OSError):
            return (("outside-read-denied", False),)


def observe_site(
    site: SiteConfiguration,
    *,
    metadata_only: bool = False,
    require_snapshot: bool = False,
) -> SiteObservation:
    """必须已不可逆降权;数据库/凭据仅以产品身份只读核对。"""
    if os.getuid() != site.product_uid or os.getgid() != site.product_gid:
        raise ValueError("collector_product_identity")
    try:
        from paper_radar.config import load_config_snapshot
        from paper_radar.pi_supply import activation_history

        history = activation_history(site.database)
        if (
            not history
            or (
                history[-1].supply_id,
                history[-1].install_id,
            )
            != (site.binding.supply_id, site.binding.install_id)
            or (
                (not metadata_only or require_snapshot)
                and history[-1].snapshot_id != site.snapshot_id
            )
        ):
            return SiteObservation(
                {}, (("metadata", False),), "binding_observation_unavailable"
            )
        load_config_snapshot(
            site.database,
            history[-1].snapshot_id if metadata_only else site.snapshot_id,
        )
        if metadata_only:
            if not site.roots.outside(site.credentials_dir):
                raise LedgerError("binding_observation_unavailable")
        else:
            check_credentials_directory(site.credentials_dir, site.roots)
        components = local_binding_components(
            site.database, site.binding, credentials_dir=site.credentials_dir
        )
        if metadata_only:
            return SiteObservation(components, (("metadata", True),))
        with acquire_install(
            site.database, site.binding.supply_id, site.binding.install_id
        ) as install:
            checks = isolation_probe(install.instance.path, proxy=site.binding.proxy)
            if all(passed for _, passed in checks) and len(checks) == 5:
                try:
                    result = subprocess.run(
                        [str(install.node), "--version"],
                        env={},
                        cwd=check_cwd(),
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    matches = result.returncode == 0 and result.stdout.strip().decode(
                        "ascii"
                    ).removeprefix(
                        "v"
                    ) == install.record.manifest.node_version.removeprefix("v")
                except (OSError, subprocess.SubprocessError, UnicodeError):
                    matches = False
                checks += (("node-version", matches),)
        return SiteObservation(components, (("metadata", True), *checks))
    except LedgerError as error:
        return SiteObservation(
            {},
            (("metadata", False),),
            "observation_unavailable"
            if error.category == "observation_unavailable"
            else "binding_observation_unavailable",
        )
    except (ExecutionError, SupplyError):
        return SiteObservation(
            {}, (("metadata", False),), "binding_observation_unavailable"
        )
    except Exception:
        return SiteObservation({}, (("metadata", False),), "observation_unavailable")


def product_observation(
    site: SiteConfiguration,
    *,
    metadata_only: bool = False,
    require_snapshot: bool = False,
) -> SiteObservation:
    """fork后不可逆降权且禁ptrace;不在降权与观察之间exec用户环境。"""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            os.environ.clear()
            os.setgroups([])
            os.setresgid(site.product_gid, site.product_gid, site.product_gid)
            os.setresuid(site.product_uid, site.product_uid, site.product_uid)
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE=0
                os._exit(2)
            observed = (
                observe_site(
                    site, metadata_only=True, require_snapshot=require_snapshot
                )
                if metadata_only
                else observe_site(site)
            )
            payload = json.dumps(
                {
                    "components": observed.components,
                    "checks": observed.checks,
                    "failure": observed.failure,
                }
            ).encode()
            os.write(write_fd, payload)
            os._exit(0)
        except BaseException:
            os._exit(2)
    os.close(write_fd)
    try:
        if not select.select([read_fd], [], [], 10 if metadata_only else 60)[0]:
            os.kill(pid, signal.SIGKILL)
            raise ValueError("collector_child_timeout")
        raw = os.read(read_fd, 65537)
        _, status = os.waitpid(pid, 0)
        if status != 0 or len(raw) > 65536:
            raise ValueError("collector_child_failed")
        result = json.loads(raw)
        failure = result.get("failure")
        if failure not in {
            None,
            "observation_unavailable",
            "binding_observation_unavailable",
        }:
            raise ValueError("collector_child_failed")
        return SiteObservation(
            {B(key): value for key, value in result["components"].items()},
            tuple((str(key), value is True) for key, value in result["checks"]),
            failure,
        )
    finally:
        os.close(read_fd)
        with suppress(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)


def _read_configuration(root: Path) -> SiteConfiguration:
    return SiteConfiguration.model_validate_json((root / "site.json").read_bytes())


def _publish(
    path: Path, data: bytes, *, replace: bool = False, mode: int = 0o644
) -> None:
    temporary = path.with_suffix(".new")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path, follow_symlinks=False)
            temporary.unlink()
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _reconcile_collector_tightening(ledger: EvidenceLedger) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

    lifecycle = EvidenceLifecycle(ledger)
    for pending in sorted(ledger.root.glob("*.tighten-pending")):
        ledger._protected(pending)
        instance = pending.read_text().strip()
        if len(instance) != 64 or any(
            value not in "0123456789abcdef" for value in instance
        ):
            raise LedgerError("ledger_untrusted")
        for received in ledger.list_received():
            if received.receipt.binding[B.INSTANCE] != instance:
                continue
            for use_id in sorted({claim.use_id for claim in received.receipt.claims}):
                lifecycle.tighten(
                    received.receipt_id, use_id, now=datetime.now(UTC), components=None
                )
        # 只有全部落账后解除待收紧标记;失败时观察仍不可读,不声称已撤销。
        pending.unlink()
        descriptor = os.open(ledger.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def collect_once(root: Path, ledger: EvidenceLedger) -> str:
    """特权边界内串行采集;重跑只刷新当前观察,不续原证明或覆盖失败。"""
    ledger._writer()
    ledger._protected(root)
    site = _read_configuration(root)
    plan = ApprovedPlan.model_validate_json((root / "plan.json").read_bytes())
    if plan.kind != "site_beta" or plan.cases != SITE_CASES or plan.max_rounds != 1:
        raise ValueError("collector_plan_invalid")
    now = datetime.now(UTC)
    if not plan.starts_at <= now <= plan.ends_at:
        raise ValueError("plan_window_invalid")
    ledger.initialize()
    plan_source = ledger.root / "inbox" / f"{plan.plan_id}-plan.json"
    if plan_source.exists():
        if ledger._read_source(plan_source) != canonical_bytes(plan):
            raise LedgerError("plan_conflict")
    else:
        _publish(plan_source, canonical_bytes(plan))
    with (ledger.root / "collector.lock").open("a+b") as lock:
        os.chmod(lock.name, 0o644)
        fcntl.flock(lock, fcntl.LOCK_EX)
        _reconcile_collector_tightening(ledger)
        stopped = ledger.root / f"{plan.plan_id}.stopped"
        if stopped.exists():
            ledger._protected(stopped)
            raise ValueError("plan_stopped")
        started = datetime.now(UTC)
        try:
            observed = product_observation(site)
            if observed.checks and observed.checks[0] == ("metadata", True):
                from paper_radar.live_evidence.site_tree import observe_tree

                actual_tree = observe_tree(
                    site.install_path, product_uid=site.product_uid
                )
                if any(
                    observed.components.get(component) != actual_tree
                    for component in (B.SUPPLY_TREE, B.INSTANCE_TREE)
                ):
                    raise ValueError("collector_tree_mismatch")
                observed.components[B.SUPPLY_TREE] = actual_tree
                observed.components[B.INSTANCE_TREE] = actual_tree
        except (ValueError, OSError):
            observed = SiteObservation({}, (("metadata", False),))
        completed = datetime.now(UTC)
        receipt, current = build_site_receipt(
            plan,
            observed,
            use_id=site.use_id,
            started_at=started,
            completed_at=completed,
            use_ids=site.claim_uses or (site.use_id,),
        )
        source = ledger.root / "inbox" / f"{plan.plan_id}-round-1.json"
        if receipt.failure_history:
            # 先封闭观察,使任何旧grant不能被local checked集合重新启用。
            _publish(
                ledger.root / "inbox/current-observation.json",
                canonical_bytes(current),
                replace=True,
                mode=0,
            )
            _publish(stopped, b"plan_stopped\n")
            from paper_radar.pi_execution.site_binding import component_digest

            _publish(
                ledger.root / f"{plan.plan_id}.tighten-pending",
                (component_digest(site.binding.install_id) + "\n").encode(),
            )
        # 每次调用都留下受保护失败/成功历史;只追加摘要,不记录子进程输出。
        event = {
            "at": completed.isoformat(),
            "cases": [case.model_dump(mode="json") for case in receipt.cases],
            "binding_sha256": hashlib.sha256(canonical_bytes(current)).hexdigest(),
        }
        with (ledger.root / "collector-history.jsonl").open("ab") as history:
            os.chmod(history.name, 0o644)
            history.write((json.dumps(event, sort_keys=True) + "\n").encode())
            history.flush()
            os.fsync(history.fileno())
        if not source.exists():
            _publish(source, canonical_bytes(receipt))
        else:
            ledger._read_source(source)
        if receipt.failure_history:
            _reconcile_collector_tightening(ledger)
        else:
            _publish(
                ledger.root / "inbox/current-observation.json",
                canonical_bytes(current),
                replace=True,
            )
        return source.name


def collector_main(arguments: list[str] | None = None) -> int:
    args = sys.argv[1:] if arguments is None else arguments
    if args:
        return 2
    try:
        name = collect_once(RUNTIME_ROOT, EvidenceLedger())
        print(f"source={name}；未接收、未证据激活；请所有者审阅受保护回执。")
        return 0
    except Exception:
        print(
            "站点采集拒绝 [collector_unavailable]；"
            "请所有者核对封印部署、计划窗口与受保护历史。",
            file=sys.stderr,
        )
        return 2


def runtime_main() -> int:
    """固定root冻结entry;放宽owner入口不在NOPASSWD中。"""
    args = sys.argv[1:]
    if args[:1] == ["collect"]:
        return collector_main(args[1:])
    if args[:1] == ["collect-models"]:
        from paper_radar.live_evidence.model_collector import model_collector_main

        return model_collector_main(args[1:])
    if args[:1] == ["refresh"]:
        from paper_radar.live_evidence.protected_observer import refresh_main

        return refresh_main(args[1:])
    if args[:1] == ["tighten"]:
        from paper_radar.live_evidence.tightening import tightening_main

        return tightening_main(args[1:])
    if args == ["owner", "provision-intents"]:
        from paper_radar.live_evidence.intents import ProtectedIntentLog

        ledger = EvidenceLedger()
        ledger._writer()
        ledger._protected(RUNTIME_ROOT)
        site = _read_configuration(RUNTIME_ROOT)
        ledger.initialize()
        ProtectedIntentLog(product_gid=site.product_gid).provision(
            ledger, now=datetime.now(UTC)
        )
        print("受保护收紧日志已核；cutover前旧资格不可恢复，新证据仍须本人显式激活。")
        return 0
    if args[:1] == ["owner"]:
        from paper_radar.live_evidence.cli import live_evidence_app

        live_evidence_app(args=args[1:])
        return 0
    return 2
