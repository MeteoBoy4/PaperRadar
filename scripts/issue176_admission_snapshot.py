#!/usr/bin/env python3
"""正式准入只读采样;只读已选择模型/adapter元数据,不读Profile/Prompt/全文。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.config.adapters import PiAdapter
from paper_radar.config.schema import ModelsDocument
from paper_radar.doctor.admission import admission_rows, render_admission_fragment
from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.lifecycle import use_for_id
from paper_radar.live_evidence.service import unavailable_projection
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.admission_guard import AdmissionGuard
from paper_radar.pi_execution.current_binding import (
    build_admission_request,
    recheck_admission_request,
)
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
from paper_radar.pi_execution.resources import (
    LAUNCH_POLICY_VERSION,
    expected_cwd_section,
)
from paper_radar.pi_protocol import PROTOCOL_PROFILES
from paper_radar.pi_supply import activation_history
from paper_radar.storage.database import DatabaseMode, open_database


def metadata_bindings(database: Path) -> tuple[str, dict[str, EvidenceBinding]]:
    history = activation_history(database)
    if not history:
        raise ValueError("snapshot_selection_missing")
    selected = history[-1]
    engine = open_database(database, mode=DatabaseMode.READ_ONLY)
    try:
        with engine.connect() as connection:
            # SQLite只投影三个selector,不把snapshot/材料正文读入Python。
            selectors = connection.execute(
                text(
                    "SELECT json_extract(payload_json,'$.selectors.models'),"
                    "json_extract(payload_json,'$.selectors.adapters.screening'),"
                    "json_extract(payload_json,'$.selectors.adapters.reading') "
                    "FROM runtime_config_snapshots WHERE snapshot_id=:snapshot"
                ),
                {"snapshot": selected.snapshot_id},
            ).one()

            def material(kind: str, name: str, version: str) -> Any:
                raw_sha, raw = connection.execute(
                    text(
                        "SELECT c.raw_sha256,c.raw_content FROM config_versions c "
                        "JOIN snapshot_version_refs r ON c.kind=r.kind "
                        "AND c.name=r.name "
                        "AND c.declared_version=r.declared_version "
                        "WHERE r.snapshot_id=:snapshot AND r.kind=:kind "
                        "AND r.name=:name "
                        "AND r.declared_version=:version"
                    ),
                    {
                        "snapshot": selected.snapshot_id,
                        "kind": kind,
                        "name": name,
                        "version": version,
                    },
                ).one()
                if hashlib.sha256(raw).hexdigest() != raw_sha:
                    raise ValueError("snapshot_metadata_integrity")
                return yaml.safe_load(raw)

            models = ModelsDocument.model_validate(
                material("models", "models", selectors[0])
            ).root
            bindings = {}
            for slot, version in zip(
                ("screening", "reading"), selectors[1:], strict=True
            ):
                adapter = PiAdapter.model_validate(
                    material("adapter", "pi-rpc", version)
                )
                model = models.screening if slot == "screening" else models.reading
                if model is None or model.provider is None or model.model is None:
                    raise ValueError("model_slot_missing")
                bindings[slot] = EvidenceBinding(
                    supply_id=selected.supply_id,
                    install_id=selected.install_id,
                    launch_policy_version=LAUNCH_POLICY_VERSION,
                    isolation_policy_version=ISOLATION_POLICY_VERSION,
                    cwd_section=expected_cwd_section(),
                    provider=model.provider,
                    model=model.model,
                    thinking_level=adapter.thinking_level,
                    sampling=getattr(model, "sampling", "explicit"),
                    temperature=model.temperature,
                    top_p=model.top_p,
                    protocol_profile=PROTOCOL_PROFILES[adapter.pi_version],
                    auth_mode="chatgpt_subscription",
                )
    finally:
        engine.dispose()
    return selected.snapshot_id, bindings


def sample(database: Path, credentials_dir: Path) -> dict[str, Any]:
    snapshot_id, bindings = metadata_bindings(database)
    reports = []
    for consumer, slot in (
        ("boundary", "screening"),
        ("value", "screening"),
        ("read", "reading"),
    ):
        binding = bindings[slot]
        use_id = f"{consumer}-{binding.thinking_level}"
        use = use_for_id(use_id)
        observed = datetime.now(UTC)
        recheck_reason = None
        try:
            request = build_admission_request(
                database,
                binding,
                use=use,
                credentials_dir=credentials_dir,
                now=observed,
            )
            guard = AdmissionGuard(use)
            try:
                projection = guard.check(request, now=datetime.now(UTC))
            except ExecutionError:
                if guard.projection is None:
                    raise
                projection = guard.projection
            try:
                recheck_admission_request(request, now=datetime.now(UTC))
            except LedgerError as error:
                recheck_reason = error.category
                projection = unavailable_projection(use, error)
        except LedgerError as error:
            projection = unavailable_projection(use, error)
        reports.append(
            {
                "use_id": use_id,
                "sampled_at": observed.isoformat(),
                "executable": projection.decision.executable,
                "reason": [reason.token for reason in projection.decision.reasons],
                "recheck_reason": recheck_reason,
                "active": [
                    row.capability.value
                    for row in admission_rows(projection)
                    if row.evidence_active and not row.revoked
                ],
                "qualified": [
                    row.capability.value
                    for row in admission_rows(projection)
                    if row.qualified
                ],
                "doctor_fragment": render_admission_fragment(projection),
            }
        )
    return {"snapshot_id": snapshot_id, "reports": reports, "read_only": True}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="只读正式准入采样，不刷新凭据/领取/收紧或打点。"
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--credentials-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = sample(args.database, args.credentials_dir)
    except (OSError, ValueError, SQLAlchemyError, yaml.YAMLError):
        parser.exit(
            2,
            "只读采样拒绝 [sampling_metadata_unavailable]；"
            "请核对现有选择/模型槽与受保护观察，不自动修复。\n",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
