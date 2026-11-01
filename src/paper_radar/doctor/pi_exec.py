"""只读执行事实诊断;不导入执行编排、认证或 attempt 资源。"""

import json
from pathlib import Path

import typer

from paper_radar.config import (
    ConfigError,
    StageName,
    load_config_snapshot,
    project_config,
    resolve_config_snapshot_reference,
)
from paper_radar.config.adapters import PiAdapter
from paper_radar.config.compile import MaterialKind, RuntimeConfigSnapshot
from paper_radar.doctor.cli import _show
from paper_radar.doctor.service import Check, Result, basic_checks
from paper_radar.llm.models import PROTOCOL_PROFILES
from paper_radar.pi_execution.admission import EvidenceBinding, admit, read_evidence
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import (
    ISOLATION_POLICY_VERSION,
    isolation_capability,
)
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
    model = json.loads(
        project_config(snapshot).projections[StageName.BOUNDARY].payload_json
    )["components"]["model"]
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


def execution_checks(
    database: Path, snapshot_reference: str, credentials_dir: Path
) -> tuple[Check, ...]:
    """每项独立披露;所有返回项均为必要项,passed 只表示该项离线成立。"""
    checks = list(basic_checks(database))
    if any(check.result is not Result.PASSED for check in checks):
        return tuple(checks)
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
                reason: str | None = (
                    admit(binding, read_evidence(binding))
                    if binding is not None
                    else "screening_configuration_missing"
                )
            except ExecutionError as error:
                reason = error.reason
            state = (
                Result.PASSED
                if reason is None
                else Result.MISSING
                if reason
                in {
                    "screening_configuration_missing",
                    "evidence_missing",
                    "cwd_evidence_missing",
                    "rpc_evidence_missing",
                    "model_evidence_missing",
                }
                else Result.INVALID
            )
            checks.append(
                Check(
                    "admission",
                    state,
                    reason or "admitted",
                    "现场隔离证据交 Cwd；DERIVED、RPC、订阅模型和参数证据交 Live。"
                    "缺证据保持阻断。",
                )
            )
        else:
            checks.append(
                Check(
                    "admission",
                    Result.MISSING,
                    "evidence_missing",
                    "先显式激活供给；Cwd/Live 尚无产品证据来源。",
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
        checks.append(Check(name, Result.NOT_ASSESSED, reason, step))
    return tuple(checks)


def diagnose_execution(database: Path, snapshot: str, credentials_dir: Path) -> None:
    checks = execution_checks(database, snapshot, credentials_dir)
    passed = all(check.result is Result.PASSED for check in checks)
    typer.echo(
        f"scope=pi-exec result={'passed' if passed else 'failed'} "
        f"executable={'true' if passed else 'false'}"
    )
    for check in checks:
        _show(check)
    if not passed:
        raise typer.Exit(2)
