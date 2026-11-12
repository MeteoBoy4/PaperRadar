"""只读执行事实诊断;不导入执行编排、认证或 attempt 资源。"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import typer

from paper_radar.config import (
    ConfigError,
    load_config_snapshot,
    resolve_config_snapshot_reference,
    screening_model,
)
from paper_radar.config.adapters import PiAdapter
from paper_radar.config.compile import MaterialKind, RuntimeConfigSnapshot
from paper_radar.config.owner_waiver import (
    OWNER_WAIVER_NOTICE,
    OWNER_WAIVER_REASON,
    OwnerWaiverError,
    owner_waiver,
)
from paper_radar.doctor.admission import projection_checks
from paper_radar.doctor.cli import _show
from paper_radar.doctor.service import Check, Result, basic_checks
from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.types import (
    AdmissionUse,
    CallSite,
    Consumer,
    ThinkingLevel,
)
from paper_radar.llm.models import PROTOCOL_PROFILES
from paper_radar.pi_execution.admission import (
    EvidenceBinding,
    load_admission_evidence,
    sampling_mapping_reason,
)
from paper_radar.pi_execution.current_binding import (
    build_admission_request,
    diagnose_observation_failure,
    recheck_admission_request,
)
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import (
    ISOLATION_POLICY_VERSION,
    isolation_capability,
)
from paper_radar.pi_execution.placement import check_placement_readiness
from paper_radar.pi_execution.resources import (
    EXECUTION_CWD,
    LAUNCH_POLICY_VERSION,
    check_auth_mode,
    check_credentials_metadata,
    check_cwd,
    check_system_prompt,
    expected_cwd_section,
)
from paper_radar.pi_supply import SupplyError, doctor_supply


def _binding(
    snapshot: RuntimeConfigSnapshot, supply_id: str, install_id: str
) -> EvidenceBinding | None:
    """仅投影已验证 snapshot;不伪造 StageInput、任务或 CallDescription。"""
    adapter = snapshot.adapters["screening"]
    selected = snapshot.adapter_selections.get("screening")
    model = screening_model(snapshot)
    if (
        adapter is None
        or selected is None
        or model is None
        or snapshot.model_slots["screening"] != "configured"
    ):
        return None
    declared = PiAdapter.model_validate_json(
        snapshot.materials[(MaterialKind.ADAPTER, "pi-rpc", selected)].config_json
    )
    if declared.pi_version not in PROTOCOL_PROFILES:
        raise ExecutionError("protocol_unsupported")
    check_auth_mode(model["provider"], "chatgpt_subscription")
    check_system_prompt(adapter.system_prompt_text.encode("utf-8"))
    return EvidenceBinding(
        supply_id=supply_id,
        install_id=install_id,
        launch_policy_version=LAUNCH_POLICY_VERSION,
        isolation_policy_version=ISOLATION_POLICY_VERSION,
        cwd_section=expected_cwd_section(),
        provider=model["provider"],
        model=model["model"],
        thinking_level=adapter.thinking_level,
        sampling=model.get("sampling", "explicit"),
        temperature=model.get("temperature"),
        top_p=model.get("top_p"),
        protocol_profile=PROTOCOL_PROFILES[declared.pi_version],
        auth_mode="chatgpt_subscription",
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _admission_checks(
    database: Path, binding: EvidenceBinding, credentials_dir: Path
) -> tuple[Check, ...]:
    sampling_reason = sampling_mapping_reason(binding)
    if sampling_reason is not None:
        raise ExecutionError(sampling_reason)
    try:
        level = ThinkingLevel(binding.thinking_level)
    except ValueError:
        return (
            Check(
                "admission",
                Result.INVALID,
                "admission_use_undefined",
                "当前档位没有登记用途；请显式选择已登记档位，不借用其他格证据。",
            ),
        )
    waiver = owner_waiver(database, now=_utc_now())
    if waiver.enabled:
        return (
            Check("admission", Result.PASSED, OWNER_WAIVER_REASON, OWNER_WAIVER_NOTICE),
            Check(
                "admission_evidence",
                Result.NOT_ASSESSED,
                "evidence_not_assessed",
                "未评估证据；豁免不证明任何分项 verified。",
                required=False,
            ),
        )
    checks: list[Check] = []
    for consumer in (Consumer.BOUNDARY, Consumer.VALUE):
        use = AdmissionUse(CallSite.SCREENING, consumer, level)
        try:
            request = build_admission_request(
                database,
                binding,
                use=use,
                credentials_dir=credentials_dir,
                now=_utc_now(),
            )
            request = replace(request, evidence_after=waiver.strict_since)
            projection = load_admission_evidence(request, now=_utc_now())
            if projection.decision.executable:
                recheck_admission_request(request, now=_utc_now())
        except LedgerError as error:
            projection = diagnose_observation_failure(
                database,
                binding,
                use=use,
                credentials_dir=credentials_dir,
                now=_utc_now(),
                error=error,
            )
        checks.extend(projection_checks(projection))
    return tuple(checks)


def execution_checks(
    database: Path, snapshot_reference: str, credentials_dir: Path
) -> tuple[Check, ...]:
    """必要项决定汇总;披露项保留原状态,不创建执行或账本事实。"""
    checks = list(basic_checks(database))
    if any(check.result is not Result.PASSED for check in checks):
        return tuple(checks)
    try:
        waiver = owner_waiver(database, now=_utc_now())
    except OwnerWaiverError as error:
        checks.append(
            Check(
                "owner_waiver",
                Result.INVALID,
                error.reason,
                "核对所有者动作记录的格式、哈希及版本链；修复前保持拒绝。",
            )
        )
        return tuple(checks)
    checks.append(
        Check(
            "owner_waiver",
            Result.PASSED,
            OWNER_WAIVER_REASON if waiver.enabled else "owner_waiver_disabled",
            OWNER_WAIVER_NOTICE if waiver.enabled else "证据前提严格路径。",
        )
    )
    try:
        snapshot = load_config_snapshot(
            database, resolve_config_snapshot_reference(database, snapshot_reference)
        )
    except ConfigError as error:
        checks.append(
            Check(
                "selection",
                Result.INVALID,
                error.reason.value,
                "请用 config snapshots list 核实显式快照；修复损坏引用。",
            )
        )
        return tuple(checks)
    checks.append(
        Check(
            "selection",
            Result.PASSED,
            "configuration_valid",
            "显式历史快照有效；未保存新事实。",
        )
    )
    try:
        report = doctor_supply(database, snapshot_reference)
    except SupplyError as error:
        checks.append(
            Check(
                "supply",
                Result.INVALID,
                error.reason,
                "请用 doctor --scope pi-supply 核实显式供给。",
            )
        )
    else:
        if report.blockers:
            for supply_reason in report.blockers:
                state = (
                    Result.MISSING
                    if supply_reason
                    in {"selection_missing", "install_unavailable", "adapter_missing"}
                    else Result.INVALID
                )
                checks.append(
                    Check(
                        "supply",
                        state,
                        supply_reason,
                        "请用 doctor --scope pi-supply 核实供给；"
                        "缺实例时显式 rebuild 后 activate。",
                    )
                )
        else:
            checks.append(
                Check(
                    "supply",
                    Result.PASSED,
                    "supply_valid",
                    "仅表示所选供给现场通过；不授予执行资格。",
                )
            )
        if report.current is not None:
            try:
                binding = _binding(
                    snapshot, report.current.supply_id, report.current.install_id
                )
                if binding is None:
                    checks.append(
                        Check(
                            "admission",
                            Result.MISSING,
                            "screening_configuration_missing",
                            "先配置显式 Screening 模型槽和 adapter；不推定其他槽资格。",
                        )
                    )
                else:
                    checks.extend(_admission_checks(database, binding, credentials_dir))
            except (ExecutionError, SupplyError, OwnerWaiverError) as error:
                checks.append(
                    Check(
                        "admission",
                        Result.INVALID,
                        error.reason,
                        "核对模型、采样、协议和本地绑定；修复前保持阻断。",
                    )
                )
        else:
            checks.append(
                Check(
                    "admission",
                    Result.MISSING,
                    "evidence_missing",
                    "先显式激活供给；再由共享权威核对当前 Cwd/Live 分项资格。",
                )
            )
    try:
        EXECUTION_CWD.lstat()
    except FileNotFoundError:
        checks.append(
            Check(
                "cwd",
                Result.MISSING,
                "cwd_missing",
                "交 Cwd 准备并现场验收唯一白名单目录及祖先资源。",
            )
        )
    except OSError:
        checks.append(
            Check(
                "cwd",
                Result.INVALID,
                "cwd_invalid",
                "交 Cwd 核实白名单目录及祖先权限。",
            )
        )
    else:
        try:
            check_cwd()
        except ExecutionError as error:
            checks.append(
                Check(
                    "cwd",
                    Result.INVALID,
                    error.reason,
                    "交 Cwd 核实空目录、祖先资源与现场隔离。",
                )
            )
        else:
            checks.append(
                Check(
                    "cwd",
                    Result.PASSED,
                    "cwd_metadata_valid",
                    "仅空目录与路径形状通过；现场隔离仍交 Cwd。",
                )
            )
    try:
        credentials_dir.lstat()
        (credentials_dir / "auth.json").lstat()
    except FileNotFoundError:
        checks.append(
            Check(
                "credentials_metadata",
                Result.MISSING,
                "credentials_missing",
                "由所有者准备专用凭据目录及 auth.json；doctor 不读取内容。",
            )
        )
    except OSError:
        checks.append(
            Check(
                "credentials_metadata",
                Result.INVALID,
                "credentials_invalid",
                "核实专用凭据目录权限和文件类型；不输出内容或路径。",
            )
        )
    else:
        try:
            check_credentials_metadata(credentials_dir)
        except ExecutionError as error:
            checks.append(
                Check(
                    "credentials_metadata",
                    Result.INVALID,
                    error.reason,
                    "核实 owner、0700、无链接与 auth.json 文件类型。",
                )
            )
        else:
            checks.append(
                Check(
                    "credentials_metadata",
                    Result.PASSED,
                    "metadata_valid",
                    "仅凭据元数据通过；认证内容、有效期和计划未验。",
                )
            )
    try:
        isolation_capability()
    except ExecutionError as error:
        checks.append(
            Check(
                "isolation",
                Result.INVALID,
                error.reason,
                "交 Cwd 配置最低内核能力；不能无隔离降级。",
            )
        )
    else:
        checks.append(
            Check(
                "isolation",
                Result.PASSED,
                "isolation_capability",
                "仅本机 Landlock 能力通过；真实 Pi/TLS/DNS 和主机出站交 Cwd/Live。",
            )
        )
    try:
        if not waiver.enabled:
            check_placement_readiness()
    except ExecutionError as error:
        checks.append(
            Check(
                "placement",
                Result.INVALID,
                error.reason,
                "放置不可用或不符；核对 user manager/linger、锚定与受保护规则目标。",
            )
        )
    else:
        checks.append(
            Check(
                "placement",
                Result.NOT_ASSESSED if waiver.enabled else Result.PASSED,
                "owner_waiver_placement_optional"
                if waiver.enabled
                else "placement_ready",
                "豁免模式不要求放置或私有 resolver；使用宿主 DNS。"
                if waiver.enabled
                else "只读锚定检查通过；实际子进程仍须逐调用双阶段核验。",
                required=not waiver.enabled,
            )
        )
    for name, reason, step in (
        (
            "credential_roots",
            "credential_roots_not_assessed",
            "执行服务须按显式四根核对凭据隔离；诊断没有业务/配置/材料根选择，不推定通过。",
        ),
        (
            "authentication",
            "authentication_not_assessed",
            "交 Live 核实订阅刷新、token 通道/前缀、有效期和额度；"
            "doctor 不刷新或解析凭据。",
        ),
        (
            "model_parameters",
            "model_parameters_not_assessed",
            "交 Live 核实计划模型权限、采样映射及全部 DERIVED；不调用模型。",
        ),
    ):
        checks.append(Check(name, Result.NOT_ASSESSED, reason, step, required=False))
    return tuple(checks)


def diagnose_execution(database: Path, snapshot: str, credentials_dir: Path) -> None:
    checks = execution_checks(database, snapshot, credentials_dir)
    passed = all(check.result is Result.PASSED for check in checks if check.required)
    typer.echo(
        f"scope=pi-exec result={'passed' if passed else 'failed'} "
        f"executable={'true' if passed else 'false'}"
    )
    typer.echo(
        "diagnostic_scope=screening_current_thinking_level "
        "Screening 当前档位 boundary/value 分别诊断；Read 此命令未选择、未诊断。"
    )
    for check in checks:
        _show(check)
    if not passed:
        raise typer.Exit(2)
