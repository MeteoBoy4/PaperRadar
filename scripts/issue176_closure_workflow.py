"""仅供所有者审阅后从root冻结副本执行的单次收口流程。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import subprocess
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from paper_radar.live_evidence.intents import ProtectedIntentLog
    from paper_radar.live_evidence.ledger import EvidenceLedger

RUNTIME = Path("/usr/libexec/paperradar/live-evidence-runtime")
OWNER = Path("/usr/libexec/paperradar/live-evidence-owner")
COLLECT = Path("/usr/libexec/paperradar/live-evidence-collect")
TIGHTEN = Path("/usr/libexec/paperradar/live-evidence-tighten")
PACKAGE = Path(__file__).parent


def now() -> datetime:
    return datetime.now(UTC)


def run_entry(arguments: list[str], *, interactive: bool = False) -> None:
    # 激活继承本人终端;绝不捕获/生成/管道传入短ID。
    result = subprocess.run(
        arguments,
        env={},
        stdin=None if interactive else subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("closure_entry_failed")


def write_report(path: Path, report: dict[str, Any]) -> None:
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(
            (json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n").encode()
        )
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def open_ledger() -> EvidenceLedger:
    from paper_radar.live_evidence.ledger import EvidenceLedger

    return EvidenceLedger()


def open_intents() -> ProtectedIntentLog:
    from paper_radar.live_evidence.intents import ProtectedIntentLog
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

    site = SiteConfiguration.model_validate_json((RUNTIME / "site.json").read_bytes())
    return ProtectedIntentLog(product_gid=site.product_gid)


def selected_state(config: dict[str, str]) -> dict[str, Any]:
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_id_for
    from paper_radar.live_evidence.observation import load_current_observation
    from paper_radar.live_evidence.service import (
        AdmissionRequest,
        load_owner_admission_evidence,
    )

    ledger = open_ledger()
    snapshot = EvidenceLifecycle(ledger).snapshot(now=now())
    sources = {(use, cap): rid for use, cap, rid in snapshot.sources}
    observation = load_current_observation(ledger, now=now())
    projections = {
        use: load_owner_admission_evidence(
            AdmissionRequest(
                use,
                ExecutionBinding(tuple(observation.binding.items())),
                frozenset(observation.checked_components),
            ),
            now=now(),
            ledger=ledger,
            intents=open_intents(),
        )
        for use in {item.use for item in snapshot.evidence}
    }
    assessments = {
        (use, assessment.capability): assessment
        for use, projection in projections.items()
        for assessment in projection.decision.capabilities
    }
    selected = []
    for item in snapshot.evidence:
        if sources[(item.use, item.capability)] != config["receipt_id"]:
            continue
        assessment = assessments.get((item.use, item.capability))
        selected.append(
            {
                "use_id": use_id_for(item.use),
                "capability": item.capability.value,
                "raw_active": item.evidence_active and not item.revoked,
                "active": bool(
                    assessment and assessment.evidence_active and not assessment.revoked
                ),
                "revoked": assessment.revoked if assessment else item.revoked,
                "qualified": bool(assessment and assessment.qualified),
                "expires_at": (
                    assessment.expires_at.isoformat()
                    if assessment and assessment.expires_at
                    else None
                ),
                "original_state": item.claim.status.value,
                "verified_at": item.claim.verified_at.isoformat()
                if item.claim.verified_at
                else None,
            }
        )
    return {
        "observed_at": now().isoformat(),
        "selected": selected,
        "watermark": snapshot.watermark.isoformat() if snapshot.watermark else None,
        "active_groups": sorted(
            {
                (sources[(item.use, item.capability)], use_id_for(item.use))
                for item in snapshot.evidence
                if (assessment := assessments.get((item.use, item.capability)))
                is not None
                and assessment.evidence_active
                and not assessment.revoked
            }
        ),
        "pending_revocation": any(
            item.pending_revocation for item in projections.values()
        ),
        "events": [
            {"sequence": event.sequence, "action": event.action}
            for event in ledger.audit()
        ],
    }


def checkpoint(config: dict[str, str], destination: Path) -> dict[str, Any]:
    # 每个检查点以全新解释器/只读账本进程取得;不把当前内存对象当重启证据。
    run_entry(
        [
            str(RUNTIME / "python/bin/python3"),
            "-I",
            "-S",
            "-B",
            str(Path(__file__).absolute()),
            "checkpoint",
            str(destination),
        ]
    )
    return json.loads(destination.read_bytes())  # type: ignore[no-any-return]


def budget_inventory() -> dict[str, dict[str, int | str]]:
    # 任务暂停且无sidecar时读取稳定主文件;immutable禁止SQLite创建WAL/SHM。
    # 仅必要预算ID/指纹、代际、attempt序号和每日领取标识,不选payload/token/正文。
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

    site = SiteConfiguration.model_validate_json((RUNTIME / "site.json").read_bytes())
    if any(
        os.path.lexists(str(site.database) + suffix)
        for suffix in ("-wal", "-shm", "-journal")
    ):
        raise ValueError("closure_business_sidecars_present")
    descriptor = os.open(site.database, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != site.product_uid:
            raise ValueError("closure_business_database_untrusted")
        queries = {
            "screening_budgets": "budget_id,fingerprint",
            "screening_tasks": "task_id,budget_id,generation",
            "screening_attempts": "task_id,attempt_no",
            "screening_requests": "receipt_id,task_id,source,scheduled_day",
            "read_budgets": "budget_id,fingerprint",
            "read_tasks": "task_id,budget_id,generation",
            "read_attempts": "attempt_id,task_id,ordinal",
        }
        result: dict[str, dict[str, int | str]] = {}
        uri = f"file:/proc/self/fd/{descriptor}?mode=ro&immutable=1"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            for table, columns in queries.items():
                rows = connection.execute(
                    f"SELECT {columns} FROM {table} ORDER BY 1,2"
                ).fetchall()
                result[table] = {
                    "count": len(rows),
                    "identity_sha256": hashlib.sha256(
                        json.dumps(rows, separators=(",", ":")).encode()
                    ).hexdigest(),
                }
        if os.fstat(descriptor) != before or any(
            os.path.lexists(str(site.database) + suffix)
            for suffix in ("-wal", "-shm", "-journal")
        ):
            raise ValueError("closure_business_database_changed")
        return result
    finally:
        os.close(descriptor)


def activate(config: dict[str, str], use_id: str) -> None:
    # 先真实刷新初始观察;已有CLI确认之后会再刷新并严格重核60秒时效。
    run_entry([str(COLLECT)])
    run_entry(
        [
            str(OWNER),
            "activate",
            "--receipt-id",
            config["receipt_id"],
            "--use-id",
            use_id,
        ],
        interactive=True,
    )


def active_for(state: dict[str, Any], use_id: str) -> set[str]:
    return {
        item["capability"]
        for item in state["selected"]
        if item["use_id"] == use_id and item["active"]
    }


def product_log_probe(config: dict[str, str]) -> dict[str, Any]:
    """owner授权现场负例;fork后降权,NNP使固定sudo helper不能提权。"""
    import ctypes
    import errno
    import select
    import signal
    import tempfile

    from paper_radar.live_evidence import intents, service
    from paper_radar.live_evidence.lifecycle import use_for_id, use_id_for
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

    ledger = open_ledger()
    ledger._writer()
    log = open_intents()
    log.read(ledger)
    site = SiteConfiguration.model_validate_json((RUNTIME / "site.json").read_bytes())
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        result: dict[str, Any] = {}
        try:
            os.environ.clear()
            os.setgroups([])
            os.setresgid(site.product_gid, site.product_gid, site.product_gid)
            os.setresuid(site.product_uid, site.product_uid, site.product_uid)
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(4, 0, 0, 0, 0) != 0 or libc.prctl(38, 1, 0, 0, 0) != 0:
                raise ValueError("closure_product_probe_failed")  # PR_SET_NO_NEW_PRIVS
            if os.getuid() != site.product_uid or os.getgid() != site.product_gid:
                raise ValueError("closure_product_probe_failed")
            with tempfile.TemporaryDirectory(
                prefix="paperradar-intent-probe-"
            ) as temporary:
                root = Path(temporary)
                replacement = root / "replacement"
                replacement.write_bytes(b"synthetic-only\n")

                def truncate() -> None:
                    fd = os.open(log.path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
                    os.close(fd)

                def overwrite() -> None:
                    fd = os.open(log.path, os.O_WRONLY | os.O_NOFOLLOW)
                    os.close(fd)

                def clear_flag() -> None:
                    import array

                    fd = os.open(log.path, os.O_RDONLY | os.O_NOFOLLOW)
                    try:
                        flags = array.array(
                            "I", [intents._get_flags(fd) & ~intents.FS_APPEND_FL]
                        )
                        fcntl.ioctl(fd, intents._flags_command(write=True), flags, True)
                    finally:
                        os.close(fd)

                operations = {
                    "delete": log.path.unlink,
                    "truncate": truncate,
                    "overwrite": overwrite,
                    "replace": lambda: replacement.replace(log.path),
                    "hardlink": lambda: os.link(log.path, root / "link"),
                    "clear_flag": clear_flag,
                }
                for name, operation in operations.items():
                    try:
                        operation()
                    except OSError as error:
                        if error.errno not in {errno.EACCES, errno.EPERM}:
                            raise ValueError("closure_product_probe_failed") from None
                    else:
                        raise ValueError("closure_product_probe_failed")
                    result[name] = True
                # NNP只作用本子进程,不改变部署/sudoers;已审固定helper必须失败。
                helper_ok = service.request_revocation(
                    config["receipt_id"],
                    use_id_for(use_for_id(config["drill_use"])),
                    now=now(),
                )
                if helper_ok:
                    raise ValueError("closure_product_probe_failed")
                result["helper_failed_intent_persisted"] = True
            os.write(write_fd, json.dumps(result, sort_keys=True).encode())
            os._exit(0)
        except BaseException:
            os._exit(2)
    os.close(write_fd)
    try:
        if not select.select([read_fd], [], [], 30)[0]:
            os.kill(pid, signal.SIGKILL)
            raise ValueError("closure_product_probe_failed")
        raw = os.read(read_fd, 4097)
        _, status = os.waitpid(pid, 0)
        expected = {
            "delete",
            "truncate",
            "overwrite",
            "replace",
            "hardlink",
            "clear_flag",
            "helper_failed_intent_persisted",
        }
        result = json.loads(raw)
        if (
            status != 0
            or len(raw) > 4096
            or set(result) != expected
            or not all(value is True for value in result.values())
        ):
            raise ValueError("closure_product_probe_failed")
        log.read(ledger)
        return result
    finally:
        os.close(read_fd)
        from contextlib import suppress

        with suppress(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)


def resolve_receipt(config: dict[str, str]) -> dict[str, str]:
    if "receipt_id" in config:
        return config
    records = [
        record
        for record in open_ledger().list_received()
        if record.receipt.plan_id == config["plan_id"]
    ]
    if len(records) != 1:
        raise ValueError("closure_current_plan_receipt_missing")
    return config | {"receipt_id": records[0].receipt_id}


def exercise(config: dict[str, str], output: Path) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

    config = resolve_receipt(config)
    ledger = open_ledger()
    lifecycle = EvidenceLifecycle(ledger)
    run_entry([str(COLLECT)])
    initial = selected_state(config)
    if config.get("initial_activation") == "required":
        if initial["active_groups"] or any(
            item["revoked"] for item in initial["selected"]
        ):
            raise ValueError("closure_initial_scope_changed")
        activate(config, config["final_use"])
        initial = selected_state(config)
    # 本方案只扰动所选最终格及一个尚未激活/撤销的独立临时格。
    if initial["active_groups"] != [(config["receipt_id"], config["final_use"])]:
        raise ValueError("closure_active_scope_changed")
    expected_final = active_for(initial, config["final_use"])
    if any(
        item["active"] and not item["qualified"]
        for item in initial["selected"]
        if item["use_id"] == config["final_use"]
    ):
        raise ValueError("closure_final_not_applicable")
    if not expected_final or any(
        item["revoked"] and item["use_id"] == config["drill_use"]
        for item in initial["selected"]
    ):
        raise ValueError("closure_not_eligible")
    output.mkdir(mode=0o755)
    write_report(output / "initial.json", initial)
    budgets = budget_inventory()
    write_report(output / "business-before.json", {"budget_inventory": budgets})
    activate(config, config["drill_use"])
    activated = checkpoint(config, output / "drill-active.json")
    if not active_for(activated, config["drill_use"]):
        raise ValueError("closure_drill_activation_missing")
    backup = output / "before-revoke.sqlite3"
    lifecycle.backup(backup)
    product_protection = {}
    if config.get("protected_log_probe") == "required":
        product_protection = product_log_probe(config)
        denied = checkpoint(config, output / "helper-failed.json")
        if active_for(denied, config["drill_use"]) or not denied["pending_revocation"]:
            raise ValueError("closure_pending_intent_ignored")
        write_report(output / "product-protection.json", product_protection)
    run_entry(
        [
            str(TIGHTEN),
            "revoke",
            config["receipt_id"],
            config["drill_use"],
            "unknown",
            "",
        ]
    )
    revoked = checkpoint(config, output / "drill-revoked.json")
    if active_for(revoked, config["drill_use"]) or not any(
        item["revoked"] and item["use_id"] == config["drill_use"]
        for item in revoked["selected"]
    ):
        raise ValueError("closure_revocation_missing")
    lifecycle.restore(backup, now=now())
    restored = checkpoint(config, output / "restored.json")
    if restored["active_groups"] or not any(
        item["revoked"] and item["use_id"] == config["drill_use"]
        for item in restored["selected"]
    ):
        raise ValueError("closure_restore_resurrected")
    activate(config, config["final_use"])
    final = checkpoint(config, output / "final.json")
    if active_for(final, config["final_use"]) != expected_final:
        raise ValueError("closure_final_activation_missing")
    if any(
        item["active"] and not item["qualified"]
        for item in final["selected"]
        if item["use_id"] == config["final_use"]
    ):
        raise ValueError("closure_final_not_applicable")
    if active_for(final, config["drill_use"]):
        raise ValueError("closure_revocation_resurrected")
    if budget_inventory() != budgets:
        raise ValueError("closure_business_database_changed")
    events = ledger.audit()
    current = ledger.show(config["receipt_id"])
    write_report(
        output / "safety-receipt.json",
        {
            "status": "completed",
            "recorded_at": now().isoformat(),
            "receipt_id": config["receipt_id"],
            "use_id": config["final_use"],
            "registry_version": current.receipt.registry_version,
            "binding_sha256": hashlib.sha256(
                json.dumps(dict(current.receipt.binding), sort_keys=True).encode()
            ).hexdigest(),
            "capabilities": sorted(expected_final),
            "activation_events": [
                {
                    "sequence": event.sequence,
                    "activated_at": event.recorded_at.isoformat(),
                    "details": json.loads(event.reason or "{}"),
                }
                for event in events
                if event.action == "evidence_activated"
                and event.subject_id == config["receipt_id"]
            ],
            "expires_by_capability": {
                item["capability"]: item["expires_at"]
                for item in final["selected"]
                if item["use_id"] == config["final_use"]
            },
            "original_claims": [
                claim.model_dump(mode="json")
                for claim in current.receipt.claims
                if claim.use_id == config["final_use"]
            ],
            "business_budget_inventory_unchanged": True,
            "product_protection": product_protection,
            "requests": {"authentication": 0, "model": 0, "network": 0},
        },
    )
    print("收口演练完成：最终非空站点分项active；模型/RPC缺口仍保持。")


def main() -> int:
    # 只从已核root冻结副本导入已部署冻结依赖;不加载repo/venv/用户site。
    sys.path.insert(0, str(RUNTIME / "site-packages"))
    ledger = open_ledger()
    ledger._writer()
    ledger._protected(Path(__file__).absolute())
    configuration = PACKAGE / (
        "owner-closure.json"
        if Path(__file__).name == "owner-closure.py"
        else "config.json"
    )
    ledger._protected(configuration)
    config: dict[str, str] = json.loads(configuration.read_bytes())
    from paper_radar.pi_execution.current_binding import ADMISSION_POLICY_VERSION

    if config.get("admission_policy") != ADMISSION_POLICY_VERSION:
        raise ValueError("closure_admission_policy_mismatch")
    config = resolve_receipt(config)
    if len(sys.argv) == 3 and sys.argv[1] == "checkpoint":
        destination = Path(sys.argv[2])
        if destination.parent != ledger.root / config["run_name"]:
            raise ValueError("closure_checkpoint_path_invalid")
        ledger._protected(destination.parent)
        write_report(destination, selected_state(config))
        return 0
    if len(sys.argv) != 1:
        raise ValueError("closure_arguments_invalid")
    # 锁只串行本收口工具;owner须事先暂停其他准入写操作/业务任务。
    descriptor = os.open(
        ledger.root / "closure.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o644
    )
    with os.fdopen(descriptor, "r+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        exercise(config, ledger.root / config["run_name"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        print("收口拒绝：检查root检查点；不自动回滚、清理或恢复资格。", file=sys.stderr)
        raise SystemExit(2) from None
