"""B 显式无 prompt 探测;复用认证、准入与固定安装,不登记业务事实。"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

from paper_radar.config import (
    ConfigError,
    StageName,
    load_config_snapshot,
    project_config,
    resolve_config_snapshot_reference,
)
from paper_radar.config.adapters import PiAdapter
from paper_radar.config.compile import MaterialKind
from paper_radar.experiment.egress import (
    Grant,
    Stage,
    require_egress_authorization,
    selected_grants,
)
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.live_evidence.types import (
    AdmissionUse,
    CallSite,
    Consumer,
    ThinkingLevel,
)
from paper_radar.llm.models import PROTOCOL_PROFILES, MappingDescription
from paper_radar.llm.rpc import RpcMappingResult, probe_mapping
from paper_radar.llm.rpc_types import RpcReason
from paper_radar.pi_execution.admission import (
    EvidenceBinding,
    bind_description,
    sampling_mapping_reason,
)
from paper_radar.pi_execution.admission_checkpoints import AdmissionCheckpoints
from paper_radar.pi_execution.admission_guard import AdmissionGuard
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.launcher import LaunchIdentity, prepare_launch
from paper_radar.pi_execution.resources import ExecutionRoots, expected_cwd_section
from paper_radar.pi_supply import (
    SupplyError,
    activation_history,
    available_installs,
    show_supply,
)

# 公开启动常量;不从 Profile、业务 Prompt 或论文材料取启动参数。
MAPPING_SYSTEM_PROMPT = b"PaperRadar model mapping probe. No user prompt is sent.\n"


class MappingReceipt(TypedDict):
    slot: Literal["screening", "reading"]
    state: Literal["mapping_settable", "failed"]
    reason: Literal["mapping_state_matched"] | RpcReason


@dataclass(frozen=True)
class _Plan:
    description: MappingDescription
    identity: LaunchIdentity
    grants: tuple[Grant, ...]


def _binding(plan: _Plan, identity: LaunchIdentity) -> EvidenceBinding:
    return bind_description(
        plan.description,
        supply_id=identity.supply_id,
        install_id=identity.install_id,
        launch_policy_version=identity.launch_policy_version,
        isolation_policy_version=identity.isolation_policy_version,
        cwd_section=expected_cwd_section(),
        auth_mode=identity.auth_mode,
    )


def _egress(root: ExperimentRoot, plan: _Plan) -> None:
    root.require()
    for grant in plan.grants:
        require_egress_authorization(
            root,
            stage=grant.stage,
            provider=grant.provider,
            model=grant.model,
            categories=grant.categories,
        )


def probe_models(
    root: ExperimentRoot,
    *,
    snapshot: str,
    credentials_dir: Path,
    material_root: Path,
    install_root: Path,
    slot: str | None = None,
) -> list[MappingReceipt]:
    """所有计划先核对;每槽认证前再次核对授权与共享准入。"""
    root.require()
    if slot not in {None, "screening", "reading"}:
        raise ExecutionError("snapshot_invalid")
    try:
        selected = load_config_snapshot(
            root.database, resolve_config_snapshot_reference(root.database, snapshot)
        )
        history = activation_history(root.database)
        if not history or history[-1].snapshot_id != selected.snapshot_id:
            raise ExecutionError("install_unavailable")
        current = history[-1]
        record = show_supply(root.database, current.supply_id)
        installs = available_installs(root.database, current.supply_id)
        instance = next(
            (item for item in installs if item.install_id == current.install_id), None
        )
        if instance is None or instance.root.resolve() != install_root.resolve():
            raise ExecutionError("install_unavailable")
        plans = []
        slots: tuple[Literal["screening", "reading"], ...] = (
            ("screening", "reading")
            if slot is None
            else ("screening",)
            if slot == "screening"
            else ("reading",)
        )
        for name in slots:
            adapter = selected.adapters[name]
            version = selected.adapter_selections.get(name)
            if adapter is None or version is None:
                raise ExecutionError("snapshot_invalid")
            declared = PiAdapter.model_validate_json(
                selected.materials[
                    (MaterialKind.ADAPTER, "pi-rpc", version)
                ].config_json
            )
            profile = PROTOCOL_PROFILES.get(declared.pi_version)
            if profile is None or declared.pi_version != record.manifest.pi_version:
                raise ExecutionError("protocol_unsupported")
            stages: list[Stage] = (
                ["read"] if name == "reading" else ["boundary", "value"]
            )
            grants = selected_grants(selected, stages)
            model = json.loads(
                project_config(selected).projections[StageName(stages[0])].payload_json
            )["components"]["model"]
            description = MappingDescription(
                name,
                selected.snapshot_id,
                declared.pi_version,
                profile,
                grants[0].provider,
                grants[0].model,
                adapter.thinking_level,
                MAPPING_SYSTEM_PROMPT,
                sampling=model.get("sampling", "explicit"),
                temperature=model.get("temperature"),
                top_p=model.get("top_p"),
            )
            identity = LaunchIdentity.for_install(
                current.supply_id,
                current.install_id,
                record.manifest,
                auth_mode="chatgpt_subscription",
            )
            plan = _Plan(description, identity, grants)
            reason = sampling_mapping_reason(_binding(plan, identity))
            if reason is not None:
                raise ExecutionError(reason)
            _egress(root, plan)
            plans.append(plan)
    except ConfigError:
        raise ExecutionError("snapshot_invalid") from None
    except SupplyError:
        raise ExecutionError("install_unavailable") from None
    roots = ExecutionRoots(root.data_root, root.config, material_root, install_root)
    result: list[MappingReceipt] = []
    for plan in plans:
        binding = _binding(plan, plan.identity)
        checkpoints = []
        for grant in plan.grants:
            try:
                use = AdmissionUse(
                    CallSite.READ
                    if plan.description.slot == "reading"
                    else CallSite.SCREENING,
                    Consumer(grant.stage),
                    ThinkingLevel(plan.description.thinking_level),
                )
            except ValueError:
                raise ExecutionError("evidence_missing") from None
            checkpoint = AdmissionCheckpoints(
                root.database,
                credentials_dir,
                AdmissionGuard(use),
                lambda: datetime.now(UTC),
            )
            checkpoints.append((checkpoint, checkpoint.before_prepare(binding)))
        _egress(root, plan)
        with prepare_launch(
            root.database,
            plan.description,
            roots=roots,
            credentials_dir=credentials_dir,
            auth_mode="chatgpt_subscription",
            placement_required=not checkpoints[0][0].owner_waived,
        ) as prepared:
            actual_binding = _binding(plan, prepared.identity)
            if actual_binding != binding:
                raise ExecutionError("evidence_mismatch")
            for checkpoint, original in checkpoints:
                checkpoint.after_prepare(original, actual_binding)
            _egress(root, plan)
            outcome = probe_mapping(plan.description, prepared)
        success = isinstance(outcome, RpcMappingResult)
        reason_code: Literal["mapping_state_matched"] | RpcReason = (
            "mapping_state_matched"
            if isinstance(outcome, RpcMappingResult)
            else outcome.reason
        )
        result.append(
            {
                "slot": plan.description.slot,
                "state": "mapping_settable" if success else "failed",
                "reason": reason_code,
            }
        )
        if not success:
            break
    return result
