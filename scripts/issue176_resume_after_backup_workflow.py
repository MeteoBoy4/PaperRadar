"""独立封印owner续行;不修改已部署v4,只从已保护backup之后继续。"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNTIME = Path("/usr/libexec/paperradar/live-evidence-runtime")
TEMP_BASE = Path("/var/tmp")
ROOT_UID = 0
ROOT_GID = 0
CHECKPOINTS = (
    "initial.json",
    "business-before.json",
    "drill-active.json",
    "before-revoke.sqlite3",
)
PROTECTION = {
    "delete",
    "truncate",
    "overwrite",
    "replace",
    "hardlink",
    "clear_flag",
    "helper_failed_intent_persisted",
}


def validate_inputs(data: dict[str, Any]) -> None:
    required = {
        "constraints_only_not_grant_authority",
        "receipt_id",
        "plan_id",
        "run_name",
        "admission_policy",
        "final_use",
        "drill_use",
        "payload_sha256",
        "manifest_sha256",
        "owner_script_sha256",
        "owner_config_sha256",
        "checkpoint_sha256",
        "expected_final_capabilities",
        "expected_drill_capabilities",
        "same_device_tempdir",
    }
    if (
        not isinstance(data, dict)
        or set(data) != required
        or data["constraints_only_not_grant_authority"] is not True
    ):
        raise ValueError("resume_inputs_invalid")
    for name in (
        "payload_sha256",
        "manifest_sha256",
        "owner_script_sha256",
        "owner_config_sha256",
    ):
        if (
            not isinstance(data[name], str)
            or re.fullmatch("[0-9a-f]{64}", data[name]) is None
        ):
            raise ValueError("resume_inputs_invalid")
    if not isinstance(data["checkpoint_sha256"], dict) or set(
        data["checkpoint_sha256"]
    ) != set(CHECKPOINTS):
        raise ValueError("resume_inputs_invalid")
    if any(
        not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None
        for value in data["checkpoint_sha256"].values()
    ):
        raise ValueError("resume_inputs_invalid")
    if (
        re.fullmatch("[0-9a-f]{16}", str(data["receipt_id"])) is None
        or re.fullmatch("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", str(data["plan_id"]))
        is None
        or re.fullmatch("closure-[A-Za-z0-9_-]{1,96}", str(data["run_name"])) is None
    ):
        raise ValueError("resume_inputs_invalid")
    if (
        data["admission_policy"],
        data["final_use"],
        data["drill_use"],
        data["same_device_tempdir"],
    ) != ("pi-admission-v4", "boundary-low", "value-low", "/var/tmp"):
        raise ValueError("resume_inputs_invalid")
    from paper_radar.live_evidence.types import Capability

    for name in ("expected_final_capabilities", "expected_drill_capabilities"):
        values = data[name]
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(value, str) for value in values)
            or len(values) != len(set(values))
        ):
            raise ValueError("resume_inputs_invalid")
        try:
            for value in values:
                Capability(value)
        except (TypeError, ValueError):
            raise ValueError("resume_inputs_invalid") from None


def protected_bytes(
    ledger: Any, path: Path, digest: str, *, retain: bool = True
) -> bytes:
    ledger._protected(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size > 128 * 1024 * 1024
        ):
            raise ValueError("resume_source_untrusted")
        hasher = hashlib.sha256()
        chunks = []
        while chunk := stream.read(65536):
            hasher.update(chunk)
            if retain:
                chunks.append(chunk)
        after = os.fstat(stream.fileno())
        if (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or hasher.hexdigest() != digest:
            raise ValueError("resume_source_integrity")
        return b"".join(chunks)


def mount_id(fd: int) -> int:
    try:
        for line in Path(f"/proc/self/fdinfo/{fd}").read_text().splitlines():
            if line.startswith("mnt_id:"):
                value = int(line.split(":", 1)[1].strip())
                if value > 0:
                    return value
    except (OSError, ValueError):
        pass
    raise ValueError("resume_temp_mount_unknown")


def same_device_probe(owner: Any, config: dict[str, Any]) -> dict[str, Any]:
    info = TEMP_BASE.lstat()
    target = owner.open_intents().path
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != ROOT_UID
        or info.st_gid != ROOT_GID
        or stat.S_IMODE(info.st_mode) != 0o1777
    ):
        raise ValueError("resume_temp_untrusted")
    if info.st_dev != target.stat().st_dev:
        raise ValueError("resume_temp_device_mismatch")
    base_fd = os.open(TEMP_BASE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        log_fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if mount_id(base_fd) != mount_id(log_fd):
                raise ValueError("resume_temp_mount_mismatch")
        finally:
            os.close(log_fd)
    finally:
        os.close(base_fd)
    # 原v4子进程会清env,但保留fork继承的标准库cached tempdir。
    # 仅改变合成文件位置,不改原probe/EACCES/EPERM/NNP/共享权威。
    previous = tempfile.tempdir
    try:
        tempfile.tempdir = str(TEMP_BASE)
        return owner.product_log_probe(config)  # type: ignore[no-any-return]
    finally:
        tempfile.tempdir = previous


def groups(state: dict[str, Any]) -> set[tuple[str, str]]:
    return {(str(item[0]), str(item[1])) for item in state["active_groups"]}


def preflight(
    inputs: dict[str, Any], owner: Any
) -> tuple[Any, dict[str, str], Path, dict[str, Any], set[str]]:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_id_for

    ledger = owner.open_ledger()
    ledger._writer()
    from paper_radar.pi_execution.current_binding import ADMISSION_POLICY_VERSION

    if inputs["admission_policy"] != ADMISSION_POLICY_VERSION:
        raise ValueError("resume_policy_changed")
    original = json.loads(
        protected_bytes(
            ledger, RUNTIME / "owner-closure.json", inputs["owner_config_sha256"]
        )
    )
    protected_bytes(
        ledger,
        RUNTIME / "owner-closure.py",
        inputs["owner_script_sha256"],
        retain=False,
    )
    for name in ("plan_id", "run_name", "admission_policy", "final_use", "drill_use"):
        if original.get(name) != inputs[name]:
            raise ValueError("resume_original_config_changed")
    if (
        original.get("initial_activation") != "required"
        or original.get("protected_log_probe") != "required"
    ):
        raise ValueError("resume_original_config_changed")
    config = owner.resolve_receipt(original)
    if config["receipt_id"] != inputs["receipt_id"]:
        raise ValueError("resume_receipt_changed")
    output = ledger.root / inputs["run_name"]
    ledger._protected(output)
    if not output.is_dir() or {path.name for path in output.iterdir()} != set(
        CHECKPOINTS
    ):
        raise ValueError("resume_phase_changed")
    checkpoints = {
        name: protected_bytes(
            ledger, output / name, digest, retain=name.endswith(".json")
        )
        for name, digest in inputs["checkpoint_sha256"].items()
    }
    if any(
        os.path.lexists(str(output / "before-revoke.sqlite3") + suffix)
        for suffix in ("-journal", "-wal", "-shm")
    ):
        raise ValueError("resume_backup_untrusted")
    initial = json.loads(checkpoints["initial.json"])
    drilled = json.loads(checkpoints["drill-active.json"])
    expected_final = set(inputs["expected_final_capabilities"])
    expected_drill = set(inputs["expected_drill_capabilities"])
    expected_groups = {
        (config["receipt_id"], config["final_use"]),
        (config["receipt_id"], config["drill_use"]),
    }
    if (
        groups(initial) != {(config["receipt_id"], config["final_use"])}
        or groups(drilled) != expected_groups
        or owner.active_for(initial, config["final_use"]) != expected_final
        or owner.active_for(drilled, config["final_use"]) != expected_final
        or owner.active_for(drilled, config["drill_use"]) != expected_drill
    ):
        raise ValueError("resume_checkpoint_state_changed")
    if (
        initial.get("pending_revocation")
        or drilled.get("pending_revocation")
        or any(item["revoked"] for item in initial["selected"] + drilled["selected"])
    ):
        raise ValueError("resume_checkpoint_state_changed")
    record = ledger.show(config["receipt_id"])
    if record.receipt.plan_id != config["plan_id"]:
        raise ValueError("resume_receipt_changed")
    plan = ledger.show_plan(config["plan_id"])
    if (
        not plan.starts_at <= owner.now() <= plan.ends_at
        or plan.max_auth_calls
        or plan.max_model_calls
        or plan.max_network_requests
        or plan.max_rounds != 1
        or not plan.stop_on_first_failure
        or os.path.lexists(ledger.root / f"{plan.plan_id}.stopped")
        or any(
            event.action == "plan_stopped" and event.subject_id == plan.plan_id
            for event in ledger.audit()
        )
    ):
        raise ValueError("resume_plan_invalid")
    log = owner.open_intents()
    if log.read(ledger):
        raise ValueError("resume_pending_revocation")
    snapshot = EvidenceLifecycle(ledger).snapshot(now=owner.now())
    sources = {
        (use, capability): receipt for use, capability, receipt in snapshot.sources
    }
    actual: dict[str, set[str]] = {}
    for item in snapshot.evidence:
        if item.evidence_active and not item.revoked:
            if sources[(item.use, item.capability)] != config["receipt_id"]:
                raise ValueError("resume_active_scope_changed")
            actual.setdefault(use_id_for(item.use), set()).add(item.capability.value)
        if (
            sources[(item.use, item.capability)] == config["receipt_id"]
            and item.revoked
        ):
            raise ValueError("resume_revocation_changed")
    if snapshot.pending_revocation or actual != {
        config["final_use"]: expected_final,
        config["drill_use"]: expected_drill,
    }:
        raise ValueError("resume_active_scope_changed")
    budgets = json.loads(checkpoints["business-before.json"])["budget_inventory"]
    if owner.budget_inventory() != budgets:
        raise ValueError("resume_business_budget_changed")
    return ledger, config, output, budgets, expected_final


def resume_after_backup(
    inputs: dict[str, Any], owner: Any, progress: Any = None
) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

    def stage(name: str) -> None:
        if progress is not None:
            progress(name)

    validate_inputs(inputs)
    stage("preflight")
    ledger, config, output, budgets, expected_final = preflight(inputs, owner)
    stage("refresh_current_observation")
    owner.run_entry([str(owner.COLLECT)])
    current = owner.selected_state(config)
    if (
        groups(current)
        != {
            (config["receipt_id"], config["final_use"]),
            (config["receipt_id"], config["drill_use"]),
        }
        or current["pending_revocation"]
        or any(item["active"] and not item["qualified"] for item in current["selected"])
    ):
        raise ValueError("resume_current_not_applicable")
    if owner.budget_inventory() != budgets:
        raise ValueError("resume_business_budget_changed")
    stage("same_device_product_probe")
    protection = same_device_probe(owner, config)
    if set(protection) != PROTECTION or not all(
        value is True for value in protection.values()
    ):
        raise ValueError("resume_product_probe_incomplete")
    denied = owner.checkpoint(config, output / "helper-failed.json")
    if (
        owner.active_for(denied, config["drill_use"])
        or not denied["pending_revocation"]
    ):
        raise ValueError("resume_pending_intent_ignored")
    owner.write_report(output / "product-protection.json", protection)
    stage("protected_revoke")
    owner.run_entry(
        [
            str(owner.TIGHTEN),
            "revoke",
            config["receipt_id"],
            config["drill_use"],
            "unknown",
            "",
        ]
    )
    revoked = owner.checkpoint(config, output / "drill-revoked.json")
    if owner.active_for(revoked, config["drill_use"]) or not any(
        item["revoked"] and item["use_id"] == config["drill_use"]
        for item in revoked["selected"]
    ):
        raise ValueError("resume_revocation_missing")
    stage("restore_existing_backup")
    EvidenceLifecycle(ledger).restore(output / "before-revoke.sqlite3", now=owner.now())
    restored = owner.checkpoint(config, output / "restored.json")
    if restored["active_groups"] or not any(
        item["revoked"] and item["use_id"] == config["drill_use"]
        for item in restored["selected"]
    ):
        raise ValueError("resume_restore_resurrected")
    stage("final_owner_activation")
    owner.activate(config, config["final_use"])
    final = owner.checkpoint(config, output / "final.json")
    if (
        owner.active_for(final, config["final_use"]) != expected_final
        or owner.active_for(final, config["drill_use"])
        or any(item["active"] and not item["qualified"] for item in final["selected"])
    ):
        raise ValueError("resume_final_not_applicable")
    if owner.budget_inventory() != budgets:
        raise ValueError("resume_business_budget_changed")
    # 原四文件/backup始终只读,包括恢复前后均复核原SHA。
    for name, digest in inputs["checkpoint_sha256"].items():
        protected_bytes(ledger, output / name, digest, retain=False)
    record = ledger.show(config["receipt_id"])
    owner.write_report(
        output / "safety-receipt.json",
        {
            "status": "completed",
            "resumed_after_backup": True,
            "resume_code_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "recorded_at": owner.now().isoformat(),
            "receipt_id": config["receipt_id"],
            "use_id": config["final_use"],
            "registry_version": record.receipt.registry_version,
            "binding_sha256": hashlib.sha256(
                json.dumps(dict(record.receipt.binding), sort_keys=True).encode()
            ).hexdigest(),
            "capabilities": sorted(expected_final),
            "product_protection": protection,
            "original_claims": [
                claim.model_dump(mode="json")
                for claim in record.receipt.claims
                if claim.use_id == config["final_use"]
            ],
            "activation_events": [
                {
                    "sequence": event.sequence,
                    "activated_at": event.recorded_at.isoformat(),
                    "details": json.loads(event.reason or "{}"),
                }
                for event in ledger.audit()
                if event.action == "evidence_activated"
                and event.subject_id == config["receipt_id"]
            ],
            "expires_by_capability": {
                item["capability"]: item["expires_at"]
                for item in final["selected"]
                if item["use_id"] == config["final_use"]
            },
            "business_budget_inventory_unchanged": True,
            "requests": {"authentication": 0, "model": 0, "network": 0},
        },
    )
    stage("completed")


def load_owner(inputs: dict[str, Any]) -> Any:
    from paper_radar.live_evidence.ledger import EvidenceLedger

    ledger = EvidenceLedger()
    ledger._writer()
    protected_bytes(
        ledger,
        RUNTIME / "owner-closure.py",
        inputs["owner_script_sha256"],
        retain=False,
    )
    spec = importlib.util.spec_from_file_location(
        "frozen_owner_v4", RUNTIME / "owner-closure.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("resume_owner_unavailable")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    return owner


def acquire_lock(ledger: Any) -> int:
    path = ledger.root / "closure.lock"
    ledger._protected(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("resume_lock_untrusted")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("resume_lock_busy") from None
        return fd
    except BaseException:
        os.close(fd)
        raise


def main() -> int:
    sys.path.insert(0, str(RUNTIME / "site-packages"))
    current_stage = "inputs"
    owner = None
    descriptor = None

    def progress(name: str) -> None:
        nonlocal current_stage
        current_stage = name
        print(f"owner-resume stage={name}", flush=True)

    try:
        if len(sys.argv) != 1 or os.geteuid() != ROOT_UID:
            raise ValueError("resume_protected_entry_required")
        inputs = json.loads(Path(__file__).with_name("config.json").read_bytes())
        validate_inputs(inputs)
        progress("load_frozen_owner")
        owner = load_owner(inputs)
        ledger = owner.open_ledger()
        ledger._protected(Path(__file__).absolute())
        ledger._protected(Path(__file__).with_name("config.json"))
        progress("lock")
        descriptor = acquire_lock(ledger)
        resume_after_backup(inputs, owner, progress)
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        category = (
            str(error)
            if isinstance(error, ValueError)
            and re.fullmatch("[a-z][a-z0-9_]{1,100}", str(error))
            else "resume_operation_failed"
        )
        print(
            f"owner-resume refused stage={current_stage} reason={category}; "
            "保留全部检查点，不自动回滚或重建。",
            file=sys.stderr,
            flush=True,
        )
        if owner is not None:
            try:
                owner.write_report(
                    Path(__file__).with_name("failure.json"),
                    {
                        "status": "failed",
                        "stage": current_stage,
                        "reason": category,
                        "recorded_at": datetime.now(UTC).isoformat(),
                    },
                )
            except (OSError, ValueError):
                print("owner-resume failure_checkpoint_unavailable", file=sys.stderr)
        return 2
    finally:
        if descriptor is not None:
            os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
