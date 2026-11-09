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


def selected_state(config: dict[str, str]) -> dict[str, Any]:
    from paper_radar.live_evidence.evaluator import evaluate_admission
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_id_for
    from paper_radar.live_evidence.observation import load_current_observation
    from paper_radar.live_evidence.registry import INITIAL_REGISTRY

    ledger = open_ledger()
    snapshot = EvidenceLifecycle(ledger).snapshot(now=now())
    sources = {(use, cap): rid for use, cap, rid in snapshot.sources}
    observation = load_current_observation(ledger, now=now())
    decisions = {
        use: evaluate_admission(
            INITIAL_REGISTRY,
            use,
            snapshot.evidence,
            binding=ExecutionBinding(tuple(observation.binding.items())),
            now=now(),
            checked_components=frozenset(observation.checked_components),
            ledger_watermark=snapshot.watermark,
        )
        for use in {item.use for item in snapshot.evidence}
    }
    selected = []
    for item in snapshot.evidence:
        if sources[(item.use, item.capability)] != config["receipt_id"]:
            continue
        assessment = decisions[item.use].for_capability(item.capability)
        selected.append(
            {
                "use_id": use_id_for(item.use),
                "capability": item.capability.value,
                "active": item.evidence_active and not item.revoked,
                "revoked": item.revoked,
                "qualified": decisions[item.use]
                .for_capability(item.capability)
                .qualified,
                "expires_at": (
                    assessment.expires_at.isoformat() if assessment.expires_at else None
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
                if item.evidence_active and not item.revoked
            }
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
            str(PACKAGE / "workflow.py"),
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


def exercise(config: dict[str, str], output: Path) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

    ledger = open_ledger()
    lifecycle = EvidenceLifecycle(ledger)
    run_entry([str(COLLECT)])
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
    ledger._protected(PACKAGE / "config.json")
    config: dict[str, str] = json.loads((PACKAGE / "config.json").read_bytes())
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
